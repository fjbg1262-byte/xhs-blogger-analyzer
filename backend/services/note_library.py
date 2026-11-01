"""Public-note dataset contract and offline exports (no model calls)."""
import csv
import io
import json
import re
from datetime import datetime, timedelta, timezone
from statistics import median
from urllib.parse import urlsplit, urlencode

SCHEMA_VERSION = "1.0"
COLUMNS = [
    ("title", "标题"), ("published_at", "发布时间"), ("liked_count", "点赞数"),
    ("collected_count", "收藏数"), ("comment_count", "评论数"), ("share_count", "分享数"),
    ("type", "内容类型"), ("note_url", "笔记链接"), ("cover_url", "封面链接"),
    ("content_text", "正文"), ("tags", "标签"), ("image_urls", "图片链接"),
    ("video_url", "视频链接"), ("author_nickname", "博主昵称"), ("author_user_id", "博主ID"),
    ("note_id", "笔记ID"), ("sticky", "置顶"), ("detail_status", "详情采集状态"),
    ("text_status", "正文采集情况"), ("tags_status", "标签采集情况"),
    ("missing_fields", "缺失字段"), ("failure_reason", "采集说明"),
    ("collected_at", "采集时间"), ("metric_source", "互动数据来源"),
    ("count_precision", "计数精度"), ("likes_vs_median", "点赞相对中位数"),
    ("list_order", "主页返回顺序"), ("profile_url", "主页链接"),
]
FIELD_LABELS = dict(COLUMNS)
COUNTS = ("liked_count", "collected_count", "comment_count", "share_count")
SHANGHAI = timezone(timedelta(hours=8))


def now_text():
    return datetime.now(SHANGHAI).isoformat(timespec="seconds")


def count_value(value):
    if value is None or isinstance(value, bool):
        return None
    text = str(value).strip().replace(",", "").lower()
    match = re.fullmatch(r"(\d+(?:\.\d+)?)\s*([万亿wk]?)\+?", text)
    if not match:
        return None
    return int(float(match[1]) * {"": 1, "万": 10000, "亿": 100000000, "w": 10000, "k": 1000}[match[2]])


def date_value(value):
    """Use explicit timestamps only. Never infer publication date from note IDs."""
    if not value:
        return None
    try:
        if str(value).replace(".", "", 1).isdigit():
            timestamp = float(value)
            if timestamp > 1e11:
                timestamp /= 1000
            date = datetime.fromtimestamp(timestamp, SHANGHAI)
        else:
            date = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
            date = date.replace(tzinfo=SHANGHAI) if date.tzinfo is None else date.astimezone(SHANGHAI)
        return date.isoformat(timespec="seconds") if date.year >= 2010 else None
    except (ValueError, TypeError, OSError, OverflowError):
        return None


def safe_url(value):
    value = str(value or "").strip()
    try:
        parsed = urlsplit(value)
        return value if parsed.scheme in ("https", "http") and parsed.hostname else ""
    except ValueError:
        return ""


def make_row(item, profile_url, order):
    interact = item.get("interact_info") or {}
    cover = item.get("cover") or {}
    note_id = str(item.get("note_id") or item.get("id") or "")
    user = item.get("user") or {}
    note_url = f"https://www.xiaohongshu.com/explore/{note_id}"
    if item.get("xsec_token"):
        note_url += "?" + urlencode({"xsec_source": item.get("xsec_source") or "pc_user", "xsec_token": str(item["xsec_token"])})
    row = {
        "note_id": note_id, "title": item.get("display_title") or item.get("title") or "",
        "published_at": date_value(item.get("time") or item.get("publish_time")),
        "type": {"video": "视频", "normal": "图文"}.get(item.get("type"), "未知"),
        "note_url": note_url,
        "profile_url": profile_url.split("?")[0],
        "cover_url": safe_url(cover.get("url_default") or cover.get("url_pre") or cover.get("url")),
        "content_text": "", "tags": [], "image_urls": [], "video_url": "",
        "author_user_id": user.get("user_id") or urlsplit(profile_url).path.rstrip("/").split("/")[-1],
        "author_nickname": user.get("nickname") or "",
        "sticky": bool(interact.get("sticky", item.get("sticky", False))),
        "detail_status": "未尝试", "text_status": "未采集", "tags_status": "未采集",
        "failure_reason": "", "collected_at": now_text(), "list_order": order,
        "metric_source": "主页列表", "likes_vs_median": None,
        "count_precision": "缩写换算" if any(re.search(r"[万亿wk+]", str(interact.get(k, "")), re.I) for k in COUNTS) else "接口数值",
    }
    row.update({key: count_value(interact.get(key)) for key in COUNTS})
    update_missing(row)
    return row


