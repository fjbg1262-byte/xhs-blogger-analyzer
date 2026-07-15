"""Application configuration — pydantic V1 compatible."""

import os
from pathlib import Path
from pydantic import BaseSettings


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
    database_url: str = "sqlite:///./data/app.db"
    python_exe: str = "python"
    data_dir: str = ""
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

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        base = str(Path(__file__).parent.parent)
        if not self.data_dir:
            self.data_dir = os.path.join(base, "data")
        if not self.spider_xhs_dir:
            self.spider_xhs_dir = os.path.join(base, "spider_xhs")

        # Auto-fill LLM API URL and model from provider preset
        preset = PROVIDER_PRESETS.get(self.llm_provider)
        if preset:
            default_url, default_model = preset
            if not self.llm_api_url:
                self.llm_api_url = default_url
            if not self.llm_model:
                self.llm_model = default_model


settings = Settings()
BASE_DIR = Path(__file__).parent.parent
