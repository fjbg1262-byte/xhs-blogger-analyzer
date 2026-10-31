import csv
import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from openpyxl import load_workbook
from backend.services.library_collector import collect_library
from backend.services.note_library import COLUMNS, apply_detail, count_value, csv_bytes, date_value, finalize, make_row, save_dataset, select_rows, xlsx_bytes

URL = "https://www.xiaohongshu.com/user/profile/testuser01"


def raw(i, likes=0):
    return {"note_id": f"note{i:020d}", "display_title": f"标题{i}", "type": "normal", "interact_info": {"liked_count": likes}}


class FakeCollector:
    def __init__(self, pages, details=None):
        self.pages = list(pages)
        self.details = details or {}
        self._api = self
        self.calls = 0
        self.detail_calls = 0
    def _ensure_api(self, cookies):
        self._cookies = cookies
    def _call(self, fn):
        return fn()
    def get_user_note_info(self, *args):
        self.calls += 1
        page = self.pages.pop(0)
        if isinstance(page, tuple):
            return page
        return True, "", {"data": page}
    def _note_url(self, item):
        return item["note_id"]
    def get_note_detail(self, url, cookies):
        self.detail_calls += 1
        return self.details.get(url, {"ok": True, "content_text": "正文\n第二行", "tags": ["摄影"], "liked_count": 0, "collected_count": 0, "comment_count": 0, "share_count": 0, "publish_time": 1710000000000, "image_urls": []})


