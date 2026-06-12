import unittest

import quark_auto_save


class PartialEpisodeRenameAccount:
    def __init__(self, savepath, files, rename_old_name, rename_new_name):
        self.nickname = "tester"
        self.files = [dict(item) for item in files]
        self.savepath_fid = {f"/{savepath}": "target"}
        self.rename_old_name = rename_old_name
        self.rename_new_name = rename_new_name
        self.episode_patterns = []

    def update_savepath_fid(self, tasklist):
        return None

    def do_save_task(self, task):
        tree = quark_auto_save.Tree()
        tree.create_node(
            f"/{task['savepath']}",
            "root",
            data={"is_dir": True},
        )
        for item in self.files:
            tree.create_node(
                item["file_name"],
                item["fid"],
                parent="root",
                data={
                    "is_dir": False,
                    "path": f"/{task['savepath']}/{item['file_name']}",
                },
            )
        return tree

    def do_rename_task(self, task):
        for item in self.files:
            if item["file_name"] == self.rename_old_name:
                item["file_name"] = self.rename_new_name
                break
        return True, [f"重命名: {self.rename_old_name} → {self.rename_new_name}"]

    def get_actual_file_names_from_directory(self, task, rename_logs):
        return {self.rename_old_name: self.rename_new_name}

    def ls_dir(self, fid):
        if fid == "target":
            return [dict(item) for item in self.files]
        return []

    def _is_auto_extract_enabled(self, mode):
        return False

    def process_rename_logs(self, task, rename_logs):
        return None


class EpisodeNotificationTreeTest(unittest.TestCase):
    def tearDown(self):
        quark_auto_save.CONFIG_DATA = {}
        quark_auto_save.NOTIFYS = []

    def test_episode_notification_keeps_unrenamed_transferred_files(self):
        savepath = "影视库/电视剧/综艺/超燃青春的合唱/Season 01"
        files = [
            {"file_name": "20260610.未播.mp4", "fid": "f1", "dir": False},
            {"file_name": "20260607.未播.mp4", "fid": "f2", "dir": False},
            {"file_name": "20260606.未播.mp4", "fid": "f3", "dir": False},
            {"file_name": "20260606.纯享版.mp4", "fid": "f4", "dir": False},
            {"file_name": "20260603.未播.mp4", "fid": "f5", "dir": False},
            {"file_name": "20260604.第7期尝鲜.mp4", "fid": "f6", "dir": False},
            {"file_name": "20260605.第7期上.mp4", "fid": "f7", "dir": False},
            {"file_name": "20260605.第7期中.mp4", "fid": "f8", "dir": False},
            {"file_name": "20260605.第7期下.mp4", "fid": "f9", "dir": False},
        ]
        account = PartialEpisodeRenameAccount(
            savepath,
            files,
            "20260604.第7期尝鲜.mp4",
            "超燃青春的合唱 - S01E07.mp4",
        )
        task = {
            "taskname": "超燃青春的合唱",
            "shareurl": "https://pan.quark.cn/s/48413f0ba8b7",
            "savepath": savepath,
            "use_episode_naming": True,
            "episode_naming": "超燃青春的合唱 - S01E[]",
        }
        quark_auto_save.CONFIG_DATA = {"push_notify_type": "full"}
        quark_auto_save.NOTIFYS = []

        quark_auto_save.do_save(account, [task], ignore_execution_rules=True)

        notification = "\n".join(quark_auto_save.NOTIFYS)
        self.assertIn("超燃青春的合唱 - S01E07.mp4", notification)
        self.assertIn("20260610.未播.mp4", notification)
        self.assertIn("20260605.第7期上.mp4", notification)
        file_lines = [
            line
            for line in quark_auto_save.NOTIFYS
            if line.startswith(("├── ", "└── "))
        ]
        self.assertEqual(len(file_lines), 9)


if __name__ == "__main__":
    unittest.main()
