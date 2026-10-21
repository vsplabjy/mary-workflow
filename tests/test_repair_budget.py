"""Repair budget runtime behavior: real actions, real subprocess evidence.

These cases exercise the actual workflow runtime (no source-string or wiring
assertions): default and explicit budgets, third-round refusal, rework and
redispatch accounting, stop/resume and history persistence, and the
failed-validation loop boundary.
"""
from __future__ import annotations

import shlex
import sys
import unittest
from unittest import mock

import test_workflow_boundaries as boundaries
from mary_workflow import legal_actions_for_state, read_state, write_state


def milestone_with_budget(rounds=None, **extra):
    task = boundaries.milestone(**extra)
    if rounds is not None:
        task["max_repair_rounds"] = rounds
    return task


class RepairBudgetTests(unittest.TestCase):
    def setUp(self):
        self.f = boundaries.WorkflowBoundaryTests(methodName="runTest")
        self.f.setUp()
        self.root, self.project = self.f.root, self.f.project

    def tearDown(self):
        self.f.tearDown()

    def budget(self, origin="milestone-1"):
        state = read_state(self.root)
        return state.get("runtime_meta", {}).get("repair_budget", {}).get("history", {}).get(origin, {})

    def rounds_used(self, origin="milestone-1"):
        return int(self.budget(origin).get("rounds_used", 0))

    def error_then_fix(self, title="Fix the product"):
        state = read_state(self.root)
        command = state["milestones"][0]["acceptance"]
        self.f.act("record_error", command=command[0], stderr="missing output", returncode="1")
        return self.f.act("enqueue_fix_task", title=title)

    def test_budget_field_validation_rejects_bool_negative_float_and_string(self):
        for bad in (True, False, -1, 1.5, "2"):
            draft = milestone_with_budget(bad)
            with self.assertRaises(SystemExit) as failure:
                self.f.freeze([draft])
            self.assertIn("max_repair_rounds", str(failure.exception))
            self.assertEqual(read_state(self.root)["phase"], "PLANNING")

    def test_zero_budget_allows_initial_but_refuses_first_repair(self):
        self.f.start([milestone_with_budget(0)])
        task = self.f.dispatch()  # the initial dispatch itself never charges
        self.assertEqual(self.rounds_used(), 0)
        self.f.submit(task, changed=[], status="failed",
                      blockers=[{"reason": "Implementation missing", "attempted": ["Ran once"]}])
        self.f.act("record_error", command="check", stderr="Implementation missing", returncode=1)
        error = self.f.rejected("enqueue_fix_task", title="Retry once")
        self.assertIn("Repair budget exhausted", error)
        self.assertIn("0/0", error)
        state = read_state(self.root)
        self.assertEqual(state["phase"], "DEBUGGING")

    def test_default_two_rounds_then_third_refused(self):
        self.f.start()  # default budget 2, omitted field
        state = read_state(self.root)
        self.assertNotIn("max_repair_rounds", state["milestones"][0])
        for expected_used in (1, 2):
            self.assertEqual(self.rounds_used(), expected_used - 1)
            self.error_then_fix(f"Repair {expected_used}")
            self.assertEqual(self.rounds_used(), expected_used)
        self.f.act("record_error", command="check", stderr="third failure", returncode=1)
        third = self.f.rejected("enqueue_fix_task", title="Third repair")
        self.assertIn("2/2", third)
        self.assertIn("user", third)

    def test_review_needs_fix_consumes_and_is_refused_at_exhaustion(self):
        self.f.start()
        task = self.f.dispatch()
        (self.project / "product.txt").write_text("ready\n")
        evidence = self.f.validate(task)
        self.f.submit(task, evidence, changed=["product.txt"])
        self.f.act("mark_task_done", id="milestone-1", task_ids=[task["task_id"]])
        verifier = self.f.dispatch("verify-1", role="verifier", agent_id="worker-b",
                                   reviews_task_ids=[task["task_id"]])
        v_evidence = self.f.validate(verifier)
        self.f.submit(verifier, v_evidence, decision="needs-fix", findings=["Output shape wrong"])
        self.assertEqual(self.rounds_used(), 0)
        self.f.act("set_phase", phase="EXECUTING", decision="needs-fix",
                   verifier_task_id=verifier["task_id"], findings=["Output shape wrong"])
        self.assertEqual(self.rounds_used(), 1)
        # Second needs-fix round is allowed (budget 2), third is refused.
        task2 = self.f.dispatch("implement-2")
        (self.project / "product.txt").write_text("ready\n")
        evidence2 = self.f.validate(task2)
        self.f.submit(task2, evidence2, changed=[])
        self.f.act("mark_task_done", id="milestone-1", task_ids=[task2["task_id"]])
        verifier2 = self.f.dispatch("verify-2", role="verifier", agent_id="worker-b",
                                    reviews_task_ids=[task2["task_id"]])
        v_evidence2 = self.f.validate(verifier2)
        self.f.submit(verifier2, v_evidence2, decision="needs-fix", findings=["Still wrong"])
        self.f.act("set_phase", phase="EXECUTING", decision="needs-fix",
                   verifier_task_id=verifier2["task_id"], findings=["Still wrong"])
        self.assertEqual(self.rounds_used(), 2)
        task3 = self.f.dispatch("implement-3")
        (self.project / "product.txt").write_text("ready\n")
        evidence3 = self.f.validate(task3)
        self.f.submit(task3, evidence3, changed=[])
        self.f.act("mark_task_done", id="milestone-1", task_ids=[task3["task_id"]])
        verifier3 = self.f.dispatch("verify-3", role="verifier", agent_id="worker-b",
                                    reviews_task_ids=[task3["task_id"]])
        v_evidence3 = self.f.validate(verifier3)
        self.f.submit(verifier3, v_evidence3, decision="needs-fix", findings=["No budget left"])
        error = self.f.rejected("set_phase", phase="EXECUTING", decision="needs-fix",
                                verifier_task_id=verifier3["task_id"], findings=["No budget left"])
        self.assertIn("Repair budget exhausted", error)

    def test_failed_worker_redispatch_consumes_even_without_retry_of(self):
        root = milestone_with_budget()
        root["deliverables"] = root["write_scope"] = ["product.txt", "part-b.txt"]
        self.f.start([root])
        task = self.f.dispatch()
        self.f.submit(task, changed=[], status="failed",
                      blockers=[{"reason": "Environment broken", "attempted": ["Retried once"]}])
        self.assertEqual(self.rounds_used(), 0)
        fresh = self.f.dispatch("implement-retry", agent_id="worker-b",
                                deliverables=["product.txt"], write_scope=["product.txt"])
        self.assertEqual(self.rounds_used(), 1)
        # Sibling dispatch in the same round stays free.
        sibling = self.f.dispatch("implement-sibling", agent_id="worker-c",
                                  deliverables=["part-b.txt"], write_scope=["part-b.txt"])
        self.assertEqual(self.rounds_used(), 1)
        self.assertEqual(fresh["attempt_id"] != sibling["attempt_id"], True)

    def test_exhaustion_refuses_redispatch_and_retry_of_only(self):
        self.f.start()
        first = self.f.dispatch("implement-1")
        self.f.submit(first, changed=[], status="failed",
                      blockers=[{"reason": "One", "attempted": ["A"]}])
        self.f.dispatch("implement-2", agent_id="worker-b")
        second = self.f.task("implement-2")
        self.f.submit(second, changed=[], status="failed",
                      blockers=[{"reason": "Two", "attempted": ["B"]}])
        # Round 1 was charged at implement-2 dispatch; the second failure needs round 2.
        self.assertEqual(self.rounds_used(), 1)
        self.f.dispatch("implement-3", agent_id="worker-c")
        self.assertEqual(self.rounds_used(), 2)
        third = self.f.task("implement-3")
        self.f.submit(third, changed=[], status="failed",
                      blockers=[{"reason": "Three", "attempted": ["C"]}])
        error_new = self.f.rejected("delegate_task", task_id="implement-4", role="implementer",
                                    agent_id="worker-d", objective="Another try")
        self.assertIn("Repair budget exhausted", error_new)
        error_retry = self.f.rejected("delegate_task", task_id="implement-5", role="implementer",
                                      agent_id="worker-e", objective="retry_of only",
                                      retry_of="implement-3")
        self.assertIn("Repair budget exhausted", error_retry)

    def test_exhaustion_survives_stop_resume_and_phase_is_preserved(self):
        self.f.start()
        for index in (1, 2):
            self.error_then_fix(f"Repair {index}")
            repair = next(m for m in read_state(self.root)["milestones"]
                          if m.get("repair_of") == "milestone-1" and m["status"] == "pending")
            self.f.dispatch(f"repair-impl-{index}", agent_id="worker-r", workers_quiescent=True)
        self.assertEqual(self.rounds_used(), 2)
        self.f.cli("stop")
        state = read_state(self.root)
        data = {"plan_digest": state["runtime_meta"]["frozen_plan_digest"],
                "confirmation": "/mw-run", "source": "/mw-run", "workers_quiescent": True}
        self.f.act("resume_execution", **data)
        self.assertEqual(self.rounds_used(), 2)
        self.f.act("record_error", command="inspect", stderr="still broken", returncode="1")
        error = self.f.rejected("enqueue_fix_task", title="After resume")
        self.assertIn("2/2", error)
        resumed = read_state(self.root)
        self.assertEqual(resumed["phase"], "DEBUGGING")
        self.assertNotEqual(resumed["phase"], "FINISHED")

    def test_history_survives_replan_and_blocks_new_rounds(self):
        self.f.start()
        self.error_then_fix("Only repair")
        self.assertEqual(self.rounds_used(), 1)
        self.f.act("delegate_task", task_id="repair-impl", role="implementer",
                   agent_id="worker-r", objective="Do the repair", workers_quiescent=True)
        # Replan with a same-id milestone: history must persist and still bind.
        self.f.act("request_replan", feedback="User approved a scope change",
                   workers_quiescent=True)
        state = read_state(self.root)
        self.assertEqual(self.rounds_used(), 1)
        self.assertEqual(state["phase"], "PLANNING")
        # New plan, same origin id: the explicit budget becomes the new
        # absolute authorized maximum for the lineage (1 used + 1 more = 2).
        self.f.freeze([milestone_with_budget(2)])
        state = read_state(self.root)
        self.f.act("start_execution", plan_digest=state["runtime_meta"]["frozen_plan_digest"],
                   confirmation="/mw-run", source="/mw-run")
        self.error_then_fix("Spend the authorized round")
        self.assertEqual(self.rounds_used(), 2)
        self.f.act("record_error", command="check", stderr="no rounds remain", returncode=1)
        self.f.rejected("enqueue_fix_task", title="Beyond new budget")

    def test_unknown_history_refuses_instead_of_assuming_zero(self):
        self.f.start()
        state = read_state(self.root)
        state.setdefault("runtime_meta", {}).setdefault("repair_budget", {})
        state["runtime_meta"]["repair_budget"]["history"] = {"milestone-1": {"rounds_used": 0, "history_known": False}}
        write_state(self.root, state)
        self.f.act("record_error", command="x", stderr="y", returncode="1")
        error = self.f.rejected("enqueue_fix_task", title="Any repair")
        self.assertIn("cannot be determined", error)

    def test_user_authorization_via_confirm_milestone_extends_budget(self):
        self.f.start([milestone_with_budget(1)])
        task = self.f.dispatch()
        self.f.submit(task, changed=[], status="failed",
                      blockers=[{"reason": "Broke", "attempted": ["Once"]}])
        self.f.dispatch("implement-2", agent_id="worker-b")
        self.assertEqual(self.rounds_used(), 1)
        second = self.f.task("implement-2")
        self.f.submit(second, changed=[], status="failed",
                      blockers=[{"reason": "Again", "attempted": ["Twice"]}])
        self.f.rejected("delegate_task", task_id="implement-3", role="implementer",
                        agent_id="worker-c", objective="Refused at exhaustion")
        state = read_state(self.root)
        # Explicit user authorization adds a round; the self-agent cannot.
        self.f.rejected("confirm_milestone", id="milestone-1", confirmation="",
                        plan_digest=state["runtime_meta"]["frozen_plan_digest"],
                        authorize_repair_rounds=1)
        state = read_state(self.root)
        self.f.act("confirm_milestone", id="milestone-1",
                   confirmation="User approves one more repair round",
                   plan_digest=state["runtime_meta"]["frozen_plan_digest"],
                   authorize_repair_rounds=1)
        entry = self.budget()
        self.assertEqual(entry.get("authorized_max"), 2)
        self.f.dispatch("implement-3", agent_id="worker-c")
        self.assertEqual(self.rounds_used(), 2)
        third = self.f.task("implement-3")
        self.f.submit(third, changed=[], status="failed",
                      blockers=[{"reason": "Done for good", "attempted": ["Three tries"]}])
        self.f.rejected("delegate_task", task_id="implement-4", role="implementer",
                        agent_id="worker-d", objective="Refused again")

    def test_parallel_initial_slices_and_verifiers_never_charge(self):
        root = milestone_with_budget(2)
        root["deliverables"] = root["write_scope"] = ["product.txt", "product-2.txt"]
        root["acceptance"].append(shlex.join([
            sys.executable, "-B", "-c",
            "from pathlib import Path; assert Path('product-2.txt').read_text() == 'ready\\n'"
        ]))
        self.f.start([root])
        writer_a = self.f.dispatch("slice-a", agent_id="worker-a",
                                   deliverables=["product.txt"], write_scope=["product.txt"],
                                   acceptance_ids=["check-1"])
        writer_b = self.f.dispatch("slice-b", agent_id="worker-b",
                                   deliverables=["product-2.txt"], write_scope=["product-2.txt"],
                                   acceptance_ids=["check-2"])
        self.assertEqual(self.rounds_used(), 0)
        for task, filename in ((writer_a, "product.txt"), (writer_b, "product-2.txt")):
            (self.project / filename).write_text("ready\n")
        for task, filename, check_id in ((writer_a, "product.txt", "check-1"),
                                         (writer_b, "product-2.txt", "check-2")):
            state = self.f.act("run_validation", task_id=task["task_id"],
                               attempt_id=task["attempt_id"], acceptance_id=check_id,
                               timeout_seconds=5)
            self.f.submit(task, state["runtime_meta"]["last_evidence"], changed=[filename])
        self.f.act("mark_task_done", id="milestone-1", task_ids=["slice-a", "slice-b"])
        verifier = self.f.dispatch("verify-1", role="verifier", agent_id="worker-c",
                                   reviews_task_ids=["slice-a", "slice-b"])
        evidence_ids = []
        for check_id in ("check-1", "check-2"):
            state = self.f.act("run_validation", task_id=verifier["task_id"],
                               attempt_id=verifier["attempt_id"], acceptance_id=check_id,
                               timeout_seconds=5)
            evidence_ids.append(state["runtime_meta"]["last_evidence"]["evidence_id"])
        self.f.act("submit_worker_result", task_id=verifier["task_id"],
                   attempt_id=verifier["attempt_id"], status="ready_for_review",
                   summary="Both independent slices match the contract", files_changed=[],
                   validation=evidence_ids, scope_deviations=[], blockers=[], uncertainties=[],
                   decision="passed", findings=[])
        accepted = self.f.act("set_phase", phase="FINISHED", decision="accepted",
                              verifier_task_id=verifier["task_id"])
        self.assertEqual(accepted["phase"], "FINISHED")
        self.assertEqual(self.rounds_used("milestone-1"), 0)


    def test_failed_validation_ends_attempt_write_authorization(self):
        failing = shlex.join([sys.executable, "-B", "-c", "raise SystemExit(3)"])
        self.f.start([boundaries.milestone(command=failing)])
        task = self.f.dispatch()
        (self.project / "product.txt").write_text("ready\n")
        evidence = self.f.validate(task)
        self.assertEqual(evidence["result"], "failed")
        # Rerunning validation on the same failed attempt is refused.
        error = self.f.rejected("run_validation", task_id=task["task_id"],
                                attempt_id=task["attempt_id"], acceptance_id="check-1",
                                timeout_seconds=5)
        self.assertIn("already failed validation", error)
        # Pseudo-ready submission of the failed attempt is refused.
        error_ready = self.f.rejected("submit_worker_result", task_id=task["task_id"],
                                      attempt_id=task["attempt_id"], status="ready_for_review",
                                      summary="Looks done", files_changed=["product.txt"],
                                      validation=[], scope_deviations=[], blockers=[],
                                      uncertainties=[])
        self.assertIn("cannot become ready_for_review", error_ready)
        # A fresh dispatch after the failure is charged exactly one round.
        self.f.submit(task, changed=["product.txt"], status="failed",
                      blockers=[{"reason": "Command exited 3", "attempted": ["Actual validation"]}])
        self.assertEqual(self.rounds_used(), 0)
        self.f.dispatch("implement-fresh", agent_id="worker-b")
        self.assertEqual(self.rounds_used(), 1)

    def test_duplicate_registration_does_not_double_charge(self):
        self.f.start()
        self.error_then_fix("One repair")
        used = self.rounds_used()
        ledger = read_state(self.root)["runtime_meta"]["repair_budget"]["rounds"]
        self.assertEqual(len(ledger), 1)
        # Redispatching within the same registered round (the fix milestone's
        # first implementer) does not charge again even after a cancel.
        self.f.dispatch("fix-impl", agent_id="worker-r")
        self.assertEqual(self.rounds_used(), used)

    def test_exhausted_debugging_keeps_legal_recovery_actions(self):
        self.f.start()
        self.error_then_fix("One")
        self.error_then_fix("Two")
        state = read_state(self.root)
        self.assertEqual(state["phase"], "EXECUTING")
        self.f.act("record_error", command="inspect", stderr="third failure", returncode="1")
        state = read_state(self.root)
        self.assertEqual(state["phase"], "DEBUGGING")
        legal = legal_actions_for_state(state)
        self.assertIn("request_replan", legal)
        self.assertNotIn("mark_task_done", legal)


    def test_relabeling_milestone_during_replan_cannot_reset_exhaustion(self):
        self.f.start([milestone_with_budget(1)])
        self.error_then_fix()
        self.f.act("request_replan", feedback="Keep the same work with a new label",
                   workers_quiescent=True)
        relabeled = boundaries.milestone()
        relabeled["id"] = "milestone-9"
        self.f.freeze([relabeled])
        state = read_state(self.root)
        self.f.act("start_execution", plan_digest=state["runtime_meta"]["frozen_plan_digest"],
                   source="/mw-run", confirmation="/mw-run")
        error = self.f.rejected("delegate_task", task_id="renamed-attempt",
                                role="implementer", agent_id="new-worker",
                                objective="Same work under a new label")
        self.assertIn("Repair budget exhausted", error)
        self.assertEqual(self.rounds_used(), 1)

    def test_missing_legacy_ledger_is_unknown_not_zero(self):
        self.f.start()
        self.error_then_fix()
        state = read_state(self.root)
        state["runtime_meta"].pop("repair_budget")
        write_state(self.root, state)
        self.f.act("record_error", command="old check", stderr="legacy failure", returncode=1)
        error = self.f.rejected("enqueue_fix_task", title="Unrecorded historical repair")
        self.assertIn("cannot be determined", error)

    def test_budget_is_durable_before_dispatch_is_published(self):
        import mary_workflow as runtime
        self.f.start()
        first = self.f.dispatch()
        self.f.submit(first, changed=[], status="failed",
                      blockers=[{"reason": "Initial failure", "attempted": ["Initial attempt"]}])
        actual_write = runtime.write_state
        def interrupt_after_task_publication(root, state):
            if (root / "tasks" / "new-repair" / "task.json").exists():
                raise OSError("Interrupted final coordinator write")
            actual_write(root, state)
        with mock.patch.object(runtime, "write_state", side_effect=interrupt_after_task_publication):
            with self.assertRaises(OSError):
                self.f.dispatch("new-repair", agent_id="worker-b")
        self.assertTrue((self.root / "tasks" / "new-repair" / "task.json").exists())
        self.assertEqual(self.rounds_used(), 1)

    def test_explicit_null_budget_is_not_an_omitted_budget(self):
        draft = boundaries.milestone()
        draft["max_repair_rounds"] = None
        with self.assertRaises(SystemExit):
            self.f.freeze([draft])


    def test_cycle_does_not_reset_unfinished_same_work(self):
        self.f.start([milestone_with_budget(1)])
        self.error_then_fix()
        self.f.cli("stop")
        self.f.cli("cycle")
        self.f.start()
        error = self.f.rejected("delegate_task", task_id="cycle-bypass",
                                role="implementer", agent_id="worker-new",
                                objective="Same unfinished work in another cycle")
        self.assertIn("Repair budget exhausted", error)
        self.assertEqual(self.rounds_used(), 1)

    def test_new_cycle_unrelated_work_has_its_own_initial_budget(self):
        self.f.start([milestone_with_budget(1)])
        self.error_then_fix()
        self.f.cli("stop")
        self.f.cli("cycle")
        new_task = boundaries.milestone()
        new_task["deliverables"] = ["different-product.txt"]
        new_task["acceptance"] = [shlex.join([
            sys.executable, "-B", "-c",
            "from pathlib import Path; assert Path('different-product.txt').read_text() == 'ready\\n'"
        ])]
        self.f.start([new_task])
        task = self.f.dispatch("different-task")
        (self.project / "different-product.txt").write_text("ready\n")
        evidence = self.f.validate(task)
        self.assertEqual(evidence["result"], "passed")
        self.assertEqual(self.rounds_used(), 0)
        archived = read_state(self.root / "cycles" / "C0")
        self.assertEqual(archived["runtime_meta"]["repair_budget"]["history"]["milestone-1"]["rounds_used"], 1)


if __name__ == "__main__":
    unittest.main()