def update_missing(row):
    fields = [key for key in (*COUNTS, "published_at", "cover_url") if row.get(key) in (None, "")]
    if row["detail_status"] != "成功":
        fields += ["content_text", "tags"]
    row["missing_fields"] = [FIELD_LABELS[key] for key in fields]


def apply_detail(row, detail):
    row["detail_status"] = "成功"
    row["collected_at"] = now_text()
    for key in ("title", "author_nickname", "author_user_id"):
        if detail.get(key):
            row[key] = detail[key]
    row["content_text"] = detail.get("content_text") or ""
    row["tags"] = detail.get("tags") or []
    row["text_status"] = ("已采集" if row["content_text"] else "原文为空") if detail.get("content_available", True) else "接口未返回"
    row["tags_status"] = ("已采集" if row["tags"] else "无标签") if detail.get("tags_available", True) else "接口未返回"
    row["image_urls"] = list(dict.fromkeys(filter(None, (safe_url(u) for u in detail.get("image_urls", [])))))
    row["cover_url"] = safe_url(detail.get("cover_url")) or row["cover_url"]
    row["video_url"] = safe_url(detail.get("video_url"))
    row["published_at"] = date_value(detail.get("publish_time")) or row["published_at"]
    sources = []
    for key in COUNTS:
        parsed = count_value(detail.get(key))
        if parsed is not None:
            row[key] = parsed
            sources.append(key)
    row["metric_source"] = "笔记详情" if len(sources) == 4 else "详情与列表（未返回的保持空白）"
    if any(re.search(r"[万亿wk+]", str(detail.get(k, "")), re.I) for k in COUNTS):
        row["count_precision"] = "缩写换算"
    elif "liked_count" in sources:
        row["count_precision"] = "接口数值"
    update_missing(row)
    for key, status in (("content_text", "text_status"), ("tags", "tags_status")):
        if row[status] == "接口未返回":
            row["missing_fields"].append(FIELD_LABELS[key])


def finalize(dataset):
    values = [r["liked_count"] for r in dataset["rows"] if r["liked_count"] is not None]
    baseline = median(values) if values else None
    for row in dataset["rows"]:
        row["likes_vs_median"] = round(row["liked_count"] / baseline, 3) if baseline and row["liked_count"] is not None else None
    dataset["summary"] = {
        "note_count": len(dataset["rows"]),
        "detail_success": sum(r["detail_status"] == "成功" for r in dataset["rows"]),
        "likes_median": baseline,
        "known_likes_count": len(values),
    }
    return dataset


def select_rows(dataset, sort="list_order", top=0, q="", after="", before="", above_median=False):
    allowed = {"list_order", "published_at", *COUNTS}
    if sort not in allowed:
        raise ValueError("不支持的排序字段")
    rows = [r for r in dataset["rows"] if (not q or q.lower() in (r["title"] + r["content_text"] + " ".join(r["tags"])).lower())
            and (not after or (r["published_at"] and r["published_at"][:10] >= after))
            and (not before or (r["published_at"] and r["published_at"][:10] <= before))
            and (not above_median or (r["liked_count"] is not None and dataset.get("summary", {}).get("likes_median") is not None and r["liked_count"] >= dataset["summary"]["likes_median"]))]
    known = [r for r in rows if r.get(sort) is not None]
    missing = [r for r in rows if r.get(sort) is None]
    rows = sorted(known, key=lambda r: r[sort], reverse=sort != "list_order") + missing
    return rows[:top] if top else rows


def cell_value(row, key):
    value = row.get(key)
    if isinstance(value, list):
        return "\n".join(map(str, value))
    if isinstance(value, bool):
        return "是" if value else "否"
    return value


def csv_bytes(rows):
    stream = io.StringIO(newline="")
    writer = csv.writer(stream)
    writer.writerow([label for _, label in COLUMNS])
    for row in rows:
        values = []
        for key, _ in COLUMNS:
            value = cell_value(row, key)
            # CSV consumers may execute user-authored strings as formulas.
            if isinstance(value, str) and value.lstrip().startswith(("=", "+", "-", "@")):
                value = "'" + value
            values.append(value)
        writer.writerow(values)
    return stream.getvalue().encode("utf-8-sig")


