"""AI Agent module — multi-provider LLM powered analysis features."""

import json
import os
import re
import base64
import hashlib
from pathlib import Path
from typing import Optional, Tuple

import httpx
from backend.config import settings, PROVIDER_PRESETS


def config_path() -> Path:
    return Path(settings.data_dir) / "llm_config.json"


def _runtime_config(user_id=None) -> dict:
    """Load runtime LLM config (written by user via Settings page), merged with env defaults."""
    runtime = {}
    if config_path().exists():
        try:
            runtime = json.loads(config_path().read_text(encoding="utf-8"))
        except Exception:
            pass
    if user_id is not None and isinstance(runtime, dict) and "users" in runtime:
        return runtime.get("users", {}).get(str(user_id), {})
    if isinstance(runtime, dict):
        return {k: v for k, v in runtime.items() if k.startswith("llm_")}
    return {}


def ai_config_status(user_id=None) -> dict:
    rc = _runtime_config(user_id)
    provider = rc.get("llm_provider") or settings.llm_provider
    preset_url, preset_model = PROVIDER_PRESETS.get(provider, ("", ""))
    same_provider = provider == settings.llm_provider
    api_key = rc.get("llm_api_key") or (settings.llm_api_key if same_provider else "")
    api_url = rc.get("llm_api_url") or (settings.llm_api_url if same_provider else preset_url)
    model = rc.get("llm_model") or (settings.llm_model if same_provider else preset_model)
    return {
        "configured": bool(api_key and api_url and model),
        "provider": provider,
        "api_key": api_key,
        "api_url": api_url,
        "model": model,
    }


def _call_llm(system: str, user_msg: str, max_tokens: int = 1024, user_id=None) -> str:
    """Call the configured LLM and return response text.

    Supports:
      - OpenAI-compatible APIs (OpenAI, DeepSeek, Kimi, Qwen, GLM, etc.)
      - Anthropic Claude API

    Reads config from runtime file first, then falls back to env vars.
    """
    cfg = ai_config_status(user_id)
    provider, api_key, api_url, model = (cfg[k] for k in ("provider", "api_key", "api_url", "model"))

    if not api_key:
        return f"AI 功能需要配置 API Key（Settings 页面 → LLM 设置）。当前 provider: {provider}"

    headers = {"Content-Type": "application/json"}

    # --- Claude format ---
    if provider == "claude":
        headers["x-api-key"] = api_key
        headers["anthropic-version"] = "2023-06-01"
        url = api_url.rstrip("/") + "/messages"
        body = {
            "model": model,
            "max_tokens": max_tokens,
            "system": system,
            "messages": [{"role": "user", "content": user_msg}],
        }
        try:
            resp = httpx.post(url, headers=headers, json=body, timeout=120)
            resp.raise_for_status()
            data = resp.json()
            return data["content"][0]["text"]
        except Exception as e:
            return f"AI 调用失败 ({provider}): {str(e)}"

    # --- OpenAI-compatible format (OpenAI, DeepSeek, Kimi, Qwen, GLM, custom) ---
    headers["Authorization"] = f"Bearer {api_key}"
    url = api_url.rstrip("/") + "/chat/completions"
    body = {
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user_msg},
        ],
        "max_completion_tokens" if provider == "openai" else "max_tokens": max_tokens,
    }
    try:
        resp = httpx.post(url, headers=headers, json=body, timeout=120)
        resp.raise_for_status()
        data = resp.json()
        return data["choices"][0]["message"]["content"]
    except Exception as e:
        return f"AI 调用失败 ({provider}): {str(e)}"


def _supports_vision(provider: str, model: str) -> bool:
    value = f"{provider} {model}".lower()
    return any(token in value for token in ("gpt-4o", "vision", "vl", "claude", "gemini"))


def _fetch_image_source(url: str) -> Optional[Tuple[str, str]]:
    try:
        response = httpx.get(url, timeout=20, follow_redirects=True)
        response.raise_for_status()
        if len(response.content) > 4 * 1024 * 1024:
            return None
        media_type = response.headers.get("content-type", "image/jpeg").split(";")[0]
        if not media_type.startswith("image/"):
            media_type = "image/jpeg"
        return media_type, base64.b64encode(response.content).decode("ascii")
    except Exception:
        return None


