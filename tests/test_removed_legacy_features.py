import copy
import json
import unittest
from pathlib import Path

from quark_auto_save import Config


ROOT = Path(__file__).resolve().parents[1]


class RemovedLegacyFeaturesTest(unittest.TestCase):
    forbidden_labels = [
        "CloudSaver",
        "PanSou",
        "AList Strm",
        "AList Strm Gen",
        "Aria2",
        "Emby",
        "Plex",
    ]

    def test_runtime_ui_and_default_config_do_not_expose_removed_features(self):
        checked_files = [
            ROOT / "app" / "run.py",
            ROOT / "app" / "templates" / "index.html",
            ROOT / "quark_config.json",
            ROOT / "README.md",
        ]

        for path in checked_files:
            content = path.read_text(encoding="utf-8")
            for label in self.forbidden_labels:
                self.assertNotIn(label, content, f"{label} still appears in {path}")

    def test_config_migration_drops_legacy_sources_and_plugins(self):
        config = {
            "source": {
                "cloudsaver": {"server": "http://old"},
                "pansou": {"server": "http://old"},
            },
            "media_servers": {
                "emby": {"url": "http://old", "token": "secret"},
            },
            "plugins": {
                "plex": {"url": "http://old"},
                "alist": {"url": "http://old"},
            },
            "task_settings": {"auto_replace_sources": ["pansou", "cloudsaver"]},
            "tasklist": [
                {"taskname": "A", "addition": {"emby": {"media_id": "1"}, "aria2": {"pause": False}}},
            ],
        }
        original = copy.deepcopy(config)

        Config.breaking_change_update(config)

        self.assertNotIn("media_servers", config)
        self.assertEqual(config.get("plugins"), {})
        self.assertNotIn("cloudsaver", config["source"])
        self.assertNotIn("pansou", config["source"])
        self.assertIn("telegram", config["source"])
        self.assertEqual(config["task_settings"]["auto_replace_sources"], ["telegram"])
        self.assertEqual(config["tasklist"][0].get("addition"), {})
        self.assertNotEqual(config, original)

    def test_default_config_contains_only_telegram_search_source(self):
        config = json.loads((ROOT / "quark_config.json").read_text(encoding="utf-8"))

        self.assertEqual(list(config.get("source", {}).keys()), ["telegram"])
        self.assertNotIn("media_servers", config)
        self.assertEqual(config["task_settings"]["auto_replace_sources"], ["telegram"])


if __name__ == "__main__":
    unittest.main()
