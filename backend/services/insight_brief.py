"""Build structured insight briefs from analysis outputs."""

import json
from pathlib import Path
from typing import Any, Union


LOW_INFO_TOPICS = {"未归类观察", "日常随手记录", "其他/未分类", "未分类", "其他"}


PathLike = Union[str, Path]


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


def _parse_count(value: Any) -> int:
    if isinstance(value, (int, float)):
        return int(value)
    if not isinstance(value, str):
        return 0
    value = value.strip()
    if not value:
        return 0
    if "万" in value:
        try:
            return int(float(value.replace("万", "")) * 10000)
        except ValueError:
            return 0
    try:
        return int(float(value))
    except ValueError:
        return 0


def _note_date(note_id: str) -> str:
    try:
        from datetime import datetime, timezone

        ts = int(str(note_id)[:8], 16)
        if 1500000000 < ts < 2000000000:
            return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d")
    except Exception:
        pass
    return ""


def _is_low_info_topic(name: str) -> bool:
    return any(token in str(name) for token in LOW_INFO_TOPICS)


def _topic_for_note(topic_distribution: dict, note_id: str) -> str:
    for name, payload in topic_distribution.items():
        if note_id in payload.get("note_ids", []):
            return name
    return "未归类观察"


def _note_to_evidence(note: dict, results: dict) -> dict:
    note_id = note.get("note_id", "")
    return {
        "id": note_id,
        "note_id": note_id,
        "title": note.get("title", ""),
        "likes": _parse_count(note.get("liked_count")),
        "type": note.get("type", ""),
        "date": _note_date(note_id),
        "topic": _topic_for_note(results.get("topic_distribution", {}), note_id),
    }


def _dedupe_notes(all_notes: list[dict]) -> list[dict]:
    deduped = []
    seen = set()
    for note in all_notes:
        note_id = note.get("note_id")
        if note_id:
            if note_id in seen:
                continue
            seen.add(note_id)
        deduped.append(note)
    return deduped


def _evidence_notes(all_notes: list[dict], results: dict, limit: int = 20) -> list[dict]:
    sorted_notes = sorted(_dedupe_notes(all_notes), key=lambda n: _parse_count(n.get("liked_count")), reverse=True)
    return [_note_to_evidence(note, results) for note in sorted_notes[:limit]]


def _top_note_ids_by_likes(all_notes: list[dict], note_ids: list[str], max_count: int = 5) -> list[str]:
    wanted = {note_id for note_id in note_ids if note_id}
    if not wanted:
        return []
    matched = [note for note in _dedupe_notes(all_notes) if note.get("note_id") in wanted]
    matched.sort(key=lambda note: _parse_count(note.get("liked_count")), reverse=True)
    return [note["note_id"] for note in matched[:max_count] if note.get("note_id")]


def _enrich_topic_clusters(results: dict, all_notes: list[dict]) -> list[dict]:
    clusters = []
    for topic in results.get("topic_clusters", []):
        enriched = dict(topic)
        enriched["evidence_note_ids"] = _top_note_ids_by_likes(
            all_notes,
            enriched.get("note_ids", []),
        )
        enriched["evidence_sort_rule"] = "按该主题内点赞数从高到低选取代表样本"
        clusters.append(enriched)
    return clusters


def _complete_evidence_notes(
    evidence_notes: list[dict],
    all_notes: list[dict],
    results: dict,
    *item_groups: list[dict],
) -> list[dict]:
    """Keep the top evidence pool, then append any note referenced by insights/actions."""
    existing_ids = {item.get("note_id") for item in evidence_notes}
    note_by_id = {note.get("note_id"): note for note in _dedupe_notes(all_notes) if note.get("note_id")}

    for group in item_groups:
        for item in group:
            for note_id in item.get("evidence_note_ids", []):
                if not note_id or note_id in existing_ids or note_id not in note_by_id:
                    continue
                evidence_notes.append(_note_to_evidence(note_by_id[note_id], results))
                existing_ids.add(note_id)
    return evidence_notes


