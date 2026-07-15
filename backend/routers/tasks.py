"""Task lifecycle endpoints."""

import json
import re
from pathlib import Path
from urllib.parse import urlparse

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.config import settings
from backend.database import Account, Cookie, Task, get_db
from backend.models.schemas import CompetitorDiscoverRequest, TaskCreate
from backend.routers.auth import get_current_user
from backend.tasks.worker import submit_competitor_discovery, submit_detail_enrichment, submit_task
from backend.utils.cookie import cookies_array_to_dict

router = APIRouter(prefix="/api/tasks", tags=["tasks"])

MSG_BAD_URL = "\u8bf7\u8f93\u5165\u5b8c\u6574\u7684\u5c0f\u7ea2\u4e66\u535a\u4e3b\u4e3b\u9875\u94fe\u63a5\u3002"
MSG_BAD_DOMAIN = "\u76ee\u524d\u53ea\u652f\u6301 xiaohongshu.com \u7684\u535a\u4e3b\u4e3b\u9875\u94fe\u63a5\u3002"
MSG_BAD_PROFILE_PATH = "\u94fe\u63a5\u683c\u5f0f\u4e0d\u6b63\u786e\uff0c\u5e94\u7c7b\u4f3c\uff1ahttps://www.xiaohongshu.com/user/profile/\u7528\u6237ID"
MSG_TASK_LIMIT = "\u5f53\u524d\u5df2\u6709\u4efb\u52a1\u5728\u8fd0\u884c\u3002\u4e3a\u964d\u4f4e\u5f02\u5e38\u8bbf\u95ee\u98ce\u9669\uff0c\u8bf7\u7b49\u5f85\u4efb\u52a1\u5b8c\u6210\u540e\u518d\u521b\u5efa\u65b0\u7684\u5206\u6790\u3002"
MSG_COOKIE_NOT_FOUND = "Cookie \u4e0d\u5b58\u5728\uff0c\u8bf7\u5148\u5728\u8bbe\u7f6e\u9875\u6dfb\u52a0 Cookie\u3002"
MSG_TASK_NOT_FOUND = "\u4efb\u52a1\u4e0d\u5b58\u5728"
MSG_TASK_CANCELLED = "\u4efb\u52a1\u5df2\u53d6\u6d88"
MSG_TASK_NOT_RUNNING = "\u4efb\u52a1\u4e0d\u5728\u8fd0\u884c\u4e2d"
MSG_KEYWORD_REQUIRED = "\u8bf7\u8f93\u5165\u5bf9\u6807\u641c\u7d22\u5173\u952e\u8bcd\u3002"
MSG_TASK_NOT_COMPLETED = "请等待基础分析完成后再补充正文与标签。"


def _progress_meta(t: Task) -> dict:
    default_steps = [
        {"key": "prepare", "label": "准备任务", "progress": 5},
        {"key": "collect", "label": "采集主页公开内容", "progress": 40},
        {"key": "analyze", "label": "识别主题与互动表现", "progress": 70},
        {"key": "report", "label": "生成分析报告", "progress": 90},
        {"key": "finish", "label": "保存结果", "progress": 100},
    ]
    meta = {}
    if t.run_log:
        try:
            parsed = json.loads(t.run_log)
            if isinstance(parsed, dict):
                meta = parsed
        except Exception:
            meta = {}

    progress = t.progress or 0
    status = t.status or "pending"
    if status == "completed":
        stage = "分析完成"
        detail = "报告已生成，可以查看结果。"
    elif status == "failed":
        stage = "分析失败"
        detail = t.error_message or "任务失败，请检查 Cookie、主页链接和网络状态。"
    elif status == "pending":
        stage = "等待开始"
        detail = "任务已创建，等待本地分析工具开始处理。"
    else:
        stage = meta.get("stage") or "分析进行中"
        detail = meta.get("detail") or "本地工具正在处理数据。"

    steps = meta.get("steps") if isinstance(meta.get("steps"), list) else default_steps
    return {
        "stage": stage,
        "detail": detail,
        "steps": steps,
        "updated_at": meta.get("updated_at", ""),
        "is_precise": bool(meta),
        "progress": progress,
    }


def _task_to_out(t: Task) -> dict:
    return {
        "id": t.id,
        "account_id": t.account_id,
        "task_type": t.task_type or "full_analysis",
        "status": t.status or "pending",
        "progress": t.progress or 0,
        "error_message": t.error_message,
        "created_at": str(t.created_at or ""),
        "started_at": str(t.started_at or ""),
        "completed_at": str(t.completed_at or ""),
        "progress_meta": _progress_meta(t),
    }


def _normalize_profile_url(profile_url: str) -> str:
    url = (profile_url or "").strip()
    if re.fullmatch(r"[A-Za-z0-9_-]{8,64}", url):
        return f"https://www.xiaohongshu.com/user/profile/{url}"
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        raise HTTPException(status_code=400, detail=MSG_BAD_URL)
    if "xiaohongshu.com" not in parsed.netloc:
        raise HTTPException(status_code=400, detail=MSG_BAD_DOMAIN)
    if "/user/profile/" not in parsed.path:
        raise HTTPException(status_code=400, detail=MSG_BAD_PROFILE_PATH)
    return url


