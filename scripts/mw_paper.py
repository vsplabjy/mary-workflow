#!/usr/bin/env python3
"""Independent paper-pipeline state runtime for Mary Workflow v2.2."""

from __future__ import annotations

import argparse
import copy
from datetime import datetime, timezone
import json
from pathlib import Path, PurePosixPath
import re
import sys
from typing import Any

from mw_runtime import (
    EnvelopeError,
    action_envelope_parts,
    append_log_entry,
    atomic_write_text,
    parse_json_payload,
    require_json_object,
)


RESEARCH_DIR = ".mary-research"
PAPERS_DIR = "papers"
PAPER_STATE_FILE = "state.json"
PAPER_LOG_FILE = "log.md"
PAPER_STATE_SCHEMA = 1
PAPER_LOG_HEADER = "# Mary Paper Log\n\n"

STAGE_ORDER = ("read", "summary", "slides", "quiz")
STAGE_DEPENDENCIES = {
    "read": (),
    "summary": ("read",),
    "slides": ("summary",),
    "quiz": ("read", "summary"),
}
STAGE_STATUSES = {"pending", "in_progress", "complete", "failed", "stale"}
ACTION_NAMES = ("complete_stage", "fail_stage", "reset_stage", "start_stage", "update_source")

PAPER_ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9._-]{0,127}$")
FINGERPRINT_PATTERN = re.compile(r"^[0-9a-f]{64}$")
MODERN_ARXIV_PATTERN = re.compile(r"^\d{4}\.\d{4,5}(?:v\d+)?$", flags=re.IGNORECASE)
LEGACY_ARXIV_PATTERN = re.compile(r"^[a-z][a-z0-9.-]*/\d{7}(?:v\d+)?$", flags=re.IGNORECASE)


JsonObject = dict[str, Any]
PaperState = dict[str, Any]


class PaperError(Exception):
    """A paper state or transition violated the P1 contract."""


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def normalize_fingerprint(value: object, field_name: str = "fingerprint") -> str:
    fingerprint = str(value or "").strip().lower()
    if fingerprint.startswith("sha256:"):
        fingerprint = fingerprint.removeprefix("sha256:")
    if not FINGERPRINT_PATTERN.fullmatch(fingerprint):
        raise PaperError(f"{field_name} must be a 64-character SHA-256 hex digest.")
    return fingerprint


def extract_arxiv_id(value: object) -> str | None:
    text = str(value or "").strip()
    if not text:
        return None
    text = re.sub(r"^arxiv:\s*", "", text, flags=re.IGNORECASE)
    text = re.sub(
        r"^https?://(?:(?:export|www)\.)?arxiv\.org/(?:abs|pdf|html)/",
        "",
        text,
        flags=re.IGNORECASE,
    )
    text = text.split("?", 1)[0].split("#", 1)[0]
    if text.lower().endswith(".pdf"):
        text = text[:-4]
    if MODERN_ARXIV_PATTERN.fullmatch(text) or LEGACY_ARXIV_PATTERN.fullmatch(text):
        return text.lower()
    return None


def normalize_paper_id(value: object) -> str:
    raw = str(value or "").strip()
    arxiv_id = extract_arxiv_id(raw)
    paper_id = f"arxiv-{arxiv_id.replace('/', '-')}" if arxiv_id else raw.lower()
    if not PAPER_ID_PATTERN.fullmatch(paper_id) or ".." in paper_id:
        raise PaperError(
            "paper_id must be 1-128 lowercase letters, digits, dots, underscores, or hyphens "
            "without path separators or '..'."
        )
    return paper_id


def derive_paper_id(source_locator: object, source_fingerprint: object) -> str:
    arxiv_id = extract_arxiv_id(source_locator)
    if arxiv_id:
        return normalize_paper_id(arxiv_id)
    fingerprint = normalize_fingerprint(source_fingerprint, "source fingerprint")
    return f"local-{fingerprint[:16]}"


def require_source_identity(paper_id: str, source_locator: str) -> None:
    arxiv_id = extract_arxiv_id(source_locator)
    if arxiv_id is None:
        return
    expected = normalize_paper_id(arxiv_id)
    if paper_id != expected:
        raise PaperError(
            f"ArXiv source {arxiv_id} requires paper_id {expected}; received {paper_id}. "
            "Create a separate paper workspace for a different arXiv revision."
        )


