from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import unittest


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from validate_marp_assets import validate_marp_assets  # noqa: E402


class MarpAssetContractTests(unittest.TestCase):
    def test_vendor_tree_is_local_and_complete(self) -> None:
        report = validate_marp_assets()
        self.assertEqual(report["remote_urls"], 0)
        self.assertEqual(report["katex_fonts"], 20)
        self.assertEqual(report["noto_fonts"], 2)
        self.assertGreaterEqual(report["resolved_local_urls"], 30)
        self.assertEqual(report["embedded_urls"], report["resolved_local_urls"])

    def test_validator_cli_reports_the_asset_closure(self) -> None:
        completed = subprocess.run(
            [sys.executable, str(REPO_ROOT / "scripts/validate_marp_assets.py")],
            cwd=REPO_ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True,
        )
        report = json.loads(completed.stdout)
        self.assertEqual(report["theme"], "assets/marp/themes/mary-shanghaitech-red.css")
        self.assertEqual(report["remote_urls"], 0)

    def test_compiled_theme_is_current_and_registered_for_the_workspace(self) -> None:
        completed = subprocess.run(
            [sys.executable, str(REPO_ROOT / "scripts/build_marp_theme.py"), "--check"],
            cwd=REPO_ROOT / "tests",
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True,
        )
        self.assertIn("embedded_urls=", completed.stdout)

        settings = json.loads(
            (REPO_ROOT / ".vscode/settings.json").read_text(encoding="utf-8")
        )
        theme = settings["markdown.marp.themes"][0]
        self.assertEqual(
            (REPO_ROOT / theme).resolve(),
            (REPO_ROOT / "assets/marp/themes/mary-shanghaitech-red.css").resolve(),
        )

    def test_p4_does_not_claim_the_slides_stage_is_implemented(self) -> None:
        paper_skill = (REPO_ROOT / "skills/paper/SKILL.md").read_text(encoding="utf-8")
        self.assertIn("Do not generate `slides.md`", paper_skill)
        self.assertFalse((REPO_ROOT / "assets/marp/VENDOR.md").exists())


if __name__ == "__main__":
    unittest.main()
