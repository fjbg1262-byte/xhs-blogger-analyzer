"""Workspace views over collected note datasets.

Phase 2 keeps the existing collection pipeline (dataset.json per task) and adds a
read model for the new front end: task cards, note rows and the public-metric
statistics used by the overview / analysis tabs.

Everything here is derived from already-collected data. No network calls, no
model calls, no writes.
"""

from collections import Counter
import json
import re
from pathlib import Path

from backend.config import settings
from backend.services.analysis_analytics import build_report_analytics

METRIC_KEYS = ("liked_count", "collected_count", "comment_count", "share_count")
STATUS_LABELS = {
    "pending": "等待开始",
    "running": "正在采集",
    "completed": "已完成",
    "partial": "部分完成",
    "cancelled": "已停止",
    "failed": "未完成",
}
TYPES = ("图文", "视频")


def dataset_path(task_id: int) -> Path:
    return Path(settings.data_dir) / "tasks" / str(task_id) / "dataset.json"


def load_dataset(task_id: int):
    """Return the stored dataset for a task, or None when it has not been written yet."""
    path = dataset_path(task_id)
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _count(row, key):
    value = row.get(key)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return int(value)


def engagement_of(row) -> int:
    return sum(value for value in (_count(row, key) for key in METRIC_KEYS) if value is not None)


def is_incomplete(row) -> bool:
    return row.get("detail_status") != "成功"


def note_view(row):
    """Map one dataset row to the note shape used by the workspace UI.

    The list keeps only a short body preview; the full body, images and video
    URL are served per note by ``note_detail`` so a 100-note payload stays small.
    """
    likes = _count(row, "liked_count")
    collected = _count(row, "collected_count")
    comments = _count(row, "comment_count")
    shares = _count(row, "share_count")
    body = row.get("content_text") or ""
    return {
        "id": str(row.get("note_id") or ""),
        "title": row.get("title") or "未获取标题",
        "author": row.get("author_nickname") or "",
        "type": row.get("type") if row.get("type") in TYPES else "未知",
        "published_at": (row.get("published_at") or "")[:10],
        "likes": likes,
        "collected": collected,
        "comments": comments,
        "shares": shares,
        "engagement": engagement_of(row),
        "tags": [str(tag) for tag in (row.get("tags") or []) if str(tag).strip()],
        "cover_url": row.get("cover_url") or "",
        "body_preview": body[:200],
        "body_length": len(body),
        "has_body": bool(body.strip()),
        "note_url": row.get("note_url") or "",
        "sticky": bool(row.get("sticky")),
        "incomplete": is_incomplete(row),
        "failure": (row.get("failure_reason") or "") if is_incomplete(row) else "",
        "collected_at": row.get("collected_at") or "",
        "missing_fields": list(row.get("missing_fields") or []),
    }


def notes_view(dataset):
    return [note_view(row) for row in (dataset.get("rows") or [])]


def find_note(dataset, note_id):
    for row in dataset.get("rows") or []:
        if str(row.get("note_id")) == str(note_id):
            return row
    return None


def note_detail(row):
    """Full detail payload for one note, fetched when the drawer opens."""
    if row is None:
        return None
    view = note_view(row)
    view.update({
        "body": row.get("content_text") or "",
        "image_urls": list(row.get("image_urls") or []),
        "video_url": row.get("video_url") or "",
        "detail_status": row.get("detail_status") or "",
        "text_status": row.get("text_status") or "",
        "tags_status": row.get("tags_status") or "",
        "metric_source": row.get("metric_source") or "",
        "count_precision": row.get("count_precision") or "",
    })
    return view


def _evidence(dataset):
    """Shape dataset rows the way analysis_analytics expects them."""
    return [
        {
            "note_id": row.get("note_id"),
            "title": row.get("title"),
            "note_url": row.get("note_url"),
            "type": row.get("type"),
            "published_at": row.get("published_at"),
            "tags": row.get("tags") or [],
            "metrics": {key: row.get(key) for key in METRIC_KEYS},
        }
        for row in (dataset.get("rows") or [])
    ]


