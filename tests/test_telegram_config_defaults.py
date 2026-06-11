import unittest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))

from run import ensure_push_config_defaults


class TelegramConfigDefaultsTest(unittest.TestCase):
    def test_legacy_telegram_credentials_remain_enabled(self):
        data = {
            "push_config": {
                "TG_BOT_TOKEN": "token",
                "TG_USER_ID": "42",
            }
        }

        push_config = ensure_push_config_defaults(data)

        self.assertEqual(push_config["TG_ENABLED"], "enabled")

    def test_new_telegram_config_defaults_to_disabled(self):
        data = {"push_config": {}}

        push_config = ensure_push_config_defaults(data)

        self.assertEqual(push_config["TG_ENABLED"], "disabled")

    def test_telegram_inbox_auto_create_defaults_to_disabled(self):
        data = {"push_config": {"TG_BOT_TOKEN": "token", "TG_USER_ID": "42"}}

        push_config = ensure_push_config_defaults(data)

        self.assertEqual(push_config["TG_INBOX_AUTO_CREATE"], "disabled")
        self.assertEqual(push_config["TG_INBOX_LAST_UPDATE_ID"], 0)


if __name__ == "__main__":
    unittest.main()
