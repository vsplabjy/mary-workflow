"""Default local-record policy checked against Git and real initialization."""
from pathlib import Path
import os
import subprocess
import sys
import tempfile
import unittest

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts"))
from mw_runtime import ensure_workflow_gitignore
from mw_paper import create_paper


class WorkflowGitignoreTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.project = Path(self.temp.name)
        self.git("init", "-q")

    def tearDown(self):
        self.temp.cleanup()

    def git(self, *args):
        return subprocess.run(["git", *args], cwd=self.project, capture_output=True, check=True)

    def ignored(self, path):
        return subprocess.run(["git", "check-ignore", "-q", path], cwd=self.project).returncode == 0

    def test_init_refresh_and_pinned_runtime_keep_records_local(self):
        existing = b"# custom\r\ncache/\r\n"
        target = self.project / ".gitignore"
        target.write_bytes(existing)
        command = [sys.executable, str(REPO_ROOT / "scripts/mary_workflow.py"), "init"]
        subprocess.run(command, cwd=self.project, capture_output=True, check=True)
        first = target.read_bytes()
        self.assertTrue(first.startswith(existing))
        lock = self.project / ".mary-workflow/workflow-lock.json"
        pinned = lock.read_bytes()
        subprocess.run(command, cwd=self.project, capture_output=True, check=True)
        self.assertEqual(target.read_bytes(), first)
        self.assertEqual(lock.read_bytes(), pinned)
        for path in (".mary-workflow/config.yaml", ".mary-workflow/analysis/hash.json",
                     ".mary-workflow/cycles/C0/log.md", ".mary-workflow/runtime/scripts/mw_runtime.py",
                     ".mary-workflow-worker/task/receipt.json", ".mary-research/reading-profile.md",
                     ".mary-research/papers/demo/state.json", ".vspi/config.json", "cache/a"):
            self.assertTrue(self.ignored(path), path)
        for path in ("config.yaml", "src/hash.json", "openspec/specs/example/spec.md",
                     "docs/result.md", "nested/.mary-workflow/config.yaml"):
            self.assertFalse(self.ignored(path), path)
        # The project-pinned helper has the same policy, without an added bundle dependency.
        subprocess.run([sys.executable, "-c",
                        "from mw_runtime import ensure_workflow_gitignore; from pathlib import Path; "
                        "assert not ensure_workflow_gitignore(Path.cwd())"],
                       cwd=self.project, env={**os.environ,
                       "PYTHONPATH": str(self.project / ".mary-workflow/runtime/scripts")}, check=True)

    def test_preserves_bytes_mode_and_index_and_repairs_missing_rule(self):
        target = self.project / ".gitignore"
        target.write_bytes(b"# legacy \xff\n/.mary-workflow/")
        target.chmod(0o640)
        tracked = self.project / ".mary-workflow/state.yaml"
        tracked.parent.mkdir()
        tracked.write_text("tracked state\n")
        self.git("add", "-f", ".mary-workflow/state.yaml")
        before = self.git("ls-files", "--stage").stdout
        self.assertTrue(ensure_workflow_gitignore(self.project))
        self.assertTrue(target.read_bytes().startswith(b"# legacy \xff\n/.mary-workflow/\n"))
        self.assertEqual(target.stat().st_mode & 0o777, 0o640)
        self.assertEqual(self.git("ls-files", "--stage").stdout, before)
        self.assertFalse(ensure_workflow_gitignore(self.project))
        target.write_bytes(target.read_bytes().replace(b"/.mary-research/\n", b""))
        self.assertTrue(ensure_workflow_gitignore(self.project))
        self.assertTrue(self.ignored(".mary-research/hash.json"))

    def test_symlink_is_not_replaced_or_followed(self):
        external = self.project / "external.ignore"
        external.write_text("keep\n")
        (self.project / ".gitignore").symlink_to(external)
        with self.assertRaisesRegex(ValueError, "symlinked"):
            ensure_workflow_gitignore(self.project)
        self.assertEqual(external.read_text(), "keep\n")
        self.assertTrue((self.project / ".gitignore").is_symlink())

    def test_standalone_paper_creation_installs_rules_without_workflow_init(self):
        create_paper(self.project, source_locator="https://arxiv.org/abs/2401.12345",
                     source_fingerprint="a" * 64)
        self.assertTrue(self.ignored(".mary-research/papers/demo/paper-state.json"))
        self.assertFalse((self.project / ".mary-workflow").exists())
        (self.project / ".gitignore").unlink()
        _, created = create_paper(self.project, source_locator="https://arxiv.org/abs/2401.12345",
                                  source_fingerprint="a" * 64)
        self.assertFalse(created)
        self.assertTrue(self.ignored(".mary-research/reading-profile.md"))


if __name__ == "__main__":
    unittest.main()