def xlsx_bytes(dataset, rows, feishu=False):
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font, PatternFill
    from openpyxl.worksheet.table import Table, TableStyleInfo
    from openpyxl.utils import get_column_letter
    wb = Workbook()
    ws = wb.active
    ws.title = "飞书导入" if feishu else "笔记库"
    ws.append([label for _, label in COLUMNS])
    for row in rows:
        values = [cell_value(row, key) for key, _ in COLUMNS]
        ws.append([re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", v) if isinstance(v, str) else v for v in values])
    for line in ws.iter_rows(min_row=2):
        for index, cell in enumerate(line):
            key = COLUMNS[index][0]
            if isinstance(cell.value, str):
                cell.value = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", cell.value)
                cell.data_type = "s"  # Set after value assignment, which auto-detects formulas.
            if key in ("published_at", "collected_at") and cell.value:
                cell.value = datetime.fromisoformat(cell.value).replace(tzinfo=None)
                cell.number_format = "yyyy-mm-dd hh:mm:ss"
            elif key in COUNTS:
                cell.number_format = "#,##0"
            elif key == "likes_vs_median":
                cell.number_format = '0.00"倍"'
            if key in ("note_url", "profile_url", "cover_url", "video_url") and cell.value:
                cell.hyperlink = safe_url(cell.value)
                cell.font = Font(color="176B9B", underline="single")
            cell.alignment = Alignment(vertical="top", wrap_text=True)
    for cell in ws[1]:
        cell.fill = PatternFill("solid", fgColor="173B47")
        cell.font = Font(color="FFFFFF", bold=True)
        cell.alignment = Alignment(wrap_text=True, vertical="center")
    widths = {"title": 40, "content_text": 64, "tags": 28, "image_urls": 42, "failure_reason": 38, "missing_fields": 30}
    for index, (key, _) in enumerate(COLUMNS, 1):
        ws.column_dimensions[get_column_letter(index)].width = widths.get(key, 23 if key.endswith("_at") or key.endswith("_url") else 18)
    ws.freeze_panes = "C2"
    ws.row_dimensions[1].height = 32
    for i in range(2, ws.max_row + 1):
        ws.row_dimensions[i].height = 62
    if rows:
        table = Table(displayName="Notes", ref=f"A1:{get_column_letter(len(COLUMNS))}{ws.max_row}")
        table.tableStyleInfo = TableStyleInfo(name="TableStyleMedium2", showRowStripes=True)
        ws.add_table(table)
    if not feishu:
        info = wb.create_sheet("采集说明")
        notes = [
            ("产品", "小红书内容整理器与 AI 交付 0.3.0-beta.6"),
            ("口径", "主页返回顺序最多100篇；含置顶。不宣称是严格按时间排列的全账号最新100篇。"),
            ("任务状态", dataset.get("status", "")),
            ("停止原因", dataset.get("stop_reason", "")),
            ("采集条数 / 本次导出", f"{len(dataset['rows'])} / {len(rows)}"),
            ("详情成功", dataset.get("summary", {}).get("detail_success", 0)),
            ("去重数量", dataset.get("duplicates", 0)),
            ("缺失值", "空白表示未获取，0表示返回的真实零；没有时间时不从笔记ID推断。"),
            ("点赞相对中位数", "以整批已知点赞（包含0）的中位数为基准；基准为0或未知时留空。"),
            ("媒体", "提供封面、图片和视频链接，不下载媒体、不做OCR/视频转写；链接可能过期。"),
            ("正文", "保留接口原文。Excel单格上限32767字符，超长原文请查看CSV或本地数据JSON。"),
            ("飞书", "下载飞书导入版，在多维表格中导入；链接列不是飞书附件，不是自动同步。"),
            ("时间", "北京时间 UTC+8。"),
            ("来源", dataset.get("profile_url", "")),
        ]
        for values in notes:
            info.append(values)
        info.column_dimensions["A"].width = 26
        info.column_dimensions["B"].width = 95
        for line in info:
            for cell in line:
                cell.alignment = Alignment(wrap_text=True, vertical="top")
            info.row_dimensions[line[0].row].height = 38
    out = io.BytesIO()
    wb.save(out)
    return out.getvalue()


def save_dataset(path, dataset):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(".tmp")
    temp.write_text(json.dumps(finalize(dataset), ensure_ascii=False, indent=2), encoding="utf-8")
    temp.replace(path)
