"""Render the customer-facing eight-dimension account diagnosis report."""

import html
from typing import Any


REPORT_RENDERER_VERSION = "customer-eight-dimension-v2"


DIMENSION_META = (
    ("positioning_audience", "01", "定位受众", "账号在讲什么，谁更可能持续关注？"),
    ("content_structure", "02", "内容结构", "长期在发什么，哪些方向更值得继续？"),
    ("title_hook", "03", "标题 Hook", "哪些标题和开头更值得复用测试？"),
    ("engagement_drivers", "04", "互动归因", "高表现内容赢在哪里？"),
    ("growth_trajectory", "05", "成长轨迹", "账号经历了哪些表现阶段与转折？"),
    ("tag_search", "06", "标签搜索", "哪些词更能承接账号的内容表达？"),
    ("commercial_signals", "07", "商业信号", "自然内容与商业表达有什么差异？"),
    ("action_plan", "08", "行动建议", "下一步最优先测试什么？"),
)

STATUS_LABELS = {"ready": "可参考", "limited": "谨慎参考", "blocked": "数据不足"}
CONFIDENCE_LABELS = {"high": "较高", "medium": "中等", "low": "较低"}
FOCUS_DIMENSIONS = {
    "positioning": {"positioning_audience"},
    "growth": {"growth_trajectory", "action_plan"},
    "content": {"content_structure", "title_hook", "engagement_drivers"},
    "commercial": {"commercial_signals", "action_plan"},
    "overall": set(),
}


def _h(value: Any) -> str:
    return html.escape(str(value if value is not None else ""), quote=True)


def _number(value: Any, digits: int = 1) -> str:
    try:
        number = float(value or 0)
    except (TypeError, ValueError):
        return "0"
    if number >= 10000:
        return f"{number / 10000:.1f}万"
    if number.is_integer():
        return f"{int(number):,}"
    return f"{number:,.{digits}f}"


def _safe_pct(value: Any) -> float:
    try:
        return max(0.0, min(100.0, float(value or 0)))
    except (TypeError, ValueError):
        return 0.0


def _list(items: list[Any], css_class: str = "plain-list") -> str:
    clean = [str(item).strip() for item in items if str(item).strip()]
    return f'<ul class="{css_class}">' + "".join(f"<li>{_h(item)}</li>" for item in clean) + "</ul>"


def _bar_rows(rows: list[dict], value_key: str, suffix: str = "", max_rows: int = 6) -> str:
    rows = [row for row in rows[:max_rows] if row.get("label")]
    maximum = max([float(row.get(value_key) or 0) for row in rows] + [1])
    output = []
    for row in rows:
        value = float(row.get(value_key) or 0)
        width = max(3, value / maximum * 100) if value else 0
        output.append(
            '<div class="bar-row"><div class="bar-label"><strong>%s</strong><span>%s%s</span></div>'
            '<div class="bar-track"><i style="width:%.1f%%"></i></div></div>'
            % (_h(row["label"]), _number(value), _h(suffix), width)
        )
    return "".join(output) or '<p class="empty">本次没有取得足够数据，暂不绘制对比。</p>'


def _topic_rows(results: dict) -> list[dict]:
    topics = results.get("topic_clusters") or []
    if not topics:
        topics = [{"name": name, **payload} for name, payload in (results.get("topic_distribution") or {}).items()]
    topics = [
        item for item in topics
        if item.get("name") and not any(token in str(item.get("name")) for token in ("未归类", "日常随手", "其他"))
    ]
    topics.sort(key=lambda item: (float(item.get("pct") or 0), float(item.get("median_likes") or 0)), reverse=True)
    return topics[:6]


def _evidence_cards(dimension_key: str, dimension: dict, brief: dict) -> str:
    index = {str(item.get("note_id") or item.get("id")): item for item in brief.get("evidence_notes", [])}
    note_ids = list(dict.fromkeys(str(note_id) for note_id in dimension.get("evidence_note_ids", []) if note_id))
    notes = [index[note_id] for note_id in note_ids if note_id in index]
    notes.sort(key=lambda item: float(item.get("likes") or 0), reverse=True)
    if not notes:
        return '<div class="evidence-empty">这一维主要依据汇总统计，没有把单篇内容当作决定性证据。</div>'
    cards = []
    for item in notes[:3]:
        cards.append(
            '<article class="evidence-card"><div class="evidence-meta">%s · %s赞</div>'
            '<strong>%s</strong><p>%s</p></article>'
            % (
                _h(item.get("date") or "日期未知"),
                _number(item.get("likes")),
                _h(item.get("title") or "未命名笔记"),
                _h(item.get("evidence_reason") or "该样本用于复核本维度的判断。"),
            )
        )
    return '<div class="evidence-grid">' + "".join(cards) + "</div>"


