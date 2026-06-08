import unittest
from unittest.mock import patch

from app.sdk.douban_service import DoubanService


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload
        self.text = "ok"

    def raise_for_status(self):
        return None

    def json(self):
        return self.payload


class FakeSession:
    def __init__(self, payload):
        self.payload = payload
        self.headers = {}
        self.last_url = None
        self.last_params = None

    def get(self, url, params=None, timeout=None):
        self.last_url = url
        self.last_params = params
        return FakeResponse(self.payload)


class DoubanSearchTest(unittest.TestCase):
    def test_search_subjects_normalizes_items_for_discovery_wall(self):
        payload = {
            "subjects": {
                "items": [
                    {
                        "target": {
                            "id": "7054120",
                            "title": "黑镜 第一季",
                            "year": "2011",
                            "uri": "douban://douban.com/tv/7054120",
                            "cover_url": "https://qnmob3.doubanio.com/view/photo/large/public/p1403875505.jpg",
                            "card_subtitle": "英国 / 剧情 科幻 惊悚 / 奥图·巴瑟赫斯特 / 罗里·金尼尔",
                            "rating": {"value": 9.4},
                            "abstract": "一部关于技术与社会的黑色寓言剧。",
                        }
                    }
                ]
            }
        }
        fake_session = FakeSession(payload)

        with patch("app.sdk.douban_service.requests.Session", return_value=fake_session):
            result = DoubanService().search_subjects("黑镜", content_type="tv", limit=5)

        self.assertTrue(result["success"])
        self.assertEqual(fake_session.last_params["q"], "黑镜")
        self.assertEqual(fake_session.last_params["type"], "movie")
        item = result["data"]["items"][0]
        self.assertEqual(item["id"], "7054120")
        self.assertEqual(item["title"], "黑镜 第一季")
        self.assertEqual(item["year"], "2011")
        self.assertEqual(item["content_type"], "tv")
        self.assertEqual(item["search_source"], "douban")
        self.assertEqual(item["url"], "https://movie.douban.com/subject/7054120/")
        self.assertEqual(
            item["pic"]["normal"],
            "https://qnmob3.doubanio.com/view/photo/large/public/p1403875505.jpg?imageView2/0/q/95/format/jpg",
        )
        self.assertEqual(
            item["card_subtitle"],
            "2011 / 英国 / 剧情 科幻 惊悚 / 奥图·巴瑟赫斯特 / 罗里·金尼尔",
        )
        self.assertEqual(item["summary"], "一部关于技术与社会的黑色寓言剧。")

    def test_search_subjects_rejects_blank_keyword(self):
        result = DoubanService().search_subjects("  ")

        self.assertFalse(result["success"])
        self.assertEqual(result["data"]["items"], [])

    def test_search_subjects_upgrades_mobile_thumbnail_query_for_high_quality_poster(self):
        payload = {
            "subjects": {
                "items": [
                    {
                        "target": {
                            "id": "7054120",
                            "title": "Black Mirror",
                            "year": "2011",
                            "uri": "douban://douban.com/tv/7054120",
                            "cover_url": "https://qnmob3.doubanio.com/view/photo/large/public/p1403875505.jpg?imageView2/0/q/80/w/9999/h/120/format/jpg",
                        }
                    }
                ]
            }
        }
        fake_session = FakeSession(payload)

        with patch("app.sdk.douban_service.requests.Session", return_value=fake_session):
            result = DoubanService().search_subjects("Black Mirror", content_type="tv", limit=5)

        item = result["data"]["items"][0]
        self.assertEqual(
            item["pic"]["normal"],
            "https://qnmob3.doubanio.com/view/photo/large/public/p1403875505.jpg?imageView2/0/q/95/format/jpg",
        )


if __name__ == "__main__":
    unittest.main()
