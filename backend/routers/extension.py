"""Local browser extension endpoints."""

from datetime import datetime
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.database import Account, Cookie, Task, User, get_db
from backend.routers.auth import _create_jwt
from backend.routers.tasks import _ensure_task_slot, _normalize_profile_url, _task_to_out
from backend.tasks.worker import submit_task
from backend.utils.cookie import cookies_array_to_dict

router = APIRouter(prefix="/api/extension", tags=["extension"])

LOCAL_USERNAME = "local_extension_user"
LOCAL_PASSWORD_HASH = "local-extension-only"
FRONTEND_BASE_URL = "http://127.0.0.1:8000"

MSG_COOKIE_REQUIRED = "\u8bf7\u5148\u5728\u5f53\u524d\u6d4f\u89c8\u5668\u91cc\u767b\u5f55\u5c0f\u7ea2\u4e66\uff0c\u7136\u540e\u518d\u70b9\u51fb\u5206\u6790\u3002"


class ExtensionAnalyzeRequest(BaseModel):
    profile_url: str
    cookie_text: str


def _get_or_create_local_user(db: Session) -> User:
    user = db.query(User).filter(User.username == LOCAL_USERNAME).first()
    if user:
        return user

    user = User(username=LOCAL_USERNAME, password_hash=LOCAL_PASSWORD_HASH)
    db.add(user)
    db.flush()
    return user


def _save_extension_cookie(db: Session, user_id: int, cookie_text: str) -> Cookie:
    try:
        normalized = cookies_array_to_dict(cookie_text)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=MSG_COOKIE_REQUIRED) from exc

    cookie = (
        db.query(Cookie)
        .filter(Cookie.user_id == user_id, Cookie.nickname == "browser_extension")
        .first()
    )
    if not cookie:
        cookie = Cookie(user_id=user_id, nickname="browser_extension")
        db.add(cookie)

    cookie.cookie_json = normalized
    cookie.is_active = True
    cookie.is_valid = True
    cookie.validated_at = datetime.utcnow()
    db.flush()
    return cookie


@router.post("/analyze-current")
def analyze_current(body: ExtensionAnalyzeRequest, db: Session = Depends(get_db)):
    """Create a local analysis task from the browser extension."""
    user = _get_or_create_local_user(db)
    profile_url = _normalize_profile_url(body.profile_url)
    _ensure_task_slot(db, user.id)
    cookie = _save_extension_cookie(db, user.id, body.cookie_text)

    account = (
        db.query(Account)
        .filter(Account.user_id == user.id, Account.profile_url == profile_url)
        .first()
    )
    if not account:
        account = Account(user_id=user.id, profile_url=profile_url)
        db.add(account)
        db.flush()

    task = Task(
        user_id=user.id,
        account_id=account.id,
        cookie_id=cookie.id,
        task_type="full_analysis",
        status="pending",
    )
    db.add(task)
    db.commit()
    db.refresh(task)

    submit_task(task.id, enable_ai=False)

    token = _create_jwt({"sub": str(user.id), "username": user.username})
    redirect = quote(f"/analysis/{task.id}", safe="")
    username = quote(user.username, safe="")
    report_url = (
        f"{FRONTEND_BASE_URL}/extension-login"
        f"?token={quote(token, safe='')}&username={username}&redirect={redirect}"
    )

    return {
        "task_id": task.id,
        "task": _task_to_out(task),
        "report_url": report_url,
    }
