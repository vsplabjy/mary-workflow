from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from mary_workflow import (  # noqa: E402
    apply_action,
    default_state,
    fingerprint_records,
    legal_actions_for_state,
    milestone_plan_signature,
    read_config,
    read_state,
    remove_tree,
    seed_core_prompts,
    sync_prompt_for_phase,
    update_config,
    write_config,
    write_state,
)
from mw_codex import prompt_path_for, render_prompt  # noqa: E402


def milestone(index: int = 1) -> dict[str, object]:
    return {
        "id": f"milestone-{index}",
        "title": f"Milestone {index}",
        "deliverables": [f"src/module_{index}.py"],
        "acceptance": [f"python -m pytest tests/test_{index}.py"],
        "estimated_scope": 1,
        "gate": "auto",
    }


def brief_payload(
    inventory: list[str], mode: str = "initial", changed_files: list[str] | None = None
) -> dict[str, object]:
    primary = inventory[0]
    return {
        "action": "submit_brief",
        "data": {
            "mode": mode,
            "positioning": {
                "purpose": "Exercise Mary Workflow boundaries.",
                "audience": "Workflow developers.",
                "problem": "Provide deterministic test fixtures.",
                "differentiators": "Uses a complete machine-validated brief.",
            },
            "architecture": {
                "modules": [
                    {
                        "name": "fixture",
                        "responsibility": "Represent the complete test project.",
                        "files": list(inventory),
                    }
                ],
                "dependency_graph": ["fixture -> workflow tests: supplies state"],
                "data_flow": ["Test input enters the fixture and is asserted by unittest."],
                "state_management": ["state.yaml -> apply_action: serialized workflow state"],
            },
            "file_ledger": [
                {
                    "path": path,
                    "purpose": f"Fixture file {path}.",
                    "exports": ["(none discovered)"],
                    "used_by": ["workflow boundary tests"],
                }
                for path in inventory
            ],
            "uncertainties": [
                {
                    "topic": "Fixture generality",
                    "status": "inferred",
                    "detail": "The fixture models protocol behavior rather than a production stack.",
                }
            ],
            "validation": [
                {
                    "kind": kind,
                    "command": f"skipped:no {kind} command in fixture",
                    "status": "skipped",
                    "summary": f"No safe {kind} command exists for the empty fixture.",
                    "duration": "0s",
                }
                for kind in ("build", "test", "run")
            ],
            "analysis_evidence": {
                "pass1_inventory_complete": True,
                "pass2": {
                    "entrypoints": [primary],
                    "configuration": [primary],
                    "core_modules": [primary],
                    "tests": [primary],
                },
                "pass3": {
                    "synthesis": "The fixture is a single complete module used by protocol tests.",
                    "module_summaries": [
                        {"module": "fixture", "summary": "Complete fixture project summary."}
                    ],
                    "reread_files": [primary],
                },
                "reviewed_changed_files": list(changed_files or []),
            },
        },
    }


class WorkflowBoundaryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.project = Path(self.tempdir.name)
        self.root = self.project / ".mary-workflow"
        (self.root / "prompts").mkdir(parents=True)
        write_config(self.root)
        seed_core_prompts(self.root)
        state = default_state(self.project)
        sync_prompt_for_phase(state, self.root)
        write_state(self.root, state)
        apply_action(self.root, brief_payload(list(state["project_inventory"])))

    def tearDown(self) -> None:
        remove_tree(self.root)
        self.tempdir.cleanup()

    def assert_rejected(self, payload: dict[str, object]) -> str:
        with self.assertRaises(SystemExit) as context:
            apply_action(self.root, payload)
        return str(context.exception)

    def open_round_one(self) -> None:
        apply_action(
            self.root,
            {
                "action": "update_interview",
                "data": {
                    "mode": "open",
                    "round": 1,
                    "anchor": "initial request",
                    "uncertainty": "scope and acceptance",
                    "questions": ["Scope?", "Acceptance?", "Tests?"],
                    "defaults": [],
                },
            },
        )

    def prepare_ready_plan(self, milestones: list[dict[str, object]] | None = None) -> dict[str, object]:
        draft = milestones or [milestone()]
        self.open_round_one()
        apply_action(
            self.root,
            {
                "action": "update_interview",
                "data": {
                    "mode": "resolve",
                    "round": 1,
                    "answers": ["The user answered scope, acceptance, and test boundaries."],
                    "complete": True,
                    "draft_milestones": draft,
                },
            },
        )
        state = read_state(self.root)
        return apply_action(
            self.root,
            {
                "action": "update_state",
                "data": {
                    "phase": "PLANNED",
                    "clarifications": state["clarifications"],
                    "milestones": milestone_plan_signature(state["draft_milestones"]),
                },
            },
        )

    def render_grant(self) -> tuple[str, str]:
        rendered = render_prompt(self.project, "mw-run")
        match = re.search(r"^- token: `([^`]+)`$", rendered, flags=re.MULTILINE)
        self.assertIsNotNone(match)
        return rendered, match.group(1)

    def start_execution(self, milestones: list[dict[str, object]] | None = None) -> dict[str, object]:
        self.prepare_ready_plan(milestones)
        _, token = self.render_grant()
        return apply_action(self.root, {"action": "start_execution", "data": {"token": token}})

    def run_cli(self, *arguments: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(REPO_ROOT / "scripts/mary_workflow.py"), *arguments],
            cwd=self.project,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True,
        )

    def test_update_state_cannot_skip_interview(self) -> None:
        message = self.assert_rejected(
            {
                "action": "update_state",
                "data": {
                    "phase": "PLANNED",
                    "clarifications": ["fabricated"],
                    "milestones": [milestone()],
                },
            }
        )
        self.assertIn("completed interview", message)
        self.assertEqual(read_state(self.root)["phase"], "PLANNING")

    def test_incomplete_brief_blocks_planning_and_incomplete_ledger_is_rejected(self) -> None:
        state = read_state(self.root)
        state["project_brief_status"] = "machine_detected"
        write_state(self.root, state)

        message = self.assert_rejected(
            {
                "action": "update_interview",
                "data": {
                    "mode": "open",
                    "round": 1,
                    "anchor": "request",
                    "uncertainty": "scope",
                    "questions": ["Q1?", "Q2?", "Q3?"],
                    "defaults": [],
                },
            }
        )
        self.assertIn("Legal actions: submit_brief, update_project", message)

        payload = brief_payload(list(state["project_inventory"]))
        payload["data"]["file_ledger"] = []
        message = self.assert_rejected(payload)
        self.assertIn("file_ledger must be a non-empty list", message)
        self.assertEqual(read_state(self.root)["project_brief_status"], "machine_detected")

    def test_complete_brief_has_five_layers_and_is_loaded_by_plan(self) -> None:
        brief = (self.root / "project-brief.md").read_text(encoding="utf-8")
        for heading in (
            "## 1. 机器探测区",
            "## 2. 项目定位",
            "## 3. 架构全景",
            "## 4. 文件级账本",
            "## 5. 不确定性清单",
        ):
            self.assertIn(heading, brief)
        self.assertIn("构建、测试与运行复现", brief)
        self.assertIn("`(empty repository)`", brief)

        rendered = render_prompt(self.project, "mw-plan")
        self.assertIn("## Project Brief Authority", rendered)
        self.assertIn("## 4. 文件级账本", rendered)
        self.assertIn("Fixture file (empty repository).", rendered)

    def test_agent_cannot_declare_plan_confirmation(self) -> None:
        self.open_round_one()
        apply_action(
            self.root,
            {
                "action": "update_interview",
                "data": {
                    "mode": "resolve",
                    "round": 1,
                    "answers": ["Answered."],
                    "complete": True,
                    "draft_milestones": [milestone()],
                },
            },
        )
        state = read_state(self.root)
        message = self.assert_rejected(
            {
                "action": "update_state",
                "data": {
                    "phase": "PLANNED",
                    "confirmed": True,
                    "confirmation": "Agent claims the user confirmed.",
                    "clarifications": state["clarifications"],
                    "milestones": milestone_plan_signature(state["draft_milestones"]),
                },
            }
        )
        self.assertIn("must not declare plan confirmation", message)
        self.assertEqual(read_state(self.root)["phase"], "PLANNING")

    def test_frozen_plan_waits_unconfirmed_without_a_lease(self) -> None:
        state = self.prepare_ready_plan()
        self.assertEqual(state["phase"], "PLANNED")
        self.assertEqual(state["status"], "ready")
        self.assertEqual(state["interview_status"], "plan_ready")
        self.assertFalse(state["final_plan_confirmed"])
        self.assertEqual(state["lease_status"], "none")
        self.assertEqual(state["started_at"], "")

        message = self.assert_rejected({"action": "mark_task_done", "data": {"id": "milestone-1"}})
        self.assertIn("Legal actions: reopen_plan, start_execution", message)

        phase, prompt = prompt_path_for(self.project, "mw-run")
        self.assertEqual(phase, "PLANNED")
        self.assertEqual(prompt.name, "mw-ready.md")
        self.assertEqual(read_state(self.root)["run_grant_digest"], "")

    def test_start_grant_is_private_and_start_is_atomic(self) -> None:
        self.prepare_ready_plan()
        rendered, token = self.render_grant()
        issued = read_state(self.root)
        state_text = (self.root / "state.yaml").read_text(encoding="utf-8")

        self.assertIn(token, rendered)
        self.assertNotIn(token, state_text)
        self.assertTrue(issued["run_grant_digest"])
        self.assertEqual(issued["run_grant_purpose"], "start")
        self.assertNotIn(token, render_prompt(self.project, "mw-status"))
        self.assertNotIn(token, render_prompt(self.project, "mw-plan"))

        evidence_match = re.search(
            r"## Final Plan Confirmation Evidence.*?```json\n(.*?)\n```",
            rendered,
            flags=re.DOTALL,
        )
        self.assertIsNotNone(evidence_match)
        evidence = json.loads(evidence_match.group(1))
        self.assertEqual(evidence["interview_rounds"][0]["questions"], ["Scope?", "Acceptance?", "Tests?"])
        self.assertEqual(
            evidence["interview_rounds"][0]["recorded_answers"],
            ["The user answered scope, acceptance, and test boundaries."],
        )
        self.assertEqual(evidence["interview_rounds"][0]["defaults"], [])
        self.assertEqual(evidence["frozen_milestones"][0]["id"], "milestone-1")
        self.assertEqual(evidence["frozen_milestones"][0]["deliverables"], ["src/module_1.py"])

        state = apply_action(self.root, {"action": "start_execution", "data": {"token": token}})
        self.assertEqual(state["phase"], "EXECUTING")
        self.assertTrue(state["final_plan_confirmed"])
        self.assertEqual(state["interview_status"], "complete")
        self.assertEqual(state["lease_status"], "active")
        self.assertTrue(state["lease_run_id"])
        self.assertTrue(state["started_at"])
        self.assertEqual(state["run_grant_digest"], "")

    def test_forged_rotated_and_replayed_grants_are_rejected(self) -> None:
        self.prepare_ready_plan()
        message = self.assert_rejected({"action": "start_execution", "data": {"token": "forged"}})
        self.assertIn("missing, invalid, or already consumed", message)

        _, first_token = self.render_grant()
        _, second_token = self.render_grant()
        self.assertNotEqual(first_token, second_token)
        message = self.assert_rejected({"action": "start_execution", "data": {"token": first_token}})
        self.assertIn("missing, invalid, or already consumed", message)

        apply_action(self.root, {"action": "start_execution", "data": {"token": second_token}})
        message = self.assert_rejected({"action": "start_execution", "data": {"token": second_token}})
        self.assertIn("Illegal action for phase EXECUTING", message)

    def test_reopen_plan_invalidates_grant_and_allows_revision(self) -> None:
        self.prepare_ready_plan()
        _, stale_token = self.render_grant()
        state = apply_action(
            self.root,
            {"action": "reopen_plan", "data": {"feedback": ["Rename the milestone."]}},
        )
        self.assertEqual(state["phase"], "PLANNING")
        self.assertEqual(state["interview_status"], "draft_ready")
        self.assertEqual(state["run_grant_digest"], "")

        revised = {**milestone(), "title": "Revised milestone"}
        apply_action(
            self.root,
            {
                "action": "update_interview",
                "data": {
                    "mode": "revise",
                    "feedback": ["Rename the milestone."],
                    "draft_milestones": [revised],
                },
            },
        )
        state = read_state(self.root)
        state = apply_action(
            self.root,
            {
                "action": "update_state",
                "data": {
                    "phase": "PLANNED",
                    "clarifications": state["clarifications"],
                    "milestones": milestone_plan_signature(state["draft_milestones"]),
                },
            },
        )
        self.assertEqual(state["milestones"][0]["title"], "Revised milestone")
        message = self.assert_rejected({"action": "start_execution", "data": {"token": stale_token}})
        self.assertIn("missing, invalid, or already consumed", message)

    def test_stop_and_resume_preserve_the_run_lease(self) -> None:
        state = self.start_execution()
        run_id = state["lease_run_id"]
        self.run_cli("stop")
        stopped = read_state(self.root)
        self.assertEqual(stopped["status"], "stopped")
        self.assertEqual(stopped["lease_status"], "paused")
        self.assertEqual(stopped["lease_run_id"], run_id)

        message = self.assert_rejected({"action": "mark_task_done", "data": {"id": "milestone-1"}})
        self.assertIn("Legal actions: resume_execution", message)
        phase, prompt = prompt_path_for(self.project, "mw-run")
        self.assertEqual(phase, "EXECUTING")
        self.assertEqual(prompt.name, "mw-resume.md")

        _, token = self.render_grant()
        resumed = apply_action(self.root, {"action": "resume_execution", "data": {"token": token}})
        self.assertEqual(resumed["phase"], "EXECUTING")
        self.assertEqual(resumed["status"], "running")
        self.assertEqual(resumed["lease_status"], "active")
        self.assertEqual(resumed["lease_run_id"], run_id)

    def test_debug_and_review_keep_one_active_run_lease(self) -> None:
        state = self.start_execution([milestone(1), milestone(2)])
        run_id = state["lease_run_id"]
        original_plan_digest = state["lease_plan_digest"]
        state = apply_action(
            self.root,
            {"action": "record_error", "data": {"command": "pytest", "stderr": "failed", "returncode": "1"}},
        )
        self.assertEqual(state["phase"], "DEBUGGING")
        self.assertEqual(state["lease_run_id"], run_id)
        self.assertEqual(state["lease_status"], "active")

        state = apply_action(
            self.root,
            {"action": "enqueue_fix_task", "data": {"title": "Fix failure", "estimated_scope": 1}},
        )
        fix_id = state["current_milestone_id"]
        self.assertEqual(state["phase"], "EXECUTING")
        self.assertEqual(state["lease_run_id"], run_id)
        self.assertNotEqual(state["lease_plan_digest"], original_plan_digest)

        state = apply_action(self.root, {"action": "mark_task_done", "data": {"id": fix_id}})
        self.assertEqual(state["phase"], "REVIEWING")
        self.assertEqual(state["lease_run_id"], run_id)
        state = apply_action(
            self.root,
            {"action": "set_phase", "data": {"phase": "EXECUTING", "decision": "accepted-next"}},
        )
        self.assertEqual(state["phase"], "EXECUTING")
        self.assertEqual(state["lease_run_id"], run_id)
        self.assertEqual(state["current_milestone_id"], "milestone-1")

    def test_finished_and_replanning_release_the_lease(self) -> None:
        self.start_execution()
        apply_action(self.root, {"action": "mark_task_done", "data": {"id": "milestone-1"}})
        state = apply_action(
            self.root,
            {"action": "set_phase", "data": {"phase": "FINISHED", "decision": "accepted"}},
        )
        self.assertEqual(state["phase"], "FINISHED")
        self.assertEqual(state["lease_status"], "released")
        self.assertIn("PLANNING -> PLANNED (envelope: update_state; plan ready)", state["phase_history"])
        self.assertIn("PLANNED -> EXECUTING (/mw-run: start_execution)", state["phase_history"])

        self.run_cli("cycle")
        state = read_state(self.root)
        self.assertEqual(state["version"], "2.1")
        self.assertEqual(state["cycle"], "C1")
        self.assertEqual(state["phase"], "PLANNING")
        self.assertEqual(state["lease_status"], "none")
        self.assertEqual(state["run_grant_digest"], "")

    def test_cycle_requires_incremental_brief_refresh_before_archive(self) -> None:
        state = read_state(self.root)
        state["phase"] = "FINISHED"
        state["status"] = "completed"
        write_state(self.root, state)
        (self.project / "app.py").write_text("def main():\n    return 1\n", encoding="utf-8")
        first = self.run_cli("cycle")
        state = read_state(self.root)
        self.assertEqual(state["cycle"], "C0")
        self.assertEqual(state["project_brief_status"], "refresh_required")
        self.assertEqual(state["project_changed_files"], ["added:app.py"])
        self.assertIn("归档已暂停", first.stdout)
        self.assertFalse((self.root / "cycles/C0").exists())
        refresh_context = render_prompt(self.project, "mw-init")
        self.assertIn("# Mary Init Understanding Phase", refresh_context)
        self.assertIn("added:app.py", refresh_context)

        state = apply_action(
            self.root,
            brief_payload(["app.py"], mode="cycle_refresh", changed_files=["added:app.py"]),
        )
        self.assertEqual(state["project_brief_status"], "complete")
        self.assertEqual(state["project_brief_version"], 2)
        self.assertEqual(state["project_file_ledger"][0]["path"], "app.py")
        (self.root / "analysis").mkdir(exist_ok=True)
        (self.root / "analysis/submit-brief.json").write_text("{}\n", encoding="utf-8")

        second = self.run_cli("cycle")
        state = read_state(self.root)
        self.assertEqual(state["cycle"], "C1")
        self.assertEqual(state["project_brief_status"], "complete")
        self.assertTrue((self.root / "cycles/C0/state.yaml").exists())
        self.assertTrue((self.root / "cycles/C0/project-brief.md").exists())
        self.assertTrue((self.root / "cycles/C0/analysis/submit-brief.json").exists())
        self.assertIn("已归档 C0", second.stdout)

    def test_submit_brief_cli_displays_the_full_document(self) -> None:
        payload = brief_payload(["(empty repository)"], mode="correction")
        result = self.run_cli("apply-action", "--json", json.dumps(payload, ensure_ascii=False))
        self.assertIn("# 项目理解简报", result.stdout)
        self.assertIn("## 1. 机器探测区", result.stdout)
        self.assertIn("## 5. 不确定性清单", result.stdout)
        self.assertIn("Fixture file (empty repository).", result.stdout)

    def test_review_can_return_to_clean_planning(self) -> None:
        self.start_execution()
        apply_action(self.root, {"action": "mark_task_done", "data": {"id": "milestone-1"}})
        state = apply_action(
            self.root,
            {"action": "set_phase", "data": {"phase": "PLANNING", "decision": "replan"}},
        )
        self.assertEqual(state["phase"], "PLANNING")
        self.assertEqual(state["lease_status"], "released")
        self.assertEqual(state["milestones"], [])
        self.assertFalse(state["final_plan_confirmed"])

    def test_large_plan_requires_two_answered_rounds(self) -> None:
        self.open_round_one()
        message = self.assert_rejected(
            {
                "action": "update_interview",
                "data": {
                    "mode": "resolve",
                    "round": 1,
                    "answers": ["One round."],
                    "complete": True,
                    "draft_milestones": [milestone(index) for index in range(1, 6)],
                },
            }
        )
        self.assertIn("at least 2 answered interview rounds", message)

        apply_action(
            self.root,
            {
                "action": "update_interview",
                "data": {
                    "mode": "resolve",
                    "round": 1,
                    "answers": ["First-round answers."],
                    "complete": False,
                    "next_round": {
                        "round": 2,
                        "anchor": "the acceptance answer",
                        "uncertainty": "five delivery boundaries",
                        "questions": ["Boundary 1?", "Boundary 2?", "Boundary 3?"],
                        "defaults": [],
                    },
                },
            },
        )
        apply_action(
            self.root,
            {
                "action": "update_interview",
                "data": {
                    "mode": "resolve",
                    "round": 2,
                    "answers": ["Second-round answers."],
                    "complete": True,
                    "draft_milestones": [milestone(index) for index in range(1, 6)],
                },
            },
        )
        self.assertEqual(read_state(self.root)["interview_status"], "draft_ready")

    def test_round_zero_requires_explicit_default_confirmation(self) -> None:
        apply_action(
            self.root,
            {
                "action": "update_interview",
                "data": {
                    "mode": "open",
                    "round": 0,
                    "questions": ["Do you accept these defaults?"],
                    "defaults": ["Use pytest and change one module."],
                },
            },
        )
        apply_action(
            self.root,
            {
                "action": "update_interview",
                "data": {
                    "mode": "resolve",
                    "round": 0,
                    "answers": ["The user accepts the defaults."],
                    "complete": True,
                    "draft_milestones": [milestone()],
                },
            },
        )
        self.assertEqual(read_state(self.root)["interview_status"], "draft_ready")

    def test_followup_round_requires_anchor_and_uncertainty(self) -> None:
        self.open_round_one()
        message = self.assert_rejected(
            {
                "action": "update_interview",
                "data": {
                    "mode": "resolve",
                    "round": 1,
                    "answers": ["First-round answers."],
                    "complete": False,
                    "next_round": {
                        "round": 2,
                        "questions": ["Q1?", "Q2?", "Q3?"],
                        "defaults": [],
                    },
                },
            }
        )
        self.assertIn("require data.anchor and data.uncertainty", message)

    def test_interview_off_assumptions_still_wait_for_confirmation(self) -> None:
        update_config(self.root, plan_interview="off")
        message = self.assert_rejected(
            {
                "action": "update_interview",
                "data": {
                    "mode": "propose",
                    "clarifications": ["Use pytest."],
                    "draft_milestones": [milestone()],
                },
            }
        )
        self.assertIn("exactly one explicit confirmation question", message)

        apply_action(
            self.root,
            {
                "action": "update_interview",
                "data": {
                    "mode": "propose",
                    "clarifications": ["Use pytest.", "Change only one module."],
                    "questions": ["Do you explicitly accept every listed assumption?"],
                    "draft_milestones": [milestone()],
                },
            },
        )
        state = read_state(self.root)
        self.assertEqual(state["interview_status"], "awaiting_answers")
        self.assertEqual(state["interview_rounds"][0]["status"], "awaiting_answer")
        rendered = render_prompt(self.project, "mw-plan")
        self.assertIn("Pending Defaults Requiring Confirmation", rendered)
        self.assertIn("Use pytest.", rendered)
        self.assertIn("Change only one module.", rendered)
        message = self.assert_rejected(
            {
                "action": "update_state",
                "data": {
                    "phase": "PLANNED",
                    "clarifications": state["clarifications"],
                    "milestones": milestone_plan_signature(state["draft_milestones"]),
                },
            }
        )
        self.assertIn("draft plan ready to freeze", message)

        apply_action(
            self.root,
            {
                "action": "update_interview",
                "data": {
                    "mode": "resolve",
                    "round": 0,
                    "answers": ["The user explicitly accepts both assumptions."],
                    "complete": True,
                    "draft_milestones": [milestone()],
                },
            },
        )
        state = read_state(self.root)
        self.assertEqual(state["interview_status"], "draft_ready")
        state = apply_action(
            self.root,
            {
                "action": "update_state",
                "data": {
                    "phase": "PLANNED",
                    "clarifications": state["clarifications"],
                    "milestones": milestone_plan_signature(state["draft_milestones"]),
                },
            },
        )
        self.assertEqual(state["phase"], "PLANNED")
        rendered, _ = self.render_grant()
        evidence_match = re.search(
            r"## Final Plan Confirmation Evidence.*?```json\n(.*?)\n```",
            rendered,
            flags=re.DOTALL,
        )
        self.assertIsNotNone(evidence_match)
        evidence = json.loads(evidence_match.group(1))
        self.assertEqual(evidence["interview_rounds"][0]["defaults"], ["Use pytest.", "Change only one module."])
        self.assertEqual(
            evidence["interview_rounds"][0]["recorded_answers"],
            ["The user explicitly accepts both assumptions."],
        )

    def test_defaults_cannot_be_injected_after_the_user_answers(self) -> None:
        self.open_round_one()
        message = self.assert_rejected(
            {
                "action": "update_interview",
                "data": {
                    "mode": "resolve",
                    "round": 1,
                    "answers": ["The user's actual answer."],
                    "defaults": ["An assumption the user never saw."],
                    "complete": True,
                    "draft_milestones": [milestone()],
                },
            }
        )
        self.assertIn("cannot introduce new defaults", message)
        self.assertEqual(read_state(self.root)["interview_status"], "awaiting_answers")

    def test_plan_prompts_have_no_default_value_escape_hatch(self) -> None:
        plan_prompt = (REPO_ROOT / ".mary-workflow/prompts/mw-plan.md").read_text(encoding="utf-8")
        ready_prompt = (REPO_ROOT / ".mary-workflow/prompts/mw-ready.md").read_text(encoding="utf-8")
        plan_skill = (REPO_ROOT / "skills/plan/SKILL.md").read_text(encoding="utf-8")
        combined = "\n".join((plan_prompt, ready_prompt, plan_skill)).lower()

        self.assertIn("must show defaults and wait for explicit confirmation", combined)
        self.assertIn("do not freeze the draft in the same response", combined)
        self.assertIn("including with interview disabled", combined)
        for forbidden in (
            "if the user does not answer, proceed",
            "if there is no response, proceed",
            "assume the user accepts",
            "silence means confirmation",
            "reasonable defaults and continue",
        ):
            self.assertNotIn(forbidden, combined)

    def test_update_interview_is_prelogged_and_counted(self) -> None:
        self.open_round_one()
        state = read_state(self.root)
        self.assertEqual(state["action_counts"]["update_interview"], 1)

        apply_action(
            self.root,
            {
                "action": "update_interview",
                "data": {
                    "mode": "resolve",
                    "round": 1,
                    "answers": ["Recorded user answer."],
                    "complete": True,
                    "draft_milestones": [milestone()],
                },
            },
        )
        state = read_state(self.root)
        self.assertEqual(state["action_counts"]["update_interview"], 2)

        log_lines = (self.root / "log.md").read_text(encoding="utf-8").splitlines()
        open_action = next(i for i, line in enumerate(log_lines) if "action update_interview mode=open round=1" in line)
        open_done = next(i for i, line in enumerate(log_lines) if "updated interview mode=open" in line)
        resolve_action = next(
            i for i, line in enumerate(log_lines) if "action update_interview mode=resolve round=1" in line
        )
        resolve_done = next(i for i, line in enumerate(log_lines) if "updated interview mode=resolve" in line)
        self.assertLess(open_action, open_done)
        self.assertLess(open_done, resolve_action)
        self.assertLess(resolve_action, resolve_done)

    def test_run_refuses_planning_and_plan_prompt_has_hard_stop(self) -> None:
        with self.assertRaises(SystemExit) as context:
            prompt_path_for(self.project, "mw-run")
        self.assertIn("Complete /mw-plan", str(context.exception))

        prompt = (REPO_ROOT / ".mary-workflow/prompts/mw-plan.md").read_text(encoding="utf-8")
        self.assertIn("Do not render `/mw-run` context", prompt)
        self.assertIn("Do not emit `start_execution`", prompt)
        self.assertIn("/mw-run` confirms and starts", prompt)

    def test_earlier_and_missing_versions_are_rejected(self) -> None:
        state_path = self.root / "state.yaml"
        state_text = state_path.read_text(encoding="utf-8")
        state_path.write_text(state_text.replace("version: 2.1", "version: 2.0", 1), encoding="utf-8")
        with self.assertRaises(SystemExit) as context:
            read_state(self.root)
        self.assertIn("Earlier state contracts", str(context.exception))

        state_path.write_text("\n".join(state_text.splitlines()[1:]) + "\n", encoding="utf-8")
        with self.assertRaises(SystemExit):
            read_state(self.root)

    def test_prompt_refresh_preserves_state_file(self) -> None:
        state_before = (self.root / "state.yaml").read_bytes()
        target = self.root / "prompts/mw-plan.md"
        target.write_text("stale prompt\n", encoding="utf-8")
        refreshed = seed_core_prompts(self.root, overwrite=True)
        self.assertEqual(refreshed, 10)
        self.assertIn("Non-Negotiable Boundary", target.read_text(encoding="utf-8"))
        self.assertTrue((self.root / "prompts/mw-resume.md").exists())
        self.assertEqual((self.root / "state.yaml").read_bytes(), state_before)

    def test_existing_state_read_does_not_scan_the_project(self) -> None:
        with mock.patch("mary_workflow.detect_project", side_effect=AssertionError("unexpected scan")):
            state = read_state(self.root)
        self.assertEqual(state["project_brief_status"], "complete")

    def test_fingerprints_stream_files_without_read_bytes(self) -> None:
        source = self.project / "streamed.txt"
        source.write_bytes((b"mary-workflow\n" * 100_000) + b"end")
        expected = hashlib.sha256(source.read_bytes()).hexdigest()
        with mock.patch.object(Path, "read_bytes", side_effect=AssertionError("whole-file read")):
            records = fingerprint_records(self.project, [source])
        self.assertEqual(records, [{"path": "streamed.txt", "sha256": expected}])

    def test_init_ignore_can_be_explicitly_empty(self) -> None:
        project = self.project / "no-default-ignore"
        root = project / ".mary-workflow"
        root.mkdir(parents=True)
        (root / "config.yaml").write_text("init:\n  ignore: []\n", encoding="utf-8")
        (project / "output").mkdir()
        (project / "output/source.csv").write_text("kept\n", encoding="utf-8")
        state = default_state(project)
        self.assertEqual(read_config(root)["init_ignore"], [])
        self.assertIn("output/source.csv", state["project_inventory"])

    def test_init_during_execution_skips_drift_and_preserves_execution(self) -> None:
        self.start_execution()
        (self.project / "runtime-change.txt").write_text("in progress\n", encoding="utf-8")
        result = self.run_cli("init")
        state = read_state(self.root)
        self.assertEqual(state["phase"], "EXECUTING")
        self.assertEqual(state["project_brief_status"], "complete")
        self.assertIn("运行中，跳过简报漂移检查", result.stdout)

        state["project_brief_status"] = "refresh_required"
        state["project_changed_files"] = ["added:runtime-change.txt"]
        write_state(self.root, state)
        self.assertEqual(legal_actions_for_state(state), {"mark_task_done", "record_error"})
        completed = apply_action(self.root, {"action": "mark_task_done", "data": {"id": "milestone-1"}})
        self.assertEqual(completed["phase"], "REVIEWING")

    def test_fresh_init_cli_creates_v21_workspace(self) -> None:
        fresh = self.project / "fresh"
        fresh.mkdir()
        for index in range(105):
            (fresh / f"file_{index:03d}.txt").write_text(f"file {index}\n", encoding="utf-8")
        (fresh / "image.bin").write_bytes(b"\x00\x01binary")
        (fresh / "node_modules").mkdir()
        (fresh / "node_modules/ignored.js").write_text("ignored\n", encoding="utf-8")
        (fresh / "output").mkdir()
        (fresh / "output/metrics.csv").write_text("loss\n0.1\n", encoding="utf-8")
        (fresh / "model.ckpt").write_bytes(b"checkpoint")
        (fresh / "scratch").mkdir()
        (fresh / "scratch/debug.json").write_text("{}\n", encoding="utf-8")
        (fresh / ".maryignore").write_text("scratch/**\n", encoding="utf-8")
        result = subprocess.run(
            [sys.executable, str(REPO_ROOT / "scripts/mary_workflow.py"), "init"],
            cwd=fresh,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True,
        )
        workflow = fresh / ".mary-workflow"
        state = read_state(workflow)
        self.assertEqual(state["version"], "2.1")
        self.assertEqual(state["phase"], "PLANNING")
        self.assertEqual(state["project_brief_status"], "machine_detected")
        self.assertEqual(len(state["project_inventory"]), 106)
        self.assertIn("file_104.txt", state["project_inventory"])
        self.assertIn(".maryignore", state["project_inventory"])
        self.assertNotIn("image.bin", state["project_inventory"])
        self.assertNotIn("model.ckpt", state["project_inventory"])
        self.assertNotIn("node_modules/ignored.js", state["project_inventory"])
        self.assertNotIn("output/metrics.csv", state["project_inventory"])
        self.assertNotIn("scratch/debug.json", state["project_inventory"])
        config = read_config(workflow)
        self.assertIn("output/**", config["init_ignore"])
        self.assertEqual(len(list((workflow / "prompts").glob("*.md"))), 10)
        self.assertTrue((workflow / "analysis").is_dir())
        self.assertIn("继续 /mw-init 理解流程", result.stdout)
        init_context = render_prompt(fresh, "mw-init")
        self.assertIn("# Mary Init Understanding Phase", init_context)
        self.assertIn("file_104.txt", init_context)

    def test_course_profiles_render_as_shared_mary_context(self) -> None:
        for alias, prompt_name, marker in (
            ("mw-learn", "mw-learn.md", "Course Learning Profile"),
            ("mw-exam", "mw-exam.md", "ExamPass Profile"),
            ("mw-review", "mw-exam.md", "ExamPass Profile"),
            ("mw-slide", "mw-slide.md", "Slide Profile"),
        ):
            phase, prompt = prompt_path_for(self.project, alias)
            self.assertEqual(phase, "PLANNING")
            self.assertEqual(prompt.name, prompt_name)
            rendered = render_prompt(self.project, alias)
            self.assertIn(f"Alias: /{alias}", rendered)
            self.assertIn(marker, rendered)
            self.assertIn("Mary Workflow v2.1 Context", rendered)

    def test_course_profiles_remain_available_after_finished_cycle(self) -> None:
        self.start_execution()
        apply_action(self.root, {"action": "mark_task_done", "data": {"id": "milestone-1"}})
        apply_action(
            self.root,
            {"action": "set_phase", "data": {"phase": "FINISHED", "decision": "accepted"}},
        )
        rendered = render_prompt(self.project, "mw-exam")
        self.assertIn("Resolved phase: FINISHED", rendered)
        self.assertIn("ExamPass Profile", rendered)


if __name__ == "__main__":
    unittest.main()
