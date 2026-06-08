import tempfile
import unittest
from pathlib import Path

from app.sdk.version import read_project_version, resolve_app_version


class VersionTest(unittest.TestCase):
    def test_reads_version_file(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            version_file = Path(temp_dir) / "VERSION"
            version_file.write_text("1.0.0\n", encoding="utf-8")

            self.assertEqual(read_project_version(version_file), "1.0.0")

    def test_resolve_app_version_prefers_build_tag(self):
        self.assertEqual(
            resolve_app_version(build_tag="v1.0.1", build_sha="abcdef123456"),
            "v1.0.1",
        )

    def test_resolve_app_version_uses_version_file_when_no_build_tag(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            version_file = Path(temp_dir) / "VERSION"
            version_file.write_text("1.0.2\n", encoding="utf-8")

            self.assertEqual(
                resolve_app_version(version_file=version_file),
                "1.0.2",
            )


if __name__ == "__main__":
    unittest.main()
