import ssl
import unittest

import certifi

from backend.services import collector  # noqa: F401


class CollectorSslCompatibilityTests(unittest.TestCase):
    def test_patched_default_context_accepts_standard_arguments(self):
        context = ssl.create_default_context(cafile=certifi.where())
        self.assertEqual(context.maximum_version, ssl.TLSVersion.TLSv1_2)


if __name__ == "__main__":
    unittest.main()
