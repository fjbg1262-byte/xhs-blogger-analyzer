"""Minimal central collector for anonymous product telemetry."""

from __future__ import annotations

import json
import os
import sqlite3
import threading
import time
from collections import defaultdict, deque
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Header, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field, validator


DATABASE_PATH = Path(os.environ.get("TELEMETRY_DATABASE", "data/telemetry.db"))
INGEST_KEY = os.environ.get("TELEMETRY_INGEST_KEY", "")
ADMIN_TOKEN = os.environ.get("TELEMETRY_ADMIN_TOKEN", "")
EVENT_NAMES = {
    "app_started",
    "extension_connected",
    "analysis_started",
    "analysis_completed",
    "analysis_failed",
    "report_opened",
    "diagnostic_copied",
    "feedback_submitted",
}
PROPERTY_RULES = {
    "app_started": set(),
    "extension_connected": set(),
    "analysis_started": {"task_type"},
    "analysis_completed": {"task_type", "duration_ms"},
    "analysis_failed": {"task_type", "duration_ms", "error_code", "stage"},
    "report_opened": {"task_type"},
    "diagnostic_copied": {"error_code"},
    "feedback_submitted": {"feedback_kind"},
}
ALLOWED_TASK_TYPES = {"full_analysis", "detail_fetch", "competitor_discovery"}
ALLOWED_ERROR_CODES = {
    "dependency_missing",
    "cookie_invalid",
    "network_timeout",
    "collector_missing",
    "collection_failed",
    "analysis_failed",
    "report_failed",
    "unknown_error",
}
ALLOWED_STAGES = {"prepare", "collect", "analyze", "report", "save", "unknown"}

_rate_lock = threading.Lock()
_rate_windows: dict[str, deque[float]] = defaultdict(deque)

app = FastAPI(title="XHS Analyzer Anonymous Telemetry", version="1.0.0")


class EventIn(BaseModel):
    install_id: str = Field(min_length=32, max_length=32)
    app_version: str = Field(min_length=1, max_length=40)
    event_name: str
    properties: dict[str, Any] = Field(default_factory=dict)
    occurred_at: str = Field(max_length=50)

    class Config:
        extra = "forbid"

    @validator("install_id")
    def validate_install_id(cls, value: str) -> str:
        int(value, 16)
        return value.lower()

    @validator("event_name")
    def validate_event_name(cls, value: str) -> str:
        if value not in EVENT_NAMES:
            raise ValueError("unsupported event")
        return value


class FeedbackIn(BaseModel):
    install_id: str = Field(min_length=32, max_length=32)
    app_version: str = Field(min_length=1, max_length=40)
    feedback_kind: str
    rating: str
    reason: str = Field(default="", max_length=80)
    comment: str = Field(default="", max_length=500)
    reuse_intent: str = Field(default="", max_length=20)
    diagnostic_code: str = Field(default="", max_length=100)
    error_code: str = Field(default="", max_length=40)
    occurred_at: str = Field(max_length=50)

    class Config:
        extra = "forbid"

    @validator("install_id")
    def validate_install_id(cls, value: str) -> str:
        int(value, 16)
        return value.lower()

    @validator("feedback_kind")
    def validate_kind(cls, value: str) -> str:
        if value not in {"report", "failure"}:
            raise ValueError("unsupported feedback kind")
        return value

    @validator("rating")
    def validate_rating(cls, value: str) -> str:
        if value not in {"helpful", "not_helpful", "problem"}:
            raise ValueError("unsupported rating")
        return value

    @validator("reuse_intent")
    def validate_reuse_intent(cls, value: str) -> str:
        if value not in {"", "yes", "maybe", "no"}:
            raise ValueError("unsupported reuse intent")
        return value

    @validator("error_code")
    def validate_error_code(cls, value: str) -> str:
        if value and value not in ALLOWED_ERROR_CODES:
            raise ValueError("unsupported error code")
        return value


def _connect() -> sqlite3.Connection:
    DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(str(DATABASE_PATH), timeout=10)
    connection.row_factory = sqlite3.Row
    return connection


@contextmanager
def _database():
    connection = _connect()
    try:
        yield connection
        connection.commit()
    finally:
        connection.close()


