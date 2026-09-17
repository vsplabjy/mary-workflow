#!/usr/bin/env python3
"""Optional, read-only host capability reporting and lifecycle reminders.

No provider/model configuration is inspected. Hook registration is printed for
review only. Hooks always continue, never authorize work or change Mary state.
"""
from __future__ import annotations

import argparse
from collections.abc import Mapping, Sequence
from itertools import islice
import json
from pathlib import Path
import re
import shlex
import sys

CAPABILITIES = (
    "workers", "worker_resume", "worker_interrupt", "readonly_enforcement",
    "isolated_workspaces", "structured_questions", "progress_list", "native_memory",
    "native_goal", "hooks",
)
EVENTS = ("SessionStart", "PreCompact", "Stop")
MAX_STATE_BYTES = 2 * 1024 * 1024
MAX_TASK_BYTES = 64 * 1024
MAX_TASKS = 64
MAX_INPUT_BYTES = 64 * 1024


def capability_report(capabilities: Mapping[str, object] | None = None) -> dict:
    """Summarize capabilities explicitly reported by the current host session.

    Unknown is not unsupported. An installed binary or provider name cannot
    establish whether a tool is exposed or authorized in this session.
    """
    supplied = {} if capabilities is None else capabilities
    if not isinstance(supplied, Mapping):
        raise ValueError("Capabilities must be an object of explicit boolean values.")
    result = {}
    for name in CAPABILITIES:
        value = supplied.get(name)
        if value is not None and not isinstance(value, bool):
            raise ValueError(f"Capability {name} must be true, false, or null.")
        result[name] = "available" if value is True else "unavailable" if value is False else "unknown"
    return {
        "schema_version": 1,
        "capabilities": result,
        "execution_route": "delegated" if supplied.get("workers") is True else "single_agent" if supplied.get("workers") is False else "discover",
        "source": "explicit host report" if capabilities else "not reported",
    }


def hook_config(host: str = "codex", project: Path | None = None) -> dict:
    """Return optional configuration; do not register it or write any file."""
    if host != "codex":
        raise ValueError("No hook schema adapter is implemented for this host; use the portable core.")
    project = (project or Path.cwd()).resolve()
    handler = project / ".mary-workflow/runtime/scripts/mw_host.py"
    hooks = {}
    for event in EVENTS:
        command = shlex.join([sys.executable, "-B", str(handler), "hook", "--event", event, "--project", str(project)])
        options = {"type": "command", "command": command, "timeout": 3}
        if event == "SessionStart":
            options["additionalContextLimit"] = 1000
        hooks[event] = [{"hooks": [options]}]
    return {"description": "Optional Mary Workflow read-only lifecycle reminders.", "hooks": hooks}


def _root(project: Path) -> Path:
    project = project.resolve()
    # A session can start below its project root. Search a bounded ancestor path,
    # stopping at the first workflow, without invoking Git or scanning a repo.
    for candidate in islice((project, *project.parents), 32):
        root = candidate if candidate.name == ".mary-workflow" else candidate / ".mary-workflow"
        if (root / "state.yaml").is_file():
            return root
    raise FileNotFoundError("No initialized workflow in this project.")


def _short_id(value: object) -> str:
    text = str(value or "")
    return text if re.fullmatch(r"[A-Za-z0-9_.:-]{1,96}", text) else "unavailable"


