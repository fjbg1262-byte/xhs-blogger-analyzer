"""Quality checks for structured report outputs."""

import json
from pathlib import Path
from typing import Any, Dict, List, Union


PathLike = Union[str, Path]
LOW_INFO_TOPICS = {"未归类观察", "日常随手记录", "其他/未分类", "未分类", "其他"}
EIGHT_DIMENSION_KEYS = {
    "positioning_audience",
    "content_structure",
    "title_hook",
    "engagement_drivers",
    "growth_trajectory",
    "tag_search",
    "commercial_signals",
    "action_plan",
}


def _read_json(path: PathLike, default: Any):
    p = Path(path)
    if not p.exists():
        return default
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return default


def _write_json(path: PathLike, data: dict):
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _issue(code: str, message: str, severity: str = "warning", path: str = "") -> dict:
    return {"code": code, "severity": severity, "message": message, "path": path}


def _is_low_info_topic(name: str) -> bool:
    return any(token in str(name) for token in LOW_INFO_TOPICS)


def _collect_evidence_ids(brief: dict) -> set:
    ids = set()
    for note in brief.get("evidence_notes", []):
        if note.get("note_id"):
            ids.add(note["note_id"])
        if note.get("id"):
            ids.add(note["id"])
    return ids


def _duplicates(values: list) -> list:
    seen = set()
    dupes = []
    for value in values:
        if not value:
            continue
        if value in seen and value not in dupes:
            dupes.append(value)
        seen.add(value)
    return dupes


def _check_profile(results: dict) -> List[dict]:
    issues = []
    profile = results.get("profile", {})
    p25 = profile.get("p25")
    median = profile.get("median_likes")
    p75 = profile.get("p75")
    if None not in (p25, median, p75) and not (p25 <= median <= p75):
        issues.append(
            _issue(
                "profile_percentile_invalid",
                "分位数异常，应满足 p25 <= median <= p75。",
                "blocking",
                "results.profile",
            )
        )
    span = profile.get("content_span_months")
    if span is not None and span < 0:
        issues.append(
            _issue(
                "profile_negative_span",
                "内容时间跨度为负数。",
                "blocking",
                "results.profile.content_span_months",
            )
        )
    if profile.get("total_notes", 0) < 30:
        issues.append(
            _issue(
                "profile_small_sample",
                "样本少于 30 条，只适合轻量观察。",
                "warning",
                "results.profile.total_notes",
            )
        )
    return issues


def _check_data_quality(data_quality: dict, brief: dict) -> List[dict]:
    issues = []
    insufficient = {m.get("module") for m in brief.get("insufficient_modules", [])}
    tag_ready = data_quality.get("tag_analysis_ready", data_quality.get("tag_completeness", 0) >= 0.5)
    content_ready = data_quality.get("content_analysis_ready", data_quality.get("content_text_completeness", 0) >= 0.5)
    comment_ready = data_quality.get("comment_analysis_ready", data_quality.get("comment_completeness", 0) >= 0.5)
    media_ready = data_quality.get("media_analysis_ready", False)
    search_ready = data_quality.get("search_analysis_ready", False)
    if not tag_ready and "标签与SEO" not in insufficient:
        issues.append(
            _issue(
                "missing_tag_downgrade",
                "标签数据不足，但 brief 未标记 SEO 降级。",
                "blocking",
                "brief.insufficient_modules",
            )
        )
    if not content_ready and "正文结构" not in insufficient:
        issues.append(
            _issue(
                "missing_content_text_downgrade",
                "正文数据不足，但 brief 未标记正文结构降级。",
                "blocking",
                "brief.insufficient_modules",
            )
        )
    if not comment_ready and "评论与用户痛点" not in insufficient:
        issues.append(
            _issue(
                "missing_comment_downgrade",
                "评论数据不足，但 brief 未标记评论与用户痛点降级。",
                "blocking",
                "brief.insufficient_modules",
            )
        )
    if not media_ready and "媒体结构" not in insufficient:
        issues.append(
            _issue(
                "missing_media_downgrade",
                "媒体数据不足，但 brief 未标记媒体结构降级。",
                "blocking",
                "brief.insufficient_modules",
            )
        )
    if not search_ready and "搜索表达" not in insufficient:
        issues.append(
            _issue(
                "missing_search_downgrade",
                "搜索研究数据不足，但 brief 未标记搜索表达降级。",
                "blocking",
                "brief.insufficient_modules",
            )
        )
    if data_quality.get("topic_unclassified_pct", 0) > 35:
        issues.append(
            _issue(
                "topic_unclassified_high",
                "主题未归类比例超过 35%，主题类强结论应降级。",
                "blocking" if any("主线" in i.get("title", "") for i in brief.get("strong_insights", [])) else "warning",
                "data_quality.topic_unclassified_pct",
            )
        )
    if data_quality.get("deduped_note_count", 0) > 0:
        issues.append(
            _issue(
                "source_notes_deduped",
                "原始采集中存在重复笔记，已去重后分析。",
                "warning",
                "data_quality.deduped_note_count",
            )
        )
    return issues


