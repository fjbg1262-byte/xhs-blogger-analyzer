"""Local telemetry preferences, events and user feedback."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend.database import Task, get_db
from backend.routers.auth import get_current_user
from backend.services.telemetry import (
    diagnostic_payload,
    public_preferences,
    save_consent,
    submit_feedback,
    track,
)


router = APIRouter(prefix="/api/telemetry", tags=["telemetry"])


class ConsentRequest(BaseModel):
    consent: str


class EventRequest(BaseModel):
    event_name: str
    properties: dict = Field(default_factory=dict)


class FeedbackRequest(BaseModel):
    task_id: int
    feedback_kind: str = "report"
    rating: str
    reason: str = ""
    comment: str = Field(default="", max_length=500)
    reuse_intent: str = ""


def _owned_task(task_id: int, user_id: int, db: Session) -> Task:
    task = db.query(Task).filter(Task.id == task_id, Task.user_id == user_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    return task


@router.get("/preferences")
def get_preferences(current_user: dict = Depends(get_current_user)):
    return public_preferences()


@router.put("/preferences")
def update_preferences(body: ConsentRequest, current_user: dict = Depends(get_current_user)):
    try:
        save_consent(body.consent)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="请选择允许或关闭匿名改进数据") from exc
    if body.consent == "granted":
        track("app_started")
    return public_preferences()


@router.post("/events")
def create_event(body: EventRequest, current_user: dict = Depends(get_current_user)):
    try:
        accepted = track(body.event_name, body.properties)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="不支持的匿名事件") from exc
    return {"accepted": accepted}


@router.get("/diagnostic/{task_id}")
def get_diagnostic(
    task_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    task = _owned_task(task_id, current_user["id"], db)
    return diagnostic_payload(task.id, task.error_message)


@router.post("/diagnostic/{task_id}/copied")
def diagnostic_copied(
    task_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    task = _owned_task(task_id, current_user["id"], db)
    payload = diagnostic_payload(task.id, task.error_message)
    return {
        "accepted": track("diagnostic_copied", {"error_code": payload["error_code"]}),
        **payload,
    }


@router.post("/feedback")
def create_feedback(
    body: FeedbackRequest,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    task = _owned_task(body.task_id, current_user["id"], db)
    if body.feedback_kind == "report" and task.status != "completed":
        raise HTTPException(status_code=400, detail="报告尚未完成")
    try:
        accepted = submit_feedback(
            task_id=task.id,
            feedback_kind=body.feedback_kind,
            rating=body.rating,
            reason=body.reason,
            comment=body.comment,
            reuse_intent=body.reuse_intent,
            error=task.error_message,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="反馈内容不符合要求") from exc
    return {
        "accepted": accepted,
        "message": "感谢反馈" if accepted else "匿名改进数据未开启，反馈没有发送",
    }