def _ensure_task_slot(db: Session, user_id: int):
    active_count = (
        db.query(Task)
        .filter(Task.user_id == user_id, Task.status.in_(("pending", "running")))
        .count()
    )
    if active_count >= settings.max_active_tasks_per_user:
        raise HTTPException(status_code=429, detail=MSG_TASK_LIMIT)


def _get_valid_cookie(db: Session, cookie_id: int, user_id: int) -> Cookie:
    cookie = db.query(Cookie).filter(Cookie.id == cookie_id, Cookie.user_id == user_id).first()
    if not cookie:
        raise HTTPException(status_code=400, detail=MSG_COOKIE_NOT_FOUND)
    try:
        cookie.cookie_json = cookies_array_to_dict(cookie.cookie_json)
        cookie.is_valid = True
    except ValueError as e:
        cookie.is_valid = False
        db.commit()
        raise HTTPException(status_code=400, detail=str(e))
    return cookie


@router.post("/")
def create_task(
    body: TaskCreate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Create a new full-analysis task."""
    user_id = current_user["id"]
    profile_url = _normalize_profile_url(body.profile_url)
    _ensure_task_slot(db, user_id)
    _get_valid_cookie(db, body.cookie_id, user_id)

    account = (
        db.query(Account)
        .filter(Account.user_id == user_id, Account.profile_url == profile_url)
        .first()
    )
    if not account:
        account = Account(user_id=user_id, profile_url=profile_url)
        db.add(account)
        db.flush()

    task = Task(
        user_id=user_id,
        account_id=account.id,
        cookie_id=body.cookie_id,
        task_type="full_analysis",
        status="pending",
    )
    db.add(task)
    db.commit()
    db.refresh(task)

    submit_task(task.id, body.enable_ai_agent)
    return _task_to_out(task)


@router.get("/")
def list_tasks(db: Session = Depends(get_db), current_user: dict = Depends(get_current_user)):
    tasks = (
        db.query(Task)
        .filter(Task.user_id == current_user["id"])
        .order_by(Task.created_at.desc())
        .limit(50)
        .all()
    )
    return [_task_to_out(t) for t in tasks]


@router.post("/competitor-discover")
def competitor_discover(
    body: CompetitorDiscoverRequest,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Create a competitor discovery task."""
    user_id = current_user["id"]
    _ensure_task_slot(db, user_id)
    keyword = body.keyword.strip()
    if not keyword:
        raise HTTPException(status_code=400, detail=MSG_KEYWORD_REQUIRED)

    count = max(1, min(body.count, settings.max_competitor_count))
    _get_valid_cookie(db, body.cookie_id, user_id)

    task = Task(
        user_id=user_id,
        cookie_id=body.cookie_id,
        task_type="competitor_discovery",
        status="pending",
    )
    db.add(task)
    db.commit()
    db.refresh(task)

    submit_competitor_discovery(task.id, keyword, count)
    return _task_to_out(task)


@router.get("/{task_id}")
def get_task(
    task_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    task = (
        db.query(Task)
        .filter(Task.id == task_id, Task.user_id == current_user["id"])
        .first()
    )
    if not task:
        raise HTTPException(status_code=404, detail=MSG_TASK_NOT_FOUND)
    return _task_to_out(task)


@router.post("/{task_id}/cancel")
def cancel_task(
    task_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    task = (
        db.query(Task)
        .filter(Task.id == task_id, Task.user_id == current_user["id"])
        .first()
    )
    if not task:
        raise HTTPException(status_code=404, detail=MSG_TASK_NOT_FOUND)
    from backend.tasks.worker import _cancel_task

    if _cancel_task(task_id):
        return {"ok": True, "message": MSG_TASK_CANCELLED}
    raise HTTPException(status_code=400, detail=MSG_TASK_NOT_RUNNING)


@router.post("/{task_id}/detail-fetch")
def start_detail_fetch(
    task_id: int,
    body: dict = None,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    task = (
        db.query(Task)
        .filter(Task.id == task_id, Task.user_id == current_user["id"])
        .first()
    )
    if not task:
        raise HTTPException(status_code=404, detail=MSG_TASK_NOT_FOUND)
    if task.status in ("pending", "running"):
        raise HTTPException(status_code=400, detail="当前任务正在运行，请稍后再试。")
    if task.status != "completed":
        raise HTTPException(status_code=400, detail=MSG_TASK_NOT_COMPLETED)
    _ensure_task_slot(db, current_user["id"])
    max_count = int((body or {}).get("max_count", 25))
    max_count = max(1, min(max_count, 30))
    task.status = "pending"
    task.progress = 0
    task.error_message = "正在补充正文与标签分析。"
    db.commit()
    db.refresh(task)
    submit_detail_enrichment(task_id, max_count=max_count)
    return _task_to_out(task)


@router.get("/{task_id}/detail-fetch")
def get_detail_fetch_status(
    task_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    task = (
        db.query(Task)
        .filter(Task.id == task_id, Task.user_id == current_user["id"])
        .first()
    )
    if not task:
        raise HTTPException(status_code=404, detail=MSG_TASK_NOT_FOUND)
    path = Path(settings.data_dir) / "tasks" / str(task_id) / "detail_fetch.json"
    if not path.exists():
        return {"enabled": False}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {"enabled": False, "error": "detail_fetch.json 不可读取"}
