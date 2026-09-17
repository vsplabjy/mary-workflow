from __future__ import annotations

from pathlib import Path
import os
import subprocess
import sys
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/mw_model.py"


class RetiredModelHelperTests(unittest.TestCase):
    def test_legacy_operations_never_read_credentials_or_mutate_host_files(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            host = root / ".codex"
            host.mkdir()
            (host / "config.toml").write_text('secret = "sentinel-do-not-print"\n')
            (host / "models.json").write_text('{"existing": true}\n')
            (root / ".zshrc").write_text("# user shell configuration\n")
            before = {str(p.relative_to(root)): p.read_bytes() for p in root.rglob("*") if p.is_file()}
            env = {**os.environ, "HOME": str(root), "CODEX_HOME": str(host)}
            for args, returncode in (([], 0), (["status"], 0), (["configure"], 2), (["use", "existing-provider"], 2), (["install-shell"], 2)):
                with self.subTest(args=args):
                    result = subprocess.run([sys.executable, str(SCRIPT), *args], capture_output=True, text=True, env=env)
                    self.assertEqual(result.returncode, returncode)
                    self.assertIn("does not manage model settings", result.stdout)
                    self.assertNotIn("sentinel-do-not-print", result.stdout + result.stderr)
                    after = {str(p.relative_to(root)): p.read_bytes() for p in root.rglob("*") if p.is_file()}
                    self.assertEqual(before, after)


if __name__ == "__main__":
    unittest.main()
