"""Customer-facing editorial report for the note-library analysis."""

import html
from datetime import datetime

from backend.services.analysis_analytics import build_report_analytics
from backend.services.note_library import safe_url


DIMENSION_LABELS = {
    "positioning_audience": "内容定位与读者线索",
    "content_structure": "内容方向",
    "title_hook": "标题与开头",
    "engagement_drivers": "高低表现对照",
    "growth_trajectory": "发布节奏",
    "tag_search": "标签与搜索表达",
    "commercial_signals": "商业表达线索",
    "action_plan": "下一步测试",
}
STATUS_LABELS = {
    "supported": "样本观察",
    "limited": "有限线索",
    "unavailable": "资料不足",
}
STRATEGY_LABELS = (
    ("content_thesis", "内容命题", "这个账号真正持续在解决什么问题"),
    ("repeatable_model", "可复用模型", "哪种选题和结构能够稳定重复"),
    ("growth_path", "增长试验", "下一步最值得验证的方向"),
    ("primary_risk", "主要误判", "最容易把相关性看成因果的地方"),
)


def _h(value) -> str:
    return html.escape(str(value if value is not None else ""), quote=True)


def _num(value, digits=0) -> str:
    if value is None:
        return "—"
    try:
        number = float(value)
    except (TypeError, ValueError):
        return "—"
    if digits:
        return f"{number:,.{digits}f}"
    return f"{number:,.0f}"


def _short_num(value) -> str:
    if value is None:
        return "—"
    try:
        number = float(value)
    except (TypeError, ValueError):
        return "—"
    if abs(number) >= 100000000:
        return f"{number / 100000000:.1f}亿"
    if abs(number) >= 10000:
        return f"{number / 10000:.1f}万"
    return f"{number:,.0f}"


def _pct(value) -> str:
    if value is None:
        return "—"
    return f"{float(value):.1f}%"


def _multiple(value) -> str:
    if value is None:
        return "—"
    return f"{float(value):.1f}x"


def _published(value: str) -> str:
    try:
        return datetime.fromisoformat(value).strftime("%Y-%m-%d")
    except (TypeError, ValueError):
        return value or "日期未获取"


def _status(status: str) -> str:
    return STATUS_LABELS.get(status, status)


def _section_head(number: str, kicker: str, title: str, subtitle: str = "") -> str:
    return (
        '<header class="section-head">'
        f'<div class="section-number">{_h(number)}</div>'
        '<div class="section-copy">'
        f'<div class="kicker">{_h(kicker)}</div><h2>{_h(title)}</h2>'
        + (f"<p>{_h(subtitle)}</p>" if subtitle else "")
        + "</div></header>"
    )


def _bar_width(value, maximum) -> float:
    try:
        return max(2.0, min(100.0, float(value or 0) / max(float(maximum or 1), 1) * 100))
    except (TypeError, ValueError):
        return 2.0


def _citation(evidence: dict, report: dict, compact: bool = False) -> str:
    note = next(
        (item for item in report.get("evidence", []) if item.get("note_id") == evidence.get("note_id")),
        {},
    )
    field = "标题" if evidence.get("field") == "title" else "正文"
    title = note.get("title") or evidence.get("note_id") or "原文"
    return (
        f'<blockquote class="citation{" compact" if compact else ""}">'
        f'<p>“{_h(evidence.get("quote", ""))}”</p>'
        f'<footer>{_h(field)} · {_h(title)}</footer></blockquote>'
    )


def _metric_cards(analytics: dict, coverage: dict) -> str:
    cards = (
        ("公开笔记", _num(analytics.get("notes")), "本批去重后的内容数"),
        ("公开互动", _short_num(analytics.get("total_engagement")), "赞 + 藏 + 评 + 分享"),
        ("单篇中位数", _num(analytics.get("median_engagement"), 1), "比均值更不易被爆款拉偏"),
        (
            "Top 20% 贡献",
            _pct((analytics.get("concentration") or {}).get("top_20pct_share")),
            f"{coverage.get('high_group', {}).get('n', 0)} 篇高表现样本参照",
        ),
    )
    return '<div class="metric-grid">' + "".join(
        '<article class="metric-card">'
        f'<span>{_h(label)}</span><strong>{_h(value)}</strong><p>{_h(note)}</p>'
        "</article>"
        for label, value, note in cards
    ) + "</div>"


def _story_cards(analytics: dict, report: dict) -> str:
    cards = analytics.get("story_cards") or []
    if not cards:
        finding = next(
            (
                section["findings"][0]
                for section in report["analysis"]["dimensions"]
                if section.get("findings")
            ),
            {},
        )
        cards = [{
            "code": "CONTENT SIGNAL",
            "value": "—",
            "label": "样本判断",
            "title": finding.get("observation", "本批内容暂不足以形成稳定结论"),
            "detail": finding.get("interpretation", ""),
        }]
    return '<div class="finding-grid">' + "".join(
        '<article class="finding-card">'
        f'<div class="finding-code">{_h(card.get("code"))}</div>'
        f'<div class="finding-value">{_h(card.get("value"))}</div>'
        f'<div class="finding-label">{_h(card.get("label"))}</div>'
        f'<h3>{_h(card.get("title"))}</h3><p>{_h(card.get("detail"))}</p>'
        "</article>"
        for card in cards
    ) + "</div>"


