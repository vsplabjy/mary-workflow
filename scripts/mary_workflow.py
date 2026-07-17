#!/usr/bin/env python3
"""Runtime helper for Mary Workflow v2.1.

The helper intentionally avoids third-party dependencies. It owns a small
YAML-shaped state file and parses only the fields it writes.
"""

from __future__ import annotations

import argparse
import copy
from datetime import datetime, timedelta, timezone
from fnmatch import fnmatchcase
import hashlib
import hmac
import json
import os
from pathlib import Path
import re
import secrets
import shutil
import subprocess
import sys
from typing import Any

from mw_runtime import (
    EnvelopeError,
    action_envelope_parts,
    append_log_entry,
    atomic_write_text,
    extract_first_json_object,
    parse_json_payload as parse_runtime_json_payload,
    require_json_object,
)


WORKFLOW_DIR = ".mary-workflow"
PROMPTS_DIR = "prompts"
REPORTS_DIR = "reports"
ANALYSIS_DIR = "analysis"
BRIEF_FILE = "project-brief.md"
CYCLES_DIR = "cycles"
STATE_VERSION = "2.1"
RUN_GRANT_TTL_SECONDS = 300
EMPTY_PROJECT_SENTINEL = "(empty repository)"
VALID_PHASES = {"PLANNING", "PLANNED", "EXECUTING", "REVIEWING", "DEBUGGING", "FINISHED"}
BRIEF_REFRESH_PHASES = {"PLANNING", "PLANNED", "FINISHED"}
PHASE_PROMPTS = {
    "PLANNING": "mw-plan.md",
    "PLANNED": "mw-ready.md",
    "EXECUTING": "mw-execute.md",
    "REVIEWING": "mw-review.md",
    "DEBUGGING": "mw-debug.md",
}
PHASE_ACTIONS = {
    "PLANNING": {"submit_brief", "update_interview", "update_project", "update_state"},
    "PLANNED": {"reopen_plan", "start_execution"},
    "EXECUTING": {"mark_task_done", "record_error"},
    "REVIEWING": {"set_phase", "record_error"},
    "DEBUGGING": {"enqueue_fix_task"},
    "FINISHED": set(),
}
CORE_PROMPT_ORDER = {
    "mw-init.md": 0,
    "mw-plan.md": 1,
    "mw-ready.md": 2,
    "mw-resume.md": 3,
    "mw-execute.md": 4,
    "mw-review.md": 5,
    "mw-debug.md": 6,
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
    "site-packages",
    ".tox",
    ".nox",
    ".next",
    ".gradle",
    "target",
    "dist",
    "build",
}
BINARY_SUFFIXES = {
    ".7z", ".a", ".avi", ".bin", ".bmp", ".bz2", ".class", ".dll", ".dylib", ".eot",
    ".exe", ".feather", ".gif", ".gz", ".h5", ".hdf5", ".ico", ".jar", ".jpeg", ".jpg",
    ".joblib", ".lockb", ".mov", ".mp3", ".mp4", ".npy", ".npz", ".o", ".obj", ".onnx",
    ".otf", ".parquet", ".pb", ".pdf", ".pkl", ".ply", ".png", ".pt", ".pth", ".pyc",
    ".safetensors", ".so", ".tar", ".tfrecord", ".tiff", ".ttf", ".wav", ".webm", ".webp",
    ".woff", ".woff2", ".xz", ".zip", ".ckpt",
}
DEFAULT_INIT_IGNORE_GLOBS = [
    "artifacts/**",
    "checkpoints/**",
    "data/**",
    "datasets/**",
    "logs/**",
    "output/**",
    "outputs/**",
    "results/**",
    "runs/**",
    "wandb/**",
]

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


