"""Spider_XHS wrapper for data collection."""

import json
import ipaddress
import os
import re
import socket
import subprocess
import sys
import time
import warnings
import threading
from pathlib import Path
from urllib.parse import quote, urlparse, parse_qs

from backend.config import settings
from backend.utils.cookie import cookies_array_to_dict

_SDK_LOCK = threading.RLock()

# Disable SSL warnings (Spider_XHS calls XHS APIs behind GFW).
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Force TLS 1.2 — XHS edge servers don't handle TLS 1.3 well behind GFW.
import ssl
try:
    _orig_create_default = ssl.create_default_context
    def _tls12_context(*args, **kwargs):
        ctx = _orig_create_default(*args, **kwargs)
        ctx.minimum_version = ssl.TLSVersion.TLSv1_2
        ctx.maximum_version = ssl.TLSVersion.TLSv1_2
        return ctx
    ssl.create_default_context = _tls12_context
except AttributeError:
    pass  # older Python, skip

import requests

# Spider_XHS uses the module-level requests helpers. Keep its existing relaxed
# certificate behavior, but respect the user's proxy/VPN settings. If a stale
# proxy is configured and cannot be reached, retry that request once directly.
_original_request = requests.Session.request


def _winhttp_proxy_url() -> str:
    """Return a reachable local WinHTTP proxy without changing system settings."""
    if os.name != "nt":
        return ""
    try:
        completed = subprocess.run(
            ["netsh", "winhttp", "show", "proxy"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=3,
            check=False,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except (OSError, subprocess.SubprocessError):
        return ""
    candidates = re.findall(
        r"(?:https?\s*=\s*)?((?:127\.0\.0\.1|localhost):\d{2,5})",
        completed.stdout or "",
        flags=re.IGNORECASE,
    )
    for candidate in candidates:
        host, port_text = candidate.rsplit(":", 1)
        try:
            with socket.create_connection((host, int(port_text)), timeout=0.4):
                return f"http://{candidate}"
        except (OSError, ValueError):
            continue
    return ""


def _auto_proxy_for_url(url: str) -> str:
    host = (urlparse(str(url or "")).hostname or "").lower()
    if host != "xiaohongshu.com" and not host.endswith(".xiaohongshu.com"):
        return ""
    if not _uses_proxy_fake_ip(_resolved_xhs_addresses()):
        return ""
    return _winhttp_proxy_url()


def _patched_request(self, method, url, **kwargs):
    kwargs.setdefault('verify', False)
    if not kwargs.get('proxies'):
        proxy_url = _auto_proxy_for_url(url)
        if proxy_url:
            kwargs['proxies'] = {'http': proxy_url, 'https': proxy_url}
    try:
        return _original_request(self, method, url, **kwargs)
    except requests.exceptions.ProxyError:
        direct_kwargs = dict(kwargs)
        direct_kwargs['proxies'] = {}
        original_trust_env = self.trust_env
        self.trust_env = False
        try:
            return _original_request(self, method, url, **direct_kwargs)
        finally:
            self.trust_env = original_trust_env


requests.Session.request = _patched_request


_NETWORK_ERROR_MARKERS = (
    "newconnectionerror",
    "max retries exceeded",
    "connection refused",
    "connection aborted",
    "connection reset",
    "failed to establish a new connection",
    "name resolution",
    "getaddrinfo failed",
    "proxyerror",
    "proxy error",
    "sslerror",
    "certificate verify failed",
    "timed out",
    "timeout",
)


def _is_network_error(message: str) -> bool:
    lower = str(message or "").lower()
    return any(marker in lower for marker in _NETWORK_ERROR_MARKERS)


def _resolved_xhs_addresses() -> list[str]:
    try:
        rows = socket.getaddrinfo("edith.xiaohongshu.com", 443, type=socket.SOCK_STREAM)
    except OSError:
        return []
    return sorted({row[4][0] for row in rows if row[4]})


def _uses_proxy_fake_ip(addresses: list[str]) -> bool:
    fake_ip_network = ipaddress.ip_network("198.18.0.0/15")
    for address in addresses:
        try:
            if ipaddress.ip_address(address) in fake_ip_network:
                return True
        except ValueError:
            continue
    return False


def _network_failure_message(raw_message: str) -> str:
    addresses = _resolved_xhs_addresses()
    lower = str(raw_message or "").lower()
    if _uses_proxy_fake_ip(addresses):
        return (
            "采集网络连接失败：检测到代理/VPN使用的虚拟网络地址。"
            "如果正在使用 Clash、VPN 或加速器，请先保持它正常开启后重试；"
            "如果已经关闭，请彻底退出代理软件并重新连接网络后再试。"
        )
    if "proxy" in lower:
        return (
            "采集网络连接失败：当前系统代理无法连接。"
            "请打开正在使用的代理/VPN，或在 Windows 网络设置中关闭已经失效的代理后重试。"
        )
    if "ssl" in lower or "certificate" in lower:
        return (
            "采集网络连接失败：安全连接没有建立成功。"
            "请确认电脑时间正确，暂时关闭 HTTPS 扫描类安全软件后重试。"
        )
    return (
        "采集网络连接失败：暂时无法连接小红书。"
        "请先在当前浏览器打开小红书主页确认可以正常访问，然后等待 30 秒再重试。"
    )


class Collector:
    """High-level wrapper around Spider_XHS SDK.

    Requires Spider_XHS to be cloned at `settings.spider_xhs_dir`.
    """

    def __init__(self):
        self.spider_xhs_path = Path(settings.spider_xhs_dir)
        self._available = self.spider_xhs_path.exists()
        self._api = None

    def _ensure_available(self):
        if not self._available:
            raise RuntimeError(
                f"Spider_XHS not found at {self.spider_xhs_path}. "
                "Clone it first:\n"
                f"  git clone https://github.com/cv-cat/Spider_XHS.git "
                f"{self.spider_xhs_path}"
            )

    def _ensure_api(self, cookies_str: str):
        """Ensure Spider_XHS API is initialized (CWD set correctly for JS requires)."""
        self._ensure_available()
        # Spider_XHS JS files use relative require('./static/*.js') via execjs,
        # so we must chdir to spider_xhs/ before they are imported/compiled.
        self._spider_cwd = str(self.spider_xhs_path)
        if str(self.spider_xhs_path) not in sys.path:
            sys.path.insert(0, str(self.spider_xhs_path))
        self._cookies = cookies_str

    def _call(self, fn, *args, **kwargs):
        """Run an API call with CWD set to spider_xhs/ for JS require resolution."""
        with _SDK_LOCK:
            return self._call_locked(fn, *args, **kwargs)

    def _call_locked(self, fn, *args, **kwargs):
        if self._api is None:
            _orig = os.getcwd()
            os.chdir(self._spider_cwd)
            try:
                from apis.xhs_pc_apis import XHS_Apis
                self._api = XHS_Apis()
            finally:
                os.chdir(_orig)

        _orig = os.getcwd()
        os.chdir(self._spider_cwd)
        try:
            return fn(*args, **kwargs)
        finally:
            os.chdir(_orig)

    def collect_all_notes(self, profile_url: str, cookies_input) -> dict:
        """Collect all notes and profile info for a given profile URL.

        Args:
            profile_url: Full XHS profile URL
            cookies_input: Cookie array (list) or string

        Returns:
            dict with keys:
              - all_notes: list of note dicts
              - profile: dict with nickname, user_id, follower_count, bio
              - contents: dict of note_id -> {tags, content_text} (optional)
        """
        try:
            cookies_str = cookies_array_to_dict(cookies_input)
        except ValueError as e:
            raise RuntimeError(str(e))

        if not cookies_str:
            raise RuntimeError("Cookie 内容为空，请检查 Cookie 是否正确导入")

        self._ensure_api(cookies_str)

        # Get all notes — wrapped in chdir so execjs resolves JS require paths
        def get_notes():
            return self._api.get_user_all_notes(profile_url, self._cookies)
        success, msg, notes_data = False, "", None
        for attempt in range(3):
            success, msg, notes_data = self._call(get_notes)
            if success or not _is_network_error(msg):
                break
            if attempt < 2:
                time.sleep(1 + attempt)
        if not success:
            if _is_network_error(msg):
                raise RuntimeError(_network_failure_message(msg))
            raise RuntimeError(f"Failed to collect notes: {msg}")

        notes_data = list(notes_data or [])

        # Normalize notes to match existing schema
        all_notes = []
        contents = {}
        seen_note_ids = set()
        duplicate_count = 0
        for item in notes_data:
            note_id = item.get("note_id", "")
            if note_id:
                if note_id in seen_note_ids:
                    duplicate_count += 1
                    continue
                seen_note_ids.add(note_id)
            if len(all_notes) >= settings.max_notes_per_task:
                break
            interact_info = item.get("interact_info") or {}
            note_type = item.get("type", "normal")
            ranked_type = "video" if note_type == "video" else "normal"
            cover = item.get("cover") or {}
            cover_url = (
                cover.get("url_default")
                or cover.get("url_pre")
                or cover.get("url")
                or ""
            ) if isinstance(cover, dict) else ""

            note = {
                "note_id": note_id,
                "xsec_token": item.get("xsec_token", ""),
                "xsec_source": item.get("xsec_source", "pc_user"),
                "title": item.get("display_title", item.get("title", "")),
                "type": ranked_type,
                "liked_count": str(interact_info.get("liked_count", 0)),
                "sticky": bool(interact_info.get("sticky", False)),
                "time": item.get("time", item.get("publish_time", "")),
                "cover_url": cover_url,
            }
            all_notes.append(note)

            # Build contents map (tags not available in list view)
            contents[note["note_id"]] = {
                "tags": [],
                "content_text": "",
            }

        # Get profile info
        user_id = profile_url.rstrip("/").split("/")[-1].split("?")[0].split("#")[0]
        profile = {
            "nickname": "unknown",
            "user_id": user_id,
            "note_count": len(all_notes),
            "duplicate_note_count": duplicate_count,
        }

        def get_info():
            return self._api.get_user_info(user_id, self._cookies)
        success2, msg2, user_info_raw = self._call(get_info)
        if success2 and user_info_raw:
            user_data = user_info_raw.get("data") or user_info_raw
            basic = user_data.get("basic_info") or {}
            profile["nickname"] = basic.get("nickname", "unknown")
            profile["bio"] = basic.get("desc", "")
            profile["red_id"] = basic.get("red_id", "")
            profile["gender"] = basic.get("gender")
            profile["ip_location"] = basic.get("ip_location", "")
            profile["avatar_url"] = (
                basic.get("imageb")
                or basic.get("image")
                or basic.get("avatar")
                or basic.get("images")
                or ""
            )
            interactions = user_data.get("interactions") or []
            for ix in interactions:
                if ix.get("type") == "follows":
                    profile["following_count"] = int(ix.get("count", 0))
                elif ix.get("type") == "fans":
                    profile["follower_count"] = int(ix.get("count", 0))
                elif ix.get("type") == "interaction":
                    profile["total_interaction"] = int(ix.get("count", 0))
            profile["profile_tags"] = [
                tag.get("name")
                for tag in (user_data.get("tags") or [])
                if isinstance(tag, dict) and tag.get("name")
            ]

        return {"all_notes": all_notes, "profile": profile, "contents": contents}

    def search_users(self, keyword: str, count: int = 10, cookies_input=None) -> list:
        """Search for users by keyword. Returns list of {user_id, nickname, follower_count}."""
        cookies_str = cookies_array_to_dict(cookies_input)
        self._ensure_api(cookies_str)

        def search():
            return self._api.search_some_user(keyword, count, self._cookies)
        success, msg, users = self._call(search)
        if not success or not users:
            return []

        results = []
        for u in (users or []):
            results.append({
                "user_id": u.get("user_id", ""),
                "nickname": u.get("username", ""),
                "follower_count": u.get("follower_count", 0),
                "avatar_url": u.get("avatar", ""),
            })
        return results

    @staticmethod
    def _image_urls(card: dict) -> list[str]:
        urls = []
        for image in card.get("image_list", []) or []:
            if not isinstance(image, dict):
                continue
            candidates = []
            candidates.extend(image.get("info_list") or [])
            candidates.extend(image.get("url_size_large") or []) if isinstance(image.get("url_size_large"), list) else []
            for candidate in candidates:
                if isinstance(candidate, dict):
                    url = candidate.get("url") or candidate.get("url_default")
                else:
                    url = candidate if isinstance(candidate, str) else ""
                if url and url not in urls:
                    urls.append(url)
            direct = image.get("url_default") or image.get("url")
            if direct and direct not in urls:
                urls.append(direct)
        return urls

    @staticmethod
    def _video_url(card: dict) -> str:
        video = card.get("video") or {}
        streams = (((video.get("media") or {}).get("stream") or {}).get("h264") or [])
        for stream in streams:
            if isinstance(stream, dict):
                url = stream.get("master_url") or stream.get("url")
                if url:
                    return url
        origin_key = (video.get("consumer") or {}).get("origin_video_key")
        return f"https://sns-video-bd.xhscdn.com/{origin_key}" if origin_key else ""

    def get_note_detail(self, note_url: str, cookies_input=None) -> dict:
        """Get the complete public detail currently exposed by Spider_XHS."""
        cookies_str = cookies_array_to_dict(cookies_input)
        self._ensure_api(cookies_str)

        def get_info():
            return self._api.get_note_info(note_url, self._cookies)
        success, msg, note = self._call(get_info)
        if not success:
            return {"ok": False, "reason": msg or "detail unavailable"}
        try:
            card = (note.get("data", {}) or {}).get("items", [{}])[0].get("note_card", {})
        except Exception:
            card = {}
        if not card:
            return {"ok": False, "reason": "empty note card"}
        interact = card.get("interact_info") or {}
        tags = []
        for tag in card.get("tag_list", []) or []:
            name = tag.get("name") if isinstance(tag, dict) else str(tag)
            if name:
                tags.append(name)
        image_urls = self._image_urls(card)
        video_url = self._video_url(card)
        user = card.get("user") or {}
        return {
            "ok": True,
            "note_id": note_url.rstrip("/").split("/")[-1].split("?")[0],
            "title": card.get("title", ""),
            "tags": tags,
            "content_text": card.get("desc", "") or "",
            "liked_count": interact.get("liked_count"),
            "collected_count": interact.get("collected_count"),
            "comment_count": interact.get("comment_count"),
            "share_count": interact.get("share_count"),
            "content_available": "desc" in card,
            "tags_available": "tag_list" in card,
            "image_urls": image_urls,
            "cover_url": image_urls[0] if image_urls else "",
            "video_url": video_url,
            "video_cover_url": image_urls[0] if video_url and image_urls else "",
            "publish_time": card.get("time", 0),
            "ip_location": card.get("ip_location", ""),
            "author_user_id": user.get("user_id", ""),
            "author_nickname": user.get("nickname", ""),
            "author_avatar_url": user.get("avatar", ""),
        }

    def enrich_note_details(
        self,
        task_dir: Path,
        cookies_input,
        max_count: int = 25,
        delay_seconds: float = 1.2,
        progress_callback=None,
    ) -> dict:
        """Low-frequency detail fetch for selected notes. Never raises for per-note failures."""
        notes_path = task_dir / "all_notes.json"
        results_path = task_dir / "results.json"
        all_notes = json.loads(notes_path.read_text(encoding="utf-8"))
        results = json.loads(results_path.read_text(encoding="utf-8")) if results_path.exists() else {}
        selected_ids = self._select_detail_note_ids(all_notes, results, max_count=max_count)
        note_by_id = {note.get("note_id"): note for note in all_notes if note.get("note_id")}

        existing_by_id = {}
        contents_path = task_dir / "contents.json"
        if contents_path.exists():
            try:
                for item in json.loads(contents_path.read_text(encoding="utf-8")):
                    if item.get("note_id"):
                        existing_by_id[item["note_id"]] = item
            except (ValueError, TypeError):
                existing_by_id = {}

        contents = []
        failures = []
        reused_count = 0
        fetched_count = 0
        for index, note_id in enumerate(selected_ids):
            existing = existing_by_id.get(note_id)
            if (
                existing
                and (existing.get("content_text") or existing.get("text") or existing.get("tags"))
                and "image_urls" in existing
                and "video_url" in existing
                and "comment_count" in existing
            ):
                contents.append(existing)
                reused_count += 1
                if progress_callback:
                    progress_callback(index + 1, len(selected_ids))
                continue
            note = note_by_id.get(note_id, {})
            url = self._note_url(note)
            if not url:
                failures.append({"note_id": note_id, "reason": "missing note url fields"})
                if progress_callback:
                    progress_callback(index + 1, len(selected_ids))
                continue
            detail = self.get_note_detail(url, cookies_input)
            fetched_count += 1
            if detail.get("ok"):
                contents.append(
                    {
                        "note_id": note_id,
                        "content_text": detail.get("content_text", ""),
                        "tags": detail.get("tags", []),
                        "comment_count": detail.get("comment_count", 0),
                        "collected_count": detail.get("collected_count", 0),
                        "share_count": detail.get("share_count", 0),
                        "image_urls": detail.get("image_urls", []),
                        "cover_url": detail.get("cover_url", ""),
                        "video_url": detail.get("video_url", ""),
                        "video_cover_url": detail.get("video_cover_url", ""),
                        "publish_time": detail.get("publish_time", 0),
                        "ip_location": detail.get("ip_location", ""),
                    }
                )
            else:
                failures.append({"note_id": note_id, "reason": detail.get("reason", "detail unavailable")})
            if progress_callback:
                progress_callback(index + 1, len(selected_ids))
            if fetched_count and index < len(selected_ids) - 1:
                time.sleep(delay_seconds)

        (task_dir / "contents.json").write_text(
            json.dumps(contents, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        detail_fetch = {
            "enabled": True,
            "requested_count": len(selected_ids),
            "success_count": len(contents),
            "reused_count": reused_count,
            "fetched_count": fetched_count,
            "failed_count": len(failures),
            "failures": failures,
        }
        (task_dir / "detail_fetch.json").write_text(
            json.dumps(detail_fetch, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return detail_fetch

    @staticmethod
    def _normalize_comment(note_id: str, raw: dict, parent_id: str = "") -> dict:
        user = raw.get("user_info") or {}
        pictures = []
        for picture in raw.get("pictures", []) or []:
            if not isinstance(picture, dict):
                continue
            for info in picture.get("info_list", []) or []:
                if isinstance(info, dict) and info.get("url"):
                    pictures.append(info["url"])
                    break
        return {
            "note_id": note_id,
            "comment_id": raw.get("id", ""),
            "parent_comment_id": parent_id,
            "content": raw.get("content", "") or "",
            "like_count": raw.get("like_count", 0),
            "create_time": raw.get("create_time", 0),
            "ip_location": raw.get("ip_location", ""),
            "user_id": user.get("user_id", ""),
            "nickname": user.get("nickname", ""),
            "pictures": pictures,
        }

    def get_note_comments(self, note: dict, cookies_input=None, limit: int = 10) -> dict:
        """Fetch one public comment page and normalize a bounded sample."""
        cookies_str = cookies_array_to_dict(cookies_input)
        self._ensure_api(cookies_str)
        note_id = note.get("note_id", "")
        token = note.get("xsec_token", "")

        def get_page():
            return self._api.get_note_out_comment(note_id, "", token, self._cookies)

        success, msg, payload = self._call(get_page)
        if not success or not isinstance(payload, dict):
            return {"ok": False, "reason": msg or "comment unavailable", "comments": []}
        raw_comments = ((payload.get("data") or {}).get("comments") or [])[:max(1, limit)]
        comments = []
        for raw in raw_comments:
            if not isinstance(raw, dict):
                continue
            comments.append(self._normalize_comment(note_id, raw))
            for child in (raw.get("sub_comments") or [])[:3]:
                if isinstance(child, dict):
                    comments.append(self._normalize_comment(note_id, child, raw.get("id", "")))
        return {"ok": True, "comments": comments}

    def enrich_comments(
        self,
        task_dir: Path,
        cookies_input,
        max_notes: int = 12,
        comments_per_note: int = 10,
        delay_seconds: float = 1.0,
        progress_callback=None,
    ) -> dict:
        """Collect representative comments without crawling every discussion thread."""
        notes = json.loads((task_dir / "all_notes.json").read_text(encoding="utf-8"))
        contents = []
        if (task_dir / "contents.json").exists():
            contents = json.loads((task_dir / "contents.json").read_text(encoding="utf-8"))
        detail_ids = [item.get("note_id") for item in contents if item.get("note_id")]
        candidates = [note for note in notes if note.get("note_id") in set(detail_ids)] or notes
        selected_ids = self._select_detail_note_ids(candidates, {}, min(max_notes, len(candidates)))
        by_id = {note.get("note_id"): note for note in notes}
        comments = []
        seen_comment_keys = set()
        failures = []
        for index, note_id in enumerate(selected_ids):
            result = self.get_note_comments(by_id[note_id], cookies_input, comments_per_note)
            if result.get("ok"):
                for comment in result.get("comments", []):
                    key = comment.get("comment_id") or "|".join(
                        str(comment.get(field) or "")
                        for field in ("note_id", "parent_comment_id", "user_id", "content", "create_time")
                    )
                    if key and key not in seen_comment_keys:
                        seen_comment_keys.add(key)
                        comments.append(comment)
            else:
                failures.append({"note_id": note_id, "reason": result.get("reason", "unavailable")})
            if progress_callback:
                progress_callback(index + 1, len(selected_ids))
            if index < len(selected_ids) - 1:
                time.sleep(delay_seconds)
        (task_dir / "comments.json").write_text(
            json.dumps(comments, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        status = {
            "enabled": True,
            "requested_note_count": len(selected_ids),
            "successful_note_count": len(set(item.get("note_id") for item in comments)),
            "comment_count": len(comments),
            "failed_note_count": len(failures),
            "failures": failures,
        }
        (task_dir / "comment_fetch.json").write_text(
            json.dumps(status, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        return status

    @staticmethod
    def _collect_suggestion_text(payload) -> list[str]:
        found = []

        def walk(value):
            if isinstance(value, dict):
                for key, child in value.items():
                    if key in {"text", "name", "keyword", "search_word", "word"} and isinstance(child, str):
                        clean = child.strip()
                        if 1 < len(clean) <= 30 and clean not in found:
                            found.append(clean)
                    else:
                        walk(child)
            elif isinstance(value, list):
                for child in value:
                    walk(child)

        walk(payload)
        return found[:20]

    @staticmethod
    def _search_terms(results: dict, limit: int = 4) -> list[str]:
        terms = []
        for item in (results.get("tags") or {}).get("top30", []):
            term = str(item.get("tag") or "").strip().lstrip("#")
            if 1 < len(term) <= 16 and term not in terms:
                terms.append(term)
        for topic in results.get("topic_clusters", []) or []:
            for keyword in topic.get("matched_keywords", []) or []:
                term = str(keyword or "").strip()
                if 1 < len(term) <= 16 and not re.fullmatch(r"[A-Za-z]?\d+", term) and term not in terms:
                    terms.append(term)
            topic_name = str(topic.get("name") or "").strip()
            if (
                1 < len(topic_name) <= 16
                and topic_name not in {"未归类观察", "其他", "未分类"}
                and topic_name not in terms
            ):
                terms.append(topic_name)
        return terms[:limit]

    def enrich_search_landscape(
        self,
        task_dir: Path,
        cookies_input,
        max_keywords: int = 4,
        results_per_keyword: int = 10,
        delay_seconds: float = 1.0,
    ) -> dict:
        """Collect search suggestions and a small public result sample for account keywords."""
        cookies_str = cookies_array_to_dict(cookies_input)
        self._ensure_api(cookies_str)
        results_path = task_dir / "results.json"
        results = json.loads(results_path.read_text(encoding="utf-8")) if results_path.exists() else {}
        keywords = self._search_terms(results, max_keywords)
        rows = []
        failures = []
        for index, keyword in enumerate(keywords):
            def recommend():
                return self._api.get_search_keyword(keyword, self._cookies)

            ok_recommend, recommend_msg, recommend_payload = self._call(recommend)

            def search():
                return self._api.search_some_note(keyword, results_per_keyword, self._cookies)

            ok_search, search_msg, search_items = self._call(search)
            normalized = []
            if ok_search:
                for item in search_items or []:
                    if not isinstance(item, dict) or item.get("model_type") not in (None, "note"):
                        continue
                    card = item.get("note_card") or item
                    interact = card.get("interact_info") or {}
                    normalized.append({
                        "note_id": item.get("id") or item.get("note_id") or card.get("note_id") or "",
                        "title": card.get("display_title") or card.get("title") or "",
                        "type": card.get("type") or "",
                        "liked_count": interact.get("liked_count", 0),
                        "collected_count": interact.get("collected_count", 0),
                        "comment_count": interact.get("comment_count", 0),
                    })
            if not ok_recommend or not ok_search:
                failures.append({
                    "keyword": keyword,
                    "reason": "; ".join(filter(None, [recommend_msg if not ok_recommend else "", search_msg if not ok_search else ""])),
                })
            rows.append({
                "keyword": keyword,
                "suggestions": self._collect_suggestion_text(recommend_payload) if ok_recommend else [],
                "result_count": len(normalized),
                "results": normalized,
            })
            if index < len(keywords) - 1:
                time.sleep(delay_seconds)
        payload = {
            "enabled": True,
            "keywords": rows,
            "keyword_count": len(rows),
            "failed_count": len(failures),
            "failures": failures,
            "scope": "搜索联想和结果样本只代表采集时公开页面，不代表真实搜索量、排名或账号搜索流量。",
        }
        (task_dir / "search_landscape.json").write_text(
            json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        return payload

    @staticmethod
    def _note_url(note: dict) -> str:
        note_id = note.get("note_id", "")
        if not note_id:
            return ""
        xsec_token = note.get("xsec_token", "")
        xsec_source = note.get("xsec_source", "pc_user") or "pc_user"
        query = f"xsec_source={quote(str(xsec_source))}"
        if xsec_token:
            query += f"&xsec_token={quote(str(xsec_token))}"
        return f"https://www.xiaohongshu.com/explore/{note_id}?{query}"

    @staticmethod
    def _parse_note_likes(note: dict) -> int:
        value = note.get("liked_count", 0)
        if isinstance(value, (int, float)):
            return int(value)
        value = str(value or "").strip()
        if "万" in value:
            try:
                return int(float(value.replace("万", "")) * 10000)
            except ValueError:
                return 0
        try:
            return int(float(value))
        except ValueError:
            return 0

    def _select_detail_note_ids(self, all_notes: list[dict], results: dict, max_count: int) -> list[str]:
        """Build a balanced detail sample instead of only fetching the highest-liked notes."""
        selected = []

        def add(note_id: str):
            if note_id and note_id not in selected and len(selected) < max_count:
                selected.append(note_id)

        valid_notes = [note for note in all_notes if note.get("note_id")]
        sorted_notes = sorted(valid_notes, key=self._parse_note_likes, reverse=True)

        # High performers support evidence review, but must not dominate the sample.
        for note in sorted_notes[:8]:
            add(note.get("note_id", ""))

        # Low performers make title/body comparisons possible without treating missing data as zero.
        for note in sorted_notes[-6:]:
            add(note.get("note_id", ""))

        # Median performers provide the account's normal baseline.
        if sorted_notes:
            middle = len(sorted_notes) // 2
            for note in sorted_notes[max(0, middle - 3):middle + 3]:
                add(note.get("note_id", ""))

        def note_timestamp(note: dict) -> int:
            try:
                return int(str(note.get("note_id", ""))[:8], 16)
            except (TypeError, ValueError):
                return 0

        # Recent notes keep the report relevant to the account's current direction.
        for note in sorted(valid_notes, key=note_timestamp, reverse=True)[:6]:
            add(note.get("note_id", ""))

        # Ensure each discovered topic has at least one concrete detail sample where possible.
        for topic in (results.get("topic_distribution") or {}).values():
            for note_id in topic.get("evidence_note_ids", [])[:2] or topic.get("note_ids", [])[:2]:
                add(note_id)
                break
            if len(selected) >= max_count:
                break

        # Fill any remaining slots across the ranking instead of clustering around one end.
        remaining = [note for note in sorted_notes if note.get("note_id") not in selected]
        if remaining:
            slots = max_count - len(selected)
            step = max(len(remaining) / max(slots, 1), 1)
            for index in range(slots):
                note = remaining[min(int(index * step), len(remaining) - 1)]
                add(note.get("note_id", ""))

        for note in remaining:
            add(note.get("note_id", ""))
            if len(selected) >= max_count:
                break

        return selected[:max_count]

    @staticmethod
    def save_task_data(task_dir: Path, data: dict):
        """Save collector data to task directory for downstream analysis."""
        task_dir.mkdir(parents=True, exist_ok=True)

        with open(task_dir / "all_notes.json", "w", encoding="utf-8") as f:
            json.dump(data["all_notes"], f, ensure_ascii=False, indent=2)

        with open(task_dir / "profile.json", "w", encoding="utf-8") as f:
            json.dump(data["profile"], f, ensure_ascii=False, indent=2)

        if data.get("contents"):
            # Build contents array from map
            contents_list = []
            for note_id, content in data["contents"].items():
                if content.get("tags") or content.get("content_text"):
                    contents_list.append({
                        "note_id": note_id,
                        "tags": content.get("tags", []),
                        "content_text": content.get("content_text", ""),
                    })
            with open(task_dir / "contents.json", "w", encoding="utf-8") as f:
                json.dump(contents_list, f, ensure_ascii=False, indent=2)
