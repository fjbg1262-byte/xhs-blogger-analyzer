"""Pydantic V1 request/response schemas."""

from pydantic import BaseModel
from typing import Optional, List


# Auth
class UserRegister(BaseModel):
    username: str
    password: str


class UserLogin(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: int
    username: str


class UserInfo(BaseModel):
    id: int
    username: str

    class Config:
        orm_mode = True


# Cookies
class CookieCreate(BaseModel):
    cookie_json: str
    nickname: Optional[str] = None


class CookieOut(BaseModel):
    id: int
    nickname: Optional[str]
    is_active: bool
    is_valid: Optional[bool]
    created_at: str

    class Config:
        orm_mode = True


# Tasks
class TaskCreate(BaseModel):
    profile_url: str
    cookie_id: int
    enable_ai_agent: bool = False


class TaskOut(BaseModel):
    id: int
    account_id: Optional[int]
    task_type: str
    status: str
    progress: int
    error_message: Optional[str]
    created_at: str
    started_at: Optional[str]
    completed_at: Optional[str]

    class Config:
        orm_mode = True


class CompetitorDiscoverRequest(BaseModel):
    keyword: str
    count: int = 10
    cookie_id: int


# Accounts
class AccountOut(BaseModel):
    id: int
    profile_url: str
    nickname: Optional[str]
    follower_count: Optional[int]
    bio: Optional[str]
    avatar_url: Optional[str]
    last_task_id: Optional[int]

    class Config:
        orm_mode = True


# Reports
class ReportOut(BaseModel):
    report_type: str
    markdown_body: str


class CompareRequest(BaseModel):
    task_ids: List[int]


# AI
class DeconstructRequest(BaseModel):
    task_id: int


class DiagnoseRequest(BaseModel):
    task_id: int
    niche: Optional[str] = None


class RewriteRequest(BaseModel):
    original_title: str
    style: str = "high-engagement"
