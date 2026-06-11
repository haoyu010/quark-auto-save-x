import unittest
from unittest.mock import patch

import quark_auto_save
from app.sdk.resource_replacer import ResourceAutoReplacer


class MediaExcludeQuark(quark_auto_save.Quark):
    def __init__(self, share_files):
        self.share_files = share_files
        self.savepath_fid = {"Shows": "target"}
        self.saved_fids = []

    def get_detail(self, pwd_id, stoken, pdir_fid="", _fetch_share=0):
        return {"list": list(self.share_files)}

    def ls_dir(self, fid):
        return []

    def get_fids(self, paths):
        return [{"fid": "target"}]

    def check_file_exists_in_records(self, file_id, task=None):
        return False

    def save_file(self, fid_list, fid_token_list, to_pdir_fid, pwd_id, stoken):
        self.saved_fids = list(fid_list)
        return {"code": 0, "data": {"task_id": "task-1"}}

    def query_task(self, task_id):
        return {"code": 0, "data": {"save_as": {"save_as_top_fids": list(self.saved_fids)}}}

    def create_transfer_record(self, task, file_info, renamed_to=""):
        return None


class FakeAccount:
    def __init__(self, shares):
        self.shares = shares

    def extract_url(self, url):
        share_id = url.rsplit("/", 1)[-1]
        return share_id, "", "", {}

    def get_stoken(self, pwd_id, passcode):
        return pwd_id in self.shares, pwd_id if pwd_id in self.shares else "失效"

    def get_detail(self, pwd_id, stoken, pdir_fid="", _fetch_share=0):
        return {"list": self.shares.get(pwd_id, [])}


class MediaSaveDefaultsTest(unittest.TestCase):
    def tearDown(self):
        quark_auto_save.CONFIG_DATA = {}

    def test_default_media_excludes_remove_poster_backup_duplicate_files(self):
        files = [
            {"file_name": "Show.S01E01.2160p.mkv", "fid": "main", "dir": False},
            {"file_name": "海报.jpg", "fid": "poster-cn", "dir": False},
            {"file_name": "poster.png", "fid": "poster-en", "dir": False},
            {"file_name": "备用.Show.S01E01.mkv", "fid": "backup", "dir": False},
            {"file_name": "duplicate.nfo", "fid": "duplicate", "dir": False},
        ]

        filtered = quark_auto_save.advanced_filter_files(
            files,
            quark_auto_save.DEFAULT_MEDIA_EXCLUDE_KEYWORDS,
        )

        self.assertEqual([item["fid"] for item in filtered], ["main"])

    def test_task_filterwords_merge_with_default_media_excludes(self):
        merged = quark_auto_save.get_effective_filterwords(
            {"filterwords": "2160P|加更"},
            {"task_settings": {"media_exclude_keywords": "海报,poster,备用"}},
        )

        self.assertEqual(merged, "2160P|加更,海报,poster,备用")

    def test_save_task_applies_default_media_excludes_without_task_filterwords(self):
        account = MediaExcludeQuark([
            {
                "file_name": "Show.S01E01.2160p.mkv",
                "fid": "main",
                "share_fid_token": "token-main",
                "dir": False,
                "obj_category": "video",
                "size": 1000,
            },
            {
                "file_name": "poster.jpg",
                "fid": "poster",
                "share_fid_token": "token-poster",
                "dir": False,
                "obj_category": "image",
                "size": 10,
            },
            {
                "file_name": "备用.Show.S01E02.2160p.mkv",
                "fid": "backup",
                "share_fid_token": "token-backup",
                "dir": False,
                "obj_category": "video",
                "size": 1001,
            },
        ])
        quark_auto_save.CONFIG_DATA = {"task_settings": {}}

        with patch.object(quark_auto_save.time, "sleep", lambda _: None):
            account.dir_check_and_save(
                {"taskname": "Show", "savepath": "Shows", "pattern": ".*", "replace": ""},
                "pwd",
                "stoken",
            )

        self.assertEqual(account.saved_fids, ["main"])

    def test_resource_replacer_applies_default_media_excludes_to_candidates(self):
        account = FakeAccount({
            "good": [
                {"file_name": "Show.S01E01.2160p.mkv", "fid": "main", "size": 4000, "dir": False},
                {"file_name": "poster.jpg", "fid": "poster", "size": 20, "dir": False},
            ],
        })
        replacer = ResourceAutoReplacer(
            {"auto_replace_invalid_shareurl": {"enabled": True, "min_score": 85}},
            account,
            searchers=[lambda query: [{"taskname": "Show S01 2160p", "shareurl": "https://pan.quark.cn/s/good"}]],
        )
        task = {"taskname": "Show S01 2160p", "shareurl": "old", "shareurl_ban": "失效"}

        result = replacer.try_replace(task, "失效")

        self.assertTrue(result["replaced"])
        self.assertEqual([item["fid"] for item in result["best"]["files"]], ["main"])

    def test_discovery_templates_use_media_library_season_folder(self):
        html = open("app/templates/index.html", encoding="utf-8").read()

        self.assertIn('anime_save_path: "动画目录前缀/剧名/Season 季数"', html)
        self.assertIn('tv_save_path: "剧集目录前缀/剧名/Season 季数"', html)
        self.assertIn('placeholder="动画目录前缀/剧名/Season 季数"', html)


if __name__ == "__main__":
    unittest.main()