def papers_root(project_root: Path) -> Path:
    return Path(project_root).resolve() / RESEARCH_DIR / PAPERS_DIR


def paper_directory(project_root: Path, paper_id: object) -> Path:
    return papers_root(project_root) / normalize_paper_id(paper_id)


def paper_state_path(project_root: Path, paper_id: object) -> Path:
    return paper_directory(project_root, paper_id) / PAPER_STATE_FILE


def paper_log_path(project_root: Path, paper_id: object) -> Path:
    return paper_directory(project_root, paper_id) / PAPER_LOG_FILE


def default_stage_state() -> JsonObject:
    return {
        "status": "pending",
        "attempts": 0,
        "input_fingerprints": {},
        "output_fingerprint": "",
        "artifact": "",
        "updated_at": "",
        "error": "",
        "stale_reason": "",
    }


def default_paper_state(paper_id: str, source_locator: str, source_fingerprint: str) -> PaperState:
    timestamp = now_iso()
    return {
        "paper_state_schema": PAPER_STATE_SCHEMA,
        "paper_id": normalize_paper_id(paper_id),
        "created_at": timestamp,
        "updated_at": timestamp,
        "source": {
            "locator": source_locator,
            "fingerprint": normalize_fingerprint(source_fingerprint, "source fingerprint"),
            "updated_at": timestamp,
        },
        "stages": {stage: default_stage_state() for stage in STAGE_ORDER},
        "audit": {
            "action_counts": {action: 0 for action in ACTION_NAMES},
            "rejected_actions": 0,
        },
    }


def normalize_artifact_path(value: object) -> str:
    artifact = str(value or "").strip()
    if not artifact:
        return ""
    path = PurePosixPath(artifact.replace("\\", "/"))
    if path.is_absolute() or ".." in path.parts:
        raise PaperError("artifact must be a relative path inside the paper workspace.")
    return path.as_posix()


