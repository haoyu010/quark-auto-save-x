import copy
import unittest

from app.sdk.telegram_inbox import (
    TelegramAutoCreateService,
    TelegramInboxPoller,
    _classify_movie_library_category,
    _classify_tv_library_category,
    _clean_media_title,
    _extract_year,
    _looks_like_series,
    build_media_task_from_share,
    extract_title_seed,
    is_authorized_message,
    mark_movie_task_completed,
    repair_media_library_task,
    repair_media_library_tasks,
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
    def __init__(self, movie=None, tv=None, details=None, movie_results=None, tv_results=None, details_by_id=None):
        self.movie = movie
        self.tv = tv
        self.movie_results = movie_results
        self.tv_results = tv_results
        self.details = details or {}
        self.details_by_id = details_by_id or {}

    def search_movie(self, query, year=None):
        return self.movie

    def search_movie_all(self, query, year=None):
        if self.movie_results is not None:
            return self.movie_results
        return [self.movie] if self.movie else []

    def search_tv_show(self, query, year=None):
        return self.tv

    def search_tv_show_all(self, query, year=None):
        if self.tv_results is not None:
            return self.tv_results
        return [self.tv] if self.tv else []

    def get_tv_show_details(self, tv_id):
        if tv_id in self.details_by_id:
            return self.details_by_id[tv_id]
        return self.details


class FakeTelegramResponse:
    def __init__(self, payload):
        self.payload = payload

    def json(self):
        return self.payload


class FakeTelegramSession:
    def __init__(self):
        self.calls = []

    def post(self, url, data=None, **kwargs):
        self.calls.append(("POST", url, data or {}, kwargs))
        return FakeTelegramResponse({"ok": True})

    def get(self, url, params=None, **kwargs):
        self.calls.append(("GET", url, params or {}, kwargs))
        return FakeTelegramResponse({"ok": True, "result": []})


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
            "genre_ids": [16],
            "original_language": "ja",
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
        self.assertEqual(task["runweek"], [])
        self.assertEqual(task["auto_replace_invalid_shareurl"], "disabled")
        self.assertTrue(task["movie_once"])
        self.assertTrue(task["skip_calendar_refresh"])

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
                "origin_country": ["CN"],
                "original_language": "zh",
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

    def test_channel_caption_quality_words_do_not_pollute_task_name(self):
        self.assertEqual(
            _clean_media_title("名称: 南部档案（2026）4K 10bit 60FPS 首更06集"),
            "南部档案",
        )

        account = FakeAccount({
            "nanbu": [
                {"file_name": "南部档案.S01E06.mkv", "dir": False, "fid": "f1"},
            ]
        })
        tmdb = FakeTMDB(
            tv={"id": 321, "name": "南部档案", "first_air_date": "2026-01-01"},
            details={
                "id": 321,
                "name": "南部档案",
                "first_air_date": "2026-01-01",
                "origin_country": ["CN"],
                "original_language": "zh",
                "last_episode_to_air": {"season_number": 1},
                "seasons": [{"season_number": 1, "episode_count": 6}],
            },
        )
        caption = """名称: 南部档案（2026）4K 10bit 60FPS 首更06集
描述: 民国初年，南洋海上发生水鬼望乡离奇命案
夸克: https://pan.quark.cn/s/nanbu"""

        task = build_media_task_from_share(
            "https://pan.quark.cn/s/nanbu",
            caption,
            account,
            {
                "task_settings": {
                    "tv_save_path": "追更电视剧/剧名/Season 季数",
                    "tv_naming_rule": "剧名 - S季数E[]",
                    "tv_ignore_extension": True,
                }
            },
            tmdb,
        )

        self.assertEqual(task["taskname"], "南部档案")
        self.assertEqual(task["savepath"], "追更电视剧/南部档案/Season 01")
        self.assertEqual(task["episode_naming"], "南部档案 - S01E[]")

    def test_channel_title_parser_handles_common_release_formats(self):
        samples = [
            ("【原盘】赌侠 (1990) 1080P REMUX 国粤多音轨 中字外挂字幕", "赌侠", "1990", False),
            ("沧月星澜(2026)4K S01E01 - E18 HiveWeb", "沧月星澜", "2026", True),
            ("她战(2026)4K S01E01 - E16 HiveWeb", "她战", "2026", True),
            ("师兄啊师兄 HQ 高码率 更至EP145", "师兄啊师兄", "", True),
        ]

        for raw, title, year, is_series in samples:
            with self.subTest(raw=raw):
                self.assertEqual(_clean_media_title(raw), title)
                self.assertEqual(_extract_year(raw), year)
                self.assertEqual(_looks_like_series(raw, []), is_series)

    def test_media_root_builds_clean_tv_library_path_for_inbox_tasks(self):
        account = FakeAccount({
            "nanbu": [
                {"file_name": "南部档案.S01E06.mkv", "dir": False, "fid": "f1"},
            ]
        })
        tmdb = FakeTMDB(
            tv={"id": 321, "name": "南部档案", "first_air_date": "2026-01-01"},
            details={
                "id": 321,
                "name": "南部档案",
                "first_air_date": "2026-01-01",
                "origin_country": ["CN"],
                "original_language": "zh",
                "last_episode_to_air": {"season_number": 1},
                "seasons": [{"season_number": 1, "episode_count": 6}],
            },
        )

        task = build_media_task_from_share(
            "https://pan.quark.cn/s/nanbu",
            "名称: 南部档案（2026）4K 10bit 60FPS 首更06集\nhttps://pan.quark.cn/s/nanbu",
            account,
            {
                "task_settings": {
                    "telegram_inbox_media_root": "影视剧",
                    "tv_save_path": "旧模板/剧名/Season 季数",
                    "tv_naming_rule": "剧名 - S季数E[]",
                    "tv_ignore_extension": True,
                }
            },
            tmdb,
        )

        self.assertEqual(task["taskname"], "南部档案")
        self.assertEqual(task["content_type"], "tv")
        self.assertEqual(task["savepath"], "影视剧/电视剧/国产剧/南部档案/Season 01")
        self.assertEqual(task["episode_naming"], "南部档案 - S01E[]")

    def test_media_root_builds_movie_library_path_for_inbox_tasks(self):
        account = FakeAccount({
            "akira": [
                {"file_name": "阿基拉.1988.1080p.mkv", "dir": False, "fid": "f1"},
            ]
        })
        tmdb = FakeTMDB(movie={
            "id": 149,
            "title": "阿基拉",
            "release_date": "1988-07-16",
            "genre_ids": [16],
            "original_language": "ja",
        })

        task = build_media_task_from_share(
            "https://pan.quark.cn/s/akira",
            "名称: 阿基拉（1988） 4K https://pan.quark.cn/s/akira",
            account,
            {
                "task_settings": {
                    "telegram_inbox_media_root": "影视剧",
                    "movie_save_path": "旧电影模板/片名 (年份)",
                    "movie_naming_pattern": "^(.*)\\.([^.]+)",
                    "movie_naming_replace": "片名 (年份).\\2",
                }
            },
            tmdb,
        )

        self.assertEqual(task["taskname"], "阿基拉")
        self.assertEqual(task["content_type"], "movie")
        self.assertEqual(task["library_category"], "动画电影")
        self.assertEqual(task["savepath"], "影视剧/电影/动画电影/阿基拉 (1988)")
        self.assertEqual(task["runweek"], [])
        self.assertEqual(task["auto_replace_invalid_shareurl"], "disabled")

    def test_mark_movie_task_completed_migrates_existing_movie_task(self):
        task = {
            "taskname": "镖人：风起大漠",
            "content_type": "movie",
            "runweek": [1, 2, 3, 4, 5, 6, 7],
            "enddate": "",
        }

        changed = mark_movie_task_completed(task)

        self.assertTrue(changed)
        self.assertEqual(task["runweek"], [])
        self.assertTrue(task["enddate"])
        self.assertEqual(task["auto_replace_invalid_shareurl"], "disabled")
        self.assertTrue(task["movie_once"])
        self.assertTrue(task["skip_calendar_refresh"])

    def test_media_root_classifies_movie_library_category_like_organizer_rules(self):
        account = FakeAccount({
            "hk": [
                {"file_name": "赌侠.1990.1080p.mkv", "dir": False, "fid": "f1"},
            ],
            "unknown": [
                {"file_name": "未知电影.2024.1080p.mkv", "dir": False, "fid": "f2"},
            ],
        })

        hk_task = build_media_task_from_share(
            "https://pan.quark.cn/s/hk",
            "名称: 赌侠 (1990) 1080P https://pan.quark.cn/s/hk",
            account,
            {"task_settings": {"telegram_inbox_media_root": "影视库"}},
            FakeTMDB(movie={"id": 624, "title": "赌侠", "release_date": "1990-12-13", "original_language": "zh"}),
        )

        self.assertEqual(hk_task["library_category"], "华语电影")
        self.assertEqual(hk_task["savepath"], "影视库/电影/华语电影/赌侠 (1990)")

        unknown_task = build_media_task_from_share(
            "https://pan.quark.cn/s/unknown",
            "名称: 未知电影 (2024) https://pan.quark.cn/s/unknown",
            account,
            {"task_settings": {"telegram_inbox_media_root": "影视库"}},
            FakeTMDB(movie={"id": 100, "title": "未知电影", "release_date": "2024-01-01"}),
        )

        self.assertEqual(unknown_task["library_category"], "其他电影")
        self.assertEqual(unknown_task["savepath"], "影视库/电影/其他电影/未知电影 (2024)")

    def test_movie_search_uses_best_tmdb_match_not_first_result(self):
        account = FakeAccount({
            "duxia": [
                {"file_name": "赌侠.1990.1080p.REMUX.mkv", "dir": False, "fid": "f1"},
            ]
        })
        wrong = {"id": 1, "title": "赌神", "release_date": "1989-12-14", "original_language": "zh"}
        right = {"id": 624, "title": "赌侠", "release_date": "1990-12-13", "original_language": "zh"}

        task = build_media_task_from_share(
            "https://pan.quark.cn/s/duxia",
            "名称：【原盘】赌侠 (1990) 1080P REMUX 国粤多音轨 中字外挂字幕 https://pan.quark.cn/s/duxia",
            account,
            {
                "task_settings": {
                    "telegram_inbox_media_root": "影视库",
                    "movie_naming_pattern": "^(.*)\\.([^.]+)",
                    "movie_naming_replace": "片名 (年份).\\2",
                }
            },
            FakeTMDB(movie=wrong, movie_results=[wrong, right]),
        )

        self.assertEqual(task["taskname"], "赌侠")
        self.assertEqual(task["library_category"], "华语电影")
        self.assertEqual(task["savepath"], "影视库/电影/华语电影/赌侠 (1990)")
        self.assertEqual(task["calendar_info"]["match"]["tmdb_id"], 624)

    def test_media_root_builds_anime_season_path_for_inbox_tasks(self):
        account = FakeAccount({
            "doupo": [
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
                "origin_country": ["CN"],
                "original_language": "zh",
                "last_episode_to_air": {"season_number": 5},
                "genres": [{"id": 16, "name": "Animation"}],
                "seasons": [{"season_number": 5, "episode_count": 104}],
            },
        )

        task = build_media_task_from_share(
            "https://pan.quark.cn/s/doupo",
            "斗破苍穹 第五季 https://pan.quark.cn/s/doupo",
            account,
            {
                "task_settings": {
                    "telegram_inbox_media_root": "影视剧",
                    "anime_save_path": "旧动漫模板/剧名/Season 季数",
                    "tv_naming_rule": "剧名 - S季数E[]",
                    "tv_ignore_extension": True,
                }
            },
            tmdb,
        )

        self.assertEqual(task["taskname"], "斗破苍穹")
        self.assertEqual(task["content_type"], "anime")
        self.assertEqual(task["savepath"], "影视剧/电视剧/国漫/斗破苍穹/Season 05")

    def test_episode_update_quality_words_build_anime_task_not_movie(self):
        self.assertEqual(
            _clean_media_title("师兄啊师兄 HQ 高码率 更至EP145"),
            "师兄啊师兄",
        )

        account = FakeAccount({
            "shixiong": [
                {"file_name": "师兄啊师兄.EP145.mkv", "dir": False, "fid": "f1"},
            ]
        })
        tmdb = FakeTMDB(
            tv={"id": 2025, "name": "师兄啊师兄", "first_air_date": "2023-01-19"},
            details={
                "id": 2025,
                "name": "师兄啊师兄",
                "first_air_date": "2023-01-19",
                "origin_country": ["CN"],
                "original_language": "zh",
                "last_episode_to_air": {"season_number": 1},
                "genres": [{"id": 16, "name": "Animation"}],
                "seasons": [{"season_number": 1, "episode_count": 145}],
            },
        )

        task = build_media_task_from_share(
            "https://pan.quark.cn/s/shixiong",
            "师兄啊师兄 HQ 高码率 更至EP145 https://pan.quark.cn/s/shixiong",
            account,
            {
                "task_settings": {
                    "telegram_inbox_media_root": "影视库",
                    "tv_naming_rule": "剧名 - S季数E[]",
                    "tv_ignore_extension": True,
                }
            },
            tmdb,
        )

        self.assertEqual(task["taskname"], "师兄啊师兄")
        self.assertEqual(task["content_type"], "anime")
        self.assertEqual(task["savepath"], "影视库/电视剧/国漫/师兄啊师兄/Season 01")
        self.assertEqual(task["episode_naming"], "师兄啊师兄 - S01E[]")
        self.assertEqual(task["pattern"], "师兄啊师兄 - S01E[]")
        self.assertEqual(task["replace"], "")

    def test_tv_search_uses_best_tmdb_match_not_first_result(self):
        account = FakeAccount({
            "shixiong": [
                {"file_name": "师兄啊师兄.EP145.mkv", "dir": False, "fid": "f1"},
            ]
        })
        wrong = {"id": 10, "name": "师兄", "first_air_date": "2020-01-01"}
        right = {
            "id": 2025,
            "name": "师兄啊师兄",
            "first_air_date": "2023-01-19",
            "genre_ids": [16],
            "origin_country": ["CN"],
            "original_language": "zh",
        }

        task = build_media_task_from_share(
            "https://pan.quark.cn/s/shixiong",
            "师兄啊师兄 HQ 高码率 更至EP145 https://pan.quark.cn/s/shixiong",
            account,
            {
                "task_settings": {
                    "telegram_inbox_media_root": "影视库",
                    "tv_naming_rule": "剧名 - S季数E[]",
                    "tv_ignore_extension": True,
                }
            },
            FakeTMDB(
                tv=wrong,
                tv_results=[wrong, right],
                details_by_id={
                    2025: {
                        "id": 2025,
                        "name": "师兄啊师兄",
                        "first_air_date": "2023-01-19",
                        "origin_country": ["CN"],
                        "original_language": "zh",
                        "last_episode_to_air": {"season_number": 1},
                        "genres": [{"id": 16, "name": "Animation"}],
                    }
                },
            ),
        )

        self.assertEqual(task["content_type"], "anime")
        self.assertEqual(task["library_category"], "国漫")
        self.assertEqual(task["savepath"], "影视库/电视剧/国漫/师兄啊师兄/Season 01")

    def test_tv_search_prefers_animated_biaoren_over_undated_placeholder(self):
        account = FakeAccount({
            "biaoren": [
                {"file_name": "1 4K.mp4", "dir": False, "fid": "f1"},
                {"file_name": "2 4K.mp4", "dir": False, "fid": "f2"},
            ]
        })
        placeholder = {
            "id": 265215,
            "name": "镖人",
            "first_air_date": "",
            "genre_ids": [18, 10759],
            "origin_country": ["CN"],
            "original_language": "zh",
        }
        animated = {
            "id": 107463,
            "name": "镖人",
            "first_air_date": "2023-06-01",
            "genre_ids": [16, 10759],
            "origin_country": ["CN", "JP"],
            "original_language": "zh",
        }
        season_two = {
            "id": 325228,
            "name": "镖人 第二季",
            "first_air_date": "",
            "genre_ids": [16, 10759],
            "origin_country": ["CN"],
            "original_language": "zh",
        }

        task = build_media_task_from_share(
            "https://pan.quark.cn/s/biaoren",
            "\u9556\u4eba S02 https://pan.quark.cn/s/biaoren",
            account,
            {
                "task_settings": {
                    "telegram_inbox_media_root": "影视库",
                    "tv_naming_rule": "剧名 - S季数E[]",
                    "tv_ignore_extension": True,
                }
            },
            FakeTMDB(
                tv=placeholder,
                tv_results=[placeholder, animated, season_two],
                details_by_id={
                    107463: {
                        "id": 107463,
                        "name": "镖人",
                        "first_air_date": "2023-06-01",
                        "origin_country": ["CN", "JP"],
                        "original_language": "zh",
                        "last_episode_to_air": {"season_number": 1},
                        "genres": [{"id": 16, "name": "动画"}, {"id": 10759, "name": "动作冒险"}],
                    },
                    265215: {
                        "id": 265215,
                        "name": "镖人",
                        "first_air_date": "",
                        "origin_country": ["CN"],
                        "original_language": "zh",
                        "genres": [{"id": 18, "name": "剧情"}, {"id": 10759, "name": "动作冒险"}],
                    },
                    325228: {
                        "id": 325228,
                        "name": "镖人 第二季",
                        "first_air_date": "",
                        "origin_country": ["CN"],
                        "original_language": "zh",
                        "genres": [{"id": 16, "name": "动画"}, {"id": 10759, "name": "动作冒险"}],
                        "seasons": [{"season_number": 2, "episode_count": 2, "air_date": "2026-06-11"}],
                    },
                },
            ),
        )

        self.assertEqual(task["taskname"], "镖人")
        self.assertEqual(task["content_type"], "anime")
        self.assertEqual(task["library_category"], "国漫")
        self.assertEqual(task["savepath"], "影视库/电视剧/国漫/镖人/Season 02")
        self.assertEqual(task["calendar_info"]["match"]["tmdb_id"], 325228)

    def test_tmdb_unavailable_does_not_create_uncategorized_folder_for_plain_series(self):
        account = FakeAccount({
            "blackmirror": [
                {"file_name": "黑镜.S07E01.mkv", "dir": False, "fid": "f1"},
            ]
        })

        task = build_media_task_from_share(
            "https://pan.quark.cn/s/blackmirror",
            "黑镜 S07 https://pan.quark.cn/s/blackmirror",
            account,
            {
                "task_settings": {
                    "telegram_inbox_media_root": "影视库",
                    "tv_naming_rule": "剧名 - S季数E[]",
                    "tv_ignore_extension": True,
                }
            },
            FakeTMDB(movie=None, tv=None),
        )

        self.assertEqual(task["content_type"], "tv")
        self.assertEqual(task["library_category"], "")
        self.assertEqual(task["savepath"], "影视库/电视剧/黑镜/Season 07")

    def test_media_root_keeps_non_chinese_animation_out_of_guoman(self):
        account = FakeAccount({
            "frieren": [
                {"file_name": "葬送的芙莉莲.S01E01.mkv", "dir": False, "fid": "f1"},
            ]
        })
        tmdb = FakeTMDB(
            tv={"id": 209867, "name": "葬送的芙莉莲", "first_air_date": "2023-09-29", "origin_country": ["JP"], "original_language": "ja"},
            details={
                "id": 209867,
                "name": "葬送的芙莉莲",
                "first_air_date": "2023-09-29",
                "origin_country": ["JP"],
                "original_language": "ja",
                "last_episode_to_air": {"season_number": 1},
                "genres": [{"id": 16, "name": "Animation"}],
                "seasons": [{"season_number": 1, "episode_count": 28}],
            },
        )

        task = build_media_task_from_share(
            "https://pan.quark.cn/s/frieren",
            "葬送的芙莉莲 4K S01E01 https://pan.quark.cn/s/frieren",
            account,
            {
                "task_settings": {
                    "telegram_inbox_media_root": "影视库",
                    "tv_naming_rule": "剧名 - S季数E[]",
                    "tv_ignore_extension": True,
                }
            },
            tmdb,
        )

        self.assertEqual(task["content_type"], "anime")
        self.assertEqual(task["savepath"], "影视库/电视剧/日番/葬送的芙莉莲/Season 01")

    def test_library_category_rules_match_organizer_defaults(self):
        tv_cases = [
            ({"genres": [{"id": 16}], "origin_country": ["CN"]}, "anime", "国漫"),
            ({"genres": [{"id": 16}], "origin_country": ["JP"]}, "anime", "日番"),
            ({"genres": [{"id": 99}], "origin_country": ["US"]}, "tv", "纪录片"),
            ({"genres": [{"id": 10762}], "origin_country": ["US"]}, "tv", "儿童"),
            ({"genres": [{"id": 10764}], "origin_country": ["CN"]}, "tv", "综艺"),
            ({"origin_country": ["CN"]}, "tv", "国产剧"),
            ({"origin_country": ["US"]}, "tv", "欧美剧"),
            ({"origin_country": ["KR"]}, "tv", "日韩剧"),
            ({}, "tv", "未分类"),
        ]

        for tmdb_data, content_type, expected in tv_cases:
            with self.subTest(expected=expected):
                self.assertEqual(_classify_tv_library_category("", [], tmdb_data, content_type), expected)

        movie_cases = [
            ({"genre_ids": [16], "original_language": "ja"}, "动画电影"),
            ({"original_language": "zh"}, "华语电影"),
            ({"original_language": "ko"}, "日韩电影"),
            ({"original_language": "en"}, "欧美电影"),
            ({}, "其他电影"),
        ]

        for tmdb_data, expected in movie_cases:
            with self.subTest(expected=expected):
                self.assertEqual(_classify_movie_library_category(tmdb_data), expected)

    def test_common_episode_update_formats_are_cleaned_and_detected(self):
        cases = {
            "师兄啊师兄 HQ 高码率 更至EP145": "师兄啊师兄",
            "师兄啊师兄 HQ 高码率 更至EP.145": "师兄啊师兄",
            "师兄啊师兄 4K 60帧 E145": "师兄啊师兄",
            "凡人修仙传 更新至第145话": "凡人修仙传",
            "凡人修仙传 更新至 145集": "凡人修仙传",
            "遮天 第145集 2160p 高码": "遮天",
        }

        for raw, expected in cases.items():
            with self.subTest(raw=raw):
                self.assertEqual(_clean_media_title(raw), expected)
                self.assertTrue(_looks_like_series(raw, [{"file_name": f"{raw}.mkv", "dir": False}]))

    def test_release_metadata_does_not_pollute_media_title(self):
        cases = {
            "名称：【原盘】赌侠 (1990) 1080P REMUX 国粤多音轨 中字外挂字幕": "赌侠",
            "名称：沧月星澜(2026)4K S01E01 - E18 HiveWeb": "沧月星澜",
            "名称：她战(2026)4K S01E01 - E16 HiveWeb": "她战",
            "名称：翘楚 (2026)剧情 陈都灵 4KHQHDR60FPS 更新15集": "翘楚",
            "名称：神墓(2022) 4K 帧享 更新至年番S03E46 HiveWeb": "神墓",
            "名称：任意国漫 年番 (2026)动作 动画 奇幻 4KHQ 更新46集": "任意国漫",
            "名称：测试动画年番（2026）4K HDR S03E46 HiveWeb": "测试动画",
        }

        for raw, expected in cases.items():
            with self.subTest(raw=raw):
                seed = extract_title_seed(raw)
                self.assertEqual(_clean_media_title(seed), expected)

    def test_calendar_catalog_date_is_not_treated_as_media_year(self):
        seed = extract_title_seed("名称：2026年6月11日 短剧更新目录8")

        self.assertEqual(_clean_media_title(seed), "短剧更新目录8")
        self.assertEqual(_extract_year(seed), "")
        self.assertFalse(_looks_like_series(seed, [{"file_name": seed, "dir": True}]))

    def test_release_metadata_samples_build_expected_library_tasks(self):
        account = FakeAccount({
            "du": [{"file_name": "赌侠.1990.1080P.REMUX.mkv", "dir": False, "fid": "f1"}],
            "cang": [{"file_name": "沧月星澜.S01E01.mkv", "dir": False, "fid": "f2"}],
            "tazhan": [{"file_name": "她战.S01E01.mkv", "dir": False, "fid": "f3"}],
        })

        movie_task = build_media_task_from_share(
            "https://pan.quark.cn/s/du",
            "名称：【原盘】赌侠 (1990) 1080P REMUX 国粤多音轨 中字外挂字幕",
            account,
            {"task_settings": {"telegram_inbox_media_root": "影视库"}},
            FakeTMDB(movie={"id": 624, "title": "赌侠", "release_date": "1990-12-13", "original_language": "zh"}),
        )
        self.assertEqual(movie_task["taskname"], "赌侠")
        self.assertEqual(movie_task["content_type"], "movie")
        self.assertEqual(movie_task["savepath"], "影视库/电影/华语电影/赌侠 (1990)")

        cang_task = build_media_task_from_share(
            "https://pan.quark.cn/s/cang",
            "名称：沧月星澜(2026)4K S01E01 - E18 HiveWeb",
            account,
            {
                "task_settings": {
                    "telegram_inbox_media_root": "影视库",
                    "tv_naming_rule": "剧名 - S季数E[]",
                }
            },
            FakeTMDB(
                tv={"id": 1001, "name": "沧月星澜", "first_air_date": "2026-01-01"},
                details={"id": 1001, "name": "沧月星澜", "first_air_date": "2026-01-01", "origin_country": ["CN"], "last_episode_to_air": {"season_number": 1}},
            ),
        )
        self.assertEqual(cang_task["taskname"], "沧月星澜")
        self.assertEqual(cang_task["content_type"], "tv")
        self.assertEqual(cang_task["savepath"], "影视库/电视剧/国产剧/沧月星澜/Season 01")

        tazhan_task = build_media_task_from_share(
            "https://pan.quark.cn/s/tazhan",
            "名称：她战(2026)4K S01E01 - E16 HiveWeb",
            account,
            {
                "task_settings": {
                    "telegram_inbox_media_root": "影视库",
                    "tv_naming_rule": "剧名 - S季数E[]",
                }
            },
            FakeTMDB(
                tv={"id": 1002, "name": "她战", "first_air_date": "2026-01-01"},
                details={"id": 1002, "name": "她战", "first_air_date": "2026-01-01", "origin_country": ["CN"], "last_episode_to_air": {"season_number": 1}},
            ),
        )
        self.assertEqual(tazhan_task["taskname"], "她战")
        self.assertEqual(tazhan_task["content_type"], "tv")
        self.assertEqual(tazhan_task["savepath"], "影视库/电视剧/国产剧/她战/Season 01")

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

    def test_service_runs_created_task_snapshot_even_if_save_hook_mutates_config(self):
        account = FakeAccount({"nitian": [{"file_name": "S01E41.mp4", "dir": False, "fid": "f1"}]})
        config = {
            "push_config": {"TG_USER_ID": "42"},
            "tasklist": [],
            "task_settings": {
                "telegram_inbox_media_root": "影视库",
                "tv_naming_rule": "剧名 - S季数E[]",
            },
        }
        runs = []

        def mutate_during_save(data):
            task = data["tasklist"][-1]
            task["savepath"] = "影视库/电视剧/逆天邪神/Season 01"
            task["content_type"] = "tv"
            task["library_category"] = ""

        service = TelegramAutoCreateService(
            config,
            account_factory=lambda: account,
            tmdb_factory=lambda: FakeTMDB(
                tv_results=[{
                    "id": 235643,
                    "name": "逆天邪神",
                    "first_air_date": "2023-09-23",
                    "genre_ids": [16, 10759, 10765],
                    "origin_country": ["CN"],
                    "original_language": "zh",
                }],
                details_by_id={
                    235643: {
                        "id": 235643,
                        "name": "逆天邪神",
                        "first_air_date": "2023-09-23",
                        "origin_country": ["CN"],
                        "original_language": "zh",
                        "last_episode_to_air": {"season_number": 1},
                        "genres": [{"id": 16, "name": "Animation"}],
                    }
                },
            ),
            save_config=mutate_during_save,
            run_task=lambda task, index: runs.append(copy.deepcopy(task)),
        )

        result = service.handle_message({
            "message_id": 3,
            "chat": {"id": 42},
            "from": {"id": 42},
            "text": "逆天邪神 https://pan.quark.cn/s/nitian",
        })

        self.assertEqual(result.status, "created")
        self.assertEqual(runs[0]["savepath"], "影视库/电视剧/国漫/逆天邪神/Season 01")
        self.assertEqual(runs[0]["content_type"], "anime")
        self.assertEqual(runs[0]["library_category"], "国漫")

    def test_repair_media_library_task_restores_tmdb_category_path(self):
        task = {
            "taskname": "逆天邪神",
            "shareurl": "https://pan.quark.cn/s/nitian",
            "savepath": "影视库/电视剧/逆天邪神/Season 01",
            "pattern": "逆天邪神 - S01E[]",
            "episode_naming": "逆天邪神 - S01E[]",
            "content_type": "tv",
            "library_category": "",
            "calendar_info": {
                "extracted": {
                    "show_name": "逆天邪神",
                    "year": "2023",
                    "content_type": "tv",
                    "library_category": "",
                    "season_number": 1,
                },
                "match": {
                    "matched_show_name": "逆天邪神",
                    "matched_year": "2023",
                    "tmdb_id": 235643,
                    "latest_season_number": 1,
                    "latest_season_fetch_url": "/tv/235643/season/1",
                },
            },
        }

        changed = repair_media_library_task(
            task,
            {
                "task_settings": {
                    "telegram_inbox_media_root": "影视库",
                    "tv_naming_rule": "剧名 - S季数E[]",
                    "tv_ignore_extension": True,
                }
            },
            FakeTMDB(
                details_by_id={
                    235643: {
                        "id": 235643,
                        "name": "逆天邪神",
                        "first_air_date": "2023-09-23",
                        "origin_country": ["CN"],
                        "original_language": "zh",
                        "genres": [{"id": 16, "name": "Animation"}],
                        "last_episode_to_air": {"season_number": 1},
                    }
                }
            ),
        )

        self.assertTrue(changed)
        self.assertEqual(task["savepath"], "影视库/电视剧/国漫/逆天邪神/Season 01")
        self.assertEqual(task["content_type"], "anime")
        self.assertEqual(task["library_category"], "国漫")
        self.assertEqual(task["episode_naming"], "逆天邪神 - S01E[]")
        self.assertEqual(task["calendar_info"]["extracted"]["content_type"], "anime")
        self.assertEqual(task["calendar_info"]["extracted"]["library_category"], "国漫")

    def test_repair_media_library_tasks_rewrites_existing_config_tasks(self):
        config = {
            "task_settings": {
                "telegram_inbox_media_root": "影视库",
                "tv_naming_rule": "剧名 - S季数E[]",
            },
            "tasklist": [{
                "taskname": "逆天邪神",
                "shareurl": "https://pan.quark.cn/s/nitian",
                "savepath": "影视库/电视剧/逆天邪神/Season 01",
                "pattern": "逆天邪神 - S01E[]",
                "episode_naming": "逆天邪神 - S01E[]",
                "content_type": "tv",
                "library_category": "",
                "calendar_info": {
                    "extracted": {
                        "show_name": "逆天邪神",
                        "year": "2023",
                        "content_type": "tv",
                        "library_category": "",
                        "season_number": 1,
                    },
                    "match": {
                        "matched_show_name": "逆天邪神",
                        "matched_year": "2023",
                        "tmdb_id": 235643,
                        "latest_season_number": 1,
                        "latest_season_fetch_url": "/tv/235643/season/1",
                    },
                },
            }],
        }

        changed = repair_media_library_tasks(
            config,
            FakeTMDB(
                details_by_id={
                    235643: {
                        "id": 235643,
                        "name": "逆天邪神",
                        "first_air_date": "2023-09-23",
                        "origin_country": ["CN"],
                        "original_language": "zh",
                        "genres": [{"id": 16, "name": "Animation"}],
                        "last_episode_to_air": {"season_number": 1},
                    }
                }
            ),
        )

        self.assertTrue(changed)
        self.assertEqual(config["tasklist"][0]["savepath"], "影视库/电视剧/国漫/逆天邪神/Season 01")
        self.assertEqual(config["tasklist"][0]["content_type"], "anime")
        self.assertEqual(config["tasklist"][0]["library_category"], "国漫")

    def test_series_tmdb_match_retries_without_misleading_year_for_category(self):
        class YearSensitiveTMDB(FakeTMDB):
            def __init__(self):
                super().__init__(
                    tv_results=[{
                        "id": 235643,
                        "name": "逆天邪神",
                        "first_air_date": "2023-09-23",
                        "genre_ids": [16, 10759, 10765],
                        "origin_country": ["CN"],
                        "original_language": "zh",
                    }],
                    details_by_id={
                        235643: {
                            "id": 235643,
                            "name": "逆天邪神",
                            "first_air_date": "2023-09-23",
                            "origin_country": ["CN"],
                            "original_language": "zh",
                            "genres": [{"id": 16, "name": "Animation"}],
                            "last_episode_to_air": {"season_number": 1},
                        }
                    },
                )
                self.calls = []

            def search_tv_show_all(self, query, year=None):
                self.calls.append(("all", query, year))
                if year:
                    return []
                return self.tv_results

            def search_tv_show(self, query, year=None):
                self.calls.append(("one", query, year))
                if year:
                    return None
                return self.tv_results[0]

        tmdb = YearSensitiveTMDB()
        task = build_media_task_from_share(
            "https://pan.quark.cn/s/nitian",
            "逆天邪神 (2026) S01E41 https://pan.quark.cn/s/nitian",
            FakeAccount({"nitian": [{"file_name": "S01E41.mp4", "dir": False, "fid": "f1"}]}),
            {
                "task_settings": {
                    "telegram_inbox_media_root": "影视库",
                    "tv_naming_rule": "剧名 - S季数E[]",
                }
            },
            tmdb,
        )

        self.assertIn(("all", "逆天邪神", "2026"), tmdb.calls)
        self.assertIn(("all", "逆天邪神", None), tmdb.calls)
        self.assertEqual(task["savepath"], "影视库/电视剧/国漫/逆天邪神/Season 01")
        self.assertEqual(task["content_type"], "anime")
        self.assertEqual(task["library_category"], "国漫")

    def test_extract_title_seed_ignores_url_noise(self):
        self.assertEqual(
            extract_title_seed("  牧神记 S01\nhttps://pan.quark.cn/s/abc  "),
            "牧神记 S01",
        )

    def test_poller_deletes_webhook_before_long_polling(self):
        session = FakeTelegramSession()
        config = {
            "push_config": {
                "TG_INBOX_AUTO_CREATE": "enabled",
                "TG_BOT_TOKEN": "token",
                "TG_USER_ID": "42",
                "TG_INBOX_LAST_UPDATE_ID": 0,
            }
        }
        poller = TelegramInboxPoller(
            config_getter=lambda: config,
            service_factory=lambda cfg: None,
            state_saver=lambda cfg: None,
            session=session,
        )

        processed = poller.poll_once()

        self.assertEqual(processed, 0)
        self.assertEqual(session.calls[0][0], "POST")
        self.assertTrue(session.calls[0][1].endswith("/deleteWebhook"))
        self.assertEqual(session.calls[1][0], "GET")
        self.assertTrue(session.calls[1][1].endswith("/getUpdates"))


if __name__ == "__main__":
    unittest.main()
