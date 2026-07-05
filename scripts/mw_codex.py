#!/usr/bin/env python3
"""Codex-facing bridge for Mary Workflow v2 slash aliases."""

from __future__ import annotations

import argparse
from pathlib import Path
import subprocess
import sys

from mary_workflow import PHASE_ACTIONS, PHASE_PROMPTS, WORKFLOW_DIR, current_milestone, read_state


PROMPTS_DIR = "prompts"
ALIAS_TO_PHASE = {
    "mw-plan": "PLANNING",
    "mw-debug": "DEBUGGING",
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
    if normalized == "mw-run":
        phase = str(state["phase"])
        if phase == "FINISHED":
            return phase, None
        if phase == "PLANNING":
            return phase, workflow / PROMPTS_DIR / PHASE_PROMPTS["PLANNING"]
        prompt_name = PHASE_PROMPTS.get(phase)
        if not prompt_name:
            raise SystemExit(f"Phase {phase} has no runnable prompt.")
        return phase, workflow / PROMPTS_DIR / prompt_name
    phase = ALIAS_TO_PHASE.get(normalized)
    if not phase:
        valid = ", ".join(f"/{name}" for name in ["mw-debug", "mw-plan", "mw-run", "mw-status"])
        raise SystemExit(f"Unknown Mary Workflow alias: /{normalized}. Available: {valid}")
    prompt_name = PHASE_PROMPTS.get(phase)
    if not prompt_name:
        raise SystemExit(f"Phase {phase} has no prompt alias.")
    return phase, workflow / PROMPTS_DIR / prompt_name


def render_prompt(root: Path, alias: str) -> str:
    normalized = alias.lstrip("/").strip()
    workflow = require_initialized(root)
    state = read_state(workflow)
    phase, prompt_path = prompt_path_for(root, normalized)
    state_text = (workflow / "state.yaml").read_text(encoding="utf-8")
    if normalized == "mw-status" or phase == "FINISHED":
        return render_status(normalized, phase, state_text)

    if not prompt_path or not prompt_path.exists():
        raise SystemExit(f"Prompt file not found: {prompt_path}")

    prompt_text = prompt_path.read_text(encoding="utf-8")
    return (
        "# Mary Workflow v2 Context\n\n"
        f"Alias: /{normalized}\n"
        f"Resolved phase: {phase}\n"
        f"Prompt file: {prompt_path}\n\n"
        "## Boundary Ritual\n\n"
        "1. 重新读取 `.mary-workflow/state.yaml`。\n"
        "2. 声明丢弃之前工作记忆，只信任本次渲染的文件系统上下文。\n"
        "3. 只查看当前 milestone 的 `deliverables` 相关文件，review 阶段只看 diff、验收输出和 deliverables。\n\n"
        f"{render_project_snapshot(state)}\n\n"
        f"{render_action_whitelist(phase)}\n\n"
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
    structure = "\n".join(f"- {item}" for item in state.get("project_structure", [])) or "- (empty)"
    tech_stack = ", ".join(state.get("project_tech_stack", [])) or "unknown"
    test_commands = "\n".join(f"- `{item}`" for item in state.get("project_test_commands", [])) or "- `manual validation`"
    return (
        "## Project Snapshot\n\n"
        f"- root: `{state.get('project_root', '')}`\n"
        f"- tech_stack: {tech_stack}\n\n"
        "### Known Test Commands\n\n"
        f"{test_commands}\n\n"
        "### Structure Sample\n\n"
        f"{structure}"
    )


def render_action_whitelist(phase: str) -> str:
    allowed = sorted(PHASE_ACTIONS.get(phase, set()))
    allowed_text = ", ".join(f"`{item}`" for item in allowed) if allowed else "(none)"
    return f"## Legal Actions For This Phase\n\nCurrent phase `{phase}` accepts: {allowed_text}."


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
        report = root / WORKFLOW_DIR / "reports" / f"{milestone['id']}.md"
        fields.extend(["", "### Report File", f"- `{report}`"])
    return "\n".join(fields)


def render_review_evidence(root: Path, phase: str) -> str:
    if phase != "REVIEWING":
        return "## Review Evidence\n\n(not in REVIEWING phase)"
    diff_stat = git_diff_stat(root)
    if not diff_stat:
        diff_stat = "(no git diff --stat output)"
    return f"## Review Evidence\n\n### git diff --stat\n\n```text\n{diff_stat}\n```"


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
    parser = argparse.ArgumentParser(description="Resolve Mary Workflow v2 slash aliases for Codex")
    parser.add_argument(
        "alias",
        choices=["mw-plan", "mw-run", "mw-debug", "mw-status"],
        help="Slash alias without the leading slash",
    )
    parser.add_argument(
        "--project-root",
        default=".",
        help="Project root containing .mary-workflow; defaults to current directory",
    )
    return parser


def main(argv: list[str]) -> int:
    args = build_parser().parse_args(argv)
    root = Path(args.project_root).resolve()
    print(render_prompt(root, args.alias))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
