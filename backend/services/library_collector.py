"""Bounded, checkpointed collection. Calls the existing SDK one page at a time."""
import time
from urllib.parse import parse_qs, urlsplit

from backend.services.collector import Collector, _is_network_error
from backend.services.note_library import SCHEMA_VERSION, apply_detail, make_row, now_text, update_missing


def failure_kind(message):
    text = str(message or "").lower()
    if any(k in text for k in ("captcha", "risk", "验证", "风控", "频繁", "429", "461", "471", "300012")):
        return "访问受限，请稍后在浏览器确认"
    if any(k in text for k in ("cookie", "登录", "unauthorized", "401", "403", "-100", "-101")):
        return "登录状态失效，请重新登录"
    return "网络暂时失败" if _is_network_error(text) else "页面不可访问或接口未返回数据"


def collect_library(profile_url, cookies, checkpoint, cancelled=lambda: False,
                    collector=None, limit=100, delay=1.5, timeout=900):
    collector = collector or Collector()
    from backend.utils.cookie import cookies_array_to_dict
    collector._ensure_api(cookies_array_to_dict(cookies))
    parsed = urlsplit(profile_url)
    user_id = parsed.path.rstrip("/").split("/")[-1]
    query = parse_qs(parsed.query)
    dataset = {"schema_version": SCHEMA_VERSION, "profile_url": profile_url.split("?")[0],
               "created_at": now_text(), "status": "running", "stop_reason": "",
               "rows": [], "duplicates": 0, "pages": 0, "requested_limit": min(limit, 100)}
    deadline = time.monotonic() + timeout

    def should_stop():
        if cancelled():
            dataset["stop_reason"] = "用户停止"
            return True
        if time.monotonic() >= deadline:
            dataset["stop_reason"] = "达到任务时间上限"
            return True
        return False

    def pause(seconds):
        until = time.monotonic() + seconds
        while time.monotonic() < until and not should_stop():
            time.sleep(min(.2, until - time.monotonic()) if until > time.monotonic() else 0)

    def request(fn):
        for attempt in range(3):
            if should_stop():
                return False, dataset["stop_reason"], None
            try:
                result = fn()
            except Exception as exc:
                result = False, str(exc), None
            if result[0] or not _is_network_error(result[1]) or attempt == 2:
                return result
            pause(delay * (attempt + 1))
        return False, "任务已停止", None

    cursor, cursors, seen, raw_by_id = "", set(), set(), {}
    checkpoint(dataset, "读取主页列表")
    while len(dataset["rows"]) < dataset["requested_limit"] and not should_stop():
        ok, message, payload = request(lambda: collector._call(lambda: collector._api.get_user_note_info(
            user_id, cursor, collector._cookies, query.get("xsec_token", [""])[0], query.get("xsec_source", ["pc_user"])[0])))
        if not ok:
            dataset["stop_reason"] = dataset["stop_reason"] or failure_kind(message)
            break
        data = (payload or {}).get("data") or {}
        items = data.get("notes") or []
        dataset["pages"] += 1
        added = 0
        for item in items:
            note_id = str(item.get("note_id") or item.get("id") or "")
            if not note_id:
                continue
            if note_id in seen:
                dataset["duplicates"] += 1
                continue
            if len(dataset["rows"]) >= dataset["requested_limit"]:
                break
            seen.add(note_id)
            raw_by_id[note_id] = dict(item, note_id=note_id)
            dataset["rows"].append(make_row(item, profile_url, len(dataset["rows"]) + 1))
            added += 1
        checkpoint(dataset, f"已读取 {len(dataset['rows'])} 篇")
        if len(dataset["rows"]) >= dataset["requested_limit"]:
            dataset["stop_reason"] = "达到本次数量上限"
            break
        if not items or not data.get("has_more"):
            dataset["stop_reason"] = "主页已返回末页"
            break
        next_cursor = str(data.get("cursor") or "")
        if not next_cursor or next_cursor in cursors or not added or dataset["pages"] >= 10:
            dataset["stop_reason"] = "分页没有继续推进，已保留已有笔记"
            break
        cursors.add(next_cursor)
        cursor = next_cursor
        pause(delay)

    # Hard failures stop detail requests too; no repeated probing after an access restriction.
    can_enrich = dataset["stop_reason"] in ("达到本次数量上限", "主页已返回末页", "分页没有继续推进，已保留已有笔记")
    consecutive_failures = 0
    for index, row in enumerate(dataset["rows"]):
        if not can_enrich or should_stop():
            break
        pause(delay)
        raw = raw_by_id[row["note_id"]]
        url = collector._note_url(raw)

        def detail_request():
            detail = collector.get_note_detail(url, cookies)
            return detail.get("ok", False), detail.get("reason", ""), detail

        ok, message, detail = request(detail_request)
        if ok:
            apply_detail(row, detail)
            consecutive_failures = 0
        else:
            row["detail_status"] = "失败"
            row["failure_reason"] = failure_kind(message)
            consecutive_failures += 1
            update_missing(row)
            if any(k in row["failure_reason"] for k in ("访问受限", "登录状态失效")) or consecutive_failures >= 3:
                dataset["stop_reason"] = row["failure_reason"] if consecutive_failures < 3 else "连续三篇详情失败，已停止补采"
                can_enrich = False
        checkpoint(dataset, f"补充详情 {index + 1}/{len(dataset['rows'])}")
    for row in dataset["rows"]:
        if row["detail_status"] == "未尝试":
            row["failure_reason"] = dataset["stop_reason"]
    stopped = should_stop()
    if stopped and dataset["stop_reason"] == "用户停止":
        dataset["status"] = "cancelled"
    elif not dataset["rows"]:
        dataset["status"] = "failed"
    elif any(r["detail_status"] != "成功" for r in dataset["rows"]) or dataset["stop_reason"] not in ("达到本次数量上限", "主页已返回末页"):
        dataset["status"] = "partial"
    else:
        dataset["status"] = "completed"
    dataset["finished_at"] = now_text()
    checkpoint(dataset, "数据已保存")
    return dataset