def _call_multimodal_json(system: str, prompt: str, image_urls: list[str], user_id=None) -> str:
    cfg = ai_config_status(user_id)
    if not cfg["configured"]:
        return ""
    provider = cfg["provider"]
    api_url = cfg["api_url"]
    model = cfg["model"]
    headers = {"Content-Type": "application/json"}
    use_images = image_urls[:8] if _supports_vision(provider, model) else []

    if provider == "claude":
        headers["x-api-key"] = cfg["api_key"]
        headers["anthropic-version"] = "2023-06-01"
        content = [{"type": "text", "text": prompt}]
        for url in use_images:
            fetched = _fetch_image_source(url)
            if fetched:
                media_type, data = fetched
                content.append({
                    "type": "image",
                    "source": {"type": "base64", "media_type": media_type, "data": data},
                })
        body = {
            "model": model,
            "max_tokens": 3000,
            "system": system,
            "messages": [{"role": "user", "content": content}],
        }
        try:
            response = httpx.post(api_url.rstrip("/") + "/messages", headers=headers, json=body, timeout=180)
            response.raise_for_status()
            return response.json()["content"][0]["text"]
        except Exception:
            return ""

    headers["Authorization"] = f"Bearer {cfg['api_key']}"
    content = [{"type": "text", "text": prompt}]
    content.extend(
        {"type": "image_url", "image_url": {"url": url, "detail": "low"}}
        for url in use_images
    )
    body = {
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": content if use_images else prompt},
        ],
        "max_completion_tokens" if provider == "openai" else "max_tokens": 6000,
        "response_format": {"type": "json_object"},
    }
    try:
        response = httpx.post(api_url.rstrip("/") + "/chat/completions", headers=headers, json=body, timeout=180)
        response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"]
    except Exception:
        # Some OpenAI-compatible providers reject response_format or image blocks.
        body.pop("response_format", None)
        body["messages"][1]["content"] = prompt
        try:
            response = httpx.post(api_url.rstrip("/") + "/chat/completions", headers=headers, json=body, timeout=180)
            response.raise_for_status()
            return response.json()["choices"][0]["message"]["content"]
        except Exception:
            return ""


AI_DIMENSION_KEYS = (
    "positioning_audience",
    "content_structure",
    "title_hook",
    "engagement_drivers",
    "growth_trajectory",
    "tag_search",
    "commercial_signals",
    "action_plan",
)


def _number(value) -> int:
    if isinstance(value, (int, float)):
        return int(value)
    text = str(value or "").strip()
    try:
        if "万" in text:
            return int(float(text.replace("万", "")) * 10000)
        return int(float(text))
    except (TypeError, ValueError):
        return 0


def _parse_json_response(text: str) -> dict:
    if not text:
        return {}
    cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", text.strip(), flags=re.I | re.S)
    try:
        value = json.loads(cleaned)
        return value if isinstance(value, dict) else {}
    except (ValueError, TypeError):
        start, end = cleaned.find("{"), cleaned.rfind("}")
        if start >= 0 and end > start:
            try:
                value = json.loads(cleaned[start:end + 1])
                return value if isinstance(value, dict) else {}
            except (ValueError, TypeError):
                pass
    return {}


