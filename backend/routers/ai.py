"""AI Agent endpoints."""

import json
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.database import Task, get_db
from backend.models.schemas import DeconstructRequest, DiagnoseRequest, RewriteRequest
from backend.routers.auth import get_current_user
from backend.services.ai_agent import (
    compare_accounts,
    deconstruct_notes,
    diagnose_account,
    rewrite_content,
)

router = APIRouter(prefix="/api/ai", tags=["ai"])


def _get_owned_task(task_id: int, db: Session, current_user: dict) -> Task:
    task = (
        db.query(Task)
        .filter(Task.id == task_id, Task.user_id == current_user["id"])
        .first()
    )
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task


def _load_task_json(task_id: int, filename: str):
    path = Path("data") / "tasks" / str(task_id) / filename
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"{filename} not found")


@router.post("/deconstruct")
async def deconstruct(
    body: DeconstructRequest,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Deconstruct top notes to find viral patterns."""
    _get_owned_task(body.task_id, db, current_user)
    all_notes = _load_task_json(body.task_id, "all_notes.json")
    result = deconstruct_notes(all_notes, user_id=current_user["id"])
    return {"result": result}


@router.post("/diagnose")
async def diagnose(
    body: DiagnoseRequest,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Diagnose account performance."""
    _get_owned_task(body.task_id, db, current_user)
    results = _load_task_json(body.task_id, "results.json")
    result = diagnose_account(results, niche=body.niche, user_id=current_user["id"])
    return {"result": result}


@router.post("/rewrite")
async def rewrite(body: RewriteRequest, current_user: dict = Depends(get_current_user)):
    """Rewrite a title in a target style."""
    result = rewrite_content(body.original_title, body.style, user_id=current_user["id"])
    return {"result": result}


@router.post("/compare")
async def compare(
    body: dict,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Compare two accounts using their task results."""
    task_a = body.get("task_id_a")
    task_b = body.get("task_id_b")

    if not task_a or not task_b:
        raise HTTPException(status_code=400, detail="Need task_id_a and task_id_b")

    _get_owned_task(int(task_a), db, current_user)
    _get_owned_task(int(task_b), db, current_user)
    ra = _load_task_json(int(task_a), "results.json")
    rb = _load_task_json(int(task_b), "results.json")

    result = compare_accounts(ra, rb, user_id=current_user["id"])
    return {"result": result}
