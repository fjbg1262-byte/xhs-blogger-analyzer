import copy
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import httpx

from backend.config import settings
from backend.routers.llm_config import get_llm_config, set_llm_config
from backend.services.ai_agent import ai_config_status, enhancement_fingerprint
from backend.services.library_analysis import (Analysis, DIMENSIONS, VERSION, build_bundle, fingerprint,
                                              generate_analysis, render_html, validate_analysis)
from backend.services.structured_ai import AIRequestError, generate_json
from backend.tasks import analysis_worker


def sample_dataset(topic="手机摄影"):
    return {"status": "completed", "rows": [
        {"note_id": f"note-{i}", "title": f"{topic}实测记录第{i}篇", "author_nickname": "测试账号（虚拟）",
         "content_text": f"本次{topic}实测先固定条件，再比较两种方法。这里是第{i}篇的实际过程。",
         "tags": [topic], "liked_count": i * 10, "collected_count": None,
         "comment_count": 0, "share_count": None, "published_at": f"2026-09-{i % 28 + 1:02d}",
         "cookie": "must-not-leak", "xsec_token": "must-not-leak"} for i in range(12)]}


def sample_output(bundle):
    note = bundle["notes"][0]
    citation = {"note_id": note["note_id"], "field": "title", "quote": note["title"]}
    finding = {"observation": "样本呈现实测表达", "interpretation": "这可能适合想比较方法的读者，不是真实粉丝画像。",
               "next_step": "先做一篇固定条件的两种方法对照", "alternative_explanation": "互动差异也可能来自发布时间和选题。",
               "evidence": [citation]}
    return {"priority_dimension": "content_structure", "strategy": {
                "content_thesis": "以固定条件做可复现的内容对照，建立清晰的方法感。",
                "repeatable_model": "每篇固定场景、单一变量和前后结果，形成连续实验栏目。",
                "growth_path": "优先测试标题是否改变收藏意图，再观察评论中的具体追问。",
                "primary_risk": "互动差异也可能来自发布时间和选题，不能宣称为标题或方法的因果效果。",
            },
            "dimensions": [
        {"key": key, "status": "limited", "findings": [copy.deepcopy(finding)], "limitation": "仅代表公开文字样本。"} for key in DIMENSIONS],
        "drafts": [{"topic": f"对照实验选题 {i}", "reader_problem": "两种方法不知道如何选择",
                    "titles": [f"第{i}组两种方法对照", f"我如何测试第{i}种方法"], "opening": "这一次先固定条件，再比较差别。",
                    "outline": ["展示实际的测试条件", "分别执行两种方法并记录", "展示差异和未解决的问题"],
                    "evidence": [copy.deepcopy(citation)], "test": "一次只改变一种方法", "check": "记录发布时间和后续互动，观察具体提问"} for i in range(3)]}


CONFIG = {"configured": True, "provider": "openai", "api_url": "https://api.openai.com/v1", "api_key": "secret-key", "model": "gpt-5.4-mini"}


