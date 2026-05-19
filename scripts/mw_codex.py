#!/usr/bin/env python3
"""Codex-facing bridge for Mary Workflow slash aliases.

Native command markdown files expose slash entries to Codex. This bridge keeps
prompt resolution deterministic by rendering the selected prompt plus state.
"""

from __future__ import annotations

import argparse
from pathlib import Path
import sys


WORKFLOW_DIR = ".mary-workflow"
PROMPTS_DIR = "prompts"
PHASE_TO_PROMPT = {
    "PLANNING": "mw-plan.md",
    "EXECUTING": "mw-execute.md",
    "REVIEWING": "mw-review.md",
    "DEBUGGING": "mw-debug.md",
}
ALIAS_TO_PHASE = {
    "mw-plan": "PLANNING",
    "mw-run": "EXECUTING",
    "mw-review": "REVIEWING",
    "mw-debug": "DEBUGGING",
}


def read_state_phase(root: Path) -> str:
    state_path = root / WORKFLOW_DIR / "state.yaml"
    if not state_path.exists():
        raise SystemExit("Mary Workflow is not initialized. Run /mw-init first.")
    in_workflow = False
    for raw_line in state_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.rstrip()
        if line == "workflow:":
            in_workflow = True
            continue
        if in_workflow and line and not line.startswith(" "):
            in_workflow = False
        if in_workflow and line.strip().startswith("phase:"):
            return line.split(":", 1)[1].strip()
    raise SystemExit("Cannot find workflow.phase in .mary-workflow/state.yaml.")


def require_initialized(root: Path) -> None:
    if not (root / WORKFLOW_DIR / "state.yaml").exists():
        raise SystemExit("Mary Workflow is not initialized. Run /mw-init first.")


def prompt_path_for(root: Path, alias: str) -> tuple[str, Path]:
    normalized = alias.lstrip("/").strip()
    require_initialized(root)
    if normalized == "mw-status":
        phase = read_state_phase(root)
        return phase, Path()
    phase = ALIAS_TO_PHASE.get(normalized)
    if normalized in {"mw-next", "mw-resume"}:
        phase = read_state_phase(root)
        if phase == "FINISHED":
            return phase, Path()
    if not phase:
        valid = ", ".join(f"/{name}" for name in sorted([*ALIAS_TO_PHASE, "mw-next", "mw-resume", "mw-status"]))
        raise SystemExit(f"Unknown Mary Workflow alias: /{normalized}. Available: {valid}")
    prompt_name = PHASE_TO_PROMPT.get(phase)
    if not prompt_name:
        raise SystemExit(f"Phase {phase} has no prompt alias.")
    prompt_path = root / WORKFLOW_DIR / PROMPTS_DIR / prompt_name
    if not prompt_path.exists():
        raise SystemExit(f"Prompt file not found: {prompt_path}")
    return phase, prompt_path


def render_prompt(root: Path, alias: str) -> str:
    normalized = alias.lstrip("/").strip()
    phase, prompt_path = prompt_path_for(root, alias)
    state_path = root / WORKFLOW_DIR / "state.yaml"
    state_text = state_path.read_text(encoding="utf-8") if state_path.exists() else ""
    if normalized == "mw-status" or phase == "FINISHED":
        return (
            f"# Mary Workflow Status Context\n\n"
            f"Alias: /{normalized}\n"
            f"Current phase: {phase}\n\n"
            f"## Current State\n\n"
            f"```yaml\n{state_text}```\n"
        )
    prompt_text = prompt_path.read_text(encoding="utf-8")
    return (
        f"# Mary Workflow Codex Context\n\n"
        f"Alias: /{alias.lstrip('/')}\n"
        f"Resolved phase: {phase}\n"
        f"Prompt file: {prompt_path}\n\n"
        f"## Current State\n\n"
        f"```yaml\n{state_text}```\n\n"
        f"## Phase Prompt\n\n"
        f"{prompt_text}\n"
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Resolve Mary Workflow slash aliases for Codex")
    parser.add_argument(
        "alias",
        choices=["mw-plan", "mw-run", "mw-review", "mw-debug", "mw-next", "mw-resume", "mw-status"],
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
