import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from backend.services import telemetry


class TelemetryPrivacyTests(unittest.TestCase):
    def test_event_properties_use_strict_allowlist(self):
        clean = telemetry.sanitize_properties(
            "analysis_failed",
            {
                "task_type": "full_analysis",
                "duration_ms": 1200,
                "error_code": "dependency_missing",
                "stage": "collect",
                "cookie": "web_session=secret",
                "profile_url": "https://example.test/user/profile/private",
                "nickname": "private",
                "report": "private report body",
                "raw_error": "private traceback",
            },
        )
        self.assertEqual(
            clean,
            {
                "task_type": "full_analysis",
                "duration_ms": 1200,
                "error_code": "dependency_missing",
                "stage": "collect",
            },
        )

    def test_unknown_event_is_rejected(self):
        with self.assertRaises(ValueError):
            telemetry.sanitize_properties("upload_cookie", {"cookie": "secret"})

    def test_error_is_reduced_to_standard_code(self):
        self.assertEqual(
            telemetry.classify_error("No module named execjs"),
            "dependency_missing",
        )
        self.assertEqual(
            telemetry.classify_error("Cookie is unauthorized"),
            "cookie_invalid",
        )

    def test_denied_consent_removes_pending_queue(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "telemetry_preferences.json"
            queue_path = Path(temp_dir) / "telemetry_queue.jsonl"
            queue_path.write_text('{"private":"no"}\n', encoding="utf-8")
            with (
                patch.object(telemetry, "_config_path", return_value=config_path),
                patch.object(telemetry, "_queue_path", return_value=queue_path),
            ):
                telemetry.save_consent("denied")
                self.assertFalse(queue_path.exists())
                self.assertEqual(telemetry.load_preferences()["consent"], "denied")


if __name__ == "__main__":
    unittest.main()
