"""Dependency-free, deliberately strict OpenSpec subset for Mary Workflow.

The supported format is Markdown requirements/scenarios and JSON mary-task fences.
Checkboxes are progress views; their values never affect the frozen definition.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import tempfile


class SDDError(ValueError):
    pass


def _fail(message):
    raise SDDError(message)


def _safe(project: Path, relative: str) -> Path:
    rel = Path(relative)
    if rel.is_absolute() or not rel.parts or any(p in {"..", "."} for p in rel.parts):
        _fail(f"Unsafe path: {relative}")
    path = project
    for part in rel.parts:
        path = path / part
        if path.is_symlink():
            _fail(f"Symlink path is forbidden: {relative}")
    return path


def _digest(text):
    return hashlib.sha256(text.encode()).hexdigest()


def canonical_tasks(text: str) -> str:
    return re.sub(r"(?m)^(\s*- )\[[ xX]\](?=\s+\d+(?:\.\d+)*\s)", r"\1[ ]", text)


def _atomic(path: Path, text: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=".mary-sdd-", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            stream.write(text)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def _sections(text, level):
    matches = list(re.finditer(rf"(?m)^{'#' * level} ([^\n]+)\s*$", text))
    return [(m.group(1).strip(), text[m.end():matches[i+1].start() if i+1 < len(matches) else len(text)].strip()) for i, m in enumerate(matches)]


def _requirements(body, validate=True):
    # Reject headings that would otherwise disappear during section extraction.
    for line in body.splitlines():
        if line.startswith("#") and not (line.startswith("### Requirement: ") or line.startswith("#### Scenario: ")):
            _fail(f"Malformed requirement/scenario heading: {line}")
    result = {}
    sections = _sections(body, 3)
    if not sections:
        _fail("Requirement section is empty")
    for heading, content in sections:
        if not heading.startswith("Requirement: "):
            _fail(f"Malformed requirement heading: {heading}")
        name = heading[len("Requirement: "):].strip()
        if not name or name in result:
            _fail(f"Duplicate or empty requirement: {name}")
        scenarios = {}
        for title, scenario in _sections(content, 4):
            if not title.startswith("Scenario: "):
                _fail(f"Malformed scenario heading: {title}")
            title = title[len("Scenario: "):].strip()
            if not title or title in scenarios:
                _fail(f"Duplicate or empty scenario: {title}")
            if validate and not all(re.search(rf"\b{word}\b", scenario) for word in ("WHEN", "THEN")):
                _fail(f"Scenario needs WHEN/THEN: {name}::{title}")
            scenarios[title] = scenario
        if validate and (not scenarios or not re.search(r"\b(?:SHALL|MUST)\b", content.split("#### ", 1)[0])):
            _fail(f"Requirement needs SHALL/MUST and scenarios: {name}")
        if re.search(r"(?m)^#{5,}\s*(?:Scenario|Requirement):", content):
            _fail("Malformed requirement/scenario heading level")
        result[name] = {"text": f"### Requirement: {name}\n{content}\n", "scenarios": scenarios}
    return result


def _base(text):
    sections = dict(_sections(text, 2))
    if set(sections) != {"Purpose", "Requirements"} or len(_sections(text, 2)) != 2 or not sections["Purpose"]:
        _fail("Main specs require exactly Purpose and Requirements sections")
    return sections["Purpose"], _requirements(sections["Requirements"]) if sections["Requirements"] else {}


def _delta(text, capability, purpose, requirements, new_capability=False):
    for line in text.splitlines():
        if line.startswith("#") and not (line.startswith("# ") or line.startswith("## ") or line.startswith("### Requirement: ") or line.startswith("#### Scenario: ")):
            _fail(f"Malformed delta heading: {line}")
    purpose_sections = [body for title, body in _sections(text, 2) if title == "Purpose"]
    if len(purpose_sections) > 1 or (purpose_sections and not purpose_sections[0].strip()):
        _fail("Delta Purpose must be unique and nonempty")
    if new_capability:
        if not purpose_sections:
            _fail("New capability requires an explicit Purpose section")
        purpose = purpose_sections[0]
    elif purpose_sections and purpose_sections[0] != purpose:
        _fail("Existing capability Purpose must be preserved")
    required = []
    seen_sections = set()
    touched = set()
    for op, body in _sections(text, 2):
        if op == "Purpose":
            continue
        if op not in {"ADDED Requirements", "MODIFIED Requirements", "REMOVED Requirements", "RENAMED Requirements"} or op in seen_sections:
            _fail(f"Unknown or duplicate delta operation: {op}")
        seen_sections.add(op)
        if op == "RENAMED Requirements":
            pairs = re.findall(r'(?m)^- FROM: `### Requirement: (.+)`\s*\n- TO: `### Requirement: (.+)`\s*$', body)
            residue = re.sub(r'(?m)^- FROM: `### Requirement: (.+)`\s*\n- TO: `### Requirement: (.+)`\s*$', '', body).strip()
            if not pairs or residue:
                _fail("RENAMED requires FROM/TO requirement pairs")
            for old, new in pairs:
                if old in touched or new in touched or old not in requirements or new in requirements:
                    _fail(f"Invalid rename: {old} -> {new}")
                value = requirements.pop(old)
                value = dict(value, text=value["text"].replace(f"### Requirement: {old}\n", f"### Requirement: {new}\n", 1))
                requirements[new] = value
                touched.update((old, new))
                required.append(f"{capability}::RENAMED::{old}")
            continue
        for name, value in _requirements(body, validate=op != "REMOVED Requirements").items():
            if name in touched:
                _fail(f"Requirement changed more than once: {name}")
            touched.add(name)
            exists = name in requirements
            if (op == "ADDED Requirements" and exists) or (op != "ADDED Requirements" and not exists):
                _fail(f"Invalid {op}: {name}")
            if op == "REMOVED Requirements":
                if not all(re.search(rf"(?:\*\*)?{field}(?:\*\*)?:\s*\S", value["text"]) for field in ("Reason", "Migration")):
                    _fail(f"Removed requirement needs Reason/Migration: {name}")
                requirements.pop(name)
                required.append(f"{capability}::REMOVED::{name}")
            else:
                requirements[name] = value
                required.extend(f"{capability}::{name}::{scenario}" for scenario in value["scenarios"])
    if not seen_sections:
        _fail("Delta contains no operations")
    merged = f"# {capability}\n\n## Purpose\n{purpose}\n\n## Requirements\n\n" + "\n".join(v["text"] for v in requirements.values())
    return required, merged


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            _fail(f"Duplicate JSON field: {key}")
        result[key] = value
    return result


def _tasks(text):
    pattern = re.compile(r"(?m)^- \[[ xX]\] (\d+(?:\.\d+)*) ([^\n]+)\n\s*```mary-task\s*\n(.*?)\n```", re.S)
    milestones, trace, task_ids, ids = [], [], set(), set()
    matches = list(pattern.finditer(text))
    if len(re.findall(r"(?m)^\s*- \[[ xX]\] ", text)) != len(matches) or text.count("```mary-task") != len(matches) or not matches:
        _fail("Every task needs a numbered checkbox immediately followed by a mary-task JSON fence")
    for match in matches:
        task_id, title, raw = match.groups()
        try:
            data = json.loads(raw, object_pairs_hook=_unique_object)
        except (ValueError, TypeError) as exc:
            raise SDDError(f"Invalid mary-task JSON: {exc}") from exc
        if not isinstance(data, dict):
            _fail("mary-task must be a JSON object")
        mid = data.get("id")
        if not isinstance(mid, str) or not re.fullmatch(r"milestone-[1-9][0-9]*", mid) or mid in ids or task_id in task_ids:
            _fail("Duplicate or invalid task/milestone id")
        ids.add(mid); task_ids.add(task_id)
        for field in ("deliverables", "acceptance"):
            if not isinstance(data.get(field), list) or not data[field] or any(not isinstance(x, str) or not x.strip() for x in data[field]):
                _fail(f"{field} must be a nonempty string list")
        if not isinstance(data.get("estimated_scope"), int) or isinstance(data["estimated_scope"], bool) or data["estimated_scope"] < 0:
            _fail("estimated_scope must be a nonnegative integer")
        if set(data) - {"id", "deliverables", "acceptance", "estimated_scope", "gate", "write_scope", "read_dependencies", "covers"}:
            _fail("Unknown mary-task field")
        covers = data.pop("covers", {})
        if not isinstance(covers, dict):
            _fail("covers must map scenario references to acceptance IDs")
        valid_checks = {f"check-{i+1}" for i in range(len(data["acceptance"]))}
        for scenario, checks in covers.items():
            if not isinstance(checks, list) or not checks or any(not isinstance(c, str) or c not in valid_checks for c in checks):
                _fail(f"Invalid acceptance mapping: {scenario}")
            trace.append({"scenario": scenario, "milestone_id": mid, "acceptance_ids": checks})
        milestones.append(dict(data, title=title.strip(), task_id=task_id))
    return milestones, trace


def load_change(project: Path, change_id: str) -> dict:
    project = Path(project).absolute()
    if not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9_-]*", change_id) or change_id == "archive":
        _fail("Invalid change id")
    relative = f"openspec/changes/{change_id}"
    directory = _safe(project, relative)
    if not directory.is_dir():
        _fail(f"Missing change: {change_id}")
    files, texts = {}, {}
    for path in sorted(directory.rglob("*")):
        rel = path.relative_to(project).as_posix()
        _safe(project, rel)
        if path.is_file():
            suffix = path.relative_to(directory).as_posix()
            if suffix not in {"proposal.md", "tasks.md", "design.md", ".openspec.yaml"} and not re.fullmatch(r"specs/(?:[A-Za-z0-9][A-Za-z0-9_-]*/)+spec.md", suffix):
                _fail(f"Unsupported change artifact: {rel}")
            text = path.read_text(encoding="utf-8")
            texts[rel] = text
            files[rel] = _digest(canonical_tasks(text) if rel == f"{relative}/tasks.md" else text)
    proposal = texts.get(f"{relative}/proposal.md", "")
    if not proposal.strip():
        _fail("Nonempty proposal.md is required")
    milestones, trace = _tasks(texts.get(f"{relative}/tasks.md", ""))
    meta = texts.get(f"{relative}/.openspec.yaml", "")
    for field in ("skip_specs", "skip_reason"):
        if len(re.findall(rf"(?m)^{field}:", meta)) > 1:
            _fail(f"Duplicate metadata field: {field}")
    skip = bool(re.search(r"(?m)^skip_specs:\s*true\s*$", meta))
    deltas = {p:t for p,t in texts.items() if p.endswith("/spec.md")}
    reason = re.search(r"(?m)^skip_reason:[ \t]*(.+)$", meta)
    reason_text = reason.group(1).strip().strip("\"'") if reason else ""
    if skip and (deltas or not reason_text or reason_text in {"|", ">", "null", "~"}):
        _fail("skip_specs requires a reason and no deltas")
    if not skip and not deltas:
        _fail("Behavior changes require delta specs; explicitly justify skip_specs otherwise")
    base_specs, merged_specs, required = {}, {}, []
    for path, text in deltas.items():
        suffix = path[len(relative)+1:]
        if not re.fullmatch(r"specs/(?:[A-Za-z0-9][A-Za-z0-9_-]*/)+spec.md", suffix):
            _fail(f"Invalid delta path: {path}")
        capability = suffix[len("specs/"):-len("/spec.md")]
        main = f"openspec/{suffix}"
        base = _safe(project, main)
        base_text = base.read_text(encoding="utf-8") if base.exists() else None
        base_specs[main] = _digest(base_text) if base_text is not None else None
        purpose, requirements = _base(base_text) if base_text is not None else ("", {})
        refs, merged = _delta(text, capability, purpose, requirements, new_capability=base_text is None)
        required.extend(refs)
        merged_specs[main] = merged
    covered = {entry["scenario"] for entry in trace}
    if covered != set(required):
        _fail(f"Scenario coverage mismatch: missing={sorted(set(required)-covered)}, unknown={sorted(covered-set(required))}")
    return {"schema_version": 1, "change_id": change_id, "files": files, "base_specs": base_specs, "milestones": milestones, "trace": trace, "merged_specs": merged_specs}


def assert_binding(project: Path, binding: dict) -> None:
    if load_change(project, binding["change_id"]) != binding:
        _fail("SDD binding drift: replan against the changed artifacts or base specs")


def sync_tasks(project: Path, binding: dict, accepted_ids: set) -> None:
    assert_binding(project, binding)
    path = _safe(Path(project), f"openspec/changes/{binding['change_id']}/tasks.md")
    accepted = {m["task_id"] for m in binding["milestones"] if m["id"] in accepted_ids}
    text = re.sub(r"(?m)^(- )\[[ xX]\]( (\d+(?:\.\d+)*) )", lambda m: f"{m[1]}[{'x' if m[3] in accepted else ' '}]{m[2]}", path.read_text(encoding="utf-8"))
    _atomic(path, text)


def archive_change(root: Path, state: dict) -> str:
    root = Path(root).absolute()
    project = root.parent
    binding = state.get("runtime_meta", {}).get("sdd")
    if not binding:
        _fail("No SDD binding")
    if state.get("phase") != "FINISHED" or not state.get("milestones") or any(m.get("status") != "done" or m.get("review") not in {"accepted", "accepted-next"} for m in state["milestones"]):
        _fail("Archive requires FINISHED and all milestones accepted")
    if {m.get("id") for m in state["milestones"] if not m.get("repair_of")} != {m["id"] for m in binding["milestones"]}:
        _fail("Accepted milestones do not match the SDD binding")
    cycle = str(state.get("cycle", "C0"))
    if not re.fullmatch(r"[A-Za-z0-9_-]+", cycle):
        _fail("Invalid cycle")
    source_rel = f"openspec/changes/{binding['change_id']}"
    destination_rel = f"openspec/changes/archive/{cycle}-{binding['change_id']}"
    source, destination = _safe(project, source_rel), _safe(project, destination_rel)
    journal_path = _safe(project, root.relative_to(project).as_posix() + "/sdd-archive.json")
    if journal_path.exists():
        journal = json.loads(journal_path.read_text(encoding="utf-8"))
        if journal.get("source") != source_rel or journal.get("destination") != destination_rel:
            if journal.get("complete"):
                journal = None
            else:
                _fail("Another SDD archive is pending")
    else:
        journal = None
    if journal is None:
        sync_tasks(project, binding, {m["id"] for m in binding["milestones"]})
        assert_binding(project, binding)
        if destination.exists():
            _fail("Archive destination already exists")
        entries = {}
        for rel, after in binding["merged_specs"].items():
            path = _safe(project, rel)
            before = path.read_text(encoding="utf-8") if path.exists() else None
            entries[rel] = {"before": before, "after": after, "before_hash": _digest(before) if before is not None else None, "after_hash": _digest(after)}
        journal = {"source": source_rel, "destination": destination_rel, "binding_hash": _digest(json.dumps(binding, sort_keys=True)), "entries": entries, "complete": False}
        _atomic(journal_path, json.dumps(journal, indent=2) + "\n")
    if journal.get("binding_hash") != _digest(json.dumps(binding, sort_keys=True)) or set(journal.get("entries", {})) != set(binding["merged_specs"]):
        _fail("Archive journal does not match frozen binding")
    if source.exists() == destination.exists():
        _fail("Archive source/destination conflict")
    # Validate all journal paths, payloads, and file states before any mutation.
    for rel, entry in journal["entries"].items():
        path = _safe(project, rel)
        if entry["after"] != binding["merged_specs"][rel] or entry["after_hash"] != _digest(entry["after"]) or entry["before_hash"] != (_digest(entry["before"]) if entry["before"] is not None else None) or entry["before_hash"] != binding["base_specs"][rel]:
            _fail("Invalid archive journal payload")
        current = path.read_text(encoding="utf-8") if path.exists() else None
        if current not in (entry["before"], entry["after"]):
            _fail(f"Third-party drift during archive: {rel}")
    actual = source if source.exists() else destination
    artifacts = {}
    for path in actual.rglob("*"):
        _safe(project, path.relative_to(project).as_posix())
        if path.is_file():
            rel = source_rel + "/" + path.relative_to(actual).as_posix()
            text = path.read_text(encoding="utf-8")
            artifacts[rel] = _digest(canonical_tasks(text) if path.name == "tasks.md" else text)
    if artifacts != binding["files"]:
        _fail("Change artifacts drifted during archive")
    if journal.get("complete"):
        if source.exists() or any((_safe(project, rel).read_text(encoding="utf-8") if _safe(project, rel).exists() else None) != entry["after"] for rel, entry in journal["entries"].items()):
            _fail("Completed archive no longer matches its final state")
        return destination_rel
    for rel, entry in journal["entries"].items():
        path = _safe(project, rel)
        if not path.exists() or path.read_text(encoding="utf-8") != entry["after"]:
            _atomic(path, entry["after"])
    if source.exists():
        destination.parent.mkdir(parents=True, exist_ok=True)
        source.rename(destination)
    journal["complete"] = True
    _atomic(journal_path, json.dumps(journal, indent=2) + "\n")
    return destination_rel
