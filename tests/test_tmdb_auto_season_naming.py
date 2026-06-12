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

    def test_build_variety_episode_name_keeps_issue_segment_and_bonus_labels(self):
        cases = [
            (
                "20260604.第7期尝鲜.mp4",
                "超燃青春的合唱 - S01E07 - 尝鲜.mp4",
            ),
            (
                "20260605.第7期上.mp4",
                "超燃青春的合唱 - S01E07 - 上.mp4",
            ),
            (
                "20260605.第7期中.mp4",
                "超燃青春的合唱 - S01E07 - 中.mp4",
            ),
            (
                "20260605.第7期下.mp4",
                "超燃青春的合唱 - S01E07 - 下.mp4",
            ),
            (
                "20260606.纯享版.mp4",
                "超燃青春的合唱 - S01 - 20260606 - 纯享版.mp4",
            ),
            (
                "20260610.未播.mp4",
                "超燃青春的合唱 - S01 - 20260610 - 未播.mp4",
            ),
            (
                "20260605.EP07上.mp4",
                "超燃青春的合唱 - S01E07 - 上.mp4",
            ),
            (
                "20260605.E07下.mp4",
                "超燃青春的合唱 - S01E07 - 下.mp4",
            ),
            (
                "20260605.S01E07纯享版.mp4",
                "超燃青春的合唱 - S01E07 - 纯享版.mp4",
            ),
            (
                "20260605.7期加更版.mp4",
                "超燃青春的合唱 - S01E07 - 加更.mp4",
            ),
            (
                "20260605.第七期下.mp4",
                "超燃青春的合唱 - S01E07 - 下.mp4",
            ),
            (
                "2026-06-05 第07期 未播.mp4",
                "超燃青春的合唱 - S01E07 - 未播.mp4",
            ),
        ]

        for filename, expected in cases:
            with self.subTest(filename=filename):
                self.assertEqual(
                    quark_auto_save.build_variety_episode_name(
                        "超燃青春的合唱",
                        1,
                        filename,
                    ),
                    expected,
                )

    def test_do_rename_task_uses_variety_naming_for_variety_tasks(self):
        account = EpisodeRenameQuark([
            {
                "fid": "f1",
                "file_name": "20260604.第7期尝鲜.mp4",
                "dir": False,
                "size": 1000,
                "updated_at": 100,
            },
            {
                "fid": "f2",
                "file_name": "20260605.第7期上.mp4",
                "dir": False,
                "size": 1001,
                "updated_at": 101,
            },
            {
                "fid": "f3",
                "file_name": "20260606.纯享版.mp4",
                "dir": False,
                "size": 1002,
                "updated_at": 102,
            },
        ])
        task = {
            "taskname": "超燃青春的合唱",
            "savepath": "影视库/电视剧/综艺/超燃青春的合唱/Season 01",
            "use_episode_naming": True,
            "episode_naming": "超燃青春的合唱 - S01E[]",
            "matched_latest_season_number": 1,
            "library_category": "综艺",
        }

        renamed, logs = account.do_rename_task(task)

        self.assertTrue(renamed)
        self.assertEqual(
            account.rename_calls,
            [
                ("f1", "超燃青春的合唱 - S01E07 - 尝鲜.mp4"),
                ("f2", "超燃青春的合唱 - S01E07 - 上.mp4"),
                ("f3", "超燃青春的合唱 - S01 - 20260606 - 纯享版.mp4"),
            ],
        )
        self.assertTrue(any("S01E07 - 尝鲜" in item for item in logs))
        self.assertTrue(any("20260606 - 纯享版" in item for item in logs))

    def test_do_rename_task_keeps_regular_tv_naming_unchanged(self):
        account = EpisodeRenameQuark([
            {
                "fid": "file-1",
                "file_name": "Show.E07.mp4",
                "dir": False,
                "size": 1000,
                "updated_at": 100,
            }
        ])
        task = {
            "taskname": "Show",
            "savepath": "Shows",
            "use_episode_naming": True,
            "episode_naming": "Show - S01E[]",
            "matched_latest_season_number": 1,
            "library_category": "国产剧",
        }

        renamed, _logs = account.do_rename_task(task)

        self.assertTrue(renamed)
        self.assertEqual(account.rename_calls, [("file-1", "Show - S01E07.mp4")])


if __name__ == "__main__":
    unittest.main()
