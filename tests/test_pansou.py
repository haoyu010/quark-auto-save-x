import unittest

from app.sdk.pansou import PanSou


class FakeResponse:
    def json(self):
        return {"code": 0, "data": {"results": []}}


class FakeSession:
    def __init__(self):
        self.headers = {}
        self.get_calls = []

    def get(self, url, **kwargs):
        self.get_calls.append((url, kwargs))
        return FakeResponse()


class PanSouTimeoutTest(unittest.TestCase):
    def test_request_json_uses_configured_timeout(self):
        client = PanSou("https://pansou.example", timeout=6)
        fake_session = FakeSession()
        client.session = fake_session

        client._request_json("https://pansou.example/api/search", {"kw": "Show"})

        self.assertEqual(fake_session.get_calls[0][1]["timeout"], 6)


if __name__ == "__main__":
    unittest.main()
