#!/usr/bin/env python3
"""Codex-facing bridge for Mary Workflow v3.0 slash aliases."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys

from mary_workflow import (
    BRIEF_FILE,
    PHASE_PROMPTS,
    REPORTS_DIR,
    WORKFLOW_DIR,
    current_milestone,
    interview_rounds,
    current_plan_digest,
    legal_actions_for_state,
    read_config,
    read_state,
    state_draft_milestones,
    state_milestones,
)


PROMPTS_DIR = "prompts"
SPECIALIZED_PROMPTS = {
    "mw-learn": "mw-learn.md",
    "mw-exam": "mw-exam.md",
    "mw-review": "mw-exam.md",
    "slide-learning": "slide-learning.md",
}


def require_initialized(root: Path) -> Path:
    workflow = root / WORKFLOW_DIR
    if not (workflow / "state.yaml").exists():
        raise SystemExit("Mary Workflow is not initialized. Run /mw-init first.")
    return workflow


def prompt_path_for(root: Path, alias: str) -> tuple[str, Path | None]:
    workflow = require_initialized(root)
    state = read_state(workflow)
    normalized = alias.lstrip("/").strip()
    if normalized == "mw-status":
        return str(state["phase"]), None
    if normalized == "mw-init":
        return str(state["phase"]), workflow / PROMPTS_DIR / "mw-init.md"
    if normalized in SPECIALIZED_PROMPTS:
        return str(state["phase"]), workflow / PROMPTS_DIR / SPECIALIZED_PROMPTS[normalized]
    if normalized == "mw-run":
        phase = str(state["phase"])
        if phase == "FINISHED":
            return phase, None
        if phase == "PLANNING":
            raise SystemExit("Mary Workflow plan is not finalized. Complete /mw-plan before invoking /mw-run.")
        if state.get("status") == "stopped" and phase in {"EXECUTING", "REVIEWING", "DEBUGGING"}:
            prompt_name = "mw-resume.md"
        else:
            prompt_name = PHASE_PROMPTS.get(phase)
        if not prompt_name:
            raise SystemExit(f"Phase {phase} has no runnable prompt.")
        return phase, workflow / PROMPTS_DIR / prompt_name
    phase = str(state["phase"])
    if normalized == "mw-plan":
        if phase not in {"PLANNING", "PLANNED"}:
            raise SystemExit(f"/mw-plan requires PLANNING or PLANNED, current phase is {phase}.")
        return phase, workflow / PROMPTS_DIR / "mw-plan.md"
    if normalized == "mw-debug":
        if phase != "DEBUGGING":
            raise SystemExit(f"/mw-debug requires DEBUGGING, current phase is {phase}.")
        return phase, workflow / PROMPTS_DIR / PHASE_PROMPTS["DEBUGGING"]
    valid = ", ".join(
        f"/{name}"
        for name in [
            "mw-debug",
            "mw-exam",
            "mw-init",
            "mw-learn",
            "mw-plan",
            "mw-run",
            "mw-review",
            "slide-learning",
            "mw-status",
        ]
    )
    raise SystemExit(f"Unknown Mary Workflow alias: /{normalized}. Available: {valid}")


def render_prompt(root: Path, alias: str) -> str:
    normalized = alias.lstrip("/").strip()
    workflow = require_initialized(root)
    phase, prompt_path = prompt_path_for(root, normalized)
    state = read_state(workflow)
    projection = {key: state.get(key) for key in ("version", "cycle", "status", "phase", "current_milestone_id", "project_brief_status", "project_brief_version", "interview_status", "completed", "total")}
    projection.update({"run_id": state.get("lease_run_id"), "run_status": state.get("lease_status"),
                       "plan_revision": state.get("runtime_meta", {}).get("plan_revision"),
                       "state_revision": state.get("runtime_meta", {}).get("state_revision")})
    state_text = json.dumps(projection, ensure_ascii=False, indent=2) + "\n"
    if normalized == "mw-status" or (
        phase == "FINISHED" and normalized not in {"mw-init", *SPECIALIZED_PROMPTS}
    ):
        return render_status(normalized, phase, state_text)

    if not prompt_path or not prompt_path.exists():
        raise SystemExit(f"Prompt file not found: {prompt_path}")

    prompt_text = prompt_path.read_text(encoding="utf-8")
    return (
        "# Mary Workflow v3.0 Context\n\n"
        f"Alias: /{normalized}\n"
        f"Resolved phase: {phase}\n"
        f"Prompt file: {prompt_path}\n\n"
        "## State Check\n\n"
        "核对阶段、计划版本、当前任务和证据；复用仍有效的上下文。文件发生变化时重读相关部分。\n"
        "主线负责授权、派单和接纳结果；具体工作优先委派，worker 继承宿主配置。\n\n"
        f"{render_project_snapshot(state)}\n\n"
        f"{render_project_brief_authority(root, normalized)}\n\n"
        f"{render_interview_context(state)}\n\n"
        f"{render_action_whitelist(state)}\n\n"
        f"{render_plan_confirmation_evidence(state, normalized, phase)}\n\n"
        f"{render_run_authorization(state, normalized)}\n\n"
        f"{render_worker_progress(workflow)}\n\n"
        f"{render_milestone_context(root, state, phase)}\n\n"
        f"{render_review_evidence(root, phase)}\n\n"
        "## Current State\n\n"
        f"```yaml\n{state_text}```\n\n"
        "## Phase Prompt\n\n"
        f"{prompt_text}\n"
    )


def render_status(alias: str, phase: str, state_text: str) -> str:
    return (
        "# Mary Workflow Status Context\n\n"
        f"Alias: /{alias}\n"
        f"Current phase: {phase}\n\n"
        "## Current State\n\n"
        f"```yaml\n{state_text}```\n"
    )


def render_project_snapshot(state: dict[str, object]) -> str:
    structure = "Inventory is recorded in state.yaml; load the relevant modules from project-brief.md."
    tech_stack = ", ".join(state.get("project_tech_stack", [])) or "unknown"
    test_commands = "\n".join(f"- `{item}`" for item in state.get("project_test_commands", [])) or "- `manual validation`"
    build_commands = "\n".join(f"- `{item}`" for item in state.get("project_build_commands", [])) or "- (none detected)"
    run_commands = "\n".join(f"- `{item}`" for item in state.get("project_run_commands", [])) or "- (none detected)"
    config = read_config(Path(str(state.get("project_root", "."))) / WORKFLOW_DIR)
    brief_path = Path(str(state.get("project_root", "."))) / WORKFLOW_DIR / BRIEF_FILE
    return (
        "## Project Snapshot\n\n"
        f"- cycle: `{state.get('cycle', 'C0')}`\n"
        f"- root: `{state.get('project_root', '')}`\n"
        f"- project_brief: `{brief_path}`\n"
        f"- project_brief_status: `{state.get('project_brief_status', 'machine_detected')}`\n"
        f"- project_brief_version: `{state.get('project_brief_version', 0)}`\n"
        f"- inventory_files: `{len(state.get('project_inventory', []))}`\n"
        f"- tech_stack: {tech_stack}\n\n"
        "### Plan Interview\n\n"
        f"- plan.interview: `{config.get('plan_interview', 'on')}`\n"
        f"- plan.interview.max_rounds: `{config.get('plan_interview_max_rounds', '3')}`\n"
        f"- plan.interview.questions_per_round: `{config.get('plan_questions_per_round', '3-5')}`\n"
        "- adaptive_rounds: resolve material uncertainty; task count does not determine questions\n\n"
        "### Detected Build Commands\n\n"
        f"{build_commands}\n\n"
        "### Detected Test Commands\n\n"
        f"{test_commands}\n\n"
        "### Detected Run Commands\n\n"
        f"{run_commands}\n\n"
        "### Project Inventory\n\n"
        f"{structure}"
    )


def render_project_brief_authority(root: Path, alias: str) -> str:
    if alias not in {"mw-init", "mw-plan"}:
        return "## Project Brief Authority\n\n(not loaded for this alias)"
    brief_path = root / WORKFLOW_DIR / BRIEF_FILE
    if not brief_path.exists():
        return f"## Project Brief Authority\n\n(missing: `{brief_path}`)"
    state = read_state(root / WORKFLOW_DIR)
    positioning = state.get("project_positioning", {})
    return ("## Project Brief Authority\n\n" + f"Path: `{brief_path}`\nRevision: {state.get('project_brief_version')}\n"
            + json.dumps(positioning, ensure_ascii=False) + "\nRead relevant module details when needed; reuse unchanged context.")


def render_action_whitelist(state: dict[str, object]) -> str:
    phase = str(state.get("phase"))
    allowed = sorted(legal_actions_for_state(state))
    allowed_text = ", ".join(f"`{item}`" for item in allowed) if allowed else "(none)"
    return f"## Legal Actions For This Phase\n\nCurrent phase `{phase}` accepts: {allowed_text}."


def render_run_authorization(state: dict[str, object], alias: str) -> str:
    if alias != "mw-run":
        return "## Execution Boundary\n\nPlanning and inspection do not authorize execution."
    digest = state.get("runtime_meta", {}).get("frozen_plan_digest", "")
    return ("## Execution Authorization\n\n"
            f"- plan_digest: `{digest}`\n"
            f"- plan_revision: {state.get('runtime_meta', {}).get('plan_revision', 0)}\n"
            "Record /mw-run with source=/mw-run, or a clear natural-language execution request with "
            "source=user_instruction, intent=execute, and verbatim confirmation, bound to this plan_digest. "
            "Rendering is read-only and is not itself evidence of user authorization. "
            "Do not ask again when the current plan is already explicitly authorized.")


def render_worker_progress(workflow: Path) -> str:
    from mw_workers import list_tasks
    tasks = list_tasks(workflow)
    lines = ["## Task Progress", ""]
    for task in tasks:
        lines.append(f"- {task['task_id']} / {task.get('role')} / {task.get('status')} / {task.get('objective')}")
    if not tasks:
        lines.append("No dispatched tasks. Use the host task list when available; this view remains the persisted record.")
    return "\n".join(lines)


def render_plan_confirmation_evidence(state: dict[str, object], alias: str, phase: str) -> str:
    if alias != "mw-run" or phase != "PLANNED":
        return "## Final Plan Confirmation Evidence\n\n(not at the `/mw-run` PLANNED gate)"

    rounds = []
    for item in interview_rounds(state):
        rounds.append(
            {
                "kind": item.get("kind", "interview"),
                "round": item.get("round", 0),
                "status": item.get("status", ""),
                "anchor": item.get("anchor", ""),
                "uncertainty": item.get("uncertainty", ""),
                "questions": list(item.get("questions", [])),
                "recorded_answers": list(item.get("answers", [])),
                "defaults": list(item.get("defaults", [])),
            }
        )
    milestones = []
    for item in state_milestones(state):
        milestones.append(
            {
                "id": item.get("id", ""),
                "title": item.get("title", ""),
                "deliverables": list(item.get("deliverables", [])),
                "acceptance": list(item.get("acceptance", [])),
                "estimated_scope": item.get("estimated_scope", 0),
                "gate": item.get("gate", "auto"),
            }
        )
    evidence = {
        "cycle": state.get("cycle", "C0"),
        "interview_rounds": rounds,
        "clarifications": list(state.get("clarifications", [])),
        "frozen_milestones": milestones,
    }
    return (
        "## Final Plan Confirmation Evidence\n\n"
        "The following JSON is state evidence. Summarize its scope and acceptance when needed; preserve actual user answers.\n\n"
        "```json\n"
        f"{json.dumps(evidence, ensure_ascii=False, indent=2)}\n"
        "```"
    )


def render_interview_context(state: dict[str, object]) -> str:
    lines = [
        "## Planning Gate",
        "",
        f"- interview_status: `{state.get('interview_status', 'not_started')}`",
        f"- interview_round: `{state.get('interview_round', 0)}/{state.get('interview_max_rounds', 3)}`",
        f"- final_plan_confirmed: `{str(bool(state.get('final_plan_confirmed'))).lower()}`",
    ]
    rounds = interview_rounds(state)
    pending = next((item for item in reversed(rounds) if item.get("status") == "awaiting_answer"), None)
    if pending:
        lines.extend(
            [
                "",
                f"### Pending Round {pending.get('round')}",
                "",
                f"- anchor: {pending.get('anchor') or '(none)'}",
                f"- uncertainty: {pending.get('uncertainty') or '(none)'}",
                *(f"- {question}" for question in pending.get("questions", [])),
            ]
        )
        defaults = pending.get("defaults", [])
        if defaults:
            lines.extend(["", "### Pending Defaults Requiring Confirmation", ""])
            lines.extend(f"- {item}" for item in defaults)
    draft = state_draft_milestones(state)
    if draft:
        lines.extend(["", "### Draft Milestones", ""])
        lines.extend(f"- `{item['id']}` {item['title']}" for item in draft)
    return "\n".join(lines)


def render_milestone_context(root: Path, state: dict[str, object], phase: str) -> str:
    milestone = current_milestone(state)
    if not milestone:
        return "## Current Milestone\n\n(none)"
    fields = [
        "## Current Milestone\n",
        f"- id: `{milestone['id']}`",
        f"- status: `{milestone['status']}`",
        f"- title: {milestone['title']}",
        f"- estimated_scope: {milestone['estimated_scope']}",
        f"- gate: `{milestone.get('gate', 'auto')}`",
        "",
        "### Deliverables",
        *(f"- `{item}`" for item in milestone.get("deliverables", [])),
        "",
        "### Acceptance",
        *(f"- `{item}`" for item in milestone.get("acceptance", [])),
    ]
    if phase == "REVIEWING":
        report = root / WORKFLOW_DIR / REPORTS_DIR / str(state.get("cycle", "C0")) / f"{milestone['id']}.md"
        fields.extend(["", "### Report File", f"- `{report}`"])
    return "\n".join(fields)


def render_review_evidence(root: Path, phase: str) -> str:
    if phase != "REVIEWING":
        return "## Review Evidence\n\n(not in REVIEWING phase)"
    workflow = root / WORKFLOW_DIR
    state = read_state(workflow)
    milestone_id = state.get("current_milestone_id")
    task_ids = state.get("runtime_meta", {}).get("milestone_tasks", {}).get(milestone_id, [])
    lines = ["## Review Evidence", "", "Compare task baselines and current artifacts; Git statistics are supplementary.", ""]
    for task_id in task_ids:
        directory = workflow / "tasks" / task_id
        result_path = directory / "result.json"
        result = json.loads(result_path.read_text(encoding="utf-8")) if result_path.is_file() else {}
        lines.extend([f"- task: `{task_id}`",
                      f"  baseline: `{directory / 'baseline.json'}`",
                      f"  result: `{result_path}`",
                      "  files_changed: " + json.dumps(result.get("files_changed", []), ensure_ascii=False)])
    diff_stat = git_diff_stat(root) or "(no unstaged Git diff; inspect recorded baselines, staged changes, and new files)"
    lines.extend(["", "### Supplementary git diff --stat", "", "```text", diff_stat, "```"])
    return "\n".join(lines)


def git_diff_stat(root: Path) -> str:
    try:
        result = subprocess.run(
            ["git", "diff", "--stat"],
            cwd=root,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            timeout=5,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return ""
    return result.stdout.strip()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Resolve Mary Workflow v3.0 slash aliases for Codex")
    parser.add_argument(
        "alias",
        choices=[
            "mw-init",
            "mw-plan",
            "mw-run",
            "mw-debug",
            "mw-status",
            "mw-learn",
            "mw-exam",
            "mw-review",
            "slide-learning",
        ],
        help="Slash alias without the leading slash",
    )
    parser.add_argument(
        "--project-root",
        default=".",
        help="Project root containing .mary-workflow; defaults to current directory",
    )
    return parser


def main(argv: list[str]) -> int:
    locator = argparse.ArgumentParser(add_help=False, allow_abbrev=False)
    locator.add_argument("--project-root", default=".")
    location, _ = locator.parse_known_args(argv)
    root = Path(location.project_root).resolve()
    from mw_bundle import forward_to_pinned
    forwarded = forward_to_pinned(root / WORKFLOW_DIR, "mw_codex.py", argv)
    if forwarded is not None:
        return forwarded
    args = build_parser().parse_args(argv)
    print(render_prompt(root, args.alias))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