class NoteLibraryTests(unittest.TestCase):
    def collect(self, collector, **kwargs):
        return collect_library(URL, "web_session=test; a1=test", lambda *a: None, collector=collector, delay=0, **kwargs)

    def test_limit_is_applied_during_pagination(self):
        c = FakeCollector([{"notes": [raw(i+j) for j in range(30)], "has_more": True, "cursor": str(i)} for i in (0,30,60,90)])
        d = self.collect(c)
        self.assertEqual(len(d["rows"]), 100)
        self.assertEqual(c.calls, 4)
        self.assertEqual(c.detail_calls, 100)
        self.assertEqual(d["status"], "completed")

    def test_last_page_without_cursor_is_not_lost(self):
        c = FakeCollector([{"notes": [raw(1)], "has_more": False}])
        self.assertEqual(len(self.collect(c)["rows"]), 1)

    def test_duplicates_and_stuck_cursor(self):
        c = FakeCollector([{"notes":[raw(1)],"cursor":"a","has_more":True}, {"notes":[raw(1),raw(2)],"cursor":"a","has_more":True}])
        d = self.collect(c)
        self.assertEqual(len(d["rows"]),2)
        self.assertEqual(d["duplicates"],1)
        self.assertEqual(d["status"],"partial")

    def test_transient_page_failure_retries(self):
        c = FakeCollector([(False,"timed out",None), {"notes":[raw(1)],"has_more":False}])
        self.assertEqual(self.collect(c)["status"],"completed")
        self.assertEqual(c.calls,2)

    def test_denied_page_stops_without_retry_or_detail_calls(self):
        c = FakeCollector([(False,"403 Cookie secret-should-not-leak",None)])
        d = self.collect(c)
        self.assertEqual(c.calls,1)
        self.assertEqual(c.detail_calls,0)
        self.assertEqual(d["status"],"failed")
        self.assertNotIn("secret-should-not-leak",str(d))

    def test_partial_page_failure_preserves_rows(self):
        c = FakeCollector([{"notes":[raw(1)],"cursor":"next","has_more":True}, (False,"risk",None)])
        d=self.collect(c)
        self.assertEqual(d["status"],"partial")
        self.assertEqual(len(d["rows"]),1)
        self.assertEqual(c.detail_calls,0)

    def test_detail_failure_preserves_unknown_instead_of_zero(self):
        c=FakeCollector([{"notes":[raw(1,5)],"has_more":False}], {raw(1)["note_id"]:{"ok":False,"reason":"not found"}})
        r=self.collect(c)["rows"][0]
        self.assertEqual(r["liked_count"],5)
        self.assertIsNone(r["comment_count"])
        self.assertEqual(r["detail_status"],"失败")

    def test_three_detail_failures_stop(self):
        items=[raw(i) for i in range(8)]
        c=FakeCollector([{"notes":items,"has_more":False}],{r["note_id"]:{"ok":False} for r in items})
        d=self.collect(c)
        self.assertEqual(c.detail_calls,3)
        self.assertEqual(d["rows"][-1]["detail_status"],"未尝试")

    def test_cancel_and_time_limit(self):
        c=FakeCollector([])
        self.assertEqual(self.collect(c,cancelled=lambda:True)["status"],"cancelled")
        self.assertEqual(c.calls,0)
        self.assertEqual(self.collect(FakeCollector([]),timeout=0)["stop_reason"],"达到任务时间上限")

    def test_blank_zero_and_abbreviations(self):
        for value in (None,"","--","未知",-5):
            self.assertIsNone(count_value(value))
        self.assertEqual(count_value("0"),0)
        self.assertEqual(count_value("1.2万"),12000)
        self.assertEqual(count_value("1,234"),1234)
        self.assertIsNone(date_value("昨天"))
        self.assertIsNone(date_value(0))
        self.assertTrue(date_value(1710000000000).endswith("+08:00"))

    def test_missing_detail_fields_not_empty_source(self):
        row=make_row(raw(1),URL,1)
        apply_detail(row,{"ok":True,"content_available":False,"tags_available":False})
        self.assertEqual(row["text_status"],"接口未返回")
        self.assertIn("正文",row["missing_fields"])

    def test_median_includes_zero_and_ranking_matches_export(self):
        rows=[make_row(raw(i,v),URL,i) for i,v in enumerate([0,10,20,None])]
        d=finalize({"rows":rows})
        self.assertEqual(d["summary"]["likes_median"],10)
        self.assertEqual(d["rows"][2]["likes_vs_median"],2)
        self.assertEqual([r["liked_count"] for r in select_rows(d,"liked_count",above_median=True)],[20,10])
        self.assertIsNone(finalize({"rows":[make_row(raw(1,0),URL,1)]})["rows"][0]["likes_vs_median"])

    def test_exports_preserve_types_text_and_structure(self):
        row=make_row(raw(1,0),URL,1)
        row.update(title='=HYPERLINK("evil")',content_text="中文,\"引号\"\n正文",published_at=date_value(1710000000000))
        d=finalize({"rows":[row]})
        data=list(csv.reader(io.StringIO(csv_bytes([row]).decode("utf-8-sig"))))
        self.assertEqual(len(data[0]),len(COLUMNS))
        self.assertTrue(data[1][0].startswith("'="))
        self.assertEqual(data[1][9],row["content_text"])
        wb=load_workbook(io.BytesIO(xlsx_bytes(d,[row])))
        self.assertEqual(wb.sheetnames,["笔记库","采集说明"])
        self.assertEqual(wb.active["A2"].data_type,"s")
        self.assertEqual(wb.active["C2"].value,0)
        self.assertIsNone(wb.active["D2"].value)
        self.assertEqual(wb.active["B2"].data_type,"d")
        self.assertEqual(wb.active.freeze_panes,"C2")
        self.assertEqual(len(wb.active.tables),1)
        self.assertEqual(load_workbook(io.BytesIO(xlsx_bytes(d,[row],True))).sheetnames,["飞书导入"])

    def test_empty_exports_and_checkpoint(self):
        d=finalize({"rows":[]})
        self.assertEqual(load_workbook(io.BytesIO(xlsx_bytes(d,[]))).active.max_row,1)
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/"dataset.json"
            save_dataset(path,d)
            self.assertTrue(path.exists())
            self.assertFalse(path.with_suffix('.tmp').exists())

    def test_excel_removes_illegal_controls_before_cell_binding(self):
        row=make_row(raw(1),URL,1)
        row['content_text']='正文\x00包含控制符'
        data=finalize({'rows':[row]})
        wb=load_workbook(io.BytesIO(xlsx_bytes(data,[row])))
        self.assertEqual(wb.active['J2'].value,'正文包含控制符')

    def test_note_link_keeps_only_note_access_parameters(self):
        from urllib.parse import parse_qs,urlsplit
        item=dict(raw(1),xsec_token='public+note=reference',cookie='never-export')
        row=make_row(item,URL,1)
        self.assertEqual(parse_qs(urlsplit(row['note_url']).query)['xsec_token'],['public+note=reference'])
        self.assertNotIn('never-export',str(row))


if __name__ == '__main__':
    unittest.main()