def _type_panel(analytics: dict) -> str:
    types = analytics.get("types") or []
    maximum = max((item.get("median_engagement") or 0 for item in types), default=1)
    rows = "".join(
        '<div class="bar-row">'
        '<div class="bar-meta">'
        f'<strong>{_h(item.get("type"))}</strong>'
        f'<span>{_num(item.get("notes"))} 篇 · 中位互动 {_num(item.get("median_engagement"), 1)}</span>'
        "</div>"
        f'<div class="bar-track"><i style="width:{_bar_width(item.get("median_engagement"), maximum):.1f}%"></i></div>'
        '<div class="bar-values">'
        f'<b>{_multiple(item.get("intensity_vs_account"))}</b>'
        f'<small>贡献 {_pct(item.get("engagement_share"))} 互动</small>'
        "</div></div>"
        for item in types
    )
    return (
        '<section class="panel portfolio-panel">'
        '<div class="panel-heading"><span>内容形式</span><h3>哪种内容承载了主要互动？</h3></div>'
        f'<div class="bar-list">{rows or "<p>没有可比较的内容形式。</p>"}</div>'
        '<p class="panel-note">倍数是相对账号公开互动中位数，不是浏览效率或爆款概率。</p>'
        "</section>"
    )


def _concentration_panel(analytics: dict) -> str:
    concentration = analytics.get("concentration") or {}
    share = float(concentration.get("top_20pct_share") or 0)
    other = max(0, 100 - share)
    return (
        '<section class="panel concentration-panel">'
        '<div class="panel-heading"><span>互动集中度</span><h3>爆款之外，是否还有稳定腰部？</h3></div>'
        '<div class="donut-wrap">'
        f'<div class="donut" style="background:conic-gradient(#b5430c 0 {share:.1f}%,#e4dccf {share:.1f}% 100%)">'
        f'<div><strong>{share:.0f}%</strong><span>头部贡献</span></div></div>'
        '<div class="legend-list">'
        f'<p><i class="legend-a"></i>Top {concentration.get("top_20pct_count", 0)} 篇贡献 {share:.1f}% 公开互动</p>'
        f'<p><i class="legend-b"></i>其余内容贡献 {other:.1f}%</p>'
        f'<p class="small">达到 80% 互动需要 {concentration.get("notes_for_80pct", 0)} 篇，占本批 {_pct(concentration.get("notes_for_80pct_share"))}。</p>'
        "</div></div>"
        '<div class="callout">集中度不是问题本身。它告诉你：先解释头部内容为什么被收藏/讨论，再判断这种结构能否被稳定复制。</div>'
        "</section>"
    )


def _tag_panel(analytics: dict) -> str:
    tags = (analytics.get("tags") or [])[:8]
    maximum = max((item.get("median_engagement") or 0 for item in tags), default=1)
    rows = "".join(
        '<div class="tag-row">'
        f'<span>{_h(item.get("tag"))}</span>'
        f'<div class="tag-track"><i style="width:{_bar_width(item.get("median_engagement"), maximum):.1f}%"></i></div>'
        f'<b>{_num(item.get("median_engagement"), 1)}</b>'
        f'<small>{item.get("notes", 0)} 篇</small>'
        "</div>"
        for item in tags
    )
    return (
        '<section class="panel tag-panel">'
        '<div class="panel-heading"><span>主题信号</span><h3>高频标签与互动中位数</h3></div>'
        f'<div class="tag-list">{rows or "<p>标签数据不足。</p>"}</div>'
        '<p class="panel-note">标签频次描述内容覆盖；没有搜索量、排名和来源数据，不能把标签解释成搜索流量。</p>'
        "</section>"
    )


def _monthly_panel(analytics: dict) -> str:
    months = analytics.get("monthly") or []
    if not months:
        return ""
    maximum = max((item.get("median_engagement") or 0 for item in months), default=1)
    columns = "".join(
        '<div class="month-column">'
        f'<span>{_num(item.get("median_engagement"), 0)}</span>'
        f'<div><i style="height:{_bar_width(item.get("median_engagement"), maximum):.1f}%"></i></div>'
        f'<b>{_h(str(item.get("month"))[2:])}</b><small>{item.get("notes", 0)} 篇</small>'
        "</div>"
        for item in months[-12:]
    )
    return (
        '<section class="panel monthly-panel">'
        '<div class="panel-heading"><span>发布节奏</span><h3>逐月内容量与互动中位数</h3></div>'
        f'<div class="month-chart">{columns}</div>'
        '<p class="panel-note">这是当前互动快照，不是粉丝增长曲线，也没有控制发布时间和题材。</p>'
        "</section>"
    )


def _top_notes_table(analytics: dict) -> str:
    rows = []
    for note in (analytics.get("top_notes") or [])[:8]:
        metrics = note.get("metrics") or {}
        title = _h(note.get("title") or "无标题")
        url = safe_url(note.get("note_url"))
        title_html = (
            f'<a href="{_h(url)}" target="_blank" rel="noopener noreferrer">{title}</a>'
            if url else title
        )
        rows.append(
            "<tr>"
            f'<td class="rank">{note.get("rank", "")}</td><td>{title_html}<small>{_h(note.get("type"))} · {_h(_published(note.get("published_at")))}</small></td>'
            f'<td>{_num(metrics.get("liked_count"))}</td><td>{_num(metrics.get("collected_count"))}</td>'
            f'<td>{_num(metrics.get("comment_count"))}</td><td>{_num(metrics.get("share_count"))}</td>'
            f'<td><strong>{_num(note.get("engagement"))}</strong></td><td>{_multiple(note.get("engagement_multiple"))}</td>'
            "</tr>"
        )
    return (
        '<div class="table-wrap"><table class="data-table"><thead><tr>'
        "<th>#</th><th>内容</th><th>赞</th><th>藏</th><th>评</th><th>享</th><th>公开互动</th><th>中位倍数</th>"
        "</tr></thead><tbody>"
        + "".join(rows)
        + "</tbody></table></div>"
    )


