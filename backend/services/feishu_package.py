"""Feishu 2.0 package and Excel backup (Phase 4).

One workbook, several clean sheets, no explanation rows mixed into data:

- 账号总览 / 全部笔记 / 图文笔记 / 视频笔记 / 选题清单 / 采集记录 / 导入说明

The note sheets keep the same 28-column contract as the CSV export, so a row
imported into Feishu has exactly the fields the workspace shows.
"""

import io
import re
from datetime import datetime

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

from backend.services.note_library import COLUMNS, COUNTS, cell_value, safe_url

HEADER_FILL = PatternFill("solid", fgColor="28251F")
HEADER_FONT = Font(color="F4ECDF", bold=True, size=10)
BODY_ALIGN = Alignment(vertical="top", wrap_text=True)
DATE_KEYS = ("published_at", "collected_at")
LINK_KEYS = ("note_url", "profile_url", "cover_url", "video_url")

NOTE_WIDTHS = {
    "title": 40,
    "content_text": 64,
    "tags": 28,
    "image_urls": 42,
    "failure_reason": 38,
    "missing_fields": 30,
    "note_url": 46,
    "cover_url": 40,
    "profile_url": 40,
    "video_url": 40,
}
GUIDE_ROWS = [
    ("一句话", "在飞书多维表格新建空白表，按工作表逐张导入；每张表只有表头和数据行。"),
    ("第一步", "打开飞书多维表格，新建一个空白多维表格，命名例如「账号内容库」。"),
    ("第二步", "对每张工作表分别导入：新建数据表 → 导入 Excel → 选择本文件对应工作表 → 勾选首行为表头。"),
    ("第三步", "按下面的字段类型建议调整列类型，再按账号、类型或互动排序。"),
    ("字段类型", "标题/博主昵称/标签=文本；发布时间=日期；点赞数/收藏数/评论数/分享数=数字；正文=多行文本；笔记链接/封面链接/主页链接=超链接。"),
    ("账号总览", "每个账号一行：笔记数、图文/视频数、公开互动、单篇中位数、Top20% 贡献、最近发布与采集时间。"),
    ("全部笔记", "本任务导出的全部笔记；如果导出前用了筛选，这里就是筛选后的结果。"),
    ("图文笔记 / 视频笔记", "从同一批数据按内容类型拆分，字段与全部笔记一致。"),
    ("选题清单", "按公开互动排序的候选选题，含来源笔记与建议角度，状态列为「候选」，可在飞书里改成已排期。"),
    ("采集记录", "本任务的条数、正文成功、失败数和停止原因，用于追溯这一批数据是怎么来的。"),
    ("缺失值", "空白表示未获取，0 表示接口返回的真实零；没有时间时不从笔记 ID 推断。"),
    ("口径", "公开互动 = 点赞 + 收藏 + 评论 + 分享；不是浏览量、曝光量或转化率，也不宣称搜索排名。"),
    ("媒体", "只提供封面、图片和视频链接，不下载媒体、不做 OCR 或视频转写；链接可能过期。"),
    ("正文", "Excel 单格上限 32767 字符，超长正文以接口原文截断为准，可回到本地 JSON 查看。"),
]


def _clean(value):
    return re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", value) if isinstance(value, str) else value


def _write_note_sheet(workbook, title, rows):
    sheet = workbook.create_sheet(title)
    sheet.append([label for _, label in COLUMNS])
    for row in rows:
        sheet.append([_clean(cell_value(row, key)) for key, _ in COLUMNS])
    for line in sheet.iter_rows(min_row=2):
        for index, cell in enumerate(line):
            key = COLUMNS[index][0]
            if isinstance(cell.value, str):
                cell.value = _clean(cell.value)
                cell.data_type = "s"  # after assignment, which auto-detects formulas
            if key in DATE_KEYS and cell.value:
                try:
                    cell.value = datetime.fromisoformat(str(cell.value)).replace(tzinfo=None)
                    cell.number_format = "yyyy-mm-dd hh:mm" if key == "collected_at" else "yyyy-mm-dd"
                except ValueError:
                    cell.value = str(cell.value)
            elif key in COUNTS:
                cell.number_format = "#,##0"
            elif key == "likes_vs_median":
                cell.number_format = '0.00"倍"'
            if key in LINK_KEYS and cell.value:
                link = safe_url(str(cell.value))
                if link:
                    cell.hyperlink = link
                    cell.font = Font(color="176B9B", underline="single")
            cell.alignment = BODY_ALIGN
    for cell in sheet[1]:
        cell.fill = HEADER_FILL
        cell.font = HEADER_FONT
        cell.alignment = Alignment(wrap_text=True, vertical="center")
    for index, (key, _) in enumerate(COLUMNS, 1):
        sheet.column_dimensions[get_column_letter(index)].width = NOTE_WIDTHS.get(
            key, 23 if key.endswith("_at") or key.endswith("_url") else 18
        )
    sheet.freeze_panes = "C2"
    sheet.row_dimensions[1].height = 30
    return sheet


