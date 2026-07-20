"""Privacy-preserving anonymous product telemetry."""

from __future__ import annotations

import json
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import httpx

from backend.config import settings


EVENT_NAMES = {
    "app_started",
    "extension_connected",
    "analysis_started",
    "analysis_completed",
    "analysis_failed",
    "report_opened",
    "diagnostic_copied",
    "feedback_submitted",
}

PROPERTY_RULES: dict[str, set[str]] = {
    "app_started": set(),
    "extension_connected": set(),
    "analysis_started": {"task_type"},
    "analysis_completed": {"task_type", "duration_ms"},
    "analysis_failed": {"task_type", "duration_ms", "error_code", "stage"},
    "report_opened": {"task_type"},
    "diagnostic_copied": {"error_code"},
    "feedback_submitted": {"feedback_kind"},
}

ALLOWED_TASK_TYPES = {"full_analysis", "detail_fetch", "competitor_discovery"}
ALLOWED_STAGES = {"prepare", "collect", "analyze", "report", "save", "unknown"}
ERROR_CODES = {
    "dependency_missing",
    "cookie_invalid",
    "network_timeout",
    "collector_missing",
    "collection_failed",
    "analysis_failed",
    "report_failed",
    "unknown_error",
}
CONSENT_VALUES = {"unknown", "granted", "denied"}

_state_lock = threading.Lock()


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _config_path() -> Path:
    return Path(settings.data_dir) / "telemetry_preferences.json"


def _queue_path() -> Path:
    return Path(settings.data_dir) / "telemetry_queue.jsonl"


def _new_preferences() -> dict[str, Any]:
    return {
        "install_id": uuid.uuid4().hex,
        "consent": "unknown",
        "updated_at": _utc_now(),
    }


def load_preferences() -> dict[str, Any]:
    with _state_lock:
        path = _config_path()
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError, TypeError):
            payload = _new_preferences()

        install_id = str(payload.get("install_id") or "")
        try:
            uuid.UUID(hex=install_id)
        except (ValueError, AttributeError):
            install_id = uuid.uuid4().hex

        consent = str(payload.get("consent") or "unknown")
        if consent not in CONSENT_VALUES:
            consent = "unknown"

        normalized = {
            "install_id": install_id,
            "consent": consent,
            "updated_at": str(payload.get("updated_at") or _utc_now()),
        }
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(normalized, ensure_ascii=False, indent=2), encoding="utf-8")
        return normalized


def save_consent(consent: str) -> dict[str, Any]:
    if consent not in {"granted", "denied"}:
        raise ValueError("consent must be granted or denied")
    prefs = load_preferences()
    prefs["consent"] = consent
    prefs["updated_at"] = _utc_now()
    with _state_lock:
        path = _config_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(prefs, ensure_ascii=False, indent=2), encoding="utf-8")
    if consent == "denied":
        try:
            _queue_path().unlink(missing_ok=True)
        except OSError:
            pass
    return prefs


def public_preferences() -> dict[str, Any]:
    prefs = load_preferences()
    return {
        "consent": prefs["consent"],
        "available": bool(settings.telemetry_endpoint),
        "app_version": settings.app_version,
        "privacy_summary": [
            "只发送启动、分析状态、报告打开和主动反馈",
            "不发送 Cookie、主页链接、账号名称、笔记内容或报告正文",
            "可以随时在设置中关闭",
        ],
    }


def classify_error(error: Any) -> str:
    text = str(error or "").lower()
    if "no module named" in text or "modulenotfounderror" in text or "execjs" in text:
        return "dependency_missing"
    if "cookie" in text or "unauthorized" in text or "403" in text or "登录" in text:
        return "cookie_invalid"
    if "timeout" in text or "timed out" in text:
        return "network_timeout"
    if "spider_xhs not found" in text:
        return "collector_missing"
    if "collect" in text or "notes" in text or "采集" in text:
        return "collection_failed"
    if "report" in text or "报告" in text:
        return "report_failed"
    if "analysis" in text or "分析" in text:
        return "analysis_failed"
    return "unknown_error"


def sanitize_properties(event_name: str, properties: Any) -> dict[str, Any]:
    if event_name not in EVENT_NAMES:
        raise ValueError("unsupported telemetry event")
    if not isinstance(properties, dict):
        return {}

    allowed = PROPERTY_RULES[event_name]
    clean: dict[str, Any] = {}
    for key in allowed:
        value = properties.get(key)
        if value is None:
            continue
        if key == "duration_ms":
            try:
                clean[key] = max(0, min(int(value), 3_600_000))
            except (TypeError, ValueError):
                continue
        elif key == "task_type" and str(value) in ALLOWED_TASK_TYPES:
            clean[key] = str(value)
        elif key == "stage" and str(value) in ALLOWED_STAGES:
            clean[key] = str(value)
        elif key == "error_code" and str(value) in ERROR_CODES:
            clean[key] = str(value)
        elif key == "feedback_kind" and str(value) in {"report", "failure"}:
            clean[key] = str(value)
    return clean


