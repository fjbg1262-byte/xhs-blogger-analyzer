"""Evidence-safe analytics derived from public note metrics."""

from collections import Counter, defaultdict
from datetime import datetime, timedelta
from math import ceil
from statistics import mean, median

from backend.services.note_library import count_value, date_value


METRIC_KEYS = ("liked_count", "collected_count", "comment_count", "share_count")
METRIC_LABELS = {
    "liked_count": "点赞",
    "collected_count": "收藏",
    "comment_count": "评论",
    "share_count": "分享",
}
TITLE_PATTERNS = (
    ("数字具体", r"\d"),
    ("问句悬念", r"[？?]|为什么|怎么|如何|多久|哪里|哪个|吗"),
    ("攻略清单", r"攻略|清单|指南|步骤|教程|方法|建议|路线|避坑"),
    ("对比选择", r"对比|区别|还是|vs|VS|选哪|怎么选|左还是右"),
    ("经历实测", r"实测|亲测|我|我的|一次|记录|体验"),
)


def _number(value):
    return count_value(value)


def _clean(row):
    metrics = {
        key: _number((row.get("metrics") or {}).get(key))
        for key in METRIC_KEYS
    }
    known = [value for value in metrics.values() if value is not None]
    return {
        "note_id": str(row.get("note_id") or ""),
        "title": str(row.get("title") or ""),
        "note_url": str(row.get("note_url") or ""),
        "type": str(row.get("type") or "未知"),
        "published_at": str(row.get("published_at") or ""),
        "tags": [str(tag)[:80] for tag in (row.get("tags") or []) if str(tag).strip()],
        "metrics": metrics,
        "engagement": sum(known),
        "metrics_known": len(known),
    }


def _median(values):
    values = [value for value in values if value is not None]
    return float(median(values)) if values else None


def _mean(values):
    values = [value for value in values if value is not None]
    return round(float(mean(values)), 1) if values else None


def _ratio(a, b):
    return round(float(a) / float(b), 2) if a is not None and b not in (None, 0) else None


def _share(part, total):
    return round(float(part) / float(total) * 100, 1) if total else 0.0


def _group_stats(rows, base_median, total_engagement):
    values = [row["engagement"] for row in rows]
    med = _median(values)
    return {
        "notes": len(rows),
        "total_engagement": sum(values),
        "median_engagement": med,
        "mean_engagement": _mean(values),
        "engagement_share": _share(sum(values), total_engagement),
        "intensity_vs_account": _ratio(med, base_median),
        "note_ids": [row["note_id"] for row in rows[:8]],
    }


def _percentile(values, fraction):
    values = sorted(values)
    if not values:
        return None
    if len(values) == 1:
        return float(values[0])
    position = (len(values) - 1) * fraction
    lower = int(position)
    upper = min(lower + 1, len(values) - 1)
    weight = position - lower
    return round(float(values[lower] * (1 - weight) + values[upper] * weight), 1)


def _title_signals(rows):
    import re

    result = []
    for label, pattern in TITLE_PATTERNS:
        matched = [row for row in rows if re.search(pattern, row["title"], re.I)]
        unmatched = [row for row in rows if not re.search(pattern, row["title"], re.I)]
        matched_median = _median([row["engagement"] for row in matched])
        unmatched_median = _median([row["engagement"] for row in unmatched])
        result.append({
            "label": label,
            "matched_notes": len(matched),
            "median_engagement": matched_median,
            "comparison_median": unmatched_median,
            "lift": _ratio(matched_median, unmatched_median),
            "reliable": len(matched) >= 5 and len(unmatched) >= 5,
            "note_ids": [row["note_id"] for row in matched[:5]],
        })
    return sorted(
        result,
        key=lambda item: (
            bool(item["reliable"]),
            item["lift"] if item["lift"] is not None else -1,
            item["matched_notes"],
        ),
        reverse=True,
    )


def _tag_signals(rows):
    grouped = defaultdict(list)
    for row in rows:
        for tag in dict.fromkeys(row["tags"]):
            grouped[tag].append(row)
    result = []
    for tag, tag_rows in grouped.items():
        values = [row["engagement"] for row in tag_rows]
        result.append({
            "tag": tag,
            "notes": len(tag_rows),
            "median_engagement": _median(values),
            "total_engagement": sum(values),
            "note_ids": [row["note_id"] for row in sorted(
                tag_rows, key=lambda row: row["engagement"], reverse=True
            )[:3]],
        })
    return sorted(
        result,
        key=lambda item: (item["notes"], item["median_engagement"] or -1),
        reverse=True,
    )[:12]


def _monthly(rows):
    grouped = defaultdict(list)
    for row in rows:
        month = row["published_at"][:7] if len(row["published_at"]) >= 7 else ""
        if month:
            grouped[month].append(row)
    result = []
    for month, month_rows in sorted(grouped.items()):
        values = [row["engagement"] for row in month_rows]
        result.append({
            "month": month,
            "notes": len(month_rows),
            "total_engagement": sum(values),
            "median_engagement": _median(values),
        })
    return result[-12:]


