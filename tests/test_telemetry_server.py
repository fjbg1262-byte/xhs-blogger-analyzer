import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from pydantic import ValidationError

from telemetry_server import app as telemetry_app


class TelemetryServerTests(unittest.TestCase):
    def test_extra_top_level_fields_are_rejected(self):
        with self.assertRaises(ValidationError):
            telemetry_app.EventIn(
                install_id="a" * 32,
                app_version="test",
                event_name="app_started",
                properties={},
                occurred_at="2026-01-01T00:00:00+00:00",
                cookie="secret",
            )

    def test_server_filters_event_properties_before_storage(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            database = Path(temp_dir) / "telemetry.db"
            with patch.object(telemetry_app, "DATABASE_PATH", database):
                telemetry_app._init_db()
                event = telemetry_app.EventIn(
                    install_id="b" * 32,
                    app_version="test",
                    event_name="analysis_failed",
                    properties={
                        "task_type": "full_analysis",
                        "error_code": "dependency_missing",
                        "stage": "collect",
                        "cookie": "secret",
                        "profile_url": "private",
                    },
                    occurred_at="2026-01-01T00:00:00+00:00",
                )
                telemetry_app.ingest_event(event, x_ingest_key="")

                with telemetry_app._database() as connection:
                    stored = connection.execute(
                        "SELECT properties_json FROM events"
                    ).fetchone()
                self.assertEqual(
                    json.loads(stored["properties_json"]),
                    {
                        "task_type": "full_analysis",
                        "error_code": "dependency_missing",
                        "stage": "collect",
                    },
                )


if __name__ == "__main__":
    unittest.main()