def diagnostic_payload(task_id: int, error: Any) -> dict[str, str]:
    prefs = load_preferences()
    error_code = classify_error(error)
    diagnostic_code = f"{prefs['install_id'][:6].upper()}-{int(task_id):04d}-{error_code.upper()}"
    return {
        "diagnostic_code": diagnostic_code,
        "error_code": error_code,
        "app_version": settings.app_version,
        "copy_text": (
            f"诊断编号：{diagnostic_code}\n"
            f"软件版本：{settings.app_version}\n"
            f"错误类型：{error_code}\n"
            "说明：诊断信息不包含 Cookie、账号链接或报告内容。"
        ),
    }


def _headers() -> dict[str, str]:
    headers = {"Content-Type": "application/json"}
    if settings.telemetry_ingest_key:
        headers["X-Ingest-Key"] = settings.telemetry_ingest_key
    return headers


def _send(path: str, payload: dict[str, Any]) -> bool:
    endpoint = settings.telemetry_endpoint.rstrip("/")
    if not endpoint:
        return False
    parsed = urlparse(endpoint)
    if parsed.scheme != "https" and parsed.hostname not in {"127.0.0.1", "localhost"}:
        return False
    try:
        response = httpx.post(
            f"{endpoint}{path}",
            json=payload,
            headers=_headers(),
            timeout=4.0,
        )
        return 200 <= response.status_code < 300
    except (httpx.HTTPError, OSError, TypeError):
        return False


def _append_queue(path: str, payload: dict[str, Any]) -> None:
    row = json.dumps({"path": path, "payload": payload}, ensure_ascii=False)
    with _state_lock:
        queue = _queue_path()
        queue.parent.mkdir(parents=True, exist_ok=True)
        with queue.open("a", encoding="utf-8") as handle:
            handle.write(row + "\n")


def _flush_queue() -> None:
    queue = _queue_path()
    with _state_lock:
        try:
            lines = queue.read_text(encoding="utf-8").splitlines()
        except OSError:
            return
        queue.unlink(missing_ok=True)

    remaining = []
    for line in lines[:100]:
        try:
            item = json.loads(line)
            if not _send(str(item["path"]), dict(item["payload"])):
                remaining.append(line)
        except (ValueError, TypeError, KeyError):
            continue
    remaining.extend(lines[100:])
    if remaining:
        with _state_lock:
            queue.parent.mkdir(parents=True, exist_ok=True)
            queue.write_text("\n".join(remaining) + "\n", encoding="utf-8")


def _deliver(path: str, payload: dict[str, Any]) -> None:
    _flush_queue()
    if not _send(path, payload):
        _append_queue(path, payload)


def track(event_name: str, properties: Any = None) -> bool:
    prefs = load_preferences()
    if prefs["consent"] != "granted" or not settings.telemetry_endpoint:
        return False
    payload = {
        "install_id": prefs["install_id"],
        "app_version": settings.app_version,
        "event_name": event_name,
        "properties": sanitize_properties(event_name, properties or {}),
        "occurred_at": _utc_now(),
    }
    threading.Thread(target=_deliver, args=("/v1/events", payload), daemon=True).start()
    return True


def submit_feedback(
    *,
    task_id: int,
    feedback_kind: str,
    rating: str,
    reason: str = "",
    comment: str = "",
    reuse_intent: str = "",
    error: Any = None,
) -> bool:
    prefs = load_preferences()
    if prefs["consent"] != "granted" or not settings.telemetry_endpoint:
        return False
    if feedback_kind not in {"report", "failure"}:
        raise ValueError("unsupported feedback kind")
    if rating not in {"helpful", "not_helpful", "problem"}:
        raise ValueError("unsupported rating")

    diagnostic = diagnostic_payload(task_id, error)
    payload = {
        "install_id": prefs["install_id"],
        "app_version": settings.app_version,
        "feedback_kind": feedback_kind,
        "rating": rating,
        "reason": str(reason or "")[:80],
        "comment": str(comment or "")[:500],
        "reuse_intent": str(reuse_intent or "")[:20],
        "diagnostic_code": diagnostic["diagnostic_code"] if feedback_kind == "failure" else "",
        "error_code": diagnostic["error_code"] if feedback_kind == "failure" else "",
        "occurred_at": _utc_now(),
    }
    threading.Thread(target=_deliver, args=("/v1/feedback", payload), daemon=True).start()
    track("feedback_submitted", {"feedback_kind": feedback_kind})
    return True
