"""Authenticated collection and downloads for the note organizer."""
import json
from pathlib import Path
from typing import Literal
import tempfile
from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import BaseModel, constr
from sqlalchemy.orm import Session
from backend.config import settings
from backend.database import Account, Task, get_db
from backend.routers.auth import get_current_user
from backend.routers.tasks import _ensure_task_slot, _get_valid_cookie, _normalize_profile_url, _task_to_out
from backend.services.note_library import csv_bytes, select_rows, xlsx_bytes
from backend.services.ai_agent import ai_config_status
from backend.services.library_analysis import render_html
from backend.tasks.analysis_worker import start_analysis, read_state, approve

router = APIRouter(prefix="/api/library", tags=["note-library"])


class CollectionRequest(BaseModel):
    profile_url: str
    cookie_id: int


def create_collection(db, user_id, profile_url, cookie_id):
    from backend.tasks.library_worker import submit_collection
    profile_url = _normalize_profile_url(profile_url)
    _ensure_task_slot(db, user_id)
    _get_valid_cookie(db, cookie_id, user_id)
    account = db.query(Account).filter(Account.user_id == user_id, Account.profile_url == profile_url).first()
    if not account:
        account = Account(user_id=user_id, profile_url=profile_url)
        db.add(account)
        db.flush()
    task = Task(user_id=user_id, account_id=account.id, cookie_id=cookie_id, task_type="note_collection", status="pending")
    db.add(task)
    db.commit()
    db.refresh(task)
    submit_collection(task.id)
    return task


@router.post("/")
def start(body: CollectionRequest, db: Session = Depends(get_db), user=Depends(get_current_user)):
    return _task_to_out(create_collection(db, user["id"], body.profile_url, body.cookie_id))


def dataset_for(task_id, db, user):
    task = db.query(Task).filter(Task.id == task_id, Task.user_id == user["id"], Task.task_type == "note_collection").first()
    if not task:
        raise HTTPException(404, "整理任务不存在")
    path = Path(settings.data_dir) / "tasks" / str(task_id) / "dataset.json"
    dataset = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {"rows": [], "status": task.status, "summary": {}, "stop_reason": ""}
    if task.status in ("completed", "partial", "failed", "cancelled"):
        dataset["status"] = task.status
        if task.error_message:
            dataset["stop_reason"] = task.error_message
    return dataset


@router.get("/{task_id}")
def get_dataset(task_id: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    return dataset_for(task_id, db, user)


@router.get("/{task_id}/export")
def export(task_id: int, format: Literal["xlsx", "csv", "feishu"] = "xlsx",
           sort: Literal["list_order", "published_at", "liked_count", "collected_count", "comment_count", "share_count"] = "list_order",
           top: int = Query(0, ge=0, le=100), q: str = "", after: str = "", before: str = "", above_median: bool = False,
           db: Session = Depends(get_db), user=Depends(get_current_user)):
    dataset = dataset_for(task_id, db, user)
    rows = select_rows(dataset, sort, top, q, after, before, above_median)
    if format == "csv":
        payload, ext, mime = csv_bytes(rows), "csv", "text/csv; charset=utf-8"
    else:
        payload, ext, mime = xlsx_bytes(dataset, rows, feishu=format == "feishu"), "xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    return Response(payload, media_type=mime, headers={"Content-Disposition": f'attachment; filename="xhs-{task_id}-{format}.{ext}"', "Cache-Control": "no-store"})


class AnalysisRequest(BaseModel):
    goal: constr(strip_whitespace=True, min_length=5, max_length=1200)
    consent: bool = False


class ApprovalRequest(BaseModel):
    run_id: str
    confirmed: bool = False


def analysis_dir(task_id: int) -> Path:
    return Path(settings.data_dir) / "tasks" / str(task_id)


@router.get("/{task_id}/analysis")
def analysis_status(task_id: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    dataset = dataset_for(task_id, db, user)
    state = read_state(analysis_dir(task_id), dataset)
    cfg = ai_config_status(user["id"])
    return {**state, "configured": cfg["configured"], "model": cfg["model"], "provider": cfg["provider"]}


@router.post("/{task_id}/analysis", status_code=202)
def analyze(task_id: int, body: AnalysisRequest, db: Session = Depends(get_db), user=Depends(get_current_user)):
    dataset = dataset_for(task_id, db, user)
    task = db.query(Task).filter(Task.id == task_id, Task.user_id == user["id"]).first()
    if task.status in ("pending", "running"):
        raise HTTPException(409, "请等待采集结束或先停止采集，再分析固定的一批内容。")
    if not body.consent:
        raise HTTPException(400, "请确认将所选账号的公开文字和本次目标发送给你配置的 AI 服务商，并承担 API 费用。")
    try:
        return start_analysis(analysis_dir(task_id), dataset, body.goal, ai_config_status(user["id"]), user["id"])
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from None


@router.post("/{task_id}/analysis/approve")
def approve_analysis(task_id: int, body: ApprovalRequest, db: Session = Depends(get_db), user=Depends(get_current_user)):
    dataset = dataset_for(task_id, db, user)
    if not body.confirmed:
        raise HTTPException(400, "请先确认已人工检查结论、原文证据与创作草稿。")
    try:
        return approve(analysis_dir(task_id), dataset, body.run_id)
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from None


@router.get("/{task_id}/analysis/export")
def export_analysis(task_id: int, format: Literal["html", "pdf"] = "html", preview: bool = False,
                    db: Session = Depends(get_db), user=Depends(get_current_user)):
    dataset = dataset_for(task_id, db, user)
    state = read_state(analysis_dir(task_id), dataset)
    if state.get("status") != "ready":
        raise HTTPException(409, "没有与当前笔记库匹配的完整报告，请先生成。")
    report = state["report"]
    if not preview and report.get("review") != "approved":
        raise HTTPException(409, "请先人工复核并确认交付；仍可预览草稿。")
    markup = render_html(report)
    if format == "pdf":
        from backend.services.delivery import render_pdf
        try:
            with tempfile.TemporaryDirectory(prefix="xhs-delivery-") as root:
                source, output = Path(root) / "report.html", Path(root) / "report.pdf"
                source.write_text(markup, encoding="utf-8")
                payload = render_pdf(source, output).read_bytes()
        except Exception:
            raise HTTPException(503, "PDF 导出失败，请确认已安装 Edge/Chrome；可以先下载网页版。") from None
        mime = "application/pdf"
    else:
        payload, mime = markup.encode("utf-8"), "text/html; charset=utf-8"
    return Response(payload, media_type=mime, headers={"Content-Disposition": f'attachment; filename="content-report-{task_id}.{format}"', "Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"})
