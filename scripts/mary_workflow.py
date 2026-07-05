#!/usr/bin/env python3
"""Runtime helper for Mary Workflow v2.

The helper intentionally avoids third-party dependencies. It owns a small
YAML-shaped state file and parses only the fields it writes.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
from typing import Any


WORKFLOW_DIR = ".mary-workflow"
PROMPTS_DIR = "prompts"
REPORTS_DIR = "reports"
STATE_VERSION = 2
VALID_PHASES = {"PLANNING", "EXECUTING", "REVIEWING", "DEBUGGING", "FINISHED"}
PHASE_PROMPTS = {
    "PLANNING": "mw-plan.md",
    "EXECUTING": "mw-execute.md",
    "REVIEWING": "mw-review.md",
    "DEBUGGING": "mw-debug.md",
}
PHASE_ACTIONS = {
    "PLANNING": {"update_state"},
    "EXECUTING": {"mark_task_done", "record_error"},
    "REVIEWING": {"set_phase", "record_error"},
    "DEBUGGING": {"enqueue_fix_task"},
    "FINISHED": set(),
}
CORE_PROMPT_ORDER = {
    "mw-plan.md": 0,
    "mw-execute.md": 1,
    "mw-review.md": 2,
    "mw-debug.md": 3,
}
IGNORED_PROJECT_PARTS = {
    ".git",
    WORKFLOW_DIR,
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    ".venv",
    "venv",
    "node_modules",
    "dist",
    "build",
}

Milestone = dict[str, Any]
State = dict[str, Any]
JsonObject = dict[str, Any]


class WorkflowError(Exception):
    """Recoverable workflow protocol error."""


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def workflow_root(cwd: Path) -> Path:
    return cwd / WORKFLOW_DIR


def skill_root() -> Path:
    return Path(__file__).resolve().parents[1]


def prompt_sort_key(path: Path) -> tuple[int, str]:
    return (CORE_PROMPT_ORDER.get(path.name, 100), path.name)


def prompt_files(root: Path) -> list[str]:
    prompts = root / PROMPTS_DIR
    if not prompts.exists():
        return []
    return [path.name for path in sorted(prompts.iterdir(), key=prompt_sort_key) if path.is_file() and path.suffix == ".md"]


def default_state(project_root: Path | None = None, status: str = "idle") -> State:
    project = detect_project(project_root or Path.cwd())
    return {
        "version": STATE_VERSION,
        "status": status,
        "phase": "PLANNING",
        "started_at": "",
        "updated_at": now_iso(),
        "project_root": project["root"],
        "project_structure": project["structure"],
        "project_tech_stack": project["tech_stack"],
        "project_test_commands": project["test_commands"],
        "current_index": 0,
        "current_prompt": "",
        "current_milestone_id": "",
        "completed": 0,
        "total": 0,
        "lease_owner": "",
        "lease_milestone_id": "",
        "lease_started_at": "",
        "milestones": [],
        "last_error": {
            "command": "",
            "stderr": "",
            "returncode": "",
            "created_at": "",
        },
        "action_counts": {
            "update_state": 0,
            "mark_task_done": 0,
            "set_phase": 0,
            "record_error": 0,
            "enqueue_fix_task": 0,
        },
        "rejected_actions": 0,
        "phase_history": [],
    }


def parse_scalar(value: str) -> str:
    value = value.strip()
    if not value:
        return ""
    if value.startswith('"') and value.endswith('"'):
        return value[1:-1].replace('\\"', '"').replace("\\\\", "\\")
    return value


def quote_value(value: object) -> str:
    text = " ".join(str(value).split())
    return '"' + text.replace("\\", "\\\\").replace('"', '\\"') + '"'


def parse_int(value: object, default: int = 0) -> int:
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return default


def read_state(root: Path) -> State:
    state_path = root / "state.yaml"
    if not state_path.exists():
        return default_state(root.parent)

    state = default_state(root.parent)
    state["project_structure"] = []
    state["project_tech_stack"] = []
    state["project_test_commands"] = []
    milestones: list[Milestone] = []
    section = ""
    subsection = ""
    current_milestone: Milestone | None = None

    for raw_line in state_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.rstrip()
        if not line or line.lstrip().startswith("#"):
            continue

        if not line.startswith(" ") and line.endswith(":"):
            section = line[:-1]
            subsection = ""
            current_milestone = None
            continue

        if not line.startswith(" ") and line.startswith("version:"):
            state["version"] = parse_int(line.split(":", 1)[1])
            continue

        if section == "project":
            if re.match(r"^\s{2}(structure|tech_stack|test_commands):\s*$", line):
                subsection = line.strip()[:-1]
                continue
            list_match = re.match(r"^\s{4}-\s*(.*)$", line)
            if list_match and subsection:
                state[f"project_{subsection}"].append(parse_scalar(list_match.group(1)))
                continue
            key_value = match_key_value(line, indent=2)
            if key_value:
                key, value = key_value
                if key == "root":
                    state["project_root"] = value
            continue

        if section == "milestones":
            if line.startswith("  - "):
                current_milestone = default_milestone()
                milestones.append(current_milestone)
                rest = line[4:].strip()
                if rest:
                    set_milestone_key(current_milestone, rest)
                subsection = ""
                continue
            if current_milestone is None:
                continue
            if re.match(r"^\s{4}(deliverables|acceptance):\s*$", line):
                subsection = line.strip()[:-1]
                continue
            list_match = re.match(r"^\s{6}-\s*(.*)$", line)
            if list_match and subsection in {"deliverables", "acceptance"}:
                current_milestone[subsection].append(parse_scalar(list_match.group(1)))
                continue
            key_value = match_key_value(line, indent=4)
            if key_value:
                set_milestone_key(current_milestone, f"{key_value[0]}: {key_value[1]}")
                subsection = ""
            continue

        if section == "audit":
            if line.startswith("  phase_history:"):
                subsection = "phase_history"
                continue
            if line.startswith("  action_counts:"):
                subsection = "action_counts"
                continue
            if subsection == "phase_history":
                item = re.match(r"^\s{4}-\s*(.*)$", line)
                if item:
                    state["phase_history"].append(parse_scalar(item.group(1)))
                    continue
            if subsection == "action_counts":
                key_value = match_key_value(line, indent=4)
                if key_value:
                    key, value = key_value
                    state["action_counts"][key] = parse_int(value)
                    continue
            key_value = match_key_value(line, indent=2)
            if key_value and key_value[0] == "rejected_actions":
                state["rejected_actions"] = parse_int(key_value[1])
            continue

        key_value = match_key_value(line, indent=2)
        if not key_value:
            continue
        key, value = key_value
        if section == "workflow" and key in {"status", "phase", "started_at", "updated_at"}:
            state[key] = value
        elif section == "current":
            if key == "index":
                state["current_index"] = parse_int(value)
            elif key == "prompt_file":
                state["current_prompt"] = value
            elif key == "milestone_id":
                state["current_milestone_id"] = value
        elif section == "progress" and key in {"completed", "total"}:
            state[key] = parse_int(value)
        elif section == "execution_lease":
            if key == "owner":
                state["lease_owner"] = value
            elif key == "milestone_id":
                state["lease_milestone_id"] = value
            elif key == "started_at":
                state["lease_started_at"] = value
        elif section == "last_error" and key in {"command", "stderr", "returncode", "created_at"}:
            state["last_error"][key] = value

    if state.get("version") != STATE_VERSION:
        raise SystemExit(
            f"Unsupported Mary Workflow state version: {state.get('version') or 'missing'}. "
            "Run /mw-init --reset to create a v2 state. v1 state files are intentionally not migrated."
        )

    state["milestones"] = milestones
    refresh_progress(state)
    sync_prompt_for_phase(state, root)
    return state


def match_key_value(line: str, indent: int) -> tuple[str, str] | None:
    match = re.match(rf"^\s{{{indent}}}([a-z_]+):\s*(.*)$", line)
    if not match:
        return None
    key, value = match.groups()
    return key, parse_scalar(value)


def default_milestone() -> Milestone:
    return {
        "id": "",
        "status": "pending",
        "title": "",
        "deliverables": [],
        "acceptance": [],
        "estimated_scope": 0,
        "gate": "auto",
        "review": "",
    }


def set_milestone_key(milestone: Milestone, text: str) -> None:
    if ":" not in text:
        return
    key, value = text.split(":", 1)
    key = key.strip()
    value = parse_scalar(value)
    if key == "estimated_scope":
        milestone[key] = parse_int(value)
    elif key in {"id", "status", "title", "gate", "review"}:
        milestone[key] = value


def write_state(root: Path, state: State) -> None:
    milestones = state_milestones(state)
    lines = [
        f"version: {STATE_VERSION}",
        "",
        "workflow:",
        f"  status: {state['status']}",
        f"  phase: {state['phase']}",
        f"  started_at: {state['started_at']}",
        f"  updated_at: {state['updated_at']}",
        "",
        "project:",
        f"  root: {quote_value(state['project_root'])}",
        "  structure:",
    ]
    lines.extend(f"    - {quote_value(item)}" for item in state.get("project_structure", []))
    lines.append("  tech_stack:")
    lines.extend(f"    - {quote_value(item)}" for item in state.get("project_tech_stack", []))
    lines.append("  test_commands:")
    lines.extend(f"    - {quote_value(item)}" for item in state.get("project_test_commands", []))
    lines.extend(
        [
            "",
            "current:",
            f"  index: {state['current_index']}",
            f"  prompt_file: {state['current_prompt']}",
            f"  milestone_id: {state['current_milestone_id']}",
            "",
            "progress:",
            f"  completed: {state['completed']}",
            f"  total: {state['total']}",
            "",
            "execution_lease:",
            f"  owner: {state['lease_owner']}",
            f"  milestone_id: {state['lease_milestone_id']}",
            f"  started_at: {state['lease_started_at']}",
            "",
            "milestones:",
        ]
    )
    for milestone in milestones:
        lines.extend(
            [
                f"  - id: {milestone['id']}",
                f"    status: {milestone['status']}",
                f"    title: {quote_value(milestone['title'])}",
                "    deliverables:",
            ]
        )
        lines.extend(f"      - {quote_value(item)}" for item in milestone.get("deliverables", []))
        lines.append("    acceptance:")
        lines.extend(f"      - {quote_value(item)}" for item in milestone.get("acceptance", []))
        lines.extend(
            [
                f"    estimated_scope: {milestone['estimated_scope']}",
                f"    gate: {milestone.get('gate', 'auto')}",
                f"    review: {quote_value(milestone.get('review', ''))}",
            ]
        )

    last_error = state.get("last_error", {})
    if isinstance(last_error, dict) and any(last_error.get(key) for key in ("command", "stderr", "returncode")):
        lines.extend(
            [
                "",
                "last_error:",
                f"  command: {quote_value(last_error.get('command', ''))}",
                f"  stderr: {quote_value(last_error.get('stderr', ''))}",
                f"  returncode: {quote_value(last_error.get('returncode', ''))}",
                f"  created_at: {last_error.get('created_at', '')}",
            ]
        )

    lines.extend(["", "audit:", "  action_counts:"])
    for action in sorted(PHASE_ACTIONS["PLANNING"] | PHASE_ACTIONS["EXECUTING"] | PHASE_ACTIONS["REVIEWING"] | PHASE_ACTIONS["DEBUGGING"]):
        lines.append(f"    {action}: {state.get('action_counts', {}).get(action, 0)}")
    lines.extend([f"  rejected_actions: {state.get('rejected_actions', 0)}", "  phase_history:"])
    lines.extend(f"    - {quote_value(item)}" for item in state.get("phase_history", []))

    (root / "state.yaml").write_text("\n".join(lines) + "\n", encoding="utf-8")


def state_milestones(state: State) -> list[Milestone]:
    milestones = state.get("milestones")
    if isinstance(milestones, list):
        return [milestone for milestone in milestones if isinstance(milestone, dict)]
    return []


def append_log(root: Path, message: str) -> None:
    log_path = root / "log.md"
    if not log_path.exists():
        log_path.write_text("# Mary Workflow Log\n\n", encoding="utf-8")
    with log_path.open("a", encoding="utf-8") as handle:
        handle.write(f"- {now_iso()} {message}\n")


def require_root(cwd: Path) -> Path:
    root = workflow_root(cwd)
    if not root.exists():
        raise SystemExit("Mary Workflow is not initialized. Run /mw-init first.")
    return root


def sync_prompt_for_phase(state: State, root: Path) -> None:
    phase = str(state.get("phase") or "PLANNING")
    prompts = prompt_files(root)
    prompt_name = PHASE_PROMPTS.get(phase)
    if not prompt_name:
        state["current_prompt"] = ""
        state["current_index"] = len(prompts)
        return
    if prompt_name in prompts:
        state["current_prompt"] = prompt_name
        state["current_index"] = prompts.index(prompt_name)


def set_phase(state: State, root: Path, phase: str, reason: str) -> None:
    phase = phase.upper()
    if phase not in VALID_PHASES:
        allowed = ", ".join(sorted(VALID_PHASES))
        raise WorkflowError(f"Invalid phase: {phase}. Expected one of: {allowed}.")
    old_phase = str(state.get("phase") or "PLANNING")
    state["phase"] = phase
    state["updated_at"] = now_iso()
    state["status"] = "completed" if phase == "FINISHED" else "running"
    sync_prompt_for_phase(state, root)
    update_lease(state, phase)
    if old_phase != phase:
        entry = f"{old_phase} -> {phase} ({reason})"
        state.setdefault("phase_history", []).append(entry)
        append_log(root, f"phase {entry}")


def update_lease(state: State, phase: str) -> None:
    if phase == "EXECUTING":
        state["lease_owner"] = "codex"
        state["lease_milestone_id"] = state.get("current_milestone_id", "")
        state["lease_started_at"] = now_iso()
    else:
        state["lease_owner"] = ""
        state["lease_milestone_id"] = ""
        state["lease_started_at"] = ""


def refresh_progress(state: State) -> None:
    milestones = state_milestones(state)
    state["completed"] = sum(1 for milestone in milestones if milestone.get("status") == "done")
    state["total"] = len(milestones)
    current = current_milestone(state)
    if current:
        state["current_milestone_id"] = current["id"]
        state["current_index"] = milestones.index(current)
    elif milestones and state.get("phase") == "FINISHED":
        state["current_milestone_id"] = ""
        state["current_index"] = len(milestones)


def current_milestone(state: State) -> Milestone | None:
    milestones = state_milestones(state)
    current_id = str(state.get("current_milestone_id") or "")
    if current_id:
        for milestone in milestones:
            if milestone.get("id") == current_id:
                return milestone
    for milestone in milestones:
        if milestone.get("status") != "done":
            return milestone
    return None


def first_pending_milestone(state: State) -> Milestone | None:
    for milestone in state_milestones(state):
        if milestone.get("status") != "done":
            return milestone
    return None


def normalize_milestones(value: object) -> list[Milestone]:
    if not isinstance(value, list):
        raise WorkflowError("update_state requires data.milestones to be a list.")
    if not 1 <= len(value) <= 7:
        raise WorkflowError("Mary Workflow accepts 1 to 7 milestones per plan.")

    milestones: list[Milestone] = []
    for index, item in enumerate(value, start=1):
        if not isinstance(item, dict):
            raise WorkflowError("Each milestone must be an object.")
        missing = [field for field in ("deliverables", "acceptance", "estimated_scope") if field not in item]
        if missing:
            raise WorkflowError(f"Milestone {index} missing required field(s): {', '.join(missing)}.")
        title = str(item.get("title", "")).strip()
        if not title:
            raise WorkflowError(f"Milestone {index} requires a non-empty title.")
        milestone_id = str(item.get("id") or f"milestone-{index}").strip()
        if not re.fullmatch(r"milestone-[1-9][0-9]*", milestone_id):
            raise WorkflowError(f"Invalid milestone id: {milestone_id}. Use milestone-1, milestone-2, ...")
        deliverables = normalize_string_list(item.get("deliverables"), f"{milestone_id}.deliverables")
        acceptance = normalize_string_list(item.get("acceptance"), f"{milestone_id}.acceptance")
        estimated_scope = parse_int(item.get("estimated_scope"), -1)
        if estimated_scope < 0:
            raise WorkflowError(f"{milestone_id}.estimated_scope must be a non-negative integer.")
        if estimated_scope > 5:
            raise WorkflowError(
                f"{milestone_id}.estimated_scope is {estimated_scope}; the limit is 5 non-test files. "
                "Split this into smaller independently verifiable milestones."
            )
        gate = str(item.get("gate") or "auto").strip()
        if gate not in {"auto", "confirm"}:
            raise WorkflowError(f"{milestone_id}.gate must be auto or confirm.")
        milestones.append(
            {
                "id": milestone_id,
                "status": "pending",
                "title": title,
                "deliverables": deliverables,
                "acceptance": acceptance,
                "estimated_scope": estimated_scope,
                "gate": gate,
                "review": "",
            }
        )
    return milestones


def normalize_string_list(value: object, field_name: str) -> list[str]:
    if not isinstance(value, list) or not value:
        raise WorkflowError(f"{field_name} must be a non-empty list.")
    result = [str(item).strip() for item in value if str(item).strip()]
    if not result:
        raise WorkflowError(f"{field_name} cannot be empty.")
    return result


def apply_action(root: Path, payload: JsonObject) -> State:
    state = read_state(root)
    action = str(payload.get("action", "")).strip()
    data = payload.get("data", {})
    if not isinstance(data, dict):
        return reject_action(root, state, action, "Action data must be an object.")
    if not is_action_allowed(state, action):
        allowed = sorted(PHASE_ACTIONS.get(str(state.get("phase")), set()))
        allowed_text = ", ".join(allowed) if allowed else "(none)"
        return reject_action(
            root,
            state,
            action,
            f"Illegal action for phase {state['phase']}. Legal actions: {allowed_text}. "
            "Resend a legal action envelope in this turn.",
        )

    try:
        append_log(root, summarize_action(action, data))
        if action == "update_state":
            state = action_update_state(root, state, data)
        elif action == "mark_task_done":
            state = action_mark_task_done(root, state, data)
        elif action == "set_phase":
            state = action_set_phase(root, state, data)
        elif action == "record_error":
            state = action_record_error(root, state, data)
        elif action == "enqueue_fix_task":
            state = action_enqueue_fix_task(root, state, data)
        else:
            return reject_action(root, state, action, f"Unknown action: {action}.")
    except WorkflowError as exc:
        return reject_action(root, state, action, str(exc))

    state.setdefault("action_counts", {})[action] = int(state.setdefault("action_counts", {}).get(action, 0)) + 1
    refresh_progress(state)
    write_state(root, state)
    return state


def is_action_allowed(state: State, action: str) -> bool:
    return action in PHASE_ACTIONS.get(str(state.get("phase")), set())


def reject_action(root: Path, state: State, action: str, reason: str) -> State:
    state["rejected_actions"] = int(state.get("rejected_actions", 0)) + 1
    state["updated_at"] = now_iso()
    append_log(root, f"rejected action={action or '(missing)'} phase={state.get('phase')} reason={reason}")
    write_state(root, state)
    raise SystemExit(f"Rejected action {action or '(missing)'}: {reason}")


def summarize_action(action: str, data: JsonObject) -> str:
    if action == "update_state":
        return f"action update_state milestones={len(data.get('milestones', []))}"
    if action == "mark_task_done":
        return f"action mark_task_done id={data.get('id') or data.get('milestone_id') or ''}"
    if action == "set_phase":
        return f"action set_phase phase={data.get('phase', '')}"
    if action == "record_error":
        return f"action record_error command={normalize_error_text(data.get('command', ''), 120)}"
    if action == "enqueue_fix_task":
        return f"action enqueue_fix_task title={normalize_error_text(data.get('title', ''), 120)}"
    return f"action {action}"


def action_update_state(root: Path, state: State, data: JsonObject) -> State:
    phase = str(data.get("phase") or "EXECUTING").upper()
    if phase != "EXECUTING":
        raise WorkflowError("update_state must move the workflow to EXECUTING.")
    milestones = normalize_milestones(data.get("milestones"))
    state["started_at"] = state["started_at"] or now_iso()
    state["milestones"] = milestones
    state["current_milestone_id"] = milestones[0]["id"]
    refresh_progress(state)
    set_phase(state, root, "EXECUTING", "envelope: update_state")
    append_log(root, f"updated milestones total={len(milestones)}")
    return state


def action_mark_task_done(root: Path, state: State, data: JsonObject) -> State:
    milestone_id = str(data.get("id") or data.get("milestone_id") or state.get("current_milestone_id") or "").strip()
    if not milestone_id:
        raise WorkflowError("mark_task_done requires data.id or data.milestone_id.")
    milestone = find_milestone(state, milestone_id)
    if not milestone:
        raise WorkflowError(f"Milestone not found: {milestone_id}")
    milestone["status"] = "done"
    milestone["review"] = "pending"
    state["current_milestone_id"] = milestone_id
    write_milestone_report(root, milestone, data, "execution")
    refresh_progress(state)
    set_phase(state, root, "REVIEWING", "auto: all tasks done")
    append_log(root, f"marked {milestone_id} done")
    return state


def action_set_phase(root: Path, state: State, data: JsonObject) -> State:
    phase = str(data.get("phase") or "").upper()
    if not phase:
        raise WorkflowError("set_phase requires data.phase.")
    decision = str(data.get("decision") or "").strip().lower()
    current = current_milestone(state)
    if current:
        current["review"] = decision or phase.lower()
        write_milestone_report(root, current, data, "review")

    if phase == "EXECUTING":
        if current and decision in {"needs-fix", "fix", "rework"}:
            current["status"] = "pending"
            state["current_milestone_id"] = current["id"]
        else:
            pending = first_pending_milestone(state)
            if not pending:
                raise WorkflowError("No pending milestone remains; use phase FINISHED.")
            state["current_milestone_id"] = pending["id"]
    elif phase == "FINISHED":
        unfinished = [milestone["id"] for milestone in state_milestones(state) if milestone.get("status") != "done"]
        if unfinished:
            raise WorkflowError(f"Cannot finish while milestones remain unfinished: {', '.join(unfinished)}")
        state["current_milestone_id"] = ""
    elif phase == "PLANNING":
        state["current_milestone_id"] = ""
    elif phase not in VALID_PHASES:
        raise WorkflowError(f"Invalid phase: {phase}.")

    refresh_progress(state)
    set_phase(state, root, phase, "envelope: set_phase")
    return state


def action_record_error(root: Path, state: State, data: JsonObject) -> State:
    state["last_error"] = {
        "command": normalize_error_text(data.get("command", ""), 200),
        "stderr": normalize_error_text(data.get("stderr", ""), 500),
        "returncode": normalize_error_text(data.get("returncode", ""), 40),
        "created_at": now_iso(),
    }
    set_phase(state, root, "DEBUGGING", "envelope: record_error")
    return state


def action_enqueue_fix_task(root: Path, state: State, data: JsonObject) -> State:
    title = str(data.get("title") or data.get("task") or "").strip()
    if not title:
        raise WorkflowError("enqueue_fix_task requires data.title.")
    current = current_milestone(state)
    next_id = f"milestone-{len(state_milestones(state)) + 1}"
    fix_milestone = {
        "id": next_id,
        "status": "pending",
        "title": title,
        "deliverables": normalize_optional_list(data.get("deliverables")) or (current or {}).get("deliverables", ["current milestone deliverables"]),
        "acceptance": normalize_optional_list(data.get("acceptance")) or (current or {}).get("acceptance", ["rerun failing command"]),
        "estimated_scope": max(1, min(parse_int(data.get("estimated_scope"), 1), 5)),
        "gate": "auto",
        "review": "",
    }
    milestones = state_milestones(state)
    insert_at = len(milestones)
    for index, milestone in enumerate(milestones):
        if milestone.get("status") != "done":
            insert_at = index
            break
    milestones.insert(insert_at, fix_milestone)
    state["milestones"] = milestones
    state["current_milestone_id"] = next_id
    if data.get("source_error"):
        state["last_error"]["stderr"] = normalize_error_text(data.get("source_error"), 500)
        state["last_error"]["created_at"] = state["last_error"].get("created_at") or now_iso()
    refresh_progress(state)
    set_phase(state, root, "EXECUTING", "enqueue_fix_task")
    append_log(root, f"enqueued fix milestone {next_id}")
    return state


def normalize_optional_list(value: object) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


def find_milestone(state: State, milestone_id: str) -> Milestone | None:
    for milestone in state_milestones(state):
        if milestone.get("id") == milestone_id:
            return milestone
    return None


def write_milestone_report(root: Path, milestone: Milestone, data: JsonObject, kind: str) -> None:
    reports = root / REPORTS_DIR
    reports.mkdir(exist_ok=True)
    report_path = reports / f"{milestone['id']}.md"
    lines = [
        f"# {milestone['id']} Report",
        "",
        f"- kind: {kind}",
        f"- created_at: {now_iso()}",
        f"- title: {milestone.get('title', '')}",
        "",
        "## Deliverables",
        "",
    ]
    lines.extend(f"- {item}" for item in milestone.get("deliverables", []))
    lines.extend(["", "## Acceptance", ""])
    lines.extend(f"- `{item}`" for item in milestone.get("acceptance", []))
    if data:
        lines.extend(["", "## Action Data", "", "```json", json.dumps(data, indent=2, ensure_ascii=False), "```"])
    diff_stat = git_diff_stat(root.parent)
    if diff_stat:
        lines.extend(["", "## git diff --stat", "", "```text", diff_stat, "```"])
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def git_diff_stat(project_root: Path) -> str:
    try:
        result = subprocess.run(
            ["git", "diff", "--stat"],
            cwd=project_root,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            timeout=5,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return ""
    return result.stdout.strip()


def normalize_error_text(value: object, max_length: int = 500) -> str:
    text = " ".join(str(value or "").split())
    if len(text) > max_length:
        return text[: max_length - 3] + "..."
    return text


def load_json_payload(args: argparse.Namespace) -> JsonObject:
    if args.file:
        raw = Path(args.file).read_text(encoding="utf-8")
    elif args.json:
        raw = args.json
    else:
        raw = sys.stdin.read()
    payload = parse_json_payload(raw)
    if not isinstance(payload, dict):
        raise SystemExit("JSON action must be an object.")
    return payload


def parse_json_payload(raw: str) -> object:
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass

    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", raw, flags=re.DOTALL)
    if fenced:
        try:
            return json.loads(fenced.group(1))
        except json.JSONDecodeError as exc:
            raise SystemExit(f"Invalid fenced JSON action: {exc}") from exc

    candidate = extract_first_json_object(raw)
    if candidate:
        try:
            return json.loads(candidate)
        except json.JSONDecodeError as exc:
            raise SystemExit(f"Invalid embedded JSON action: {exc}") from exc
    raise SystemExit("Invalid JSON action: no JSON object found.")


def extract_first_json_object(raw: str) -> str | None:
    start = raw.find("{")
    if start == -1:
        return None
    depth = 0
    in_string = False
    escaped = False
    for index, char in enumerate(raw[start:], start=start):
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            continue
        if char == '"':
            in_string = True
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return raw[start : index + 1]
    return None


def seed_core_prompts(root: Path) -> int:
    source_dir = skill_root() / WORKFLOW_DIR / PROMPTS_DIR
    target_dir = root / PROMPTS_DIR
    if not source_dir.exists():
        return 0
    count = 0
    for source in sorted(source_dir.glob("mw-*.md"), key=prompt_sort_key):
        target = target_dir / source.name
        if target.exists():
            continue
        if source.resolve() == target.resolve():
            continue
        shutil.copyfile(source, target)
        count += 1
    return count


def write_example_prompts(root: Path) -> int:
    examples = {
        "001-project-scan.md": "Scan the current project structure and summarize the main components.\n",
        "002-improvement-plan.md": "Based on the project scan, propose a short improvement plan with concrete next steps.\n",
    }
    count = 0
    for name, content in examples.items():
        path = root / PROMPTS_DIR / name
        if path.exists():
            continue
        path.write_text(content, encoding="utf-8")
        count += 1
    return count


def detect_project(project_root: Path) -> dict[str, object]:
    files = list_project_files(project_root)
    tech_stack: list[str] = []
    test_commands: list[str] = []
    names = {path.name for path in files}
    suffixes = {path.suffix for path in files}
    if ".py" in suffixes or {"pyproject.toml", "requirements.txt", "setup.py"} & names:
        tech_stack.append("python")
        test_commands.append("pytest")
    if "package.json" in names:
        tech_stack.append("node")
        test_commands.append("npm test")
    if "go.mod" in names:
        tech_stack.append("go")
        test_commands.append("go test ./...")
    if "Cargo.toml" in names:
        tech_stack.append("rust")
        test_commands.append("cargo test")
    if not tech_stack:
        tech_stack.append("unknown")
    structure = [str(path.relative_to(project_root)) for path in files[:40]]
    return {
        "root": str(project_root),
        "structure": structure,
        "tech_stack": tech_stack,
        "test_commands": test_commands or ["manual validation"],
    }


def list_project_files(project_root: Path) -> list[Path]:
    result: list[Path] = []
    for path in sorted(project_root.rglob("*")):
        if any(part in IGNORED_PROJECT_PARTS for part in path.relative_to(project_root).parts):
            continue
        if path.is_file():
            result.append(path)
        if len(result) >= 80:
            break
    return result


def write_config(root: Path) -> None:
    config_path = root / "config.yaml"
    if not config_path.exists():
        config_path.write_text(
            "workflow:\n"
            "  name: Mary Workflow\n"
            "  prompt_glob: prompts/*.md\n"
            "output:\n"
            "  language: auto\n",
            encoding="utf-8",
        )


def cmd_init(args: argparse.Namespace) -> int:
    root = workflow_root(Path.cwd())
    if args.reset and root.exists():
        shutil.rmtree(root)
    elif (root / "state.yaml").exists():
        state_text = (root / "state.yaml").read_text(encoding="utf-8")
        if not re.search(r"^version:\s*2\s*$", state_text, flags=re.MULTILINE):
            raise SystemExit("Existing Mary Workflow state is not v2. Run /mw-init --reset to recreate it.")
        print("Mary Workflow is already initialized. Use /mw-init --reset to recreate it.")
        print_status(read_state(root))
        return 0

    root.mkdir(exist_ok=True)
    (root / PROMPTS_DIR).mkdir(exist_ok=True)
    (root / REPORTS_DIR).mkdir(exist_ok=True)
    write_config(root)

    seeded = seed_core_prompts(root)
    examples = write_example_prompts(root) if args.with_examples else 0
    prompts = prompt_files(root)

    state = default_state(Path.cwd())
    state["phase"] = "PLANNING"
    state["status"] = "idle"
    sync_prompt_for_phase(state, root)
    refresh_progress(state)
    write_state(root, state)
    append_log(root, "initialized workflow v2")

    print(f"Initialized {WORKFLOW_DIR} v2 with {len(prompts)} prompt(s).")
    print("Next: /mw-plan")
    if seeded:
        print(f"Seeded {seeded} core prompt(s).")
    if examples:
        print(f"Seeded {examples} example prompt(s).")
    return 0


def cmd_status(args: argparse.Namespace) -> int:
    root = require_root(Path.cwd())
    state = read_state(root)
    print_status(state)
    return 0


def cmd_apply_action(args: argparse.Namespace) -> int:
    root = require_root(Path.cwd())
    payload = load_json_payload(args)
    state = apply_action(root, payload)
    print_status(state)
    return 0


def cmd_stop(args: argparse.Namespace) -> int:
    root = require_root(Path.cwd())
    state = read_state(root)
    state["status"] = "stopped"
    state["updated_at"] = now_iso()
    write_state(root, state)
    append_log(root, "stopped workflow")
    print_status(state)
    return 0


def print_status(state: State) -> None:
    milestone = current_milestone(state)
    milestone_id = milestone["id"] if milestone else "(none)"
    print(f"version: {state['version']}")
    print(f"status: {state['status']}")
    print(f"phase: {state['phase']}")
    print(f"progress: {state['completed']}/{state['total']}")
    print(f"current_prompt: {state['current_prompt'] or '(none)'}")
    print(f"current_milestone: {milestone_id}")
    if milestone:
        print(f"title: {milestone['title']}")
        print(f"gate: {milestone.get('gate', 'auto')}")
    milestones = state_milestones(state)
    if milestones:
        print("milestones:")
        for item in milestones:
            print(f"  - {item['id']} [{item['status']}] scope={item['estimated_scope']} {item['title']}")
    print(f"rejected_actions: {state.get('rejected_actions', 0)}")
    print("action_counts:")
    for action, count in sorted(state.get("action_counts", {}).items()):
        print(f"  {action}: {count}")
    if state.get("phase_history"):
        print("phase_history:")
        for entry in state["phase_history"]:
            print(f"  - {entry}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Mary Workflow v2 runtime helper")
    subparsers = parser.add_subparsers(dest="command", required=True)

    init_parser = subparsers.add_parser("init", help="create or reset .mary-workflow")
    init_parser.add_argument("--reset", action="store_true", help="remove and recreate .mary-workflow")
    init_parser.add_argument("--with-examples", action="store_true", help="create two starter prompts")
    init_parser.set_defaults(func=cmd_init)

    subparsers.add_parser("status", help="show status without mutating state").set_defaults(func=cmd_status)

    action_parser = subparsers.add_parser("apply-action", help="apply AI JSON action to state")
    action_source = action_parser.add_mutually_exclusive_group()
    action_source.add_argument("--json", help="JSON action string")
    action_source.add_argument("--file", help="path to JSON action file")
    action_parser.set_defaults(func=cmd_apply_action)

    subparsers.add_parser("stop", help="stop workflow").set_defaults(func=cmd_stop)
    return parser


def main(argv: list[str]) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