def _high_low(analytics: dict) -> str:
    high = (analytics.get("high_low") or {}).get("high") or {}
    low = (analytics.get("high_low") or {}).get("low") or {}
    cards = (
        ("高表现组", high, "high"),
        ("低表现组", low, "low"),
    )
    return '<div class="compare-grid">' + "".join(
        '<article class="compare-card">'
        f'<span>{_h(label)}</span><strong>{_num(group.get("median_engagement"), 1)}</strong>'
        '<p>公开互动中位数</p>'
        f'<small>{group.get("notes", 0)} 篇 · 贡献 {_pct(group.get("engagement_share"))} 互动</small>'
        "</article>"
        for label, group, _ in cards
    ) + "</div>"


def _strategy_cards(report: dict) -> str:
    strategy = report["analysis"].get("strategy") or {}
    return '<div class="strategy-grid">' + "".join(
        '<article class="strategy-card">'
        f'<span>{_h(kicker)}</span><h3>{_h(title)}</h3><p>{_h(strategy.get(key) or "本次资料不足以形成判断。")}</p>'
        "</article>"
        for key, title, kicker in STRATEGY_LABELS
    ) + "</div>"


def _title_signal_panel(analytics: dict) -> str:
    signals = [item for item in (analytics.get("title_signals") or []) if item.get("lift") is not None]
    maximum = max((item.get("lift") or 0 for item in signals), default=1)
    rows = "".join(
        '<div class="bar-row title-signal">'
        '<div class="bar-meta">'
        f'<strong>{_h(item.get("label"))}{"" if item.get("reliable") else " · 样本偏少"}</strong>'
        f'<span>{item.get("matched_notes", 0)} 篇匹配 · 中位互动 {_num(item.get("median_engagement"), 1)}</span>'
        "</div>"
        f'<div class="bar-track"><i style="width:{_bar_width(item.get("lift"), maximum):.1f}%"></i></div>'
        f'<div class="bar-values"><b>{_multiple(item.get("lift"))}</b><small>相对未匹配内容</small></div>'
        "</div>"
        for item in signals[:5]
    )
    return (
        '<section class="panel title-signal-panel">'
        '<div class="panel-heading"><span>标题语言</span><h3>哪些表达与更高互动同时出现？</h3></div>'
        f'<div class="bar-list">{rows}</div>'
        '<p class="panel-note">“样本偏少”表示匹配或对照不足 5 篇。这些是相关信号，不能直接判定某种标题导致了互动。</p>'
        "</section>"
    )


def _dimension_pages(report: dict) -> str:
    dimensions = report["analysis"].get("dimensions") or []
    pages = []
    for start in range(0, len(dimensions), 2):
        cards = []
        for index, section in enumerate(dimensions[start:start + 2], start + 1):
            findings = section.get("findings") or []
            body = ""
            for finding in findings:
                body += (
                    '<div class="dimension-finding">'
                    f'<h3>{_h(finding.get("observation"))}</h3>'
                    f'<p><b>这意味着什么</b>{_h(finding.get("interpretation"))}</p>'
                    f'<p><b>下一步怎么做</b>{_h(finding.get("next_step"))}</p>'
                    f'<p class="alternate"><b>另一种解释</b>{_h(finding.get("alternative_explanation"))}</p>'
                    + "".join(_citation(item, report, compact=True) for item in finding.get("evidence", []))
                    + "</div>"
                )
            if not body:
                body = '<div class="dimension-empty">本批公开资料不足以支持这一维度的确定判断。</div>'
            cards.append(
                '<article class="dimension-card">'
                f'<header><span>{index:02d}</span><div><h3>{_h(DIMENSION_LABELS.get(section.get("key")))}</h3>'
                f'<em>{_h(_status(section.get("status")))}</em></div></header>'
                f'{body}<p class="boundary">{_h(section.get("limitation"))} {_h(section.get("boundary"))}</p>'
                "</article>"
            )
        pages.append(
            '<section class="page">'
            + _section_head(
                "04",
                "EIGHT DIMENSIONS",
                "从内容表现，到可执行的下一步",
                "每一维都把观察、解释、行动和另一种解释分开。",
            )
            + '<div class="dimension-grid">' + "".join(cards) + "</div>"
            + _footer("八维内容诊断")
            + '</section>'
        )
    return "".join(pages)


def _draft_card(draft: dict, index: int, report: dict) -> str:
    titles = "".join(f"<li>{_h(title)}</li>" for title in draft.get("titles", []))
    outline = "".join(f"<li>{_h(item)}</li>" for item in draft.get("outline", []))
    citations = "".join(_citation(item, report, compact=True) for item in draft.get("evidence", []))
    return (
        '<article class="draft-card">'
        f'<div class="draft-index">{index:02d}</div>'
        '<div class="draft-body">'
        f'<h2>{_h(draft.get("topic"))}</h2>'
        f'<p class="reader-problem">{_h(draft.get("reader_problem"))}</p>'
        f'<section><h3>标题备选</h3><ol class="title-options">{titles}</ol></section>'
        f'<section><h3>开头草稿</h3><p class="opening">{_h(draft.get("opening"))}</p></section>'
        f'<section><h3>正文骨架</h3><ol class="outline-list">{outline}</ol></section>'
        f'<div class="test-grid"><div><span>怎么测试</span><p>{_h(draft.get("test"))}</p></div>'
        f'<div><span>如何复盘</span><p>{_h(draft.get("check"))}</p></div></div>'
        f'<div class="evidence-inline"><h3>创作依据</h3>{citations}</div>'
        "</div></article>"
    )