def _positioning_visual(results: dict) -> str:
    topics = _topic_rows(results)
    rows = [{"label": item.get("name"), "pct": item.get("pct", 0)} for item in topics]
    audience = results.get("audience_signals") or {}
    question_rate = _number(audience.get("question_rate"), 1)
    comment_count = _number(audience.get("comment_count"))
    note_count = _number(audience.get("note_count"))
    return f"""
    <div class="visual-split">
      <div><div class="mini-title">内容心智分布</div>{_bar_rows(rows, 'pct', '%', 5)}</div>
      <div class="signal-panel"><div class="mini-title">受众需求线索</div>
        <div class="signal-number">{question_rate}%</div><p>代表评论中的主动提问占比</p>
        <div class="signal-foot">来自 {comment_count} 条评论 / {note_count} 篇代表笔记</div>
      </div>
    </div>"""


def _content_visual(results: dict) -> str:
    topics = _topic_rows(results)
    rows = [{"label": item.get("name"), "pct": item.get("pct", 0)} for item in topics]
    media = results.get("media_analysis") or {}
    content_types = results.get("content_type") or {}
    image_pct = content_types.get("normal", {}).get("pct", 0)
    video_pct = content_types.get("video", {}).get("pct", 0)
    return f"""
    <div class="visual-split">
      <div><div class="mini-title">主题占比</div>{_bar_rows(rows, 'pct', '%', 5)}</div>
      <div><div class="mini-title">内容形态</div>
        <div class="metric-pair"><div><strong>{_number(image_pct)}%</strong><span>图文</span></div><div><strong>{_number(video_pct)}%</strong><span>视频</span></div></div>
        <div class="metric-pair compact"><div><strong>{_number(media.get('avg_image_count'))}</strong><span>详情样本平均图片数</span></div><div><strong>{_number(media.get('sample_count'))}</strong><span>媒体详情样本</span></div></div>
      </div>
    </div>"""


def _title_visual(results: dict) -> str:
    formulas = []
    for name, item in (results.get("title_formulas") or {}).items():
        if int(item.get("count") or 0) >= 3:
            formulas.append({"label": name, "median": item.get("median_likes", 0), "count": item.get("count", 0)})
    formulas.sort(key=lambda item: float(item.get("median") or 0), reverse=True)
    hooks = []
    for name, item in (results.get("hook_analysis") or {}).get("patterns", {}).items():
        if int(item.get("count") or 0) >= 3:
            hooks.append({"label": name, "median": item.get("median_likes", 0), "count": item.get("count", 0)})
    hooks.sort(key=lambda item: float(item.get("median") or 0), reverse=True)
    return f"""
    <div class="visual-split">
      <div><div class="mini-title">标题模式 · 点赞中位数</div>{_bar_rows(formulas, 'median', '', 5)}</div>
      <div><div class="mini-title">正文开头 · 点赞中位数</div>{_bar_rows(hooks, 'median', '', 5)}</div>
    </div>"""


def _engagement_visual(results: dict) -> str:
    data = results.get("engagement_drivers") or {}
    top = data.get("top_group") or {}
    bottom = data.get("bottom_group") or {}
    metrics = (("收藏", "favorites"), ("评论", "comments"), ("分享", "shares"), ("正文长度", "text_length"), ("图片数", "image_count"))
    rows = []
    for label, key in metrics:
        maximum = max(float(top.get(key) or 0), float(bottom.get(key) or 0), 1)
        rows.append(
            '<div class="compare-row"><strong>%s</strong><div><i class="top" style="width:%.1f%%"></i><span>高表现组 %s</span></div>'
            '<div><i class="bottom" style="width:%.1f%%"></i><span>低表现组 %s</span></div></div>'
            % (label, float(top.get(key) or 0) / maximum * 100, _number(top.get(key)), float(bottom.get(key) or 0) / maximum * 100, _number(bottom.get(key)))
        )
    concentration = (results.get("engagement") or {}).get("pareto_80pct_pct", 0)
    return f"""
    <div class="visual-split engagement-visual"><div><div class="mini-title">高低表现组差异</div>{''.join(rows) if rows else '<p class="empty">暂无详情对比</p>'}</div>
      <div class="signal-panel"><div class="mini-title">互动集中度</div><div class="signal-number">Top {_number(concentration)}%</div><p>笔记贡献了 80% 公开点赞</p><div class="signal-foot">对比组各 {int(data.get('group_size') or 0)} 篇详情样本</div></div>
    </div>"""


def _growth_visual(results: dict) -> str:
    stats = (results.get("growth") or {}).get("monthly_stats") or []
    stats = stats[-12:]
    maximum = max([float(item.get("median_likes") or 0) for item in stats] + [1])
    columns = []
    for item in stats:
        height = max(4, float(item.get("median_likes") or 0) / maximum * 100)
        columns.append(
            '<div class="month-col"><span>%s</span><div><i style="height:%.1f%%"></i></div><small>%s<br>%s篇</small></div>'
            % (_number(item.get("median_likes")), height, _h(str(item.get("month", ""))[5:]), _number(item.get("count")))
        )
    return '<div class="mini-title">逐月点赞中位数（柱顶数字）与发布篇数</div><div class="timeline">' + "".join(columns) + "</div>" if columns else '<p class="empty">发布时间跨度不足，暂不判断阶段变化。</p>'