def _write_table_sheet(workbook, title, headers, rows, widths):
    sheet = workbook.create_sheet(title)
    sheet.append(headers)
    for row in rows:
        sheet.append([_clean(value) for value in row])
    for line in sheet.iter_rows(min_row=2):
        for cell in line:
            cell.alignment = BODY_ALIGN
            if isinstance(cell.value, str):
                cell.value = _clean(cell.value)
                cell.data_type = "s"
    for cell in sheet[1]:
        cell.fill = HEADER_FILL
        cell.font = HEADER_FONT
        cell.alignment = Alignment(wrap_text=True, vertical="center")
    for index, width in enumerate(widths, 1):
        sheet.column_dimensions[get_column_letter(index)].width = width
    sheet.freeze_panes = "A2"
    sheet.row_dimensions[1].height = 30
    return sheet


def _overview_rows(card, stats, account, dataset):
    return [[
        account.get("name") or "未命名账号",
        str(account.get("profile_url") or dataset.get("profile_url") or "").split("?")[0],
        stats.get("note_count", 0),
        stats.get("image_count", 0),
        stats.get("video_count", 0),
        stats.get("total_engagement", 0),
        stats.get("median_engagement") or "",
        f"{stats.get('top_share', 0)}%",
        (stats.get("latest_published_at") or "")[:10],
        (card.get("completed_at") or card.get("created_at") or "")[:16],
        card.get("status_label") or "",
    ]]


def _topic_rows(rows, limit=10):
    ranked = sorted(rows, key=lambda row: sum(
        value for value in (row.get(key) for key in COUNTS) if isinstance(value, (int, float))
    ), reverse=True)[:limit]
    topics = []
    for index, row in enumerate(ranked, 1):
        tags = [str(tag) for tag in (row.get("tags") or []) if str(tag).strip()][:3]
        engagement = sum(value for value in (row.get(key) for key in COUNTS) if isinstance(value, (int, float)))
        topics.append([
            index,
            row.get("title") or "未获取标题",
            row.get("note_id") or "",
            row.get("note_url") or "",
            row.get("type") or "",
            engagement,
            " / ".join(tags) if tags else "按原标题改写",
            "候选",
        ])
    return topics


def build_feishu_package(rows, dataset, card, stats, account):
    """Multi-sheet workbook for Feishu import."""
    workbook = Workbook()
    workbook.remove(workbook.active)

    _write_table_sheet(
        workbook, "账号总览",
        ["账号", "主页链接", "笔记数", "图文", "视频", "公开互动", "单篇中位数", "Top20% 贡献", "最近发布", "采集时间", "任务状态"],
        _overview_rows(card, stats, account, dataset),
        [20, 46, 10, 8, 8, 15, 12, 12, 14, 18, 10],
    )
    _write_note_sheet(workbook, "全部笔记", rows)
    _write_note_sheet(workbook, "图文笔记", [row for row in rows if row.get("type") == "图文"])
    _write_note_sheet(workbook, "视频笔记", [row for row in rows if row.get("type") == "视频"])
    _write_table_sheet(
        workbook, "选题清单",
        ["序号", "选题", "来源笔记ID", "笔记链接", "类型", "公开互动", "建议角度", "状态"],
        _topic_rows(rows),
        [6, 40, 26, 44, 8, 12, 30, 8],
    )
    _write_table_sheet(
        workbook, "采集记录",
        ["任务ID", "账号", "目标数量", "实际数量", "正文成功", "未完成", "开始时间", "完成时间", "状态", "未完成原因"],
        [[
            card.get("id"), account.get("name") or "", card.get("target", 0), card.get("note_count", 0),
            card.get("body_count", 0), card.get("failed_count", 0),
            (card.get("started_at") or "")[:16], (card.get("completed_at") or "")[:16],
            card.get("status_label") or "", card.get("reason") or "",
        ]],
        [10, 20, 10, 10, 10, 8, 18, 18, 10, 34],
    )
    _write_table_sheet(workbook, "导入说明", ["项目", "说明"], [list(item) for item in GUIDE_ROWS], [14, 110])

    out = io.BytesIO()
    workbook.save(out)
    return out.getvalue()


def build_excel_backup(rows, dataset, card, stats, account):
    """Excel backup with the note sheet, the account overview and the guide."""
    workbook = Workbook()
    workbook.remove(workbook.active)
    _write_note_sheet(workbook, "笔记库", rows)
    _write_table_sheet(
        workbook, "账号总览",
        ["账号", "主页链接", "笔记数", "图文", "视频", "公开互动", "单篇中位数", "Top20% 贡献", "最近发布", "采集时间", "任务状态"],
        _overview_rows(card, stats, account, dataset),
        [20, 46, 10, 8, 8, 15, 12, 12, 14, 18, 10],
    )
    _write_table_sheet(workbook, "采集说明", ["项目", "说明"], [list(item) for item in GUIDE_ROWS], [14, 110])
    out = io.BytesIO()
    workbook.save(out)
    return out.getvalue()
