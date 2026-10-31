"""Settings endpoints for per-user runtime LLM configuration."""

import json
import os
import uuid
from pathlib import Path
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, constr

from backend.config import PROVIDER_PRESETS, settings
from backend.routers.auth import get_current_user
from backend.services.ai_agent import config_path, ai_config_status
from backend.services.structured_ai import AIRequestError, validate_api_url

router = APIRouter(prefix="/api/settings", tags=["settings"])


class LLMConfigRequest(BaseModel):
    llm_provider: Optional[Literal["openai", "deepseek", "kimi", "qwen", "glm", "claude", "custom"]] = None
    llm_api_key: Optional[constr(strip_whitespace=True, max_length=8192)] = None
    llm_api_url: Optional[constr(strip_whitespace=True, max_length=2048)] = None
    llm_model: Optional[constr(strip_whitespace=True, max_length=200)] = None


def _load_all_config() -> dict:
    if config_path().exists():
        try:
            data = json.loads(config_path().read_text(encoding="utf-8"))
            if isinstance(data, dict):
                return data
        except Exception:
            pass
    return {}


def _save_all_config(cfg: dict):
    config_path().parent.mkdir(parents=True, exist_ok=True)
    temporary = config_path().with_name(config_path().name + "." + uuid.uuid4().hex + ".tmp")
    temporary.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")
    try:
        os.chmod(temporary, 0o600)
    except OSError:
        pass
    temporary.replace(config_path())


def _user_config(all_cfg: dict, user_id: int) -> dict:
    if "users" in all_cfg:
        return all_cfg.get("users", {}).get(str(user_id), {})
    # Backward compatibility for the old single-user format.
    return {k: v for k, v in all_cfg.items() if k.startswith("llm_")}


def _set_user_config(all_cfg: dict, user_id: int, user_cfg: dict) -> dict:
    users = all_cfg.setdefault("users", {})
    users[str(user_id)] = user_cfg
    for key in ("llm_provider", "llm_api_key", "llm_api_url", "llm_model"):
        all_cfg.pop(key, None)
    return all_cfg


@router.get("/llm")
def get_llm_config(current_user: dict = Depends(get_current_user)):
    """Get current user's LLM configuration with the API key masked."""
    cfg = ai_config_status(current_user["id"])
    provider, api_url, model = (cfg[k] for k in ("provider", "api_url", "model"))

    return {
        "provider": provider,
        "api_url": api_url,
        "model": model,
        "api_key_masked": "已配置" if cfg["api_key"] else "",
        "has_key": bool(cfg["api_key"]),
        "presets": {k: v[0] for k, v in PROVIDER_PRESETS.items()},
        "default_models": {k: v[1] for k, v in PROVIDER_PRESETS.items()},
    }


@router.post("/llm")
def set_llm_config(body: LLMConfigRequest, current_user: dict = Depends(get_current_user)):
    """Update current user's LLM configuration at runtime."""
    if isinstance(body, dict):
        body = LLMConfigRequest.parse_obj(body)
    all_cfg = _load_all_config()
    runtime = dict(_user_config(all_cfg, current_user["id"]))
    payload = body.dict(exclude_unset=True)

    provider_changed = "llm_provider" in payload and payload["llm_provider"] != runtime.get("llm_provider")
    if provider_changed:
        runtime.pop("llm_api_key", None)
        if "llm_model" not in payload:
            runtime.pop("llm_model", None)
        if "llm_api_url" not in payload:
            runtime.pop("llm_api_url", None)

    for key in ("llm_provider", "llm_api_key", "llm_api_url", "llm_model"):
        if key in payload:
            val = payload[key]
            if val:
                runtime[key] = val
            elif key != "llm_api_key":
                runtime.pop(key, None)

    provider = runtime.get("llm_provider") or settings.llm_provider
    preset = PROVIDER_PRESETS.get(provider)
    if preset:
        default_url, default_model = preset
        if not runtime.get("llm_api_url"):
            runtime["llm_api_url"] = default_url
        if not runtime.get("llm_model"):
            runtime["llm_model"] = default_model

    if provider == "custom" and (not runtime.get("llm_api_url") or not runtime.get("llm_model")):
        raise HTTPException(400, "自定义模型必须填写 API 地址和模型名称。")
    try:
        runtime["llm_api_url"] = validate_api_url(runtime.get("llm_api_url", ""))
    except AIRequestError as exc:
        raise HTTPException(400, str(exc)) from None

    _save_all_config(_set_user_config(all_cfg, current_user["id"], runtime))
    return {"ok": True, "message": "LLM configuration updated"}