def _init_db() -> None:
    with _database() as db:
        db.executescript(
            """
            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                install_id TEXT NOT NULL,
                app_version TEXT NOT NULL,
                event_name TEXT NOT NULL,
                properties_json TEXT NOT NULL,
                occurred_at TEXT NOT NULL,
                received_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_events_install ON events(install_id);
            CREATE INDEX IF NOT EXISTS idx_events_name ON events(event_name);
            CREATE INDEX IF NOT EXISTS idx_events_received ON events(received_at);

            CREATE TABLE IF NOT EXISTS feedback (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                install_id TEXT NOT NULL,
                app_version TEXT NOT NULL,
                feedback_kind TEXT NOT NULL,
                rating TEXT NOT NULL,
                reason TEXT NOT NULL,
                comment TEXT NOT NULL,
                reuse_intent TEXT NOT NULL,
                diagnostic_code TEXT NOT NULL,
                error_code TEXT NOT NULL,
                occurred_at TEXT NOT NULL,
                received_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_feedback_received ON feedback(received_at);
            """
        )


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _require_ingest_key(value: str) -> None:
    if INGEST_KEY and value != INGEST_KEY:
        raise HTTPException(status_code=401, detail="invalid ingest key")


def _require_admin(value: str) -> None:
    if not ADMIN_TOKEN or value != ADMIN_TOKEN:
        raise HTTPException(status_code=401, detail="invalid admin token")


def _rate_limit(install_id: str) -> None:
    now = time.monotonic()
    cutoff = now - 3600
    with _rate_lock:
        window = _rate_windows[install_id]
        while window and window[0] < cutoff:
            window.popleft()
        if len(window) >= 120:
            raise HTTPException(status_code=429, detail="rate limit exceeded")
        window.append(now)


def _sanitize_properties(event_name: str, properties: dict[str, Any]) -> dict[str, Any]:
    clean: dict[str, Any] = {}
    for key in PROPERTY_RULES[event_name]:
        value = properties.get(key)
        if value is None:
            continue
        if key == "duration_ms":
            try:
                clean[key] = max(0, min(int(value), 3_600_000))
            except (TypeError, ValueError):
                continue
        elif key == "task_type" and str(value) in ALLOWED_TASK_TYPES:
            clean[key] = str(value)
        elif key == "error_code" and str(value) in ALLOWED_ERROR_CODES:
            clean[key] = str(value)
        elif key == "stage" and str(value) in ALLOWED_STAGES:
            clean[key] = str(value)
        elif key == "feedback_kind" and str(value) in {"report", "failure"}:
            clean[key] = str(value)
    return clean


@app.on_event("startup")
def startup() -> None:
    _init_db()


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/v1/events")
def ingest_event(body: EventIn, x_ingest_key: str = Header(default="")) -> dict[str, bool]:
    _require_ingest_key(x_ingest_key)
    _rate_limit(body.install_id)
    properties = _sanitize_properties(body.event_name, body.properties)
    with _database() as db:
        db.execute(
            """
            INSERT INTO events (
                install_id, app_version, event_name, properties_json, occurred_at, received_at
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                body.install_id,
                body.app_version,
                body.event_name,
                json.dumps(properties, ensure_ascii=False),
                body.occurred_at,
                _utc_now(),
            ),
        )
    return {"accepted": True}


@app.post("/v1/feedback")
def ingest_feedback(body: FeedbackIn, x_ingest_key: str = Header(default="")) -> dict[str, bool]:
    _require_ingest_key(x_ingest_key)
    _rate_limit(body.install_id)
    with _database() as db:
        db.execute(
            """
            INSERT INTO feedback (
                install_id, app_version, feedback_kind, rating, reason, comment,
                reuse_intent, diagnostic_code, error_code, occurred_at, received_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                body.install_id,
                body.app_version,
                body.feedback_kind,
                body.rating,
                body.reason,
                body.comment,
                body.reuse_intent,
                body.diagnostic_code,
                body.error_code,
                body.occurred_at,
                _utc_now(),
            ),
        )
    return {"accepted": True}


def _count_distinct(db: sqlite3.Connection, event_name: str) -> int:
    row = db.execute(
        "SELECT COUNT(DISTINCT install_id) AS count FROM events WHERE event_name = ?",
        (event_name,),
    ).fetchone()
    return int(row["count"] or 0)