def _check_eight_dimensions(brief: dict) -> List[dict]:
    issues = []
    dimensions = brief.get("eight_dimensions") or {}
    missing = sorted(EIGHT_DIMENSION_KEYS - set(dimensions))
    if missing:
        issues.append(
            _issue(
                "missing_eight_dimensions",
                "八维交付缺少模块：%s" % "、".join(missing),
                "blocking",
                "brief.eight_dimensions",
            )
        )
    evidence_ids = _collect_evidence_ids(brief)
    for key in sorted(EIGHT_DIMENSION_KEYS & set(dimensions)):
        item = dimensions.get(key) or {}
        path = f"brief.eight_dimensions.{key}"
        if item.get("status") not in ("ready", "limited"):
            issues.append(_issue("dimension_invalid_status", f"{key} 缺少有效状态。", "blocking", path))
        if not item.get("sources"):
            issues.append(_issue("dimension_missing_sources", f"{key} 未说明数据来源。", "blocking", path))
        if not item.get("findings"):
            issues.append(_issue("dimension_missing_findings", f"{key} 没有形成可读结论。", "blocking", path))
        if not item.get("limits"):
            issues.append(_issue("dimension_missing_limits", f"{key} 未声明分析边界。", "blocking", path))
        unknown = [note_id for note_id in item.get("evidence_note_ids", []) if note_id not in evidence_ids]
        if unknown:
            issues.append(
                _issue(
                    "dimension_unknown_evidence",
                    f"{key} 引用了证据池中不存在的笔记：{'、'.join(unknown[:3])}",
                    "blocking",
                    path,
                )
            )

    ai = brief.get("ai_enhancement") or {}
    if ai.get("enabled"):
        ai_dimensions = ai.get("dimensions") or {}
        for key, item in ai_dimensions.items():
            path = f"brief.ai_enhancement.dimensions.{key}"
            if key not in EIGHT_DIMENSION_KEYS:
                issues.append(_issue("ai_unknown_dimension", f"AI 返回了未知维度 {key}。", "blocking", path))
                continue
            unknown = [note_id for note_id in item.get("evidence_note_ids", []) if note_id not in evidence_ids]
            if unknown:
                issues.append(
                    _issue(
                        "ai_unknown_evidence",
                        f"AI 结论引用了不存在的笔记：{'、'.join(unknown[:3])}",
                        "blocking",
                        path,
                    )
                )
    return issues


def _check_dimension_reliability(data_quality: dict, brief: dict) -> List[dict]:
    """Stop weak upstream analysis from becoming confident client advice."""
    issues = []
    dimensions = brief.get("eight_dimensions") or {}
    unclassified_pct = data_quality.get("topic_unclassified_pct", 0) or 0
    if unclassified_pct > 35:
        for key in ("positioning_audience", "content_structure", "action_plan"):
            item = dimensions.get(key) or {}
            if item.get("status") == "ready" or item.get("confidence") in ("medium", "high"):
                issues.append(
                    _issue(
                        "unreliable_topic_used_by_dimension",
                        f"主题未归类占比为 {unclassified_pct}%，但 {key} 仍输出了确定结论。",
                        "blocking",
                        f"brief.eight_dimensions.{key}",
                    )
                )

    tag_ready = data_quality.get("tag_analysis_ready", False)
    tag_search = dimensions.get("tag_search") or {}
    if not tag_ready and tag_search.get("confidence") in ("medium", "high"):
        issues.append(
            _issue(
                "tag_search_overconfident",
                "标签样本不足，但标签与搜索维度仍被标记为中高置信。",
                "blocking",
                "brief.eight_dimensions.tag_search",
            )
        )

    return issues