def build_grounded_ai_enhancement(
    results: dict,
    all_notes: list[dict],
    contents: list[dict],
    comments: list[dict],
    user_id=None,
    context=None,
) -> dict:
    """Generate evidence-bound AI interpretation for the eight delivery dimensions."""
    cfg = ai_config_status(user_id)
    if not cfg["configured"]:
        return {
            "enabled": False,
            "status": "not_configured",
            "message": "未配置 AI API，报告使用结构化规则分析。",
            "dimensions": {},
        }

    note_by_id = {str(note.get("note_id")): note for note in all_notes if note.get("note_id")}
    content_by_id = {str(item.get("note_id")): item for item in contents if item.get("note_id")}
    evidence_ids = []
    for dimension in (results.get("eight_dimensions") or {}).values():
        for note_id in dimension.get("evidence_note_ids", []):
            if note_id in note_by_id and note_id not in evidence_ids:
                evidence_ids.append(note_id)
    for note in sorted(all_notes, key=lambda item: _number(item.get("liked_count", 0)), reverse=True):
        note_id = str(note.get("note_id") or "")
        if note_id and note_id not in evidence_ids:
            evidence_ids.append(note_id)
        if len(evidence_ids) >= 24:
            break

    evidence = []
    image_urls = []
    for note_id in evidence_ids[:24]:
        note = note_by_id[note_id]
        content = content_by_id.get(note_id, {})
        images = content.get("image_urls") or []
        cover = content.get("cover_url") or (images[0] if images else "") or note.get("cover_url", "")
        image_index = None
        if cover and cover not in image_urls:
            image_urls.append(cover)
            image_index = len(image_urls)
        elif cover:
            image_index = image_urls.index(cover) + 1
        evidence.append({
            "note_id": note_id,
            "title": note.get("title", ""),
            "type": note.get("type", ""),
            "likes": note.get("liked_count", 0),
            "favorites": content.get("collected_count", 0),
            "comments": content.get("comment_count", 0),
            "shares": content.get("share_count", 0),
            "body_excerpt": str(content.get("content_text") or "")[:500],
            "tags": (content.get("tags") or [])[:10],
            "image_count": len(images),
            "has_video": bool(content.get("video_url")),
            "visual_input_index": image_index if image_index and image_index <= 8 else None,
        })

    comment_evidence = sorted(
        [comment for comment in comments if str(comment.get("content") or "").strip()],
        key=lambda item: _number(item.get("like_count", 0)),
        reverse=True,
    )[:50]
    bundle = {
        "customer_goal": context or {},
        "verified_summary": {
            "profile": results.get("profile", {}),
            "data_quality": results.get("data_quality", {}),
            "eight_dimensions": results.get("eight_dimensions", {}),
            "topics": results.get("topic_clusters", [])[:10],
            "hooks": results.get("hook_analysis", {}),
            "engagement": results.get("engagement_drivers", {}),
            "search": results.get("search_landscape", {}),
            "commercial": results.get("commercial", {}),
        },
        "note_evidence": evidence,
        "comment_evidence": [
            {
                "comment_id": item.get("comment_id", ""),
                "note_id": item.get("note_id", ""),
                "content": item.get("content", ""),
                "like_count": item.get("like_count", 0),
                "ip_location": item.get("ip_location", ""),
            }
            for item in comment_evidence
        ],
    }
    system = (
        "你是严谨的小红书账号研究员。只能解释输入中的事实，不得创造数字、平台机制、粉丝属性、因果关系或商业结果。"
        "每条判断必须引用输入中真实存在的 note_id；证据不足时明确写局限。"
    )
    prompt = f"""请基于下面的已核验数据，为8个维度生成AI增强解读。

只返回JSON对象，结构必须是：
{{
  "dimensions": {{
    "positioning_audience": {{"summary":"", "findings":[""], "evidence_note_ids":[""], "confidence":"medium", "limits":[""]}},
    "content_structure": {{...}},
    "title_hook": {{...}},
    "engagement_drivers": {{...}},
    "growth_trajectory": {{...}},
    "tag_search": {{...}},
    "commercial_signals": {{...}},
    "action_plan": {{...}}
  }}
}}

要求：
1. 每维 summary 不超过120字，findings最多4条。
2. evidence_note_ids只能从输入出现的note_id中选择，最多6条。
3. 不把相关性写成因果；不推断年龄、性别、收入、曝光、搜索量、涨粉或成交。
4. 图片仅按输入顺序对应 note_evidence 中具有封面的样本，只描述清楚可见的构图、首屏文字与信息密度。
5. action_plan必须是可执行测试，不承诺结果。

已核验数据：
{json.dumps(bundle, ensure_ascii=False, separators=(',', ':'))}
"""
    raw = _call_multimodal_json(system, prompt, image_urls, user_id=user_id)
    parsed = _parse_json_response(raw)
    dimensions = {}
    allowed_ids = {item["note_id"] for item in evidence}
    for key in AI_DIMENSION_KEYS:
        item = (parsed.get("dimensions") or {}).get(key)
        if not isinstance(item, dict):
            continue
        ids = [note_id for note_id in item.get("evidence_note_ids", []) if note_id in allowed_ids][:6]
        findings = [str(value).strip()[:220] for value in item.get("findings", []) if str(value).strip()][:4]
        summary = str(item.get("summary") or "").strip()[:260]
        if not summary or (key != "action_plan" and not ids):
            continue
        dimensions[key] = {
            "summary": summary,
            "findings": findings,
            "evidence_note_ids": ids,
            "confidence": item.get("confidence") if item.get("confidence") in ("high", "medium", "low") else "medium",
            "limits": [str(value).strip()[:180] for value in item.get("limits", []) if str(value).strip()][:3],
        }
    if not dimensions:
        return {
            "enabled": False,
            "status": "failed",
            "message": "AI 调用未返回可校验的结构化结果，已保留规则分析。",
            "dimensions": {},
        }
    return {
        "enabled": True,
        "status": "ready" if len(dimensions) == len(AI_DIMENSION_KEYS) else "partial",
        "provider": cfg["provider"],
        "model": cfg["model"],
        "multimodal": bool(image_urls and _supports_vision(cfg["provider"], cfg["model"])),
        "image_sample_count": min(len(image_urls), 8),
        "dimensions": dimensions,
        "dimension_count": len(dimensions),
        "scope": "AI只解释已核验的公开数据和代表媒体，不覆盖原始数字，不替代证据边界。",
    }


