"""FastAPI application entry point — sync version."""

import os

from backend.runtime import configure_runtime_environment, find_resource

configure_runtime_environment()

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from backend.database import init_db
from backend.config import settings
from backend.tasks.worker import init_worker
from backend.routers import ai, auth, cookies, extension, llm_config, reports, tasks, telemetry
from backend.services.telemetry import track

app = FastAPI(
    title="XHS Blogger Analyzer",
    description="小红书博主深度分析平台 — AI 驱动的 8 维度内容分析",
    version="1.0.0",
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Startup event
@app.on_event("startup")
def startup():
    print("[App] Initializing database...")
    os.makedirs(settings.data_dir, exist_ok=True)
    os.makedirs(settings.reports_dir, exist_ok=True)
    os.makedirs(settings.logs_dir, exist_ok=True)
    os.makedirs(os.path.join(settings.data_dir, "cookies"), exist_ok=True)
    os.makedirs(os.path.join(settings.data_dir, "tasks"), exist_ok=True)
    init_db()

    # Check Spider_XHS
    if not os.path.exists(settings.spider_xhs_dir):
        print(f"[App] WARNING: Spider_XHS not found at {settings.spider_xhs_dir}")
        print("[App] Clone it with: git clone https://github.com/cv-cat/Spider_XHS.git spider_xhs")

    init_worker()
    track("app_started")
    print("[App] Startup complete")


# Register routers
app.include_router(auth.router)
app.include_router(cookies.router)
app.include_router(tasks.router)
app.include_router(reports.router)
app.include_router(ai.router)
app.include_router(llm_config.router)
app.include_router(extension.router)
app.include_router(telemetry.router)


@app.get("/api/health")
def health():
    return {
        "status": "ok",
        "app_version": settings.app_version,
        "spider_xhs_available": os.path.exists(settings.spider_xhs_dir),
        "limits": {
            "max_notes_per_task": settings.max_notes_per_task,
            "max_active_tasks_per_user": settings.max_active_tasks_per_user,
            "max_competitor_count": settings.max_competitor_count,
        },
    }


# Serve built frontend static files (SPA) — must come AFTER API routes
frontend_dist = find_resource("frontend", "dist")
if frontend_dist.exists():
    frontend_assets = frontend_dist / "assets"
    if frontend_assets.exists():
        app.mount(
            "/assets",
            StaticFiles(directory=str(frontend_assets)),
            name="frontend-assets",
        )

    @app.get("/", include_in_schema=False)
    @app.get("/{full_path:path}", include_in_schema=False)
    def serve_frontend(full_path: str = ""):
        if full_path.startswith("api/"):
            raise HTTPException(status_code=404, detail="Not found")

        index_file = frontend_dist / "index.html"
        if not index_file.exists():
            raise HTTPException(status_code=404, detail="Frontend build not found")
        return FileResponse(index_file)
