#!/usr/bin/env python3
"""Docs-first project context; explicit paths only, no source scans or hashes."""
from __future__ import annotations

import argparse
import copy
from datetime import datetime, timezone
import json
from pathlib import Path, PurePosixPath
import re

from mw_runtime import atomic_write_text, ensure_workflow_gitignore, workflow_lock

DETAILS = ("responsibility", "entrypoints", "interfaces", "constraints", "verification", "known_gaps")
IMPORTED_UNKNOWN = "UNKNOWN: complete this introduction from existing understanding."


def _text(value, name):
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be nonempty text (use UNKNOWN for unverified facts)")
    return value.strip()


def _paths(values):
    if not isinstance(values, list):
        raise ValueError("files must be a list of exact project-relative paths")
    result = []
    for value in values:
        if (not isinstance(value, str) or not value or value == "." or "\\" in value
                or PurePosixPath(value).is_absolute() or ".." in value.split("/")
                or str(PurePosixPath(value)) != value):
            raise ValueError(f"Invalid exact relative path: {value!r}")
        result.append(value)
    return sorted(set(result))


def location(project):
    return Path(project).resolve() / ".mary-workflow" / "knowledge"


def load(project):
    path = location(project) / "index.json"
    if not path.is_file():
        return {"schema": 1, "revision": 0, "overview": "UNKNOWN: project overview not recorded.",
                "handoff": "UNKNOWN: current task, decisions and next steps not recorded.",
                "modules": {}, "unmapped_files": []}
    value = json.loads(path.read_text(encoding="utf-8"))
    if value.get("schema") != 1:
        raise ValueError("Unsupported knowledge schema")
    return value


def module_text(module):
    parts = [f"# {module['id']}", f"Status: {module['status']}",
             "Pending changes: " + (", ".join(module.get("pending_files", [])) or "none"),
             "Reason: " + module.get("reason", "none"),
             "Files: " + (", ".join(module["files"]) or "none"),
             "Boundary files: " + (", ".join(module.get("boundary_files", [])) or "none"),
             "Depends on: " + (", ".join(module.get("depends_on", [])) or "none")]
    for key in DETAILS:
        parts += ["## " + key, module[key]]
    return "\n\n".join(parts) + "\n"


def context_text(data, modules=()):
    rows = [f"# Project context (revision {data['revision']})", "## Overview", data["overview"],
            "## Module index"]
    rows += [f"- {key}: {m['status']} — {m['responsibility'].splitlines()[0]} "
             f"(modules/{key}.md)" for key, m in data["modules"].items()]
    rows += ["Unmapped changes: " + (", ".join(data["unmapped_files"]) or "none"),
             "## Handoff", data["handoff"],
             "Read only relevant module introductions next; open code when implementing or resolving a concrete uncertainty. "
             "Stale/UNKNOWN text is a clue, not verified current behavior. Reading context never resumes work. "
             "Formal state, USER_STOP and experiment records remain authoritative."]
    for key in modules:
        if key not in data["modules"]:
            raise ValueError(f"Unknown module: {key}")
        rows += [module_text(data["modules"][key])]
    return "\n\n".join(rows) + "\n"


