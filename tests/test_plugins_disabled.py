import unittest

from quark_auto_save import Config


class PluginsDisabledTest(unittest.TestCase):
    def test_plugins_are_not_loaded(self):
        plugins, plugin_config, task_plugin_config = Config.load_plugins()

        self.assertEqual(plugins, {})
        self.assertEqual(plugin_config, {})
        self.assertEqual(task_plugin_config, {})


if __name__ == "__main__":
    unittest.main()
