"""SDD runtime integration using real subprocess evidence and temporary projects."""
from __future__ import annotations

import hashlib
import json
import shlex
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import test_workflow_boundaries as boundaries
from mary_workflow import current_plan_digest, milestone_plan_signature, read_state
from mw_sdd import load_change


SCENARIO = "product::Ready output::Write requested output"


class SDDIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.f = boundaries.WorkflowBoundaryTests(methodName="runTest")
        self.f.setUp()
        self.project, self.root = self.f.project, self.f.root
        self.change = self.project / "openspec/changes/ready-output"
        (self.change / "specs/product").mkdir(parents=True)
        (self.change / "proposal.md").write_text("# Ready output\n\nDeliver the requested ready output.\n")
        (self.change / "specs/product/spec.md").write_text(
            "## Purpose\nProvide the requested ready output.\n\n## ADDED Requirements\n\n### Requirement: Ready output\n"
            "The product MUST contain ready followed by a newline.\n\n"
            "#### Scenario: Write requested output\n"
            "- **WHEN** the product is generated\n- **THEN** its contents are ready followed by a newline.\n"
        )
        task = boundaries.milestone()
        title = task.pop("title")
        task["covers"] = {SCENARIO: ["check-1"]}
        (self.change / "tasks.md").write_text(
            f"# Tasks\n\n- [ ] 1.1 {title}\n```mary-task\n{json.dumps(task, indent=2)}\n```\n"
        )

    def tearDown(self):
        self.f.tearDown()

    def freeze(self):
        binding = load_change(self.project, "ready-output")
        self.f.act("update_interview", mode="propose", clarifications=["Deliver the reviewed ready output"],
                   draft_milestones=binding["milestones"])
        self.f.act("bind_change", change_id="ready-output")
        state = read_state(self.root)
        return self.f.act("update_state", phase="PLANNED", clarifications=state["clarifications"],
                          milestones=milestone_plan_signature(state["draft_milestones"]))

    def start(self):
        state = self.freeze()
        return self.f.act("start_execution", plan_digest=state["runtime_meta"]["frozen_plan_digest"],
                          source="user_instruction", intent="execute", confirmation="通过，直接修改。")

    def review(self, implementation):
        return self.f.review(implementation, scenario_reviews=[{
            "scenario": SCENARIO, "decision": "passed",
            "evidence": [f"tasks/{implementation['task_id']}/result.json", "product.txt"],
        }])

    def test_sdd_check_is_read_only_and_emits_source_plan(self):
        before = {p.relative_to(self.project): p.read_bytes() for p in self.project.rglob("*") if p.is_file()}
        result = self.f.cli("sdd-check", "ready-output")
        binding = json.loads(result.stdout)
        self.assertEqual(binding["trace"][0]["scenario"], SCENARIO)
        self.assertEqual(binding["milestones"][0]["id"], "milestone-1")
        after = {p.relative_to(self.project): p.read_bytes() for p in self.project.rglob("*") if p.is_file()}
        self.assertEqual(before, after)

    def test_explicit_natural_language_execution_records_real_authorization(self):
        state = self.start()
        authorization = state["runtime_meta"]["authorizations"][-1]
        self.assertEqual(state["phase"], "EXECUTING")
        self.assertEqual(authorization["source"], "user_instruction")
        self.assertEqual(authorization["confirmation"], "通过，直接修改。")
        self.assertEqual(authorization["plan_digest"], state["runtime_meta"]["frozen_plan_digest"])
        task = self.f.dispatch()
        self.assertEqual(task["sdd"]["change_id"], "ready-output")
        self.assertEqual(task["sdd"]["trace"][0]["scenario"], SCENARIO)

    def test_unspecified_natural_language_intent_cannot_start(self):
        state = self.freeze()
        error = self.f.rejected("start_execution", source="user_instruction", confirmation="可以",
                                plan_digest=state["runtime_meta"]["frozen_plan_digest"])
        self.assertIn("intent=execute", error)
        self.assertEqual(read_state(self.root)["phase"], "PLANNED")

    def test_bind_rejects_plan_not_derived_from_tasks(self):
        task = boundaries.milestone()
        task["title"] = "A different reviewed task"
        self.f.act("update_interview", mode="propose", clarifications=["Review a different task"], draft_milestones=[task])
        self.assertIn("tasks.md differs", self.f.rejected("bind_change", change_id="ready-output"))
        self.assertNotIn("sdd", read_state(self.root)["runtime_meta"])

    def test_artifact_drift_blocks_start_and_can_be_rebound_after_reopen(self):
        state = self.freeze()
        original = state["runtime_meta"]["frozen_plan_digest"]
        (self.change / "proposal.md").write_text("# Revised rationale\n\nThe same behavior now has clarified motivation.\n")
        self.assertIn("drift", self.f.rejected("start_execution", source="/mw-run", confirmation="/mw-run", plan_digest=original))
        self.f.act("reopen_plan", feedback="Review the clarified proposal")
        rebound = self.freeze()
        self.assertNotEqual(original, rebound["runtime_meta"]["frozen_plan_digest"])
        self.assertGreater(rebound["runtime_meta"]["plan_revision"], state["runtime_meta"]["plan_revision"])

    def test_artifact_drift_rejects_late_worker_evidence(self):
        self.start()
        task = self.f.dispatch()
        (self.project / "product.txt").write_text("ready\n")
        evidence = self.f.validate(task)
        self.assertEqual(evidence["result"], "passed")
        (self.change / "proposal.md").write_text("# Changed after validation\n")
        with self.assertRaises(SystemExit) as failure:
            self.f.submit(task, evidence, changed=["product.txt"])
        self.assertIn("drift", str(failure.exception))
        self.assertFalse((self.root / "tasks/implement-1/result.json").exists())

    def test_zero_exit_validation_is_cancelled_when_specs_change_during_command(self):
        tasks_path = self.change / "tasks.md"
        original = boundaries.milestone()["acceptance"][0]
        program = "from pathlib import Path; Path('openspec/changes/ready-output/proposal.md').write_text('# Changed during validation\\n')"
        command = shlex.join([sys.executable, "-B", "-c", program])
        tasks_path.write_text(tasks_path.read_text().replace(json.dumps(original), json.dumps(command)))
        self.start()
        task = self.f.dispatch()
        evidence = self.f.validate(task)
        self.assertEqual(evidence["exit_code"], 0)
        self.assertEqual(evidence["result"], "cancelled")
        self.assertIn("drift", evidence["summary"])

    def test_review_requires_scenario_judgments_before_acceptance(self):
        self.start()
        implementation = self.f.implementation()
        verifier = self.f.dispatch("verify-1", role="verifier", agent_id="independent-reviewer",
                                   reviews_task_ids=[implementation["task_id"]])
        evidence = self.f.validate(verifier)
        with self.assertRaises(SystemExit) as failure:
            self.f.submit(verifier, evidence, decision="passed", findings=[])
        self.assertIn("scenario_reviews", str(failure.exception))
        self.assertIn("- [ ] 1.1", (self.change / "tasks.md").read_text())
        self.f.submit(verifier, evidence, decision="passed", findings=[], scenario_reviews=[{
            "scenario": SCENARIO, "decision": "passed", "evidence": ["product.txt"],
        }])
        done = self.f.act("set_phase", phase="FINISHED", decision="accepted", verifier_task_id=verifier["task_id"])
        self.assertEqual(done["phase"], "FINISHED")
        self.assertIn("- [x] 1.1", (self.change / "tasks.md").read_text())
        self.assertEqual(load_change(self.project, "ready-output"), done["runtime_meta"]["sdd"])

    def test_pause_resume_preserves_run_and_sdd_digest(self):
        state = self.start()
        self.f.cli("stop")
        resumed = self.f.act("resume_execution", source="user_instruction", intent="execute",
                             confirmation="继续执行这个已确认计划", workers_quiescent=True,
                             plan_digest=state["runtime_meta"]["frozen_plan_digest"])
        self.assertEqual(resumed["lease_run_id"], state["lease_run_id"])
        self.assertEqual(resumed["runtime_meta"]["sdd"], state["runtime_meta"]["sdd"])

    def test_unbound_legacy_digest_keeps_original_hash_contract(self):
        state = self.f.freeze()
        payload = {"cycle": state.get("cycle", "C0"), "clarifications": list(state["clarifications"]),
                   "milestones": milestone_plan_signature([m for m in state["milestones"] if not m.get("repair_of")])}
        old_hash = hashlib.sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        self.assertEqual(current_plan_digest(state), old_hash)

    def test_worker_write_scope_cannot_include_bound_source(self):
        self.start()
        error = self.f.rejected("delegate_task", task_id="source-editor", role="implementer", agent_id="worker-a",
            objective="Attempt to edit frozen source", write_scope=["openspec/changes/ready-output/proposal.md"])
        self.assertIn("coordinator-owned", error)
        self.assertFalse((self.root / "tasks/source-editor/task.json").exists())

    def test_product_drift_after_finish_blocks_archive_and_allows_replan(self):
        self.start()
        implementation = self.f.implementation()
        finished = self.review(implementation)
        (self.project / "product.txt").write_text("changed after acceptance\n")
        result = self.f.cli("cycle", check=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Product changed after SDD acceptance", result.stderr)
        self.assertTrue(self.change.is_dir())
        self.assertFalse((self.project / "openspec/specs/product/spec.md").exists())
        replanned = self.f.act("request_replan", feedback="The accepted product changed; repeat execution and scenario review")
        self.assertEqual(replanned["phase"], "PLANNING")
        self.assertEqual(replanned["runtime_meta"]["plan_history"][-1]["sdd"], finished["runtime_meta"]["sdd"])
        self.assertFalse(replanned["runtime_meta"]["frozen_plan_digest"])
        rebound = self.freeze()
        self.assertGreater(rebound["runtime_meta"]["plan_revision"], finished["runtime_meta"]["plan_revision"])

    def test_repair_uses_original_scenario_trace_without_premature_task_completion(self):
        initial = self.start()
        command = initial["milestones"][0]["acceptance"]
        self.f.act("record_error", command=command[0], stderr="Product missing", returncode="1")
        self.f.act("enqueue_fix_task", title="Produce required output", source_error="Product missing",
            deliverables=["product.txt"], acceptance=command, estimated_scope=1)
        repair = self.f.implementation(task_id="repair-1")
        self.assertEqual(repair["sdd"]["trace"][0]["scenario"], SCENARIO)
        self.assertEqual(repair["sdd"]["trace"][0]["milestone_id"], "milestone-1")
        self.f.review(repair, phase="EXECUTING", scenario_reviews=[{
            "scenario": SCENARIO, "decision": "passed", "evidence": ["product.txt"],
        }])
        self.assertIn("- [ ] 1.1", (self.change / "tasks.md").read_text())
        implementation = self.f.implementation(task_id="original-after-repair", file_change=False)
        done = self.review(implementation)
        self.assertEqual(done["phase"], "FINISHED")
        self.assertIn("- [x] 1.1", (self.change / "tasks.md").read_text())
        self.f.cli("cycle")
        self.assertTrue((self.project / "openspec/specs/product/spec.md").is_file())

    def refresh_brief(self):
        state = read_state(self.root)
        changed = [p.relative_to(self.project).as_posix() for p in self.project.rglob("*")
                   if p.is_file() and self.root not in p.parents and p.name != "spec.txt"]
        brief = state["runtime_meta"]["brief"]
        self.f.act("submit_brief", mode="cycle_refresh", update={
            "base_version": brief["version"], "reviewed_changed_files": state["project_changed_files"],
            "updated_modules": [{"id": "output", "summary": "Verified product and accepted SDD change",
                "files": changed, "read_files": changed, "reread_files": changed,
                "boundary_files": [], "depends_on": [], "review_evidence": "Read product, merged spec and archived change"}],
            "deleted_modules": [], "retained_modules": [{"id": "fixture", "evidence": "Input specification remains unchanged"}],
            "architecture": boundaries.architecture(["spec.txt", *changed]),
        })

    def test_archived_change_allows_exploration_and_records_later_unreviewed_work(self):
        self.start()
        self.review(self.f.implementation())
        self.f.cli("cycle")
        (self.project / "product.txt").write_text("later work has not been accepted\n")
        result = self.f.cli("cycle")
        self.assertIn("后续产品变化", result.stdout)
        explorer = self.f.dispatch("refresh-explorer", role="explorer", agent_id="reader")
        self.f.submit(explorer)
        self.refresh_brief()
        self.f.cli("cycle")
        self.assertEqual(read_state(self.root)["cycle"], "C1")
        archived = read_state(self.root / "cycles/C0")
        self.assertTrue(archived["runtime_meta"]["sdd_post_archive_changes"])
        self.assertEqual((self.project / "product.txt").read_text(), "later work has not been accepted\n")

    def test_unfinished_sdd_cycle_preserves_unmerged_change(self):
        self.start()
        self.f.cli("stop")
        self.f.cli("cycle", "--workers-quiescent")
        self.refresh_brief()
        self.f.cli("cycle")
        self.assertEqual(read_state(self.root)["cycle"], "C1")
        self.assertTrue(self.change.is_dir())
        self.assertIn("- [ ]", (self.change / "tasks.md").read_text())
        self.assertFalse((self.project / "openspec/specs/product/spec.md").exists())

    def test_replanning_explorer_can_report_while_old_binding_is_stale(self):
        self.start()
        self.f.act("request_replan", feedback="Investigate a clarified requirement")
        (self.change / "proposal.md").write_text("# Refined rationale\n")
        explorer = self.f.dispatch("replan-explorer", role="explorer", agent_id="reader")
        self.f.submit(explorer)
        self.assertEqual(self.f.task("replan-explorer")["status"], "ready_for_review")

    def test_accepted_change_merges_specs_refreshes_brief_and_archives_evidence(self):
        self.start()
        implementation = self.f.implementation()
        self.review(implementation)
        self.f.cli("cycle")
        state = read_state(self.root)
        self.assertEqual(state["project_brief_status"], "refresh_required")
        self.assertFalse(self.change.exists())
        archive = self.project / "openspec/changes/archive/C0-ready-output"
        self.assertIn("- [x] 1.1", (archive / "tasks.md").read_text())
        self.assertIn("### Requirement: Ready output", (self.project / "openspec/specs/product/spec.md").read_text())
        self.refresh_brief()
        self.f.cli("cycle")
        reset = read_state(self.root)
        self.assertEqual(reset["cycle"], "C1")
        self.assertEqual(reset["phase"], "PLANNING")
        self.assertNotIn("sdd", reset["runtime_meta"])
        cycle = self.root / "cycles/C0"
        self.assertTrue((cycle / "tasks/implement-1/result.json").is_file())
        self.assertTrue((cycle / "reports/milestone-1.review.0001.md").is_file())
        self.assertTrue((cycle / "sdd-archive.json").is_file())


if __name__ == "__main__":
    unittest.main()