def _check_insights(brief: dict) -> List[dict]:
    issues = []
    evidence_ids = _collect_evidence_ids(brief)
    strong_insight_ids = {i.get("id") for i in brief.get("strong_insights", [])}
    evidence_note_ids = [n.get("note_id") for n in brief.get("evidence_notes", [])]
    duplicated_pool_ids = _duplicates(evidence_note_ids)
    if duplicated_pool_ids:
        issues.append(
            _issue(
                "duplicate_evidence_notes",
                "证据池存在重复 note_id: %s" % ", ".join(duplicated_pool_ids[:3]),
                "blocking",
                "brief.evidence_notes",
            )
        )

    for idx, insight in enumerate(brief.get("strong_insights", [])):
        path = "brief.strong_insights[%s]" % idx
        ev = [e for e in insight.get("evidence_note_ids", []) if e]
        duplicated_ev = _duplicates(ev)
        if duplicated_ev:
            issues.append(
                _issue(
                    "duplicate_insight_evidence",
                    "强洞察引用了重复证据 note_id: %s" % ", ".join(duplicated_ev[:3]),
                    "blocking",
                    path,
                )
            )
        if not ev:
            issues.append(
                _issue(
                    "strong_insight_missing_evidence",
                    "强洞察缺少证据样本。",
                    "blocking",
                    path,
                )
            )
        missing = [e for e in ev if e not in evidence_ids]
        if missing:
            issues.append(
                _issue(
                    "strong_insight_unknown_evidence",
                    "强洞察引用了不存在的 evidence note_id: %s" % ", ".join(missing[:3]),
                    "blocking",
                    path,
                )
            )
        if insight.get("sample_size", 0) < 3 and insight.get("confidence") == "high":
            issues.append(
                _issue(
                    "strong_insight_overconfident",
                    "样本数不足却标记为高置信。",
                    "warning",
                    path,
                )
            )

    for idx, action in enumerate(brief.get("recommended_actions", [])):
        path = "brief.recommended_actions[%s]" % idx
        if action.get("source_insight_id") not in strong_insight_ids:
            issues.append(
                _issue(
                    "action_unknown_source",
                    "行动建议未绑定有效强洞察。",
                    "blocking",
                    path,
                )
            )
        ev = [e for e in action.get("evidence_note_ids", []) if e]
        if not ev:
            issues.append(
                _issue("action_missing_evidence", "行动建议缺少证据样本。", "blocking", path)
            )
        missing = [e for e in ev if e not in evidence_ids]
        if missing:
            issues.append(
                _issue(
                    "action_unknown_evidence",
                    "行动建议引用了不存在的 evidence note_id: %s" % ", ".join(missing[:3]),
                    "blocking",
                    path,
                )
            )

    return issues


def _check_patterns(brief: dict) -> List[dict]:
    issues = []
    for idx, pattern in enumerate(brief.get("title_patterns", {}).get("recommended", [])):
        if (
            pattern.get("count", 0) < 5
            or pattern.get("vs_overall_pct", 0) <= 20
            or pattern.get("vs_median_pct", 0) <= 10
        ):
            issues.append(
                _issue(
                    "recommended_pattern_below_threshold",
                    "推荐标题模式未达到 count>=5、均值提升>20% 且中位数提升>10% 的门槛。",
                    "blocking",
                    "brief.title_patterns.recommended[%s]" % idx,
                )
            )
    for idx, pattern in enumerate(brief.get("title_patterns", {}).get("avoid", [])):
        if (
            pattern.get("count", 0) < 5
            or pattern.get("vs_overall_pct", 0) >= -30
            or pattern.get("vs_median_pct", 0) >= -10
        ):
            issues.append(
                _issue(
                    "avoid_pattern_below_threshold",
                    "避坑标题模式未达到 count>=5、均值下降<-30% 且中位数下降<-10% 的门槛。",
                    "warning",
                    "brief.title_patterns.avoid[%s]" % idx,
                )
            )
    return issues


REQUIRED_REPORTS = {
    "00_博主画像卡片.md",
    "01_内容结构分析.md",
    "02_标题与文案分析.md",
    "03_互动归因分析.md",
    "04_成长轨迹分析.md",
    "05_标签与SEO分析.md",
    "06_商业化分析.md",
    "07_竞争定位分析.md",
    "08_策略建议与行动计划.md",
}

