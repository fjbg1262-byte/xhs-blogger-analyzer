"""Write a ready analysis fixture for interface verification (no model calls).

The fixture uses the real dataset numbers and real note titles for evidence, but
the wording is written by hand and clearly marked as an example, so it must not
be shipped as a generated report.

Usage:
  .venv\\Scripts\\python.exe scripts/dev_seed_analysis.py --task 8
"""

import argparse
import json
import os
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.config import settings
from backend.services.analysis_analytics import build_report_analytics
from backend.services.library_analysis import DIMENSIONS, VERSION, build_bundle, fingerprint
from backend.services.note_library import now_text
from backend.services.note_workspace import dataset_stats, load_dataset


def _evidence(notes, title, body=None):
    if not notes:
        return []
    note = notes[0]
    items = [{"note_id": note["note_id"], "field": "title", "quote": note["title"][:120]}]
    if body and note.get("body_excerpt"):
        items.append({"note_id": note["note_id"], "field": "body_excerpt", "quote": note["body_excerpt"][:120]})
    return items


def build_fixture(dataset, goal):
    stats = dataset_stats(dataset)
    bundle = build_bundle(dataset, goal)
    notes = [note for note in bundle["notes"] if note.get("title")]
    ranked = sorted(
        notes,
        key=lambda note: sum(value for value in note["metrics"].values() if isinstance(value, int)),
        reverse=True,
    )
    pool = ranked or notes
    median = stats.get("median_engagement") or 0
    ratio = stats.get("format_ratio") or 0
    top_tag = stats.get("top_tag") or "未获取"
    findings = {
        "positioning_audience": (
            f"本批 {stats['note_count']} 篇里，最高频标签是「{top_tag}」，标题集中在{ '、'.join(t for t in [n['title'][:12] for n in pool[:3]]) }这类具体场景。",
            "读者更像是在找可以直接照着做的信息，而不是只看风景或感受。",
            "把主页简介和置顶统一成「地点 + 成本 + 时间」三件套，让新读者三秒判断要不要关注。",
            "也可能只是这批样本恰好集中在同一个季节，换个时间段结论会变。",
        ),
        "content_structure": (
            f"图文 {stats['image_count']} 篇、视频 {stats['video_count']} 篇；表现最好的形式相对账号中位数是 {ratio} 倍。",
            "清单和路线类内容更容易被收藏，视频在同样主题下更容易被转发。",
            "固定两条主线：一条做可复用的路线清单，一条做同类目的对比或排行。",
            "形式差异可能来自少数几篇爆款，不能直接说明视频一定更好。",
        ),
        "title_hook": (
            f"{stats['title_count']} 篇标题带数字，占 {stats['title_pct']}%；带价格或具体地点的标题在中位数以上。",
            "数字和具体地点降低了判断成本，读者能立刻知道这篇能解决什么。",
            "下一批标题保留一个具体数字（价格、时长、数量），其余部分说清目的地或对象。",
            "没有曝光和点击数据，不能证明是标题带来了互动。",
        ),
        "engagement_drivers": (
            f"公开互动中位数 {median}，Top {stats['top_count']} 篇贡献了 {stats['top_share']}% 的互动。",
            "互动高度集中在少数头部内容，长尾内容更多承担补充和搜索作用。",
            "复盘先解释头部内容的结构，再把可复用的部分写成模板。",
            "头部集中也可能来自平台分发的偶然性，不一定代表内容质量差异。",
        ),
        "growth_trajectory": (
            f"本批最近一篇发布于 {(stats.get('latest_published_at') or '')[:10] or '未获取'}，发布节奏集中在部分月份。",
            "节奏更像按目的地或季节集中更新，而不是稳定日更。",
            "按季节提前一个月排期，节假日前后各留一篇长线内容。",
            "只有当前互动快照，无法还原历史涨粉阶段。",
        ),
        "tag_search": (
            f"标签里「{top_tag}」出现 {stats['top_tag_count']} 次，其次是地域和形式类标签。",
            "标签主要起到归类作用，方便后续按主题复盘。",
            "每篇固定 2 个地域标签 + 1 个形式标签，导入飞书后按标签分组查看。",
            "没有搜索量和排名数据，不能说明标签带来了搜索流量。",
        ),
        "commercial_signals": None,
        "action_plan": (
            "先做一个两周的小系列：同结构、同封面、只换目的地，再看收藏中位数是否抬升。",
            "可复用的结构比单篇灵感更重要，先验证结构再扩题材。",
            "两周 4 篇同结构内容，第三周对比收藏和分享。",
            "如果两周没有变化，也可能是发布时段或选题本身的问题。",
        ),
    }

    dimensions = []
    for index, key in enumerate(DIMENSIONS):
        note = pool[index % len(pool)]
        if findings[key] is None:
            dimensions.append({
                "key": key,
                "status": "unavailable",
                "findings": [],
                "limitation": "本批没有合作、报价或商品信息，未获取；不做推测，也不补数字。",
            })
            continue
        observation, interpretation, next_step, alternative = findings[key]
        dimensions.append({
            "key": key,
            "status": "supported" if index < 4 else "limited",
            "findings": [{
                "observation": observation,
                "interpretation": interpretation,
                "next_step": next_step,
                "alternative_explanation": alternative,
                "evidence": _evidence([note], "title", body=index == 0),
            }],
            "limitation": f"只代表本批 {stats['note_count']} 篇公开样本。",
        })

    drafts = []
    topics = [
        ("三条不超过 50 元的周末路线", "想出门但不想自驾，也不想临时查换乘。", "50 元以内，公交能到的三个周末目的地", "不用自驾：我整理了三条便宜又好走的路线"),
        ("把常去的地方做成一张成本表", "看过很多推荐，但不知道真实花销。", "先去这三个地方，再决定值不值得跑远", "我按车费、时间和体力做了一张表"),
        ("一个人也能拍的旅行视频", "想记录但觉得设备不够。", "一个人拍旅行视频，三个镜头就够了", "不用稳定器，手机也能拍出旅行感"),
    ]
    for index, (topic, problem, title_a, title_b) in enumerate(topics):
        note = pool[(index + 1) % len(pool)]
        drafts.append({
            "topic": topic,
            "reader_problem": problem,
            "titles": [title_a, title_b],
            "opening": f"先说我自己的情况：{problem} 这篇把能直接抄的部分写清楚。",
            "outline": [
                "先说结论：适合谁、要花多少时间",
                "第一步：出发前要确认的三件事",
                "第二步：路线和停留点，按顺序写",
                "第三步：费用和时间成本对照",
                "结尾：什么情况下不建议去",
            ],
            "evidence": _evidence([note], "title"),
            "test": "连续两周发布同结构内容，记录收藏和分享。",
            "check": "第三周对比这两周的收藏中位数，是否高于本批中位数。",
        })

    analysis = {
        "priority_dimension": "content_structure",
        "headline": "先固定「地点 + 成本 + 时间」的清单结构，再扩题材。",
        "dimensions": dimensions,
        "drafts": drafts,
        "strategy": {
            "content_thesis": "低成本、可照着走的路线清单是这个账号最稳的内容主线。",
            "repeatable_model": "同结构系列：固定封面、固定三个信息位，只换目的地。",
            "growth_path": "先把路线系列做成可搜可收藏的合集，再补对比和排行。",
            "primary_risk": "只复制爆款标题、不验证结构，会让内容越来越像模板。",
        },
    }

    report = {
        "version": VERSION,
        "generated_at": now_text(),
        "dataset_fingerprint": fingerprint(dataset),
        "goal": goal,
        "model": "示例数据（未调用模型）",
        "provider": "fixture",
        "usage": [],
        "coverage": bundle["coverage"],
        "selection": bundle["selection"],
        "evidence": bundle["notes"],
        "analysis": analysis,
        "review": "pending",
        "validation": "示例数据：用于界面验证，未调用模型。",
    }
    report["analytics"] = build_report_analytics(report["evidence"], report["coverage"])
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Seed a ready analysis fixture for one task.")
    parser.add_argument("--task", type=int, required=True)
    parser.add_argument("--goal", default="想找出更适合继续做的方向，并给下周 3 个能直接发的选题。")
    args = parser.parse_args()

    dataset = load_dataset(args.task)
    if dataset is None:
        print(f"task {args.task} has no dataset")
        return 1

    report = build_fixture(dataset, args.goal)
    state = {
        "run_id": "fixture-" + uuid.uuid4().hex[:8],
        "analysis_version": VERSION,
        "status": "ready",
        "process_id": os.getpid(),
        "stage": "示例报告（未调用模型）",
        "dataset_fingerprint": fingerprint(dataset),
        "goal": args.goal,
        "report": report,
    }
    path = Path(settings.data_dir) / "tasks" / str(args.task) / "content_analysis.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"wrote {path}")
    print(f"dimensions={len(report['analysis']['dimensions'])} drafts={len(report['analysis']['drafts'])} review={report['review']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
