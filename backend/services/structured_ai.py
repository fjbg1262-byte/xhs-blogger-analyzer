"""Bounded, text-only structured generation. Never return provider error bodies."""
import json
from urllib.parse import urlsplit

import httpx


class AIRequestError(RuntimeError):
    def __init__(self, message: str, code: str = "request"):
        super().__init__(message)
        self.code = code


def validate_api_url(value: str) -> str:
    """Accept HTTPS APIs and local HTTP model servers; reject credential-bearing URLs."""
    url = str(value or "").strip()
    if not url:
        raise AIRequestError("请填写模型 API 地址。")
    try:
        parsed = urlsplit(url)
        _ = parsed.port
    except ValueError:
        raise AIRequestError("模型 API 地址格式无效。") from None
    if parsed.scheme != "https" and not (
        parsed.scheme == "http" and parsed.hostname in ("127.0.0.1", "localhost", "::1")
    ):
        raise AIRequestError("模型地址必须使用 HTTPS；本机模型可以使用 HTTP。")
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise AIRequestError("模型地址不能包含账号、查询参数或片段。")
    return url.rstrip("/")


def generate_json(config: dict, system: str, prompt: str, schema: dict) -> tuple[dict, dict]:
    url = validate_api_url(config["api_url"])
    provider = config["provider"]
    headers = {"Content-Type": "application/json"}
    if provider == "claude":
        headers.update({"x-api-key": config["api_key"], "anthropic-version": "2023-06-01"})
        endpoint = "/messages"
        body = {"model": config["model"], "max_tokens": 14000, "system": system,
                "messages": [{"role": "user", "content": prompt + "\nJSON Schema:\n" + json.dumps(schema, ensure_ascii=False)}]}
    elif provider == "openai":
        headers["Authorization"] = "Bearer " + config["api_key"]
        endpoint = "/responses"
        body = {"model": config["model"], "instructions": system, "input": prompt,
                "max_output_tokens": 16000, "store": False,
                "text": {"format": {"type": "json_schema", "name": "content_delivery", "strict": True, "schema": schema}}}
    else:
        headers["Authorization"] = "Bearer " + config["api_key"]
        endpoint = "/chat/completions"
        body = {"model": config["model"], "max_tokens": 16000,
                "response_format": {"type": "json_object"},
                "messages": [{"role": "system", "content": system},
                             {"role": "user", "content": prompt + "\nJSON Schema:\n" + json.dumps(schema, ensure_ascii=False)}]}
    try:
        response = httpx.post(url + endpoint, headers=headers, json=body, timeout=httpx.Timeout(180, connect=20))
        response.raise_for_status()
        data = response.json()
        if provider == "openai":
            if data.get("status") != "completed":
                raise AIRequestError("模型未完成输出，请检查模型输出额度后重试。")
            text = "".join(part.get("text", "") for item in data.get("output", [])
                           for part in item.get("content", []) if part.get("type") == "output_text")
        elif provider == "claude":
            if data.get("stop_reason") != "end_turn":
                raise AIRequestError("模型输出被截断或未正常结束。")
            text = "".join(item.get("text", "") for item in data.get("content", []) if item.get("type") == "text")
        else:
            choice = data["choices"][0]
            if choice.get("finish_reason") != "stop":
                if choice.get("finish_reason") == "length":
                    raise AIRequestError("模型输出达到 token 上限。", "length")
                raise AIRequestError("模型输出被拒绝或未正常结束，请检查设置。")
            text = choice["message"]["content"]
        text = text.strip()
        if text.startswith("```json") and text.endswith("```"):
            text = text[7:-3].strip()
        value = json.loads(text)
        if not isinstance(value, dict):
            raise ValueError("not an object")
        usage = data.get("usage") or {}
        # Keep numeric billing metadata only, never provider response/request blobs.
        return value, {k: v for k, v in usage.items() if isinstance(v, int) and not isinstance(v, bool)}
    except httpx.HTTPStatusError as exc:
        code = exc.response.status_code
        labels = {401: "API Key 无效", 403: "模型或账号无访问权限", 429: "额度不足或请求过于频繁",
                  400: "模型名称、结构化输出或参数不兼容", 404: "模型或 API 地址不存在"}
        raise AIRequestError(f"AI 请求失败（{code}）：{labels.get(code, '模型服务暂不可用')}。") from None
    except httpx.TimeoutException:
        raise AIRequestError("AI 请求超时，未自动重试以避免重复扣费。稍后可重新生成。") from None
    except httpx.RequestError:
        raise AIRequestError("无法连接模型服务，请检查模型地址和网络。") from None
    except (ValueError, KeyError, IndexError, TypeError, AttributeError):
        raise AIRequestError("模型未返回完整 JSON，未生成可交付报告。") from None