def _draft_pages(report: dict) -> str:
    drafts = report["analysis"].get("drafts") or []
    pages = []
    for index, draft in enumerate(drafts, 1):
        pages.append(
            '<section class="page">'
            + _section_head(
                "05",
                "ORIGINAL CONTENT PLANNING",
                "下一条内容，不从空白开始",
                "以下是根据当前公开内容生成的原创草稿，不是已验证有效的爆款模板。",
            )
            + _draft_card(draft, index, report)
            + _footer("内容选题与创作草稿")
            + '</section>'
        )
    return "".join(pages)


def _action_pages(report: dict) -> str:
    drafts = report["analysis"].get("drafts") or []
    first = drafts[0] if drafts else {}
    second = drafts[1] if len(drafts) > 1 else first
    plan = (
        ("D1", "确定变量", "从第一条草稿中选一个只改变标题或开头的测试。", first.get("test", "")),
        ("D2", "完成素材", "按第一条草稿的条件与大纲完成一个可复现样本。", first.get("reader_problem", "")),
        ("D3", "发布记录", "记录发布时间、标题版本和发布前固定条件。", "不用发布后的结果反推拍摄条件。"),
        ("D5", "第二条对照", "使用第二条草稿的测试方法，保留主题一致。", second.get("test", "")),
        ("D6", "查看评论", "区分笼统夸赞与询问条件、步骤、地点的具体追问。", "只读公开评论；本工具未自动采集评论正文。"),
        ("D7", "复盘判断", "比较公开赞藏评享中位数，不为没有依据的因果背书。", first.get("check", "")),
    )
    rows = "".join(
        '<div class="plan-row">'
        f'<b>{_h(day)}</b><div><strong>{_h(title)}</strong><p>{_h(task)}</p><small>{_h(note)}</small></div>'
        "</div>"
        for day, title, task, note in plan
    )
    return (
        '<section class="page">'
        + _section_head(
            "06",
            "SEVEN-DAY TEST PLAN",
            "把报告变成一周内能完成的动作",
            "先验证一个变量，再做有限复盘。",
        )
        + '<div class="plan-layout"><div class="plan-list">'
        + rows
        + '</div><aside class="boundary-card"><span>不要把测试当成承诺</span>'
        '<p>没有曝光、粉丝和后台转化数据，本计划只能比较公开互动快照与具体评论线索。一次发布不足以下结论，建议连续做两轮同条件测试。</p>'
        '<strong>可观察</strong><p>赞、藏、评、享的原始数；收藏相对点赞的变化；评论里是否出现具体追问。</p>'
        '<strong>不能计算</strong><p>浏览量、点击率、互动率、ROI、涨粉率、转化率。</p>'
        '</aside></div>'
        + _footer("7 天最小验证计划")
        + '</section>'
    )


def _evidence_page(report: dict) -> str:
    seen = set()
    rows = []
    for draft in report["analysis"].get("drafts", []):
        for item in draft.get("evidence", []):
            key = (item.get("note_id"), item.get("field"), item.get("quote"))
            if key not in seen:
                seen.add(key)
                rows.append((draft.get("topic", "创作草稿"), item))
    for section in report["analysis"].get("dimensions", []):
        for finding in section.get("findings", []):
            for item in finding.get("evidence", []):
                key = (item.get("note_id"), item.get("field"), item.get("quote"))
                if key not in seen:
                    seen.add(key)
                    rows.append((DIMENSION_LABELS.get(section.get("key"), "内容诊断"), item))
    pages = []
    for start in range(0, len(rows), 12):
        chunk = rows[start:start + 12]
        body = "".join(
            '<div class="evidence-row">'
            f'<span>{_h(source)}</span><blockquote>“{_h(item.get("quote"))}”</blockquote>'
            f'<small>{_h(item.get("field") == "title" and "标题" or "正文")} · {_h(item.get("note_id"))}</small>'
            "</div>"
            for source, item in chunk
        )
        subtitle = (
            "以下证据来自本次实际发送给模型的标题或正文摘录。"
            if start == 0 else f"证据索引续页 {start + 1}-{start + len(chunk)}。"
        )
        pages.append(
            '<section class="page">'
            + _section_head(
                "07",
                "EVIDENCE APPENDIX",
                "每个判断，都能回到一句原文",
                subtitle,
            )
            + '<div class="evidence-list">' + body + "</div>"
            + _footer("原文证据索引")
            + "</section>"
        )
    return "".join(pages)


def _method_page(report: dict) -> str:
    coverage = report.get("coverage") or {}
    review_text = "交付前已人工确认" if report.get("review") == "approved" else "待人工复核"
    return (
        '<section class="page">'
        + _section_head(
            "08",
            "METHOD & BOUNDARIES",
            "这份报告能说明什么，不能说明什么",
            "把数据口径写清楚，结论才值得被使用。",
        )
        + '<div class="method-grid">'
        '<article><span>样本</span><strong>'
        + _num(coverage.get("notes"))
        + '</strong><p>本批去重后的公开笔记。正文参与 AI 阅读 '
        + _num(coverage.get("bodies_sent"))
        + ' 篇，每篇最多 1600 字；标题、标签和互动数据覆盖整批。</p></article>'
        '<article><span>互动口径</span><strong>公开互动</strong><p>点赞、收藏、评论、分享相加。它不是平台后台的曝光、阅读、点击或转化。</p></article>'
        '<article><span>相关与因果</span><strong>不等于</strong><p>标题、形式和主题与互动的差异只是相关线索。未控制发布时间、曝光和选题，不宣称因果。</p></article>'
        '<article><span>缺失能力</span><strong>不猜测</strong><p>未分析图片、视频、评论正文、搜索流量、粉丝历史、订单和收入。资料不足的维度保持空缺。</p></article>'
        '</div>'
        '<div class="method-note"><strong>建议使用方式</strong><p>先读核心发现，再按一周计划完成两条同条件内容；下一次用新的公开数据复盘。不要直接复制原文，也不要承诺流量、涨粉或成交。</p></div>'
        '<footer class="signature"><span>内容诊断工作底稿</span><span>生成模型：'
        + _h(report.get("model") or "未记录")
        + '</span><span>·</span><span>'
        + review_text
        + '</span></footer>'
        + _footer("方法与边界")
        + '</section>'
    )