def _annotate_evidence_notes(evidence_notes: list[dict], *item_groups: tuple[str, list[dict]]) -> list[dict]:
    note_usage: dict[str, list[dict]] = {}
    for group_type, group in item_groups:
        for item in group:
            item_title = item.get("title") or item.get("name") or item.get("id", "")
            for note_id in item.get("evidence_note_ids", []):
                note_usage.setdefault(note_id, []).append(
                    {
                        "id": item.get("id", ""),
                        "title": item_title,
                        "type": group_type,
                    }
                )

    for note in evidence_notes:
        usage = note_usage.get(note.get("note_id"), [])
        note["used_by"] = usage
        if usage:
            titles = "、".join([u["title"] for u in usage[:2] if u.get("title")])
            note["evidence_reason"] = (
                f"这条样本被「{titles}」引用。它的主题是「{note.get('topic', '未归类')}」，"
                f"互动表现为 {note.get('likes', 0)} 赞；系统优先按相关范围内点赞数选择代表样本，"
                "不是按发布时间排序。"
            )
        else:
            note["evidence_reason"] = (
                f"这条样本在本次数据中互动较高，主题是「{note.get('topic', '未归类')}」，"
                "属于默认高赞证据池，适合用来观察账号的高表现内容特征。"
            )
    return evidence_notes


def _attach_seven_day_plan(actions: list[dict]) -> list[dict]:
    for action in actions:
        action["seven_day_plan"] = [
            {"day": 1, "task": "拆 3 条证据样本", "goal": "记录对象、场景、标题承诺和结果反差。"},
            {"day": 2, "task": "写 10 个相邻选题", "goal": "围绕本建议筛出 3 个最具体、最容易执行的方向。"},
            {"day": 3, "task": "每个选题写 5 个标题", "goal": "保留具体对象、时间锚、成本或结果承诺。"},
            {"day": 4, "task": "完成 1 篇内容大纲", "goal": "把开头、主体、结尾和行动提示写清楚。"},
            {"day": 5, "task": "发布并记录初始数据", "goal": "记录发布时间、标题、主题、点赞和评论反馈。"},
            {"day": 6, "task": "复盘标题和选题反馈", "goal": "比较中位数、爆款率和评论里的真实问题。"},
            {"day": 7, "task": "决定放大或停止", "goal": "保留有效变量，停止低表现或数据不足的方向。"},
        ]
    return actions


def _find_note_ids_by_titles(all_notes: list[dict], titles: list[str], max_count: int = 5) -> list[str]:
    wanted = {t for t in titles if t}
    matched = [note for note in _dedupe_notes(all_notes) if note.get("title") in wanted and note.get("note_id")]
    matched.sort(key=lambda note: _parse_count(note.get("liked_count")), reverse=True)
    return [note["note_id"] for note in matched[:max_count]]


def _best_topic(results: dict):
    profile = results.get("profile", {})
    overall_avg = profile.get("avg_likes", 0) or 0
    data_quality = results.get("data_quality", {})
    if data_quality.get("topic_unclassified_pct", 0) > 50:
        return None
    candidates = []
    for name, topic in results.get("topic_distribution", {}).items():
        if _is_low_info_topic(name):
            continue
        if topic.get("count", 0) < 5:
            continue
        if topic.get("confidence") == "low":
            continue
        if topic.get("avg_likes", 0) < overall_avg * 1.15:
            continue
        candidates.append((name, topic))
    if not candidates:
        return None
    return max(candidates, key=lambda item: item[1].get("avg_likes", 0))


def _recommended_title_patterns(results: dict, all_notes: list[dict]) -> tuple[list[dict], list[dict]]:
    recommended = []
    avoid = []
    for name, payload in results.get("title_formulas", {}).items():
        item = {
            "name": name,
            "count": payload.get("count", 0),
            "avg_likes": payload.get("avg_likes", 0),
            "vs_overall_pct": payload.get("vs_overall_pct", 0),
            "burst_rate": payload.get("burst_rate", 0),
            "sample_titles": payload.get("sample", []),
            "top_title": payload.get("top", ""),
            "evidence_note_ids": _find_note_ids_by_titles(
                all_notes,
                payload.get("sample", []) + [payload.get("top", "")],
            ),
        }
        if item["count"] >= 3 and item["vs_overall_pct"] > 20:
            item["recommendation"] = "recommended"
            recommended.append(item)
        elif item["count"] >= 3 and item["vs_overall_pct"] < -30:
            item["recommendation"] = "avoid"
            avoid.append(item)
    recommended.sort(key=lambda x: x["avg_likes"], reverse=True)
    avoid.sort(key=lambda x: x["vs_overall_pct"])
    return recommended, avoid