FORBIDDEN_REPORT_PHRASES = {
    "深度内容更易引爆": "正文长度相关性被写成因果",
    "增长爆发期": "公开笔记数据不能证明账号增长阶段",
    "成熟运营期": "公开笔记数据不能证明账号成熟阶段",
    "粉丝基础和传播力在持续增长": "缺少粉丝与曝光历史数据",
    "早期爆款和后期爆款的差距表明受众规模在扩大": "缺少受众规模历史数据",
    "搜索量极低": "缺少平台搜索量数据",
    "核心固定组合（高频标签）": "标签频次不能直接生成固定 SEO 组合",
    "当前处于早期商业化阶段": "公开内容信号不能证明商业化阶段",
}


def _check_report_files(reports_dir: Any) -> List[dict]:
    if not reports_dir:
        return []
    root = Path(reports_dir)
    issues = []
    missing = sorted(name for name in REQUIRED_REPORTS if not (root / name).exists())
    if missing:
        issues.append(
            _issue(
                "missing_report_dimensions",
                "完整交付缺少报告维度：%s" % "、".join(missing),
                "blocking",
                "reports",
            )
        )
    for path in root.glob("*.md") if root.exists() else []:
        try:
            content = path.read_text(encoding="utf-8")
        except Exception:
            issues.append(_issue("unreadable_report", f"无法读取 {path.name}", "blocking", str(path)))
            continue
        for phrase, reason in FORBIDDEN_REPORT_PHRASES.items():
            if phrase in content:
                issues.append(
                    _issue(
                        "unsupported_report_claim",
                        f"{path.name} 包含不受数据支持的表述“{phrase}”：{reason}。",
                        "blocking",
                        str(path),
                    )
                )
    return issues


def _check_topics(brief: dict) -> List[dict]:
    issues = []
    for idx, topic in enumerate(brief.get("topic_clusters", [])):
        path = "brief.topic_clusters[%s]" % idx
        if not topic.get("note_ids"):
            issues.append(_issue("topic_missing_note_ids", "主题缺少 note_ids。", "blocking", path))
        if _is_low_info_topic(topic.get("name", "")) and topic.get("avg_likes", 0) > 0:
            # Low-info topics can exist, but should not be the basis of recommendations.
            for insight in brief.get("strong_insights", []):
                if topic.get("name") and topic.get("name") in insight.get("title", ""):
                    issues.append(
                        _issue(
                            "low_info_topic_in_strong_insight",
                            "低信息主题进入强洞察。",
                            "blocking",
                            path,
                        )
                    )
    return issues


def run_report_quality_check(
    results_path: PathLike,
    brief_path: PathLike,
    output_path: PathLike,
    data_quality_path: Any = None,
    reports_dir: Any = None,
) -> Dict[str, Any]:
    """Run report quality checks and write report_quality_check.json."""
    results = _read_json(results_path, {})
    brief = _read_json(brief_path, {})
    data_quality = _read_json(data_quality_path, {}) if data_quality_path else {}
    if not data_quality:
        data_quality = brief.get("data_quality") or results.get("data_quality", {})

    issues = []
    if not results:
        issues.append(_issue("missing_results", "results.json 不存在或不可读取。", "blocking"))
    if not brief:
        issues.append(_issue("missing_brief", "insight_brief.json 不存在或不可读取。", "blocking"))

    if results:
        issues.extend(_check_profile(results))
    if brief:
        issues.extend(_check_data_quality(data_quality, brief))
        issues.extend(_check_eight_dimensions(brief))
        issues.extend(_check_dimension_reliability(data_quality, brief))
        issues.extend(_check_topics(brief))
        issues.extend(_check_insights(brief))
        issues.extend(_check_patterns(brief))
    issues.extend(_check_report_files(reports_dir))

    blocking = [i for i in issues if i["severity"] == "blocking"]
    warnings = [i for i in issues if i["severity"] != "blocking"]
    score = max(0, 100 - len(blocking) * 25 - len(warnings) * 5)
    result = {
        "passed": not blocking,
        "score": score,
        "blocking_issues": blocking,
        "warnings": warnings,
        "checks": {
            "blocking_count": len(blocking),
            "warning_count": len(warnings),
            "result_readable": bool(results),
            "brief_readable": bool(brief),
            "all_report_dimensions_present": not any(i["code"] == "missing_report_dimensions" for i in issues),
            "unsupported_claims_absent": not any(i["code"] == "unsupported_report_claim" for i in issues),
            "eight_dimensions_complete": not any(i["code"].startswith("dimension_") or i["code"] == "missing_eight_dimensions" for i in issues),
            "ai_evidence_valid": not any(i["code"].startswith("ai_") for i in issues),
        },
    }
    _write_json(output_path, result)
    return result