def _footer(section: str) -> str:
    return (
        '<footer class="page-footer"><span>XHS CONTENT DIAGNOSTIC</span>'
        f'<span>{_h(section)}</span><span>AI 辅助生成 · 交付前需人工复核</span></footer>'
    )


STYLE = r"""
*{box-sizing:border-box}
html{-webkit-print-color-adjust:exact;print-color-adjust:exact}
body{margin:0;background:#d9d0c3;color:#20201d;font-family:"Microsoft YaHei","PingFang SC",sans-serif;line-height:1.7;letter-spacing:0}
main{width:210mm;margin:0 auto}
.page{position:relative;width:210mm;min-height:297mm;padding:16mm 17mm 18mm;background:#f5f0e7;page-break-after:always;overflow:visible}
.page:last-child{page-break-after:auto}
.page::before{content:"";position:absolute;inset:0;pointer-events:none;background:
 radial-gradient(circle at 92% 7%,rgba(181,67,12,.08),transparent 22%),
 radial-gradient(circle at 5% 94%,rgba(179,53,46,.055),transparent 26%)}
.page>*{position:relative}
.cover{padding-top:14mm;display:flex;flex-direction:column;justify-content:space-between}
.topline,.page-footer,.signature{display:flex;justify-content:space-between;gap:10px;color:#756d61;font-size:9px;text-transform:uppercase;letter-spacing:.12em}
.topline{border-bottom:1px solid #bfb5a7;padding-bottom:10px}
.cover h1{font-family:"Songti SC","STSong","SimSun",serif;font-size:52px;line-height:1.14;letter-spacing:-.04em;margin:28mm 0 7mm;max-width:165mm}
.cover h1 em{font-style:normal;color:#b5430c}
.cover .lead{font-family:"Songti SC","STSong",serif;font-size:21px;line-height:1.6;margin:0 0 9mm;max-width:150mm;color:#3c3933}
.goal-box{border-left:4px solid #b5430c;padding:10px 16px;background:rgba(255,255,255,.34);font-size:12px;color:#665f54;margin:0 0 11mm}
.goal-box b{display:block;color:#25231f;margin-bottom:3px}
.metric-grid{display:grid;grid-template-columns:repeat(4,1fr);gap:8px;margin:12px 0}
.metric-card{background:rgba(255,255,255,.42);border:1px solid #d6ccbe;padding:13px 12px;min-height:95px}
.metric-card span,.panel-heading span,.strategy-card>span,.compare-card>span{font-size:9px;font-weight:700;color:#8a3b18;letter-spacing:.08em;text-transform:uppercase}
.metric-card strong{display:block;font-family:"Songti SC","STSong",serif;font-size:31px;line-height:1.2;margin-top:7px}
.metric-card p{font-size:9px;color:#7c7468;margin:4px 0 0}
.cover-thesis{margin-top:10mm;padding:17px 19px;background:#25231f;color:#f8f3e9}
.cover-thesis span{font-size:9px;color:#d59a78;letter-spacing:.1em}
.cover-thesis p{font-family:"Songti SC","STSong",serif;font-size:17px;line-height:1.75;margin:8px 0 0}
.cover-foot{border-top:1px solid #bfb5a7;padding-top:10px;font-size:10px;color:#726a5d}
.section-head{display:grid;grid-template-columns:22mm 1fr;gap:8mm;align-items:start;border-top:2px solid #25231f;padding-top:7mm;margin-bottom:8mm}
.section-number{font-family:"Songti SC","STSong",serif;font-size:42px;line-height:1;color:#b5430c}
.section-copy .kicker{font-size:9px;text-transform:uppercase;letter-spacing:.16em;color:#8a3b18;font-weight:700}
.section-copy h2{font-family:"Songti SC","STSong",serif;font-size:31px;line-height:1.25;margin:4px 0 3px;font-weight:700}
.section-copy p{font-size:11px;color:#736b5f;margin:0}
.finding-grid{display:grid;grid-template-columns:1fr 1fr;gap:9px}
.finding-card{min-height:102mm;padding:15px;background:rgba(255,255,255,.42);border:1px solid #d8cfc2;display:flex;flex-direction:column}
.finding-code{font-size:8px;letter-spacing:.14em;color:#8b8175;font-weight:700}
.finding-value{font-family:"Songti SC","STSong",serif;font-size:43px;line-height:1;color:#b5430c;margin-top:13px}
.finding-label{font-size:9px;color:#776e61;margin:4px 0 13px}
.finding-card h3{font-family:"Songti SC","STSong",serif;font-size:20px;line-height:1.45;margin:0 0 10px}
.finding-card p{font-size:11px;line-height:1.8;color:#4f4a42;margin:auto 0 0}
.question-strip{display:grid;grid-template-columns:repeat(4,1fr);gap:7px;margin-top:9px}
.question-strip div{border-top:2px solid #b5430c;padding-top:9px;font-size:10px;line-height:1.65}
.question-strip b{display:block;font-size:11px;margin-bottom:3px}
.panel{background:rgba(255,255,255,.4);border:1px solid #d8cfc2;padding:16px}
.panel-heading{margin-bottom:16px}.panel-heading h3{font-family:"Songti SC","STSong",serif;font-size:20px;margin:4px 0 0}
.portfolio-layout{display:grid;grid-template-columns:1.15fr .85fr;gap:9px}
.bar-list{display:grid;gap:17px}.bar-row{display:grid;grid-template-columns:minmax(0,1fr) 54px;gap:5px 9px;align-items:center}
.bar-meta strong{display:block;font-size:12px}.bar-meta span{font-size:9px;color:#7e7568}
.bar-track{height:8px;background:#e3dbcf;grid-column:1;overflow:hidden}.bar-track i{display:block;height:100%;background:#b5430c}
.bar-values{grid-column:2;grid-row:1/3;text-align:right}.bar-values b{display:block;font-family:"Songti SC","STSong",serif;font-size:20px;color:#b5430c}.bar-values small{font-size:8px;color:#82796c}
.panel-note{font-size:9px;line-height:1.6;color:#7c7366;margin:16px 0 0;padding-top:10px;border-top:1px solid #ddd4c7}
.donut-wrap{display:flex;align-items:center;gap:15px}.donut{width:130px;height:130px;border-radius:50%;display:grid;place-items:center;flex:0 0 130px}.donut>div{width:90px;height:90px;border-radius:50%;background:#f5f0e7;display:grid;place-items:center;text-align:center}.donut strong{font-family:"Songti SC","STSong",serif;font-size:27px;line-height:1}.donut span{font-size:8px;color:#746b5f;margin-top:4px}
.legend-list{font-size:9px;line-height:1.7}.legend-list p{margin:0 0 7px}.legend-list i{display:inline-block;width:8px;height:8px;margin-right:6px}.legend-a{background:#b5430c}.legend-b{background:#d5ccbf}.legend-list .small{color:#7a7164}
.callout{margin-top:15px;padding:10px 12px;background:#28251f;color:#f5efe3;font-size:9px;line-height:1.7}
.tag-panel,.monthly-panel,.title-signal-panel{margin-top:9px}.tag-list{display:grid;gap:11px}
.tag-row{display:grid;grid-template-columns:36mm minmax(0,1fr) 15mm 12mm;gap:7px;align-items:center;font-size:10px}
.tag-row>span{overflow-wrap:anywhere}.tag-track{height:6px;background:#e3dbcf}.tag-track i{display:block;height:100%;background:#c07339}.tag-row b{text-align:right;font-size:10px}.tag-row small{color:#847b6e;text-align:right}
.month-chart{height:48mm;display:flex;align-items:flex-end;gap:6px;border-bottom:1px solid #bfb5a7;padding:0 5px}
.month-column{flex:1;min-width:0;display:grid;grid-template-rows:auto 1fr auto;height:100%;text-align:center}
.month-column>span{font-size:8px;color:#7f766a}.month-column>div{display:flex;align-items:flex-end;justify-content:center}.month-column i{display:block;width:65%;max-width:18px;background:#b5430c;min-height:3px}.month-column b{font-size:8px;color:#514c43;margin-top:4px}.month-column small{font-size:7px;color:#8a8175}
.table-wrap{overflow:hidden}.data-table{width:100%;border-collapse:collapse;font-size:9px}.data-table th{background:#28251f;color:#f7f0e5;text-align:left;padding:7px 6px;font-size:8px}.data-table td{padding:7px 6px;border-bottom:1px solid #d8cfc2;vertical-align:top}.data-table td small{display:block;color:#81786b;font-size:7px;margin-top:2px}.data-table a{color:#292620;text-decoration:none}.data-table .rank{color:#b5430c;font-family:"Songti SC","STSong",serif;font-size:14px}
.compare-grid{display:grid;grid-template-columns:1fr 1fr;gap:9px;margin-top:9px}.compare-card{padding:14px;background:#eee6da;border-top:4px solid #2f2c27}.compare-card strong{display:block;font-family:"Songti SC","STSong",serif;font-size:35px;line-height:1.2;margin-top:8px}.compare-card p{margin:0;font-size:9px;color:#71685d}.compare-card small{display:block;margin-top:8px;font-size:8px;color:#81786b}
.strategy-grid{display:grid;grid-template-columns:1fr 1fr;gap:9px}.strategy-card{padding:17px;background:rgba(255,255,255,.45);border:1px solid #d8cfc2;min-height:54mm}.strategy-card h3{font-family:"Songti SC","STSong",serif;font-size:19px;margin:10px 0 8px}.strategy-card p{font-size:11px;line-height:1.85;color:#514b42;margin:0}
.dimension-grid{display:grid;grid-template-columns:1fr 1fr;gap:8px}.dimension-card{padding:13px;background:rgba(255,255,255,.43);border:1px solid #d8cfc2}.dimension-card>header{display:flex;gap:10px;align-items:center;border-bottom:1px solid #d8cfc2;padding-bottom:8px}.dimension-card>header>span{font-family:"Songti SC","STSong",serif;font-size:25px;color:#b5430c}.dimension-card h3{font-family:"Songti SC","STSong",serif;font-size:16px;margin:0}.dimension-card em{font-size:8px;font-style:normal;color:#836e5d}.dimension-finding h3{font-size:13px;line-height:1.55;margin:10px 0 7px}.dimension-finding p,.dimension-empty{font-size:9px;line-height:1.7;margin:6px 0}.dimension-finding p b{display:block;font-size:8px;color:#8a3b18;margin-bottom:2px}.dimension-finding .alternate{color:#746c60}.boundary{font-size:8px;color:#7d7365;background:#ebe2d6;padding:6px 8px;margin-top:9px}
.citation{margin:7px 0;padding:7px 9px;background:#eee7dc;border-left:2px solid #c47a49}.citation p{font-family:"Songti SC","STSong",serif;font-size:10px;line-height:1.65;margin:0}.citation footer{font-size:7px;color:#81776a;margin-top:3px}.citation.compact{margin:5px 0;padding:5px 7px}.citation.compact p{font-size:8px}
.draft-card{display:grid;grid-template-columns:14mm minmax(0,1fr);gap:9px;padding:11px 0 18px;border-bottom:1px solid #cfc4b5}.draft-card:nth-of-type(even){border-bottom:0}.draft-index{font-family:"Songti SC","STSong",serif;font-size:33px;color:#b5430c}.draft-card h2{font-family:"Songti SC","STSong",serif;font-size:23px;line-height:1.45;margin:0 0 6px}.reader-problem{font-size:10px;color:#686055;margin:0 0 12px}.draft-card section h3,.evidence-inline h3{font-size:9px;color:#8a3b18;margin:10px 0 5px;text-transform:uppercase;letter-spacing:.08em}.title-options{display:grid;grid-template-columns:1fr 1fr;gap:7px;padding:0;list-style:none;margin:0}.title-options li{padding:9px;background:#eee6da;font-size:10px;line-height:1.65}.opening{font-family:"Songti SC","STSong",serif;font-size:11px;line-height:1.8;margin:0;padding:9px 11px;background:rgba(255,255,255,.48);border-left:3px solid #b5430c}.outline-list{margin:0;padding-left:18px;columns:2;column-gap:16px}.outline-list li{font-size:9px;line-height:1.65;margin-bottom:5px;break-inside:avoid}.test-grid{display:grid;grid-template-columns:1fr 1fr;gap:7px;margin-top:10px}.test-grid div{padding:9px;background:#e9e1d5}.test-grid span{font-size:8px;color:#8a3b18;font-weight:700}.test-grid p{font-size:8px;line-height:1.6;margin:3px 0 0}.evidence-inline{margin-top:8px}
.plan-layout{display:grid;grid-template-columns:1.15fr .85fr;gap:11px}.plan-row{display:grid;grid-template-columns:15mm 1fr;gap:9px;padding:10px 0;border-bottom:1px solid #cfc4b5}.plan-row>b{font-family:"Songti SC","STSong",serif;font-size:18px;color:#b5430c}.plan-row strong{font-size:11px}.plan-row p{font-size:9px;line-height:1.65;margin:2px 0}.plan-row small{font-size:8px;color:#7c7367}.boundary-card{padding:17px;background:#28251f;color:#f4eee3}.boundary-card span{font-family:"Songti SC","STSong",serif;font-size:20px}.boundary-card p{font-size:10px;line-height:1.8;color:#d8d0c4}.boundary-card strong{display:block;color:#dca77f;margin-top:14px;font-size:9px}
.evidence-list{display:grid;grid-template-columns:1fr 1fr;gap:7px}.evidence-row{padding:9px;background:rgba(255,255,255,.42);border:1px solid #d8cfc2;break-inside:avoid}.evidence-row>span{font-size:7px;color:#8a3b18}.evidence-row blockquote{font-family:"Songti SC","STSong",serif;font-size:9px;line-height:1.6;margin:4px 0}.evidence-row small{font-size:7px;color:#847a6d}
.method-grid{display:grid;grid-template-columns:1fr 1fr;gap:9px}.method-grid article{padding:17px;background:rgba(255,255,255,.43);border:1px solid #d8cfc2;min-height:43mm}.method-grid span{font-size:8px;color:#8a3b18}.method-grid strong{display:block;font-family:"Songti SC","STSong",serif;font-size:23px;margin:8px 0}.method-grid p{font-size:10px;line-height:1.75;margin:0;color:#5e574d}.method-note{margin-top:12px;padding:17px;border:2px solid #28251f}.method-note p{font-size:11px;line-height:1.8;margin:5px 0 0}.signature{margin-top:16mm;padding-top:10px;border-top:1px solid #bfb5a7}
.page-footer{position:absolute;left:17mm;right:17mm;bottom:7mm;border-top:1px solid #cfc4b5;padding-top:5px;font-size:7px}
@media screen{body{padding:22px}.page{margin:0 auto 20px;box-shadow:0 10px 34px rgba(55,43,27,.16)}}
@media print{body{background:#fff}main{width:210mm}.page{margin:0;box-shadow:none}@page{size:A4;margin:0}}
@media(max-width:760px){body{padding:0;background:#f5f0e7}main,.page{width:100%;min-height:auto}.page{padding:24px 18px 32px}.cover h1{font-size:35px;margin-top:14vh}.metric-grid,.finding-grid,.portfolio-layout,.dimension-grid,.strategy-grid,.compare-grid,.test-grid,.plan-layout,.evidence-list,.method-grid{grid-template-columns:1fr}.finding-card{min-height:auto}.question-strip{grid-template-columns:1fr 1fr}.section-head{grid-template-columns:1fr}.section-number{font-size:28px}.page-footer{position:static;margin-top:30px}.outline-list{columns:1}.title-options{grid-template-columns:1fr}.tag-row{grid-template-columns:1fr 1fr 15mm 12mm}.table-wrap{overflow-x:auto}.data-table{min-width:680px}}
@media print{
  body{padding:0}
  main,.page{width:210mm;min-height:297mm}
  .page{padding:14mm 17mm 17mm}
  .metric-grid{grid-template-columns:repeat(4,1fr)}
  .finding-grid,.dimension-grid,.strategy-grid,.compare-grid,.test-grid,.portfolio-layout,.plan-layout,.evidence-list,.method-grid,.ov-strategy>div{grid-template-columns:1fr 1fr}
  .question-strip{grid-template-columns:repeat(4,1fr)}
  .section-head{grid-template-columns:22mm 1fr}
  .section-number{font-size:42px}
  .finding-card{min-height:94mm}
  .page-footer{position:absolute;left:17mm;right:17mm;bottom:7mm;margin:0}
  .outline-list{columns:2}
  .title-options{grid-template-columns:1fr 1fr}
  .tag-row{grid-template-columns:36mm minmax(0,1fr) 15mm 12mm}
  .data-table{min-width:0}
}
"""