@app.get("/v1/admin/summary")
def admin_summary(x_admin_token: str = Header(default="")) -> dict[str, Any]:
    _require_admin(x_admin_token)
    with _database() as db:
        installs = _count_distinct(db, "app_started")
        analysis_started = _count_distinct(db, "analysis_started")
        analysis_completed = _count_distinct(db, "analysis_completed")
        reports_opened = _count_distinct(db, "report_opened")
        repeat_row = db.execute(
            """
            SELECT COUNT(*) AS count FROM (
                SELECT install_id
                FROM events
                WHERE event_name = 'analysis_started'
                GROUP BY install_id
                HAVING COUNT(*) >= 2
            )
            """
        ).fetchone()
        feedback_total = db.execute("SELECT COUNT(*) AS count FROM feedback").fetchone()["count"]
        report_feedback = db.execute(
            "SELECT rating, COUNT(*) AS count FROM feedback WHERE feedback_kind = 'report' GROUP BY rating"
        ).fetchall()
        feedback_counts = {row["rating"]: row["count"] for row in report_feedback}
        failure_rows = db.execute(
            """
            SELECT json_extract(properties_json, '$.error_code') AS error_code, COUNT(*) AS count
            FROM events
            WHERE event_name = 'analysis_failed'
            GROUP BY error_code
            ORDER BY count DESC
            """
        ).fetchall()
        day_rows = db.execute(
            """
            SELECT substr(received_at, 1, 10) AS day, COUNT(DISTINCT install_id) AS installs,
                   SUM(CASE WHEN event_name = 'analysis_completed' THEN 1 ELSE 0 END) AS completed
            FROM events
            GROUP BY day
            ORDER BY day DESC
            LIMIT 14
            """
        ).fetchall()

    helpful = int(feedback_counts.get("helpful", 0))
    not_helpful = int(feedback_counts.get("not_helpful", 0))
    rated = helpful + not_helpful
    return {
        "funnel": {
            "started_app": installs,
            "started_analysis": analysis_started,
            "completed_analysis": analysis_completed,
            "opened_report": reports_opened,
            "repeat_users": int(repeat_row["count"] or 0),
        },
        "rates": {
            "first_analysis_rate": round(analysis_started / installs * 100, 1) if installs else 0,
            "completion_rate": round(analysis_completed / analysis_started * 100, 1) if analysis_started else 0,
            "report_open_rate": round(reports_opened / analysis_completed * 100, 1) if analysis_completed else 0,
            "helpful_rate": round(helpful / rated * 100, 1) if rated else 0,
        },
        "feedback_total": int(feedback_total or 0),
        "failures": [
            {"error_code": row["error_code"] or "unknown_error", "count": row["count"]}
            for row in failure_rows
        ],
        "daily": [dict(row) for row in day_rows],
    }


@app.get("/v1/admin/feedback")
def admin_feedback(x_admin_token: str = Header(default="")) -> dict[str, Any]:
    _require_admin(x_admin_token)
    with _database() as db:
        rows = db.execute(
            """
            SELECT app_version, feedback_kind, rating, reason, comment, reuse_intent,
                   diagnostic_code, error_code, received_at
            FROM feedback
            ORDER BY id DESC
            LIMIT 100
            """
        ).fetchall()
    return {"feedback": [dict(row) for row in rows]}


