import unittest
from unittest.mock import patch

import notify


class FakeTelegramResponse:
    def __init__(self, payload):
        self.payload = payload

    def json(self):
        return self.payload


class TelegramNotifyTest(unittest.TestCase):
    def test_send_telegram_message_requires_enabled_token_and_chat_id(self):
        ok, message = notify.send_telegram_message(
            "title",
            "body",
            {
                "TG_ENABLED": "enabled",
                "TG_BOT_TOKEN": "",
                "TG_USER_ID": "42",
            },
        )

        self.assertFalse(ok)
        self.assertIn("bot_token", message)

    def test_send_telegram_message_skips_when_disabled(self):
        with patch("notify.requests.post") as post:
            ok, message = notify.send_telegram_message(
                "title",
                "body",
                {
                    "TG_ENABLED": "disabled",
                    "TG_BOT_TOKEN": "token",
                    "TG_USER_ID": "42",
                },
            )

        self.assertFalse(ok)
        self.assertIn("未启用", message)
        post.assert_not_called()

    def test_send_telegram_message_uses_custom_api_host(self):
        with patch("notify.requests.post", return_value=FakeTelegramResponse({"ok": True})) as post:
            ok, message = notify.send_telegram_message(
                "【夸克自动转存】",
                "Telegram 测试通知",
                {
                    "TG_ENABLED": "enabled",
                    "TG_BOT_TOKEN": "token",
                    "TG_USER_ID": "42",
                    "TG_API_HOST": "https://tg.example.com",
                },
            )

        self.assertTrue(ok)
        self.assertEqual(message, "tg 推送成功")
        post.assert_called_once()
        call = post.call_args
        self.assertEqual(call.kwargs["url"], "https://tg.example.com/bottoken/sendMessage")
        self.assertEqual(call.kwargs["params"]["chat_id"], "42")
        self.assertIn("Telegram 测试通知", call.kwargs["params"]["text"])

    def test_send_telegram_message_keeps_legacy_config_enabled_by_default(self):
        with patch("notify.requests.post", return_value=FakeTelegramResponse({"ok": True})) as post:
            ok, _ = notify.send_telegram_message(
                "title",
                "body",
                {
                    "TG_BOT_TOKEN": "token",
                    "TG_USER_ID": "42",
                },
            )

        self.assertTrue(ok)
        post.assert_called_once()


if __name__ == "__main__":
    unittest.main()
