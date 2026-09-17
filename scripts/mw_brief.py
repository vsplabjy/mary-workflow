"""Model-independent project coverage, incremental refresh, and durable records.

These helpers do not read or write state. The workflow owns inventory generation,
fingerprints, authorization, and persistence; coverage is a checked record of
reading, not proof that an agent understood the source.
"""

from __future__ import annotations

from copy import deepcopy
import hashlib
from pathlib import PurePosixPath
from typing import Any


class BriefError(ValueError):
    """A brief update cannot be applied without losing or inventing evidence."""


def _object(value: object, field: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise BriefError(f"{field} must be an object.")
    return value


def _text(value: object, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise BriefError(f"{field} must be non-empty text.")
    return value.strip()


def _strings(value: object, field: str) -> list[str]:
    if not isinstance(value, list):
        raise BriefError(f"{field} must be a list.")
    result = [_text(item, field) for item in value]
    if len(result) != len(set(result)):
        raise BriefError(f"{field} contains duplicate entries.")
    return result


def _paths(value: object, field: str) -> list[str]:
    if not isinstance(value, list):
        raise BriefError(f"{field} must be a list.")
    # Filesystem names can contain significant leading/trailing spaces.
    result = []
    for item in value:
        _text(item, field)
        result.append(item)
    if len(result) != len(set(result)):
        raise BriefError(f"{field} contains duplicate entries.")
    for path in result:
        normalized = PurePosixPath(path)
        if (normalized.is_absolute() or ".." in normalized.parts or "\\" in path
                or str(normalized) != path or path == "."):
            raise BriefError(f"{field} requires canonical project-relative paths: {path}")
    return result


def normalize_coverage(value: object, inventory: list[str]) -> dict[str, Any]:
    """Validate exact ownership and compute coverage without trusting totals.

    Incomplete read coverage is returned with ``complete=False`` so a migrated
    brief or exploration progress can be represented honestly. Accepting a brief
    requires the caller to reject that result until its unread_files is empty.
    """
    data = _object(value, "coverage")
    expected = set(_paths(inventory, "inventory"))
    raw_modules = data.get("modules")
    if not isinstance(raw_modules, list):
        raise BriefError("coverage.modules must be a list.")
    modules: list[dict[str, Any]] = []
    owners: dict[str, str] = {}
    seen_ids: set[str] = set()
    unread: set[str] = set()
    for index, raw in enumerate(raw_modules):
        record = _object(raw, f"coverage.modules[{index}]")
        module_id = _text(record.get("id"), "module.id")
        if module_id in seen_ids:
            raise BriefError(f"Duplicate module id: {module_id}")
        seen_ids.add(module_id)
        files = _paths(record.get("files"), f"module {module_id}.files")
        reads = _paths(record.get("read_files", []), f"module {module_id}.read_files")
        boundary = _paths(record.get("boundary_files", []), f"module {module_id}.boundary_files")
        extra = (set(files) | set(boundary)) - expected
        if extra:
            raise BriefError(f"Module {module_id} references unknown inventory paths: {sorted(extra)}")
        if set(reads) - (set(files) | set(boundary)):
            raise BriefError(f"Module {module_id}.read_files must be owned or boundary files.")
        for path in files:
            if path in owners:
                raise BriefError(f"Duplicate file ownership: {path} ({owners[path]}, {module_id})")
            owners[path] = module_id
        unread.update(set(files) - set(reads))
        # A boundary reference asserts only a relationship, not a completed read.
        unread.update(set(boundary) - set(reads))
        module: dict[str, Any] = {
            "id": module_id,
            "summary": _text(record.get("summary"), f"module {module_id}.summary"),
            "files": files,
            "read_files": reads,
            "boundary_files": boundary,
            "depends_on": _strings(record.get("depends_on", []), f"module {module_id}.depends_on"),
        }
        for key in ("review_evidence", "provenance"):
            if key in record:
                module[key] = _text(record[key], f"module {module_id}.{key}")
        if "reread_files" in record:
            rereads = _paths(record["reread_files"], f"module {module_id}.reread_files")
            if set(rereads) - set(reads):
                raise BriefError(f"Module {module_id}.reread_files must be included in read_files.")
            module["reread_files"] = rereads
        if "reviewed_dependencies" in record:
            module["reviewed_dependencies"] = _strings(
                record["reviewed_dependencies"], f"module {module_id}.reviewed_dependencies"
            )
        modules.append(module)
    missing = expected - set(owners)
    if missing:
        raise BriefError(f"Coverage is missing inventory paths: {sorted(missing)}")
    for module in modules:
        invalid = set(module["depends_on"]) - seen_ids
        if invalid or module["id"] in module["depends_on"]:
            raise BriefError(f"Module {module['id']} has unknown or self dependencies: {sorted(invalid)}")
    return {
        "schema_version": 1,
        "modules": modules,
        "inventory_count": len(expected),
        "covered_count": len(expected - unread),
        "unread_files": sorted(unread),
        "complete": not unread,
    }


def normalize_records(value: object) -> list[dict[str, Any]]:
    """Keep durable record history, validating optional stable supersession IDs."""
    if not isinstance(value, list):
        raise BriefError("records must be a list.")
    result: list[dict[str, Any]] = []
    ids: set[str] = set()
    for raw in value:
        item = _object(raw, "record")
        kind = item.get("kind")
        if kind not in {"fact", "preference", "decision"}:
            raise BriefError("record.kind must be fact, preference, or decision.")
        record: dict[str, Any] = {"kind": kind, "text": _text(item.get("text"), "record.text")}
        if "source" in item:
            record["source"] = _text(item["source"], "record.source")
        if "id" in item:
            record["id"] = _text(item["id"], "record.id")
            if record["id"] in ids:
                raise BriefError(f"Duplicate durable record id: {record['id']}")
        if "supersedes" in item:
            previous = _strings(item["supersedes"], "record.supersedes")
            if not record.get("id"):
                raise BriefError("A superseding record must have an id.")
            if set(previous) - ids:
                raise BriefError(f"record.supersedes references unknown or later ids: {sorted(set(previous) - ids)}")
            record["supersedes"] = previous
        if record.get("id"):
            ids.add(record["id"])
        result.append(record)
    return result


def affected_modules(coverage: dict[str, Any], changed_files: list[str]) -> set[str]:
    """Find direct file/boundary impact and its transitive module dependents."""
    changed = set(changed_files)
    modules = coverage.get("modules", [])
    affected = {
        module["id"] for module in modules
        if changed.intersection(module.get("files", []) + module.get("boundary_files", []))
    }
    while True:
        dependents = {module["id"] for module in modules if affected.intersection(module.get("depends_on", []))}
        expanded = affected | dependents
        if expanded == affected:
            return affected
        affected = expanded


def merge_brief_update(
    existing: dict[str, Any], update: dict[str, Any], inventory: list[str], changed_files: list[str]
) -> dict[str, Any]:
    """Merge a revision-bound delta without implicitly carrying stale modules.

    Existing uses {version, coverage, positioning, architecture, uncertainties,
    validation, records}. update requires base_version, updated_modules,
    deleted_modules, retained_modules[{id,evidence}], reviewed_changed_files.
    Optional brief fields replace only their own section; record_updates append.
    """
    existing = _object(existing, "existing brief")
    update = _object(update, "brief update")
    version = existing.get("version", 0)
    if type(version) is not int or version < 0:
        raise BriefError("Existing brief version must be a non-negative integer.")
    if type(update.get("base_version")) is not int or update["base_version"] != version:
        raise BriefError("Stale or missing base_version; reread the current project brief.")
    changed = set(_paths(changed_files, "changed_files"))
    reviewed = set(_paths(update.get("reviewed_changed_files"), "reviewed_changed_files"))
    if reviewed != changed:
        raise BriefError("reviewed_changed_files must exactly match machine changed_files, including deletions.")
    old_coverage = _object(existing.get("coverage"), "existing.coverage")
    old_inventory = sorted({path for module in old_coverage.get("modules", []) for path in module.get("files", [])})
    old_coverage = normalize_coverage(old_coverage, old_inventory)
    current_inventory = set(_paths(inventory, "inventory"))
    if changed - (set(old_inventory) | current_inventory):
        raise BriefError("changed_files references paths outside both the old and current inventory.")
    if (set(old_inventory) ^ current_inventory) - changed:
        raise BriefError("changed_files must account for every added or deleted inventory path.")
    old = {module["id"]: module for module in old_coverage["modules"]}
    raw_updates = update.get("updated_modules", [])
    if not isinstance(raw_updates, list):
        raise BriefError("updated_modules must be a list.")
    updated: dict[str, dict[str, Any]] = {}
    for raw in raw_updates:
        module = _object(raw, "updated module")
        module_id = _text(module.get("id"), "updated module.id")
        if module_id in updated:
            raise BriefError(f"Duplicate updated module: {module_id}")
        updated[module_id] = deepcopy(module)
    deleted = set(_strings(update.get("deleted_modules", []), "deleted_modules"))
    raw_retained = update.get("retained_modules", [])
    if not isinstance(raw_retained, list):
        raise BriefError("retained_modules must be a list.")
    retained: dict[str, str] = {}
    for raw in raw_retained:
        item = _object(raw, "retained module")
        module_id = _text(item.get("id"), "retained module.id")
        if module_id in retained:
            raise BriefError(f"Duplicate retained module: {module_id}")
        retained[module_id] = _text(item.get("evidence"), "retained module.evidence")
    if (deleted | set(retained)) - set(old):
        raise BriefError("deleted_modules and retained_modules must reference existing module ids.")
    if (deleted & set(retained)) or (set(updated) & (deleted | set(retained))):
        raise BriefError("Updated, deleted, and retained module ids must be disjoint.")
    unaccounted = set(old) - (deleted | set(retained) | set(updated))
    if unaccounted:
        raise BriefError(f"Every existing module must be updated, deleted, or explicitly retained: {sorted(unaccounted)}")
    combined = [deepcopy(module) for module in old.values() if module["id"] in retained]
    combined.extend(updated.values())
    coverage = normalize_coverage({"modules": combined}, inventory)
    affected = affected_modules(old_coverage, sorted(changed)) | affected_modules(coverage, sorted(changed))
    # Reassigning or deleting a module changes its contract even if no file changed.
    structurally_changed = set(deleted)
    for module_id, module in updated.items():
        before = old.get(module_id)
        if before and any(set(before.get(key, [])) != set(module.get(key, []))
                          for key in ("files", "boundary_files", "depends_on")):
            structurally_changed.add(module_id)
    affected |= structurally_changed
    while True:
        dependents = {module["id"] for module in old_coverage["modules"] + coverage["modules"]
                      if affected.intersection(module.get("depends_on", []))}
        if dependents <= affected:
            break
        affected |= dependents
    if affected & set(retained):
        raise BriefError(f"Affected modules require update and reread evidence, not retention: {sorted(affected & set(retained))}")
    current_paths = current_inventory
    for module in coverage["modules"]:
        module_id = module["id"]
        if module_id not in affected:
            continue
        _text(module.get("review_evidence"), f"module {module_id}.review_evidence")
        before = old.get(module_id, {})
        related = set(module["files"] + module["boundary_files"])
        required_reads = changed & related & current_paths
        if required_reads - set(module.get("reread_files", [])):
            raise BriefError(f"Module {module_id} requires reread_files for changed paths: {sorted(required_reads)}")
        dependencies = set(before.get("depends_on", []) + module.get("depends_on", [])) & affected
        if dependencies - set(module.get("reviewed_dependencies", [])):
            raise BriefError(f"Module {module_id} requires reviewed_dependencies: {sorted(dependencies)}")
    if not coverage["complete"]:
        raise BriefError(f"Brief update leaves unread files: {coverage['unread_files']}")
    result = deepcopy(existing)
    result.update({"version": version + 1, "coverage": coverage})
    for key in ("positioning", "architecture", "uncertainties", "validation"):
        if key in update:
            result[key] = deepcopy(update[key])
    additions = update.get("record_updates", [])
    if not isinstance(additions, list):
        raise BriefError("record_updates must be a list.")
    result["records"] = normalize_records(list(existing.get("records", [])) + additions)
    result["refresh_evidence"] = {
        "base_version": version,
        "reviewed_changed_files": sorted(changed),
        "retained_modules": [{"id": module_id, "evidence": evidence} for module_id, evidence in retained.items()],
        "deleted_modules": sorted(deleted),
        "affected_modules": sorted(affected),
    }
    return result


def migrate_legacy_ledger(
    ledger: list[dict[str, Any]], inventory: list[str], architecture: dict[str, Any] | None = None
) -> dict[str, Any]:
    """Group historical ledger records without inventing new reading evidence.

    The caller retains the original ledger, uncertainties, and brief. A migration
    records provenance and leaves the new coverage pending explicit verification.
    """
    paths = _paths([path for path in inventory if path != "(empty repository)"], "inventory")
    historical = {item.get("path"): item for item in ledger if isinstance(item, dict)}
    summaries = (architecture or {}).get("modules", [])
    groups: dict[str, list[str]] = {}
    for path in paths:
        directory = str(PurePosixPath(path).parent)
        groups.setdefault(directory, []).append(path)
    modules = []
    for directory, files in sorted(groups.items()):
        related = [item for item in summaries if isinstance(item, dict) and set(item.get("files", [])) & set(files)]
        descriptions = [str(item.get("responsibility", "")).strip() for item in related]
        summary = "; ".join(item for item in descriptions if item) or f"Historical module {directory}; verify responsibilities."
        known_count = sum(path in historical for path in files)
        modules.append({
            "id": "legacy-" + hashlib.sha256(directory.encode()).hexdigest()[:12],
            "summary": summary,
            "files": files,
            "read_files": [],
            "boundary_files": [],
            "provenance": f"Migrated legacy ledger: {known_count}/{len(files)} paths had historical entries; no fresh read claimed.",
        })
    return normalize_coverage({"modules": modules}, paths)
