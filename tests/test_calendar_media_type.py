import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "app"
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

from app import run as run_module


class CalendarMediaTypeTest(unittest.TestCase):
    def test_explicit_movie_task_is_not_tv_calendar_content(self):
        self.assertFalse(run_module.is_tv_calendar_content({"content_type": "movie"}))
        self.assertFalse(run_module.is_tv_calendar_content({
            "calendar_info": {"extracted": {"content_type": "movie"}}
        }))

    def test_tv_like_and_legacy_tasks_still_use_tv_calendar_content(self):
        self.assertTrue(run_module.is_tv_calendar_content({"content_type": "tv"}))
        self.assertTrue(run_module.is_tv_calendar_content({"content_type": "anime"}))
        self.assertTrue(run_module.is_tv_calendar_content({}))

    def test_explicit_movie_show_is_not_tv_calendar_content(self):
        self.assertFalse(run_module.is_tv_calendar_show({"content_type": "movie"}))
        self.assertTrue(run_module.is_tv_calendar_show({"content_type": "tv"}))
        self.assertTrue(run_module.is_tv_calendar_show({}))


if __name__ == "__main__":
    unittest.main()