def enhancement_fingerprint(results, notes, contents, comments, context):
    clean = {key: value for key, value in results.items() if key != "ai_enhancement"}
    payload = ["legacy-ai-input-v2", clean, notes, contents, comments, context]
    return hashlib.sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True).encode()).hexdigest()


def deconstruct_notes(all_notes: list[dict], top_n: int = 10, user_id=None) -> str:
    """Analyze top-performing notes to identify viral patterns."""
    top = sorted(all_notes, key=lambda n: int(n.get("liked_count", 0)), reverse=True)[:top_n]
    notes_text = "\n\n".join(
        f"标题: {n.get('title', '')}\n正文: {n.get('content_text', '')[:200]}"
        for n in top
    )

    system = "你是一个专业的小红书爆款拆解专家。分析笔记的钩子类型、结构模式、情绪触发点。"
    prompt = f"""分析以下 {top_n} 篇高赞小红书笔记，输出结构化分析：

1. **钩子类型**：每篇笔记用了哪种开头（反常识/故事/数据/提问/共情）
2. **结构模式**：正文结构（清单体/故事体/观点论证/教程步骤）
3. **情绪触发点**：引发互动的主要情绪
4. **共性规律**：这些爆款的共同特征

笔记数据：
{notes_text}
"""
    return _call_llm(system, prompt, max_tokens=1500, user_id=user_id)


def diagnose_account(results_json: dict, niche=None, user_id=None) -> str:
    """Diagnose account performance from analysis results."""
    p = results_json.get("profile", {})
    t = results_json.get("topic_distribution", [])
    ta = results_json.get("title_analysis", {})
    e = results_json.get("engagement", {})
    g = results_json.get("growth", {})

    topics_summary = "\n".join(
        f"  - {cat['category']}: {cat['count']}篇, 均赞{cat['avg_likes']:.0f}, 爆款率{cat['burst_rate']:.1f}%"
        for cat in t[:5]
    )

    features = ta.get("features", [])
    title_summary = "\n".join(
        f"  - {f['name']}: 使用率{f['pct']:.0f}%, 均赞{f['avg_likes']:.0f} (vs基准{f.get('vs_baseline_pct', 0):+.0f}%)"
        for f in features[:5]
    )

    burst_notes = g.get("burst_notes", [])

    system = "你是一个专业的小红书账号诊断专家。分析账号的优劣势并给出改进建议。"
    prompt = f"""分析以下小红书账号数据，输出诊断报告：

**账号概览**
- 昵称: {p.get('nickname', '未知')}
- 总笔记: {p.get('total_notes', 0)}篇
- 均赞: {p.get('avg_likes', 0):.0f}
- 中位数点赞: {p.get('median_likes', 0):.0f}
- 最高赞: {p.get('max_likes', 0):.0f}
{'  - 领域: ' + niche if niche else ''}

**内容结构**
{topics_summary}

**标题表现**
{title_summary}

**互动分布**
- Top10%贡献: {e.get('top10pct_share', 0):.1f}%
- Top5贡献: {e.get('top5_share', 0):.1f}%
- 爆款数: {g.get('burst_count', 0)}
{'  - 最近爆款: ' + burst_notes[0]['title'] if burst_notes else ''}

请给出：
1. 账号综合健康度评分 (百分制)
2. Top 3 优势
3. Top 3 待改进项
4. 具体改进建议（内容方向、标题策略、发布节奏）
"""
    return _call_llm(system, prompt, max_tokens=1200, user_id=user_id)