def _tag_visual(results: dict) -> str:
    tags = (results.get("tags") or {}).get("top30") or []
    chips = "".join(f'<span class="tag-chip">#{_h(item.get("tag"))}<b>{_number(item.get("count"))}</b></span>' for item in tags[:12])
    search = (results.get("search_landscape") or {}).get("keywords") or []
    search_rows = "".join(
        '<tr><td>%s</td><td>%s 条</td><td>%s</td><td>%s</td></tr>'
        % (_h(item.get("keyword")), _number(item.get("result_count")), _number(item.get("result_median_likes")), _h("、".join((item.get("suggestions") or [])[:3]) or "未取得"))
        for item in search[:5]
    )
    table = f'<div class="table-wrap"><table><thead><tr><th>研究词</th><th>公开结果样本</th><th>样本点赞中位数</th><th>联想词示例</th></tr></thead><tbody>{search_rows}</tbody></table></div>' if search_rows else '<p class="empty">本次没有取得有效搜索样本。</p>'
    return f'<div class="mini-title">账号高频标签</div><div class="tag-cloud">{chips or "暂无有效标签"}</div><div class="mini-title search-title">公开搜索表达样本</div>{table}'


def _commercial_visual(results: dict) -> str:
    data = results.get("commercial") or {}
    count = int(data.get("detected_count") or 0)
    if not count:
        return '<div class="zero-state"><strong>本次未发现足够的公开商业表达</strong><p>这不等于账号没有合作或变现，只代表不能从当前公开标题和正文中确认。建议把“可合作内容形态”作为下一轮小样本测试，而不是直接下商业化结论。</p></div>'
    comparison = "样本数不足，暂不比较自然内容与商业内容" if not data.get("comparison_ready") else f"商业表达样本均赞 {_number(data.get('avg_likes_commercial'))}，自然内容均赞 {_number(data.get('avg_likes_organic'))}"
    return f'<div class="metric-pair"><div><strong>{_number(count)}</strong><span>疑似商业表达样本</span></div><div><strong>{_number(data.get("detected_pct"))}%</strong><span>占公开笔记比例</span></div></div><div class="zero-state compact-state"><p>{_h(comparison)}</p></div>'


def _action_visual(brief: dict) -> str:
    actions = brief.get("recommended_actions") or []
    plan = next((item.get("seven_day_plan") for item in actions if item.get("seven_day_plan")), []) or []
    if not plan:
        plan = [
            {"day": 1, "task": "选定一个可验证方向", "goal": "从报告证据中挑一个变量。"},
            {"day": 2, "task": "写出三个测试版本", "goal": "保持主题一致，只改一个变量。"},
            {"day": 3, "task": "发布并记录", "goal": "与账号历史中位数比较。"},
        ]
    rows = "".join(
        '<div class="plan-row"><b>D%s</b><div><strong>%s</strong><span>%s</span></div></div>'
        % (_h(item.get("day")), _h(item.get("task")), _h(item.get("goal")))
        for item in plan[:7]
    )
    return '<div class="mini-title">7 天最小行动计划</div><div class="plan-list">' + rows + "</div>"


def _dimension_visual(key: str, results: dict, brief: dict) -> str:
    builders = {
        "positioning_audience": lambda: _positioning_visual(results),
        "content_structure": lambda: _content_visual(results),
        "title_hook": lambda: _title_visual(results),
        "engagement_drivers": lambda: _engagement_visual(results),
        "growth_trajectory": lambda: _growth_visual(results),
        "tag_search": lambda: _tag_visual(results),
        "commercial_signals": lambda: _commercial_visual(results),
        "action_plan": lambda: _action_visual(brief),
    }
    return builders[key]()


def _plain_meaning(key: str, dimension: dict, results: dict, brief: dict) -> str:
    topics = _topic_rows(results)
    positioning = str((brief.get("account_summary") or {}).get("positioning") or "")
    top_topic = positioning.split("：", 1)[-1] if positioning else (topics[0].get("name") if topics else "尚未形成稳定主线")
    actions = brief.get("recommended_actions") or []
    meanings = {
        "positioning_audience": f"当前最清晰的内容心智是「{top_topic}」。受众分析应围绕他们持续关心的问题展开，而不是猜年龄、性别等平台外信息。",
        "content_structure": f"不要平均分配精力。先把「{top_topic}」做成连续内容，再用相邻主题扩展，能更清楚地验证账号主线。",
        "title_hook": "复用的是信息结构，不是照抄一句话。优先保留具体对象、时间、成本或结果反差，并让正文兑现标题。",
        "engagement_drivers": "这些差异是值得测试的线索，不是平台因果。下一轮每次只改变一个可控变量，才能判断什么真正适合这个账号。",
        "growth_trajectory": "这里看的是发布与公开互动轨迹，不是粉丝增长曲线。判断账号稳定性时应看月度中位数，避免被单篇高赞带偏。",
        "tag_search": "标签的作用是让内容表达更一致，搜索样本只用来观察用户如何表达同一问题，不能被写成搜索量或排名保证。",
        "commercial_signals": "公开商业表达只是合作可能性的线索。先验证哪种自然内容能稳定建立信任，再设计不破坏内容主线的商业样本。",
        "action_plan": (actions[0].get("title") if actions else "先选择一个有证据的方向，连续完成一轮小样本测试。"),
    }
    return meanings[key]