def _story_cards(rows, types, title_signals, tags, concentration, base_median):
    cards = []
    if concentration["top_20pct_share"] is not None:
        cards.append({
            "code": "CONCENTRATION",
            "value": f"{concentration['top_20pct_share']:.0f}%",
            "label": "头部的互动贡献",
            "title": f"Top {concentration['top_20pct_count']} 篇内容贡献了主要公开互动",
            "detail": (
                f"本批 Top {concentration['top_20pct_count']} 篇贡献 "
                f"{concentration['top_20pct_share']:.1f}% 的赞藏评享。"
                "这不等于账号长期只能靠爆款，但说明复盘应优先解释头部内容的结构。"
            ),
        })
    type_rows = [item for item in types if item["notes"] >= 3]
    if type_rows:
        strongest = max(
            type_rows,
            key=lambda item: item["median_engagement"] if item["median_engagement"] is not None else -1,
        )
        cards.append({
            "code": "FORMAT",
            "value": (
                f"{strongest['intensity_vs_account']:.1f}x"
                if strongest["intensity_vs_account"] is not None else "—"
            ),
            "label": "相对账号中位数",
            "title": f"{strongest['type']}是当前样本中互动中位数最高的形式",
            "detail": (
                f"该形式共 {strongest['notes']} 篇，互动中位数 "
                f"{strongest['median_engagement']:.1f}。这里比较的是公开互动快照，"
                "不是浏览或曝光效率。"
            ),
        })
    reliable_titles = [item for item in title_signals if item["reliable"] and item["lift"] is not None]
    if reliable_titles:
        signal = reliable_titles[0]
        cards.append({
            "code": "TITLE SIGNAL",
            "value": f"{signal['lift']:.1f}x",
            "label": "标题信号倍数",
            "title": f"“{signal['label']}”标题在本批样本中互动中位数更高",
            "detail": (
                f"匹配 {signal['matched_notes']} 篇，中位互动 "
                f"{signal['median_engagement']:.1f}，对照为中位数 "
                f"{signal['comparison_median']:.1f}。这是相关性信号，不是标题导致互动的证明。"
            ),
        })
    if tags:
        top = tags[0]
        cards.append({
            "code": "CONTENT PILLAR",
            "value": f"{top['notes']} 篇",
            "label": "高频内容标签",
            "title": f"“{top['tag']}”是当前样本最常出现的内容线索",
            "detail": (
                f"该标签出现于 {top['notes']} 篇，互动中位数 "
                f"{top['median_engagement'] if top['median_engagement'] is not None else '未获取'}。"
                "标签频次只说明内容覆盖，不等同于搜索流量。"
            ),
        })
    return cards[:4]


def build_report_analytics(evidence, coverage=None):
    """Build compact public-metric analytics with explicit non-causal boundaries."""
    rows = [_clean(row) for row in evidence if row.get("note_id")]
    engagements = [row["engagement"] for row in rows]
    total_engagement = sum(engagements)
    base_median = _median(engagements)
    ranked = sorted(
        rows,
        key=lambda row: (
            row["engagement"],
            row["metrics"].get("liked_count") or -1,
        ),
        reverse=True,
    )
    for rank, row in enumerate(ranked, 1):
        row["rank"] = rank
        row["engagement_multiple"] = _ratio(row["engagement"], base_median)

    by_type = defaultdict(list)
    for row in rows:
        by_type[row["type"]].append(row)
    types = [
        {"type": type_name, **_group_stats(group, base_median, total_engagement)}
        for type_name, group in by_type.items()
    ]
    types.sort(key=lambda item: item["median_engagement"] or -1, reverse=True)

    top_20pct_count = max(1, ceil(len(rows) * 0.2)) if rows else 0
    top_20pct_total = sum(row["engagement"] for row in ranked[:top_20pct_count])
    cumulative = 0
    notes_for_80pct = 0
    for row in ranked:
        cumulative += row["engagement"]
        notes_for_80pct += 1
        if cumulative >= total_engagement * 0.8:
            break

    dated_rows = []
    for row in rows:
        parsed = date_value(row["published_at"])
        if parsed:
            dated_rows.append((row, datetime.fromisoformat(parsed)))
    recent_window = None
    if dated_rows:
        latest = max(value for _, value in dated_rows)
        cutoff = latest - timedelta(days=30)
        recent_rows = [
            row for row, value in dated_rows if value >= cutoff
        ]
        older_rows = [row for row in rows if row not in recent_rows]
        recent_window = {
            "latest_published_at": latest.isoformat(timespec="seconds"),
            "days": 30,
            "recent": _group_stats(recent_rows, base_median, total_engagement),
            "older": _group_stats(older_rows, base_median, total_engagement),
        }

    title_signals = _title_signals(rows)
    tags = _tag_signals(rows)
    monthly = _monthly(rows)
    concentration = {
        "top_20pct_count": top_20pct_count,
        "top_20pct_share": _share(top_20pct_total, total_engagement),
        "notes_for_80pct": notes_for_80pct,
        "notes_for_80pct_share": _share(notes_for_80pct, len(rows)),
    }
    return {
        "metric_basis": "公开互动=点赞+收藏+评论+分享；不是浏览量、曝光率、ROI或转化率。",
        "notes": len(rows),
        "total_engagement": total_engagement,
        "mean_engagement": _mean(engagements),
        "median_engagement": base_median,
        "percentiles": {
            "p25": _percentile(engagements, 0.25),
            "p50": _percentile(engagements, 0.5),
            "p75": _percentile(engagements, 0.75),
            "p90": _percentile(engagements, 0.9),
        },
        "metric_totals": {
            key: sum(
                row["metrics"][key]
                for row in rows
                if row["metrics"].get(key) is not None
            )
            for key in METRIC_KEYS
        },
        "types": types,
        "concentration": concentration,
        "title_signals": title_signals,
        "tags": tags,
        "monthly": monthly,
        "recent_window": recent_window,
        "top_notes": ranked[:10],
        "high_low": {
            "high": _group_stats(
                [row for row in rows if row["note_id"] in set((coverage or {}).get("high_group", {}).get("note_ids", []))],
                base_median,
                total_engagement,
            ),
            "low": _group_stats(
                [row for row in rows if row["note_id"] in set((coverage or {}).get("low_group", {}).get("note_ids", []))],
                base_median,
                total_engagement,
            ),
        },
        "story_cards": _story_cards(
            rows, types, title_signals, tags, concentration, base_median
        ),
    }
