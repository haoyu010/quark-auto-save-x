import copy
import sys
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "app"
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

from app import run as run_module


class FakeTelegramCache:
    enabled = True

    def __init__(self, config):
        self.config = config

    def index_channels(self, deep=False):
        return {"success": True, "indexed": 0, "channels": 1, "message": "ok"}

    def ensure_fresh(self):
        return None

    def search(self, keyword):
        return []

    def stats(self):
        return {"count": 0, "last_indexed_at": 0}


class TaskSuggestionsRouteTest(unittest.TestCase):
    def setUp(self):
        self.original_config = copy.deepcopy(run_module.config_data)
        run_module.config_data = {
            "webui": {"username": "admin", "password": "admin"},
            "source": {
                "telegram": {
                    "enabled": True,
                    "channels": ["https://t.me/Quark_Movies"],
                    "read_limit": 1,
                    "deep_limit": 1,
                    "cache_ttl_seconds": 60,
                }
            },
        }
        self.client = run_module.app.test_client()
        self.token = run_module.get_login_token()

    def tearDown(self):
        run_module.config_data = self.original_config

    @patch.object(run_module, "TelegramChannelCache", FakeTelegramCache)
    def test_fallback_failure_returns_visible_empty_result_message(self):
        with patch.object(run_module.requests, "get", side_effect=TimeoutError("timeout")):
            response = self.client.get(
                "/task_suggestions",
                query_string={"q": "吞噬星空", "d": "1", "token": self.token},
            )

        payload = response.get_json()

        self.assertTrue(payload["success"])
        self.assertEqual(payload["data"], [])
        self.assertIn("备用搜索失败", payload["message"])
        self.assertIn("Telegram", payload["message"])

    @patch.object(run_module, "TelegramChannelCache", FakeTelegramCache)
    def test_fallback_dict_payload_is_unwrapped_to_result_list(self):
        fallback_response = Mock()
        fallback_response.raise_for_status.return_value = None
        fallback_response.json.return_value = {
            "success": True,
            "data": [{"taskname": "吞噬星空", "shareurl": "https://pan.quark.cn/s/good"}],
        }
        with patch.object(run_module.requests, "get", return_value=fallback_response):
            response = self.client.get(
                "/task_suggestions",
                query_string={"q": "吞噬星空", "d": "1", "token": self.token},
            )

        payload = response.get_json()

        self.assertTrue(payload["success"])
        self.assertEqual(payload["source"], "网络公开")
        self.assertEqual(payload["data"], [{"taskname": "吞噬星空", "shareurl": "https://pan.quark.cn/s/good"}])


if __name__ == "__main__":
    unittest.main()