def _dimension_section(key: str, number: str, label: str, question: str, brief: dict, results: dict, context: dict) -> str:
    dimensions = brief.get("eight_dimensions") or results.get("eight_dimensions") or {}
    dimension = dimensions.get(key) or {}
    status = dimension.get("status", "limited")
    findings = [str(item) for item in dimension.get("findings", []) if str(item).strip()]
    ai_item = ((brief.get("ai_enhancement") or {}).get("dimensions") or {}).get(key) or {}
    summary = ai_item.get("summary") or (findings[0] if findings else "本次数据不足，暂不输出确定判断。")
    ai_findings = [str(item) for item in ai_item.get("findings", []) if str(item).strip()]
    source_items = [str(item) for item in dimension.get("sources", []) if str(item).strip()]
    limits = [str(item) for item in dimension.get("limits", []) if str(item).strip()]
    if ai_item:
        limits.extend(str(item) for item in ai_item.get("limits", []) if str(item).strip())
    focused = key in FOCUS_DIMENSIONS.get(context.get("focus", "overall"), set())
    focus_badge = '<span class="focus-badge">本次重点</span>' if focused else ""
    evidence = _evidence_cards(key, dimension, brief)
    finding_html = _list(findings[:4]) if findings else '<p class="empty">这一维目前只能保留观察，不能写成确定策略。</p>'
    ai_html = ""
    if ai_item:
        ai_html = f'<div class="ai-note"><div class="mini-title">AI 增强解读</div><p>{_h(ai_item.get("summary"))}</p>{_list(ai_findings[:3]) if ai_findings else ""}</div>'
    return f"""
    <section class="dimension-section {'focused' if focused else ''}" id="dimension-{key}">
      <div class="dimension-head"><div class="dimension-number">{number}</div><div><div class="dimension-label">{label}{focus_badge}</div><h2>{_h(question)}</h2></div>
        <div class="dimension-state {status}"><strong>{_h(STATUS_LABELS.get(status, '谨慎参考'))}</strong><span>{_number(dimension.get('sample_count'))} 个样本 · 置信度 {_h(CONFIDENCE_LABELS.get(dimension.get('confidence'), '较低'))}</span></div>
      </div>
      <div class="answer-box"><span>一句话答案</span><strong>{_h(summary)}</strong></div>
      <div class="chapter-grid"><div><h3>你现在是什么情况</h3>{finding_html}</div><div><h3>这对你意味着什么</h3><p class="meaning">{_h(_plain_meaning(key, dimension, results, brief))}</p></div></div>
      <div class="visual-block">{_dimension_visual(key, results, brief)}</div>
      {ai_html}
      <div class="evidence-block"><div class="block-title"><div><span>为什么这么判断</span><strong>代表证据</strong></div><small>{_h('；'.join(source_items) or '本次公开样本汇总')}</small></div>{evidence}</div>
      <div class="boundary"><strong>阅读边界</strong><span>{_h('；'.join(dict.fromkeys(limits)) or '结论仅适用于本次可见公开样本，需要通过后续内容测试验证。')}</span></div>
    </section>"""


def _navigation(brief: dict, results: dict, context: dict) -> str:
    dimensions = brief.get("eight_dimensions") or results.get("eight_dimensions") or {}
    cards = []
    for key, number, label, question in DIMENSION_META:
        dimension = dimensions.get(key) or {}
        finding = next((str(item) for item in dimension.get("findings", []) if str(item).strip()), "本次数据不足，查看验证建议")
        focused = key in FOCUS_DIMENSIONS.get(context.get("focus", "overall"), set())
        cards.append(
            '<a class="dimension-nav %s" href="#dimension-%s"><span>%s</span><div><strong>%s</strong><small>%s</small></div><b>%s</b></a>'
            % ("focused" if focused else "", key, number, _h(label), _h(finding[:48]), _h(STATUS_LABELS.get(dimension.get("status"), "谨慎参考")))
        )
    return '<section class="map-section"><div class="section-intro"><span>报告目录</span><h2>一份报告，看懂账号的 8 个关键问题</h2><p>先看结论，再按你最关心的维度进入；每一章都包含判断、依据、边界和下一步。</p></div><div class="dimension-nav-grid">' + "".join(cards) + "</div></section>"


def _appendix(appendix_sections: list[tuple[str, str]], status: dict) -> str:
    items = "".join(
        f'<details><summary>{index:02d} · {_h(label)}</summary><div class="appendix-body">{body}</div></details>'
        for index, (label, body) in enumerate(appendix_sections, 1)
    )
    modules = "".join(
        '<div class="source-item %s"><strong>%s</strong><span>%s</span></div>'
        % (_h(item.get("status")), _h(item.get("name")), _h(item.get("note")))
        for item in status.get("modules", [])
    )
    return f'<section class="appendix"><div class="section-intro"><span>附录</span><h2>数据说明与研究底稿</h2><p>主报告已经把结论翻译成客户语言。需要复核计算过程时，再展开下面的研究材料。</p></div><div class="source-grid">{modules}</div><div class="appendix-list">{items}</div></section>'


