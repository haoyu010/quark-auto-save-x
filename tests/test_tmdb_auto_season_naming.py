import unittest

import quark_auto_save


class EpisodeRenameQuark(quark_auto_save.Quark):
    def __init__(self, files):
        self.files = files
        self.savepath_fid = {"Shows": "target"}
        self.rename_calls = []

    def ls_dir(self, fid):
        return self.files

    def get_fids(self, paths):
        return [{"fid": "target"}]

    def rename(self, fid, file_name):
        self.rename_calls.append((fid, file_name))
        for item in self.files:
            if item.get("fid") == fid:
                item["file_name"] = file_name
                break
        return {"code": 0}


class TMDBAutoSeasonNamingTest(unittest.TestCase):
    def tearDown(self):
        quark_auto_save.CONFIG_DATA = {}

    def test_rewrite_episode_naming_uses_task_matched_season(self):
        task = {
            "episode_naming": "Doupo - S01E[]",
            "matched_latest_season_number": 5,
        }

        naming = quark_auto_save.resolve_episode_naming_with_tmdb_season(task, {})

        self.assertEqual(naming, "Doupo - S05E[]")

    def test_rewrite_episode_naming_uses_injected_tmdb_resolver(self):
        task = {
            "taskname": "Doupo",
            "episode_naming": "Doupo - S01E[]",
        }

        naming = quark_auto_save.resolve_episode_naming_with_tmdb_season(
            task,
            {"tmdb_api_key": "fake"},
            season_resolver=lambda _task, _config: 6,
        )

        self.assertEqual(naming, "Doupo - S06E[]")

    def test_rewrite_episode_naming_keeps_non_season_patterns(self):
        task = {
            "episode_naming": "Doupo - EP[]",
            "matched_latest_season_number": 5,
        }

        naming = quark_auto_save.resolve_episode_naming_with_tmdb_season(task, {})

        self.assertEqual(naming, "Doupo - EP[]")

    def test_do_rename_task_applies_tmdb_season_before_local_rename(self):
        account = EpisodeRenameQuark([
            {
                "fid": "file-1",
                "file_name": "Doupo.E01.mkv",
                "dir": False,
                "size": 1000,
                "updated_at": 100,
            }
        ])
        task = {
            "taskname": "Doupo",
            "savepath": "Shows",
            "use_episode_naming": True,
            "episode_naming": "Doupo - S01E[]",
            "matched_latest_season_number": 5,
        }

        renamed, logs = account.do_rename_task(task)

        self.assertTrue(renamed)
        self.assertEqual(account.rename_calls, [("file-1", "Doupo - S05E01.mkv")])
        self.assertEqual(task["episode_naming"], "Doupo - S05E[]")
        self.assertTrue(any("S05E01" in item for item in logs))


if __name__ == "__main__":
    unittest.main()