def _save(project, data, module_ids=None, *, ensure_ignore=True):
    """Commit canonical JSON first; Markdown views are recoverable projections."""
    if ensure_ignore:
        ensure_workflow_gitignore(Path(project).resolve())
    root = location(project)
    data["revision"] += 1
    data["updated_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    atomic_write_text(root / "index.json", json.dumps(data, ensure_ascii=False, indent=2) + "\n")
    render(project, data, module_ids=module_ids)
    return data


def render(project, data=None, *, module_ids=None):
    data = load(project) if data is None else data
    root = location(project)
    (root / "modules").mkdir(parents=True, exist_ok=True)
    header = f"<!-- Generated from index.json revision {data['revision']}; edit via mw_knowledge.py update. -->\n\n"
    atomic_write_text(root / "overview.md", header + context_text({**data, "handoff": "See handoff.md."}))
    atomic_write_text(root / "handoff.md", header + "# Handoff\n\n" + data["handoff"] +
                      "\n\nRead overview.md and relevant modules first. Check formal state/experiment records only when needed; "
                      "preserve USER_STOP. This document does not authorize execution.\n")
    keys = data["modules"] if module_ids is None else module_ids
    for key in keys:
        module = data["modules"][key]
        atomic_write_text(root / "modules" / f"{key}.md", header + module_text(module))


def mark_changed(project, files, reason="Implementation changed; introduction needs review", *, existing_only=False):
    files = _paths(files)
    if not files:
        return load(project)
    root = location(project)
    # Formal results should not invent documentation for projects without this feature.
    if existing_only and not (root / "index.json").is_file():
        return None
    with workflow_lock(root):
        data = load(project)
        affected = {key: set(files) & set(m["files"] + m.get("boundary_files", []))
                    for key, m in data["modules"].items()}
        while True:
            previous = copy.deepcopy(affected)
            for key, m in data["modules"].items():
                for dep in m.get("depends_on", []):
                    affected[key].update(affected.get(dep, set()))
            if previous == affected:
                break
        owned = {p for m in data["modules"].values() for p in m["files"]}
        data["unmapped_files"] = sorted(set(data["unmapped_files"]) | (set(files) - owned))
        for key, paths in affected.items():
            if paths:
                m = data["modules"][key]
                m.update(status="stale", reason=_text(reason, "reason"),
                         pending_files=sorted(set(m.get("pending_files", [])) | paths))
        return _save(project, data, module_ids=[key for key, paths in affected.items() if paths],
                     ensure_ignore=not existing_only)


def update(project, payload, expected_revision):
    """Apply authored descriptions; acknowledge exactly the outstanding known changes."""
    with workflow_lock(location(project)):
        data = load(project)
        if data["revision"] != expected_revision:
            raise ValueError(f"Knowledge revision changed: expected {expected_revision}, current {data['revision']}")
        for key in ("overview", "handoff"):
            if key in payload:
                data[key] = _text(payload[key], key)
        items = payload.get("modules", [])
        if not isinstance(items, list) or not all(isinstance(item, dict) for item in items):
            raise ValueError("modules must be a list of introductions")
        supplied = set()
        for item in items:
            key = _text(item.get("id"), "module id")
            if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,79}", key):
                raise ValueError("Module id must be a safe stable filename")
            if key in supplied:
                raise ValueError(f"Duplicate module update: {key}")
            supplied.add(key)
            old = data["modules"].get(key, {})
            reviewed = _paths(item.get("reviewed_files", []))
            if set(reviewed) != set(old.get("pending_files", [])):
                raise ValueError(f"{key}: reviewed_files must match current pending_files")
            module = {field: _text(item.get(field, old.get(field)), field) for field in DETAILS}
            module.update(id=key, files=_paths(item.get("files", old.get("files", []))),
                          boundary_files=_paths(item.get("boundary_files", old.get("boundary_files", []))),
                          depends_on=item.get("depends_on", old.get("depends_on", [])),
                          status="current", pending_files=[], reason="Author updated the introduction")
            if any(module[field] == IMPORTED_UNKNOWN for field in DETAILS):
                module.update(status="incomplete", reason="Imported introduction still has unauthored fields")
            if not isinstance(module["depends_on"], list) or not all(isinstance(x, str) for x in module["depends_on"]):
                raise ValueError("depends_on must be a list of module ids")
            data["modules"][key] = module
        owners = {}
        for key, m in data["modules"].items():
            for dep in m.get("depends_on", []):
                if dep not in data["modules"] or dep == key:
                    raise ValueError(f"{key}: invalid dependency {dep}")
            for path in m["files"]:
                if path in owners:
                    raise ValueError(f"{path}: duplicate module ownership")
                owners[path] = key
        resolved = _paths(payload.get("resolved_unmapped_files", []))
        removed = _paths(payload.get("removed_files", []))
        if removed and (not payload.get("handoff") or not set(removed) <= set(resolved)):
            raise ValueError("Record deleted-file reasons in handoff and include removed_files in resolved_unmapped_files")
        if any(p not in data["unmapped_files"] or (p not in owners and p not in removed) for p in resolved):
            raise ValueError("Resolve only pending unmapped files now assigned or explicitly documented as deleted")
        data["unmapped_files"] = sorted(set(data["unmapped_files"]) - set(resolved))
        return _save(project, data, module_ids=sorted(supplied))


def seed_brief(project, brief, *, ensure_ignore=True):
    """Reuse supplied brief metadata only. Never reread or infer source understanding."""
    with workflow_lock(location(project)):
        data = load(project)
        modules = brief.get("coverage", {}).get("modules", [])
        # Preserve authored introductions. A brief refresh cannot certify their prose.
        changed = False
        if data["revision"] == 0:
            data["overview"] = json.dumps(brief.get("positioning", {}), ensure_ascii=False, indent=2)
            for item in modules:
                key = item["id"]
                if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,79}", key):
                    continue
                data["modules"][key] = {
                    **{field: IMPORTED_UNKNOWN for field in DETAILS},
                    "id": key, "responsibility": item["summary"], "files": item["files"],
                    "boundary_files": item.get("boundary_files", []), "depends_on": item.get("depends_on", []),
                    "status": "incomplete", "pending_files": [], "reason": "Imported summary; detailed introduction not authored"}
            changed = True
        return _save(project, data, ensure_ignore=ensure_ignore) if changed else data


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", type=Path, default=Path.cwd())
    sub = parser.add_subparsers(dest="command", required=True)
    read = sub.add_parser("read")
    read.add_argument("--module", action="append", default=[])
    change = sub.add_parser("changed")
    change.add_argument("--files", nargs="+", required=True)
    change.add_argument("--reason", required=True)
    edit = sub.add_parser("update")
    edit.add_argument("--data", type=Path, required=True, help="Authored JSON payload file")
    edit.add_argument("--expected-revision", type=int, required=True)
    sub.add_parser("import-brief")
    sub.add_parser("render")
    args = parser.parse_args(argv)
    try:
        if args.command == "read":
            print(context_text(load(args.project), args.module), end="")
            return
        if args.command == "changed":
            data = mark_changed(args.project, args.files, args.reason)
        elif args.command == "update":
            data = update(args.project, json.loads(args.data.read_text(encoding="utf-8")), args.expected_revision)
        elif args.command == "import-brief":
            if not (args.project.resolve() / ".mary-workflow" / "state.yaml").is_file():
                raise ValueError("No saved formal state; author context directly without initialization")
            from mary_workflow import read_state
            state = read_state(args.project.resolve() / ".mary-workflow")
            brief = state.get("runtime_meta", {}).get("brief")
            if not brief:
                raise ValueError("No existing brief metadata; author a small update instead of scanning")
            data = seed_brief(args.project, brief)
        else:
            with workflow_lock(location(args.project)):
                data = load(args.project)
                render(args.project, data)
        print(json.dumps({"revision": data["revision"], "modules": len(data["modules"]),
                          "unmapped_files": data["unmapped_files"]}, ensure_ascii=False))
    except (ValueError, OSError) as exc:
        parser.exit(2, f"knowledge: {exc}\n")


if __name__ == "__main__":
    main()
