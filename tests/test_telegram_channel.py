import os
import tempfile
import unittest

from app.sdk.telegram_channel import (
    TelegramChannelCache,
    extract_quark_links,
    normalize_channel,
    parse_tme_messages,
)


class TelegramChannelTest(unittest.TestCase):
    def test_normalize_channel_accepts_public_urls_and_handles(self):
        self.assertEqual(normalize_channel("https://t.me/mqte5"), "mqte5")
        self.assertEqual(normalize_channel("https://t.me/s/Quark_Movies"), "Quark_Movies")
        self.assertEqual(normalize_channel("@Quark_Movies"), "Quark_Movies")
        self.assertEqual(normalize_channel("bad url"), "")

    def test_extracts_quark_links_from_text(self):
        text = "Show https://pan.quark.cn/s/abc123?pwd=88 more https://pan.quark.cn/s/def456"

        self.assertEqual(
            extract_quark_links(text),
            ["https://pan.quark.cn/s/abc123?pwd=88", "https://pan.quark.cn/s/def456"],
        )

    def test_parse_tme_messages_extracts_links_text_and_time(self):
        html = """
        <div class="tgme_widget_message js-widget_message" data-post="mqte5/42">
          <div class="tgme_widget_message_text js-message_text">
            牧神记 S01 2160p<br>
            <a href="https://pan.quark.cn/s/good42">夸克</a>
          </div>
          <time datetime="2026-06-10T12:00:00+00:00">12:00</time>
        </div>
        """

        messages = parse_tme_messages(html, "mqte5")

        self.assertEqual(len(messages), 1)
        self.assertEqual(messages[0]["message_id"], "42")
        self.assertEqual(messages[0]["shareurl"], "https://pan.quark.cn/s/good42")
        self.assertEqual(messages[0]["taskname"], "牧神记 S01 2160p")
        self.assertEqual(messages[0]["publish_date"], "2026-06-10T12:00:00+00:00")
        self.assertEqual(messages[0]["source"], "Telegram")
        self.assertEqual(messages[0]["telegram_source"], "tg:mqte5")

    def test_cache_search_returns_matching_results(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = os.path.join(tmp, "data.db")
            cache = TelegramChannelCache({"enabled": True}, db_path=db_path)
            cache.save_candidates([
                {
                    "channel": "mqte5",
                    "message_id": "42",
                    "message_url": "https://t.me/mqte5/42",
                    "taskname": "牧神记 S01 2160p",
                    "content": "牧神记 S01 2160p 夸克",
                    "shareurl": "https://pan.quark.cn/s/good42",
                    "publish_date": "2026-06-10T12:00:00+00:00",
                    "source": "Telegram",
                    "telegram_source": "tg:mqte5",
                }
            ])

            results = cache.search("牧神记")

            self.assertEqual(len(results), 1)
            self.assertEqual(results[0]["shareurl"], "https://pan.quark.cn/s/good42")
            self.assertEqual(results[0]["source"], "Telegram")


if __name__ == "__main__":
    unittest.main()
