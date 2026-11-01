"""Workspace API for the new front end (Phase 2).

Read endpoints expose the dataset of a finished collection task in the shape the
workspace UI consumes; write endpoints only stop a running task or retry the
detail fetch of notes that failed. Nothing here changes the collection pipeline
or the dataset contract.
"""

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from backend.database import Account, Task, get_db
from backend.routers.auth import get_current_user
from backend.routers.library import export as library_export
from backend.services.note_workspace import (
    account_card,
    dataset_stats,
    load_dataset,
    notes_view,
    task_card,
)

router = APIRouter(prefix="/api/workspace", tags=["workspace"])

MSG_NO_TASK = "找不到这个采集任务，或它不属于当前账号。"
MSG_NO_DATA = "这个任务还没有可用的采集结果，可能仍在进行或已经失败。"


def _collection_task(db: Session, task_id: int, user_id: int) -> Task:
    task = (
        db.query(Task)
        .filter(Task.id == task_id, Task.user_id == user_id, Task.task_type == "note_collection")
        .first()
    )
    if not task:
        raise HTTPException(404, MSG_NO_TASK)
    return task


@router.get("/tasks")
def list_tasks(db: Session = Depends(get_db), user=Depends(get_current_user)):
    """Task cards plus one card per account (latest finished collection)."""
    tasks = (
        db.query(Task)
        .filter(Task.user_id == user["id"], Task.task_type == "note_collection")
        .order_by(Task.id.desc())
        .all()
    )
    cards = [task_card(task, load_dataset(task.id)) for task in tasks]

    latest_by_account = {}
    for task in tasks:
        if not task.account_id:
            continue
        current = latest_by_account.get(task.account_id)
        if current is None:
            latest_by_account[task.account_id] = task
            continue
        # Prefer the newest task that actually produced a dataset, so the account
        # card does not show 0 notes just because a newer task is still running.
        if not load_dataset(current.id) and load_dataset(task.id):
            latest_by_account[task.account_id] = task
    accounts = []
    for account_id, task in latest_by_account.items():
        account = db.query(Account).filter(Account.id == account_id, Account.user_id == user["id"]).first()
        accounts.append(account_card(account, task, load_dataset(task.id)))

    return {"tasks": cards, "accounts": accounts, "counts": {"tasks": len(cards), "accounts": len(accounts)}}


@router.get("/tasks/{task_id}")
def get_task(task_id: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    """Full workspace payload: task card, account, note rows and statistics."""
    task = _collection_task(db, task_id, user["id"])
    dataset = load_dataset(task_id)
    if dataset is None:
        raise HTTPException(404, MSG_NO_DATA)
    account = db.query(Account).filter(Account.id == task.account_id, Account.user_id == user["id"]).first()
    card = task_card(task, dataset)
    return {
        "task": card,
        "account": account_card(account, task, dataset),
        "notes": notes_view(dataset),
        "stats": dataset_stats(dataset),
        "meta": {
            "schema_version": dataset.get("schema_version", ""),
            "status": dataset.get("status", ""),
            "stop_reason": dataset.get("stop_reason", ""),
            "pages": dataset.get("pages", 0),
            "duplicates": dataset.get("duplicates", 0),
            "requested_limit": dataset.get("requested_limit", 0),
            "created_at": dataset.get("created_at", ""),
            "finished_at": dataset.get("finished_at", ""),
        },
    }


@router.get("/tasks/{task_id}/progress")
def get_progress(task_id: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    """Light polling payload for the collection progress panel."""
    task = _collection_task(db, task_id, user["id"])
    dataset = load_dataset(task_id)
    card = task_card(task, dataset)
    return {
        "task": card,
        "counts": {
            "note_count": card["note_count"],
            "body_count": card["body_count"],
            "failed_count": card["failed_count"],
        },
        "stage": (dataset or {}).get("stop_reason", "") or task.error_message or "",
    }


@router.get("/tasks/{task_id}/export")
def export(
    task_id: int,
    format: Literal["xlsx", "csv", "feishu"] = "xlsx",
    sort: Literal[
        "list_order", "published_at", "liked_count", "collected_count", "comment_count", "share_count"
    ] = "list_order",
    top: int = Query(0, ge=0, le=100),
    q: str = "",
    after: str = "",
    before: str = "",
    above_median: bool = False,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    """Same export contract as the legacy library page, kept in one place."""
    _collection_task(db, task_id, user["id"])
    return library_export(task_id, format, sort, top, q, after, before, above_median, db, user)


@router.post("/tasks/{task_id}/stop")
def stop(task_id: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    """Stop a running collection; already collected rows stay downloadable."""
    task = _collection_task(db, task_id, user["id"])
    if task.status not in ("pending", "running"):
        raise HTTPException(409, "这个任务已经结束，不需要停止。")
    from backend.tasks.worker import _cancel_task

    if not _cancel_task(task_id):
        task.status = "cancelled"
        task.error_message = "用户停止"
        db.commit()
    return {"ok": True, "task_id": task_id, "status": "cancelled"}


@router.post("/tasks/{task_id}/retry")
def retry(task_id: int, max_count: int = Query(10, ge=1, le=50), db: Session = Depends(get_db),
          user=Depends(get_current_user)):
    """Retry the detail fetch of notes whose detail or body is still missing."""
    task = _collection_task(db, task_id, user["id"])
    if task.status in ("pending", "running"):
        raise HTTPException(409, "任务正在采集，结束后再补采未完成笔记。")
    dataset = load_dataset(task_id)
    if dataset is None:
        raise HTTPException(404, MSG_NO_DATA)
    pending = [row for row in dataset.get("rows") or [] if row.get("detail_status") != "成功"]
    if not pending:
        return {"ok": True, "queued": 0, "message": "没有需要补采的笔记。"}
    if not task.cookie_id:
        raise HTTPException(400, "这个任务没有可用的登录状态，请用浏览器插件重新采集。")
    from backend.tasks.retry_worker import submit_retry

    submit_retry(task_id, min(max_count, len(pending)))
    return {"ok": True, "queued": min(max_count, len(pending)), "message": "已开始补采未完成笔记。"}