def _projection(project: Path) -> dict:
    root = _root(project)
    if (root / "state.yaml").stat().st_size > MAX_STATE_BYTES:
        raise ValueError("State exceeds hook inspection limit.")
    # Avoid generating bytecode inside the pinned bundle on this read-only path.
    sys.dont_write_bytecode = True
    from mary_workflow import read_state, legal_actions_for_state
    state = read_state(root)
    phase = str(state.get("phase", ""))
    if phase not in {"PLANNING", "PLANNED", "EXECUTING", "REVIEWING", "DEBUGGING", "FINISHED"}:
        raise ValueError("Unknown phase.")
    pending = 0
    inspected = 0
    truncated = False
    tasks = root / "tasks"
    if tasks.is_dir():
        for directory in islice(tasks.iterdir(), MAX_TASKS + 1):
            if inspected == MAX_TASKS:
                truncated = True
                break
            inspected += 1
            path = directory / "task.json"
            if path.is_file() and path.stat().st_size <= MAX_TASK_BYTES:
                try:
                    task = json.loads(path.read_text(encoding="utf-8"))
                    if isinstance(task, dict) and task.get("status") in {"running", "ready_for_review", "blocked", "failed"}:
                        pending += 1
                except (OSError, ValueError):
                    truncated = True
    return {
        "phase": phase,
        "status": _short_id(state.get("status")),
        "milestone": _short_id(state.get("current_milestone_id")),
        "run_id": _short_id(state.get("lease_run_id")),
        "actions": sorted(legal_actions_for_state(state)),
        "pending_tasks": pending,
        "partial_task_scan": truncated,
    }


def hook_response(event: str, project: Path) -> dict:
    """Fail-open advisory output. Never infer unsaved memory or authorize a run."""
    output: dict = {"continue": True}
    if event not in EVENTS:
        return output
    try:
        info = _projection(project)
        text = (
            f"Mary Workflow: phase={info['phase']}; status={info['status']}; "
            f"milestone={info['milestone']}; run={info['run_id']}. "
            f"Legal actions: {', '.join(info['actions']) or 'none'}. "
            "This snapshot is advisory; re-read current state before applying an action. "
            "It does not authorize execution or change existing user instructions."
        )
        if event == "SessionStart":
            output["hookSpecificOutput"] = {"hookEventName": event, "additionalContext": text}
        else:
            count = ("at least " if info["partial_task_scan"] else "") + str(info["pending_tasks"])
            output["systemMessage"] = (
                text + f" Recorded unfinished worker tasks: {count}. "
                "Check that material findings and unfinished results are persisted; "
                "this hook cannot observe unsaved working memory. "
                "Respect stop requests; do not restart work from this reminder."
            )
    except (Exception, SystemExit):
        # Missing, old, malformed, changing, or oversized state cannot prevent a
        # session, compaction, or stop. Do not echo private parser/OS error text.
        output["systemMessage"] = "Mary Workflow state reminder unavailable; continuing without changes."
    return output


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    status = commands.add_parser("capabilities", help="report only explicitly supplied host capabilities")
    status.add_argument("--json", default="{}", help="object of capability booleans; no configuration is read")
    config = commands.add_parser("hook-config", help="print optional hook JSON without registering it")
    config.add_argument("--host", default="codex")
    config.add_argument("--project", type=Path, default=Path.cwd())
    hook = commands.add_parser("hook", help="process one read-only lifecycle event")
    hook.add_argument("--event")
    hook.add_argument("--project", type=Path)
    args = parser.parse_args(argv)
    if args.command == "hook":
        try:
            payload = {}
            # Generated commands supply both flags and need no stdin. A host
            # invoking without flags provides one closed JSON input stream.
            if not args.event or args.project is None:
                raw = sys.stdin.read(MAX_INPUT_BYTES + 1)
                if len(raw.encode("utf-8")) > MAX_INPUT_BYTES:
                    raise ValueError("Hook input too large.")
                payload = json.loads(raw) if raw.strip() else {}
                if not isinstance(payload, dict):
                    raise ValueError("Hook input must be an object.")
            event = args.event or payload.get("hook_event_name") or payload.get("hookEventName") or ""
            project = args.project or Path(payload.get("cwd") or Path.cwd())
            result = hook_response(event, project)
        except (Exception, SystemExit):
            result = {"continue": True}
        print(json.dumps(result, ensure_ascii=False))
        return 0
    try:
        result = capability_report(json.loads(args.json)) if args.command == "capabilities" else hook_config(args.host, args.project)
    except (ValueError, TypeError) as exc:
        parser.error(str(exc))
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
