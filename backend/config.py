"""Application configuration — pydantic V1 compatible."""

import json
import os
import sys
from pathlib import Path
from pydantic import BaseSettings

from backend.runtime import app_root, find_resource, writable_path


# Provider presets: (default_api_url, default_model)
PROVIDER_PRESETS = {
    "openai":     ("https://api.openai.com/v1",             "gpt-4o-mini"),
    "deepseek":   ("https://api.deepseek.com/v1",           "deepseek-chat"),
    "kimi":       ("https://api.moonshot.cn/v1",            "moonshot-v1-8k"),
    "qwen":       ("https://dashscope.aliyuncs.com/compatible-mode/v1", "qwen-plus"),
    "glm":        ("https://open.bigmodel.cn/api/paas/v4",  "glm-4-flash"),
    "claude":     ("https://api.anthropic.com/v1",          "claude-sonnet-4-20250514"),
    "custom":     ("",                                      ""),
}


class Settings(BaseSettings):
    database_url: str = ""
    python_exe: str = "python"
    data_dir: str = ""
    reports_dir: str = ""
    logs_dir: str = ""
    spider_xhs_dir: str = ""

    # LLM provider settings
    llm_provider: str = "openai"
    llm_api_key: str = ""
    llm_api_url: str = ""   # auto-filled from preset if empty
    llm_model: str = ""     # auto-filled from preset if empty

    max_task_timeout: int = 600
    max_concurrent_tasks: int = 2
    max_active_tasks_per_user: int = 1
    max_notes_per_task: int = 100
    max_competitor_count: int = 5
    secret_key: str = "change-me-in-production"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 1440

    # Optional anonymous product telemetry. Disabled until the user consents.
    app_version: str = "0.1.0-beta.3"
    telemetry_endpoint: str = ""
    telemetry_ingest_key: str = ""

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        base = str(app_root())
        if not self.data_dir:
            self.data_dir = str(writable_path("data"))
        if not self.reports_dir:
            self.reports_dir = str(writable_path("reports"))
        if not self.logs_dir:
            self.logs_dir = str(writable_path("logs"))
        if not self.database_url:
            db_path = Path(self.data_dir) / "app.db"
            self.database_url = f"sqlite:///{db_path.as_posix()}"
        if getattr(sys, "frozen", False):
            self.python_exe = sys.executable
        if not self.spider_xhs_dir:
            self.spider_xhs_dir = str(find_resource("spider_xhs"))

        telemetry_config = find_resource("telemetry_config.json")
        if telemetry_config.exists():
            try:
                payload = json.loads(telemetry_config.read_text(encoding="utf-8-sig"))
                if not self.telemetry_endpoint:
                    self.telemetry_endpoint = str(payload.get("endpoint") or "").strip()
                if not self.telemetry_ingest_key:
                    self.telemetry_ingest_key = str(payload.get("ingest_key") or "").strip()
                if payload.get("app_version"):
                    self.app_version = str(payload["app_version"]).strip()
            except (OSError, ValueError, TypeError):
                pass

        # Auto-fill LLM API URL and model from provider preset
        preset = PROVIDER_PRESETS.get(self.llm_provider)
        if preset:
            default_url, default_model = preset
            if not self.llm_api_url:
                self.llm_api_url = default_url
            if not self.llm_model:
                self.llm_model = default_model


settings = Settings()
BASE_DIR = app_root()
