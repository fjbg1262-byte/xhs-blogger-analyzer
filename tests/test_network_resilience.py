import unittest
from unittest.mock import patch

import requests

from backend.services.collector import (
    Collector,
    _network_failure_message,
    _patched_request,
    _winhttp_proxy_url,
)
from backend.tasks.worker import _friendly_error


class NetworkResilienceTests(unittest.TestCase):
    def test_proxy_fake_ip_gets_actionable_chinese_message(self):
        with patch(
            "backend.services.collector._resolved_xhs_addresses",
            return_value=["198.18.0.36"],
        ):
            message = _network_failure_message(
                "HTTPSConnectionPool: Max retries exceeded with NewConnectionError"
            )
        self.assertIn("代理/VPN", message)
        self.assertIn("保持它正常开启", message)
        self.assertNotIn("HTTPSConnectionPool", message)

    def test_worker_hides_requests_stack_from_customer(self):
        result = _friendly_error(
            RuntimeError(
                "Failed to collect notes: HTTPSConnectionPool: "
                "Max retries exceeded with NewConnectionError"
            )
        )
        self.assertIn("采集网络连接失败", result)
        self.assertNotIn("HTTPSConnectionPool", result)

    def test_stale_proxy_retries_once_without_environment_proxy(self):
        session = requests.Session()
        session.trust_env = True
        response = object()
        with patch("backend.services.collector._auto_proxy_for_url", return_value=""), patch(
                "backend.services.collector._original_request",
                side_effect=[requests.exceptions.ProxyError("proxy down"), response],
            ) as request:
                result = _patched_request(session, "GET", "https://example.test")
        self.assertIs(result, response)
        self.assertTrue(session.trust_env)
        self.assertEqual(request.call_count, 2)
        self.assertEqual(request.call_args_list[1].kwargs["proxies"], {})

    def test_xhs_fake_ip_uses_reachable_winhttp_proxy(self):
        session = requests.Session()
        response = object()
        proxy_url = "http://127.0.0.1:7892"
        with patch(
            "backend.services.collector._auto_proxy_for_url",
            return_value=proxy_url,
        ), patch(
            "backend.services.collector._original_request",
            return_value=response,
        ) as request:
            result = _patched_request(
                session,
                "GET",
                "https://edith.xiaohongshu.com/api/test",
                proxies=None,
            )
        self.assertIs(result, response)
        self.assertEqual(
            request.call_args.kwargs["proxies"],
            {"http": proxy_url, "https": proxy_url},
        )

    def test_winhttp_proxy_is_used_only_when_local_port_is_reachable(self):
        completed = type("Completed", (), {
            "stdout": "Proxy Server(s) : 127.0.0.1:7892",
        })()
        connection = unittest.mock.MagicMock()
        connection.__enter__.return_value = connection
        with patch("backend.services.collector.os.name", "nt"), patch(
            "backend.services.collector.subprocess.run", return_value=completed
        ), patch(
            "backend.services.collector.socket.create_connection", return_value=connection
        ):
            self.assertEqual(_winhttp_proxy_url(), "http://127.0.0.1:7892")

    def test_note_collection_retries_transient_network_errors(self):
        collector = Collector()
        collector._api = object()
        collector._cookies = "a1=test"
        collector._ensure_api = lambda cookies: None
        calls = iter([
            (False, "Max retries exceeded with NewConnectionError", None),
            (True, "", []),
            (False, "profile unavailable", None),
        ])
        collector._call = lambda fn, *args, **kwargs: next(calls)
        with patch("backend.services.collector.time.sleep") as sleep:
            result = collector.collect_all_notes(
                "https://www.xiaohongshu.com/user/profile/u1",
                "a1=test; web_session=test",
            )
        self.assertEqual(result["all_notes"], [])
        sleep.assert_called_once_with(1)


if __name__ == "__main__":
    unittest.main()
