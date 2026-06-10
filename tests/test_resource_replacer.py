import unittest

from app.sdk.resource_replacer import ResourceAutoReplacer


class FakeAccount:
    def __init__(self, shares):
        self.shares = shares
        self.savepath_fid = {}

    def extract_url(self, url):
        share_id = url.rsplit("/", 1)[-1]
        return share_id, "", "", {}

    def get_stoken(self, pwd_id, passcode):
        return pwd_id in self.shares, pwd_id if pwd_id in self.shares else "失效"

    def get_detail(self, pwd_id, stoken, pdir_fid="", _fetch_share=0):
        return {"list": self.shares.get(pwd_id, [])}


class ResourceAutoReplacerTest(unittest.TestCase):
    def test_rejects_lower_resolution_than_task_hint(self):
        account = FakeAccount({
            "low": [{"file_name": "Show.S01E01.1080p.mkv", "size": 1000, "dir": False}],
        })
        replacer = ResourceAutoReplacer(
            {"auto_replace_invalid_shareurl": {"enabled": True, "min_score": 85}},
            account,
            searchers=[lambda query: [{"taskname": "Show S01", "shareurl": "https://pan.quark.cn/s/low"}]],
        )
        task = {"taskname": "Show S01 2160p", "shareurl": "old", "shareurl_ban": "失效"}

        result = replacer.try_replace(task, "失效")

        self.assertFalse(result["replaced"])
        self.assertEqual(task["shareurl"], "old")

    def test_replaces_with_verified_no_downgrade_candidate(self):
        account = FakeAccount({
            "good": [{"file_name": "Show.S01E01.2160p.mkv", "fid": "fid-good-01", "size": 4000, "dir": False}],
        })
        replacer = ResourceAutoReplacer(
            {"auto_replace_invalid_shareurl": {"enabled": True, "min_score": 85}},
            account,
            searchers=[lambda query: [{"taskname": "Show S01 2160p", "shareurl": "https://pan.quark.cn/s/good"}]],
        )
        task = {"taskname": "Show S01 2160p", "shareurl": "old", "shareurl_ban": "失效"}

        result = replacer.try_replace(task, "失效")

        self.assertTrue(result["replaced"])
        self.assertEqual(result["old_shareurl"], "old")
        self.assertEqual(task["shareurl"], "https://pan.quark.cn/s/good")
        self.assertIsNone(task.get("shareurl_ban"))
        self.assertEqual(result["best"]["files"][0]["fid"], "fid-good-01")

    def test_filters_candidates_with_task_filterwords(self):
        account = FakeAccount({
            "extra": [{"file_name": "Show.S01E01.2160p.加更.mkv", "size": 4000, "dir": False}],
            "clean": [{"file_name": "Show.S01E01.2160p.mkv", "size": 4000, "dir": False}],
        })
        replacer = ResourceAutoReplacer(
            {"auto_replace_invalid_shareurl": {"enabled": True, "min_score": 85}},
            account,
            searchers=[
                lambda query: [
                    {"taskname": "Show S01 2160p 加更", "shareurl": "https://pan.quark.cn/s/extra"},
                    {"taskname": "Show S01 2160p", "shareurl": "https://pan.quark.cn/s/clean"},
                ]
            ],
        )
        task = {
            "taskname": "Show S01 2160p",
            "shareurl": "old",
            "shareurl_ban": "失效",
            "filterwords": "加更",
        }

        result = replacer.try_replace(task, "失效")

        self.assertTrue(result["replaced"])
        self.assertEqual(task["shareurl"], "https://pan.quark.cn/s/clean")

    def test_rejects_explicit_sub_1080_candidate_without_quality_hint(self):
        account = FakeAccount({
            "low": [{"file_name": "Show.S01E01.720p.mkv", "size": 700, "dir": False}],
        })
        replacer = ResourceAutoReplacer(
            {"auto_replace_invalid_shareurl": {"enabled": True, "min_score": 85}},
            account,
            searchers=[lambda query: [{"taskname": "Show S01 720p", "shareurl": "https://pan.quark.cn/s/low"}]],
        )
        task = {"taskname": "Show S01", "shareurl": "old", "shareurl_ban": "失效"}

        result = replacer.try_replace(task, "失效")

        self.assertFalse(result["replaced"])
        self.assertEqual(task["shareurl"], "old")

    def test_loads_search_timeout_setting(self):
        replacer = ResourceAutoReplacer(
            {"auto_replace_invalid_shareurl": {"enabled": True, "timeout_seconds": 6}},
            FakeAccount({}),
            searchers=[],
        )

        self.assertEqual(replacer.settings["search_timeout"], 6)

    def test_defaults_to_telegram_source_only(self):
        replacer = ResourceAutoReplacer(
            {"auto_replace_invalid_shareurl": {"enabled": True}},
            FakeAccount({}),
            searchers=[],
        )

        self.assertEqual(replacer.settings["sources"], ["telegram"])


if __name__ == "__main__":
    unittest.main()
