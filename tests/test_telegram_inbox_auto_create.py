import copy
import unittest

from app.sdk.telegram_inbox import (
    TelegramAutoCreateService,
    build_media_task_from_share,
    extract_title_seed,
    is_authorized_message,
)


class FakeAccount:
    def __init__(self, shares):
        self.shares = shares

    def extract_url(self, url):
        share_id = url.rsplit("/", 1)[-1].split("?", 1)[0]
        return share_id, "", 0, []

    def get_stoken(self, pwd_id, passcode=""):
        if pwd_id in self.shares:
            return True, f"token-{pwd_id}"
        return False, "share invalid"

    def get_detail(self, pwd_id, stoken, pdir_fid=0, _fetch_share=0):
        return {"list": copy.deepcopy(self.shares.get(pwd_id, []))}


class FakeTMDB:
    def __init__(self, movie=None, tv=None, details=None):
        self.movie = movie
        self.tv = tv
        self.details = details or {}

    def search_movie(self, query, year=None):
        return self.movie

    def search_tv_show(self, query, year=None):
        return self.tv

    def get_tv_show_details(self, tv_id):
        return self.details


class TelegramInboxAutoCreateTest(unittest.TestCase):
    def test_authorization_accepts_configured_user_or_chat_id(self):
        private_message = {"chat": {"id": 42}, "from": {"id": 42}}
        group_message = {"chat": {"id": -100}, "from": {"id": 42}}
        other_message = {"chat": {"id": 7}, "from": {"id": 7}}

        self.assertTrue(is_authorized_message(private_message, "42"))
        self.assertTrue(is_authorized_message(group_message, "42"))
        self.assertFalse(is_authorized_message(other_message, "42"))

    def test_movie_share_builds_movie_library_path(self):
        account = FakeAccount({
            "movie123": [
                {"file_name": "阿基拉.1988.1080p.mkv", "dir": False, "fid": "f1"},
            ]
        })
        tmdb = FakeTMDB(movie={
            "id": 149,
            "title": "阿基拉",
            "release_date": "1988-07-16",
        })

        task = build_media_task_from_share(
            "https://pan.quark.cn/s/movie123",
            "阿基拉 1988 https://pan.quark.cn/s/movie123",
            account,
            {
                "task_settings": {
                    "movie_save_path": "电影目录前缀/片名 (年份)",
                    "movie_naming_pattern": "^(.*)\\.([^.]+)",
                    "movie_naming_replace": "片名 (年份).\\2",
                }
            },
            tmdb,
        )

        self.assertEqual(task["taskname"], "阿基拉")
        self.assertEqual(task["content_type"], "movie")
        self.assertEqual(task["savepath"], "电影目录前缀/阿基拉 (1988)")
        self.assertEqual(task["replace"], "阿基拉 (1988).\\2")
        self.assertFalse(task["use_episode_naming"])
        self.assertEqual(task["calendar_info"]["match"]["tmdb_id"], 149)

    def test_tv_share_builds_season_path_and_episode_naming(self):
        account = FakeAccount({
            "tv123": [
                {"file_name": "斗破苍穹.S05E01.mkv", "dir": False, "fid": "f1"},
                {"file_name": "斗破苍穹.S05E02.mkv", "dir": False, "fid": "f2"},
            ]
        })
        tmdb = FakeTMDB(
            tv={"id": 999, "name": "斗破苍穹", "first_air_date": "2017-01-07"},
            details={
                "id": 999,
                "name": "斗破苍穹",
                "first_air_date": "2017-01-07",
                "last_episode_to_air": {"season_number": 5},
                "genres": [{"id": 16, "name": "Animation"}],
                "seasons": [{"season_number": 5, "episode_count": 104}],
            },
        )

        task = build_media_task_from_share(
            "https://pan.quark.cn/s/tv123",
            "斗破苍穹 第五季 https://pan.quark.cn/s/tv123",
            account,
            {
                "task_settings": {
                    "anime_save_path": "追更/追更动漫/剧名/Season 季数",
                    "tv_naming_rule": "剧名 - S季数E[]",
                    "tv_ignore_extension": True,
                }
            },
            tmdb,
        )

        self.assertEqual(task["taskname"], "斗破苍穹")
        self.assertEqual(task["content_type"], "anime")
        self.assertEqual(task["savepath"], "追更/追更动漫/斗破苍穹/Season 05")
        self.assertEqual(task["episode_naming"], "斗破苍穹 - S05E[]")
        self.assertEqual(task["pattern"], "斗破苍穹 - S05E[]")
        self.assertTrue(task["use_episode_naming"])
        self.assertTrue(task["ignore_extension"])
        self.assertEqual(task["calendar_info"]["match"]["latest_season_number"], 5)

    def test_episode_files_still_build_series_task_when_tmdb_is_unavailable(self):
        account = FakeAccount({
            "anime123": [
                {"file_name": "牧神记.S01E01.mkv", "dir": False, "fid": "f1"},
                {"file_name": "牧神记.S01E02.mkv", "dir": False, "fid": "f2"},
            ]
        })

        task = build_media_task_from_share(
            "https://pan.quark.cn/s/anime123",
            "动漫 牧神记 S01 https://pan.quark.cn/s/anime123",
            account,
            {
                "task_settings": {
                    "anime_save_path": "追更/追更动漫/剧名/Season 季数",
                    "tv_naming_rule": "剧名 - S季数E[]",
                }
            },
            FakeTMDB(movie=None, tv=None),
        )

        self.assertEqual(task["taskname"], "牧神记")
        self.assertEqual(task["content_type"], "anime")
        self.assertEqual(task["savepath"], "追更/追更动漫/牧神记/Season 01")
        self.assertEqual(task["episode_naming"], "牧神记 - S01E[]")

    def test_default_animation_template_does_not_force_all_series_to_anime(self):
        account = FakeAccount({
            "drama123": [
                {"file_name": "黑镜.S07E01.mkv", "dir": False, "fid": "f1"},
            ]
        })

        task = build_media_task_from_share(
            "https://pan.quark.cn/s/drama123",
            "黑镜 S07 https://pan.quark.cn/s/drama123",
            account,
            {
                "task_settings": {
                    "tv_save_path": "追更/追更剧集/剧名/Season 季数",
                    "anime_save_path": "动画目录前缀/剧名/Season 季数",
                    "tv_naming_rule": "剧名 - S季数E[]",
                }
            },
            FakeTMDB(movie=None, tv=None),
        )

        self.assertEqual(task["content_type"], "tv")
        self.assertEqual(task["savepath"], "追更/追更剧集/黑镜/Season 07")

    def test_service_skips_duplicate_share_and_does_not_run(self):
        account = FakeAccount({"dup": [{"file_name": "阿基拉.mkv", "dir": False, "fid": "f1"}]})
        config = {
            "push_config": {"TG_USER_ID": "42"},
            "tasklist": [{"taskname": "阿基拉", "shareurl": "https://pan.quark.cn/s/dup"}],
        }
        runs = []
        service = TelegramAutoCreateService(
            config,
            account_factory=lambda: account,
            tmdb_factory=lambda: FakeTMDB(movie={"id": 1, "title": "阿基拉", "release_date": "1988-07-16"}),
            save_config=lambda data: None,
            run_task=lambda task, index: runs.append((task, index)),
        )

        result = service.handle_message({
            "message_id": 1,
            "chat": {"id": 42},
            "from": {"id": 42},
            "text": "阿基拉 https://pan.quark.cn/s/dup",
        })

        self.assertEqual(result.status, "duplicate")
        self.assertEqual(len(config["tasklist"]), 1)
        self.assertEqual(runs, [])

    def test_service_adds_task_and_runs_immediately(self):
        account = FakeAccount({"new": [{"file_name": "阿基拉.mkv", "dir": False, "fid": "f1"}]})
        config = {"push_config": {"TG_USER_ID": "42"}, "tasklist": [], "task_settings": {}}
        saved = []
        runs = []
        service = TelegramAutoCreateService(
            config,
            account_factory=lambda: account,
            tmdb_factory=lambda: FakeTMDB(movie={"id": 1, "title": "阿基拉", "release_date": "1988-07-16"}),
            save_config=lambda data: saved.append(copy.deepcopy(data)),
            run_task=lambda task, index: runs.append((task["taskname"], index)),
        )

        result = service.handle_message({
            "message_id": 2,
            "chat": {"id": 42},
            "from": {"id": 42},
            "text": "阿基拉 https://pan.quark.cn/s/new",
        })

        self.assertEqual(result.status, "created")
        self.assertEqual(len(config["tasklist"]), 1)
        self.assertEqual(saved[-1]["tasklist"][0]["taskname"], "阿基拉")
        self.assertEqual(runs, [("阿基拉", 0)])
        self.assertTrue(result.run_started)

    def test_extract_title_seed_ignores_url_noise(self):
        self.assertEqual(
            extract_title_seed("  牧神记 S01\nhttps://pan.quark.cn/s/abc  "),
            "牧神记 S01",
        )


if __name__ == "__main__":
    unittest.main()