def dataset_stats(dataset):
    """Public-metric statistics for the overview and analysis tabs."""
    rows = dataset.get("rows") or []
    analytics = build_report_analytics(_evidence(dataset))
    total = analytics.get("total_engagement") or 0
    median = analytics.get("median_engagement")

    counts = Counter(row.get("type") for row in rows)
    image_count = counts.get("图文", 0)
    video_count = counts.get("视频", 0)

    # Best-performing format: highest median engagement among formats with data.
    types = [item for item in analytics.get("types") or [] if item.get("median_engagement") is not None]
    types.sort(key=lambda item: item.get("median_engagement") or 0, reverse=True)
    best = types[0] if types else None
    format_ratio = None
    if best and median:
        format_ratio = round(best["median_engagement"] / median, 2)

    dated = [row.get("published_at") for row in rows if row.get("published_at")]
    titled = [row for row in rows if re.search(r"\d", str(row.get("title") or ""))]
    tags = Counter(tag for row in rows for tag in (row.get("tags") or []) if str(tag).strip())
    top_tag, top_tag_count = (tags.most_common(1)[0] if tags else ("", 0))

    return {
        "metric_basis": analytics.get("metric_basis", ""),
        "note_count": len(rows),
        "total_engagement": total,
        "mean_engagement": analytics.get("mean_engagement"),
        "median_engagement": median,
        "percentiles": analytics.get("percentiles"),
        "metric_totals": analytics.get("metric_totals"),
        "top_count": (analytics.get("concentration") or {}).get("top_20pct_count", 0),
        "top_share": (analytics.get("concentration") or {}).get("top_20pct_share", 0.0),
        "notes_for_80pct": (analytics.get("concentration") or {}).get("notes_for_80pct", 0),
        "types": analytics.get("types") or [],
        "image_count": image_count,
        "image_share": round(image_count / len(rows) * 100, 1) if rows else 0.0,
        "video_count": video_count,
        "video_share": round(video_count / len(rows) * 100, 1) if rows else 0.0,
        "best_type": (best or {}).get("type", ""),
        "format_ratio": format_ratio,
        "title_count": len(titled),
        "title_pct": round(len(titled) / len(rows) * 100, 1) if rows else 0.0,
        "top_tag": top_tag,
        "top_tag_count": top_tag_count,
        "latest_published_at": max(dated) if dated else "",
        "body_count": sum(1 for row in rows if (row.get("content_text") or "").strip()),
        "failed_count": sum(1 for row in rows if is_incomplete(row)),
    }


STAGE_STEPS = [
    ("prepare", "准备任务"),
    ("read", "读取主页列表"),
    ("detail", "补充正文与标签"),
    ("save", "保存结果"),
]


def progress_steps(task, dataset):
    """Four-stage collection progress derived from task status and the collector stage text."""
    stage_text = ""
    if task.run_log:
        try:
            payload = json.loads(task.run_log)
            if isinstance(payload, dict):
                stage_text = str(payload.get("stage") or "")
        except (json.JSONDecodeError, TypeError):
            stage_text = ""
    status = task.status or "pending"
    if status in ("completed", "partial", "cancelled", "failed"):
        current = len(STAGE_STEPS)
    elif "保存" in stage_text:
        current = 3
    elif "补充详情" in stage_text:
        current = 2
    elif "读取" in stage_text:
        current = 1
    else:
        current = 0
    steps = [
        {
            "key": key,
            "label": label,
            "done": index < current,
            "active": index == current and status in ("pending", "running"),
        }
        for index, (key, label) in enumerate(STAGE_STEPS)
    ]
    return {"stage": stage_text or STATUS_LABELS.get(status, status), "steps": steps}


def task_card(task, dataset):
    """Compact task row used by the home page and the collection history."""
    rows = (dataset or {}).get("rows") or []
    status = task.status or "pending"
    summary = (dataset or {}).get("summary") or {}
    body_count = summary.get("detail_success")
    if body_count is None:
        body_count = sum(1 for row in rows if (row.get("content_text") or "").strip())
    return {
        "id": task.id,
        "account_id": task.account_id,
        "status": status,
        "status_label": STATUS_LABELS.get(status, status),
        "progress": task.progress or 0,
        "target": (dataset or {}).get("requested_limit") or 100,
        "note_count": len(rows),
        "body_count": int(body_count),
        "failed_count": sum(1 for row in rows if is_incomplete(row)),
        "reason": task.error_message or (dataset or {}).get("stop_reason") or "",
        "created_at": str(task.created_at or ""),
        "started_at": str(task.started_at or ""),
        "completed_at": str(task.completed_at or ""),
        "has_dataset": dataset is not None,
    }


def account_name(account, dataset):
    if account is not None and getattr(account, "nickname", None):
        return account.nickname
    for row in (dataset or {}).get("rows") or []:
        if row.get("author_nickname"):
            return row["author_nickname"]
    if account is not None and account.profile_url:
        tail = account.profile_url.rstrip("/").split("/")[-1]
        return tail[:16] or "未命名账号"
    return "未命名账号"


def account_card(account, latest_task, dataset):
    return {
        "id": account.id if account is not None else 0,
        "name": account_name(account, dataset),
        "profile_url": getattr(account, "profile_url", "") or "",
        "last_task_id": latest_task.id if latest_task is not None else None,
        "note_count": len((dataset or {}).get("rows") or []),
        "updated_at": str(getattr(latest_task, "completed_at", "") or getattr(latest_task, "created_at", "") or ""),
    }
