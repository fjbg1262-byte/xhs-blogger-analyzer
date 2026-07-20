"""Spider_XHS wrapper for data collection."""

import json
import os
import sys
import time
import warnings
from pathlib import Path
from urllib.parse import quote

from backend.config import settings
from backend.utils.cookie import cookies_array_to_dict

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

# Force bypass system proxy — Windows has proxy 127.0.0.1:7892 (e.g. Clash) that
# may not be running, which breaks requests entirely.
os.environ['no_proxy'] = '*'

# Default verify=False AND force-empty proxy for all Spider_XHS calls
_original_request = requests.Session.request
def _patched_request(self, method, url, **kwargs):
    kwargs.setdefault('verify', False)
    kwargs['proxies'] = {}  # bypass system proxy entirely
    return _original_request(self, method, url, **kwargs)
requests.Session.request = _patched_request


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
        success, msg, notes_data = self._call(get_notes)
        if not success:
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
            user_info = item.get("user") or {}
            note_type = item.get("type", "normal")
            ranked_type = "video" if note_type == "video" else "normal"

            note = {
                "note_id": note_id,
                "xsec_token": item.get("xsec_token", ""),
                "xsec_source": item.get("xsec_source", "pc_user"),
                "title": item.get("display_title", item.get("title", "")),
                "type": ranked_type,
                "liked_count": str(interact_info.get("liked_count", 0)),
                "sticky": bool(interact_info.get("sticky", False)),
                "time": item.get("time", item.get("publish_time", "")),
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
            profile["avatar_url"] = (
                basic.get("imageb")
                or basic.get("image")
                or basic.get("avatar")
                or basic.get("images")
                or ""
            )
            interactions = user_data.get("interactions") or []
            for ix in interactions:
                if ix.get("type") == "fans":
                    profile["follower_count"] = int(ix.get("count", 0))
                elif ix.get("type") == "interaction":
                    profile["total_interaction"] = int(ix.get("count", 0))

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

    def get_note_detail(self, note_url: str, cookies_input=None) -> dict:
        """Get full detail for a single note (tags, content_text, comments)."""
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
        return {
            "ok": True,
            "note_id": note_url.rstrip("/").split("/")[-1].split("?")[0],
            "title": card.get("title", ""),
            "tags": tags,
            "content_text": card.get("desc", "") or "",
            "liked_count": interact.get("liked_count", 0),
            "collected_count": interact.get("collected_count", 0),
            "comment_count": interact.get("comment_count", 0),
            "share_count": interact.get("share_count", 0),
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

        contents = []
        failures = []
        for index, note_id in enumerate(selected_ids):
            note = note_by_id.get(note_id, {})
            url = self._note_url(note)
            if not url:
                failures.append({"note_id": note_id, "reason": "missing note url fields"})
                if progress_callback:
                    progress_callback(index + 1, len(selected_ids))
                continue
            detail = self.get_note_detail(url, cookies_input)
            if detail.get("ok"):
                contents.append(
                    {
                        "note_id": note_id,
                        "content_text": detail.get("content_text", ""),
                        "tags": detail.get("tags", []),
                        "comment_count": detail.get("comment_count", 0),
                        "collected_count": detail.get("collected_count", 0),
                        "share_count": detail.get("share_count", 0),
                    }
                )
            else:
                failures.append({"note_id": note_id, "reason": detail.get("reason", "detail unavailable")})
            if progress_callback:
                progress_callback(index + 1, len(selected_ids))
            if index < len(selected_ids) - 1:
                time.sleep(delay_seconds)

        (task_dir / "contents.json").write_text(
            json.dumps(contents, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        detail_fetch = {
            "enabled": True,
            "requested_count": len(selected_ids),
            "success_count": len(contents),
            "failed_count": len(failures),
            "failures": failures,
        }
        (task_dir / "detail_fetch.json").write_text(
            json.dumps(detail_fetch, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return detail_fetch

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
        selected = []

        def add(note_id: str):
            if note_id and note_id not in selected and len(selected) < max_count:
                selected.append(note_id)

        sorted_notes = sorted(all_notes, key=self._parse_note_likes, reverse=True)
        for note in sorted_notes[:10]:
            add(note.get("note_id", ""))

        for topic in (results.get("topic_distribution") or {}).values():
            for note_id in topic.get("note_ids", [])[:2]:
                add(note_id)
                if len(selected) >= 20:
                    break
            if len(selected) >= 20:
                break

        positive_notes = [note for note in all_notes if note.get("note_id") and self._parse_note_likes(note) > 0]
        for note in sorted(positive_notes, key=self._parse_note_likes)[:5]:
            add(note.get("note_id", ""))

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
