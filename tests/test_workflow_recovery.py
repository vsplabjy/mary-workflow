"""Regression cases found by independent integration and forward checks."""
from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import unittest

import test_workflow_boundaries as fixtures
from mary_workflow import apply_action, current_plan_digest, detect_project, legal_actions_for_state, milestone_plan_signature, read_state, write_state


class RecoveryTests(unittest.TestCase):
    def setUp(self):
        self.fixture = fixtures.WorkflowBoundaryTests()
        self.fixture.setUp()
        self.root = self.fixture.root

    def tearDown(self):
        self.fixture.tearDown()

    def test_disclosed_defaults_are_frozen_without_forcing_an_extra_interview(self):
        f = self.fixture
        f.act("update_interview", mode="propose", clarifications=["Requested behavior"],
              defaults=["Keep existing input whitespace handling"], draft_milestones=[fixtures.milestone()])
        state = read_state(self.root)
        self.assertIn("Disclosed assumption: Keep existing input whitespace handling", state["clarifications"])
        frozen = f.act("update_state", phase="PLANNED", clarifications=state["clarifications"],
                       milestones=milestone_plan_signature(state["draft_milestones"]))
        self.assertFalse(frozen["final_plan_confirmed"])
        digest = frozen["runtime_meta"]["frozen_plan_digest"]
        frozen["clarifications"][-1] = "Disclosed assumption: Change whitespace handling"
        self.assertNotEqual(current_plan_digest(frozen), digest)

    def test_repair_cannot_bypass_original_confirmation_gate(self):
        f = self.fixture
        f.start([fixtures.milestone(gate="confirm")])
        f.act("record_error", command="inspection", stderr="Implementation required", returncode="1")
        state = f.act("enqueue_fix_task", title="Repair the original behavior")
        repair = next(item for item in state["milestones"] if item.get("repair_of"))
        self.assertEqual(repair["gate"], "confirm")
        f.rejected("delegate_task", task_id="early-repair", role="implementer", agent_id="worker-a", objective="Repair")
        f.act("confirm_milestone", id=repair["id"], confirmation="Proceed with this scoped milestone", plan_digest=state["runtime_meta"]["frozen_plan_digest"])
        f.dispatch("approved-repair")
        self.assertIn("milestone-1", read_state(self.root)["runtime_meta"]["confirmations"])

    def test_stopped_understanding_has_a_nonexecuting_resume_path(self):
        f = self.fixture
        f.dispatch("read-project", role="explorer", agent_id="reader")
        f.cli("stop")
        f.cli("stop")
        self.assertTrue(read_state(self.root)["runtime_meta"]["stop_pending"])
        self.assertNotEqual(f.cli("init", check=False).returncode, 0)
        f.cli("init", "--workers-quiescent")
        state = read_state(self.root)
        self.assertEqual(state["phase"], "PLANNING")
        self.assertNotEqual(state["status"], "stopped")
        self.assertFalse(state["final_plan_confirmed"])
        f.dispatch("read-project-again", role="explorer", agent_id="reader-2")

    def test_error_barrier_prevents_new_writer_until_old_worker_is_quiescent(self):
        f = self.fixture
        f.start()
        f.dispatch("partial-worker")
        f.act("record_error", command="inspection", stderr="Need scoped repair", returncode="1")
        f.act("enqueue_fix_task", title="Repair current behavior")
        f.rejected("delegate_task", task_id="racing-repair", role="implementer", agent_id="worker-b", objective="Repair")
        f.dispatch("settled-repair", agent_id="worker-b", workers_quiescent=True)

    def test_stopped_cycle_with_changes_has_a_legal_refresh_route(self):
        f = self.fixture
        f.start()
        f.dispatch("partial-worker")
        (f.project / "product.txt").write_text("partial\n")
        f.cli("stop")
        f.cli("cycle", "--workers-quiescent")
        state = read_state(self.root)
        self.assertEqual(state["phase"], "PLANNING")
        self.assertEqual(state["project_brief_status"], "refresh_required")
        self.assertTrue(state["runtime_meta"]["plan_history"])
        self.assertIn("delegate_task", legal_actions_for_state(state))
        f.dispatch("refresh-reader", role="explorer", agent_id="reader")

    def test_reviewing_pause_reuses_preexisting_ready_evidence(self):
        f = self.fixture
        state = f.start()
        implementation = f.implementation()
        f.dispatch("interrupted-reviewer", role="verifier", agent_id="reviewer-a", reviews_task_ids=[implementation["task_id"]])
        f.cli("stop")
        self.assertEqual(f.task(implementation["task_id"])["status"], "ready_for_review")
        f.act("resume_execution", source="/mw-run", confirmation="/mw-run", plan_digest=state["runtime_meta"]["frozen_plan_digest"], workers_quiescent=True)
        self.assertEqual(read_state(self.root)["phase"], "REVIEWING")
        done = f.review(implementation, agent_id="reviewer-b")
        self.assertEqual(done["phase"], "FINISHED")

    def test_expected_revision_rejects_stale_action_without_changing_plan(self):
        f = self.fixture
        state = read_state(self.root)
        revision = state["runtime_meta"]["state_revision"]
        f.act("update_project", test_commands=["python -m unittest"])
        with self.assertRaises(SystemExit):
            apply_action(self.root, {"action":"update_project", "expected_revision":revision,
                                     "data":{"test_commands":["invented command"]}})
        self.assertEqual(read_state(self.root)["project_test_commands"], ["python -m unittest"])

    def test_completed_brief_does_not_request_resubmission_for_empty_optional_sections(self):
        self.assertNotIn("等待", (self.root / "project-brief.md").read_text())

    def test_unittest_candidate_is_grounded_in_existing_tests(self):
        (self.fixture.project / "test_parser.py").write_text("import unittest\n")
        commands = detect_project(self.fixture.project)["test_commands"]
        self.assertIn("python -m unittest discover -v", commands)
        self.assertFalse(any("pytest" in item for item in commands))

    def test_deferred_legacy_coverage_cannot_be_silently_archived(self):
        state = read_state(self.root)
        state["runtime_meta"]["legacy_brief_refresh_pending"] = True
        state["runtime_meta"]["brief"]["legacy_pending"] = True
        write_state(self.root, state)
        self.fixture.cli("cycle")
        state = read_state(self.root)
        self.assertEqual(state["cycle"], "C0")
        self.assertEqual(state["project_brief_status"], "refresh_required")
        self.assertIn("submit_brief", legal_actions_for_state(state))

    def test_parallel_cli_rejections_do_not_lose_audit_updates(self):
        script = str(fixtures.REPO_ROOT / "scripts/mary_workflow.py")
        payload = json.dumps({"action": "set_phase", "data": {"phase": "FINISHED"}})
        processes = [subprocess.Popen([sys.executable, "-B", script, "apply-action", "--json", payload],
                                     cwd=self.fixture.project, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                     for _ in range(6)]
        for process in processes:
            process.communicate(timeout=10)
            self.assertNotEqual(process.returncode, 0)
        state = read_state(self.root)
        self.assertEqual(state["rejected_actions"], 6)
        self.assertEqual(state["phase"], "PLANNING")


if __name__ == "__main__":
    unittest.main()