def _insufficient_modules(data_quality: dict) -> list[dict]:
    modules = []
    if data_quality.get("tag_completeness", 0) < 0.5:
        modules.append(
            {
                "module": "标签与SEO",
                "reason": "标签字段不足，不能稳定判断搜索和标签策略。",
                "impact": "SEO 建议降级为数据不足提示。",
            }
        )
    if data_quality.get("content_text_completeness", 0) < 0.5:
        modules.append(
            {
                "module": "正文结构",
                "reason": "完整正文不足，不能稳定拆解 Hook、正文结构和 CTA。",
                "impact": "正文模板暂不进入强建议。",
            }
        )
    if data_quality.get("comment_completeness", 0) < 0.5:
        modules.append(
            {
                "module": "评论与用户痛点",
                "reason": "评论字段不足，不能判断用户真实问题和情绪。",
                "impact": "用户画像和互动归因只做弱推断。",
            }
        )
    if data_quality.get("topic_unclassified_pct", 0) > 50:
        modules.append(
            {
                "module": "主题分类",
                "reason": "未归类比例过高，主题结论不稳定。",
                "impact": "最佳主题和内容配比建议应降级。",
            }
        )
    return modules


def build_insight_brief(
    results_path: PathLike,
    all_notes_path: PathLike,
    output_path: PathLike,
    data_quality_path: Any = None,
) -> dict:
    """Generate insight_brief.json and return the brief dict."""
    results = _read_json(results_path, {})
    all_notes = _dedupe_notes(_read_json(all_notes_path, []))
    data_quality = _read_json(data_quality_path, {}) if data_quality_path else {}
    if not data_quality:
        data_quality = results.get("data_quality", {})

    profile = results.get("profile", {})
    engagement = results.get("engagement", {})
    best_topic = _best_topic(results)
    recommended_patterns, avoid_patterns = _recommended_title_patterns(results, all_notes)
    evidence_notes = _evidence_notes(all_notes, results)

    if best_topic:
        topic_name, topic_payload = best_topic
        one_sentence = (
            f"这个账号目前最值得学习的是「{topic_name}」："
            f"{topic_payload.get('count', 0)} 篇样本，均赞 {topic_payload.get('avg_likes', 0)}，"
            f"爆款率 {topic_payload.get('burst_rate', 0)}%。"
        )
        positioning = f"以{topic_name}为核心的内容观察型账号"
    else:
        topic_name, topic_payload = "", {}
        one_sentence = "本次数据暂未形成稳定的高表现主题，需要先改善主题分类或补充样本。"
        positioning = "内容观察型账号"

    strong_insights = []
    weak_insights = []
    recommended_actions = []
    avoid_actions = []

    if best_topic:
        insight_id = "insight_topic_1"
        top_note_ids = _top_note_ids_by_likes(all_notes, topic_payload.get("note_ids", []))
        strong_insights.append(
            {
                "id": insight_id,
                "title": f"{topic_name}是当前最强内容主线",
                "summary": (
                    f"该主题均赞 {topic_payload.get('avg_likes', 0)}，"
                    f"是整体均赞 {profile.get('avg_likes', 0)} 的 "
                    f"{round(topic_payload.get('avg_likes', 0) / max(profile.get('avg_likes', 1), 1), 1)} 倍。"
                ),
                "confidence": topic_payload.get("confidence", "medium"),
                "sample_size": topic_payload.get("count", 0),
                "metric": {
                    "avg_likes": topic_payload.get("avg_likes", 0),
                    "burst_rate": topic_payload.get("burst_rate", 0),
                    "above_avg_rate": topic_payload.get("above_avg_rate", 0),
                },
                "evidence_note_ids": top_note_ids,
                "evidence_rule": "在该主题内按点赞数从高到低选取代表样本。",
                "why_it_matters": "这说明用户更容易被该主题里的明确对象、场景或反差感吸引。",
                "action": f"围绕「{topic_name}」继续测试 3-5 个相邻选题，不要先扩散到泛内容。",
            }
        )
        recommended_actions.append(
            {
                "id": "action_topic_1",
                "title": f"围绕「{topic_name}」做一组连续选题",
                "source_insight_id": insight_id,
                "evidence_note_ids": top_note_ids,
                "evidence_rule": "沿用主题洞察的高赞代表样本。",
                "steps": [
                    "先拆出高赞样本里的对象、场景和结果反差。",
                    "写 3 个相邻选题，保持同一受众期待。",
                    "发布后用中位数和爆款率复盘，不只看单篇最高赞。",
                ],
            }
        )

    if recommended_patterns:
        pattern = recommended_patterns[0]
        insight_id = "insight_title_1"
        strong_insights.append(
            {
                "id": insight_id,
                "title": f"标题公式「{pattern['name']}」表现显著更好",
                "summary": (
                    f"该公式 {pattern['count']} 篇样本，均赞 {pattern['avg_likes']}，"
                    f"相对整体 {pattern['vs_overall_pct']:+.1f}%。"
                ),
                "confidence": "high" if pattern["count"] >= 5 else "medium",
                "sample_size": pattern["count"],
                "metric": {
                    "avg_likes": pattern["avg_likes"],
                    "vs_overall_pct": pattern["vs_overall_pct"],
                    "burst_rate": pattern["burst_rate"],
                },
                "evidence_note_ids": pattern["evidence_note_ids"],
                "why_it_matters": "标题里的时间锚、对象和结果承诺能降低理解成本，也更容易制造反差。",
                "action": f"优先测试「{pattern['name']}」标题，但不要套用低表现标题公式。",
            }
        )
        recommended_actions.append(
            {
                "id": "action_title_1",
                "title": f"用「{pattern['name']}」写 5 个标题草稿",
                "source_insight_id": insight_id,
                "evidence_note_ids": pattern["evidence_note_ids"],
                "steps": [
                    "保留具体时间、对象或成本信息。",
                    "标题里直接给出结果反差。",
                    "避免只用疑问句制造悬念。",
                ],
            }
        )

    pareto_pct = engagement.get("pareto_80pct_pct", 100)
    if pareto_pct and pareto_pct <= 20:
        strong_insights.append(
            {
                "id": "insight_engagement_1",
                "title": "账号互动高度依赖少数爆款",
                "summary": f"Top {pareto_pct}% 笔记贡献了 80% 点赞，说明账号是爆款驱动型。",
                "confidence": "high",
                "sample_size": profile.get("total_notes", 0),
                "metric": {
                    "pareto_80pct_pct": pareto_pct,
                    "top10pct_share": engagement.get("top10pct_share", 0),
                },
                "evidence_note_ids": [n["note_id"] for n in evidence_notes[:5]],
                "why_it_matters": "新手不应照抄全量内容，而应优先学习爆款样本里的可复用变量。",
                "action": "复盘时把爆款样本单独拆，不要用平均值代表整个账号。",
            }
        )

    for pattern in avoid_patterns[:3]:
        avoid_actions.append(
            {
                "id": f"avoid_title_{len(avoid_actions) + 1}",
                "title": f"谨慎套用「{pattern['name']}」",
                "reason": (
                    f"该模式均赞 {pattern['avg_likes']}，"
                    f"相对整体 {pattern['vs_overall_pct']:+.1f}%。"
                ),
                "evidence_note_ids": pattern["evidence_note_ids"],
            }
        )

    for module in _insufficient_modules(data_quality):
        weak_insights.append(
            {
                "id": f"weak_{module['module']}",
                "title": f"{module['module']}数据不足",
                "summary": module["reason"],
                "confidence": "low",
                "sample_size": 0,
                "evidence_note_ids": [],
                "action": f"{module['impact']} 当前页面会先保留提示，不把它写成确定策略。",
            }
        )

    recommended_actions = _attach_seven_day_plan(recommended_actions)
    evidence_notes = _complete_evidence_notes(
        evidence_notes,
        all_notes,
        results,
        strong_insights,
        recommended_actions,
        avoid_actions,
    )
    evidence_notes = _annotate_evidence_notes(
        evidence_notes,
        ("洞察", strong_insights),
        ("行动", recommended_actions),
        ("避坑", avoid_actions),
    )

    brief = {
        "version": "0.1",
        "account_summary": {
            "nickname": profile.get("nickname", ""),
            "user_id": profile.get("user_id", ""),
            "avatar_url": profile.get("avatar_url", ""),
            "bio": profile.get("bio", ""),
            "follower_count": profile.get("follower_count", 0),
            "positioning": positioning,
            "one_sentence": one_sentence,
            "learnability": "high" if best_topic and topic_payload.get("burst_rate", 0) >= 30 else "medium",
            "data_confidence": data_quality.get("overall_grade", "medium"),
        },
        "data_quality": data_quality,
        "strong_insights": strong_insights,
        "weak_insights": weak_insights,
        "topic_clusters": _enrich_topic_clusters(results, all_notes),
        "title_patterns": {
            "recommended": recommended_patterns,
            "avoid": avoid_patterns,
        },
        "evidence_notes": evidence_notes,
        "evidence_policy": {
            "default_sort": "默认证据池按点赞数从高到低展示。",
            "insight_sort": "点击具体洞察或主题时，优先展示该结论范围内的高赞代表样本。",
            "sample_count_note": "主题样本数表示该主题覆盖的全部笔记数，证据样本数表示当前用于复核结论的代表笔记数。",
        },
        "recommended_actions": recommended_actions,
        "avoid_actions": avoid_actions,
        "insufficient_modules": _insufficient_modules(data_quality),
    }
    _write_json(output_path, brief)
    return brief
