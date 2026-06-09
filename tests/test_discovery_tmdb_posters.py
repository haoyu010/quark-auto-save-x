import unittest

from app.sdk.douban_service import DoubanService


class FakeTMDBService:
    def __init__(self, movie_result=None, tv_result=None):
        self.movie_result = movie_result
        self.tv_result = tv_result
        self.movie_calls = []
        self.tv_calls = []

    def is_configured(self):
        return True

    def search_movie(self, query, year=None):
        self.movie_calls.append((query, year))
        return self.movie_result

    def search_tv_show(self, query, year=None):
        self.tv_calls.append((query, year))
        return self.tv_result

    def build_image_url(self, poster_path, size="w500"):
        return f"https://image.tmdb.org/t/p/{size}{poster_path}"


class DiscoveryTMDBPosterTest(unittest.TestCase):
    def test_enrich_items_prefers_tmdb_poster_when_available(self):
        items = [
            {
                "title": "\u6d41\u6d6a\u5730\u7403",
                "year": "2019",
                "content_type": "movie",
                "pic": {"normal": "https://img.doubanio.com/view/photo/s_ratio_poster/public/p2545472803.jpg"},
            }
        ]
        tmdb = FakeTMDBService(movie_result={"id": 535167, "poster_path": "/fhm3BrS4jrIhz2zUj7bveYw4hGZ.jpg"})

        DoubanService().enrich_items_with_tmdb_posters(items, tmdb)

        self.assertEqual(tmdb.movie_calls, [("\u6d41\u6d6a\u5730\u7403", "2019")])
        self.assertEqual(
            items[0]["pic"]["normal"],
            "https://image.tmdb.org/t/p/w500/fhm3BrS4jrIhz2zUj7bveYw4hGZ.jpg",
        )
        self.assertEqual(
            items[0]["pic"]["douban"],
            "https://img.doubanio.com/view/photo/s_ratio_poster/public/p2545472803.jpg",
        )
        self.assertEqual(items[0]["tmdb_id"], 535167)
        self.assertEqual(items[0]["image_source"], "tmdb")

    def test_enrich_items_uses_tv_search_for_non_movie_content(self):
        items = [
            {
                "title": "\u9ed1\u955c",
                "year": "2011",
                "content_type": "tv",
                "pic": {"normal": ""},
            }
        ]
        tmdb = FakeTMDBService(tv_result={"id": 42009, "poster_path": "/7PRddO7z7mcPi21nZTCMGShAyy1.jpg"})

        DoubanService().enrich_items_with_tmdb_posters(items, tmdb)

        self.assertEqual(tmdb.tv_calls, [("\u9ed1\u955c", "2011")])
        self.assertEqual(
            items[0]["pic"]["normal"],
            "https://image.tmdb.org/t/p/w500/7PRddO7z7mcPi21nZTCMGShAyy1.jpg",
        )

    def test_enrich_items_keeps_existing_poster_when_tmdb_has_no_match(self):
        items = [
            {
                "title": "\u672a\u77e5\u7247",
                "year": "2026",
                "content_type": "movie",
                "pic": {"normal": "https://img.doubanio.com/view/photo/public/existing.jpg"},
            }
        ]
        tmdb = FakeTMDBService(movie_result=None)

        DoubanService().enrich_items_with_tmdb_posters(items, tmdb)

        self.assertEqual(items[0]["pic"]["normal"], "https://img.doubanio.com/view/photo/public/existing.jpg")
        self.assertNotIn("image_source", items[0])

    def test_enrich_items_respects_max_items_for_discovery_speed(self):
        items = [
            {
                "title": f"movie-{index}",
                "year": "2026",
                "content_type": "movie",
                "pic": {"normal": f"https://img.doubanio.com/view/photo/public/{index}.jpg"},
            }
            for index in range(6)
        ]
        tmdb = FakeTMDBService(movie_result={"id": 100, "poster_path": "/poster.jpg"})

        DoubanService().enrich_items_with_tmdb_posters(items, tmdb, max_items=2)

        self.assertEqual(tmdb.movie_calls, [("movie-0", "2026"), ("movie-1", "2026")])
        self.assertEqual(items[0]["image_source"], "tmdb")
        self.assertEqual(items[1]["image_source"], "tmdb")
        self.assertNotIn("image_source", items[2])


if __name__ == "__main__":
    unittest.main()