def validate_paper_state(state: object, expected_paper_id: str | None = None) -> PaperState:
    if not isinstance(state, dict):
        raise PaperError("Paper state must be a JSON object.")
    if state.get("paper_state_schema") != PAPER_STATE_SCHEMA:
        raise PaperError(
            f"Unsupported paper_state_schema: {state.get('paper_state_schema', 'missing')}. "
            f"Expected {PAPER_STATE_SCHEMA}."
        )

    paper_id = normalize_paper_id(state.get("paper_id"))
    if state.get("paper_id") != paper_id:
        raise PaperError("Paper state paper_id is not canonical.")
    if expected_paper_id is not None and paper_id != normalize_paper_id(expected_paper_id):
        raise PaperError(f"Paper state belongs to {paper_id}, not {expected_paper_id}.")

    for field in ("created_at", "updated_at"):
        if not str(state.get(field) or "").strip():
            raise PaperError(f"Paper state requires non-empty {field}.")

    source = state.get("source")
    if not isinstance(source, dict):
        raise PaperError("Paper state source must be an object.")
    if not str(source.get("locator") or "").strip():
        raise PaperError("Paper state source.locator must be non-empty.")
    require_source_identity(paper_id, str(source["locator"]))
    source["fingerprint"] = normalize_fingerprint(source.get("fingerprint"), "source.fingerprint")
    if not str(source.get("updated_at") or "").strip():
        raise PaperError("Paper state source.updated_at must be non-empty.")

    stages = state.get("stages")
    if not isinstance(stages, dict) or set(stages) != set(STAGE_ORDER):
        raise PaperError(f"Paper state stages must contain exactly: {', '.join(STAGE_ORDER)}.")
    for stage in STAGE_ORDER:
        item = stages.get(stage)
        if not isinstance(item, dict):
            raise PaperError(f"Stage {stage} must be an object.")
        status = str(item.get("status") or "")
        if status not in STAGE_STATUSES:
            raise PaperError(f"Stage {stage} has invalid status: {status or '(missing)'}.")
        attempts = item.get("attempts")
        if not isinstance(attempts, int) or isinstance(attempts, bool) or attempts < 0:
            raise PaperError(f"Stage {stage}.attempts must be a non-negative integer.")
        inputs = item.get("input_fingerprints")
        if not isinstance(inputs, dict):
            raise PaperError(f"Stage {stage}.input_fingerprints must be an object.")
        item["input_fingerprints"] = {
            str(name): normalize_fingerprint(value, f"{stage}.input_fingerprints.{name}")
            for name, value in inputs.items()
        }
        output = str(item.get("output_fingerprint") or "").strip()
        item["output_fingerprint"] = normalize_fingerprint(output, f"{stage}.output_fingerprint") if output else ""
        item["artifact"] = normalize_artifact_path(item.get("artifact"))
        for field in ("updated_at", "error", "stale_reason"):
            if not isinstance(item.get(field), str):
                raise PaperError(f"Stage {stage}.{field} must be a string.")
        if status == "pending" and (inputs or output or item["artifact"]):
            raise PaperError(f"Pending stage {stage} must not retain lineage or artifact fields.")
        if status == "complete" and not item["output_fingerprint"]:
            raise PaperError(f"Complete stage {stage} requires output_fingerprint.")
        if status in {"in_progress", "complete", "failed"}:
            required_inputs = {"source"} if stage == "read" else set(STAGE_DEPENDENCIES[stage])
            if set(item["input_fingerprints"]) != required_inputs:
                raise PaperError(
                    f"Stage {stage} status {status} requires input fingerprints: "
                    f"{', '.join(sorted(required_inputs))}."
                )

    audit = state.get("audit")
    if not isinstance(audit, dict):
        raise PaperError("Paper state audit must be an object.")
    counts = audit.get("action_counts")
    if not isinstance(counts, dict) or set(counts) != set(ACTION_NAMES):
        raise PaperError(f"audit.action_counts must contain exactly: {', '.join(ACTION_NAMES)}.")
    if any(not isinstance(value, int) or isinstance(value, bool) or value < 0 for value in counts.values()):
        raise PaperError("audit.action_counts values must be non-negative integers.")
    rejected = audit.get("rejected_actions")
    if not isinstance(rejected, int) or isinstance(rejected, bool) or rejected < 0:
        raise PaperError("audit.rejected_actions must be a non-negative integer.")

    for stage in STAGE_ORDER:
        item = stages[stage]
        if item["status"] == "complete" and item["input_fingerprints"] != current_input_fingerprints(state, stage):
            raise PaperError(f"Complete stage {stage} has stale input fingerprints but is not marked stale.")
    return state


def write_paper_state(project_root: Path, state: PaperState) -> None:
    validate_paper_state(state)
    state_path = paper_state_path(project_root, state["paper_id"])
    atomic_write_text(state_path, json.dumps(state, ensure_ascii=False, indent=2) + "\n")