def render_analysis_html(report: dict) -> str:
    analytics = report.get("analytics") or build_report_analytics(
        report.get("evidence", []), report.get("coverage", {})
    )
    account = report.get("account_name") or "账号内容"
    coverage = report.get("coverage") or {}
    goal = report.get("goal") or "本次未填写客户目标"
    generated = _published(report.get("generated_at", ""))

    cover = (
        '<section class="page cover">'
        '<div><div class="topline"><span>XHS CONTENT DIAGNOSTIC · DEEP REPORT</span>'
        f'<span>{_h(generated)}</span></div>'
        f'<h1>把公开内容，<br><em>变成下一步动作。</em></h1>'
        f'<p class="lead">{_h(account)} · 一份基于公开笔记的内容战略与创作诊断</p>'
        f'<div class="goal-box"><b>客户目标</b>{_h(goal)}</div>'
        + _metric_cards(analytics, coverage)
        + '<div class="cover-thesis"><span>本次核心判断</span>'
        f'<p>{_h(report["analysis"].get("headline"))}</p></div>'
        '</div>'
        f'<div class="cover-foot">基于 {_num(coverage.get("notes"))} 篇公开笔记 · AI 阅读 {_num(coverage.get("bodies_sent"))} 篇正文摘录 · 公开互动口径：赞藏评享 · 图片、视频、评论正文未分析</div>'
        + _footer("核心诊断")
        + '</section>'
    )

    executive = (
        '<section class="page">'
        + _section_head(
            "01",
            "EXECUTIVE FINDINGS",
            "先看真正影响下一步的四个发现",
            "数字只是入口。每条发现都说明它意味着什么、为什么还不能过度解读。",
        )
        + _story_cards(analytics, report)
        + '<div class="question-strip">'
        '<div><b>01 稳定方向</b>账号持续在解决什么具体问题？</div>'
        '<div><b>02 偶然波动</b>哪些题材只有单篇高表现？</div>'
        '<div><b>03 表达信号</b>什么标题与形式同时出现更高互动？</div>'
        '<div><b>04 下一步</b>下周最值得用哪条内容实验？</div>'
        '</div>'
        + _footer("核心发现")
        + '</section>'
    )

    portfolio = (
        '<section class="page">'
        + _section_head(
            "02",
            "CONTENT PORTFOLIO",
            "账号在发什么，互动集中在哪里",
            "从内容形式、主题标签和发布节奏三个角度拆开看。",
        )
        + '<div class="portfolio-layout">'
        + _type_panel(analytics)
        + _concentration_panel(analytics)
        + '</div>'
        + _footer("内容与互动结构")
        + '</section>'
    )
    portfolio_continued = (
        '<section class="page">'
        + _section_head(
            "02",
            "CONTENT PORTFOLIO · CONTINUED",
            "主题分布与发布节奏",
            "标签描述内容覆盖，月份描述当前样本的发布与互动快照。",
        )
        + _tag_panel(analytics)
        + _monthly_panel(analytics)
        + '</section>'
    )

    performance = (
        '<section class="page">'
        + _section_head(
            "03",
            "PERFORMANCE ANATOMY",
            "头部内容做对了什么，不能证明什么",
            "先看数据表现，再看内容解释，最后区分事实与假设。",
        )
        + _top_notes_table(analytics)
        + _high_low(analytics)
        + _footer("高低表现解剖")
        + '</section>'
    )

    strategy_page = (
        '<section class="page">'
        + _section_head(
            "04",
            "CONTENT STRATEGY",
            "从内容清单，到可重复的内容系统",
            "战略判断不是口号：每个方向都要能连接样本证据和下一步测试。",
        )
        + _strategy_cards(report)
        + _footer("内容战略")
        + '</section>'
    )
    title_page = (
        '<section class="page">'
        + _section_head(
            "04",
            "TITLE & FORMAT SIGNALS",
            "标题不是装饰，是内容承诺的一部分",
            "比较与更高互动同时出现的语言特征，并保留样本量和因果边界。",
        )
        + _title_signal_panel(analytics)
        + _footer("内容战略与标题信号")
        + '</section>'
    )

    evidence = _evidence_page(report)
    method = _method_page(report)
    drafts = _draft_pages(report)
    actions = _action_pages(report)

    return (
        '<!doctype html><html lang="zh-CN"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        f'<title>{_h(account)} · 内容战略诊断</title><style>{STYLE}</style></head><body>'
        '<main>'
        + cover
        + executive
        + portfolio
        + portfolio_continued
        + performance
        + strategy_page
        + title_page
        + _dimension_pages(report)
        + drafts
        + actions
        + evidence
        + method
        + '</main></body></html>'
    )
