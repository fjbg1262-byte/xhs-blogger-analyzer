"""Compare 2-5 collected accounts on the same eight dimensions.

All values come from the stored datasets; nothing here calls a model. The
"next step" row and the week plan are rule-based suggestions derived from the
same numbers, so they stay consistent with the cards above them.
"""

from collections import Counter

from backend.services.note_workspace import is_incomplete


def _title_stats(rows):
    titles = [str(row.get("title") or "") for row in rows if row.get("title")]
    if not titles:
        return {"avg_length": 0, "digit_pct": 0.0, "missing_cover": 0}
    digit = sum(1 for title in titles if any(char.isdigit() for char in title))
    return {
        "avg_length": round(sum(len(title) for title in titles) / len(titles), 1),
        "digit_pct": round(digit / len(titles) * 100, 1),
        "missing_cover": sum(1 for row in rows if not row.get("cover_url")),
    }


def _tag_counts(rows, limit=6):
    counter = Counter(
        str(tag) for row in rows for tag in (row.get("tags") or []) if str(tag).strip()
    )
    return counter.most_common(limit)


def _monthly(rows, limit=6):
    months = Counter((row.get("published_at") or "")[:7] for row in rows if row.get("published_at"))
    ordered = sorted(months.items(), reverse=True)[:limit]
    return [{"month": month, "count": count} for month, count in sorted(ordered)]


def account_profile(card, stats, dataset, account):
    rows = dataset.get("rows") or []
    titles = _title_stats(rows)
    tags = _tag_counts(rows)
    monthly = _monthly(rows)
    published = [row.get("published_at") for row in rows if row.get("published_at")]
    span = len({value[:7] for value in published})
    avg_monthly = round(len(rows) / span, 1) if span else 0
    best = max(rows, key=lambda row: sum(
        value for value in (row.get("liked_count"), row.get("collected_count"),
                            row.get("comment_count"), row.get("share_count"))
        if isinstance(value, int)
    ), default=None)
    best_engagement = 0
    if best is not None:
        best_engagement = sum(
            value for value in (best.get("liked_count"), best.get("collected_count"),
                                best.get("comment_count"), best.get("share_count"))
            if isinstance(value, int)
        )
    return {
        "task_id": card.get("id"),
        "account_id": card.get("account_id"),
        "name": account.get("name") or "未命名账号",
        "profile_url": str(account.get("profile_url") or "").split("?")[0],
        "notes": stats.get("note_count", 0),
        "image_share": stats.get("image_share", 0),
        "video_share": stats.get("video_share", 0),
        "total_engagement": stats.get("total_engagement", 0),
        "median_engagement": stats.get("median_engagement") or 0,
        "top_share": stats.get("top_share", 0),
        "top_count": stats.get("top_count", 0),
        "latest_publish": (stats.get("latest_published_at") or "")[:10],
        "top_tag": stats.get("top_tag") or "",
        "top_tag_count": stats.get("top_tag_count", 0),
        "best_type": stats.get("best_type") or "",
        "format_ratio": stats.get("format_ratio") or 0,
        "title": titles,
        "tag_rank": tags,
        "monthly": monthly,
        "avg_monthly": avg_monthly,
        "body_coverage": round(
            stats.get("body_count", 0) / stats["note_count"] * 100, 1
        ) if stats.get("note_count") else 0,
        "failed": sum(1 for row in rows if is_incomplete(row)),
        "best_note": {
            "title": (best or {}).get("title") or "",
            "engagement": best_engagement,
        } if best is not None else {"title": "", "engagement": 0},
    }


def _join_tags(profile, count=3):
    tags = [f"{tag}({hits})" for tag, hits in profile["tag_rank"][:count]]
    return " / ".join(tags) if tags else "未获取"


def _next_step(profile):
    if not profile["notes"]:
        return "先完成一次采集，再谈方向。"
    tag = profile["top_tag"] or "现有主题"
    if profile["best_type"]:
        return f"先把「{tag}」做成 {profile['best_type']} 连续栏目，再看收藏是否抬升。"
    return f"先把「{tag}」做成连续栏目。"


