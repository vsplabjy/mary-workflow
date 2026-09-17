from __future__ import annotations

from pathlib import Path
import shutil
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from mw_surfaces import COMMAND_SKILLS, expected_outputs, generate, skill_parts


class GeneratedSurfacesTests(unittest.TestCase):
    def test_checked_in_surfaces_are_current(self):
        self.assertEqual(generate(ROOT, check=True), [])

    def test_entrypoints_route_to_actual_skills_and_alias(self):
        outputs = expected_outputs(ROOT)
        for command, skill in COMMAND_SKILLS.items():
            self.assertIn(f"skills/{skill}/SKILL.md", outputs[ROOT / f"commands/{command}.md"])
        self.assertNotIn("mw-model", COMMAND_SKILLS)
        self.assertEqual(COMMAND_SKILLS["mw-review"], "exam-review")
        self.assertEqual(COMMAND_SKILLS["slide-learning"], "slide-to-lecture")

    def test_drift_check_is_read_only_then_regeneration_repairs_it(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            shutil.copytree(ROOT / "skills", root / "skills")
            shutil.copytree(ROOT / "references/phases", root / "references/phases")
            self.assertTrue(generate(root, check=True))
            self.assertFalse((root / "commands").exists())
            generate(root)
            target = root / "commands/mw-run.md"
            target.write_text("manual edit\n")
            self.assertEqual(generate(root, check=True), ["commands/mw-run.md"])
            self.assertEqual(target.read_text(), "manual edit\n")
            generate(root)
            self.assertEqual(generate(root, check=True), [])
            source = root / "references/phases/mw-execute.md"
            source.write_text(source.read_text() + "\nUpdated protocol.\n")
            self.assertEqual(generate(root, check=True), [".mary-workflow/prompts/mw-execute.md"])

    def test_skills_have_valid_required_metadata(self):
        for skill in [ROOT / "SKILL.md", *(ROOT / "skills").glob("*/SKILL.md")]:
            with self.subTest(skill=skill):
                description, body = skill_parts(skill)
                self.assertTrue(description.strip())
                self.assertTrue(body.strip())

    def test_malformed_frontmatter_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "SKILL.md"
            path.write_text("---\nname: sample\n---\nBody\n")
            with self.assertRaisesRegex(ValueError, "description"):
                skill_parts(path)


if __name__ == "__main__":
    unittest.main()
