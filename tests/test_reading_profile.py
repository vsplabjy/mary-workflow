from __future__ import annotations

from pathlib import Path
import sys
import tempfile
import unittest


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from mw_reading_profile import (  # noqa: E402
    DEFAULT_READING_PROFILE_PATH,
    default_reading_profile,
    ensure_reading_profile,
)


class ReadingProfileTests(unittest.TestCase):
    def test_new_project_uses_the_versioned_default_without_overwriting_edits(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            path, created = ensure_reading_profile(project)
            self.assertTrue(created)
            self.assertEqual(path.read_text(encoding="utf-8"), default_reading_profile())
            self.assertEqual(DEFAULT_READING_PROFILE_PATH, REPO_ROOT / "defaults" / "reading-profile.md")

            path.write_text("<!-- mary-reading-profile:v1 -->\n\n# My profile\n", encoding="utf-8")
            preserved, created = ensure_reading_profile(project)
            self.assertFalse(created)
            self.assertEqual(preserved.read_text(encoding="utf-8"), "<!-- mary-reading-profile:v1 -->\n\n# My profile\n")


if __name__ == "__main__":
    unittest.main()
