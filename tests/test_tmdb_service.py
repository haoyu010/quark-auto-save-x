import logging
import unittest

import requests

from app.sdk.tmdb_service import TMDBService


class FakeResponse:
    def __init__(self, status_code, payload=None):
        self.status_code = status_code
        self.payload = payload or {}

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"{self.status_code} Client Error", response=self)

    def json(self):
        return self.payload


class FakeSession:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def get(self, url, params=None, timeout=None):
        self.calls.append((url, dict(params or {}), timeout))
        if self.responses:
            return self.responses.pop(0)
        return FakeResponse(200, {"ok": True})


class TMDBServiceTest(unittest.TestCase):
    def test_404_returns_none_without_backup_retry_and_is_cached(self):
        service = TMDBService("key", request_timeout=1)
        session = FakeSession([FakeResponse(404)])
        service.session = session

        with self.assertLogs("app.sdk.tmdb_service", level=logging.DEBUG) as logs:
            first = service._make_request("/tv/1305781")
            second = service._make_request("/tv/1305781")

        self.assertIsNone(first)
        self.assertIsNone(second)
        self.assertEqual(len(session.calls), 1)
        self.assertTrue(session.calls[0][0].endswith("/tv/1305781"))
        self.assertFalse(any("备用地址" in item and "失败" in item for item in logs.output))
        self.assertEqual(service.get_current_api_url(), service.primary_url)


if __name__ == "__main__":
    unittest.main()
