import json
import tempfile
import unittest
from pathlib import Path

from backend.services.collector import Collector
from backend.services.delivery import REPORT_ORDER, build_delivery_html, delivery_status, markdown_to_html
from backend.services.report_quality import _check_dimension_reliability, _check_report_files


class DeliveryTests(unittest.TestCase):
    def test_markdown_renderer_escapes_customer_content(self):
        rendered = markdown_to_html("# 标题\n\n<script>alert(1)</script>\n\n| A | B |\n|---|---|\n| 1 | 2 |")
        self.assertNotIn("<script>", rendered)
        self.assertIn("&lt;script&gt;", rendered)
        self.assertIn("<table>", rendered)

    def test_ready_delivery_contains_customer_eight_dimensions_and_appendix(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            task_dir = root / "task"
            reports_dir = root / "reports"
            task_dir.mkdir()
            reports_dir.mkdir()
            (task_dir / "results.json").write_text(
                json.dumps({"profile": {"nickname": "测试账号", "total_notes": 80}}, ensure_ascii=False),
                encoding="utf-8",
            )
            (task_dir / "data_quality.json").write_text(
                json.dumps({
                    "content_analysis_ready": True,
                    "tag_analysis_ready": True,
                    "comment_analysis_ready": True,
                    "media_analysis_ready": True,
                    "search_analysis_ready": True,
                    "content_sample_count": 20,
                    "tag_sample_count": 20,
                    "comment_sample_count": 40,
                    "comment_note_count": 8,
                    "media_sample_count": 15,
                    "search_keyword_count": 4,
                    "topic_unclassified_pct": 20,
                }),
                encoding="utf-8",
            )
            (task_dir / "insight_brief.json").write_text(
                json.dumps({"account_summary": {"nickname": "测试账号", "one_sentence": "结论"}}, ensure_ascii=False),
                encoding="utf-8",
            )
            (task_dir / "report_quality_check.json").write_text(
                json.dumps({"passed": True, "score": 100}), encoding="utf-8"
            )
            for filename, label in REPORT_ORDER:
                (reports_dir / filename).write_text(f"# {label}\n\n正文", encoding="utf-8")

            status = delivery_status(task_dir, reports_dir)
            output = build_delivery_html(1, task_dir, reports_dir)
            self.assertTrue(status["ready"])
            self.assertEqual(output.count('class="dimension-section'), 8)
            self.assertEqual(output.count("<details>"), len(REPORT_ORDER))
            self.assertIn("先看结论", output)
            self.assertIn("为什么这么判断", output)
            self.assertIn("7 天最小行动计划", output)
            self.assertIn("数据说明与研究底稿", output)
            self.assertIn("测试账号", output)

    def test_customer_report_does_not_invent_commercial_success_when_no_signal_exists(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            task_dir = root / "task"
            reports_dir = root / "reports"
            task_dir.mkdir()
            reports_dir.mkdir()
            results = {
                "profile": {"nickname": "零商业信号账号", "total_notes": 50},
                "commercial": {"detected_count": 0, "detected_pct": 0, "comparison_ready": False},
                "eight_dimensions": {
                    "commercial_signals": {
                        "status": "limited",
                        "confidence": "low",
                        "sample_count": 0,
                        "sources": ["公开标题与正文"],
                        "findings": [],
                        "evidence_note_ids": [],
                        "limits": ["不推断真实商单或收入"],
                    }
                },
            }
            (task_dir / "results.json").write_text(json.dumps(results, ensure_ascii=False), encoding="utf-8")
            (task_dir / "insight_brief.json").write_text(
                json.dumps(
                    {"account_summary": {"nickname": "零商业信号账号"}, "eight_dimensions": results["eight_dimensions"]},
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            for filename, label in REPORT_ORDER:
                (reports_dir / filename).write_text(f"# {label}\n\n正文", encoding="utf-8")
            output = build_delivery_html(2, task_dir, reports_dir)
            self.assertIn("本次未发现足够的公开商业表达", output)
            self.assertIn("这不等于账号没有合作或变现", output)
            self.assertNotIn("商业化成功", output)

    def test_unsupported_claim_blocks_quality(self):
        with tempfile.TemporaryDirectory() as temp:
            reports_dir = Path(temp)
            for filename, _ in REPORT_ORDER:
                (reports_dir / filename).write_text("# 正常报告", encoding="utf-8")
            (reports_dir / REPORT_ORDER[3][0]).write_text("深度内容更易引爆", encoding="utf-8")
            issues = _check_report_files(reports_dir)
            self.assertTrue(any(item["code"] == "unsupported_report_claim" for item in issues))

    def test_unreliable_topics_cannot_drive_ready_action_plan(self):
        issues = _check_dimension_reliability(
            {"topic_unclassified_pct": 53, "tag_analysis_ready": False},
            {
                "eight_dimensions": {
                    "positioning_audience": {"status": "limited", "confidence": "low"},
                    "content_structure": {"status": "limited", "confidence": "low"},
                    "action_plan": {"status": "ready", "confidence": "medium"},
                    "tag_search": {"status": "limited", "confidence": "medium"},
                }
            },
        )
        codes = {item["code"] for item in issues}
        self.assertIn("unreliable_topic_used_by_dimension", codes)
        self.assertIn("tag_search_overconfident", codes)

    def test_detail_selection_fills_balanced_sample(self):
        notes = [
            {"note_id": f"{1700000000 + index:08x}{index:016x}", "liked_count": index}
            for index in range(60)
        ]
        results = {"topic_distribution": {"主题A": {"note_ids": [notes[20]["note_id"]]}}}
        selected = Collector()._select_detail_note_ids(notes, results, 30)
        likes = {note["note_id"]: note["liked_count"] for note in notes}
        selected_likes = [likes[note_id] for note_id in selected]
        self.assertEqual(len(selected), 30)
        self.assertGreaterEqual(max(selected_likes), 55)
        self.assertLessEqual(min(selected_likes), 5)
        self.assertTrue(any(25 <= value <= 35 for value in selected_likes))


if __name__ == "__main__":
    unittest.main()
