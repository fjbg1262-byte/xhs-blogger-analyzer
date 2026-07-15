"""JWT auth endpoints — pure Python implementation (no jose library needed)."""

import hashlib
import hmac
import json
import time
import base64
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Header
from sqlalchemy.orm import Session

from backend.config import settings
from backend.database import get_db, User
from backend.models.schemas import UserRegister, UserLogin, TokenResponse, UserInfo

router = APIRouter(prefix="/api/auth", tags=["auth"])


def _hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()


def _base64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _base64url_decode(s: str) -> bytes:
    s = s + "=" * (4 - len(s) % 4)
    return base64.urlsafe_b64decode(s)


def _create_jwt(payload: dict) -> str:
    header = _base64url_encode(json.dumps({"alg": "HS256", "typ": "JWT"}).encode())
    payload["iat"] = int(time.time())
    payload["exp"] = int(time.time()) + settings.jwt_expire_minutes * 60
    payload_b64 = _base64url_encode(json.dumps(payload).encode())
    signature = hmac.new(
        settings.secret_key.encode(),
        f"{header}.{payload_b64}".encode(),
        hashlib.sha256,
    ).digest()
    sig_b64 = _base64url_encode(signature)
    return f"{header}.{payload_b64}.{sig_b64}"


def decode_jwt(token: str) -> dict:
    """Decode and verify JWT. Returns payload dict."""
    parts = token.split(".")
    if len(parts) != 3:
        raise HTTPException(status_code=401, detail="Invalid token")

    # Verify signature
    expected_sig = hmac.new(
        settings.secret_key.encode(),
        f"{parts[0]}.{parts[1]}".encode(),
        hashlib.sha256,
    ).digest()
    actual_sig = _base64url_decode(parts[2])

    if not hmac.compare_digest(expected_sig, actual_sig):
        raise HTTPException(status_code=401, detail="Invalid token signature")

    payload = json.loads(_base64url_decode(parts[1]))
    if payload.get("exp", 0) < time.time():
        raise HTTPException(status_code=401, detail="Token expired")

    return payload


def get_current_user(authorization: str = Header(None)):
    """FastAPI dependency to get current user from Authorization header."""
    if not authorization:
        raise HTTPException(status_code=401, detail="Unauthorized")
    token = authorization.replace("Bearer ", "")
    payload = decode_jwt(token)
    return {"id": int(payload["sub"]), "username": payload.get("username", "")}


@router.post("/register", response_model=TokenResponse)
def register(body: UserRegister, db: Session = Depends(get_db)):
    existing = db.query(User).filter(User.username == body.username).first()
    if existing:
        raise HTTPException(status_code=400, detail="Username already exists")

    user = User(username=body.username, password_hash=_hash_password(body.password))
    db.add(user)
    db.commit()
    db.refresh(user)

    token = _create_jwt({"sub": str(user.id), "username": user.username})
    return TokenResponse(access_token=token, user_id=user.id, username=user.username)


@router.post("/login", response_model=TokenResponse)
def login(body: UserLogin, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == body.username).first()
    if not user or user.password_hash != _hash_password(body.password):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    token = _create_jwt({"sub": str(user.id), "username": user.username})
    return TokenResponse(access_token=token, user_id=user.id, username=user.username)


@router.get("/me", response_model=UserInfo)
def get_me(current_user: dict = Depends(get_current_user)):
    return UserInfo(id=current_user["id"], username=current_user["username"])
