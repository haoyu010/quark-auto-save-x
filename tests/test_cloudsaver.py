import unittest

from app.sdk.cloudsaver import CloudSaver


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def json(self):
        return self.payload


class FakeSession:
    def __init__(self):
        self.headers = {}
        self.get_calls = []
        self.post_calls = []

    def get(self, url, **kwargs):
        self.get_calls.append((url, kwargs))
        return FakeResponse({"success": True, "data": []})

    def post(self, url, **kwargs):
        self.post_calls.append((url, kwargs))
        return FakeResponse({"success": True, "data": {"token": "new-token"}})


class CloudSaverTimeoutTest(unittest.TestCase):
    def test_search_uses_configured_timeout(self):
        client = CloudSaver("https://cloudsaver.example", timeout=7)
        fake_session = FakeSession()
        client.session = fake_session

        result = client.search("Show")

        self.assertTrue(result["success"])
        self.assertEqual(fake_session.get_calls[0][1]["timeout"], 7)

    def test_login_uses_configured_timeout(self):
        client = CloudSaver("https://cloudsaver.example", timeout=7)
        fake_session = FakeSession()
        client.session = fake_session
        client.set_auth("user", "pass")

        result = client.login()

        self.assertTrue(result["success"])
        self.assertEqual(fake_session.post_calls[0][1]["timeout"], 7)


if __name__ == "__main__":
    unittest.main()
