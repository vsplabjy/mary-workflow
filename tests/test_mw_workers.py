from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import copy
import json
import os
from pathlib import Path
import shlex
import signal
import subprocess
import sys
import tempfile
import time
import unittest


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from mw_runtime import workflow_lock  # noqa: E402
from mw_workers import (  # noqa: E402
    WorkerError, accept_tasks, cancel_tasks, create_task, list_tasks,
    recover_validation, run_validation, submit_result, validate_relative_path,
    verify_milestone_evidence, verify_review_evidence,
)


def python_command(source: str) -> str:
    return shlex.quote(sys.executable) + " -c " + shlex.quote(source)


class WorkerContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.project = Path(self.temporary.name)
        self.root = self.project / ".mary-workflow"
        self.root.mkdir()
        (self.project / "product.txt").write_text("existing user edit\n", encoding="utf-8")
        (self.project / "other.txt").write_text("unrelated user file\n", encoding="utf-8")
        self.command = python_command("from pathlib import Path; assert Path('product.txt').read_text() == 'finished\\n'; print('verified')")
        self.milestone = {"id": "milestone-1", "deliverables": ["product.txt"], "acceptance": [self.command]}
        self.state = {"phase": "EXECUTING", "status": "running", "cycle": "C0",
                      "lease_run_id": "run-1", "current_milestone_id": "milestone-1",
                      "milestones": [self.milestone],
                      "runtime_meta": {"plan_revision": 1, "execution_mode": "delegated"}}

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def dispatch(self, task_id: str = "implementation", **fields):
        data = {"task_id": task_id, "agent_id": task_id, "role": "implementer", "objective": "Finish product"}
        data.update(fields)
        return create_task(self.root, self.state, data)

    def validate(self, task, **fields):
        data = {"task_id": task["task_id"], "attempt_id": task["attempt_id"], "acceptance_id": "check-1"}
        data.update(fields)
        return run_validation(self.root, self.state, data)

    def submit(self, task, evidence=None, **fields):
        data = {"task_id": task["task_id"], "attempt_id": task["attempt_id"],
                "status": "ready_for_review", "summary": "Product complete",
                "files_changed": ["product.txt"], "validation": [evidence["evidence_id"]] if evidence else [],
                "scope_deviations": [], "blockers": [], "uncertainties": []}
        data.update(fields)
        return submit_result(self.root, self.state, data)

    def finish_implementation(self):
        task = self.dispatch()
        (self.project / "product.txt").write_text("finished\n", encoding="utf-8")
        evidence = self.validate(task)
        self.submit(task, evidence)
        return task, evidence

    def verify(self, tasks=None):
        return verify_milestone_evidence(self.root, self.state, self.milestone,
                                         {"task_ids": tasks or ["implementation"]})

    def test_full_implementation_and_independent_review(self):
        task, evidence = self.finish_implementation()
        summary = self.verify()
        self.assertEqual(summary["files_changed"], ["product.txt"])
        self.assertEqual(evidence["result"], "passed")
        self.assertEqual(evidence["exit_code"], 0)
        self.assertEqual(evidence["command"], self.command)
        self.assertEqual(evidence["cwd"], str(self.project))
        log = self.root / "tasks" / task["task_id"] / evidence["stdout"]
        self.assertEqual(log.read_text(), "verified\n")
        self.state["phase"] = "REVIEWING"
        reviewer = self.dispatch("review", role="verifier", reviews_task_ids=[task["task_id"]],
                                 read_dependencies=["product.txt"])
        self.submit(reviewer, files_changed=[], decision="passed", findings=[])
        review = verify_review_evidence(self.root, self.state, self.milestone, {"verifier_task_id": "review"})
        self.assertTrue(review["independent_review"])
        accept_tasks(self.root, self.state, [task["task_id"], reviewer["task_id"]])
        self.assertEqual({task["status"] for task in list_tasks(self.root)}, {"accepted"})
        # A crash after sidecars close but before state.yaml advances can retry.
        accept_tasks(self.root, self.state, [task["task_id"], reviewer["task_id"]])

    def test_self_approval_rejected(self):
        task, _ = self.finish_implementation()
        self.state["phase"] = "REVIEWING"
        with self.assertRaisesRegex(WorkerError, "independent"):
            self.dispatch("review", role="verifier", agent_id=task["agent_id"], reviews_task_ids=[task["task_id"]])

    def test_single_agent_review_explicitly_marks_lack_of_independence(self):
        self.state["runtime_meta"]["execution_mode"] = "single_agent"
        task, _ = self.finish_implementation()
        self.state["phase"] = "REVIEWING"
        reviewer = self.dispatch("review", role="verifier", agent_id=task["agent_id"], reviews_task_ids=[task["task_id"]])
        with self.assertRaisesRegex(WorkerError, "review_mode=same_agent"):
            self.submit(reviewer, files_changed=[], decision="passed", findings=[])
        self.submit(reviewer, files_changed=[], decision="passed", findings=[], review_mode="same_agent")
        result = verify_review_evidence(self.root, self.state, self.milestone, {"verifier_task_id": "review"})
        self.assertFalse(result["independent_review"])

    def test_claimed_pass_without_actual_execution_rejected(self):
        task = self.dispatch()
        (self.project / "product.txt").write_text("finished\n")
        with self.assertRaisesRegex(WorkerError, "never supplied"):
            self.validate(task, result="passed")
        self.submit(task)
        with self.assertRaisesRegex(WorkerError, "Missing executed"):
            self.verify()

    def test_failure_evidence_preserved_but_cannot_pass(self):
        task = self.dispatch()
        evidence = self.validate(task)
        self.assertEqual(evidence["result"], "failed")
        self.submit(task, evidence, files_changed=[])
        with self.assertRaisesRegex(WorkerError, "did not pass"):
            self.verify()

    def test_command_cannot_be_substituted(self):
        task = self.dispatch()
        with self.assertRaisesRegex(WorkerError, "exact frozen command"):
            self.validate(task, command="true")
        with self.assertRaisesRegex(WorkerError, "exact frozen command"):
            self.validate(task, acceptance_id="check-999")

    def test_evidence_freshness_after_edit(self):
        task = self.dispatch()
        (self.project / "product.txt").write_text("finished\n")
        evidence = self.validate(task)
        (self.project / "product.txt").write_text("changed after testing\n")
        with self.assertRaisesRegex(WorkerError, "stale"):
            self.submit(task, evidence)

    def test_result_freshness_after_submission(self):
        self.finish_implementation()
        (self.project / "product.txt").write_text("changed after submission\n")
        with self.assertRaisesRegex(WorkerError, "stale"):
            self.verify()

    def test_validation_that_modifies_product_is_not_fresh(self):
        self.milestone["acceptance"] = [python_command("from pathlib import Path; Path('product.txt').write_text('test changed it')")]
        task = self.dispatch()
        evidence = self.validate(task)
        self.assertEqual(evidence["result"], "passed")
        with self.assertRaisesRegex(WorkerError, "command changed product"):
            self.submit(task, evidence)

    def test_log_tampering_detected(self):
        task, evidence = self.finish_implementation()
        log = self.root / "tasks" / task["task_id"] / evidence["stdout"]
        log.chmod(0o644)
        log.write_text("forged output")
        with self.assertRaisesRegex(WorkerError, "raw validation log"):
            self.verify()

    def test_result_tampering_detected(self):
        task, _ = self.finish_implementation()
        result = self.root / "tasks" / task["task_id"] / "result.json"
        result.chmod(0o644)
        data = json.loads(result.read_text())
        data["summary"] = "silently changed claim"
        result.write_text(json.dumps(data))
        with self.assertRaisesRegex(WorkerError, "result record changed"):
            self.verify()

    def test_submitted_revision_cannot_disagree_with_dispatch(self):
        task = self.dispatch()
        with self.assertRaisesRegex(WorkerError, "Submitted plan_revision"):
            self.submit(task, files_changed=[], plan_revision=999)

    def test_wrong_or_missing_attempt_rejected(self):
        task = self.dispatch()
        for attempt in ("wrong", ""):
            with self.subTest(attempt=attempt), self.assertRaisesRegex(WorkerError, "attempt_id"):
                self.validate(task, attempt_id=attempt)

    def test_stale_run_revision_cycle_and_milestone_contract_rejected(self):
        task = self.dispatch()
        variants = []
        for key, value in (("lease_run_id", "run-2"), ("cycle", "C1"), ("current_milestone_id", "milestone-2")):
            state = copy.deepcopy(self.state)
            state[key] = value
            variants.append(state)
        state = copy.deepcopy(self.state)
        state["runtime_meta"]["plan_revision"] = 2
        variants.append(state)
        state = copy.deepcopy(self.state)
        state["milestones"][0]["acceptance"] = ["true"]
        variants.append(state)
        for state in variants:
            with self.subTest(state=state), self.assertRaisesRegex(WorkerError, "Stale"):
                run_validation(self.root, state, {"task_id": task["task_id"], "attempt_id": task["attempt_id"], "acceptance_id": "check-1"})

    def test_duplicate_result_and_task_id_rejected(self):
        task, evidence = self.finish_implementation()
        with self.assertRaisesRegex(WorkerError, "duplicate or late"):
            self.submit(task, evidence)
        with self.assertRaisesRegex(WorkerError, "task_id already exists"):
            self.dispatch()

    def test_cancelled_and_stopped_tasks_cannot_submit(self):
        task = self.dispatch()
        self.state["status"] = "stopped"
        with self.assertRaisesRegex(WorkerError, "stopped"):
            self.submit(task, files_changed=[])
        self.state["status"] = "running"
        self.assertEqual(cancel_tasks(self.root), ["implementation"])
        with self.assertRaisesRegex(WorkerError, "cancelled"):
            self.submit(task, files_changed=[])

    def test_review_pause_preserves_prior_ready_evidence_but_rejects_late_worker(self):
        task, _ = self.finish_implementation()
        self.state["phase"] = "REVIEWING"
        reviewer = self.dispatch("review-old", role="verifier", reviews_task_ids=[task["task_id"]])
        cancelled = cancel_tasks(self.root, "pause", include_ready=False)
        self.assertEqual(cancelled, [reviewer["task_id"]])
        self.state["status"] = "stopped"
        with self.assertRaisesRegex(WorkerError, "stopped"):
            self.verify()
        self.state["status"] = "running"
        with self.assertRaisesRegex(WorkerError, "cancelled"):
            self.submit(reviewer, files_changed=[], decision="passed", findings=[])
        new_reviewer = self.dispatch("review-new", role="verifier", reviews_task_ids=[task["task_id"]])
        self.submit(new_reviewer, files_changed=[], decision="passed", findings=[])
        result = verify_review_evidence(self.root, self.state, self.milestone, {"verifier_task_id": new_reviewer["task_id"]})
        self.assertTrue(result["independent_review"])

    def test_path_traversal_control_directory_and_symlink_rejected(self):
        for path in ("../other.txt", "/tmp/other.txt", ".mary-workflow/state.yaml", ".git/config", "*.py", "src/../x", "a\\b"):
            with self.subTest(path=path), self.assertRaises(WorkerError):
                validate_relative_path(path)
        (self.project / "link").symlink_to(self.project / "product.txt")
        self.milestone["deliverables"] = ["link"]
        with self.assertRaisesRegex(WorkerError, "Symlink"):
            self.dispatch()

    def test_post_dispatch_symlink_substitution_rejected(self):
        task = self.dispatch()
        (self.project / "product.txt").unlink()
        (self.project / "product.txt").symlink_to(self.project / "other.txt")
        with self.assertRaisesRegex(WorkerError, "Symlink"):
            self.submit(task)

    def test_scope_deviation_and_inaccurate_changed_files_rejected(self):
        task = self.dispatch()
        (self.project / "other.txt").write_text("out of scope")
        with self.assertRaisesRegex(WorkerError, "Out-of-scope"):
            self.submit(task, files_changed=[])
        (self.project / "other.txt").write_text("unrelated user file\n")
        (self.project / "product.txt").write_text("finished\n")
        with self.assertRaisesRegex(WorkerError, "files_changed differs"):
            self.submit(task, files_changed=[])

    def test_dependency_conflicts_rejected_and_disjoint_writes_allowed(self):
        self.milestone["deliverables"] = ["product.txt", "other.txt"]
        self.dispatch(deliverables=["product.txt"], write_scope=["product.txt"], read_dependencies=["other.txt"])
        with self.assertRaisesRegex(WorkerError, "conflict"):
            self.dispatch("other", deliverables=["other.txt"], write_scope=["other.txt"])
        cancel_tasks(self.root)
        self.dispatch("new", deliverables=["product.txt"], write_scope=["product.txt"])
        self.dispatch("parallel", deliverables=["other.txt"], write_scope=["other.txt"])
        self.assertEqual(len(list_tasks(self.root)), 3)

    def test_parallel_workers_converge_before_validation(self):
        self.milestone["deliverables"] = ["product.txt", "other.txt"]
        first = self.dispatch(deliverables=["product.txt"], write_scope=["product.txt"])
        second = self.dispatch("parallel", deliverables=["other.txt"], write_scope=["other.txt"])
        (self.project / "product.txt").write_text("finished\n")
        (self.project / "other.txt").write_text("other completed\n")
        evidence = self.validate(first)
        self.submit(first, evidence)
        self.submit(second, files_changed=["other.txt"])
        summary = self.verify(["implementation", "parallel"])
        self.assertEqual(summary["files_changed"], ["other.txt", "product.txt"])

    def test_cannot_finish_with_another_writer_running_or_omitted(self):
        self.milestone["deliverables"] = ["product.txt", "other.txt"]
        first = self.dispatch(deliverables=["product.txt"], write_scope=["product.txt"])
        second = self.dispatch("parallel", deliverables=["other.txt"], write_scope=["other.txt"])
        (self.project / "product.txt").write_text("finished\n")
        evidence = self.validate(first)
        self.submit(first, evidence)
        with self.assertRaisesRegex(WorkerError, "still running"):
            self.verify()
        self.submit(second, files_changed=[])
        with self.assertRaisesRegex(WorkerError, "omits implementation"):
            self.verify()

    def test_debugging_allows_diagnosis_but_not_fixer_writes(self):
        self.state["phase"] = "DEBUGGING"
        with self.assertRaisesRegex(WorkerError, "Cannot dispatch"):
            self.dispatch()
        explorer = self.dispatch("diagnosis", role="explorer")
        self.submit(explorer, files_changed=[])

    def test_explorer_has_no_product_write_scope(self):
        self.state.update(phase="PLANNING", current_milestone_id="", lease_run_id="")
        with self.assertRaisesRegex(WorkerError, "empty product write_scope"):
            self.dispatch(role="explorer", write_scope=["product.txt"])
        explorer = self.dispatch("explorer", role="explorer", read_dependencies=["product.txt"])
        scratch = self.project / explorer["scratch"]
        scratch.mkdir(parents=True, exist_ok=True)
        (scratch / "module-summary.md").write_text("Read product.txt")
        self.submit(explorer, files_changed=[])

    def test_blocker_requires_specific_record(self):
        task = self.dispatch()
        with self.assertRaisesRegex(WorkerError, "concrete blockers"):
            self.submit(task, status="blocked", files_changed=[])
        received = self.submit(task, status="blocked", files_changed=[], blockers=[{"reason": "Missing fixture", "attempted": ["Checked configured path"]}])
        self.assertEqual(received["status"], "blocked")

    def test_failed_attempt_preserves_reported_and_observed_scope_violations(self):
        task = self.dispatch()
        (self.project / "other.txt").write_text("unexpected edit")
        deviations = [{"path": "other.txt", "reason": "Mistaken file selection"}]
        received = self.submit(task, status="failed", files_changed=["../outside.txt"],
                               scope_deviations=deviations, validation=["../untrusted-evidence"],
                               blockers=[{"reason": "Scope violation", "attempted": ["Stopped writing"]}])
        result = received["result"]
        self.assertEqual(result["files_changed"], ["other.txt"])
        self.assertEqual(result["reported_files_changed"], ["../outside.txt"])
        self.assertEqual(result["scope_deviations"], deviations)
        self.assertEqual(result["observed_scope_deviations"], ["other.txt"])
        self.assertTrue(result["contract_issues"])
        with self.assertRaisesRegex(WorkerError, "failed"):
            self.verify()

    def test_failed_verifier_can_record_crash_without_a_verdict(self):
        task, _ = self.finish_implementation()
        self.state["phase"] = "REVIEWING"
        reviewer = self.dispatch("review", role="verifier", reviews_task_ids=[task["task_id"]])
        received = self.submit(reviewer, status="blocked", files_changed=[], blockers=[{"reason": "Tool connection lost", "attempted": ["One reconnect"]}])
        self.assertEqual(received["status"], "blocked")

    def test_timeout_is_not_a_pass_and_has_raw_logs(self):
        self.milestone["acceptance"] = [python_command("import time; print('started', flush=True); time.sleep(10)")]
        task = self.dispatch()
        evidence = self.validate(task, timeout_seconds=0.1)
        self.assertEqual(evidence["result"], "timeout")
        self.assertLess(evidence["duration_ms"], 3000)
        self.submit(task, evidence, files_changed=[])
        with self.assertRaisesRegex(WorkerError, "did not pass"):
            self.verify()

    def test_stop_does_not_wait_for_long_validation_and_cancels_process(self):
        self.milestone["acceptance"] = [python_command("import time; time.sleep(20)")]
        task = self.dispatch()
        with ThreadPoolExecutor(max_workers=1) as executor:
            running = executor.submit(self.validate, task)
            deadline = time.monotonic() + 5
            while not list_tasks(self.root)[0].get("active_validation") and time.monotonic() < deadline:
                time.sleep(0.01)
            start = time.monotonic()
            with workflow_lock(self.root):
                cancel_tasks(self.root)
            self.assertLess(time.monotonic() - start, 1)
            evidence = running.result(timeout=5)
        self.assertEqual(evidence["result"], "cancelled")
        self.assertEqual(list_tasks(self.root)[0]["status"], "cancelled")

    def make_crashed_receipt(self, *, alive=False, coordinator_alive=False):
        source = "import time; print('partial evidence', flush=True); time.sleep(20)" if alive else "print('partial evidence')"
        self.milestone["acceptance"] = [python_command(source)]
        task = self.dispatch()
        directory = self.root / "tasks" / task["task_id"]
        with (directory / "check-crashed.stdout.log").open("wb") as stdout, (directory / "check-crashed.stderr.log").open("wb") as stderr:
            process = subprocess.Popen([sys.executable, "-c", source], stdout=stdout, stderr=stderr, start_new_session=True)
        if not alive:
            process.wait(timeout=5)
        coordinator = subprocess.Popen([sys.executable, "-c", "pass"], start_new_session=True)
        coordinator.wait(timeout=5)
        path = directory / "task.json"
        record = json.loads(path.read_text())
        record["active_validation"] = {
            "evidence_id": "check-crashed", "pid": process.pid,
            "process_group_id": process.pid, "isolated_process_group": True, "platform": "posix",
            "coordinator_pid": os.getpid() if coordinator_alive else coordinator.pid,
            "acceptance_id": "check-1", "command": self.milestone["acceptance"][0],
            "cwd": str(self.project), "snapshot_digest": task["baseline_digest"],
            "started_at": "2026-09-17T00:00:00+00:00",
        }
        path.write_text(json.dumps(record))
        return task, process

    @unittest.skipUnless(os.name == "posix", "Recovery requires POSIX process-group evidence")
    def test_crashed_validation_receipt_recovers_as_interrupted_never_success(self):
        task, process = self.make_crashed_receipt()
        self.assertEqual(process.returncode, 0)  # Caller must not infer this lost exit code.
        self.state["status"] = "stopped"
        result = recover_validation(self.root, self.state, {"task_id": task["task_id"], "attempt_id": task["attempt_id"]})
        self.assertEqual(result["status"], "cancelled")
        self.assertNotIn("active_validation", result)
        evidence = result["recovery_evidence"]
        self.assertEqual(evidence["result"], "interrupted")
        self.assertIsNone(evidence["exit_code"])
        self.assertIsNone(evidence["duration_ms"])
        self.assertEqual(evidence["missing_logs"], [])
        path = self.root / "tasks" / task["task_id"]
        self.assertEqual((path / evidence["stdout"]).read_text(), "partial evidence\n")
        self.assertTrue((path / (evidence["evidence_id"] + ".json")).exists())
        self.state["status"] = "running"
        with self.assertRaisesRegex(WorkerError, "cancelled"):
            self.submit(task, files_changed=[])

    @unittest.skipUnless(os.name == "posix", "Recovery requires POSIX process-group evidence")
    def test_living_validation_receipt_refuses_recovery_without_killing_process(self):
        task, process = self.make_crashed_receipt(alive=True)
        try:
            with self.assertRaisesRegex(WorkerError, "still exists"):
                recover_validation(self.root, self.state, {"task_id": task["task_id"], "attempt_id": task["attempt_id"]})
            self.assertIsNone(process.poll())
            self.assertIn("active_validation", list_tasks(self.root)[0])
            self.assertEqual(list((self.root / "tasks" / task["task_id"]).glob("recovery-*.json")), [])
        finally:
            os.killpg(process.pid, signal.SIGKILL)
            process.wait(timeout=5)

    @unittest.skipUnless(os.name == "posix", "Recovery requires POSIX process-group evidence")
    def test_live_coordinator_prevents_recovery_race_after_command_exit(self):
        task, _ = self.make_crashed_receipt(coordinator_alive=True)
        with self.assertRaisesRegex(WorkerError, "coordinator PID.*still exists"):
            recover_validation(self.root, self.state, {"task_id": task["task_id"], "attempt_id": task["attempt_id"]})
        self.assertIn("active_validation", list_tasks(self.root)[0])

    @unittest.skipUnless(os.name == "posix", "Recovery requires POSIX process-group evidence")
    def test_recovery_rejects_wrong_attempt_and_symlink_log(self):
        task, _ = self.make_crashed_receipt()
        with self.assertRaisesRegex(WorkerError, "attempt_id"):
            recover_validation(self.root, self.state, {"task_id": task["task_id"], "attempt_id": "wrong"})
        path = self.root / "tasks" / task["task_id"] / "check-crashed.stdout.log"
        path.unlink()
        path.symlink_to(self.project / "other.txt")
        with self.assertRaisesRegex(WorkerError, "ordinary file"):
            recover_validation(self.root, self.state, {"task_id": task["task_id"], "attempt_id": task["attempt_id"]})
        self.assertIn("active_validation", list_tasks(self.root)[0])

    def test_git_baseline_handles_preexisting_staged_and_untracked_files(self):
        def git(*args):
            return subprocess.run(["git", *args], cwd=self.project, check=True, capture_output=True)
        git("init", "-q")
        git("add", "product.txt")
        task = self.dispatch()
        (self.project / "product.txt").write_text("finished\n")
        evidence = self.validate(task)
        self.submit(task, evidence)
        self.assertEqual(self.verify()["files_changed"], ["product.txt"])
        self.assertEqual((self.project / "other.txt").read_text(), "unrelated user file\n")

    def test_git_index_mutation_detected_even_for_allowed_file(self):
        subprocess.run(["git", "init", "-q"], cwd=self.project, check=True)
        task = self.dispatch()
        subprocess.run(["git", "add", "product.txt"], cwd=self.project, check=True)
        with self.assertRaisesRegex(WorkerError, "Git index changed"):
            self.submit(task, files_changed=["product.txt"])

    def test_delete_and_new_file_reported_without_diff_stat(self):
        self.milestone.update(deliverables=["product.txt", "new.txt"], acceptance=[python_command("from pathlib import Path; assert not Path('product.txt').exists(); assert Path('new.txt').exists()")])
        task = self.dispatch()
        (self.project / "product.txt").unlink()
        (self.project / "new.txt").write_text("replacement")
        evidence = self.validate(task)
        self.submit(task, evidence, files_changed=["new.txt", "product.txt"])
        self.assertEqual(self.verify()["files_changed"], ["new.txt", "product.txt"])


if __name__ == "__main__":
    unittest.main()