DASHBOARD_HTML = """<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>测试反馈后台</title>
  <style>
    :root { --red:#ff3158; --ink:#151318; --muted:#746b70; --line:#efdce1; --green:#1ca96b; }
    * { box-sizing:border-box; }
    body { margin:0; background:#fff8f9; color:var(--ink); font-family:"Microsoft YaHei","Segoe UI",sans-serif; }
    main { width:min(1120px,calc(100% - 28px)); margin:0 auto; padding:28px 0 48px; }
    header { display:flex; justify-content:space-between; gap:18px; align-items:flex-end; margin-bottom:20px; }
    h1,h2,p { margin:0; } h1 { font-size:28px; } header p { color:var(--muted); margin-top:5px; }
    .login { display:flex; gap:8px; } input,button { min-height:38px; border-radius:6px; font:inherit; }
    input { width:240px; border:1px solid var(--line); padding:8px 10px; }
    button { border:0; background:var(--red); color:#fff; padding:8px 14px; font-weight:800; cursor:pointer; }
    .funnel { display:grid; grid-template-columns:repeat(5,1fr); border:1px solid var(--line); background:#fff; }
    .funnel article { padding:18px; border-right:1px solid var(--line); }
    .funnel article:last-child { border-right:0; } article span { color:var(--muted); font-size:12px; }
    article strong { display:block; margin-top:4px; font-size:27px; }
    .rates { display:grid; grid-template-columns:repeat(4,1fr); gap:10px; margin-top:12px; }
    .rates article { padding:14px; border:1px solid var(--line); background:#fff; }
    section { margin-top:22px; } section h2 { margin-bottom:10px; font-size:19px; }
    .split { display:grid; grid-template-columns:0.8fr 1.2fr; gap:18px; }
    table { width:100%; border-collapse:collapse; background:#fff; border:1px solid var(--line); }
    th,td { padding:10px; border-bottom:1px solid var(--line); text-align:left; font-size:13px; vertical-align:top; }
    th { color:var(--muted); background:#fff0f3; } .comment { min-width:240px; white-space:pre-wrap; }
    .empty { padding:24px; border:1px dashed var(--line); color:var(--muted); background:#fff; }
    #error { color:#a31535; margin-top:8px; }
    @media(max-width:800px){ header{align-items:stretch;flex-direction:column}.login input{width:100%}.funnel{grid-template-columns:1fr 1fr}.funnel article{border-bottom:1px solid var(--line)}.rates,.split{grid-template-columns:1fr 1fr}.table-wrap{overflow:auto} }
    @media(max-width:520px){ .rates,.split{grid-template-columns:1fr}.login{display:grid;grid-template-columns:1fr auto} }
  </style>
</head>
<body>
<main>
  <header>
    <div><h1>测试反馈后台</h1><p>只显示匿名产品事件和用户主动填写的反馈。</p></div>
    <div><div class="login"><input id="token" type="password" placeholder="输入后台查看口令" /><button onclick="loadAll()">查看数据</button></div><p id="error"></p></div>
  </header>
  <div id="content" hidden>
    <div class="funnel" id="funnel"></div>
    <div class="rates" id="rates"></div>
    <div class="split">
      <section><h2>失败类型</h2><div class="table-wrap"><table><thead><tr><th>错误代码</th><th>次数</th></tr></thead><tbody id="failures"></tbody></table></div></section>
      <section><h2>最近 14 天</h2><div class="table-wrap"><table><thead><tr><th>日期</th><th>活跃安装</th><th>完成分析</th></tr></thead><tbody id="daily"></tbody></table></div></section>
    </div>
    <section><h2>最近反馈</h2><div class="table-wrap"><table><thead><tr><th>时间</th><th>类型</th><th>评价</th><th>原因</th><th>会再用</th><th>用户原话</th><th>诊断编号</th></tr></thead><tbody id="feedback"></tbody></table></div></section>
  </div>
</main>
<script>
const esc=(v)=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
async function api(path){const token=document.getElementById('token').value;const r=await fetch(path,{headers:{'X-Admin-Token':token}});if(!r.ok)throw new Error('口令不正确或服务不可用');return r.json()}
async function loadAll(){const error=document.getElementById('error');error.textContent='';try{const [s,f]=await Promise.all([api('/v1/admin/summary'),api('/v1/admin/feedback')]);render(s,f);document.getElementById('content').hidden=false}catch(e){error.textContent=e.message}}
function render(s,f){
 const labels={started_app:'启动过',started_analysis:'开始分析',completed_analysis:'完成分析',opened_report:'打开报告',repeat_users:'重复使用'};
 document.getElementById('funnel').innerHTML=Object.entries(s.funnel).map(([k,v])=>`<article><span>${labels[k]||esc(k)}</span><strong>${v}</strong></article>`).join('');
 const rates={first_analysis_rate:'首次分析率',completion_rate:'分析完成率',report_open_rate:'报告打开率',helpful_rate:'报告有用率'};
 document.getElementById('rates').innerHTML=Object.entries(s.rates).map(([k,v])=>`<article><span>${rates[k]||esc(k)}</span><strong>${v}%</strong></article>`).join('');
 document.getElementById('failures').innerHTML=s.failures.length?s.failures.map(x=>`<tr><td>${esc(x.error_code)}</td><td>${x.count}</td></tr>`).join(''):'<tr><td colspan="2">暂无失败记录</td></tr>';
 document.getElementById('daily').innerHTML=s.daily.length?s.daily.map(x=>`<tr><td>${esc(x.day)}</td><td>${x.installs}</td><td>${x.completed}</td></tr>`).join(''):'<tr><td colspan="3">暂无数据</td></tr>';
 document.getElementById('feedback').innerHTML=f.feedback.length?f.feedback.map(x=>`<tr><td>${esc(x.received_at.slice(0,19))}</td><td>${esc(x.feedback_kind)}</td><td>${esc(x.rating)}</td><td>${esc(x.reason)}</td><td>${esc(x.reuse_intent)}</td><td class="comment">${esc(x.comment)}</td><td>${esc(x.diagnostic_code)}</td></tr>`).join(''):'<tr><td colspan="7">暂无反馈</td></tr>';
}
</script>
</body>
</html>"""


@app.get("/dashboard", response_class=HTMLResponse)
def dashboard() -> str:
    return DASHBOARD_HTML