def build_customer_report_html(
    task_id: int,
    brief: dict,
    results: dict,
    status: dict,
    context: dict,
    appendix_sections: list[tuple[str, str]],
) -> str:
    """Return a self-contained customer report with eight decision-oriented chapters."""
    summary = brief.get("account_summary") or {}
    profile = results.get("profile") or {}
    nickname = str(summary.get("nickname") or profile.get("nickname") or "账号")
    nickname_html = _h(nickname)
    avatar_url = str(summary.get("avatar_url") or profile.get("avatar_url") or "")
    avatar_initial = _h(nickname[:1])
    avatar = (
        f'<span>{avatar_initial}</span><img src="{_h(avatar_url)}" alt="账号头像" onerror="this.remove()">'
        if avatar_url.startswith(("http://", "https://"))
        else f"<span>{avatar_initial}</span>"
    )
    positioning = summary.get("positioning") or "内容主线待验证"
    conclusion = summary.get("one_sentence") or "报告已按本次公开样本完成分析。"
    insights = brief.get("strong_insights") or []
    actions = brief.get("recommended_actions") or []
    insight_html = "".join(
        '<article><b>%02d</b><div><strong>%s</strong><p>%s</p></div></article>'
        % (index, _h(item.get("title")), _h(item.get("why_it_matters") or item.get("summary")))
        for index, item in enumerate(insights[:3], 1)
    ) or '<article><b>01</b><div><strong>当前没有通过门槛的强结论</strong><p>先按各维度的数据缺口完成补充，再做确定策略。</p></div></article>'
    action_html = "".join(
        '<li><b>%02d</b><span>%s</span></li>' % (index, _h(item.get("title")))
        for index, item in enumerate(actions[:3], 1)
    ) or '<li><b>01</b><span>选择一个有证据的方向，连续测试 3 篇内容。</span></li>'
    buyer_question = context.get("buyer_question") or "未指定，按综合诊断交付"
    seller_note = f'<div class="seller-note"><strong>交付备注</strong><span>{_h(context.get("seller_note"))}</span></div>' if context.get("seller_note") else ""
    dimensions = "".join(_dimension_section(*meta, brief, results, context) for meta in DIMENSION_META)
    ai = brief.get("ai_enhancement") or results.get("ai_enhancement") or {}
    ai_text = f"AI 增强已启用 · {_h(ai.get('model') or '已配置模型')}" if ai.get("enabled") else "结构化分析 · 未启用 AI 增强"
    return f"""<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="xhs-report-renderer" content="{REPORT_RENDERER_VERSION}">
<title>{nickname_html} · 8 维账号内容诊断报告</title>
<style>
:root{{--red:#f52143;--red-dark:#c90f2d;--ink:#121316;--muted:#666b74;--line:#e4e5e9;--paper:#fff;--soft:#fff4f6;--warm:#fff9e8;--yellow:#ffd12f;--green:#137a4f;--orange:#a45c00}}
*{{box-sizing:border-box}}html{{scroll-behavior:smooth}}body{{margin:0;background:#f3f4f6;color:var(--ink);font-family:-apple-system,BlinkMacSystemFont,"Segoe UI","Microsoft YaHei",sans-serif;letter-spacing:0}}
.toolbar{{position:sticky;top:0;z-index:5;display:flex;justify-content:center;background:rgba(255,255,255,.96);border-bottom:1px solid var(--line);padding:10px}}.toolbar-inner{{width:min(1120px,100%);display:flex;justify-content:space-between;align-items:center;gap:12px}}.toolbar span{{font-size:13px;color:var(--muted)}}button{{border:0;border-radius:6px;background:var(--ink);color:#fff;font-weight:800;padding:10px 16px;cursor:pointer}}
main{{width:min(1120px,calc(100% - 32px));margin:20px auto 64px}}section{{background:var(--paper);border:1px solid var(--line);border-radius:8px;margin-bottom:18px}}
.cover{{position:relative;overflow:hidden;padding:44px 48px 40px;border-top:8px solid var(--red)}}.cover:after{{content:"08";position:absolute;right:34px;top:4px;font-size:144px;font-weight:1000;color:#fff0f3;line-height:1;z-index:0}}.cover>*{{position:relative;z-index:1}}.cover-top{{display:flex;justify-content:space-between;color:var(--red);font-size:12px;font-weight:900}}.profile{{display:flex;align-items:center;gap:16px;margin:30px 0 18px}}.avatar{{position:relative;width:76px;height:76px;border:3px solid #ffb6c3;background:var(--soft);border-radius:50%;display:grid;place-items:center;color:var(--red);font-size:28px;font-weight:900;overflow:hidden}}.avatar img{{position:absolute;inset:0;width:100%;height:100%;object-fit:cover}}h1{{font-size:42px;line-height:1.08;margin:0}}.position{{color:var(--muted);margin-top:7px;font-size:15px}}.cover-title{{max-width:820px;font-size:29px;line-height:1.42;margin:22px 0 10px;font-weight:900}}.cover-title:after{{content:"";display:block;width:110px;height:6px;background:var(--yellow);margin-top:14px}}.cover-sub{{font-size:16px;color:var(--muted)}}
.meta-strip{{display:grid;grid-template-columns:repeat(5,1fr);gap:8px;margin:26px 0 18px}}.meta-strip div{{background:#f7f7f8;padding:13px;border-radius:6px}}.meta-strip span{{display:block;color:var(--muted);font-size:11px;margin-bottom:5px}}.meta-strip strong{{font-size:18px}}.customer-question{{display:flex;gap:18px;align-items:flex-start;background:var(--soft);border-left:5px solid var(--red);padding:15px 17px;border-radius:6px}}.customer-question b{{color:var(--red);white-space:nowrap}}.seller-note{{margin-top:10px;display:flex;gap:14px;padding:13px 17px;border:1px solid #ffd1d9;border-radius:6px}}.seller-note strong{{white-space:nowrap}}
.executive{{padding:34px 40px}}.section-intro>span,.mini-title{{font-size:12px;color:var(--red);font-weight:900}}.section-intro h2{{font-size:28px;margin:6px 0 8px}}.section-intro p{{color:var(--muted);margin:0;line-height:1.7}}.executive-grid{{display:grid;grid-template-columns:1.4fr .9fr;gap:16px;margin-top:22px}}.key-insights article{{display:flex;gap:14px;border-top:1px solid var(--line);padding:15px 0}}.key-insights article:first-child{{border-top:0;padding-top:0}}.key-insights article>b{{color:var(--red);font-size:22px}}.key-insights strong{{font-size:16px}}.key-insights p{{margin:5px 0 0;color:var(--muted);line-height:1.65}}.first-actions{{background:var(--ink);color:#fff;padding:20px;border-radius:6px}}.first-actions h3{{margin:0 0 16px;font-size:17px}}.first-actions ol{{list-style:none;padding:0;margin:0}}.first-actions li{{display:flex;gap:12px;border-top:1px solid #36383e;padding:12px 0;line-height:1.5}}.first-actions li:first-child{{border-top:0}}.first-actions b{{color:var(--yellow)}}
.map-section,.appendix{{padding:34px 40px}}.dimension-nav-grid{{display:grid;grid-template-columns:repeat(4,1fr);gap:9px;margin-top:22px}}.dimension-nav{{min-height:146px;display:flex;flex-direction:column;text-decoration:none;color:var(--ink);border:1px solid var(--line);border-top:5px solid var(--red);border-radius:6px;padding:14px;transition:transform .15s,box-shadow .15s}}.dimension-nav:hover{{transform:translateY(-2px);box-shadow:0 8px 24px rgba(31,35,45,.09)}}.dimension-nav.focused{{background:var(--soft);border-color:#ff9eb0}}.dimension-nav>span{{font-size:22px;font-weight:950;color:var(--red)}}.dimension-nav div{{flex:1}}.dimension-nav strong{{display:block;font-size:17px;margin:7px 0}}.dimension-nav small{{display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden;line-height:1.5;color:var(--muted)}}.dimension-nav>b{{font-size:11px;color:var(--red);margin-top:8px}}
.dimension-section{{padding:34px 40px;scroll-margin-top:68px}}.dimension-section.focused{{border-top:6px solid var(--red)}}.dimension-head{{display:grid;grid-template-columns:auto 1fr auto;gap:16px;align-items:start}}.dimension-number{{background:var(--red);color:#fff;font-size:24px;font-weight:950;padding:6px 10px;border-radius:5px}}.dimension-label{{font-size:13px;color:var(--red);font-weight:900}}.dimension-head h2{{margin:5px 0 0;font-size:27px}}.focus-badge{{margin-left:8px;background:var(--yellow);color:var(--ink);padding:3px 6px;border-radius:4px;font-size:10px}}.dimension-state{{text-align:right;border-left:4px solid var(--orange);padding:7px 0 7px 12px;min-width:150px}}.dimension-state.ready{{border-color:var(--green)}}.dimension-state.blocked{{border-color:var(--red)}}.dimension-state strong,.dimension-state span{{display:block}}.dimension-state span{{font-size:11px;color:var(--muted);margin-top:4px}}.answer-box{{display:grid;grid-template-columns:110px 1fr;gap:18px;align-items:start;background:var(--soft);border-left:5px solid var(--red);padding:18px;margin:24px 0}}.answer-box span{{font-size:12px;color:var(--red);font-weight:900}}.answer-box strong{{font-size:19px;line-height:1.55}}.chapter-grid{{display:grid;grid-template-columns:1fr 1fr;gap:18px}}.chapter-grid>div{{border-top:1px solid var(--line);padding-top:4px}}.chapter-grid h3{{font-size:16px;margin:14px 0}}.plain-list{{margin:0;padding-left:20px}}.plain-list li,.meaning{{line-height:1.75;margin:8px 0}}.meaning{{color:#34363c}}.empty{{color:var(--muted)}}
.visual-block{{margin:24px 0;padding:20px;background:#f7f7f8;border-radius:6px}}.visual-split{{display:grid;grid-template-columns:1.35fr .8fr;gap:24px}}.bar-row{{margin:12px 0}}.bar-label{{display:flex;justify-content:space-between;gap:10px;font-size:12px}}.bar-label strong{{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}}.bar-label span{{color:var(--muted)}}.bar-track{{height:8px;background:#e1e2e6;border-radius:3px;margin-top:6px;overflow:hidden}}.bar-track i{{display:block;height:100%;background:var(--red);border-radius:3px}}.signal-panel{{display:flex;flex-direction:column;justify-content:center;border-left:1px solid var(--line);padding-left:24px}}.signal-number{{font-size:38px;font-weight:950;margin:10px 0 0}}.signal-panel p{{margin:4px 0;line-height:1.5}}.signal-foot{{color:var(--muted);font-size:11px;margin-top:12px}}.metric-pair{{display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-top:12px}}.metric-pair div{{background:#fff;border:1px solid var(--line);padding:16px;border-radius:5px}}.metric-pair strong,.metric-pair span{{display:block}}.metric-pair strong{{font-size:25px}}.metric-pair span{{font-size:11px;color:var(--muted);margin-top:5px}}.metric-pair.compact strong{{font-size:19px}}
.compare-row{{display:grid;grid-template-columns:76px 1fr 1fr;gap:8px;align-items:center;margin:12px 0;font-size:11px}}.compare-row>div{{position:relative;height:28px;background:#e7e7ea;overflow:hidden;border-radius:4px}}.compare-row i{{position:absolute;left:0;top:0;bottom:0}}.compare-row i.top{{background:var(--red)}}.compare-row i.bottom{{background:#858892}}.compare-row span{{position:relative;z-index:1;display:block;padding:7px;color:#17171b;white-space:nowrap}}.timeline{{display:flex;align-items:flex-end;gap:8px;height:230px;padding-top:18px;overflow-x:auto}}.month-col{{flex:1;min-width:54px;height:100%;display:grid;grid-template-rows:20px 1fr 38px;text-align:center;font-size:10px}}.month-col>div{{display:flex;align-items:flex-end;justify-content:center;border-bottom:1px solid #c8cad0}}.month-col i{{display:block;width:65%;background:var(--red);border-radius:3px 3px 0 0}}.month-col small{{color:var(--muted);padding-top:5px}}.tag-cloud{{display:flex;flex-wrap:wrap;gap:7px;margin:12px 0 22px}}.tag-chip{{background:#fff;border:1px solid #ffc1cc;color:var(--red-dark);padding:7px 10px;border-radius:4px;font-size:12px}}.tag-chip b{{color:var(--muted);margin-left:6px}}.search-title{{margin-top:20px}}.table-wrap{{overflow-x:auto}}table{{width:100%;border-collapse:collapse;margin-top:10px;font-size:12px}}th,td{{border:1px solid var(--line);padding:9px;text-align:left;vertical-align:top}}th{{background:#fff}}.zero-state{{background:#fff;border:1px solid var(--line);border-left:5px solid var(--yellow);padding:18px;border-radius:5px}}.zero-state p{{color:var(--muted);line-height:1.7;margin-bottom:0}}.compact-state{{margin-top:10px}}.plan-list{{display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-top:12px}}.plan-row{{display:flex;gap:12px;background:#fff;border:1px solid var(--line);padding:12px;border-radius:5px}}.plan-row>b{{display:grid;place-items:center;min-width:36px;height:36px;background:var(--red);color:#fff;border-radius:4px}}.plan-row strong,.plan-row span{{display:block}}.plan-row span{{font-size:11px;color:var(--muted);margin-top:4px;line-height:1.5}}
.ai-note{{margin:20px 0;border:1px solid #d4d7df;border-left:5px solid #373a42;padding:16px;border-radius:5px}}.ai-note p{{line-height:1.7}}.evidence-block{{margin-top:24px;border-top:1px solid var(--line);padding-top:20px}}.block-title{{display:flex;justify-content:space-between;align-items:end;gap:12px;margin-bottom:12px}}.block-title span,.block-title strong{{display:block}}.block-title span{{font-size:11px;color:var(--red);font-weight:900}}.block-title strong{{font-size:17px;margin-top:4px}}.block-title small{{color:var(--muted);text-align:right}}.evidence-grid{{display:grid;grid-template-columns:repeat(3,1fr);gap:9px}}.evidence-card{{border:1px solid var(--line);border-top:4px solid #bcc0c8;padding:13px;border-radius:5px}}.evidence-meta{{font-size:10px;color:var(--muted);margin-bottom:7px}}.evidence-card strong{{line-height:1.45}}.evidence-card p{{font-size:11px;color:var(--muted);line-height:1.6;margin-bottom:0}}.evidence-empty{{color:var(--muted);background:#f7f7f8;padding:14px;border-radius:5px}}.boundary{{display:flex;gap:12px;margin-top:14px;padding:12px 14px;background:var(--warm);border-radius:5px;font-size:11px;line-height:1.6}}.boundary strong{{white-space:nowrap;color:#7e5700}}
.source-grid{{display:grid;grid-template-columns:repeat(3,1fr);gap:8px;margin:20px 0}}.source-item{{border:1px solid var(--line);border-left:4px solid var(--orange);padding:11px;border-radius:5px}}.source-item.ready{{border-left-color:var(--green)}}.source-item.blocked{{border-left-color:var(--red)}}.source-item strong,.source-item span{{display:block}}.source-item span{{font-size:10px;color:var(--muted);margin-top:4px}}.appendix-list details{{border-top:1px solid var(--line)}}.appendix-list summary{{cursor:pointer;padding:15px 0;font-weight:800}}.appendix-body{{padding:4px 0 24px}}.appendix-body h2{{font-size:21px}}.appendix-body h3{{font-size:17px}}.appendix-body p,.appendix-body li{{line-height:1.7}}.footer{{text-align:center;color:var(--muted);font-size:11px;line-height:1.7;padding:20px}}
@media(max-width:760px){{html,body{{max-width:100%;overflow-x:hidden}}main{{width:calc(100% - 20px);margin-top:10px}}.cover,.executive,.map-section,.dimension-section,.appendix{{padding:24px 18px}}.cover:after{{font-size:90px;right:8px}}.cover-top span:last-child{{display:none}}.profile{{align-items:flex-start;gap:12px}}.profile>div:last-child{{min-width:0}}.avatar{{width:58px;height:58px;flex:0 0 58px;font-size:22px}}h1{{font-size:27px;overflow-wrap:anywhere}}.position,.cover-sub{{overflow-wrap:anywhere;word-break:break-word}}.cover-title{{font-size:23px}}.meta-strip{{grid-template-columns:minmax(0,1fr) minmax(0,1fr)}}.meta-strip strong{{font-size:16px;overflow-wrap:anywhere}}.customer-question{{flex-direction:column;gap:5px}}.executive-grid,.chapter-grid,.visual-split{{grid-template-columns:minmax(0,1fr)}}.section-intro h2,.dimension-head h2{{font-size:23px;overflow-wrap:anywhere}}.dimension-nav-grid{{grid-template-columns:1fr}}.dimension-head{{grid-template-columns:auto minmax(0,1fr)}}.dimension-state{{grid-column:1/-1;text-align:left}}.answer-box{{grid-template-columns:1fr;gap:5px}}.evidence-grid,.source-grid,.plan-list{{grid-template-columns:1fr}}.signal-panel{{border-left:0;border-top:1px solid var(--line);padding:18px 0 0}}.compare-row{{grid-template-columns:62px minmax(0,1fr)}}.compare-row>div:last-child{{grid-column:2}}.block-title{{align-items:flex-start;flex-direction:column}}.block-title small{{text-align:left}}.toolbar span{{display:none}}}}
@page{{size:A4;margin:12mm}}@media print{{body{{background:#fff}}.toolbar{{display:none}}main{{width:auto;margin:0}}section{{border:0;margin:0;border-radius:0}}.cover{{min-height:268mm;page-break-after:always}}.executive,.map-section{{page-break-after:always}}.dimension-section{{page-break-before:always}}.dimension-nav:hover{{transform:none;box-shadow:none}}.appendix-list details{{display:none}}.evidence-card,.plan-row,.visual-block{{break-inside:avoid}}}}
</style></head><body>
<div class="toolbar"><div class="toolbar-inner"><span>客户交付版 · 从看懂账号，到知道下一步怎么做</span><button onclick="window.print()">打印 / 另存为 PDF</button></div></div>
<main>
<section class="cover"><div class="cover-top"><span>XHS 博主分析助手</span><span>客户交付版 · 任务 {task_id}</span></div><div class="profile"><div class="avatar">{avatar}</div><div><h1>{nickname_html}</h1><div class="position">{_h(positioning)} · {_h(profile.get('bio') or '')}</div></div></div><div class="cover-title">8 维账号内容诊断报告</div><div class="cover-sub">{_h(conclusion)}</div>
<div class="meta-strip"><div><span>公开笔记</span><strong>{_number(status.get('sample_count'))} 篇</strong></div><div><span>正文样本</span><strong>{_number(status.get('content_sample_count'))} 篇</strong></div><div><span>评论样本</span><strong>{_number(status.get('comment_sample_count'))} 条</strong></div><div><span>搜索研究词</span><strong>{_number(status.get('search_keyword_count'))} 个</strong></div><div><span>分析方式</span><strong>{ai_text}</strong></div></div>
<div class="customer-question"><b>客户最关心</b><span>{_h(buyer_question)}</span></div>{seller_note}</section>
<section class="executive"><div class="section-intro"><span>先看结论</span><h2>不用先读数据，先拿走 {len(insights)} 个判断和下一步</h2><p>结论来自本次公开样本；报告会把事实、相关性线索与待验证假设分开。</p></div><div class="executive-grid"><div class="key-insights">{insight_html}</div><div class="first-actions"><h3>建议优先做</h3><ol>{action_html}</ol></div></div></section>
{_navigation(brief, results, context)}{dimensions}{_appendix(appendix_sections, status)}
<p class="footer">报告基于采集时可见的公开内容生成，不代表平台官方数据；不承诺流量、涨粉、搜索排名或商业结果。建议执行一轮小样本测试后再复盘。<br>任务编号：{task_id}</p>
</main></body></html>"""
