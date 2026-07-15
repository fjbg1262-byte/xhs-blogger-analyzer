"""Settings endpoints for per-user runtime LLM configuration."""

import json
from pathlib import Path

from fastapi import APIRouter, Depends

from backend.config import PROVIDER_PRESETS, settings
from backend.routers.auth import get_current_user

router = APIRouter(prefix="/api/settings", tags=["settings"])

CONFIG_FILE = Path(__file__).resolve().parent.parent.parent / "data" / "llm_config.json"


def _load_all_config() -> dict:
    if CONFIG_FILE.exists():
        try:
            data = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                return data
        except Exception:
            pass
    return {}


def _save_all_config(cfg: dict):
    CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
    CONFIG_FILE.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")


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
    all_cfg = _load_all_config()
    runtime = _user_config(all_cfg, current_user["id"])

    provider = runtime.get("llm_provider") or settings.llm_provider
    preset = PROVIDER_PRESETS.get(provider)
    preset_url, preset_model = preset if preset else ("", "")
    api_url = runtime.get("llm_api_url") or preset_url or settings.llm_api_url
    model = runtime.get("llm_model") or preset_model or settings.llm_model
    api_key = runtime.get("llm_api_key") or settings.llm_api_key

    masked_key = (
        api_key[:8] + "****" + api_key[-4:]
        if len(api_key) > 12
        else (api_key[:4] + "****" if api_key else "")
    )

    return {
        "provider": provider,
        "api_url": api_url,
        "model": model,
        "api_key_masked": masked_key,
        "has_key": bool(api_key),
        "presets": {k: v[0] for k, v in PROVIDER_PRESETS.items()},
    }


@router.post("/llm")
def set_llm_config(body: dict, current_user: dict = Depends(get_current_user)):
    """Update current user's LLM configuration at runtime."""
    all_cfg = _load_all_config()
    runtime = dict(_user_config(all_cfg, current_user["id"]))

    provider_changed = "llm_provider" in body and body["llm_provider"] != runtime.get("llm_provider")
    if provider_changed:
        if "llm_model" not in body:
            runtime.pop("llm_model", None)
        if "llm_api_url" not in body:
            runtime.pop("llm_api_url", None)

    for key in ("llm_provider", "llm_api_key", "llm_api_url", "llm_model"):
        if key in body:
            val = body[key]
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

    _save_all_config(_set_user_config(all_cfg, current_user["id"], runtime))
    return {"ok": True, "message": "LLM configuration updated"}
