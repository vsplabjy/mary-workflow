from __future__ import annotations

import json
from pathlib import Path
import shlex
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from mw_host import capability_report, hook_config, hook_response
from mary_workflow import default_state, write_state


class HostAdapterTests(unittest.TestCase):
    def test_capabilities_require_explicit_booleans(self):
        self.assertEqual(capability_report()["execution_route"], "discover")
        self.assertEqual(set(capability_report()["capabilities"].values()), {"unknown"})
        report = capability_report({"workers": True, "worker_interrupt": False})
        self.assertEqual(report["execution_route"], "delegated")
        self.assertEqual(report["capabilities"]["worker_interrupt"], "unavailable")
        self.assertEqual(capability_report({"workers": False})["execution_route"], "single_agent")
        with self.assertRaises(ValueError):
            capability_report({"workers": "yes"})
        with self.assertRaises(ValueError):
            capability_report([])

    def test_config_is_printable_only_with_stable_quoted_project_paths(self):
        with tempfile.TemporaryDirectory(prefix="mary host '") as directory:
            project = Path(directory)
            config = hook_config(project=project)
            self.assertEqual(list(project.iterdir()), [])
            self.assertEqual(set(config["hooks"]), {"SessionStart", "PreCompact", "Stop"})
            for event, groups in config["hooks"].items():
                handler = groups[0]["hooks"][0]
                command = shlex.split(handler["command"])
                self.assertIn(str(project / ".mary-workflow/runtime/scripts/mw_host.py"), command)
                self.assertEqual(command[-1], str(project))
                self.assertIn("-B", command)
                self.assertEqual(handler["timeout"], 3)
            with self.assertRaises(ValueError):
                hook_config("unsupported", project)

    def test_hooks_are_read_only_bounded_state_views(self):
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            root = project / ".mary-workflow"
            root.mkdir()
            state = default_state(project, scan_project=False)
            write_state(root, state)
            task = root / "tasks/work-1"
            task.mkdir(parents=True)
            (task / "task.json").write_text(json.dumps({"status": "running"}))
            before = {str(p.relative_to(project)): p.read_bytes() for p in project.rglob("*") if p.is_file()}
            start = hook_response("SessionStart", project)
            self.assertTrue(start["continue"])
            self.assertIn("phase=PLANNING", start["hookSpecificOutput"]["additionalContext"])
            for event in ("PreCompact", "Stop"):
                response = hook_response(event, project)
                self.assertTrue(response["continue"])
                self.assertIn("unfinished worker tasks: 1", response["systemMessage"])
                self.assertNotIn("decision", response)
            after = {str(p.relative_to(project)): p.read_bytes() for p in project.rglob("*") if p.is_file()}
            self.assertEqual(before, after)

    def test_absent_or_malformed_state_never_blocks_or_creates_files(self):
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            self.assertTrue(hook_response("Stop", project)["continue"])
            self.assertEqual(list(project.iterdir()), [])
            root = project / ".mary-workflow"
            root.mkdir()
            (root / "state.yaml").write_text("version: unsupported\n")
            self.assertTrue(hook_response("SessionStart", project)["continue"])
            self.assertEqual(hook_response("unknown-event", project), {"continue": True})

    def test_stdin_aliases_and_malformed_inputs_fail_open(self):
        with tempfile.TemporaryDirectory() as directory:
            for payload in ("{bad json", "[]", json.dumps({"hook_event_name": "Stop", "cwd": directory}), json.dumps({"hookEventName": "PreCompact", "cwd": directory})):
                result = subprocess.run([sys.executable, "-B", str(ROOT / "scripts/mw_host.py"), "hook"], input=payload, capture_output=True, text=True, timeout=5)
                self.assertEqual(result.returncode, 0)
                self.assertTrue(json.loads(result.stdout)["continue"])
                self.assertFalse(result.stderr)


if __name__ == "__main__":
    unittest.main()
