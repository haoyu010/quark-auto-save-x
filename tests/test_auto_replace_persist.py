import os
import unittest
from unittest.mock import patch

import quark_auto_save


class AutoReplacePersistTest(unittest.TestCase):
    def tearDown(self):
        quark_auto_save.CONFIG_DATA = {}

    def test_manual_single_task_replacement_merges_back_to_config_by_original_index(self):
        quark_auto_save.CONFIG_DATA = {
            "tasklist": [
                {
                    "taskname": "Show S01",
                    "shareurl": "old",
                    "shareurl_ban": "expired",
                },
                {
                    "taskname": "Other",
                    "shareurl": "other",
                    "shareurl_ban": None,
                },
            ]
        }
        runtime_task = {
            "taskname": "Show S01",
            "shareurl": "https://pan.quark.cn/s/new",
            "shareurl_ban": None,
        }

        with patch.dict(os.environ, {"ORIGINAL_TASK_INDEX": "1"}):
            changed = quark_auto_save.persist_auto_replaced_shareurl(
                runtime_task,
                {"old_shareurl": "old"},
            )

        self.assertTrue(changed)
        self.assertEqual(
            quark_auto_save.CONFIG_DATA["tasklist"][0]["shareurl"],
            "https://pan.quark.cn/s/new",
        )
        self.assertIsNone(quark_auto_save.CONFIG_DATA["tasklist"][0].get("shareurl_ban"))
        self.assertEqual(quark_auto_save.CONFIG_DATA["tasklist"][1]["shareurl"], "other")


if __name__ == "__main__":
    unittest.main()
