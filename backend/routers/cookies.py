"""Cookie management endpoints — sync version."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.database import get_db, Cookie
from backend.models.schemas import CookieCreate, CookieOut
from backend.routers.auth import get_current_user
from backend.utils.cookie import cookies_array_to_dict

router = APIRouter(prefix="/api/cookies", tags=["cookies"])


@router.get("/")
def list_cookies(db: Session = Depends(get_db), current_user: dict = Depends(get_current_user)):
    """List all cookies for current user."""
    cookies = (
        db.query(Cookie)
        .filter(Cookie.user_id == current_user["id"])
        .order_by(Cookie.created_at.desc())
        .limit(50)
        .all()
    )
    return [
        CookieOut(
            id=c.id,
            nickname=c.nickname,
            is_active=c.is_active,
            is_valid=c.is_valid,
            created_at=str(c.created_at or ""),
        )
        for c in cookies
    ]


@router.post("/", response_model=CookieOut)
def create_cookie(
    body: CookieCreate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    try:
        normalized_cookie = cookies_array_to_dict(body.cookie_json)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    cookie = Cookie(
        user_id=current_user["id"],
        cookie_json=normalized_cookie,
        nickname=body.nickname,
        is_valid=True,
    )
    db.add(cookie)
    db.commit()
    db.refresh(cookie)

    return CookieOut(
        id=cookie.id,
        nickname=cookie.nickname,
        is_active=cookie.is_active,
        is_valid=cookie.is_valid,
        created_at=str(cookie.created_at or ""),
    )


@router.delete("/{cookie_id}")
def delete_cookie(
    cookie_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    cookie = (
        db.query(Cookie)
        .filter(Cookie.id == cookie_id, Cookie.user_id == current_user["id"])
        .first()
    )
    if not cookie:
        raise HTTPException(status_code=404, detail="Cookie not found")
    db.delete(cookie)
    db.commit()
    return {"ok": True}
