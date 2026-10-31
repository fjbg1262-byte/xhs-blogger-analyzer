"""Build customer-ready, self-contained report deliverables."""

import html
import json
import os
import re
import shutil
import subprocess
import tempfile
import zipfile
from io import BytesIO
from pathlib import Path
from typing import Any

from backend.services.customer_report import build_customer_report_html


REPORT_ORDER = [
    ("00_博主画像卡片.md", "账号定位与基础盘"),
    ("01_内容结构分析.md", "内容结构与主题"),
    ("02_标题与文案分析.md", "标题、正文与钩子"),
    ("03_互动归因分析.md", "公开点赞表现"),
    ("04_成长轨迹分析.md", "发布与表现轨迹"),
    ("05_标签与SEO分析.md", "标签与搜索表达"),
    ("06_商业化分析.md", "商业化信号"),
    ("07_竞争定位分析.md", "内容坐标与竞争假设"),
    ("08_策略建议与行动计划.md", "7 天行动计划"),
]

FOCUS_OPTIONS = {
    "growth": "涨粉与内容增长",
    "positioning": "账号定位",
    "content": "选题与内容结构",
    "commercial": "商业化",
    "overall": "综合诊断",
}


def _read_json(path: Path, default: Any):
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def load_context(task_dir: Path) -> dict:
    context = _read_json(task_dir / "delivery_context.json", {})
    focus = context.get("focus", "overall")
    if focus not in FOCUS_OPTIONS:
        focus = "overall"
    return {
        "focus": focus,
        "focus_label": FOCUS_OPTIONS[focus],
        "buyer_question": str(context.get("buyer_question", ""))[:300].strip(),
        "seller_note": str(context.get("seller_note", ""))[:500].strip(),
    }


