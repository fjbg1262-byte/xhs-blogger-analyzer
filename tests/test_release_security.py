import importlib.util
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("release_source", ROOT / "scripts" / "release_source.py")
release_source = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(release_source)


class ReleaseSecurityTests(unittest.TestCase):
    def test_clean_package_is_scanned_and_checksummed(self):
        with tempfile.TemporaryDirectory() as tmp:
            package = Path(tmp)
            (package / "README.md").write_text("# clean release", encoding="utf-8")
            (package / "app.js").write_text("const endpoint = 'https://model.example/v1';", encoding="utf-8")
            count = release_source.scan(package)
            self.assertEqual(count, 2)
            self.assertTrue((package / "checksums.sha256").exists())

    def test_runtime_data_and_secret_like_values_are_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            package = Path(tmp)
            (package / "cookies.json").write_text("{}", encoding="utf-8")
            with self.assertRaisesRegex(RuntimeError, "runtime data"):
                release_source.scan(package)
        for content, expected in (
            ('{"llm_api_key":"private-value-123456"}', "secret-like"),
            ("session=web_session=abcdefghijklmnopqrstuvwxyz123456", "secret-like"),
            ("token=sk-abcdefghijklmnopqrstuvwxyz123456", "secret-like"),
        ):
            with tempfile.TemporaryDirectory() as tmp:
                package = Path(tmp)
                (package / "config.json").write_text(content, encoding="utf-8")
                with self.assertRaisesRegex(RuntimeError, expected):
                    release_source.scan(package)


if __name__ == "__main__":
    unittest.main()
