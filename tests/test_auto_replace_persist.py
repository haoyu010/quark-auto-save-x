import os
import unittest
from unittest.mock import patch

import quark_auto_save


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


if __name__ == "__main__":
    unittest.main()