def read_paper_state(project_root: Path, paper_id: object) -> PaperState:
    canonical_id = normalize_paper_id(paper_id)
    state_path = paper_state_path(project_root, canonical_id)
    if not state_path.exists():
        raise PaperError(f"Paper {canonical_id} is not registered. Use /mw-paper create first.")
    try:
        payload = json.loads(state_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise PaperError(f"Invalid paper state JSON for {canonical_id}: {exc}") from exc
    return validate_paper_state(payload, canonical_id)


def append_paper_log(project_root: Path, paper_id: str, message: str) -> None:
    append_log_entry(
        paper_log_path(project_root, paper_id),
        message,
        timestamp=now_iso(),
        header=PAPER_LOG_HEADER,
    )


def create_paper(
    project_root: Path,
    source_locator: object,
    source_fingerprint: object,
    paper_id: object | None = None,
) -> tuple[PaperState, bool]:
    locator = str(source_locator or "").strip()
    if not locator:
        raise PaperError("source locator must be non-empty.")
    fingerprint = normalize_fingerprint(source_fingerprint, "source fingerprint")
    canonical_id = normalize_paper_id(paper_id) if paper_id is not None else derive_paper_id(locator, fingerprint)
    require_source_identity(canonical_id, locator)
    directory = paper_directory(project_root, canonical_id)
    if directory.is_symlink():
        raise PaperError(f"Paper workspace must not be a symlink: {directory}")
    if directory.exists() and not directory.is_dir():
        raise PaperError(f"Paper workspace path is not a directory: {directory}")
    state_path = directory / PAPER_STATE_FILE
    if state_path.exists():
        state = read_paper_state(project_root, canonical_id)
        source = state["source"]
        if source["locator"] == locator and source["fingerprint"] == fingerprint:
            return state, False
        raise PaperError(
            f"Paper {canonical_id} already exists with a different source. Use update_source instead of create."
        )

    directory.mkdir(parents=True, exist_ok=True)
    state = default_paper_state(canonical_id, locator, fingerprint)
    write_paper_state(project_root, state)
    append_paper_log(project_root, canonical_id, f"created paper source={locator} fingerprint={fingerprint[:12]}")
    return state, True


def list_paper_ids(project_root: Path) -> list[str]:
    root = papers_root(project_root)
    if not root.exists():
        return []
    return sorted(
        item.name
        for item in root.iterdir()
        if item.is_dir() and not item.is_symlink() and (item / PAPER_STATE_FILE).is_file()
    )


def resolve_paper_id(project_root: Path, paper_id: object | None = None) -> str:
    if paper_id is not None and str(paper_id).strip():
        return normalize_paper_id(paper_id)
    paper_ids = list_paper_ids(project_root)
    if not paper_ids:
        raise PaperError("No papers are registered. Use /mw-paper create first.")
    if len(paper_ids) > 1:
        raise PaperError("Multiple papers are registered; specify paper_id explicitly.")
    return paper_ids[0]


def current_input_fingerprints(state: PaperState, stage: str) -> dict[str, str]:
    if stage == "read":
        return {"source": state["source"]["fingerprint"]}
    return {
        dependency: state["stages"][dependency]["output_fingerprint"]
        for dependency in STAGE_DEPENDENCIES[stage]
    }


def dependency_blockers(state: PaperState, stage: str) -> list[str]:
    return [
        dependency
        for dependency in STAGE_DEPENDENCIES[stage]
        if state["stages"][dependency]["status"] != "complete"
    ]


def downstream_stages(stage: str) -> list[str]:
    pending = [stage]
    descendants: set[str] = set()
    while pending:
        current = pending.pop(0)
        for candidate, dependencies in STAGE_DEPENDENCIES.items():
            if current in dependencies and candidate not in descendants:
                descendants.add(candidate)
                pending.append(candidate)
    return [candidate for candidate in STAGE_ORDER if candidate in descendants]


def mark_stage_stale(state: PaperState, stage: str, reason: str, timestamp: str) -> None:
    item = state["stages"][stage]
    if item["status"] == "pending":
        return
    item["status"] = "stale"
    item["updated_at"] = timestamp
    item["error"] = ""
    item["stale_reason"] = reason


def cascade_stale(state: PaperState, stage: str, reason: str, timestamp: str) -> None:
    for downstream in downstream_stages(stage):
        mark_stage_stale(state, downstream, reason, timestamp)


def require_stage(data: JsonObject) -> str:
    stage = str(data.get("stage") or "").strip()
    if stage not in STAGE_ORDER:
        raise PaperError(f"data.stage must be one of: {', '.join(STAGE_ORDER)}.")
    return stage


def action_start_stage(state: PaperState, data: JsonObject) -> None:
    stage = require_stage(data)
    item = state["stages"][stage]
    if item["status"] not in {"pending", "failed", "stale"}:
        raise PaperError(f"start_stage requires {stage} to be pending, failed, or stale; current={item['status']}.")
    blockers = dependency_blockers(state, stage)
    if blockers:
        raise PaperError(f"start_stage {stage} is blocked by incomplete dependencies: {', '.join(blockers)}.")
    timestamp = now_iso()
    item.update(
        {
            "status": "in_progress",
            "attempts": item["attempts"] + 1,
            "input_fingerprints": current_input_fingerprints(state, stage),
            "output_fingerprint": "",
            "artifact": "",
            "updated_at": timestamp,
            "error": "",
            "stale_reason": "",
        }
    )


def action_complete_stage(state: PaperState, data: JsonObject) -> None:
    stage = require_stage(data)
    item = state["stages"][stage]
    if item["status"] != "in_progress":
        raise PaperError(f"complete_stage requires {stage} to be in_progress; current={item['status']}.")
    current_inputs = current_input_fingerprints(state, stage)
    if item["input_fingerprints"] != current_inputs:
        raise PaperError(f"complete_stage {stage} rejected because its input fingerprints changed.")
    item.update(
        {
            "status": "complete",
            "output_fingerprint": normalize_fingerprint(
                data.get("output_fingerprint"), f"complete_stage {stage} output_fingerprint"
            ),
            "artifact": normalize_artifact_path(data.get("artifact")),
            "updated_at": now_iso(),
            "error": "",
            "stale_reason": "",
        }
    )


def action_fail_stage(state: PaperState, data: JsonObject) -> None:
    stage = require_stage(data)
    item = state["stages"][stage]
    if item["status"] != "in_progress":
        raise PaperError(f"fail_stage requires {stage} to be in_progress; current={item['status']}.")
    error = " ".join(str(data.get("error") or "").split())
    if not error:
        raise PaperError(f"fail_stage {stage} requires non-empty data.error.")
    item.update(
        {
            "status": "failed",
            "output_fingerprint": "",
            "artifact": "",
            "updated_at": now_iso(),
            "error": error[:500],
            "stale_reason": "",
        }
    )


def action_reset_stage(state: PaperState, data: JsonObject) -> None:
    stage = require_stage(data)
    item = state["stages"][stage]
    if item["status"] == "pending":
        raise PaperError(f"reset_stage requires {stage} to have started.")
    timestamp = now_iso()
    attempts = item["attempts"]
    item.clear()
    item.update(default_stage_state())
    item["attempts"] = attempts
    item["updated_at"] = timestamp
    cascade_stale(state, stage, f"upstream stage {stage} was reset", timestamp)


def action_update_source(state: PaperState, data: JsonObject) -> None:
    source = state["source"]
    locator = str(data.get("locator", source["locator"]) or "").strip()
    if not locator:
        raise PaperError("update_source locator must be non-empty.")
    require_source_identity(state["paper_id"], locator)
    fingerprint = normalize_fingerprint(data.get("fingerprint"), "update_source fingerprint")
    timestamp = now_iso()
    changed = fingerprint != source["fingerprint"]
    source.update({"locator": locator, "fingerprint": fingerprint, "updated_at": timestamp})
    if changed:
        mark_stage_stale(state, "read", "source fingerprint changed", timestamp)
        cascade_stale(state, "read", "source fingerprint changed", timestamp)


def summarize_action(action: str, data: JsonObject) -> str:
    if action == "update_source":
        fingerprint = str(data.get("fingerprint") or "").removeprefix("sha256:")
        return f"action update_source fingerprint={fingerprint[:12]}"
    return f"action {action} stage={data.get('stage', '')}"


def reject_paper_action(
    project_root: Path,
    state: PaperState,
    action: str,
    reason: str,
) -> PaperState:
    audit = state["audit"]
    audit["rejected_actions"] += 1
    state["updated_at"] = now_iso()
    append_paper_log(
        project_root,
        state["paper_id"],
        f"rejected action={action or '(missing)'} reason={reason}",
    )
    write_paper_state(project_root, state)
    raise SystemExit(f"Rejected paper action {action or '(missing)'}: {reason}")


def apply_paper_action(project_root: Path, paper_id: object, payload: object) -> PaperState:
    state = read_paper_state(project_root, paper_id)
    try:
        payload_object = require_json_object(payload)
        action, data = action_envelope_parts(payload_object)
    except EnvelopeError as exc:
        action = str(payload.get("action", "")).strip() if isinstance(payload, dict) else ""
        return reject_paper_action(project_root, state, action, str(exc))
    if action not in ACTION_NAMES:
        return reject_paper_action(
            project_root,
            state,
            action,
            f"Unknown action. Legal actions: {', '.join(ACTION_NAMES)}.",
        )

    append_paper_log(project_root, state["paper_id"], summarize_action(action, data))
    working_state = copy.deepcopy(state)
    try:
        if action == "start_stage":
            action_start_stage(working_state, data)
        elif action == "complete_stage":
            action_complete_stage(working_state, data)
        elif action == "fail_stage":
            action_fail_stage(working_state, data)
        elif action == "reset_stage":
            action_reset_stage(working_state, data)
        elif action == "update_source":
            action_update_source(working_state, data)
    except PaperError as exc:
        return reject_paper_action(project_root, state, action, str(exc))

    working_state["audit"]["action_counts"][action] += 1
    working_state["updated_at"] = now_iso()
    write_paper_state(project_root, working_state)
    return working_state


def paper_progress(state: PaperState) -> JsonObject:
    stages = state["stages"]
    eligible = [
        stage
        for stage in STAGE_ORDER
        if stages[stage]["status"] in {"pending", "failed", "stale"}
        and not dependency_blockers(state, stage)
    ]
    return {
        "completed": sum(1 for stage in STAGE_ORDER if stages[stage]["status"] == "complete"),
        "total": len(STAGE_ORDER),
        "eligible_stages": eligible,
    }


def status_payload(state: PaperState) -> JsonObject:
    return {"paper": state, "progress": paper_progress(state)}


def load_action_payload(args: argparse.Namespace) -> JsonObject:
    if args.file:
        raw = Path(args.file).read_text(encoding="utf-8")
    elif args.json:
        raw = args.json
    else:
        raw = sys.stdin.read()
    try:
        return require_json_object(parse_json_payload(raw))
    except EnvelopeError as exc:
        raise PaperError(str(exc)) from exc


def cmd_create(args: argparse.Namespace) -> int:
    state, created = create_paper(
        Path(args.project_root),
        args.source,
        args.fingerprint,
        args.paper_id,
    )
    print(f"paper_workspace: {paper_directory(Path(args.project_root), state['paper_id'])}")
    print(f"created: {str(created).lower()}")
    print(json.dumps(status_payload(state), ensure_ascii=False, indent=2))
    return 0


def cmd_list(args: argparse.Namespace) -> int:
    paper_ids = list_paper_ids(Path(args.project_root))
    if not paper_ids:
        print("(no registered papers)")
        return 0
    for paper_id in paper_ids:
        print(paper_id)
    return 0


def cmd_status(args: argparse.Namespace) -> int:
    project_root = Path(args.project_root)
    paper_id = resolve_paper_id(project_root, args.paper_id)
    print(json.dumps(status_payload(read_paper_state(project_root, paper_id)), ensure_ascii=False, indent=2))
    return 0


def cmd_apply_action(args: argparse.Namespace) -> int:
    project_root = Path(args.project_root)
    paper_id = resolve_paper_id(project_root, args.paper_id)
    try:
        payload = load_action_payload(args)
    except PaperError as exc:
        return reject_paper_action(project_root, read_paper_state(project_root, paper_id), "", str(exc))
    state = apply_paper_action(project_root, paper_id, payload)
    print(json.dumps(status_payload(state), ensure_ascii=False, indent=2))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Mary paper state runtime (paper_state_schema 1)")
    parser.add_argument("--project-root", default=".", help="Project root; defaults to current directory")
    subparsers = parser.add_subparsers(dest="command", required=True)

    create_parser = subparsers.add_parser("create", help="create or reuse one paper workspace")
    create_parser.add_argument("--source", required=True, help="source locator; acquisition is implemented after P1")
    create_parser.add_argument("--fingerprint", required=True, help="source SHA-256 fingerprint")
    create_parser.add_argument("--paper-id", help="optional canonical paper id")
    create_parser.set_defaults(func=cmd_create)

    subparsers.add_parser("list", help="list registered paper ids").set_defaults(func=cmd_list)

    status_parser = subparsers.add_parser("status", help="show one paper state")
    status_parser.add_argument("--paper-id", help="optional when exactly one paper exists")
    status_parser.set_defaults(func=cmd_status)

    action_parser = subparsers.add_parser("apply-action", help="apply a validated paper action envelope")
    action_parser.add_argument("--paper-id", help="optional when exactly one paper exists")
    action_source = action_parser.add_mutually_exclusive_group()
    action_source.add_argument("--json", help="JSON action string")
    action_source.add_argument("--file", help="path to JSON action file")
    action_parser.set_defaults(func=cmd_apply_action)
    return parser


def main(argv: list[str]) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except PaperError as exc:
        raise SystemExit(str(exc)) from exc


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
