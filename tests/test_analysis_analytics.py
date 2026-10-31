import unittest

from backend.services.analysis_analytics import build_report_analytics


def evidence_row(index, title, note_type, tags, likes, collected, comments, shares):
    return {
        "note_id": f"note-{index}",
        "title": title,
        "note_url": f"https://www.xiaohongshu.com/explore/note-{index}",
        "type": note_type,
        "published_at": f"2026-10-{index + 1:02d}T10:00:00+08:00",
        "tags": tags,
        "metrics": {
            "liked_count": likes,
            "collected_count": collected,
            "comment_count": comments,
            "share_count": shares,
        },
    }


class AnalysisAnalyticsTests(unittest.TestCase):
    def setUp(self):
        self.rows = [
            evidence_row(0, "周末手机摄影的3个步骤", "图文", ["手机摄影"], 80, 40, 10, 5),
            evidence_row(1, "手机摄影怎么拍才自然", "图文", ["手机摄影"], 40, 22, 6, 2),
            evidence_row(2, "这个周末怎么安排", "图文", ["周末"], 12, 3, 1, 0),
            evidence_row(3, "周末出行清单", "图文", ["周末"], 10, 2, 0, 0),
            evidence_row(4, "旧手机拍晚霞", "图文", ["手机摄影"], 20, 8, 2, 1),
            evidence_row(5, "冷涡天的视频记录", "视频", ["天气"], 5, 1, 0, 0),
        ]

    def test_public_engagement_metrics_and_concentration(self):
        result = build_report_analytics(self.rows)
        self.assertEqual(result["notes"], 6)
        self.assertEqual(result["total_engagement"], 270)
        self.assertEqual(result["metric_totals"]["liked_count"], 167)
        self.assertEqual(result["concentration"]["top_20pct_count"], 2)
        self.assertEqual(result["top_notes"][0]["note_id"], "note-0")
        self.assertEqual(result["top_notes"][0]["engagement"], 135)
        self.assertIn("不是浏览量", result["metric_basis"])

    def test_types_tags_and_title_signals_have_sample_context(self):
        result = build_report_analytics(self.rows)
        types = {item["type"]: item for item in result["types"]}
        self.assertEqual(types["图文"]["notes"], 5)
        self.assertEqual(types["视频"]["notes"], 1)
        title = next(item for item in result["title_signals"] if item["label"] == "数字具体")
        self.assertEqual(title["matched_notes"], 1)
        self.assertFalse(title["reliable"])
        self.assertEqual(result["tags"][0]["tag"], "手机摄影")
        self.assertEqual(result["tags"][0]["notes"], 3)
        self.assertEqual(len(result["story_cards"]), 3)

    def test_group_with_missing_metrics_keeps_known_totals(self):
        row = evidence_row(9, "缺少数值", "图文", [], 10, None, None, None)
        result = build_report_analytics([row])
        self.assertEqual(result["total_engagement"], 10)
        self.assertEqual(result["metric_totals"]["collected_count"], 0)
        self.assertEqual(result["median_engagement"], 10.0)


if __name__ == "__main__":
    unittest.main()
