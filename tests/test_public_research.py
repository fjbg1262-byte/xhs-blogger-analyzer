import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from backend.services.ai_agent import AI_DIMENSION_KEYS, build_grounded_ai_enhancement
from backend.services.collector import Collector
from backend.services.insight_brief import build_insight_brief
from backend.services.report_quality import run_report_quality_check
from backend.services.reporter import generate_reports


ROOT = Path(__file__).resolve().parents[1]


class DetailCollector(Collector):
    def __init__(self, payload):
        self.payload = payload
        self._api = object()
        self._cookies = "a1=test"

    def _ensure_api(self, cookies_str):
        self._cookies = cookies_str

    def _call(self, fn, *args, **kwargs):
        return True, "", self.payload


class PublicResearchTests(unittest.TestCase):
    def test_detail_parser_keeps_text_tags_media_video_and_interactions(self):
        payload = {
            "data": {
                "items": [{
                    "note_card": {
                        "title": "测试标题",
                        "desc": "这是完整正文，用于验证详情字段。",
                        "time": 1710000000000,
                        "ip_location": "北京",
                        "tag_list": [{"name": "摄影"}],
                        "interact_info": {
                            "liked_count": "120",
                            "collected_count": "30",
                            "comment_count": "8",
                            "share_count": "5",
                        },
                        "image_list": [{"info_list": [{"url": "https://img.test/1.jpg"}]}],
                        "video": {"media": {"stream": {"h264": [{"master_url": "https://video.test/a.mp4"}]}}},
                        "user": {"user_id": "u1", "nickname": "作者"},
                    }
                }]
            }
        }
        detail = DetailCollector(payload).get_note_detail(
            "https://www.xiaohongshu.com/explore/n1", "a1=test; web_session=test"
        )
        self.assertTrue(detail["ok"])
        self.assertEqual(detail["tags"], ["摄影"])
        self.assertEqual(detail["image_urls"], ["https://img.test/1.jpg"])
        self.assertEqual(detail["video_url"], "https://video.test/a.mp4")
        self.assertEqual(detail["share_count"], "5")

    def test_comment_enrichment_deduplicates_repeated_comment_ids(self):
        class CommentCollector(Collector):
            def get_note_comments(self, note, cookies_input=None, limit=10):
                duplicate = {
                    "note_id": note["note_id"],
                    "comment_id": "same-comment",
                    "parent_comment_id": "",
                    "content": "请问怎么做？",
                    "like_count": 2,
                    "create_time": 1,
                    "user_id": "u1",
                }
                return {"ok": True, "comments": [duplicate, dict(duplicate)]}

        with tempfile.TemporaryDirectory() as temp:
            task_dir = Path(temp)
            note_id = "656000000000000000000001"
            (task_dir / "all_notes.json").write_text(
                json.dumps([{"note_id": note_id, "liked_count": 10}]), encoding="utf-8"
            )
            result = CommentCollector().enrich_comments(task_dir, "a1=test", max_notes=1, delay_seconds=0)
            comments = json.loads((task_dir / "comments.json").read_text(encoding="utf-8"))
            self.assertEqual(result["comment_count"], 1)
            self.assertEqual(len(comments), 1)

    def test_analysis_emits_all_eight_dimensions_with_full_public_samples(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            notes = []
            contents = []
            comments = []
            for index in range(40):
                note_id = f"{1700000000 + index:08x}{index:016x}"
                notes.append({
                    "note_id": note_id,
                    "title": f"北京摄影教程第{index}期，手机也能拍清楚",
                    "liked_count": 100 + index * 5,
                    "type": "video" if index % 4 == 0 else "normal",
                })
                if index < 24:
                    contents.append({
                        "note_id": note_id,
                        "content_text": "今天拆解一个真实摄影场景，先看问题，再给步骤，最后总结可以直接照做的方法。",
                        "tags": ["手机摄影", "摄影教程"],
                        "comment_count": 12,
                        "collected_count": 30 + index,
                        "share_count": 5 + index,
                        "image_urls": [f"https://img.test/{index}.jpg"],
                        "video_url": f"https://video.test/{index}.mp4" if index % 4 == 0 else "",
                    })
            for index in range(35):
                comments.append({
                    "note_id": notes[index % 8]["note_id"],
                    "comment_id": f"c{index}",
                    "content": "请问这个方法新手怎么练习？",
                    "like_count": index,
                    "ip_location": "北京",
                })
            search = {
                "keywords": [{
                    "keyword": "手机摄影",
                    "suggestions": ["手机摄影教程"],
                    "result_count": 1,
                    "results": [{"note_id": "s1", "title": "手机摄影教程", "liked_count": 300}],
                }]
            }
            paths = {}
            for name, value in (("notes", notes), ("contents", contents), ("comments", comments), ("search", search)):
                path = root / f"{name}.json"
                path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")
                paths[name] = path
            output = root / "results.json"
            quality = root / "data_quality.json"
            subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "analyze_all.py"),
                    "--notes", str(paths["notes"]),
                    "--contents", str(paths["contents"]),
                    "--comments", str(paths["comments"]),
                    "--search", str(paths["search"]),
                    "--output", str(output),
                    "--quality-output", str(quality),
                ],
                check=True,
                cwd=ROOT,
                capture_output=True,
                text=True,
            )
            result = json.loads(output.read_text(encoding="utf-8"))
            data_quality = json.loads(quality.read_text(encoding="utf-8"))
            self.assertEqual(set(result["eight_dimensions"]), set(AI_DIMENSION_KEYS))
            self.assertTrue(data_quality["comment_analysis_ready"])
            self.assertTrue(data_quality["media_analysis_ready"])
            self.assertTrue(data_quality["search_analysis_ready"])
            brief_path = root / "insight_brief.json"
            reports_dir = root / "reports"
            quality_path = root / "report_quality_check.json"
            build_insight_brief(output, paths["notes"], brief_path, quality)
            generate_reports(str(output), str(reports_dir))
            report_quality = run_report_quality_check(
                output,
                brief_path,
                quality_path,
                data_quality_path=quality,
                reports_dir=reports_dir,
            )
            self.assertTrue(report_quality["passed"], report_quality["blocking_issues"])
            self.assertTrue(report_quality["checks"]["eight_dimensions_complete"])

    def test_ai_filters_unknown_evidence_ids(self):
        notes = [{"note_id": "n1", "title": "标题", "liked_count": 10}]
        results = {
            "profile": {},
            "data_quality": {},
            "eight_dimensions": {
                key: {"evidence_note_ids": ["n1"]} for key in AI_DIMENSION_KEYS
            },
        }
        response = {
            "dimensions": {
                key: {
                    "summary": "基于样本的判断",
                    "findings": ["可验证发现"],
                    "evidence_note_ids": ["n1", "made-up"],
                    "confidence": "medium",
                    "limits": ["仅代表公开样本"],
                }
                for key in AI_DIMENSION_KEYS
            }
        }
        with patch("backend.services.ai_agent.ai_config_status", return_value={
            "configured": True,
            "provider": "openai",
            "api_key": "test",
            "api_url": "https://api.test/v1",
            "model": "gpt-4o-mini",
        }), patch("backend.services.ai_agent._call_multimodal_json", return_value=json.dumps(response, ensure_ascii=False)):
            enhancement = build_grounded_ai_enhancement(results, notes, [], [], user_id=1)
        self.assertEqual(enhancement["status"], "ready")
        for item in enhancement["dimensions"].values():
            self.assertEqual(item["evidence_note_ids"], ["n1"])


if __name__ == "__main__":
    unittest.main()