def default_state(
    project_root: Path | None = None,
    status: str = "idle",
    *,
    scan_project: bool = True,
) -> State:
    resolved_root = project_root or Path.cwd()
    project = (
        detect_project(resolved_root)
        if scan_project
        else {
            "root": str(resolved_root),
            "structure": [],
            "tech_stack": [],
            "build_commands": [],
            "test_commands": [],
            "run_commands": [],
            "inventory": [],
            "fingerprints": [],
        }
    )
    return {
        "version": STATE_VERSION,
        "cycle": "C0",
        "status": status,
        "phase": "PLANNING",
        "started_at": "",
        "updated_at": now_iso(),
        "project_root": project["root"],
        "project_brief": str(Path(WORKFLOW_DIR) / BRIEF_FILE),
        "project_language": "zh",
        "project_structure": project["structure"],
        "project_tech_stack": project["tech_stack"],
        "project_build_commands": project["build_commands"],
        "project_test_commands": project["test_commands"],
        "project_run_commands": project["run_commands"],
        "project_inventory": project["inventory"],
        "project_brief_status": "machine_detected",
        "project_brief_version": 0,
        "project_brief_updated_at": "",
        "project_brief_cycle": "C0",
        "project_positioning": {},
        "project_architecture": {},
        "project_file_ledger": [],
        "project_uncertainties": [],
        "project_validation": [],
        "project_analysis_evidence": {},
        "project_fingerprints": project["fingerprints"],
        "project_changed_files": [],
        "interview_status": "not_started",
        "interview_round": 0,
        "interview_max_rounds": 3,
        "interview_rounds": [],
        "final_plan_confirmed": False,
        "clarifications": [],
        "draft_milestones": [],
        "current_index": 0,
        "current_prompt": "",
        "current_milestone_id": "",
        "completed": 0,
        "total": 0,
        "lease_owner": "",
        "lease_status": "none",
        "lease_run_id": "",
        "lease_plan_digest": "",
        "lease_cycle": "",
        "lease_milestone_id": "",
        "lease_started_at": "",
        "lease_heartbeat_at": "",
        "run_grant_digest": "",
        "run_grant_fingerprint": "",
        "run_grant_purpose": "",
        "run_grant_plan_digest": "",
        "run_grant_cycle": "",
        "run_grant_issued_at": "",
        "run_grant_expires_at": "",
        "milestones": [],
        "last_error": {
            "command": "",
            "stderr": "",
            "returncode": "",
            "created_at": "",
        },
        "action_counts": {
            "update_interview": 0,
            "update_project": 0,
            "submit_brief": 0,
            "update_state": 0,
            "reopen_plan": 0,
            "start_execution": 0,
            "resume_execution": 0,
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


def parse_json_scalar(value: str, field_name: str) -> object:
    try:
        return json.loads(parse_scalar(value))
    except json.JSONDecodeError as exc:
        raise SystemExit(f"Invalid {field_name} in state.yaml: {exc}") from exc


def quote_value(value: object) -> str:
    text = " ".join(str(value).split())
    return '"' + text.replace("\\", "\\\\").replace('"', '\\"') + '"'


def parse_int(value: object, default: int = 0) -> int:
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return default


def parse_bool(value: object, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    text = str(value).strip().lower()
    if text in {"true", "yes", "1", "on"}:
        return True
    if text in {"false", "no", "0", "off"}:
        return False
    return default


def read_state(root: Path) -> State:
    state_path = root / "state.yaml"
    if not state_path.exists():
        return default_state(root.parent)

    # Existing state is authoritative. Project discovery belongs to explicit init/cycle
    # operations, not to every status read or action envelope.
    state = default_state(root.parent, scan_project=False)
    state["version"] = ""
    state["project_structure"] = []
    state["project_tech_stack"] = []
    state["project_build_commands"] = []
    state["project_test_commands"] = []
    state["project_run_commands"] = []
    state["project_inventory"] = []
    state["project_file_ledger"] = []
    state["project_uncertainties"] = []
    state["project_validation"] = []
    state["project_fingerprints"] = []
    state["project_changed_files"] = []
    state["project_positioning"] = {}
    state["project_architecture"] = {}
    state["project_analysis_evidence"] = {}
    state["interview_rounds"] = []
    state["clarifications"] = []
    state["draft_milestones"] = []
    state["interview_max_rounds"] = max(
        1,
        min(parse_int(read_config(root).get("plan_interview_max_rounds"), 3), 3),
    )
    milestones: list[Milestone] = []
    draft_milestones: list[Milestone] = []
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
            state["version"] = parse_scalar(line.split(":", 1)[1])
            continue
        if not line.startswith(" ") and line.startswith("cycle:"):
            state["cycle"] = parse_scalar(line.split(":", 1)[1])
            continue

        if section == "project":
            if re.match(
                r"^\s{2}(structure|tech_stack|build_commands|test_commands|run_commands|inventory|file_ledger|uncertainties|validation|fingerprints|changed_files):\s*$",
                line,
            ):
                subsection = line.strip()[:-1]
                continue
            list_match = re.match(r"^\s{4}-\s*(.*)$", line)
            if list_match and subsection:
                raw_value = list_match.group(1)
                if subsection in {"file_ledger", "uncertainties", "validation", "fingerprints"}:
                    value = parse_json_scalar(raw_value, f"project.{subsection}")
                    if isinstance(value, dict):
                        state[f"project_{subsection}"].append(value)
                else:
                    state[f"project_{subsection}"].append(parse_scalar(raw_value))
                continue
            key_value = match_key_value(line, indent=2)
            if key_value:
                key, value = key_value
                if key == "root":
                    state["project_root"] = value
                elif key == "brief":
                    state["project_brief"] = value
                elif key == "language":
                    state["project_language"] = value
                elif key == "brief_status":
                    state["project_brief_status"] = value
                elif key == "brief_version":
                    state["project_brief_version"] = parse_int(value)
                elif key == "brief_updated_at":
                    state["project_brief_updated_at"] = value
                elif key == "brief_cycle":
                    state["project_brief_cycle"] = value
                elif key in {"positioning", "architecture", "analysis_evidence"}:
                    parsed = parse_json_scalar(value, f"project.{key}")
                    if isinstance(parsed, dict):
                        state[f"project_{key}"] = parsed
            continue

        if section == "planning":
            if line.startswith("  clarifications:"):
                subsection = "clarifications"
                continue
            if line.startswith("  interview_rounds:"):
                subsection = "interview_rounds"
                continue
            item = re.match(r"^\s{4}-\s*(.*)$", line)
            if item and subsection == "clarifications":
                state["clarifications"].append(parse_scalar(item.group(1)))
                continue
            if item and subsection == "interview_rounds":
                try:
                    round_data = json.loads(parse_scalar(item.group(1)))
                except json.JSONDecodeError as exc:
                    raise SystemExit(f"Invalid interview round in state.yaml: {exc}") from exc
                if isinstance(round_data, dict):
                    state["interview_rounds"].append(round_data)
                continue
            key_value = match_key_value(line, indent=2)
            if key_value:
                key, value = key_value
                if key == "interview_status":
                    state["interview_status"] = value
                elif key == "interview_round":
                    state["interview_round"] = parse_int(value)
                elif key == "interview_max_rounds":
                    state["interview_max_rounds"] = parse_int(value, 3)
                elif key == "final_plan_confirmed":
                    state["final_plan_confirmed"] = parse_bool(value)
            continue

        if section in {"draft_milestones", "milestones"}:
            target_milestones = draft_milestones if section == "draft_milestones" else milestones
            if line.startswith("  - "):
                current_milestone = default_milestone()
                target_milestones.append(current_milestone)
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
            elif key == "status":
                state["lease_status"] = value
            elif key == "run_id":
                state["lease_run_id"] = value
            elif key == "plan_digest":
                state["lease_plan_digest"] = value
            elif key == "cycle":
                state["lease_cycle"] = value
            elif key == "milestone_id":
                state["lease_milestone_id"] = value
            elif key == "started_at":
                state["lease_started_at"] = value
            elif key == "heartbeat_at":
                state["lease_heartbeat_at"] = value
        elif section == "run_grant":
            if key == "token_digest":
                state["run_grant_digest"] = value
            elif key == "fingerprint":
                state["run_grant_fingerprint"] = value
            elif key == "purpose":
                state["run_grant_purpose"] = value
            elif key == "plan_digest":
                state["run_grant_plan_digest"] = value
            elif key == "cycle":
                state["run_grant_cycle"] = value
            elif key == "issued_at":
                state["run_grant_issued_at"] = value
            elif key == "expires_at":
                state["run_grant_expires_at"] = value
        elif section == "last_error" and key in {"command", "stderr", "returncode", "created_at"}:
            state["last_error"][key] = value

    if state.get("version") != STATE_VERSION:
        raise SystemExit(
            f"Unsupported Mary Workflow state version: {state.get('version') or 'missing'}. "
            "Run /mw-init --reset to create a v2.1 state. Earlier state contracts are intentionally not migrated."
        )

    state["milestones"] = milestones
    state["draft_milestones"] = draft_milestones
    refresh_progress(state)
    sync_prompt_for_phase(state, root)
    return state


def match_key_value(line: str, indent: int) -> tuple[str, str] | None:
    match = re.match(r"^\s{%d}([a-z_.]+):\s*(.*)$" % indent, line)
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


def append_milestone_section(lines: list[str], name: str, milestones: list[Milestone]) -> None:
    lines.extend(["", f"{name}:"])
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


def write_state(root: Path, state: State) -> None:
    milestones = state_milestones(state)
    draft_milestones = state_draft_milestones(state)
    lines = [
        f"version: {STATE_VERSION}",
        f"cycle: {state.get('cycle', 'C0')}",
        "",
        "workflow:",
        f"  status: {state['status']}",
        f"  phase: {state['phase']}",
        f"  started_at: {state['started_at']}",
        f"  updated_at: {state['updated_at']}",
        "",
        "project:",
        f"  root: {quote_value(state['project_root'])}",
        f"  brief: {quote_value(state.get('project_brief', str(Path(WORKFLOW_DIR) / BRIEF_FILE)))}",
        f"  language: {state.get('project_language', 'zh')}",
        f"  brief_status: {state.get('project_brief_status', 'machine_detected')}",
        f"  brief_version: {state.get('project_brief_version', 0)}",
        f"  brief_updated_at: {state.get('project_brief_updated_at', '')}",
        f"  brief_cycle: {state.get('project_brief_cycle', state.get('cycle', 'C0'))}",
        f"  positioning: {quote_value(json.dumps(state.get('project_positioning', {}), ensure_ascii=False, separators=(',', ':')))}",
        f"  architecture: {quote_value(json.dumps(state.get('project_architecture', {}), ensure_ascii=False, separators=(',', ':')))}",
        f"  analysis_evidence: {quote_value(json.dumps(state.get('project_analysis_evidence', {}), ensure_ascii=False, separators=(',', ':')))}",
        "  structure:",
    ]
    lines.extend(f"    - {quote_value(item)}" for item in state.get("project_structure", []))
    lines.append("  tech_stack:")
    lines.extend(f"    - {quote_value(item)}" for item in state.get("project_tech_stack", []))
    lines.append("  build_commands:")
    lines.extend(f"    - {quote_value(item)}" for item in state.get("project_build_commands", []))
    lines.append("  test_commands:")
    lines.extend(f"    - {quote_value(item)}" for item in state.get("project_test_commands", []))
    lines.append("  run_commands:")
    lines.extend(f"    - {quote_value(item)}" for item in state.get("project_run_commands", []))
    lines.append("  inventory:")
    lines.extend(f"    - {quote_value(item)}" for item in state.get("project_inventory", []))
    for section_name in ("file_ledger", "uncertainties", "validation", "fingerprints"):
        lines.append(f"  {section_name}:")
        lines.extend(
            f"    - {quote_value(json.dumps(item, ensure_ascii=False, separators=(',', ':')))}"
            for item in state.get(f"project_{section_name}", [])
            if isinstance(item, dict)
        )
    lines.append("  changed_files:")
    lines.extend(f"    - {quote_value(item)}" for item in state.get("project_changed_files", []))
    lines.extend(
        [
            "",
            "planning:",
            f"  interview_status: {state.get('interview_status', 'not_started')}",
            f"  interview_round: {state.get('interview_round', 0)}",
            f"  interview_max_rounds: {state.get('interview_max_rounds', 3)}",
            f"  final_plan_confirmed: {str(bool(state.get('final_plan_confirmed'))).lower()}",
            "  interview_rounds:",
        ]
    )
    lines.extend(
        f"    - {quote_value(json.dumps(item, ensure_ascii=False, separators=(',', ':')))}"
        for item in state.get("interview_rounds", [])
        if isinstance(item, dict)
    )
    lines.append("  clarifications:")
    lines.extend(f"    - {quote_value(item)}" for item in state.get("clarifications", []))
    append_milestone_section(lines, "draft_milestones", draft_milestones)
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
            f"  status: {state.get('lease_status', 'none')}",
            f"  run_id: {state.get('lease_run_id', '')}",
            f"  plan_digest: {state.get('lease_plan_digest', '')}",
            f"  cycle: {state.get('lease_cycle', '')}",
            f"  milestone_id: {state['lease_milestone_id']}",
            f"  started_at: {state['lease_started_at']}",
            f"  heartbeat_at: {state.get('lease_heartbeat_at', '')}",
            "",
            "run_grant:",
            f"  token_digest: {state.get('run_grant_digest', '')}",
            f"  fingerprint: {state.get('run_grant_fingerprint', '')}",
            f"  purpose: {state.get('run_grant_purpose', '')}",
            f"  plan_digest: {state.get('run_grant_plan_digest', '')}",
            f"  cycle: {state.get('run_grant_cycle', '')}",
            f"  issued_at: {state.get('run_grant_issued_at', '')}",
            f"  expires_at: {state.get('run_grant_expires_at', '')}",
        ]
    )
    append_milestone_section(lines, "milestones", milestones)

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
    for action in all_action_names():
        lines.append(f"    {action}: {state.get('action_counts', {}).get(action, 0)}")
    lines.extend([f"  rejected_actions: {state.get('rejected_actions', 0)}", "  phase_history:"])
    lines.extend(f"    - {quote_value(item)}" for item in state.get("phase_history", []))

    atomic_write_text(root / "state.yaml", "\n".join(lines) + "\n", encoding="utf-8")


def state_milestones(state: State) -> list[Milestone]:
    milestones = state.get("milestones")
    if isinstance(milestones, list):
        return [milestone for milestone in milestones if isinstance(milestone, dict)]
    return []


def state_draft_milestones(state: State) -> list[Milestone]:
    milestones = state.get("draft_milestones")
    if isinstance(milestones, list):
        return [milestone for milestone in milestones if isinstance(milestone, dict)]
    return []


def all_action_names() -> list[str]:
    return sorted({action for actions in PHASE_ACTIONS.values() for action in actions} | {"resume_execution"})


def append_log(root: Path, message: str) -> None:
    append_log_entry(
        root / "log.md",
        message,
        timestamp=now_iso(),
        header="# Mary Workflow Log\n\n",
    )


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
    if phase == "FINISHED":
        state["status"] = "completed"
    elif phase == "PLANNED":
        state["status"] = "ready"
    elif phase == "PLANNING":
        state["status"] = "planning"
    else:
        state["status"] = "running"
    sync_prompt_for_phase(state, root)
    if old_phase != phase:
        entry = f"{old_phase} -> {phase} ({reason})"
        state.setdefault("phase_history", []).append(entry)
        append_log(root, f"phase {entry}")


def current_plan_digest(state: State) -> str:
    payload = {
        "cycle": state.get("cycle", "C0"),
        "clarifications": list(state.get("clarifications", [])),
        "milestones": milestone_plan_signature(state_milestones(state)),
    }
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def clear_run_grant(state: State) -> None:
    state["run_grant_digest"] = ""
    state["run_grant_fingerprint"] = ""
    state["run_grant_purpose"] = ""
    state["run_grant_plan_digest"] = ""
    state["run_grant_cycle"] = ""
    state["run_grant_issued_at"] = ""
    state["run_grant_expires_at"] = ""


def issue_run_authorization(root: Path) -> JsonObject:
    state = read_state(root)
    phase = str(state.get("phase"))
    if (
        phase == "PLANNED"
        and state.get("interview_status") == "plan_ready"
        and not state.get("final_plan_confirmed")
        and state.get("lease_status") in {"none", "released"}
    ):
        purpose = "start"
    elif (
        phase in {"EXECUTING", "REVIEWING", "DEBUGGING"}
        and state.get("status") == "stopped"
        and state.get("lease_status") == "paused"
    ):
        purpose = "resume"
    else:
        raise SystemExit("Run authorization requires a ready plan or a stopped workflow with a paused lease.")

    token = secrets.token_urlsafe(24)
    token_digest = hashlib.sha256(token.encode("utf-8")).hexdigest()
    issued_at = datetime.now(timezone.utc).replace(microsecond=0)
    expires_at = issued_at + timedelta(seconds=RUN_GRANT_TTL_SECONDS)
    plan_digest = current_plan_digest(state)
    fingerprint = token_digest[:12]
    state["run_grant_digest"] = token_digest
    state["run_grant_fingerprint"] = fingerprint
    state["run_grant_purpose"] = purpose
    state["run_grant_plan_digest"] = plan_digest
    state["run_grant_cycle"] = str(state.get("cycle", "C0"))
    state["run_grant_issued_at"] = issued_at.isoformat()
    state["run_grant_expires_at"] = expires_at.isoformat()
    state["updated_at"] = issued_at.isoformat()
    write_state(root, state)
    append_log(root, f"issued /mw-run grant purpose={purpose} fingerprint={fingerprint} plan={plan_digest[:12]}")
    return {
        "token": token,
        "purpose": purpose,
        "fingerprint": fingerprint,
        "plan_digest": plan_digest,
        "expires_at": expires_at.isoformat(),
    }


def consume_run_grant(state: State, token: str, expected_purpose: str) -> str:
    stored_digest = str(state.get("run_grant_digest") or "")
    supplied_digest = hashlib.sha256(token.encode("utf-8")).hexdigest()
    if not stored_digest or not hmac.compare_digest(stored_digest, supplied_digest):
        raise WorkflowError("The /mw-run grant is missing, invalid, or already consumed.")
    if state.get("run_grant_purpose") != expected_purpose:
        raise WorkflowError(f"The /mw-run grant purpose must be {expected_purpose}.")
    if state.get("run_grant_cycle") != state.get("cycle"):
        raise WorkflowError("The /mw-run grant belongs to a different cycle.")
    if state.get("run_grant_plan_digest") != current_plan_digest(state):
        raise WorkflowError("The /mw-run grant is stale because the plan changed.")
    try:
        expires_at = datetime.fromisoformat(str(state.get("run_grant_expires_at")))
    except ValueError as exc:
        raise WorkflowError("The /mw-run grant has an invalid expiry timestamp.") from exc
    if datetime.now(timezone.utc) > expires_at:
        raise WorkflowError("The /mw-run grant has expired.")
    fingerprint = str(state.get("run_grant_fingerprint") or supplied_digest[:12])
    clear_run_grant(state)
    return fingerprint


def acquire_execution_lease(state: State) -> None:
    if state.get("lease_status") not in {"none", "released"}:
        raise WorkflowError(f"Cannot acquire execution lease while lease_status={state.get('lease_status')}.")
    timestamp = now_iso()
    state["lease_owner"] = "codex"
    state["lease_status"] = "active"
    state["lease_run_id"] = secrets.token_hex(12)
    state["lease_plan_digest"] = current_plan_digest(state)
    state["lease_cycle"] = str(state.get("cycle", "C0"))
    state["lease_milestone_id"] = state.get("current_milestone_id", "")
    state["lease_started_at"] = timestamp
    state["lease_heartbeat_at"] = timestamp


def sync_execution_lease(state: State) -> None:
    if state.get("lease_status") == "active":
        state["lease_plan_digest"] = current_plan_digest(state)
        state["lease_milestone_id"] = state.get("current_milestone_id", "")
        state["lease_heartbeat_at"] = now_iso()


def pause_execution_lease(state: State) -> None:
    if state.get("lease_status") == "active":
        state["lease_owner"] = ""
        state["lease_status"] = "paused"
        state["lease_heartbeat_at"] = now_iso()


def resume_execution_lease(state: State) -> None:
    if state.get("lease_status") != "paused" or not state.get("lease_run_id"):
        raise WorkflowError("resume_execution requires a paused existing lease.")
    if state.get("lease_plan_digest") != current_plan_digest(state):
        raise WorkflowError("Cannot resume because the active plan no longer matches the lease.")
    state["lease_owner"] = "codex"
    state["lease_status"] = "active"
    state["lease_heartbeat_at"] = now_iso()


def release_execution_lease(state: State) -> None:
    state["lease_owner"] = ""
    state["lease_status"] = "released"
    state["lease_milestone_id"] = ""
    state["lease_heartbeat_at"] = now_iso()


def clear_execution_lease(state: State) -> None:
    state["lease_owner"] = ""
    state["lease_status"] = "none"
    state["lease_run_id"] = ""
    state["lease_plan_digest"] = ""
    state["lease_cycle"] = ""
    state["lease_milestone_id"] = ""
    state["lease_started_at"] = ""
    state["lease_heartbeat_at"] = ""


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
    try:
        action, data = action_envelope_parts(payload)
    except EnvelopeError as exc:
        action = str(payload.get("action", "")).strip()
        return reject_action(root, state, action, str(exc))
    if not is_action_allowed(state, action):
        allowed = sorted(legal_actions_for_state(state))
        allowed_text = ", ".join(allowed) if allowed else "(none)"
        return reject_action(
            root,
            state,
            action,
            f"Illegal action for phase {state['phase']}. Legal actions: {allowed_text}. "
            "Resend a legal action envelope in this turn.",
        )

    try:
        working_state = copy.deepcopy(state)
        append_log(root, summarize_action(action, data))
        if action == "update_interview":
            state = action_update_interview(root, working_state, data)
        elif action == "update_project":
            state = action_update_project(root, working_state, data)
        elif action == "submit_brief":
            state = action_submit_brief(root, working_state, data)
        elif action == "update_state":
            state = action_update_state(root, working_state, data)
        elif action == "reopen_plan":
            state = action_reopen_plan(root, working_state, data)
        elif action == "start_execution":
            state = action_start_execution(root, working_state, data)
        elif action == "resume_execution":
            state = action_resume_execution(root, working_state, data)
        elif action == "mark_task_done":
            state = action_mark_task_done(root, working_state, data)
        elif action == "set_phase":
            state = action_set_phase(root, working_state, data)
        elif action == "record_error":
            state = action_record_error(root, working_state, data)
        elif action == "enqueue_fix_task":
            state = action_enqueue_fix_task(root, working_state, data)
        else:
            return reject_action(root, state, action, f"Unknown action: {action}.")
    except WorkflowError as exc:
        return reject_action(root, state, action, str(exc))

    state.setdefault("action_counts", {})[action] = int(state.setdefault("action_counts", {}).get(action, 0)) + 1
    refresh_progress(state)
    write_state(root, state)
    return state


def is_action_allowed(state: State, action: str) -> bool:
    return action in legal_actions_for_state(state)


def legal_actions_for_state(state: State) -> set[str]:
    phase = str(state.get("phase"))
    brief_status = str(state.get("project_brief_status") or "machine_detected")
    if brief_status == "refresh_required" and phase in BRIEF_REFRESH_PHASES:
        return {"submit_brief"}
    if phase == "PLANNING" and brief_status != "complete":
        return {"submit_brief", "update_project"}
    if state.get("status") == "stopped" and phase in {"EXECUTING", "REVIEWING", "DEBUGGING"}:
        return {"resume_execution"}
    return PHASE_ACTIONS.get(phase, set())


def reject_action(root: Path, state: State, action: str, reason: str) -> State:
    state["rejected_actions"] = int(state.get("rejected_actions", 0)) + 1
    state["updated_at"] = now_iso()
    append_log(root, f"rejected action={action or '(missing)'} phase={state.get('phase')} reason={reason}")
    write_state(root, state)
    raise SystemExit(f"Rejected action {action or '(missing)'}: {reason}")


def summarize_action(action: str, data: JsonObject) -> str:
    if action == "update_interview":
        return f"action update_interview mode={data.get('mode', '')} round={data.get('round', '')}"
    if action == "update_state":
        return f"action update_state milestones={len(data.get('milestones', []))}"
    if action == "reopen_plan":
        return "action reopen_plan"
    if action == "start_execution":
        return "action start_execution"
    if action == "resume_execution":
        return "action resume_execution"
    if action == "update_project":
        return "action update_project"
    if action == "submit_brief":
        return f"action submit_brief mode={data.get('mode', '')} ledger={len(data.get('file_ledger', []))}"
    if action == "mark_task_done":
        return f"action mark_task_done id={data.get('id') or data.get('milestone_id') or ''}"
    if action == "set_phase":
        return f"action set_phase phase={data.get('phase', '')}"
    if action == "record_error":
        return f"action record_error command={normalize_error_text(data.get('command', ''), 120)}"
    if action == "enqueue_fix_task":
        return f"action enqueue_fix_task title={normalize_error_text(data.get('title', ''), 120)}"
    return f"action {action}"


def interview_rounds(state: State) -> list[JsonObject]:
    rounds = state.get("interview_rounds")
    if isinstance(rounds, list):
        return [item for item in rounds if isinstance(item, dict)]
    return []


def interview_clarifications(state: State) -> list[str]:
    result: list[str] = []
    revision_index = 0
    for item in interview_rounds(state):
        kind = str(item.get("kind") or "interview")
        answers = " | ".join(normalize_optional_list(item.get("answers"))) or "(none)"
        defaults = " | ".join(normalize_optional_list(item.get("defaults"))) or "(none)"
        if kind == "interview":
            questions = " | ".join(normalize_optional_list(item.get("questions"))) or "(none)"
            result.append(
                f"Round {parse_int(item.get('round'))}: anchor={item.get('anchor') or 'initial request'}; "
                f"uncertainty={item.get('uncertainty') or '(none)'}; questions={questions}; "
                f"answers={answers}; defaults={defaults}"
            )
        elif kind == "default_confirmation":
            result.append(f"Round 0 defaults: {defaults}; user_response={answers}")
        elif kind == "assumptions":
            result.append(f"Interview off assumptions: {defaults}; user_response={answers}")
        elif kind == "revision":
            revision_index += 1
            result.append(f"Plan revision {revision_index}: feedback={answers}; defaults={defaults}")
    return result


def milestone_plan_signature(milestones: list[Milestone]) -> list[dict[str, object]]:
    return [
        {
            "id": item.get("id"),
            "title": item.get("title"),
            "deliverables": list(item.get("deliverables", [])),
            "acceptance": list(item.get("acceptance", [])),
            "estimated_scope": item.get("estimated_scope"),
            "gate": item.get("gate", "auto"),
        }
        for item in milestones
    ]


def configured_interview_max_rounds(root: Path) -> int:
    return max(1, min(parse_int(read_config(root).get("plan_interview_max_rounds"), 3), 3))


def reset_planning_session(state: State, root: Path, clear_milestones: bool = True) -> None:
    state["interview_status"] = "not_started"
    state["interview_round"] = 0
    state["interview_max_rounds"] = configured_interview_max_rounds(root)
    state["interview_rounds"] = []
    state["final_plan_confirmed"] = False
    state["clarifications"] = []
    state["draft_milestones"] = []
    state["started_at"] = ""
    clear_run_grant(state)
    state["current_milestone_id"] = ""
    if clear_milestones:
        state["milestones"] = []


def append_interview_round(state: State, root: Path, data: JsonObject) -> None:
    round_number = parse_int(data.get("round"), -1)
    rounds = interview_rounds(state)
    if any(item.get("status") == "awaiting_answer" for item in rounds):
        raise WorkflowError("Resolve the pending interview round before opening another round.")

    defaults = normalize_optional_list(data.get("defaults"))
    questions = normalize_optional_list(data.get("questions"))
    if round_number == 0:
        if rounds or parse_int(state.get("interview_round"), 0) != 0:
            raise WorkflowError("Round 0 default confirmation is allowed only before any interview round.")
        if not defaults:
            raise WorkflowError("Round 0 requires non-empty data.defaults.")
        if len(questions) != 1:
            raise WorkflowError("Round 0 requires exactly one explicit confirmation question.")
        kind = "default_confirmation"
        anchor = "small-task defaults"
        uncertainty = "user confirmation"
    else:
        positive_rounds = [parse_int(item.get("round")) for item in rounds if parse_int(item.get("round")) > 0]
        expected_round = (max(positive_rounds) + 1) if positive_rounds else 1
        if round_number != expected_round:
            raise WorkflowError(f"Expected interview round {expected_round}, got {round_number}.")
        max_rounds = configured_interview_max_rounds(root)
        if round_number > max_rounds:
            raise WorkflowError(f"Interview round {round_number} exceeds configured maximum {max_rounds}.")
        if not 3 <= len(questions) <= 5:
            raise WorkflowError("Each active interview round requires 3 to 5 questions.")
        anchor = str(data.get("anchor") or "").strip()
        uncertainty = str(data.get("uncertainty") or "").strip()
        if round_number > 1 and (not anchor or not uncertainty):
            raise WorkflowError("Rounds after the first require data.anchor and data.uncertainty.")
        kind = "interview"

    rounds.append(
        {
            "kind": kind,
            "round": round_number,
            "status": "awaiting_answer",
            "anchor": anchor,
            "uncertainty": uncertainty,
            "questions": questions,
            "answers": [],
            "defaults": defaults,
        }
    )
    state["interview_rounds"] = rounds
    state["interview_round"] = max(parse_int(state.get("interview_round")), round_number)
    state["interview_max_rounds"] = configured_interview_max_rounds(root)
    state["interview_status"] = "awaiting_answers"
    state["final_plan_confirmed"] = False
    state["draft_milestones"] = []
    state["clarifications"] = interview_clarifications(state)


def validate_interview_depth(root: Path, state: State, draft: list[Milestone]) -> None:
    if read_config(root).get("plan_interview", "on") != "on":
        return
    answered_rounds = [
        item
        for item in interview_rounds(state)
        if item.get("kind") == "interview" and item.get("status") == "answered"
    ]
    if len(draft) >= 5 and len(answered_rounds) < 2:
        raise WorkflowError("Plans with 5 or more milestones require at least 2 answered interview rounds.")
    if 3 <= len(draft) <= 4 and not answered_rounds:
        raise WorkflowError("Plans with 3 or 4 milestones require at least 1 answered interview round.")
    if len(draft) <= 2 and not answered_rounds:
        defaults_confirmed = any(
            item.get("kind") == "default_confirmation" and item.get("status") == "answered"
            for item in interview_rounds(state)
        )
        if not defaults_confirmed:
            raise WorkflowError("A 0-round small plan requires explicit user confirmation of its defaults.")


def action_update_interview(root: Path, state: State, data: JsonObject) -> State:
    mode = str(data.get("mode") or "").strip().lower()
    interview_enabled = read_config(root).get("plan_interview", "on") == "on"

    if mode == "open":
        if not interview_enabled:
            raise WorkflowError("Interview is off; use update_interview mode=propose.")
        if state.get("interview_status") not in {"not_started", "in_progress"}:
            raise WorkflowError(f"Cannot open a round while interview_status={state.get('interview_status')}.")
        append_interview_round(state, root, data)
    elif mode == "resolve":
        rounds = interview_rounds(state)
        pending = next((item for item in reversed(rounds) if item.get("status") == "awaiting_answer"), None)
        if not pending:
            raise WorkflowError("No pending interview round is awaiting answers.")
        round_number = parse_int(data.get("round"), -1)
        if round_number != parse_int(pending.get("round"), -2):
            raise WorkflowError(f"Expected answers for round {pending.get('round')}, got round {round_number}.")
        answers = normalize_string_list(data.get("answers"), "update_interview.data.answers")
        if normalize_optional_list(data.get("defaults")):
            raise WorkflowError(
                "resolve cannot introduce new defaults. Persist and show every default before waiting for the user's answer."
            )
        pending["answers"] = answers
        pending["status"] = "answered"

        if parse_bool(data.get("complete")):
            draft = normalize_milestones(data.get("draft_milestones"))
            validate_interview_depth(root, state, draft)
            state["draft_milestones"] = draft
            state["interview_status"] = "draft_ready"
            state["final_plan_confirmed"] = False
        else:
            next_round = data.get("next_round")
            if not isinstance(next_round, dict):
                raise WorkflowError("Incomplete interviews require data.next_round.")
            state["interview_status"] = "in_progress"
            append_interview_round(state, root, next_round)
    elif mode == "propose":
        if interview_enabled:
            raise WorkflowError("Interview is on; open and resolve the required interview rounds first.")
        assumptions = normalize_string_list(data.get("clarifications"), "update_interview.data.clarifications")
        questions = normalize_optional_list(data.get("questions"))
        if len(questions) != 1:
            raise WorkflowError("Interview-off assumptions require exactly one explicit confirmation question.")
        draft = normalize_milestones(data.get("draft_milestones"))
        state["interview_rounds"] = [
            {
                "kind": "assumptions",
                "round": 0,
                "status": "awaiting_answer",
                "anchor": "interview disabled",
                "uncertainty": "explicit assumption confirmation",
                "questions": questions,
                "answers": [],
                "defaults": assumptions,
            }
        ]
        state["draft_milestones"] = draft
        state["interview_status"] = "awaiting_answers"
        state["final_plan_confirmed"] = False
    elif mode == "revise":
        if state.get("interview_status") != "draft_ready":
            raise WorkflowError("Plan revisions require interview_status=draft_ready.")
        if normalize_optional_list(data.get("defaults")):
            raise WorkflowError(
                "revise cannot introduce new defaults. Open a confirmation round before using additional assumptions."
            )
        feedback = normalize_string_list(data.get("feedback"), "update_interview.data.feedback")
        draft = normalize_milestones(data.get("draft_milestones"))
        validate_interview_depth(root, state, draft)
        rounds = interview_rounds(state)
        rounds.append(
            {
                "kind": "revision",
                "round": state.get("interview_round", 0),
                "status": "answered",
                "anchor": "draft plan",
                "uncertainty": "user-requested revision",
                "questions": [],
                "answers": feedback,
                "defaults": [],
            }
        )
        state["interview_rounds"] = rounds
        state["draft_milestones"] = draft
        state["final_plan_confirmed"] = False
    else:
        raise WorkflowError("update_interview data.mode must be open, resolve, propose, or revise.")

    state["clarifications"] = interview_clarifications(state)
    state["updated_at"] = now_iso()
    append_log(root, f"updated interview mode={mode} status={state.get('interview_status')}")
    return state


def action_update_project(root: Path, state: State, data: JsonObject) -> State:
    if "structure" in data:
        state["project_structure"] = normalize_optional_list(data.get("structure"))
    if "tech_stack" in data:
        state["project_tech_stack"] = normalize_optional_list(data.get("tech_stack")) or ["unknown"]
    if "build_commands" in data:
        state["project_build_commands"] = normalize_optional_list(data.get("build_commands")) or ["no build command detected"]
    if "test_commands" in data:
        state["project_test_commands"] = normalize_optional_list(data.get("test_commands")) or ["manual validation"]
    if "run_commands" in data:
        state["project_run_commands"] = normalize_optional_list(data.get("run_commands")) or ["no run command detected"]
    if data.get("language"):
        language = str(data.get("language")).strip()
        if language not in {"auto", "zh", "en"}:
            raise WorkflowError("update_project data.language must be auto, zh, or en.")
        state["project_language"] = language
        update_config(root, language=language)
    state["updated_at"] = now_iso()
    write_project_brief(root, state)
    append_log(root, "updated project brief")
    return state


def require_text(value: object, field_name: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise WorkflowError(f"{field_name} must be non-empty.")
    return text


def require_object(value: object, field_name: str) -> JsonObject:
    if not isinstance(value, dict):
        raise WorkflowError(f"{field_name} must be an object.")
    return value


def normalize_positioning(value: object) -> JsonObject:
    data = require_object(value, "submit_brief.data.positioning")
    return {
        "purpose": require_text(data.get("purpose"), "positioning.purpose"),
        "audience": require_text(data.get("audience"), "positioning.audience"),
        "problem": require_text(data.get("problem"), "positioning.problem"),
        "differentiators": require_text(data.get("differentiators"), "positioning.differentiators"),
    }


def normalize_brief_architecture(value: object, inventory: set[str]) -> JsonObject:
    data = require_object(value, "submit_brief.data.architecture")
    raw_modules = data.get("modules")
    if not isinstance(raw_modules, list) or not raw_modules:
        raise WorkflowError("architecture.modules must be a non-empty list.")
    modules: list[JsonObject] = []
    for index, item in enumerate(raw_modules, start=1):
        module = require_object(item, f"architecture.modules[{index}]")
        files = normalize_string_list(module.get("files"), f"architecture.modules[{index}].files")
        invalid = [path for path in files if path not in inventory and not path.startswith("(none")]
        if invalid:
            raise WorkflowError(f"architecture module references files outside inventory: {', '.join(invalid)}")
        modules.append(
            {
                "name": require_text(module.get("name"), f"architecture.modules[{index}].name"),
                "responsibility": require_text(
                    module.get("responsibility"), f"architecture.modules[{index}].responsibility"
                ),
                "files": files,
            }
        )
    return {
        "modules": modules,
        "dependency_graph": normalize_string_list(data.get("dependency_graph"), "architecture.dependency_graph"),
        "data_flow": normalize_string_list(data.get("data_flow"), "architecture.data_flow"),
        "state_management": normalize_string_list(data.get("state_management"), "architecture.state_management"),
    }


def normalize_file_ledger(value: object, expected_inventory: list[str]) -> list[JsonObject]:
    if not isinstance(value, list) or not value:
        raise WorkflowError("file_ledger must be a non-empty list covering the full machine inventory.")
    ledger: list[JsonObject] = []
    seen: set[str] = set()
    for index, item in enumerate(value, start=1):
        record = require_object(item, f"file_ledger[{index}]")
        path = require_text(record.get("path"), f"file_ledger[{index}].path")
        if path in seen:
            raise WorkflowError(f"file_ledger contains duplicate path: {path}")
        seen.add(path)
        ledger.append(
            {
                "path": path,
                "purpose": require_text(record.get("purpose"), f"file_ledger[{index}].purpose"),
                "exports": normalize_string_list(record.get("exports"), f"file_ledger[{index}].exports"),
                "used_by": normalize_string_list(record.get("used_by"), f"file_ledger[{index}].used_by"),
            }
        )
    expected = set(expected_inventory)
    missing = sorted(expected - seen)
    extra = sorted(seen - expected)
    if missing or extra:
        details = []
        if missing:
            details.append(f"missing={missing}")
        if extra:
            details.append(f"extra={extra}")
        raise WorkflowError("file_ledger must exactly cover machine inventory: " + "; ".join(details))
    return ledger


def normalize_uncertainties(value: object) -> list[JsonObject]:
    if not isinstance(value, list) or not value:
        raise WorkflowError("uncertainties must be a non-empty list of inferred or unresolved items.")
    result: list[JsonObject] = []
    for index, item in enumerate(value, start=1):
        record = require_object(item, f"uncertainties[{index}]")
        status = require_text(record.get("status"), f"uncertainties[{index}].status")
        if status not in {"inferred", "unresolved"}:
            raise WorkflowError(f"uncertainties[{index}].status must be inferred or unresolved.")
        result.append(
            {
                "topic": require_text(record.get("topic"), f"uncertainties[{index}].topic"),
                "status": status,
                "detail": require_text(record.get("detail"), f"uncertainties[{index}].detail"),
            }
        )
    return result


def normalize_validation_evidence(value: object) -> list[JsonObject]:
    if not isinstance(value, list) or not value:
        raise WorkflowError("validation must contain build, test, and run evidence.")
    result: list[JsonObject] = []
    kinds: set[str] = set()
    for index, item in enumerate(value, start=1):
        record = require_object(item, f"validation[{index}]")
        kind = require_text(record.get("kind"), f"validation[{index}].kind")
        status = require_text(record.get("status"), f"validation[{index}].status")
        if kind not in {"build", "test", "run"}:
            raise WorkflowError(f"validation[{index}].kind must be build, test, or run.")
        if status not in {"passed", "failed", "skipped"}:
            raise WorkflowError(f"validation[{index}].status must be passed, failed, or skipped.")
        kinds.add(kind)
        result.append(
            {
                "kind": kind,
                "command": require_text(record.get("command"), f"validation[{index}].command"),
                "status": status,
                "summary": require_text(record.get("summary"), f"validation[{index}].summary"),
                "duration": require_text(record.get("duration"), f"validation[{index}].duration"),
            }
        )
    missing = {"build", "test", "run"} - kinds
    if missing:
        raise WorkflowError(f"validation is missing evidence kind(s): {', '.join(sorted(missing))}.")
    return result


def normalize_analysis_evidence(value: object, inventory: set[str], changed_files: list[str]) -> JsonObject:
    data = require_object(value, "submit_brief.data.analysis_evidence")
    if data.get("pass1_inventory_complete") is not True:
        raise WorkflowError("analysis_evidence.pass1_inventory_complete must be true.")
    pass2 = require_object(data.get("pass2"), "analysis_evidence.pass2")
    normalized_pass2: JsonObject = {}
    for category in ("entrypoints", "configuration", "core_modules", "tests"):
        paths = normalize_string_list(pass2.get(category), f"analysis_evidence.pass2.{category}")
        invalid = [path for path in paths if path not in inventory and not path.startswith("(none")]
        if invalid:
            raise WorkflowError(f"analysis_evidence.pass2.{category} references unknown files: {', '.join(invalid)}")
        normalized_pass2[category] = paths
    pass3 = require_object(data.get("pass3"), "analysis_evidence.pass3")
    raw_summaries = pass3.get("module_summaries")
    if not isinstance(raw_summaries, list) or not raw_summaries:
        raise WorkflowError("analysis_evidence.pass3.module_summaries must be non-empty.")
    module_summaries: list[JsonObject] = []
    for index, item in enumerate(raw_summaries, start=1):
        summary = require_object(item, f"analysis_evidence.pass3.module_summaries[{index}]")
        module_summaries.append(
            {
                "module": require_text(summary.get("module"), f"module_summaries[{index}].module"),
                "summary": require_text(summary.get("summary"), f"module_summaries[{index}].summary"),
            }
        )
    reread_files = normalize_string_list(pass3.get("reread_files"), "analysis_evidence.pass3.reread_files")
    invalid_reread = [path for path in reread_files if path not in inventory and not path.startswith("(none")]
    if invalid_reread:
        raise WorkflowError(f"analysis_evidence.pass3.reread_files references unknown files: {', '.join(invalid_reread)}")
    reviewed_changed_files = normalize_optional_list(data.get("reviewed_changed_files"))
    if reviewed_changed_files != changed_files:
        raise WorkflowError(
            "analysis_evidence.reviewed_changed_files must exactly match project.changed_files for this refresh."
        )
    return {
        "pass1_inventory_complete": True,
        "pass2": normalized_pass2,
        "pass3": {
            "synthesis": require_text(pass3.get("synthesis"), "analysis_evidence.pass3.synthesis"),
            "module_summaries": module_summaries,
            "reread_files": reread_files,
        },
        "reviewed_changed_files": reviewed_changed_files,
    }


def action_submit_brief(root: Path, state: State, data: JsonObject) -> State:
    mode = str(data.get("mode") or "").strip()
    brief_status = str(state.get("project_brief_status") or "machine_detected")
    expected_mode = "cycle_refresh" if brief_status == "refresh_required" else "initial"
    if brief_status == "complete":
        expected_mode = "correction"
    if mode != expected_mode:
        raise WorkflowError(f"submit_brief mode must be {expected_mode} while brief_status={brief_status}.")
    if brief_status == "refresh_required":
        current_changes = changed_project_files(state)
        if current_changes != list(state.get("project_changed_files", [])):
            raise WorkflowError("Project files changed again after cycle scan. Rerun /mw-cycle before submit_brief.")

    project_root = Path(str(state.get("project_root") or root.parent))
    detected = detect_project(project_root)
    inventory = list(detected["inventory"])
    inventory_set = set(inventory)
    positioning = normalize_positioning(data.get("positioning"))
    architecture = normalize_brief_architecture(data.get("architecture"), inventory_set)
    ledger = normalize_file_ledger(data.get("file_ledger"), inventory)
    uncertainties = normalize_uncertainties(data.get("uncertainties"))
    validation = normalize_validation_evidence(data.get("validation"))
    analysis_evidence = normalize_analysis_evidence(
        data.get("analysis_evidence"), inventory_set, list(state.get("project_changed_files", []))
    )

    apply_project_detection(state, detected)
    state["project_positioning"] = positioning
    state["project_architecture"] = architecture
    state["project_file_ledger"] = ledger
    state["project_uncertainties"] = uncertainties
    state["project_validation"] = validation
    state["project_analysis_evidence"] = analysis_evidence
    state["project_changed_files"] = []
    state["project_brief_status"] = "complete"
    state["project_brief_version"] = parse_int(state.get("project_brief_version"), 0) + 1
    state["project_brief_updated_at"] = now_iso()
    state["project_brief_cycle"] = str(state.get("cycle", "C0"))
    state["updated_at"] = now_iso()
    write_project_brief(root, state)
    append_log(
        root,
        f"submitted project brief mode={mode} version={state['project_brief_version']} files={len(ledger)}",
    )
    return state


def action_update_state(root: Path, state: State, data: JsonObject) -> State:
    phase = str(data.get("phase") or "PLANNED").upper()
    if phase != "PLANNED":
        raise WorkflowError("update_state must move the workflow to PLANNED. Only /mw-run may start execution.")
    if any(key in data for key in ("confirmed", "confirmation")):
        raise WorkflowError("update_state must not declare plan confirmation; /mw-run confirms the frozen plan.")
    if state.get("interview_status") != "draft_ready":
        raise WorkflowError("update_state requires a completed interview and a draft plan ready to freeze.")
    clarifications = normalize_optional_list(data.get("clarifications"))
    expected_clarifications = interview_clarifications(state)
    if not clarifications:
        raise WorkflowError("update_state requires data.clarifications covering every interview round and default.")
    if clarifications != expected_clarifications:
        raise WorkflowError("update_state data.clarifications must exactly match the persisted interview record.")
    milestones = normalize_milestones(data.get("milestones"))
    draft = state_draft_milestones(state)
    if milestone_plan_signature(milestones) != milestone_plan_signature(draft):
        raise WorkflowError("update_state milestones must exactly match the user-reviewed draft_milestones.")
    state["final_plan_confirmed"] = False
    state["interview_status"] = "plan_ready"
    state["clarifications"] = clarifications
    state["milestones"] = milestones
    state["current_milestone_id"] = milestones[0]["id"]
    clear_run_grant(state)
    refresh_progress(state)
    set_phase(state, root, "PLANNED", "envelope: update_state; plan ready")
    append_log(root, f"finalized plan milestones={len(milestones)} awaiting=/mw-run")
    return state


def action_reopen_plan(root: Path, state: State, data: JsonObject) -> State:
    feedback = normalize_optional_list(data.get("feedback"))
    state["draft_milestones"] = copy.deepcopy(state_milestones(state))
    state["milestones"] = []
    state["interview_status"] = "draft_ready"
    state["final_plan_confirmed"] = False
    state["current_milestone_id"] = ""
    clear_run_grant(state)
    clear_execution_lease(state)
    refresh_progress(state)
    set_phase(state, root, "PLANNING", "envelope: reopen_plan")
    if feedback:
        append_log(root, f"reopened plan feedback={normalize_error_text(' | '.join(feedback), 160)}")
    else:
        append_log(root, "reopened plan")
    return state


def action_start_execution(root: Path, state: State, data: JsonObject) -> State:
    token = str(data.get("token") or "")
    fingerprint = consume_run_grant(state, token, "start")
    if state.get("final_plan_confirmed") or state.get("interview_status") != "plan_ready":
        raise WorkflowError("start_execution requires an unconfirmed plan_ready state.")
    pending = first_pending_milestone(state)
    if not pending:
        raise WorkflowError("start_execution requires at least one pending milestone.")
    state["final_plan_confirmed"] = True
    state["interview_status"] = "complete"
    state["started_at"] = state.get("started_at") or now_iso()
    state["current_milestone_id"] = pending["id"]
    refresh_progress(state)
    acquire_execution_lease(state)
    set_phase(state, root, "EXECUTING", "/mw-run: start_execution")
    sync_execution_lease(state)
    append_log(root, f"consumed /mw-run grant purpose=start fingerprint={fingerprint}")
    append_log(root, f"started execution run={state['lease_run_id']} milestone={pending['id']}")
    return state


def action_resume_execution(root: Path, state: State, data: JsonObject) -> State:
    if state.get("status") != "stopped":
        raise WorkflowError("resume_execution requires status=stopped.")
    token = str(data.get("token") or "")
    fingerprint = consume_run_grant(state, token, "resume")
    resume_execution_lease(state)
    state["status"] = "running"
    state["updated_at"] = now_iso()
    sync_prompt_for_phase(state, root)
    append_log(root, f"consumed /mw-run grant purpose=resume fingerprint={fingerprint}")
    append_log(root, f"resumed execution run={state['lease_run_id']} phase={state['phase']}")
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
    sync_execution_lease(state)
    append_log(root, f"marked {milestone_id} done")
    return state


def action_set_phase(root: Path, state: State, data: JsonObject) -> State:
    phase = str(data.get("phase") or "").upper()
    if not phase:
        raise WorkflowError("set_phase requires data.phase.")
    if phase not in {"EXECUTING", "PLANNING", "FINISHED"}:
        raise WorkflowError("REVIEWING set_phase may target only EXECUTING, PLANNING, or FINISHED.")
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
        clear_run_grant(state)
        release_execution_lease(state)
    elif phase == "PLANNING":
        clear_run_grant(state)
        release_execution_lease(state)
        reset_planning_session(state, root)
    elif phase not in VALID_PHASES:
        raise WorkflowError(f"Invalid phase: {phase}.")

    refresh_progress(state)
    set_phase(state, root, phase, "envelope: set_phase")
    sync_execution_lease(state)
    return state


def action_record_error(root: Path, state: State, data: JsonObject) -> State:
    state["last_error"] = {
        "command": normalize_error_text(data.get("command", ""), 200),
        "stderr": normalize_error_text(data.get("stderr", ""), 500),
        "returncode": normalize_error_text(data.get("returncode", ""), 40),
        "created_at": now_iso(),
    }
    set_phase(state, root, "DEBUGGING", "envelope: record_error")
    sync_execution_lease(state)
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
    sync_execution_lease(state)
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
    cycle = read_state(root).get("cycle", "C0") if (root / "state.yaml").exists() else "C0"
    reports = root / REPORTS_DIR / str(cycle)
    reports.mkdir(parents=True, exist_ok=True)
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


def next_cycle_id(cycle_id: str) -> str:
    match = re.fullmatch(r"C([0-9]+)", cycle_id.strip())
    if not match:
        return "C1"
    return f"C{int(match.group(1)) + 1}"


def make_readonly(path: Path) -> None:
    for item in path.rglob("*"):
        if item.is_file():
            item.chmod(0o444)
        elif item.is_dir():
            item.chmod(0o555)
    path.chmod(0o555)


def remove_tree(path: Path) -> None:
    if not path.exists():
        return
    for item in path.rglob("*"):
        try:
            if item.is_dir():
                item.chmod(0o755)
            else:
                item.chmod(0o644)
        except OSError:
            pass
    path.chmod(0o755)
    shutil.rmtree(path)


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
    try:
        return require_json_object(payload)
    except EnvelopeError as exc:
        raise SystemExit(str(exc)) from exc


def parse_json_payload(raw: str) -> object:
    try:
        return parse_runtime_json_payload(raw)
    except EnvelopeError as exc:
        raise SystemExit(str(exc)) from exc


def seed_core_prompts(root: Path, overwrite: bool = False) -> int:
    source_dir = skill_root() / WORKFLOW_DIR / PROMPTS_DIR
    target_dir = root / PROMPTS_DIR
    if not source_dir.exists():
        return 0
    count = 0
    for source in sorted(source_dir.glob("mw-*.md"), key=prompt_sort_key):
        target = target_dir / source.name
        if target.exists() and not overwrite:
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
    build_commands: list[str] = []
    test_commands: list[str] = []
    run_commands: list[str] = []
    names = {path.name for path in files}
    suffixes = {path.suffix for path in files}
    if ".py" in suffixes or {"pyproject.toml", "requirements.txt", "setup.py"} & names:
        tech_stack.append("python")
        test_commands.append("pytest")
        if {"pyproject.toml", "setup.py"} & names:
            build_commands.append("python -m build")
        if "main.py" in names:
            run_commands.append("python main.py")
        if "__main__.py" in names:
            run_commands.append("python -m <package>")
    if "package.json" in names:
        tech_stack.append("node")
        test_commands.append("npm test")
        package_path = next((path for path in files if path.name == "package.json"), None)
        package_scripts: dict[str, object] = {}
        if package_path:
            try:
                package_data = json.loads(package_path.read_text(encoding="utf-8"))
                if isinstance(package_data, dict) and isinstance(package_data.get("scripts"), dict):
                    package_scripts = package_data["scripts"]
            except (OSError, UnicodeDecodeError, json.JSONDecodeError):
                package_scripts = {}
        if "build" in package_scripts:
            build_commands.append("npm run build")
        if "start" in package_scripts:
            run_commands.append("npm start")
    if "go.mod" in names:
        tech_stack.append("go")
        build_commands.append("go build ./...")
        test_commands.append("go test ./...")
        run_commands.append("go run .")
    if "Cargo.toml" in names:
        tech_stack.append("rust")
        build_commands.append("cargo build")
        test_commands.append("cargo test")
        run_commands.append("cargo run")
    if "CMakeLists.txt" in names:
        tech_stack.append("cmake")
        build_commands.append("cmake -S . -B build && cmake --build build")
    if not tech_stack:
        tech_stack.append("unknown")
    inventory = [str(path.relative_to(project_root)) for path in files] or [EMPTY_PROJECT_SENTINEL]
    return {
        "root": str(project_root),
        "structure": list(inventory),
        "tech_stack": tech_stack,
        "build_commands": build_commands or ["no build command detected"],
        "test_commands": test_commands or ["manual validation"],
        "run_commands": run_commands or ["no run command detected"],
        "inventory": inventory,
        "fingerprints": fingerprint_records(project_root, files),
    }


def apply_project_detection(state: State, detected: dict[str, object]) -> None:
    inventory = list(detected["inventory"])
    state["project_root"] = str(detected["root"])
    state["project_structure"] = list(inventory)
    state["project_inventory"] = list(inventory)
    state["project_tech_stack"] = list(detected["tech_stack"])
    state["project_build_commands"] = list(detected["build_commands"])
    state["project_test_commands"] = list(detected["test_commands"])
    state["project_run_commands"] = list(detected["run_commands"])
    state["project_fingerprints"] = list(detected["fingerprints"])


def read_maryignore(project_root: Path) -> list[str]:
    ignore_path = project_root / ".maryignore"
    if not ignore_path.exists():
        return []
    try:
        lines = ignore_path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeDecodeError):
        return []
    return [line.strip() for line in lines if line.strip() and not line.lstrip().startswith("#")]


def configured_init_ignore_globs(project_root: Path) -> list[str]:
    root = workflow_root(project_root)
    configured = read_config(root).get("init_ignore", DEFAULT_INIT_IGNORE_GLOBS)
    globs = configured if isinstance(configured, list) else DEFAULT_INIT_IGNORE_GLOBS
    return list(dict.fromkeys([str(item).strip() for item in globs if str(item).strip()] + read_maryignore(project_root)))


def matches_init_ignore(relative_path: str, patterns: list[str]) -> bool:
    normalized = relative_path.replace(os.sep, "/").strip("/")
    for raw_pattern in patterns:
        pattern = raw_pattern.replace("\\", "/").strip().strip("/")
        if not pattern or pattern.startswith("!"):
            continue
        if pattern.endswith("/**"):
            base = pattern[:-3].rstrip("/")
            if normalized == base or normalized.startswith(f"{base}/"):
                return True
        if fnmatchcase(normalized, pattern):
            return True
        if "/" not in pattern and any(fnmatchcase(part, pattern) for part in normalized.split("/")):
            return True
    return False


def list_project_files(project_root: Path, ignore_globs: list[str] | None = None) -> list[Path]:
    patterns = configured_init_ignore_globs(project_root) if ignore_globs is None else ignore_globs
    result: list[Path] = []
    for current_root, directory_names, file_names in os.walk(project_root, topdown=True, followlinks=False):
        current = Path(current_root)
        directory_names[:] = sorted(
            name
            for name in directory_names
            if name not in IGNORED_PROJECT_PARTS
            and not (current / name).is_symlink()
            and not matches_init_ignore(str((current / name).relative_to(project_root)), patterns)
        )
        for name in sorted(file_names):
            path = current / name
            relative_path = str(path.relative_to(project_root))
            if path.is_symlink() or matches_init_ignore(relative_path, patterns) or is_binary_file(path):
                continue
            result.append(path)
    return result


def is_binary_file(path: Path) -> bool:
    if path.suffix.lower() in BINARY_SUFFIXES:
        return True
    try:
        with path.open("rb") as handle:
            probe = handle.read(8192)
    except OSError:
        return True
    if b"\x00" in probe:
        return True
    if not probe:
        return False
    control_bytes = sum(1 for byte in probe if byte < 9 or 13 < byte < 32)
    return control_bytes / len(probe) > 0.20


def fingerprint_records(project_root: Path, files: list[Path] | None = None) -> list[JsonObject]:
    records: list[JsonObject] = []
    for path in files if files is not None else list_project_files(project_root):
        try:
            digest = hashlib.sha256()
            with path.open("rb") as handle:
                while chunk := handle.read(1024 * 1024):
                    digest.update(chunk)
        except OSError:
            continue
        records.append({"path": str(path.relative_to(project_root)), "sha256": digest.hexdigest()})
    return records


def changed_project_files(state: State) -> list[str]:
    project_root = Path(str(state.get("project_root") or "."))
    current = {item["path"]: item["sha256"] for item in fingerprint_records(project_root)}
    previous = {
        str(item.get("path")): str(item.get("sha256"))
        for item in state.get("project_fingerprints", [])
        if isinstance(item, dict) and item.get("path")
    }
    changes: list[str] = []
    for path in sorted(current.keys() - previous.keys()):
        changes.append(f"added:{path}")
    for path in sorted(previous.keys() - current.keys()):
        changes.append(f"deleted:{path}")
    for path in sorted(current.keys() & previous.keys()):
        if current[path] != previous[path]:
            changes.append(f"modified:{path}")
    return changes


def read_config(root: Path) -> dict[str, Any]:
    config: dict[str, Any] = {
        "language": "zh",
        "plan_interview": "on",
        "plan_interview_max_rounds": "3",
        "plan_questions_per_round": "3-5",
        "init_ignore": list(DEFAULT_INIT_IGNORE_GLOBS),
    }
    config_path = root / "config.yaml"
    if not config_path.exists():
        return config
    section = ""
    subsection = ""
    found_init_ignore = False
    for raw_line in config_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.rstrip()
        if not line or line.lstrip().startswith("#"):
            continue
        if not line.startswith(" ") and line.endswith(":"):
            section = line[:-1]
            subsection = ""
            continue
        init_ignore = re.match(r"^\s{2}ignore:\s*(.*)$", line) if section == "init" else None
        if init_ignore:
            raw_ignore = init_ignore.group(1).strip()
            subsection = "ignore" if not raw_ignore else ""
            config["init_ignore"] = []
            found_init_ignore = True
            if raw_ignore:
                try:
                    inline_patterns = json.loads(raw_ignore)
                except json.JSONDecodeError:
                    inline_patterns = None
                if not isinstance(inline_patterns, list) or not all(isinstance(item, str) for item in inline_patterns):
                    raise SystemExit("config.yaml init.ignore must be a YAML list or an inline JSON string list.")
                config["init_ignore"] = inline_patterns
            continue
        if section == "init" and subsection == "ignore":
            item = re.match(r"^\s{4}-\s*(.*)$", line)
            if item:
                value = parse_scalar(item.group(1))
                if value:
                    config["init_ignore"].append(value)
                continue
        key_value = match_key_value(line, indent=2)
        if not key_value:
            continue
        key, value = key_value
        if section == "output" and key == "language":
            config["language"] = value or "zh"
        elif section == "plan" and key == "interview":
            config["plan_interview"] = value or "on"
        elif section == "plan" and key in {"interview.max_rounds", "max_rounds"}:
            config["plan_interview_max_rounds"] = value or "3"
        elif section == "plan" and key in {"interview.questions_per_round", "questions_per_round"}:
            config["plan_questions_per_round"] = value or "3-5"
        elif section == "plan" and key == "max_questions":
            config["plan_questions_per_round"] = f"3-{value or '5'}"
    if not found_init_ignore:
        config["init_ignore"] = list(DEFAULT_INIT_IGNORE_GLOBS)
    return config


def write_config(
    root: Path,
    language: str = "zh",
    plan_interview: str = "on",
    plan_interview_max_rounds: str = "3",
    plan_questions_per_round: str = "3-5",
    init_ignore: list[str] | None = None,
) -> None:
    config_path = root / "config.yaml"
    if not config_path.exists():
        ignore_patterns = DEFAULT_INIT_IGNORE_GLOBS if init_ignore is None else init_ignore
        config_path.write_text(
            "workflow:\n"
            "  name: Mary Workflow\n"
            "  prompt_glob: prompts/*.md\n"
            "output:\n"
            f"  language: {language}\n"
            "plan:\n"
            f"  interview: {plan_interview}\n"
            f"  interview.max_rounds: {plan_interview_max_rounds}\n"
            f"  interview.questions_per_round: {quote_value(plan_questions_per_round)}\n"
            "init:\n"
            "  ignore:\n"
            + "".join(f"    - {quote_value(pattern)}\n" for pattern in ignore_patterns),
            encoding="utf-8",
        )


def ensure_init_ignore_config(root: Path) -> None:
    config_path = root / "config.yaml"
    if not config_path.exists():
        write_config(root)
        return
    text = config_path.read_text(encoding="utf-8")
    lines = text.splitlines()
    init_index = next((index for index, line in enumerate(lines) if re.match(r"^init:\s*$", line)), None)
    ignore_lines = ["  ignore:", *(f"    - {quote_value(pattern)}" for pattern in DEFAULT_INIT_IGNORE_GLOBS)]
    if init_index is None:
        separator = [""] if lines and lines[-1] else []
        config_path.write_text("\n".join([*lines, *separator, "init:", *ignore_lines]) + "\n", encoding="utf-8")
        return
    section_end = next(
        (index for index in range(init_index + 1, len(lines)) if lines[index] and not lines[index].startswith(" ")),
        len(lines),
    )
    if any(re.match(r"^\s{2}ignore:\s*", line) for line in lines[init_index + 1 : section_end]):
        return
    lines[section_end:section_end] = ignore_lines
    config_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def update_config(root: Path, language: str | None = None, plan_interview: str | None = None) -> None:
    config = read_config(root)
    if language is not None:
        config["language"] = language
    if plan_interview is not None:
        config["plan_interview"] = plan_interview
    (root / "config.yaml").write_text(
        "workflow:\n"
        "  name: Mary Workflow\n"
        "  prompt_glob: prompts/*.md\n"
        "output:\n"
        f"  language: {config['language']}\n"
        "plan:\n"
        f"  interview: {config['plan_interview']}\n"
        f"  interview.max_rounds: {config['plan_interview_max_rounds']}\n"
        f"  interview.questions_per_round: {quote_value(config['plan_questions_per_round'])}\n"
        "init:\n"
        "  ignore:\n"
        + "".join(f"    - {quote_value(pattern)}\n" for pattern in config["init_ignore"]),
        encoding="utf-8",
    )


def write_project_brief(root: Path, state: State) -> None:
    brief_path = root / BRIEF_FILE
    ignore_globs = configured_init_ignore_globs(Path(str(state.get("project_root") or root.parent)))
    positioning = state.get("project_positioning") if isinstance(state.get("project_positioning"), dict) else {}
    architecture = state.get("project_architecture") if isinstance(state.get("project_architecture"), dict) else {}
    analysis = (
        state.get("project_analysis_evidence") if isinstance(state.get("project_analysis_evidence"), dict) else {}
    )
    pending = "（等待 `submit_brief` 全量理解结果）"
    lines = [
        "# 项目理解简报",
        "",
        f"- 简报版本：{state.get('project_brief_version', 0)}",
        f"- 简报状态：`{state.get('project_brief_status', 'machine_detected')}`",
        f"- 最近更新时间：{state.get('project_brief_updated_at') or now_iso()}",
        f"- 最近理解 cycle：`{state.get('project_brief_cycle', state.get('cycle', 'C0'))}`",
        f"- 项目根目录：`{state.get('project_root', '')}`",
        f"- 当前 cycle：`{state.get('cycle', 'C0')}`",
        f"- 输出语言：`{state.get('project_language', 'zh')}`",
        "",
        "## 1. 机器探测区",
        "",
        "### 技术栈",
        *(f"- {item}" for item in state.get("project_tech_stack", [])),
        "",
        "### 候选构建命令",
        *(f"- `{item}`" for item in state.get("project_build_commands", [])),
        "",
        "### 候选测试命令",
        *(f"- `{item}`" for item in state.get("project_test_commands", [])),
        "",
        "### 候选运行命令",
        *(f"- `{item}`" for item in state.get("project_run_commands", [])),
        "",
        "### Inventory 排除规则",
        *(f"- `{item}`" for item in ignore_globs),
        "" if ignore_globs else "- （无）",
        "",
        f"### 全量文本文件清单（{len(state.get('project_inventory', []))}）",
        *(f"- `{item}`" for item in state.get("project_inventory", [])),
        "",
        "### 三遍理解证据",
        "",
        "```json",
        json.dumps(analysis or {"status": pending}, ensure_ascii=False, indent=2),
        "```",
        "",
        "### 构建、测试与运行复现",
        "",
    ]
    validation = [item for item in state.get("project_validation", []) if isinstance(item, dict)]
    if validation:
        lines.extend(
            f"- **{item.get('kind', '')}** `{item.get('command', '')}` → `{item.get('status', '')}`，"
            f"耗时 {item.get('duration', '')}；{item.get('summary', '')}"
            for item in validation
        )
    else:
        lines.append(f"- {pending}")
    lines.extend(
        [
            "",
            "## 2. 项目定位",
            "",
            f"- **做什么**：{positioning.get('purpose', pending)}",
            f"- **给谁用**：{positioning.get('audience', pending)}",
            f"- **解决的问题**：{positioning.get('problem', pending)}",
            f"- **与同类差异**：{positioning.get('differentiators', pending)}",
            "",
            "## 3. 架构全景",
            "",
            "### 模块与职责",
            "",
        ]
    )
    modules = architecture.get("modules", []) if isinstance(architecture, dict) else []
    if modules:
        for module in modules:
            files = ", ".join(f"`{item}`" for item in module.get("files", []))
            lines.append(f"- **{module.get('name', '')}**：{module.get('responsibility', '')}；文件：{files}")
    else:
        lines.append(f"- {pending}")
    lines.extend(["", "### 依赖方向邻接表", ""])
    dependencies = architecture.get("dependency_graph", []) if isinstance(architecture, dict) else []
    if dependencies:
        lines.extend(f"- {item}" for item in dependencies)
    else:
        lines.append(f"- {pending}")
    lines.extend(["", "### 关键数据流", ""])
    data_flow = architecture.get("data_flow", []) if isinstance(architecture, dict) else []
    if data_flow:
        lines.extend(f"{index}. {item}" for index, item in enumerate(data_flow, start=1))
    else:
        lines.append(f"- {pending}")
    lines.extend(["", "### 状态存储与修改者", ""])
    state_flow = architecture.get("state_management", []) if isinstance(architecture, dict) else []
    if state_flow:
        lines.extend(f"- {item}" for item in state_flow)
    else:
        lines.append(f"- {pending}")
    lines.extend(["", "## 4. 文件级账本", ""])
    ledger = [item for item in state.get("project_file_ledger", []) if isinstance(item, dict)]
    if ledger:
        for item in ledger:
            exports = ", ".join(item.get("exports", []))
            used_by = ", ".join(item.get("used_by", []))
            lines.append(
                f"- `{item.get('path', '')}` — {item.get('purpose', '')}；导出：{exports}；被使用：{used_by}"
            )
    else:
        lines.append(f"- {pending}")
    lines.extend(["", "## 5. 不确定性清单", ""])
    uncertainties = [item for item in state.get("project_uncertainties", []) if isinstance(item, dict)]
    if uncertainties:
        for item in uncertainties:
            lines.append(f"- **[{item.get('status', '')}] {item.get('topic', '')}**：{item.get('detail', '')}")
    else:
        lines.append(f"- {pending}")
    changed = list(state.get("project_changed_files", []))
    if changed:
        lines.extend(["", "## 待增量重读", ""])
        lines.extend(f"- `{item}`" for item in changed)
    lines.extend(
        [
            "",
            "## 修正方式",
            "",
            "如果理解不准确，请指出证据；机器探测字段用 `update_project` 修正，理解正文用 `submit_brief` 重交。",
        ]
    )
    brief_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def cmd_init(args: argparse.Namespace) -> int:
    root = workflow_root(Path.cwd())
    if args.reset and root.exists():
        remove_tree(root)
    elif (root / "state.yaml").exists():
        state_text = (root / "state.yaml").read_text(encoding="utf-8")
        version_pattern = rf"^version:\s*{re.escape(STATE_VERSION)}\s*$"
        if not re.search(version_pattern, state_text, flags=re.MULTILINE):
            raise SystemExit("Existing Mary Workflow state is not v2.1. Run /mw-init --reset to recreate it.")
        (root / PROMPTS_DIR).mkdir(exist_ok=True)
        (root / ANALYSIS_DIR).mkdir(exist_ok=True)
        ensure_init_ignore_config(root)
        refreshed = seed_core_prompts(root, overwrite=True)
        state = read_state(root)
        state_changed = False
        phase = str(state.get("phase") or "PLANNING")
        brief_status = str(state.get("project_brief_status") or "machine_detected")
        skipped_active_check = phase not in BRIEF_REFRESH_PHASES
        if brief_status == "complete" and not skipped_active_check:
            changed_files = changed_project_files(state)
            if changed_files:
                state["project_brief_status"] = "refresh_required"
                state["project_changed_files"] = changed_files
                state["updated_at"] = now_iso()
                write_state(root, state)
                write_project_brief(root, state)
                state_changed = True
        elif brief_status == "machine_detected" and not skipped_active_check:
            apply_project_detection(state, detect_project(Path(str(state.get("project_root") or Path.cwd()))))
            state["updated_at"] = now_iso()
            write_state(root, state)
            write_project_brief(root, state)
        append_log(root, f"refreshed {refreshed} core prompts")
        if skipped_active_check:
            suffix = f"当前阶段为 {phase}，运行中，跳过简报漂移检查。"
            append_log(root, f"skipped project brief drift check phase={phase}")
        elif state_changed:
            suffix = "检测到项目变化，brief 已进入 refresh_required。"
        elif brief_status == "machine_detected":
            suffix = "已按当前 init.ignore 与 .maryignore 刷新机器探测。"
        else:
            suffix = "state 保持不变。"
        print(f"Mary Workflow 已初始化，已刷新 {refreshed} 个核心 prompt；{suffix}")
        print_status(state, read_config(root).get("language", "zh"))
        print("下一步：渲染 /mw-init 理解上下文；简报 complete 后才能运行 /mw-plan。")
        return 0

    root.mkdir(exist_ok=True)
    (root / PROMPTS_DIR).mkdir(exist_ok=True)
    (root / REPORTS_DIR).mkdir(exist_ok=True)
    (root / ANALYSIS_DIR).mkdir(exist_ok=True)
    write_config(root, language="zh")

    seeded = seed_core_prompts(root)
    examples = write_example_prompts(root) if args.with_examples else 0
    prompts = prompt_files(root)

    state = default_state(Path.cwd())
    config = read_config(root)
    state["project_language"] = config.get("language", "zh")
    state["interview_max_rounds"] = configured_interview_max_rounds(root)
    state["phase"] = "PLANNING"
    state["status"] = "idle"
    sync_prompt_for_phase(state, root)
    refresh_progress(state)
    write_state(root, state)
    write_project_brief(root, state)
    append_log(root, "initialized workflow v2.1")

    print(f"已初始化 {WORKFLOW_DIR} v2.1，写入 {len(prompts)} 个 prompt。")
    print(f"项目理解简报：{root / BRIEF_FILE}")
    print("机器探测骨架已生成；接下来必须完成三遍全量理解并提交 submit_brief。")
    print("后续 plan/run 默认使用中文。若希望改为 auto 或 en，请告诉我，我会写入 config.yaml 的 output.language。")
    print("下一步：继续 /mw-init 理解流程；简报 complete 后再运行 /mw-plan。")
    if seeded:
        print(f"Seeded {seeded} core prompt(s).")
    if examples:
        print(f"Seeded {examples} example prompt(s).")
    return 0


def cmd_cycle(args: argparse.Namespace) -> int:
    root = require_root(Path.cwd())
    state = read_state(root)
    brief_status = str(state.get("project_brief_status") or "machine_detected")
    if brief_status not in {"complete", "refresh_required"}:
        raise SystemExit("Project brief is incomplete. Finish /mw-init and submit_brief before /mw-cycle.")
    changed_files = changed_project_files(state)
    if changed_files:
        state["project_brief_status"] = "refresh_required"
        state["project_changed_files"] = changed_files
        state["updated_at"] = now_iso()
        write_state(root, state)
        write_project_brief(root, state)
        append_log(root, f"project brief refresh required files={len(changed_files)}")
        print("检测到本 cycle 的项目文件变化，归档已暂停。")
        for item in changed_files:
            print(f"- {item}")
        print("请按 /mw-init 的增量重读流程提交 submit_brief mode=cycle_refresh，然后再次运行 /mw-cycle。")
        return 0
    if brief_status == "refresh_required":
        state["project_brief_status"] = "complete"
        state["project_changed_files"] = []

    old_cycle = str(state.get("cycle") or "C0")
    new_cycle = next_cycle_id(old_cycle)
    archive = root / CYCLES_DIR / old_cycle
    if archive.exists():
        raise SystemExit(f"Cycle archive already exists: {archive}")
    archive.mkdir(parents=True)

    for name in ("state.yaml", "log.md", BRIEF_FILE):
        source = root / name
        if source.exists():
            shutil.copy2(source, archive / name)

    reports_root = root / REPORTS_DIR
    cycle_reports = reports_root / old_cycle
    if cycle_reports.exists():
        shutil.copytree(cycle_reports, archive / REPORTS_DIR)
    elif reports_root.exists():
        shutil.copytree(reports_root, archive / REPORTS_DIR)
    if reports_root.exists():
        shutil.rmtree(reports_root)
    (root / REPORTS_DIR).mkdir(exist_ok=True)

    analysis_root = root / ANALYSIS_DIR
    if analysis_root.exists():
        shutil.copytree(analysis_root, archive / ANALYSIS_DIR)
        shutil.rmtree(analysis_root)
    analysis_root.mkdir(exist_ok=True)
    make_readonly(archive)

    state["cycle"] = new_cycle
    state["status"] = "idle"
    state["phase"] = "PLANNING"
    state["started_at"] = ""
    state["updated_at"] = now_iso()
    state["current_index"] = 0
    reset_planning_session(state, root)
    state["completed"] = 0
    state["total"] = 0
    clear_execution_lease(state)
    clear_run_grant(state)
    state["last_error"] = {"command": "", "stderr": "", "returncode": "", "created_at": ""}
    state["action_counts"] = {action: 0 for action in all_action_names()}
    state["rejected_actions"] = 0
    state["phase_history"] = []
    sync_prompt_for_phase(state, root)
    write_state(root, state)
    write_project_brief(root, state)
    atomic_write_text(root / "log.md", "# Mary Workflow Log\n\n", encoding="utf-8")
    append_log(root, f"cycle {old_cycle} archived; started {new_cycle}")
    print(f"已归档 {old_cycle} 到 {archive}")
    print(f"已开启 {new_cycle}。下一步：/mw-plan")
    return 0


def cmd_status(args: argparse.Namespace) -> int:
    root = require_root(Path.cwd())
    state = read_state(root)
    print_status(state, read_config(root).get("language", "zh"))
    return 0


def cmd_apply_action(args: argparse.Namespace) -> int:
    root = require_root(Path.cwd())
    payload = load_json_payload(args)
    state = apply_action(root, payload)
    if payload.get("action") == "submit_brief":
        print((root / BRIEF_FILE).read_text(encoding="utf-8"))
        return 0
    print_status(state, read_config(root).get("language", "zh"))
    return 0


def cmd_stop(args: argparse.Namespace) -> int:
    root = require_root(Path.cwd())
    state = read_state(root)
    if state.get("phase") == "FINISHED":
        raise SystemExit("Mary Workflow is already FINISHED.")
    clear_run_grant(state)
    if state.get("phase") in {"EXECUTING", "REVIEWING", "DEBUGGING"}:
        pause_execution_lease(state)
    state["status"] = "stopped"
    state["updated_at"] = now_iso()
    write_state(root, state)
    append_log(root, "stopped workflow")
    print_status(state, read_config(root).get("language", "zh"))
    return 0


def print_status(state: State, language: str = "zh") -> None:
    milestone = current_milestone(state)
    milestone_id = milestone["id"] if milestone else "(none)"
    if language == "en":
        print_status_en(state, milestone, milestone_id)
    else:
        print_status_zh(state, milestone, milestone_id)


def print_status_en(state: State, milestone: Milestone | None, milestone_id: str) -> None:
    print(f"version: {state['version']}")
    print(f"cycle: {state.get('cycle', 'C0')}")
    print(f"status: {state['status']}")
    print(f"phase: {state['phase']}")
    print(f"project_brief_status: {state.get('project_brief_status', 'machine_detected')}")
    print(f"project_brief_version: {state.get('project_brief_version', 0)}")
    print(f"project_inventory_files: {len(state.get('project_inventory', []))}")
    print(f"project_changed_files: {len(state.get('project_changed_files', []))}")
    print(f"interview_status: {state.get('interview_status', 'not_started')}")
    print(f"interview_round: {state.get('interview_round', 0)}/{state.get('interview_max_rounds', 3)}")
    print(f"final_plan_confirmed: {str(bool(state.get('final_plan_confirmed'))).lower()}")
    print(f"draft_milestones: {len(state_draft_milestones(state))}")
    print(f"progress: {state['completed']}/{state['total']}")
    print(f"current_prompt: {state['current_prompt'] or '(none)'}")
    print(f"current_milestone: {milestone_id}")
    print(f"lease_status: {state.get('lease_status', 'none')}")
    print(f"lease_run_id: {state.get('lease_run_id') or '(none)'}")
    print(f"run_grant: {state.get('run_grant_purpose') or '(none)'}")
    if state.get("run_grant_fingerprint"):
        print(f"run_grant_fingerprint: {state['run_grant_fingerprint']}")
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


def print_status_zh(state: State, milestone: Milestone | None, milestone_id: str) -> None:
    print(f"版本: {state['version']}")
    print(f"cycle: {state.get('cycle', 'C0')}")
    print(f"状态: {state['status']}")
    print(f"阶段: {state['phase']}")
    print(f"项目简报状态: {state.get('project_brief_status', 'machine_detected')}")
    print(f"项目简报版本: {state.get('project_brief_version', 0)}")
    print(f"项目 inventory 文件数: {len(state.get('project_inventory', []))}")
    print(f"待增量重读文件数: {len(state.get('project_changed_files', []))}")
    print(f"问答状态: {state.get('interview_status', 'not_started')}")
    print(f"问答轮次: {state.get('interview_round', 0)}/{state.get('interview_max_rounds', 3)}")
    print(f"最终计划已确认: {str(bool(state.get('final_plan_confirmed'))).lower()}")
    print(f"草案 milestone 数: {len(state_draft_milestones(state))}")
    print(f"进度: {state['completed']}/{state['total']}")
    print(f"当前 prompt: {state['current_prompt'] or '(none)'}")
    print(f"当前 milestone: {milestone_id}")
    print(f"lease 状态: {state.get('lease_status', 'none')}")
    print(f"lease run id: {state.get('lease_run_id') or '(none)'}")
    print(f"run grant: {state.get('run_grant_purpose') or '(none)'}")
    if state.get("run_grant_fingerprint"):
        print(f"run grant 指纹: {state['run_grant_fingerprint']}")
    if milestone:
        print(f"标题: {milestone['title']}")
        print(f"gate: {milestone.get('gate', 'auto')}")
    milestones = state_milestones(state)
    if milestones:
        print("milestones:")
        for item in milestones:
            print(f"  - {item['id']} [{item['status']}] scope={item['estimated_scope']} {item['title']}")
    print(f"被拒信封数: {state.get('rejected_actions', 0)}")
    print("action_counts:")
    for action, count in sorted(state.get("action_counts", {}).items()):
        print(f"  {action}: {count}")
    if state.get("phase_history"):
        print("phase_history:")
        for entry in state["phase_history"]:
            print(f"  - {entry}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Mary Workflow v2.1 runtime helper")
    subparsers = parser.add_subparsers(dest="command", required=True)

    init_parser = subparsers.add_parser("init", help="create or reset .mary-workflow")
    init_parser.add_argument("--reset", action="store_true", help="remove and recreate .mary-workflow")
    init_parser.add_argument("--with-examples", action="store_true", help="create two starter prompts")
    init_parser.set_defaults(func=cmd_init)

    subparsers.add_parser("status", help="show status without mutating state").set_defaults(func=cmd_status)
    subparsers.add_parser("cycle", help="archive current cycle and reset active state").set_defaults(func=cmd_cycle)

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
