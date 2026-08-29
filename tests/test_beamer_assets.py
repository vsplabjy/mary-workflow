from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from validate_beamer_assets import (  # noqa: E402
    UPSTREAM_COMMIT,
    validate_beamer_assets,
)


class BeamerAssetContractTests(unittest.TestCase):
    def test_vendor_tree_is_local_complete_and_pinned(self) -> None:
        report = validate_beamer_assets()
        self.assertEqual(report["remote_dependencies"], 0)
        self.assertEqual(report["runtime_files"], 6)
        self.assertEqual(report["upstream_commit"], UPSTREAM_COMMIT)
        self.assertEqual(len(report["bundle_fingerprint"]), 64)

    def test_validator_cli_reports_bundle_identity(self) -> None:
        completed = subprocess.run(
            [sys.executable, str(REPO_ROOT / "scripts/validate_beamer_assets.py")],
            cwd=REPO_ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True,
        )
        report = json.loads(completed.stdout)
        self.assertEqual(
            report["theme"],
            "assets/beamer/themes/beamerthememary-shanghaitech-red.sty",
        )

    def test_offline_preview_compiles_with_xelatex(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary)
            source = REPO_ROOT / "assets/beamer/templates/offline-preview.tex"
            completed = subprocess.run(
                [
                    "latexmk",
                    "-xelatex",
                    "-interaction=nonstopmode",
                    "-halt-on-error",
                    f"-outdir={output}",
                    str(source),
                ],
                cwd=REPO_ROOT,
                env={
                    **__import__("os").environ,
                    "TEXINPUTS": (
                        f"{REPO_ROOT / 'assets/beamer/themes'}//:"
                        f"{REPO_ROOT / 'assets/beamer/assets'}//:"
                    ),
                },
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=True,
                timeout=180,
            )
            self.assertTrue((output / "offline-preview.pdf").is_file())


if __name__ == "__main__":
    unittest.main()