def save_context(task_dir: Path, payload: dict) -> dict:
    context = {
        "focus": payload.get("focus", "overall"),
        "buyer_question": payload.get("buyer_question", ""),
        "seller_note": payload.get("seller_note", ""),
    }
    normalized = load_context_from_data(context)
    task_dir.mkdir(parents=True, exist_ok=True)
    (task_dir / "delivery_context.json").write_text(
        json.dumps(normalized, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return normalized


def load_context_from_data(context: dict) -> dict:
    focus = context.get("focus", "overall")
    if focus not in FOCUS_OPTIONS:
        focus = "overall"
    return {
        "focus": focus,
        "focus_label": FOCUS_OPTIONS[focus],
        "buyer_question": str(context.get("buyer_question", ""))[:300].strip(),
        "seller_note": str(context.get("seller_note", ""))[:500].strip(),
    }


def delivery_status(task_dir: Path, reports_dir: Path) -> dict:
    quality = _read_json(task_dir / "report_quality_check.json", {})
    results = _read_json(task_dir / "results.json", {})
    data_quality = _read_json(task_dir / "data_quality.json", {}) or results.get("data_quality", {})
    profile = results.get("profile", {})
    missing = [name for name, _ in REPORT_ORDER if not (reports_dir / name).exists()]
    blockers = []
    if profile.get("total_notes", 0) < 30:
        blockers.append("公开笔记样本少于 30 篇，暂不适合按完整账号报告交付。")
    if not quality.get("passed"):
        blockers.append("报告语义质检未通过，请先处理阻断问题。")
    if missing:
        blockers.append("缺少报告模块：" + "、".join(missing))
    if not data_quality.get("content_analysis_ready", False):
        blockers.append("正文分层样本未达到交付门槛，请先补充完整公开数据。")
    if not data_quality.get("tag_analysis_ready", False):
        blockers.append("标签分层样本未达到交付门槛，请先补充完整公开数据。")
    if not data_quality.get("comment_analysis_ready", False):
        blockers.append("代表评论样本未达到交付门槛，受众和互动归因只能降级。")
    if not data_quality.get("media_analysis_ready", False):
        blockers.append("图片或视频详情样本未达到交付门槛，媒体结构只能降级。")
    if not data_quality.get("search_analysis_ready", False):
        blockers.append("关键词联想或公开搜索样本未达到交付门槛，搜索表达只能降级。")

    ai = results.get("ai_enhancement") or {}

    modules = [
        {"name": "账号定位", "status": "ready" if data_quality.get("topic_unclassified_pct", 100) <= 35 else "limited", "note": "基于公开内容主题与主页信息"},
        {"name": "内容结构", "status": "ready", "note": f"基于 {profile.get('total_notes', 0)} 篇公开笔记"},
        {"name": "标题与正文", "status": "ready" if data_quality.get("content_analysis_ready") else "blocked", "note": f"有效正文 {data_quality.get('content_sample_count', 0)} 篇"},
        {"name": "互动归因", "status": "ready" if data_quality.get("comment_analysis_ready") else "blocked", "note": f"代表评论 {data_quality.get('comment_sample_count', 0)} 条 / {data_quality.get('comment_note_count', 0)} 篇"},
        {"name": "发布轨迹", "status": "ready", "note": "不等同于粉丝或曝光增长"},
        {"name": "标签与搜索", "status": "ready" if data_quality.get("tag_analysis_ready") and data_quality.get("search_analysis_ready") else "blocked", "note": f"有效标签 {data_quality.get('tag_sample_count', 0)} 篇，关键词 {data_quality.get('search_keyword_count', 0)} 个"},
        {"name": "媒体结构", "status": "ready" if data_quality.get("media_analysis_ready") else "blocked", "note": f"图片/视频详情 {data_quality.get('media_sample_count', 0)} 篇"},
        {"name": "商业化", "status": "limited", "note": "仅识别公开商业信号，不推断收入"},
        {"name": "行动建议", "status": "ready", "note": "每条建议绑定公开样本与验证方式"},
        {"name": "AI 增强", "status": "ready" if ai.get("enabled") else "limited", "note": (f"{ai.get('model', '')}，含视觉样本" if ai.get("enabled") and ai.get("multimodal") else "未启用时使用结构化规则分析")},
    ]
    return {
        "ready": not blockers,
        "status": "ready" if not blockers else "needs_work",
        "blockers": blockers,
        "modules": modules,
        "sample_count": profile.get("total_notes", 0),
        "content_sample_count": data_quality.get("content_sample_count", 0),
        "tag_sample_count": data_quality.get("tag_sample_count", 0),
        "comment_sample_count": data_quality.get("comment_sample_count", 0),
        "media_sample_count": data_quality.get("media_sample_count", 0),
        "search_keyword_count": data_quality.get("search_keyword_count", 0),
        "ai_enabled": bool(ai.get("enabled")),
        "quality_score": quality.get("score"),
    }


def _inline(text: str) -> str:
    value = html.escape(text, quote=True)
    value = re.sub(r"`([^`]+)`", r"<code>\1</code>", value)
    value = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", value)
    return value


def markdown_to_html(markdown: str) -> str:
    """Render the limited Markdown emitted by this project without remote dependencies."""
    lines = markdown.replace("\r\n", "\n").split("\n")
    output = []
    index = 0
    in_code = False
    code_lines = []
    while index < len(lines):
        line = lines[index]
        if line.strip().startswith("```"):
            if in_code:
                output.append("<pre><code>%s</code></pre>" % html.escape("\n".join(code_lines)))
                code_lines = []
            in_code = not in_code
            index += 1
            continue
        if in_code:
            code_lines.append(line)
            index += 1
            continue
        if line.startswith("|") and index + 1 < len(lines) and re.match(r"^\|[\s:|-]+\|$", lines[index + 1]):
            headers = [cell.strip() for cell in line.strip("|").split("|")]
            index += 2
            rows = []
            while index < len(lines) and lines[index].startswith("|"):
                rows.append([cell.strip() for cell in lines[index].strip("|").split("|")])
                index += 1
            head = "".join(f"<th>{_inline(cell)}</th>" for cell in headers)
            body = "".join("<tr>" + "".join(f"<td>{_inline(cell)}</td>" for cell in row) + "</tr>" for row in rows)
            output.append(f"<div class='table-wrap'><table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table></div>")
            continue
        heading = re.match(r"^(#{1,4})\s+(.+)$", line)
        if heading:
            level = min(len(heading.group(1)) + 1, 5)
            output.append(f"<h{level}>{_inline(heading.group(2))}</h{level}>")
        elif re.match(r"^[-*]\s+", line):
            items = []
            while index < len(lines) and re.match(r"^[-*]\s+", lines[index]):
                items.append(re.sub(r"^[-*]\s+", "", lines[index]))
                index += 1
            output.append("<ul>" + "".join(f"<li>{_inline(item)}</li>" for item in items) + "</ul>")
            continue
        elif re.match(r"^\d+\.\s+", line):
            items = []
            while index < len(lines) and re.match(r"^\d+\.\s+", lines[index]):
                items.append(re.sub(r"^\d+\.\s+", "", lines[index]))
                index += 1
            output.append("<ol>" + "".join(f"<li>{_inline(item)}</li>" for item in items) + "</ol>")
            continue
        elif line.startswith("> "):
            output.append(f"<blockquote>{_inline(line[2:])}</blockquote>")
        elif line.strip():
            output.append(f"<p>{_inline(line.strip())}</p>")
        index += 1
    if in_code and code_lines:
        output.append("<pre><code>%s</code></pre>" % html.escape("\n".join(code_lines)))
    return "\n".join(output)


def build_delivery_html(task_id: int, task_dir: Path, reports_dir: Path) -> str:
    brief = _read_json(task_dir / "insight_brief.json", {})
    results = _read_json(task_dir / "results.json", {})
    status = delivery_status(task_dir, reports_dir)
    context = load_context(task_dir)
    sections = []
    for filename, label in REPORT_ORDER:
        path = reports_dir / filename
        body = markdown_to_html(path.read_text(encoding="utf-8")) if path.exists() else "<p>本模块未生成。</p>"
        sections.append((label, body))
    return build_customer_report_html(task_id, brief, results, status, context, sections)


def _find_browser() -> str:
    candidates = [
        os.path.join(os.environ.get("PROGRAMFILES(X86)", ""), "Microsoft", "Edge", "Application", "msedge.exe"),
        os.path.join(os.environ.get("PROGRAMFILES", ""), "Microsoft", "Edge", "Application", "msedge.exe"),
        os.path.join(os.environ.get("PROGRAMFILES", ""), "Google", "Chrome", "Application", "chrome.exe"),
        "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    ]
    for candidate in candidates:
        if candidate and Path(candidate).exists():
            return candidate
    for name in ("msedge", "chrome", "google-chrome"):
        found = shutil.which(name)
        if found:
            return found
    return ""


def render_pdf(html_path: Path, pdf_path: Path) -> Path:
    browser = _find_browser()
    if not browser:
        raise RuntimeError("未找到 Edge 或 Chrome，无法自动生成 PDF。")
    pdf_path.parent.mkdir(parents=True, exist_ok=True)
    browser_output = pdf_path.parent / ".xhs-report-output.pdf"
    if browser_output.exists():
        browser_output.unlink()
    logs = []
    for headless_flag in ("--headless=new", "--headless"):
        with tempfile.TemporaryDirectory(prefix="xhs-report-browser-") as user_data:
            command = [
                browser,
                headless_flag,
                "--disable-gpu",
                "--disable-dev-shm-usage",
                "--disable-extensions",
                "--disable-features=Vulkan,CanvasOopRasterization",
                "--no-pdf-header-footer",
                f"--user-data-dir={user_data}",
                f"--print-to-pdf={browser_output.resolve()}",
                html_path.resolve().as_uri(),
            ]
            completed = subprocess.run(
                command,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=90,
                check=False,
            )
            logs.append(completed.stderr or completed.stdout or f"exit={completed.returncode}")
            if browser_output.exists() and browser_output.stat().st_size >= 1000:
                browser_output.replace(pdf_path)
                break
    if not pdf_path.exists() or pdf_path.stat().st_size < 1000:
        raise RuntimeError("PDF 生成失败：" + logs[-1][-500:])
    return pdf_path


def build_delivery_files(task_id: int, task_dir: Path, reports_dir: Path, output_dir: Path) -> dict:
    status = delivery_status(task_dir, reports_dir)
    if not status["ready"]:
        raise ValueError("当前报告未达到客户交付门槛：" + "；".join(status["blockers"]))
    output_dir.mkdir(parents=True, exist_ok=True)
    brief = _read_json(task_dir / "insight_brief.json", {})
    nickname = re.sub(r"[^\w\u4e00-\u9fff-]+", "_", str(brief.get("account_summary", {}).get("nickname") or f"task_{task_id}"))
    html_path = output_dir / f"{nickname}_8维账号内容诊断报告.html"
    pdf_path = output_dir / f"{nickname}_8维账号内容诊断报告.pdf"
    html_path.write_text(build_delivery_html(task_id, task_dir, reports_dir), encoding="utf-8")
    render_pdf(html_path, pdf_path)
    return {"html": html_path, "pdf": pdf_path, "nickname": nickname}


def build_delivery_zip(task_id: int, task_dir: Path, reports_dir: Path) -> tuple[BytesIO, str]:
    with tempfile.TemporaryDirectory(prefix=f"xhs-delivery-{task_id}-") as temp:
        built = build_delivery_files(task_id, task_dir, reports_dir, Path(temp))
        context = load_context(task_dir)
        guide = """8 维账号内容诊断报告阅读说明\n\n1. 优先打开 PDF，从“先看结论”开始阅读。\n2. 主报告按定位受众、内容结构、标题 Hook、互动归因、成长轨迹、标签搜索、商业信号和行动建议 8 个维度展开。\n3. HTML 是可交互网页版本，双击即可打开；需要复核计算过程时，可展开最后的“研究底稿”。\n4. 报告基于采集时可见的公开内容，不代表平台官方数据，不承诺流量、涨粉、搜索排名或商业结果。\n5. 最有价值的用法是先执行一轮 7 天小样本测试，再带新数据复盘。\n"""
        message = f"您好，您的 8 维账号内容诊断报告已经完成。\n本次重点：{context['focus_label']}\n请优先打开 PDF，从“先看结论”和“行动建议”开始；HTML 版本可以展开查看完整研究依据。建议先执行一轮 7 天测试，再根据新数据复盘。"
        buf = BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as archive:
            archive.write(built["pdf"], built["pdf"].name)
            archive.write(built["html"], built["html"].name)
            archive.writestr("01_报告阅读说明.txt", guide)
            archive.writestr("02_发给客户的话.txt", message)
        buf.seek(0)
        return buf, f"{built['nickname']}_8维账号诊断交付包.zip"
