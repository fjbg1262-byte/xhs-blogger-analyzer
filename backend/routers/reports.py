"""Report retrieval and comparison endpoints."""

import html
import json
import zipfile
from io import BytesIO
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from backend.database import Task, get_db
from backend.routers.auth import get_current_user

router = APIRouter(prefix="/api/reports", tags=["reports"])

MSG_REPORTS_NOT_FOUND = "Reports not found"
MSG_NEED_TWO_TASKS = "Need at least 2 task IDs"


def _get_owned_task(task_id: int, db: Session, current_user: dict) -> Task:
    task = (
        db.query(Task)
        .filter(Task.id == task_id, Task.user_id == current_user["id"])
        .first()
    )
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task


def _reports_dir(task_id: int) -> Path:
    return Path(f"reports/task_{task_id}")


def _task_data_dir(task_id: int) -> Path:
    return Path(f"data/tasks/{task_id}")


def _safe_text(value) -> str:
    return html.escape(str(value or ""), quote=True)


def _format_count(value) -> str:
    try:
        n = float(value or 0)
    except (TypeError, ValueError):
        return "0"
    if n >= 10000:
        return f"{n / 10000:.1f}万"
    return str(int(n)) if n.is_integer() else f"{n:.1f}"


def _share_html(task_id: int, brief: dict, quality: dict) -> str:
    summary = brief.get("account_summary", {})
    data_quality = brief.get("data_quality", {})
    strong = brief.get("strong_insights", [])[:3]
    weak = brief.get("weak_insights", [])
    actions = brief.get("recommended_actions", [])[:2]
    evidence_by_id = {
        item.get("note_id"): item
        for item in brief.get("evidence_notes", [])
        if item.get("note_id")
    }

    def evidence_titles(ids):
        rows = []
        for note_id in ids[:5]:
            note = evidence_by_id.get(note_id)
            if not note:
                continue
            rows.append(
                "<li>"
                f"<strong>{_safe_text(note.get('title'))}</strong>"
                f"<span>{_format_count(note.get('likes'))} 赞 · {_safe_text(note.get('topic'))}</span>"
                "</li>"
            )
        return "".join(rows) or "<li><span>暂无可分享证据样本</span></li>"

    insight_html = ""
    for item in strong:
        insight_html += (
            "<section class='card'>"
            f"<p class='eyebrow'>关键洞察</p>"
            f"<h2>{_safe_text(item.get('title'))}</h2>"
            f"<p>{_safe_text(item.get('summary'))}</p>"
            f"<p class='muted'>{_safe_text(item.get('why_it_matters'))}</p>"
            f"<ul class='evidence'>{evidence_titles(item.get('evidence_note_ids', []))}</ul>"
            "</section>"
        )

    action_html = ""
    for action in actions:
        days = "".join(
            f"<li><strong>第 {day.get('day')} 天</strong>{_safe_text(day.get('task'))}<span>{_safe_text(day.get('goal'))}</span></li>"
            for day in action.get("seven_day_plan", [])[:7]
        )
        action_html += (
            "<section class='card'>"
            f"<p class='eyebrow'>行动方案</p>"
            f"<h2>{_safe_text(action.get('title'))}</h2>"
            f"<ol class='plan'>{days}</ol>"
            "</section>"
        )

    warning_items = [_safe_text(w) for w in data_quality.get("warnings", [])]
    warning_items.extend(_safe_text(w.get("title")) for w in weak[:3])
    warnings_html = "".join(f"<li>{w}</li>" for w in warning_items if w)

    quality_text = "通过" if quality.get("passed") else "需复查"
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>{_safe_text(summary.get('nickname'))} - 小红书分析摘要</title>
  <style>
    body {{ margin: 0; background: #f5f5f7; color: #1f2937; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; }}
    main {{ max-width: 920px; margin: 0 auto; padding: 28px 18px 44px; }}
    .hero, .card {{ background: #fff; border: 1px solid #e5e7eb; border-radius: 8px; padding: 22px; margin-bottom: 16px; }}
    .profile {{ display: flex; gap: 16px; align-items: center; margin-bottom: 16px; }}
    .avatar {{ width: 64px; height: 64px; border-radius: 50%; background: #dbeafe; display: grid; place-items: center; color: #1d4ed8; font-size: 28px; font-weight: 700; overflow: hidden; }}
    .avatar img {{ width: 100%; height: 100%; object-fit: cover; }}
    h1 {{ margin: 0; font-size: 28px; line-height: 1.3; letter-spacing: 0; }}
    h2 {{ margin: 6px 0 8px; font-size: 20px; line-height: 1.35; letter-spacing: 0; }}
    p {{ line-height: 1.7; }}
    .muted, .evidence span, .plan span {{ color: #6b7280; }}
    .eyebrow {{ color: #2563eb; font-weight: 700; font-size: 12px; margin: 0 0 6px; }}
    .metrics {{ display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px; margin-top: 16px; }}
    .metric {{ background: #f9fafb; border-radius: 8px; padding: 12px; }}
    .metric span {{ display: block; color: #6b7280; font-size: 12px; }}
    .metric strong {{ display: block; font-size: 20px; margin-top: 4px; }}
    ul, ol {{ padding-left: 22px; }}
    .evidence li, .plan li {{ margin: 8px 0; }}
    .evidence span, .plan span {{ display: block; font-size: 13px; }}
    .footer {{ color: #6b7280; font-size: 12px; margin-top: 20px; }}
    @media (max-width: 680px) {{ .metrics {{ grid-template-columns: 1fr; }} h1 {{ font-size: 23px; }} }}
  </style>
</head>
<body>
  <main>
    <section class="hero">
      <div class="profile">
        <div class="avatar">{f"<img src='{_safe_text(summary.get('avatar_url'))}' alt='' />" if summary.get('avatar_url') else _safe_text((summary.get('nickname') or '账')[:1])}</div>
        <div>
          <h1>{_safe_text(summary.get('nickname') or '未命名账号')}</h1>
          <p class="muted">{_safe_text(summary.get('bio') or summary.get('positioning') or '内容账号分析')}</p>
        </div>
      </div>
      <p class="eyebrow">一句话判断</p>
      <h2>{_safe_text(summary.get('one_sentence'))}</h2>
      <p>{_safe_text(summary.get('positioning'))}</p>
      <div class="metrics">
        <div class="metric"><span>样本数</span><strong>{_format_count(data_quality.get('sample_count'))}</strong></div>
        <div class="metric"><span>数据可信度</span><strong>{_safe_text(summary.get('data_confidence'))}</strong></div>
        <div class="metric"><span>质检</span><strong>{quality_text}</strong></div>
      </div>
    </section>
    {f"<section class='card'><p class='eyebrow'>数据提示</p><ul>{warnings_html}</ul></section>" if warnings_html else ""}
    {insight_html}
    {action_html}
    <p class="footer">由本地小红书分析助手生成。此分享版已做脱敏处理，仅保留适合阅读的结论、证据标题和行动建议。</p>
  </main>
</body>
</html>"""


@router.post("/compare")
async def compare_reports(
    body: dict,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Compare reports from multiple task IDs."""
    task_ids = body.get("task_ids", [])
    if len(task_ids) < 2:
        raise HTTPException(status_code=400, detail=MSG_NEED_TWO_TASKS)

    summaries = []
    for tid in task_ids:
        _get_owned_task(int(tid), db, current_user)
        reports_dir = _reports_dir(int(tid))
        if not reports_dir.exists():
            continue

        profile_card = ""
        for f in reports_dir.glob("00*.md"):
            profile_card = f.read_text(encoding="utf-8")[:500]
            break

        summary = {"task_id": tid, "profile": profile_card, "metrics": {}}

        results_file = Path(f"data/tasks/{tid}/results.json")
        if results_file.exists():
            try:
                results = json.loads(results_file.read_text(encoding="utf-8"))
                p = results.get("profile", {})
                summary["metrics"] = {
                    "avg_likes": p.get("avg_likes", 0),
                    "median_likes": p.get("median_likes", 0),
                    "max_likes": p.get("max_likes", 0),
                    "total_notes": p.get("total_notes", 0),
                }
            except Exception:
                pass

        summaries.append(summary)

    return {"comparison": summaries}


@router.get("/{task_id}")
async def list_reports(
    task_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """List all reports for a completed task."""
    _get_owned_task(task_id, db, current_user)
    reports_dir = _reports_dir(task_id)
    if not reports_dir.exists():
        return {"reports": {}, "message": "No reports found"}

    reports = {}
    for f in sorted(reports_dir.glob("*.md")):
        if f.name == "README.md":
            continue
        reports[f.stem] = f.read_text(encoding="utf-8")

    return {"reports": reports}


@router.get("/{task_id}/brief")
async def get_brief(
    task_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Get structured insight brief for a completed task."""
    _get_owned_task(task_id, db, current_user)
    brief_path = _task_data_dir(task_id) / "insight_brief.json"
    if not brief_path.exists():
        raise HTTPException(status_code=404, detail="Insight brief not found")
    return {"brief": json.loads(brief_path.read_text(encoding="utf-8"))}


@router.get("/{task_id}/quality")
async def get_quality(
    task_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Get report quality check result for a completed task."""
    _get_owned_task(task_id, db, current_user)
    quality_path = _task_data_dir(task_id) / "report_quality_check.json"
    if not quality_path.exists():
        raise HTTPException(status_code=404, detail="Report quality check not found")
    return {"quality": json.loads(quality_path.read_text(encoding="utf-8"))}


@router.get("/{task_id}/share")
async def export_share_report(
    task_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Download a sanitized HTML report for sharing."""
    _get_owned_task(task_id, db, current_user)
    data_dir = _task_data_dir(task_id)
    brief_path = data_dir / "insight_brief.json"
    if not brief_path.exists():
        raise HTTPException(status_code=404, detail="Insight brief not found")
    quality_path = data_dir / "report_quality_check.json"
    brief = json.loads(brief_path.read_text(encoding="utf-8"))
    quality = {}
    if quality_path.exists():
        quality = json.loads(quality_path.read_text(encoding="utf-8"))

    html_body = _share_html(task_id, brief, quality)
    buf = BytesIO(html_body.encode("utf-8"))
    return StreamingResponse(
        buf,
        media_type="text/html; charset=utf-8",
        headers={"Content-Disposition": f"attachment; filename=xhs_share_report_{task_id}.html"},
    )


@router.get("/{task_id}/export")
async def export_reports(
    task_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Download all reports as a zip file."""
    _get_owned_task(task_id, db, current_user)
    reports_dir = _reports_dir(task_id)
    if not reports_dir.exists():
        raise HTTPException(status_code=404, detail="No reports found")

    buf = BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for f in reports_dir.glob("*.md"):
            zf.writestr(f.name, f.read_text(encoding="utf-8"))

    buf.seek(0)
    return StreamingResponse(
        buf,
        media_type="application/zip",
        headers={"Content-Disposition": f"attachment; filename=reports_{task_id}.zip"},
    )


@router.get("/{task_id}/{report_type}")
async def get_report(
    task_id: int,
    report_type: str,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Get a specific report by task_id and report type."""
    _get_owned_task(task_id, db, current_user)
    reports_dir = _reports_dir(task_id)
    if not reports_dir.exists():
        raise HTTPException(status_code=404, detail=MSG_REPORTS_NOT_FOUND)

    for f in reports_dir.glob("*.md"):
        if f.name == "README.md":
            continue
        if f.stem == report_type or f.stem.endswith(report_type) or report_type.endswith(f.stem):
            return {"report_type": f.stem, "markdown_body": f.read_text(encoding="utf-8")}

    raise HTTPException(status_code=404, detail=f"Report '{report_type}' not found")
