"""Quality checks for structured report outputs."""

import json
from pathlib import Path
from typing import Any, Dict, List, Union


PathLike = Union[str, Path]
LOW_INFO_TOPICS = {"未归类观察", "日常随手记录", "其他/未分类", "未分类", "其他"}


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
    if data_quality.get("tag_completeness", 0) < 0.5 and "标签与SEO" not in insufficient:
        issues.append(
            _issue(
                "missing_tag_downgrade",
                "标签数据不足，但 brief 未标记 SEO 降级。",
                "blocking",
                "brief.insufficient_modules",
            )
        )
    if data_quality.get("content_text_completeness", 0) < 0.5 and "正文结构" not in insufficient:
        issues.append(
            _issue(
                "missing_content_text_downgrade",
                "正文数据不足，但 brief 未标记正文结构降级。",
                "blocking",
                "brief.insufficient_modules",
            )
        )
    if data_quality.get("comment_completeness", 0) < 0.5 and "评论与用户痛点" not in insufficient:
        issues.append(
            _issue(
                "missing_comment_downgrade",
                "评论数据不足，但 brief 未标记评论与用户痛点降级。",
                "blocking",
                "brief.insufficient_modules",
            )
        )
    if data_quality.get("topic_unclassified_pct", 0) > 50:
        issues.append(
            _issue(
                "topic_unclassified_high",
                "主题未归类比例超过 50%，主题类强结论应降级。",
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
        if pattern.get("count", 0) < 3 or pattern.get("vs_overall_pct", 0) <= 20:
            issues.append(
                _issue(
                    "recommended_pattern_below_threshold",
                    "推荐标题模式未达到 count>=3 且 vs_overall_pct>20 的门槛。",
                    "blocking",
                    "brief.title_patterns.recommended[%s]" % idx,
                )
            )
    for idx, pattern in enumerate(brief.get("title_patterns", {}).get("avoid", [])):
        if pattern.get("count", 0) < 3 or pattern.get("vs_overall_pct", 0) >= -30:
            issues.append(
                _issue(
                    "avoid_pattern_below_threshold",
                    "避坑标题模式未达到 count>=3 且 vs_overall_pct<-30 的门槛。",
                    "warning",
                    "brief.title_patterns.avoid[%s]" % idx,
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
        issues.extend(_check_topics(brief))
        issues.extend(_check_insights(brief))
        issues.extend(_check_patterns(brief))

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
        },
    }
    _write_json(output_path, result)
    return result
