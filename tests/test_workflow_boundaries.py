"""Behavioral v3 workflow tests with actual worker acceptance subprocesses.

Native host spawning is outside this CPU integration fixture. File edits model
bounded workers; validation executes the exact frozen command and uses the
runtime's immutable evidence without mocked success or fabricated log records.
"""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
import shlex
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts"))
from mary_workflow import (
    apply_action, default_state, fingerprint_records, legal_actions_for_state,
    milestone_plan_signature, read_config, read_state, remove_tree,
    seed_core_prompts, sync_prompt_for_phase, update_config, write_config, write_state,
)
from mw_codex import prompt_path_for, render_prompt


def milestone(index: int = 1, *, gate: str = "auto", command: str | None = None) -> dict:
    filename = "product.txt" if index == 1 else f"product-{index}.txt"
    program = f"from pathlib import Path; assert Path({filename!r}).read_text() == 'ready\\n'; print('validated product')"
    return {
        "id": f"milestone-{index}", "title": f"Deliver product {index}",
        "deliverables": [filename],
        "acceptance": [command or shlex.join([sys.executable, "-B", "-c", program])],
        "estimated_scope": 1, "gate": gate,
    }


def architecture(inventory: list[str]) -> dict:
    return {
        "modules": [{"name": "fixture", "responsibility": "Project inputs and outputs", "files": inventory}] if inventory else [],
        "dependency_graph": [], "data_flow": ["Input specification -> product"],
        "state_management": ["Workflow actions persist lifecycle state"],
    }


def brief_payload(inventory: list[str], mode: str = "initial") -> dict:
    return {"action": "submit_brief", "data": {
        "mode": mode,
        "positioning": {"purpose": "Exercise workflow contracts", "audience": "Maintainers", "problem": "Detect invalid delivery", "differentiators": "Actual recorded subprocess evidence"},
        "architecture": architecture(inventory),
        "coverage": {"modules": [{"id": "fixture", "summary": "Reviewed fixture inputs", "files": inventory, "read_files": inventory, "boundary_files": [], "depends_on": []}] if inventory else []},
        "records": [{"id": "fact-1", "kind": "fact", "text": "The fixture has an explicit product requirement", "source": "spec.txt"}],
        "uncertainties": [], "validation": [],
    }}


class WorkflowBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.project = Path(self.tempdir.name)
        (self.project / "spec.txt").write_text("Product must contain ready followed by a newline.\n")
        self.root = self.project / ".mary-workflow"
        (self.root / "prompts").mkdir(parents=True)
        write_config(self.root)
        seed_core_prompts(self.root)
        state = default_state(self.project)
        sync_prompt_for_phase(state, self.root)
        write_state(self.root, state)
        apply_action(self.root, brief_payload(state["project_inventory"]))

    def tearDown(self):
        remove_tree(self.root)
        self.tempdir.cleanup()

    def act(self, action: str, **data):
        return apply_action(self.root, {"action": action, "data": data})

    def rejected(self, action: str, **data):
        with self.assertRaises(SystemExit) as failure:
            self.act(action, **data)
        return str(failure.exception)

    def cli(self, *args, cwd=None, check=True):
        return subprocess.run([sys.executable, "-B", str(REPO_ROOT / "scripts/mary_workflow.py"), *args], cwd=cwd or self.project, text=True, capture_output=True, check=check, timeout=20)

    def freeze(self, milestones=None):
        self.act("update_interview", mode="propose", clarifications=["User requested the stated product behavior"], draft_milestones=milestones or [milestone()])
        state = read_state(self.root)
        return self.act("update_state", phase="PLANNED", clarifications=state["clarifications"], milestones=milestone_plan_signature(state["draft_milestones"]))

    def start(self, milestones=None, **extra):
        state = self.freeze(milestones)
        return self.act("start_execution", plan_digest=state["runtime_meta"]["frozen_plan_digest"], confirmation="/mw-run", source="/mw-run", **extra)

    def task(self, task_id):
        return json.loads((self.root / "tasks" / task_id / "task.json").read_text())

    def dispatch(self, task_id="implement-1", *, role="implementer", agent_id="worker-a", **extra):
        data = {"task_id": task_id, "role": role, "agent_id": agent_id, "objective": "Deliver or verify the specified behavior", **extra}
        if role != "implementer":
            data.setdefault("write_scope", [])
        self.act("delegate_task", **data)
        return self.task(task_id)

    def validate(self, task):
        state = self.act("run_validation", task_id=task["task_id"], attempt_id=task["attempt_id"], acceptance_id="check-1", timeout_seconds=5)
        return state["runtime_meta"]["last_evidence"]

    def submit(self, task, evidence=None, *, changed=None, **extra):
        data = {
            "task_id": task["task_id"], "attempt_id": task["attempt_id"], "status": "ready_for_review",
            "summary": "Artifacts inspected against the required behavior", "files_changed": changed or [],
            "validation": [evidence["evidence_id"]] if evidence else [],
            "scope_deviations": [], "blockers": [], "uncertainties": [], **extra,
        }
        return self.act("submit_worker_result", **data)

    def implementation(self, task_id="implement-1", *, file_change=True):
        task = self.dispatch(task_id)
        filename = read_state(self.root)["milestones"][0]["deliverables"][0]
        if file_change:
            (self.project / filename).write_text("ready\n")
        evidence = self.validate(task)
        self.assertEqual(evidence["result"], "passed")
        self.submit(task, evidence, changed=[filename] if file_change else [])
        state = self.act("mark_task_done", id=task["milestone_id"], task_ids=[task_id])
        self.assertEqual(state["phase"], "REVIEWING")
        return task

    def review(self, implementation, *, phase="FINISHED", agent_id="worker-b", **extra):
        verifier = self.dispatch("verify-" + implementation["task_id"], role="verifier", agent_id=agent_id, reviews_task_ids=[implementation["task_id"]])
        evidence = self.validate(verifier)
        self.submit(verifier, evidence, decision="passed", findings=[], **extra)
        return self.act("set_phase", phase=phase, decision="accepted" if phase == "FINISHED" else "accepted-next", verifier_task_id=verifier["task_id"])

    def test_initial_brief_uses_computed_module_coverage_without_ledger(self):
        state = read_state(self.root)
        self.assertEqual(state["version"], "3.0")
        self.assertEqual(state["project_brief_status"], "complete")
        self.assertEqual(state["project_file_ledger"], [])
        self.assertTrue(state["runtime_meta"]["brief"]["coverage"]["complete"])
        self.assertIn("Exercise workflow contracts", render_prompt(self.project, "mw-plan"))

    def test_empty_repository_can_submit_empty_coverage(self):
        (self.project / "spec.txt").unlink()
        state = default_state(self.project)
        write_state(self.root, state)
        self.assertEqual(state["project_inventory"], [])
        payload = brief_payload([])
        payload["data"]["records"] = []
        accepted = apply_action(self.root, payload)
        self.assertEqual(accepted["runtime_meta"]["brief"]["coverage"]["covered_count"], 0)

    def test_unread_claim_cannot_override_actual_module_coverage(self):
        payload = brief_payload(["spec.txt"], "correction")
        payload["data"]["coverage"]["modules"][0]["read_files"] = []
        payload["data"]["coverage"]["unread_files"] = []
        with self.assertRaises(SystemExit):
            apply_action(self.root, payload)
        self.assertEqual(read_state(self.root)["project_brief_version"], 1)

    def test_incomplete_brief_blocks_planning(self):
        state = read_state(self.root)
        state["project_brief_status"] = "machine_detected"
        write_state(self.root, state)
        self.assertNotIn("update_interview", legal_actions_for_state(state))
        self.rejected("update_interview", mode="propose", clarifications=["Known"], draft_milestones=[milestone()])

    def test_complete_request_needs_no_extra_interview_or_artificial_scope_caps(self):
        tasks = [milestone(index) for index in range(1, 10)]
        tasks[0]["estimated_scope"] = 12
        tasks[0]["deliverables"] = [f"module-{index}.txt" for index in range(12)]
        state = self.freeze(tasks)
        self.assertEqual(state["phase"], "PLANNED")
        self.assertEqual(len(state["milestones"]), 9)
        self.assertEqual(state["milestones"][0]["estimated_scope"], 12)
        self.assertFalse(state["final_plan_confirmed"])
        self.assertEqual(state["runtime_meta"]["plan_revision"], 1)
        self.assertRegex(state["runtime_meta"]["frozen_plan_digest"], r"^[a-f0-9]{64}$")

    def test_pending_real_question_blocks_proposal_and_freeze(self):
        self.act("update_interview", mode="open", round=1, anchor="user request", uncertainty="required output", questions=["Which output format?"], defaults=[])
        self.rejected("update_interview", mode="propose", clarifications=["Invented answer"], draft_milestones=[milestone()])
        self.rejected("update_state", phase="PLANNED", clarifications=[], milestones=[milestone()])
        self.assertEqual(read_state(self.root)["interview_status"], "awaiting_answers")
        self.act("update_interview", mode="resolve", round=1, answers=["Plain text"], complete=True, draft_milestones=[milestone()])
        self.assertEqual(read_state(self.root)["interview_status"], "draft_ready")

    def test_answers_cannot_retroactively_introduce_defaults(self):
        self.act("update_interview", mode="open", round=1, anchor="user request", uncertainty="format", questions=["Which format?"], defaults=[])
        self.rejected("update_interview", mode="resolve", round=1, answers=["Plain text"], defaults=["Also publish externally"], complete=True, draft_milestones=[milestone()])
        self.assertEqual(read_state(self.root)["interview_rounds"][0]["answers"], [])

    def test_plan_action_cannot_claim_authorization_or_execute(self):
        self.act("update_interview", mode="propose", clarifications=["Specified behavior"], draft_milestones=[milestone()])
        state = read_state(self.root)
        data = {"clarifications": state["clarifications"], "milestones": milestone_plan_signature(state["draft_milestones"])}
        self.rejected("update_state", phase="EXECUTING", **data)
        self.rejected("update_state", phase="PLANNED", confirmation="yes", **data)
        self.assertFalse(read_state(self.root)["final_plan_confirmed"])

    def test_run_rendering_is_read_only_and_digest_bound(self):
        state = self.freeze()
        before = {str(p.relative_to(self.root)): p.read_bytes() for p in self.root.rglob("*") if p.is_file()}
        rendered = render_prompt(self.project, "mw-run")
        self.assertIn(state["runtime_meta"]["frozen_plan_digest"], rendered)
        self.assertEqual(before, {str(p.relative_to(self.root)): p.read_bytes() for p in self.root.rglob("*") if p.is_file()})
        running = self.act("start_execution", plan_digest=state["runtime_meta"]["frozen_plan_digest"], confirmation="/mw-run", source="/mw-run")
        self.assertEqual(running["phase"], "EXECUTING")
        self.assertTrue(running["final_plan_confirmed"])
        self.assertTrue(running["lease_run_id"])
        self.rejected("start_execution", plan_digest=state["runtime_meta"]["frozen_plan_digest"], confirmation="/mw-run", source="/mw-run")

    def test_start_rejects_wrong_digest_and_absent_confirmation(self):
        state = self.freeze()
        digest = state["runtime_meta"]["frozen_plan_digest"]
        self.rejected("start_execution", plan_digest="0" * 64, confirmation="/mw-run", source="/mw-run")
        self.rejected("start_execution", plan_digest=digest, confirmation="", source="/mw-run")
        self.rejected("start_execution", plan_digest=digest, confirmation="/mw-plan", source="/mw-plan")
        self.assertEqual(read_state(self.root)["phase"], "PLANNED")

    def test_frozen_plan_tampering_is_detected(self):
        state = self.freeze()
        digest = state["runtime_meta"]["frozen_plan_digest"]
        state["milestones"][0]["title"] = "Different unapproved task"
        write_state(self.root, state)
        self.rejected("start_execution", plan_digest=digest, confirmation="/mw-run", source="/mw-run")

    def test_reopen_requires_refreeze_and_new_revision(self):
        initial = self.freeze()
        self.act("reopen_plan", feedback=["User requests another output"])
        state = read_state(self.root)
        self.assertEqual(state["phase"], "PLANNING")
        self.assertFalse(state["runtime_meta"]["frozen_plan_digest"])
        changed = milestone()
        changed["title"] = "Revised product title"
        self.act("update_interview", mode="revise", feedback=["Updated title"], draft_milestones=[changed])
        state = read_state(self.root)
        frozen = self.act("update_state", phase="PLANNED", clarifications=state["clarifications"], milestones=milestone_plan_signature(state["draft_milestones"]))
        self.assertEqual(frozen["runtime_meta"]["plan_revision"], 2)
        self.assertNotEqual(frozen["runtime_meta"]["frozen_plan_digest"], initial["runtime_meta"]["frozen_plan_digest"])

    def test_actual_implementation_validation_review_and_finish(self):
        self.start()
        task = self.implementation()
        state = read_state(self.root)
        self.assertEqual(state["completed"], 0)
        self.assertEqual(state["milestones"][0]["review"], "pending")
        evidence_id = self.task(task["task_id"])["validation"][0]
        directory = self.root / "tasks" / task["task_id"]
        evidence = json.loads((directory / f"{evidence_id}.json").read_text())
        self.assertEqual(evidence["exit_code"], 0)
        self.assertIn("validated product", (directory / evidence["stdout"]).read_text())
        self.assertGreaterEqual(evidence["duration_ms"], 0)
        accepted = self.review(task)
        self.assertEqual(accepted["phase"], "FINISHED")
        self.assertEqual(accepted["completed"], 1)
        reports = self.root / "reports/C0"
        self.assertEqual(len(list(reports.glob("milestone-1.execution.*.md"))), 1)
        self.assertEqual(len(list(reports.glob("milestone-1.review.*.md"))), 1)
        aggregate = (reports / "milestone-1.md").read_text()
        self.assertIn("kind: execution", aggregate)
        self.assertIn("kind: review", aggregate)
        self.assertEqual(self.task(task["task_id"])["status"], "accepted")

    def test_completion_requires_current_task_and_actual_evidence(self):
        self.start()
        self.rejected("mark_task_done", id="milestone-1")
        self.rejected("mark_task_done", id="milestone-9", task_ids=["invented"])
        self.rejected("mark_task_done", id="milestone-1", task_ids=["invented"])
        task = self.dispatch()
        (self.project / "product.txt").write_text("ready\n")
        self.submit(task, changed=["product.txt"])
        self.rejected("mark_task_done", id="milestone-1", task_ids=[task["task_id"]])
        self.assertEqual(read_state(self.root)["phase"], "EXECUTING")

    def test_failed_actual_validation_cannot_complete(self):
        failing = shlex.join([sys.executable, "-B", "-c", "raise SystemExit(7)"])
        self.start([milestone(command=failing)])
        task = self.dispatch()
        (self.project / "product.txt").write_text("ready\n")
        evidence = self.validate(task)
        self.assertEqual(evidence["exit_code"], 7)
        self.assertEqual(evidence["result"], "failed")
        self.submit(task, evidence, changed=["product.txt"])
        self.rejected("mark_task_done", id="milestone-1", task_ids=[task["task_id"]])

    def test_product_change_invalidates_validation_evidence(self):
        self.start()
        task = self.dispatch()
        (self.project / "product.txt").write_text("ready\n")
        evidence = self.validate(task)
        (self.project / "product.txt").write_text("broken\n")
        with self.assertRaises(SystemExit):
            self.submit(task, evidence, changed=["product.txt"])
        self.assertEqual(self.task(task["task_id"])["status"], "running")

    def test_undeclared_file_change_is_not_hidden_by_files_changed(self):
        self.start()
        task = self.dispatch()
        (self.project / "product.txt").write_text("ready\n")
        (self.project / "unrelated.txt").write_text("unexpected\n")
        with self.assertRaises(SystemExit):
            self.submit(task, changed=["product.txt"])
        self.assertEqual(self.task(task["task_id"])["status"], "running")

    def test_review_requires_distinct_worker_and_cannot_change_plan(self):
        self.start()
        task = self.implementation()
        self.rejected("delegate_task", task_id="self-review", role="verifier", agent_id=task["agent_id"], objective="Self certify", write_scope=[], reviews_task_ids=[task["task_id"]])
        self.rejected("set_phase", phase="FINISHED", decision="accepted")
        self.rejected("update_state", phase="PLANNED", clarifications=[], milestones=[milestone()])
        self.assertEqual(read_state(self.root)["phase"], "REVIEWING")

    def test_single_agent_fallback_exposes_lack_of_independence(self):
        self.start(execution_mode="single_agent")
        task = self.implementation()
        accepted = self.review(task, agent_id=task["agent_id"], review_mode="same_agent")
        self.assertEqual(accepted["phase"], "FINISHED")
        report = (self.root / "reports/C0/milestone-1.review.0001.md").read_text()
        self.assertIn('"independent_review": false', report)

    def test_review_can_return_to_planning_only_with_findings(self):
        self.start()
        self.implementation()
        self.rejected("set_phase", phase="PLANNING", findings=[])
        state = self.act("set_phase", phase="PLANNING", findings=["User-required format is incompatible with current acceptance"])
        self.assertEqual(state["phase"], "PLANNING")
        self.assertEqual(state["milestones"], [])
        self.assertFalse(state["runtime_meta"]["frozen_plan_digest"])

    def test_debug_only_queues_scoped_repair_and_preserves_frozen_digest(self):
        initial = self.start()
        command = initial["milestones"][0]["acceptance"]
        self.act("record_error", command=command[0], stderr="Expected file missing", returncode="1")
        self.rejected("delegate_task", task_id="premature-fix", role="implementer", agent_id="worker-fix", objective="Fix now", write_scope=["product.txt"])
        self.rejected("enqueue_fix_task", title="Overbroad fix", source_error="Missing file", deliverables=["unrelated.txt"], acceptance=command, estimated_scope=1)
        self.rejected("enqueue_fix_task", title="Weaken check", source_error="Missing file", deliverables=["product.txt"], acceptance=["true"], estimated_scope=1)
        repaired = self.act("enqueue_fix_task", title="Create required output", source_error="Expected file missing", deliverables=["product.txt"], acceptance=command, estimated_scope=1)
        self.assertEqual(repaired["phase"], "EXECUTING")
        self.assertEqual(repaired["runtime_meta"]["frozen_plan_digest"], initial["runtime_meta"]["frozen_plan_digest"])
        current = next(m for m in repaired["milestones"] if m["id"] == repaired["current_milestone_id"])
        self.assertEqual(current["repair_of"], "milestone-1")
        self.assertEqual(current["acceptance"], command)
        self.assertEqual(current["write_scope"], ["product.txt"])

    def test_stop_preserves_run_rejects_late_result_and_requires_quiescence(self):
        started = self.start()
        task = self.dispatch()
        (self.project / "product.txt").write_text("ready\n")
        self.cli("stop")
        state = read_state(self.root)
        self.assertEqual(state["status"], "stopped")
        self.assertEqual(state["phase"], "EXECUTING")
        self.assertEqual(self.task(task["task_id"])["status"], "cancelled")
        with self.assertRaises(SystemExit):
            self.submit(task, changed=["product.txt"])
        data = {"plan_digest": state["runtime_meta"]["frozen_plan_digest"], "confirmation": "/mw-run", "source": "/mw-run"}
        self.rejected("resume_execution", **data)
        resumed = self.act("resume_execution", workers_quiescent=True, **data)
        self.assertEqual(resumed["lease_run_id"], started["lease_run_id"])
        self.assertEqual(resumed["phase"], "EXECUTING")
        self.rejected("delegate_task", task_id=task["task_id"], role="implementer", agent_id="worker-a", objective="Reuse stale identity")
        fresh = self.implementation("implement-after-resume", file_change=False)
        self.assertEqual(self.review(fresh)["phase"], "FINISHED")

    def test_confirm_gate_records_user_decision_before_dispatch(self):
        state = self.start([milestone(gate="confirm")])
        self.rejected("delegate_task", task_id="unconfirmed", role="implementer", agent_id="worker-a", objective="Premature work")
        self.act("confirm_milestone", id="milestone-1", confirmation="Execute this gate's work", plan_digest=state["runtime_meta"]["frozen_plan_digest"])
        self.assertEqual(self.dispatch()["milestone_id"], "milestone-1")

    def test_cycle_refresh_merges_delta_then_archives_task_evidence(self):
        self.start()
        task = self.implementation()
        self.review(task)
        self.cli("cycle")
        state = read_state(self.root)
        self.assertEqual(state["project_brief_status"], "refresh_required")
        self.assertEqual(state["project_changed_files"], ["added:product.txt"])
        brief = state["runtime_meta"]["brief"]
        update = {
            "base_version": brief["version"], "reviewed_changed_files": state["project_changed_files"],
            "updated_modules": [{"id": "output", "summary": "Completed verified product", "files": ["product.txt"], "read_files": ["product.txt"], "boundary_files": [], "depends_on": [], "reread_files": ["product.txt"], "review_evidence": "Read actual product and recorded acceptance"}],
            "deleted_modules": [], "retained_modules": [{"id": "fixture", "evidence": "spec.txt fingerprint unchanged and requirement remains valid"}],
            "architecture": architecture(["spec.txt", "product.txt"]),
        }
        self.act("submit_brief", mode="cycle_refresh", update=update)
        refreshed = read_state(self.root)
        self.assertEqual(refreshed["project_brief_version"], 2)
        self.cli("cycle")
        reset = read_state(self.root)
        self.assertEqual(reset["cycle"], "C1")
        self.assertEqual(reset["phase"], "PLANNING")
        self.assertEqual(reset["milestones"], [])
        self.assertFalse(reset["runtime_meta"]["frozen_plan_digest"])
        archive = self.root / "cycles/C0"
        self.assertTrue((archive / "tasks" / task["task_id"] / "result.json").is_file())
        self.assertTrue((archive / "reports/milestone-1.review.0001.md").is_file())
        self.assertEqual(reset["runtime_meta"]["brief"]["records"], brief["records"])

    def test_cycle_cannot_archive_actively_running_work(self):
        self.start()
        result = self.cli("cycle", check=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(read_state(self.root)["phase"], "EXECUTING")
        self.assertFalse((self.root / "cycles/C0").exists())

    def test_run_refuses_unfrozen_planning(self):
        with self.assertRaises(SystemExit):
            prompt_path_for(self.project, "mw-run")
        self.assertEqual(read_state(self.root)["phase"], "PLANNING")

    def test_unsupported_state_versions_require_migration_not_silent_reset(self):
        path = self.root / "state.yaml"
        before = path.read_text()
        for replacement in (before.replace("version: 3.0", "version: 2.1", 1), "\n".join(before.splitlines()[1:]) + "\n"):
            path.write_text(replacement)
            with self.assertRaises(SystemExit):
                read_state(self.root)
            self.assertEqual(path.read_text(), replacement)

    def test_prompt_seeding_preserves_existing_snapshot_by_default(self):
        before = (self.root / "state.yaml").read_bytes()
        target = self.root / "prompts/mw-plan.md"
        target.write_text("Pinned old phase\n")
        self.assertEqual(seed_core_prompts(self.root), 0)
        self.assertEqual(target.read_text(), "Pinned old phase\n")
        self.assertEqual((self.root / "state.yaml").read_bytes(), before)

    def test_existing_state_read_does_not_scan_the_project(self):
        with mock.patch("mary_workflow.detect_project", side_effect=AssertionError("unexpected scan")):
            state = read_state(self.root)
        self.assertEqual(state["project_brief_status"], "complete")

    def test_fingerprints_stream_files_without_whole_file_read(self):
        source = self.project / "streamed.txt"
        source.write_bytes(b"mary-workflow\n" * 100_000 + b"end")
        expected = hashlib.sha256(source.read_bytes()).hexdigest()
        with mock.patch.object(Path, "read_bytes", side_effect=AssertionError("whole file read")):
            records = fingerprint_records(self.project, [source])
        self.assertEqual(records, [{"path": "streamed.txt", "sha256": expected}])

    def test_ignore_can_be_explicitly_empty_and_language_can_change(self):
        project = self.project / "no-default-ignore"
        root = project / ".mary-workflow"
        root.mkdir(parents=True)
        (root / "config.yaml").write_text("init:\n  ignore: []\n")
        (project / "output").mkdir()
        (project / "output/source.csv").write_text("kept\n")
        self.assertEqual(read_config(root)["init_ignore"], [])
        self.assertIn("output/source.csv", default_state(project)["project_inventory"])
        update_config(root, language="auto")
        self.assertEqual(read_config(root)["language"], "auto")
        self.assertEqual(read_config(root)["init_ignore"], [])

    def test_init_during_execution_preserves_phase_plan_and_existing_prompts(self):
        initial = self.start()
        (self.project / "runtime-change.txt").write_text("in progress\n")
        target = self.root / "prompts/mw-plan.md"
        original = target.read_bytes()
        self.cli("init")
        state = read_state(self.root)
        self.assertEqual(state["phase"], "EXECUTING")
        self.assertEqual(state["project_brief_status"], "complete")
        self.assertEqual(state["runtime_meta"]["frozen_plan_digest"], initial["runtime_meta"]["frozen_plan_digest"])
        self.assertEqual(target.read_bytes(), original)

    def test_fresh_cli_init_scans_all_text_and_pins_runtime(self):
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            for index in range(105):
                (project / f"file_{index:03d}.txt").write_text(f"file {index}\n")
            (project / "image.bin").write_bytes(b"\x00\x01binary")
            for folder, name in (("node_modules", "ignored.js"), ("output", "metrics.csv"), ("scratch", "debug.json")):
                (project / folder).mkdir()
                (project / folder / name).write_text("ignored\n")
            (project / "weights.ckpt").write_bytes(b"checkpoint")
            (project / ".maryignore").write_text("scratch/**\n")
            self.cli("init", cwd=project)
            workflow = project / ".mary-workflow"
            state = read_state(workflow)
            self.assertEqual(state["version"], "3.0")
            self.assertEqual(state["phase"], "PLANNING")
            self.assertEqual(len(state["project_inventory"]), 106)
            self.assertIn("file_104.txt", state["project_inventory"])
            for excluded in ("image.bin", "weights.ckpt", "node_modules/ignored.js", "output/metrics.csv", "scratch/debug.json"):
                self.assertNotIn(excluded, state["project_inventory"])
            self.assertEqual(len(list((workflow / "prompts").glob("*.md"))), 10)
            self.assertTrue((workflow / "runtime/scripts/mary_workflow.py").is_file())
            self.assertTrue((project / ".mary-research/reading-profile.md").is_file())
            before = (workflow / "state.yaml").read_bytes()
            self.cli("status", cwd=project)
            self.assertEqual((workflow / "state.yaml").read_bytes(), before)
            remove_tree(workflow)

    def test_course_aliases_keep_local_scene_and_shared_phase_context(self):
        for alias, expected, marker in (("mw-learn", "mw-learn.md", "Course Learning Profile"), ("mw-exam", "mw-exam.md", "ExamPass Profile"), ("mw-review", "mw-exam.md", "ExamPass Profile"), ("slide-learning", "slide-learning.md", "Slide Learning Profile")):
            phase, prompt = prompt_path_for(self.project, alias)
            self.assertEqual(phase, "PLANNING")
            self.assertEqual(prompt.name, expected)
            self.assertIn(marker, render_prompt(self.project, alias))
        for name in ("mw-learn", "mw-exam"):
            source = (REPO_ROOT / "references/phases" / f"{name}.md").read_text()
            self.assertIn("Local Delivery Contract", source)
            self.assertIn("relative path", source)
            self.assertNotIn("notion", source.lower())

    def test_course_profile_is_available_after_finish(self):
        self.start()
        self.review(self.implementation())
        phase, prompt = prompt_path_for(self.project, "mw-exam")
        self.assertEqual(phase, "FINISHED")
        self.assertEqual(prompt.name, "mw-exam.md")
        self.assertIn("ExamPass Profile", render_prompt(self.project, "mw-exam"))


if __name__ == "__main__":
    unittest.main()
