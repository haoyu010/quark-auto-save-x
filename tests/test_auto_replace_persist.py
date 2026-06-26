import os
import tempfile
import unittest
from unittest.mock import patch

import quark_auto_save
from app.sdk.db import RecordDB


class AutoReplaceFloorQuark(quark_auto_save.Quark):
    def __init__(self, share_files):
        self.share_files = share_files
        self.savepath_fid = {"Show S01": "target"}
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


class AutoReplacePersistTest(unittest.TestCase):
    def tearDown(self):
        quark_auto_save.CONFIG_DATA = {}

    def test_manual_single_task_replacement_merges_back_to_config_by_original_index(self):
        quark_auto_save.CONFIG_DATA = {
            "tasklist": [
                {
                    "taskname": "Show S01",
                    "shareurl": "old",
                    "shareurl_ban": "expired",
                },
                {
                    "taskname": "Other",
                    "shareurl": "other",
                    "shareurl_ban": None,
                },
            ]
        }
        runtime_task = {
            "taskname": "Show S01",
            "shareurl": "https://pan.quark.cn/s/new",
            "shareurl_ban": None,
        }

        with patch.dict(os.environ, {"ORIGINAL_TASK_INDEX": "1"}):
            changed = quark_auto_save.persist_auto_replaced_shareurl(
                runtime_task,
                {"old_shareurl": "old"},
            )

        self.assertTrue(changed)
        self.assertEqual(
            quark_auto_save.CONFIG_DATA["tasklist"][0]["shareurl"],
            "https://pan.quark.cn/s/new",
        )
        self.assertIsNone(quark_auto_save.CONFIG_DATA["tasklist"][0].get("shareurl_ban"))
        self.assertEqual(quark_auto_save.CONFIG_DATA["tasklist"][1]["shareurl"], "other")

    def test_saved_episode_floor_uses_directory_and_transfer_records(self):
        saved_files = [
            {"file_name": "Show.S01E01.mkv", "dir": False},
            {"file_name": "Extras", "dir": True},
        ]
        records = [
            {"original_name": "Show.S01E02.mkv", "renamed_to": "Show - 02.mkv"},
            {"original_name": "Show.S01E01.mkv", "renamed_to": "Show - 01.mkv"},
        ]

        floor = quark_auto_save.get_saved_episode_floor(saved_files, records)

        self.assertEqual(floor, 2)

    def test_replacement_startfid_moves_to_oldest_missing_episode_by_modified_time(self):
        replacement_files = [
            {"file_name": "Show.S01E03.mkv", "fid": "fid-e03", "dir": False, "updated_at": 300},
            {"file_name": "Show.S01E04.mkv", "fid": "fid-e04", "dir": False, "updated_at": 100},
            {"file_name": "Show.S01E02.mkv", "fid": "fid-e02", "dir": False, "updated_at": 200},
        ]

        selection = quark_auto_save.select_replacement_startfid_by_saved_progress(
            replacement_files,
            saved_episode_floor=2,
        )

        self.assertEqual(selection["startfid"], "fid-e04")
        self.assertEqual(selection["episode"], 4)
        self.assertEqual(selection["file_name"], "Show.S01E04.mkv")

    def test_filter_share_files_by_saved_episode_floor_keeps_only_missing_episodes(self):
        files = [
            {"file_name": "Show.S01E01.mkv", "fid": "fid-e01", "dir": False},
            {"file_name": "Show.S01E02.mkv", "fid": "fid-e02", "dir": False},
            {"file_name": "Show.S01E03.mkv", "fid": "fid-e03", "dir": False},
            {"file_name": "Show.S01E04.mkv", "fid": "fid-e04", "dir": False},
            {"file_name": "Behind The Scenes", "fid": "folder", "dir": True},
        ]

        filtered = quark_auto_save.filter_share_files_by_saved_episode_floor(files, 2)

        self.assertEqual([item["fid"] for item in filtered], ["fid-e03", "fid-e04", "folder"])

    def test_completed_tv_task_by_tmdb_episode_count_suppresses_invalid_replacement(self):
        task = {
            "taskname": "南部档案",
            "content_type": "tv",
            "matched_latest_season_number": 1,
            "calendar_info": {
                "match": {
                    "tmdb_id": 12345,
                    "latest_season_number": 1,
                }
            },
        }
        progress_resolver = lambda _task: 12
        total_resolver = lambda _task, _config: 12

        self.assertTrue(
            quark_auto_save.is_task_completed_by_tmdb_episode_count(
                task,
                {},
                progress_resolver=progress_resolver,
                total_resolver=total_resolver,
            )
        )

    def test_incomplete_tv_task_by_tmdb_episode_count_keeps_invalid_replacement(self):
        task = {
            "taskname": "追更剧",
            "content_type": "tv",
            "matched_latest_season_number": 1,
            "calendar_info": {
                "match": {
                    "tmdb_id": 23456,
                    "latest_season_number": 1,
                }
            },
        }
        progress_resolver = lambda _task: 10
        total_resolver = lambda _task, _config: 12

        self.assertFalse(
            quark_auto_save.is_task_completed_by_tmdb_episode_count(
                task,
                {},
                progress_resolver=progress_resolver,
                total_resolver=total_resolver,
            )
        )

    def test_completed_movie_task_suppresses_invalid_replacement(self):
        task = {"taskname": "迷墙", "content_type": "movie", "movie_once": True}

        self.assertTrue(quark_auto_save.is_completed_task_for_invalid_share(task, {}))

    def test_completed_invalid_share_task_does_not_notify_or_replace(self):
        class QuietCompletedQuark(quark_auto_save.Quark):
            def __init__(self):
                pass

            def is_completed_invalid_share_task(self, task):
                return True

            def retry_save_after_auto_replace(self, task, reason=""):
                raise AssertionError("completed task should not auto replace")

        task = {
            "taskname": "南部档案",
            "shareurl": "https://pan.quark.cn/s/expired",
            "shareurl_ban": "分享地址已失效",
            "savepath": "影视库/电视剧/南部档案/Season 01",
        }
        quark_auto_save.NOTIFYS = []

        result = QuietCompletedQuark().do_save_task(task)

        self.assertIsNone(result)
        self.assertEqual(quark_auto_save.NOTIFYS, [])

    def test_persist_auto_replaced_shareurl_updates_startfid_when_available(self):
        quark_auto_save.CONFIG_DATA = {
            "tasklist": [
                {
                    "taskname": "Show S01",
                    "shareurl": "old",
                    "shareurl_ban": "expired",
                    "startfid": "old-start",
                }
            ]
        }
        runtime_task = {
            "taskname": "Show S01",
            "shareurl": "https://pan.quark.cn/s/new",
            "shareurl_ban": None,
            "startfid": "fid-e04",
        }

        changed = quark_auto_save.persist_auto_replaced_shareurl(
            runtime_task,
            {
                "old_shareurl": "old",
                "startfid_update": {"startfid": "fid-e04"},
            },
        )

        self.assertTrue(changed)
        self.assertEqual(
            quark_auto_save.CONFIG_DATA["tasklist"][0]["shareurl"],
            "https://pan.quark.cn/s/new",
        )
        self.assertEqual(quark_auto_save.CONFIG_DATA["tasklist"][0]["startfid"], "fid-e04")

    def test_persist_auto_replaced_shareurl_persists_saved_episode_floor(self):
        quark_auto_save.CONFIG_DATA = {
            "tasklist": [
                {
                    "taskname": "Show S01",
                    "shareurl": "old",
                    "shareurl_ban": "expired",
                }
            ]
        }
        runtime_task = {
            "taskname": "Show S01",
            "shareurl": "https://pan.quark.cn/s/new",
            "shareurl_ban": None,
            "_auto_replace_saved_episode_floor": 47,
        }

        changed = quark_auto_save.persist_auto_replaced_shareurl(
            runtime_task,
            {"old_shareurl": "old"},
        )

        self.assertTrue(changed)
        self.assertEqual(
            quark_auto_save.CONFIG_DATA["tasklist"][0]["auto_replace_saved_episode_floor"],
            47,
        )

    def test_dir_check_uses_persisted_auto_replace_floor_before_saving(self):
        share_files = [
            {
                "file_name": f"Show.S01E{episode:02d}.mkv",
                "fid": f"fid-e{episode:02d}",
                "share_fid_token": f"token-e{episode:02d}",
                "dir": False,
                "obj_category": "video",
                "size": 1000 + episode,
            }
            for episode in range(1, 51)
        ]
        account = AutoReplaceFloorQuark(share_files)
        task = {
            "taskname": "Show S01",
            "savepath": "Show S01",
            "pattern": ".*",
            "replace": "",
            "auto_replace_saved_episode_floor": 47,
        }

        with patch.object(quark_auto_save.time, "sleep", lambda _: None):
            account.dir_check_and_save(task, "pwd", "stoken")

        self.assertEqual(account.saved_fids, ["fid-e50", "fid-e49", "fid-e48"])

    def test_auto_replace_progress_falls_back_to_same_task_records_when_savepath_changed(self):
        replacement_files = [
            {
                "file_name": f"Show - S01E{episode:02d}.mkv",
                "fid": f"fid-e{episode:02d}",
                "share_fid_token": f"token-e{episode:02d}",
                "dir": False,
                "obj_category": "video",
                "size": 1000 + episode,
                "updated_at": 100 + episode,
            }
            for episode in range(1, 14)
        ]
        account = AutoReplaceFloorQuark(replacement_files)
        account.savepath_fid = {"Anime/Show - S07": "target"}

        with tempfile.TemporaryDirectory() as tmp:
            db_path = os.path.join(tmp, "data.db")
            db = RecordDB(db_path)
            db.add_record(
                task_name="Show",
                original_name="Show - S01E12.mkv",
                renamed_to="Show - S01E12.mkv",
                file_size=1012,
                modify_date=100,
                file_id="old-fid-e12",
                save_path="Anime/Show - S01",
            )
            db.close()

            with patch.object(quark_auto_save, "RecordDB", lambda: RecordDB(db_path)):
                task = {"taskname": "Show", "savepath": "Anime/Show - S07"}
                selection = account.prepare_auto_replace_startfid(
                    task,
                    {"best": {"files": replacement_files}},
                )

        self.assertEqual(selection["startfid"], "fid-e13")
        self.assertEqual(task["auto_replace_saved_episode_floor"], 12)

    def test_movie_task_does_not_attempt_auto_replace(self):
        account = AutoReplaceFloorQuark([])
        calls = []
        task = {
            "taskname": "镖人：风起大漠",
            "content_type": "movie",
            "shareurl_ban": "分享资源已失效",
        }

        with patch.object(
            account,
            "try_auto_replace_invalid_shareurl",
            side_effect=lambda *args, **kwargs: calls.append((args, kwargs)) or {"replaced": True},
        ):
            replaced, retry_tree = account.retry_save_after_auto_replace(task, task["shareurl_ban"])

        self.assertFalse(replaced)
        self.assertIsNone(retry_tree)
        self.assertEqual(calls, [])


if __name__ == "__main__":
    unittest.main()
