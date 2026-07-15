"""AI Agent module — multi-provider LLM powered analysis features."""

import json
import os
from pathlib import Path

import httpx
from backend.config import settings


_CONFIG_FILE = Path(__file__).resolve().parent.parent.parent / "data" / "llm_config.json"


def _runtime_config(user_id=None) -> dict:
    """Load runtime LLM config (written by user via Settings page), merged with env defaults."""
    runtime = {}
    if _CONFIG_FILE.exists():
        try:
            runtime = json.loads(_CONFIG_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    if user_id is not None and isinstance(runtime, dict) and "users" in runtime:
        return runtime.get("users", {}).get(str(user_id), {})
    if isinstance(runtime, dict):
        return {k: v for k, v in runtime.items() if k.startswith("llm_")}
    return {}


def _call_llm(system: str, user_msg: str, max_tokens: int = 1024, user_id=None) -> str:
    """Call the configured LLM and return response text.

    Supports:
      - OpenAI-compatible APIs (OpenAI, DeepSeek, Kimi, Qwen, GLM, etc.)
      - Anthropic Claude API

    Reads config from runtime file first, then falls back to env vars.
    """
    rc = _runtime_config(user_id)

    provider = rc.get("llm_provider") or settings.llm_provider
    api_key = rc.get("llm_api_key") or settings.llm_api_key
    api_url = rc.get("llm_api_url") or settings.llm_api_url
    model = rc.get("llm_model") or settings.llm_model

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
        "max_tokens": max_tokens,
    }
    try:
        resp = httpx.post(url, headers=headers, json=body, timeout=120)
        resp.raise_for_status()
        data = resp.json()
        return data["choices"][0]["message"]["content"]
    except Exception as e:
        return f"AI 调用失败 ({provider}): {str(e)}"


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
