from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import time
import unittest
from unittest import mock
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import mw_experiment as experiment


@unittest.skipUnless(sys.platform.startswith("linux"), "Linux supervision")
class ExperimentTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.project = Path(self.temp.name)
        self.runs = []
        self.addCleanup(self.stop_all)

    def stop_all(self):
        for project, run_id in self.runs:
            experiment.stop_run(project, run_id)

    def start(self, code="print('done', flush=True)", project=None, **kwargs):
        project = project or self.project
        result = experiment.start_run(project, [sys.executable, "-c", code], **kwargs)
        self.runs.append((project, result["run_id"]))
        return result

    def wait(self, record):
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            result = experiment.status(Path(record["cwd"]), record["run_id"])
            if result["execution_status"] in experiment.TERMINAL:
                return result
            time.sleep(0.02)
        self.fail("Run did not exit")

    def test_no_init_or_audit_required_and_success_is_not_acceptance(self):
        result = self.wait(self.start())
        self.assertEqual(result["execution_status"], "completed")
        self.assertEqual(result["exit_code"], 0)
        self.assertEqual(result["assessment_status"], "unreviewed")
        self.assertEqual(result["provenance_status"], "partial")
        self.assertFalse((self.project / ".mary-workflow/state.yaml").exists())
        self.assertEqual(Path(result["stdout"]).read_text(), "done\n")
        self.assertIn("/.mary-workflow/", (self.project / ".gitignore").read_text())

    def test_existing_strict_state_is_not_read_or_changed(self):
        root = self.project / ".mary-workflow"
        root.mkdir()
        state = root / "state.yaml"
        state.write_bytes(b"unparseable existing stopped milestone state\n")
        before = state.read_bytes()
        result = self.wait(self.start())
        self.assertEqual(result["exit_code"], 0)
        self.assertEqual(state.read_bytes(), before)

    def test_config_bytes_preserved_and_large_files_not_read(self):
        config = self.project / "config.yaml"
        config.write_bytes(b"lr: 0.0001\r\nseed: 3\r\n")
        large = self.project / "weights.pth"
        with large.open("wb") as stream:
            stream.truncate(512 * 1024 * 1024)
        original = Path.read_bytes
        def guarded(path):
            if path == large:
                raise AssertionError("Large config/checkpoint must not be read")
            return original(path)
        with mock.patch.object(Path, "read_bytes", guarded), mock.patch.object(hashlib, "sha256", side_effect=AssertionError("No launch hashes")):
            one = self.wait(self.start(config=config))
            two = self.wait(self.start(config=large))
        folder = experiment.run_path(self.project, one["run_id"])
        self.assertEqual((folder / "config.snapshot").read_bytes(), config.read_bytes())
        self.assertIsNone(two["config"]["snapshot"])

    def test_nonzero_exit_keeps_failure_and_logs(self):
        result = self.wait(self.start("import sys; print('broken', file=sys.stderr); sys.exit(7)"))
        self.assertEqual(result["execution_status"], "failed")
        self.assertEqual(result["exit_code"], 7)
        self.assertIn("broken", Path(result["stderr"]).read_text())

    def test_status_read_only_and_does_not_parse_metrics(self):
        result = self.wait(self.start())
        folder = experiment.run_path(self.project, result["run_id"])
        before = (folder / "run.json").read_bytes()
        with mock.patch.object(hashlib, "sha256", side_effect=AssertionError("status hashes")), mock.patch.object(experiment, "metrics", side_effect=AssertionError("status metrics")):
            self.assertEqual(experiment.status(self.project, result["run_id"])["exit_code"], 0)
        self.assertEqual((folder / "run.json").read_bytes(), before)

    def test_stop_is_sticky_and_same_id_cannot_restart(self):
        result = self.start("import time; time.sleep(30)", run_id="sticky")
        stopped = experiment.stop_run(self.project, result["run_id"])
        self.assertEqual(stopped["execution_status"], "stopped")
        self.assertEqual(stopped["stop_reason"], "USER_STOP")
        self.assertTrue(experiment.status(self.project, "sticky")["stop_requested"])
        with self.assertRaises(FileExistsError):
            self.start(run_id="sticky")
        self.assertFalse(experiment.alive(result["pid"], result["process_identity"]))

    def test_duplicate_supervisor_cannot_start_or_corrupt_an_existing_run(self):
        result = self.start("import time; time.sleep(.3)")
        with mock.patch.object(experiment.subprocess, "Popen", side_effect=AssertionError("duplicate launch")):
            experiment.supervise(self.project, result["run_id"])
        final = self.wait(result)
        before = experiment.run_path(self.project, final["run_id"]).joinpath("run.json").read_bytes()
        experiment.supervise(self.project, final["run_id"])
        self.assertEqual(experiment.run_path(self.project, final["run_id"]).joinpath("run.json").read_bytes(), before)

    def test_stop_before_child_creation(self):
        folder = experiment.run_path(self.project, "prestop")
        folder.mkdir(parents=True)
        experiment.save(folder, {"execution_status": "starting", "resource": None})
        (folder / "USER_STOP").write_text("requested")
        with mock.patch.object(experiment.subprocess, "Popen", side_effect=AssertionError("started after stop")):
            experiment.supervise(self.project, "prestop")
        self.assertEqual(experiment.read(folder)["execution_status"], "stopped")

    def test_budget_stops_child_without_claiming_success(self):
        result = self.wait(self.start("import time; time.sleep(30)", timeout=0.2))
        self.assertEqual(result["execution_status"], "failed")
        self.assertEqual(result["stop_reason"], "TIMEOUT")

    def test_resource_claim_is_shared_across_projects_and_released(self):
        resource = "test-" + uuid.uuid4().hex
        one = self.start("import time; time.sleep(30)", resource=resource)
        other = self.project / "other"
        other.mkdir()
        two = self.wait(self.start(project=other, resource=resource))
        self.assertEqual(two["execution_status"], "failed")
        self.assertIn("claimed", two["error"])
        experiment.stop_run(self.project, one["run_id"])
        three = self.wait(self.start(project=other, resource=resource))
        self.assertEqual(three["exit_code"], 0)

    def test_supervisor_loss_is_unknown_and_orphan_blocks_resource(self):
        resource = "test-" + uuid.uuid4().hex
        one = self.start("import time; time.sleep(30)", resource=resource)
        os.kill(one["supervisor_pid"], signal.SIGKILL)
        deadline = time.monotonic() + 3
        while experiment.alive(one["supervisor_pid"], one["supervisor_identity"]) and time.monotonic() < deadline:
            time.sleep(0.02)
        self.assertEqual(experiment.status(self.project, one["run_id"])["execution_status"], "unknown")
        two = self.wait(self.start(resource=resource))
        self.assertIn("live child", two["error"])
        stopped = experiment.stop_run(self.project, one["run_id"])
        self.assertEqual(stopped["execution_status"], "stopped")
        self.assertIsNone(stopped["exit_code"])

    def test_stop_never_signals_a_reused_pid(self):
        with mock.patch.object(experiment.os, "killpg") as kill:
            self.assertFalse(experiment.terminate(os.getpid(), "wrong-start-identity"))
        kill.assert_not_called()

    def test_process_group_descendants_are_stopped(self):
        code = "import subprocess,sys,time; p=subprocess.Popen([sys.executable,'-c','import time; time.sleep(30)']); print(p.pid,flush=True); time.sleep(30)"
        result = self.start(code)
        log = Path(result["stdout"])
        deadline = time.monotonic() + 3
        while not log.read_text().strip() and time.monotonic() < deadline:
            time.sleep(0.02)
        descendant = int(log.read_text().strip())
        identity = experiment.process_identity(descendant)
        experiment.stop_run(self.project, result["run_id"])
        self.assertFalse(experiment.alive(descendant, identity))

    def test_compare_rejects_nan_and_missing_metrics_without_reruns(self):
        one = self.wait(self.start())
        two = self.wait(self.start())
        Path(one["metrics_file"]).write_text('{"loss": NaN}')
        rows = experiment.compare(self.project, [one["run_id"], two["run_id"]])["runs"]
        self.assertEqual([r["metrics_status"] for r in rows], ["unavailable", "unavailable"])
        Path(one["metrics_file"]).write_text('{"loss": 0.5}')
        result = experiment.compare(self.project, [one["run_id"]])
        self.assertEqual(result["runs"][0]["metrics"], {"loss": 0.5})
        self.assertEqual(result["assessment_status"], "unreviewed")

    def test_audit_is_selected_and_does_not_upgrade_provenance(self):
        result = self.wait(self.start())
        artifact = Path(result["output_dir"]) / "value.txt"
        artifact.write_text("observed")
        with self.assertRaises(ValueError):
            experiment.audit(self.project, result["run_id"], [])
        audited = experiment.audit(self.project, result["run_id"], [artifact])
        self.assertEqual(audited["artifacts"][0]["sha256"], hashlib.sha256(b"observed").hexdigest())
        self.assertEqual(audited["provenance_status"], "partial")
        self.assertEqual(experiment.status(self.project, result["run_id"])["assessment_status"], "unreviewed")

    def test_live_run_cannot_be_audited(self):
        result = self.start("import time; time.sleep(30)")
        with self.assertRaises(ValueError):
            experiment.audit(self.project, result["run_id"], [Path(result["stdout"])])

    def test_output_directory_cannot_overwrite_previous_outputs(self):
        output = self.project / "existing"
        output.mkdir()
        (output / "keep").write_text("original")
        with self.assertRaises(FileExistsError):
            self.start(output_dir=output)
        self.assertEqual((output / "keep").read_text(), "original")

    def test_cli_supervisor_survives_launcher_and_arguments_are_literal(self):
        argument = "$(touch should-not-exist); $HOME"
        command = [sys.executable, str(ROOT / "scripts/mw_experiment.py"), "--project", str(self.project),
                   "run", "--id", "literal", "--", sys.executable, "-c", "import sys,time; time.sleep(.2); print(sys.argv[1])", argument]
        launched = subprocess.run(command, capture_output=True, text=True, timeout=5)
        self.assertEqual(launched.returncode, 0, launched.stderr)
        result = json.loads(launched.stdout)
        self.runs.append((self.project, result["run_id"]))
        result = self.wait(result)
        self.assertEqual(Path(result["stdout"]).read_text().strip(), argument)
        self.assertFalse((self.project / "should-not-exist").exists())

    def test_readme_change_does_not_interrupt_running_experiment(self):
        result = self.start("import time; time.sleep(.4)")
        (self.project / "README.md").write_text("unrelated change")
        self.assertEqual(self.wait(result)["execution_status"], "completed")

    def test_invalid_budget_config_and_path_fail_before_launch(self):
        for timeout in (-1, float("nan"), float("inf")):
            with self.assertRaises(ValueError):
                self.start(timeout=timeout)
        with self.assertRaises(ValueError):
            self.start(run_id="../escape")
        with self.assertRaises(FileNotFoundError):
            self.start(config=Path("missing.yaml"))