def rewrite_content(original_title: str, style: str, top_titles=None, user_id=None) -> str:
    """Rewrite a title in a target style."""
    style_map = {
        "high-engagement": "高互动：使用感叹句/疑问句/情绪词，引发评论",
        "authoritative": "专业权威：数据支撑/结论先行/行业视角",
        "curiosity-gap": "好奇心缺口：制造悬念/反常识/信息差",
        "storytelling": "故事叙述：时间锚+情节+情感共鸣",
        "listicle": "清单体：数字+价值承诺",
    }
    style_desc = style_map.get(style, style)

    system = "你是一个小红书爆款标题写作专家。擅长将普通标题改写成高互动标题。"
    prompt = f"""请将以下小红书标题改写成「{style_desc}」风格的标题。

原标题: 「{original_title}」

{'参考这些爆款标题的风格:' + chr(10) + chr(10).join(f'  - 「{t}」' for t in top_titles[:5]) if top_titles else ''}

要求：
1. 保持原意，不要偏离主题
2. 给出 3 个改写版本
3. 每个版本用一句话解释改写策略
4. 推荐最佳版本并说明原因
"""
    return _call_llm(system, prompt, max_tokens=800, user_id=user_id)


def compare_accounts(results_a: dict, results_b: dict, user_id=None) -> str:
    """Compare two accounts side-by-side across 8 dimensions."""
    def summarize(r):
        p = r.get("profile", {})
        t = r.get("topic_distribution", [])
        e = r.get("engagement", {})
        g = r.get("growth", {})
        c = r.get("commercial", {})
        return {
            "name": p.get("nickname", "未知"),
            "notes": p.get("total_notes", 0),
            "avg_likes": p.get("avg_likes", 0),
            "median_likes": p.get("median_likes", 0),
            "max_likes": p.get("max_likes", 0),
            "video_pct": next(
                (ct.get("pct", 0) for ct in r.get("content_type", []) if ct.get("type") == "video"), 0
            ),
            "top_topic": t[0]["category"] if t else "",
            "pareto": e.get("pareto_80pct_pct", 0),
            "burst_count": g.get("burst_count", 0),
            "commercial_pct": c.get("note_count", 0) / max(r.get("profile", {}).get("total_notes", 1), 1) * 100,
        }

    a = summarize(results_a)
    b = summarize(results_b)

    system = "你是一个专业的小红书竞品分析专家。"
    prompt = f"""对比分析两位小红书博主，输出对比报告：

**博主A: {a['name']}** vs **博主B: {b['name']}**

| 维度 | A | B |
|------|---|---|
| 总笔记 | {a['notes']} | {b['notes']} |
| 均赞 | {a['avg_likes']:.0f} | {b['avg_likes']:.0f} |
| 中位数点赞 | {a['median_likes']:.0f} | {b['median_likes']:.0f} |
| 最高赞 | {a['max_likes']:.0f} | {b['max_likes']:.0f} |
| 视频占比 | {a['video_pct']:.0f}% | {b['video_pct']:.0f}% |
| 核心领域 | {a['top_topic']} | {b['top_topic']} |
| 爆款数 | {a['burst_count']} | {b['burst_count']} |
| 互动集中度 | {a['pareto']:.1f}% | {b['pareto']:.1f}% |

请分析：
1. 两者的核心定位差异
2. 各自的内容策略特点
3. A可以从B学习什么
4. B可以从A学习什么
5. 差异化竞争建议
"""
    return _call_llm(system, prompt, max_tokens=1200, user_id=user_id)