class LibraryAnalysisTests(unittest.TestCase):
    def test_bundle_is_deduplicated_minimized_and_balanced(self):
        dataset = sample_dataset()
        dataset["rows"].append(dataset["rows"][0])
        dataset["rows"][1]["liked_count"] = None
        b = build_bundle(dataset, "为新手准备实测选题")
        self.assertEqual(b["coverage"]["notes"], 12)
        self.assertEqual(b["coverage"]["duplicate_rows_removed"], 1)
        self.assertEqual(b["coverage"]["known_likes"], 11)
        self.assertEqual(b["coverage"]["median_likes"], 60)
        self.assertFalse(set(b["coverage"]["high_group"]["note_ids"]) & set(b["coverage"]["low_group"]["note_ids"]))
        self.assertEqual(b["notes"][0]["metrics"]["liked_count"], 0)
        self.assertIsNone(b["notes"][0]["metrics"]["collected_count"])
        self.assertNotIn("must-not-leak", json.dumps(b))

    def test_body_budget_includes_low_and_high_performers(self):
        data = sample_dataset()
        data["rows"] = [{**data["rows"][0], "note_id": str(i), "liked_count": i} for i in range(100)]
        b = build_bundle(data, "分析内容")
        sent = [n["note_id"] for n in b["notes"] if n["body_excerpt"]]
        self.assertEqual(len(sent), 36)
        self.assertIn("0", sent)
        self.assertIn("99", sent)
        self.assertEqual(b["coverage"]["notes"], 100)

    def test_no_domain_dictionary_and_goal_is_in_generation(self):
        for topic in ("军事历史", "手机摄影", "面包烘焙", "开源软件"):
            dataset = sample_dataset(topic)
            bundle = build_bundle(dataset, "优先改标题，不做商业诊断")
            with patch("backend.services.library_analysis.generate_json", return_value=(sample_output(bundle), {"output_tokens": 99})) as call:
                report = generate_analysis(dataset, bundle["goal"], CONFIG)
            prompt = call.call_args.args[2]
            self.assertIn(topic, prompt)
            self.assertIn(bundle["goal"], prompt)
            self.assertNotIn("topic_clusters", prompt)
            self.assertEqual(report["goal"], bundle["goal"])
            self.assertEqual(report["review"], "pending")
            self.assertEqual(len(report["analysis"]["drafts"]), 3)
            self.assertIn("content_thesis", report["analysis"]["strategy"])
            self.assertEqual(report["analytics"]["notes"], 12)
            self.assertEqual(report["analytics"]["total_engagement"], 660)

    def test_fabricated_quote_unknown_id_and_unseen_body_are_rejected(self):
        bundle = build_bundle(sample_dataset(), "计划三个选题")
        for mutation in ({"quote": "这句话不存在于真实原文"}, {"note_id": "nonexistent"}, {"field": "body_excerpt", "quote": "不在正文里的文字"}):
            output = sample_output(bundle)
            output["dimensions"][0]["findings"][0]["evidence"][0].update(mutation)
            with self.assertRaises(ValueError):
                validate_analysis(output, bundle)

    def test_duplicate_dimensions_titles_and_evidence_rejected(self):
        b = build_bundle(sample_dataset(), "计划三个选题")
        for change in range(3):
            output = sample_output(b)
            if change == 0:
                output["dimensions"][1]["key"] = output["dimensions"][0]["key"]
            elif change == 1:
                output["drafts"][1]["titles"] = output["drafts"][0]["titles"]
            else:
                refs = output["dimensions"][0]["findings"][0]["evidence"]
                refs.append(copy.deepcopy(refs[0]))
            with self.assertRaises(ValueError): validate_analysis(output, b)

    def test_unavailable_has_no_finding_and_priority_is_single_source(self):
        b = build_bundle(sample_dataset(), "计划三个选题")
        output = sample_output(b)
        output["dimensions"][6].update(status="unavailable", findings=[])
        result = validate_analysis(output, b)
        self.assertEqual(result["headline"], result["dimensions"][1]["findings"][0]["next_step"])
        output["priority_dimension"] = "commercial_signals"
        with self.assertRaises(ValueError): validate_analysis(output, b)

    def test_failure_has_one_repair_only(self):
        with patch("backend.services.library_analysis.generate_json", return_value=({}, {})) as call:
            with self.assertRaisesRegex(ValueError, "采集数据和表格未受影响"):
                generate_analysis(sample_dataset(), "计划三个选题", CONFIG)
        self.assertEqual(call.call_count, 2)
        self.assertIn("上次输出未通过", call.call_args_list[1].args[2])

    def test_truncated_output_gets_one_compact_retry(self):
        bundle = build_bundle(sample_dataset(), "计划三个选题")
        with patch("backend.services.library_analysis.generate_json",
                   side_effect=[AIRequestError("模型输出达到 token 上限。", "length"),
                                (sample_output(bundle), {"output_tokens": 99})]) as call:
            report = generate_analysis(sample_dataset(), "计划三个选题", CONFIG)
        self.assertEqual(report["analysis"]["drafts"][0]["topic"], "对照实验选题 0")
        self.assertEqual(call.call_count, 2)
        self.assertIn("token 上限", call.call_args_list[1].args[2])

    def test_large_batch_uses_independent_analysis_and_draft_stages(self):
        dataset = sample_dataset()
        template = dataset["rows"][0]
        for index in range(12, 20):
            dataset["rows"].append({**template, "note_id": f"note-{index}", "title": f"手机摄影实测记录第{index}篇"})
        bundle = build_bundle(dataset, "计划三个选题")
        output = sample_output(bundle)
        dimensions = {
            "priority_dimension": output["priority_dimension"],
            "dimensions": output["dimensions"],
            "strategy": output["strategy"],
        }
        drafts = {"drafts": output["drafts"]}
        with patch("backend.services.library_analysis.generate_json",
                   side_effect=[(dimensions, {"output_tokens": 60}),
                                (drafts, {"output_tokens": 39})]) as call:
            report = generate_analysis(dataset, "计划三个选题", CONFIG)
        self.assertEqual(report["analytics"]["notes"], 20)
        self.assertEqual(call.call_count, 2)
        self.assertIn("只生成分析部分", call.call_args_list[0].args[2])
        self.assertIn("只生成创作草稿", call.call_args_list[1].args[2])

    def test_export_escapes_and_excludes_private_metadata(self):
        b = build_bundle(sample_dataset(), "测试 <script>alert(1)</script>")
        with patch("backend.services.library_analysis.generate_json", return_value=(sample_output(b), {})):
            report = generate_analysis(sample_dataset(), b["goal"], CONFIG)
        report["api_key"] = "PRIVATE_KEY"
        markup = render_html(report)
        self.assertNotIn("<script>", markup)
        self.assertIn("&lt;script&gt;", markup)
        self.assertNotIn("PRIVATE_KEY", markup)
        self.assertIn("待人工复核", markup)
        self.assertIn("公开互动", markup)
        self.assertIn("Top 20%", markup)
        for draft in report["analysis"]["drafts"]:
            for title in draft["titles"]: self.assertIn(title, markup)

    def test_stale_report_and_interrupted_jobs(self):
        with tempfile.TemporaryDirectory() as tmp:
            root, ds = Path(tmp), sample_dataset()
            dataset_hash = fingerprint(ds)
            state = {"status": "ready", "run_id": "r1", "analysis_version": VERSION,
                     "dataset_fingerprint": dataset_hash,
                     "report": {"review": "pending", "version": VERSION,
                                "dataset_fingerprint": dataset_hash}}
            analysis_worker._save(root / "content_analysis.json", state)
            self.assertEqual(analysis_worker.approve(root, ds, "r1")["report"]["review"], "approved")
            ds["rows"][0]["title"] = "内容已变"
            self.assertEqual(analysis_worker.read_state(root, ds)["status"], "stale")
            with self.assertRaises(ValueError): analysis_worker.approve(root, ds, "r1")
            state.update(status="running", dataset_fingerprint=fingerprint(ds))
            analysis_worker._save(root / "content_analysis.json", state)
            self.assertEqual(analysis_worker.read_state(root, ds)["status"], "failed")

    def test_report_generation_version_is_isolated(self):
        with tempfile.TemporaryDirectory() as tmp:
            root, ds = Path(tmp), sample_dataset()
            dataset_hash = fingerprint(ds)
            state = {"status": "ready", "run_id": "old", "analysis_version": "evidence-delivery-1",
                     "dataset_fingerprint": dataset_hash,
                     "report": {"review": "approved", "version": "evidence-delivery-1",
                                "dataset_fingerprint": dataset_hash}}
            analysis_worker._save(root / "content_analysis.json", state)
            current = analysis_worker.read_state(root, ds)
            self.assertEqual(current["status"], "stale")
            self.assertIsNone(current["report"])
            with self.assertRaises(ValueError):
                analysis_worker.approve(root, ds, "old")

    def test_another_live_process_can_own_running_report(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(analysis_worker, "_process_alive", return_value=True):
            root, ds = Path(tmp), sample_dataset()
            state = {
                "status": "running",
                "run_id": "other-process",
                "analysis_version": VERSION,
                "process_id": os.getpid() + 100000,
                "dataset_fingerprint": fingerprint(ds),
                "report": None,
            }
            analysis_worker._save(root / "content_analysis.json", state)
            self.assertEqual(analysis_worker.read_state(root, ds)["status"], "running")

    def test_concurrent_submission_blocked(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(analysis_worker._pool, "submit"):
            try:
                analysis_worker.start_analysis(Path(tmp), sample_dataset(), "计划三个选题", CONFIG, 99)
                with self.assertRaisesRegex(ValueError, "已有 AI"):
                    analysis_worker.start_analysis(Path(tmp), sample_dataset(), "计划三个选题", CONFIG, 99)
            finally:
                analysis_worker._active.pop(99, None)

    def test_config_uses_runtime_data_dir_and_saved_model_wins(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(settings, "data_dir", tmp):
            set_llm_config({"llm_provider": "custom", "llm_api_url": "https://model.example/v1", "llm_model": "chosen-model", "llm_api_key": "test-only"}, {"id": 42})
            self.assertTrue((Path(tmp) / "llm_config.json").exists())
            self.assertEqual(ai_config_status(42)["model"], "chosen-model")
            self.assertEqual(get_llm_config({"id": 42})["model"], "chosen-model")
            self.assertNotIn("api_key", get_llm_config({"id": 42}))
            self.assertNotIn("test", get_llm_config({"id": 42})["api_key_masked"])
            self.assertFalse(ai_config_status(43)["configured"])

    def test_legacy_cache_changes_when_goal_or_content_changes(self):
        a = enhancement_fingerprint({}, [], [], [], {"focus": "标题"})
        b = enhancement_fingerprint({}, [], [], [], {"focus": "选题"})
        self.assertNotEqual(a, b)


class StructuredTransportTests(unittest.TestCase):
    def test_openai_responses_uses_schema_and_no_storage(self):
        response = Mock()
        response.json.return_value = {"status": "completed", "output": [{"content": [{"type": "output_text", "text": '{"ok":true}'}]}], "usage": {"input_tokens": 12}}
        with patch("backend.services.structured_ai.httpx.post", return_value=response) as call:
            value, usage = generate_json(CONFIG, "system", "prompt", Analysis.schema())
        self.assertTrue(value["ok"])
        self.assertTrue(call.call_args.args[0].endswith("/responses"))
        self.assertFalse(call.call_args.kwargs["json"]["store"])
        self.assertTrue(call.call_args.kwargs["json"]["text"]["format"]["strict"])
        self.assertEqual(usage["input_tokens"], 12)

    def test_length_finish_reason_is_classified_for_compact_retry(self):
        response = Mock()
        response.json.return_value = {"choices": [{"finish_reason": "length", "message": {"content": "{}"}}]}
        with patch("backend.services.structured_ai.httpx.post", return_value=response):
            with self.assertRaises(AIRequestError) as caught:
                generate_json({**CONFIG, "provider": "deepseek"}, "s", "p", {})
        self.assertEqual(caught.exception.code, "length")

    def test_auth_failure_is_sanitized_and_not_retried(self):
        response = httpx.Response(401, request=httpx.Request("POST", "https://model.example"), text="SECRET_KEY")
        with patch("backend.services.structured_ai.httpx.post", return_value=response) as call:
            with self.assertRaises(AIRequestError) as caught:
                generate_json(CONFIG, "system", "prompt", {})
        self.assertNotIn("SECRET_KEY", str(caught.exception))
        self.assertEqual(call.call_count, 1)

    def test_refusal_truncation_and_insecure_remote_url_are_errors(self):
        response = Mock()
        for data in ({"status": "incomplete"}, {"status": "completed", "output": []}):
            response.json.return_value = data
            with patch("backend.services.structured_ai.httpx.post", return_value=response):
                with self.assertRaises(AIRequestError): generate_json(CONFIG, "s", "p", {})
        with self.assertRaises(AIRequestError):
            generate_json({**CONFIG, "api_url": "http://remote.example"}, "s", "p", {})
        for url in ("https://user:pass@model.example/v1", "https://model.example/v1?key=secret"):
            with self.assertRaises(AIRequestError):
                generate_json({**CONFIG, "api_url": url}, "s", "p", {})