DIMENSION_ROWS = [
    ("账号定位", lambda p: f"{p['top_tag'] or '未获取'} · 图文 {p['image_share']}% / 视频 {p['video_share']}%"),
    ("内容方向", lambda p: " / ".join(tag for tag, _ in p["tag_rank"][:3]) or "未获取"),
    ("选题结构", lambda p: f"Top 标签出现 {p['top_tag_count']} 次 · 覆盖 {len(p['tag_rank'])} 个标签"),
    ("标题与封面", lambda p: f"平均 {p['title']['avg_length']} 字 · 含数字 {p['title']['digit_pct']}% · 缺封面 {p['title']['missing_cover']} 篇"),
    ("互动表现", lambda p: f"中位数 {int(p['median_engagement'])} · 头部 {p['top_share']}% · 均值 {round(p['total_engagement'] / p['notes'], 1) if p['notes'] else 0}"),
    ("发布节奏", lambda p: f"月均 {p['avg_monthly']} 篇 · 最近 {p['latest_publish'] or '未获取'}"),
    ("标签与搜索", lambda p: _join_tags(p)),
    ("下一步动作", _next_step),
]


def _takeaways(profiles):
    if len(profiles) < 2:
        return []
    ordered = sorted(profiles, key=lambda item: item["median_engagement"], reverse=True)
    top, bottom = ordered[0], ordered[-1]
    items = []
    if bottom["median_engagement"]:
        gap = round((top["median_engagement"] / bottom["median_engagement"] - 1) * 100)
        if gap > 300:
            body = (
                f"{top['name']} 的单篇互动中位数比 {bottom['name']} 高出一个数量级，"
                f"先拆它的头部结构；{bottom['name']} 样本更少，结论只作参考。"
            )
            items.append({
                "kind": "值得借鉴",
                "title": "单篇互动差距明显",
                "body": body,
            })
        elif gap > 0:
            items.append({
                "kind": "值得借鉴",
                "title": f"{top['name']} 的单篇中位数高 {gap}%",
                "body": f"先拆解它的头部内容结构：{top['best_note']['title'][:40] or '头部内容'}。不要直接复制标题，先看信息密度和栏目结构。",
            })
    types = {profile["best_type"] for profile in profiles if profile["best_type"]}
    if len(types) > 1:
        detail = "、".join(f"{profile['name']} 靠{profile['best_type']}" for profile in profiles if profile["best_type"])
        items.append({
            "kind": "不要照搬",
            "title": "两个账号的最佳形式不同",
            "body": f"{detail}。形式互换前先用同主题小样本测试，不要一次改掉全部内容。",
        })
    shared = set(profiles[0]["tag_rank"]) & set(profiles[1]["tag_rank"]) if len(profiles) >= 2 else set()
    shared_tags = [tag for tag, _ in sorted(shared, key=lambda item: -item[1])][:3] if shared else []
    if shared_tags:
        items.append({
            "kind": "共同主题",
            "title": "部分标签重叠",
            "body": f"共同标签：{'、'.join(shared_tags)[:60]}。这些主题可以互相参考，但标题和封面要保留各自风格。",
        })
    return items


def _week_plan(profiles):
    if not profiles:
        return []
    lead = max(profiles, key=lambda item: item["notes"])
    tag = lead["top_tag"] or "高频主题"
    type_name = lead["best_type"] or "图文"
    return [
        {"day": "周一", "title": f"整理「{tag}」可用素材", "copy": f"把 {type_name} 里反复出现的场景和问题列出来，选 3 个能连续做的。"},
        {"day": "周二", "title": "发布第一篇同结构内容", "copy": f"封面和标题固定格式，只换{tag}下的具体对象。"},
        {"day": "周三", "title": "补拍封面和对比图", "copy": "同一机位、同一字体，保证系列识别度。"},
        {"day": "周五", "title": "发布第二篇并加来源说明", "copy": "正文里写清成本、时间和适用人群，方便收藏。"},
        {"day": "周日", "title": "复盘收藏与分享", "copy": "对比两篇的收藏中位数，再决定是否扩到其他主题。"},
    ]


def build_comparison(profiles):
    rows = [
        {"title": title, "values": [builder(profile) for profile in profiles]}
        for title, builder in DIMENSION_ROWS
    ]
    return {
        "accounts": profiles,
        "rows": rows,
        "takeaways": _takeaways(profiles),
        "plan": _week_plan(profiles),
        "boundary": "对比只用公开互动和已采集字段，不含浏览、曝光、粉丝或转化；建议是规则推导，不是模型结论。",
    }
