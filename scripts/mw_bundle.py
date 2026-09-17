"""Pin a self-contained, model-independent core runtime to each project."""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import secrets
import shutil
import subprocess
import sys
import tempfile
from typing import Any

from mw_brief import migrate_legacy_ledger
from mw_runtime import atomic_write_text, workflow_lock


BUNDLE_VERSION = 1
STATE_VERSION = "3.0"
LOCK_FILE = "workflow-lock.json"
CORE_SCRIPTS = (
    "mary_workflow.py", "mw_codex.py", "mw_runtime.py", "mw_workers.py",
    "mw_brief.py", "mw_bundle.py", "mw_host.py", "mw_surfaces.py", "mw_reading_profile.py",
)
CORE_REFERENCES = (
    "state-contract.md", "memory-contract.md", "subagent-contract.md", "host-contract.md",
)
CORE_SKILLS = ("lecture-learning", "exam-review", "slide-to-lecture", "roundtrip-screenshot")


class BundleError(ValueError):
    """A pinned runtime cannot be installed, verified, or safely migrated."""


def _hash(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _bundle_contents(source_root: Path) -> tuple[dict[str, bytes], dict[str, bytes]]:
    """Read the complete install input before mutating the project."""
    source_root = source_root.resolve()
    files: dict[str, bytes] = {}
    for name in CORE_SCRIPTS:
        path = source_root / "scripts" / name
        if not path.is_file():
            raise BundleError(f"Core bundle source is missing {path}.")
        files[f"scripts/{name}"] = path.read_bytes()
    default = source_root / "defaults" / "reading-profile.md"
    if not default.is_file():
        raise BundleError("Core bundle requires defaults/reading-profile.md.")
    files["defaults/reading-profile.md"] = default.read_bytes()
    phases = sorted((source_root / "references" / "phases").glob("*.md"))
    if not phases:
        raise BundleError("Core bundle requires maintained references/phases/*.md.")
    prompts: dict[str, bytes] = {}
    for path in phases:
        content = path.read_bytes()
        files[f"references/phases/{path.name}"] = content
        prompts[path.name] = content
    for name in CORE_REFERENCES:
        path = source_root / "references" / name
        if not path.is_file():
            raise BundleError(f"Core bundle source is missing {path}.")
        files[f"references/{name}"] = path.read_bytes()
    # These four profiles reference one another and the core subagent contract;
    # they have no bundled binary assets or additional script dependencies.
    for name in CORE_SKILLS:
        path = source_root / "skills" / name / "SKILL.md"
        if not path.is_file():
            raise BundleError(f"Core profile source is missing {path}.")
        files[f"skills/{name}/SKILL.md"] = path.read_bytes()
    return files, prompts


def _read_manifest(root: Path) -> dict[str, Any]:
    try:
        manifest = json.loads((root / LOCK_FILE).read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise BundleError(f"Cannot read pinned workflow manifest: {exc}") from exc
    if not isinstance(manifest, dict) or manifest.get("bundle_version") != BUNDLE_VERSION:
        raise BundleError("Unsupported workflow bundle manifest; use an explicit compatible upgrade.")
    if manifest.get("state_version") != STATE_VERSION or manifest.get("runtime_version") != STATE_VERSION:
        raise BundleError("Pinned runtime/state version mismatch; use the appropriate migration or upgrade.")
    hashes = manifest.get("files")
    if not isinstance(hashes, dict) or not hashes:
        raise BundleError("Pinned workflow manifest must contain file hashes.")
    for relative, digest in hashes.items():
        if not isinstance(relative, str) or not isinstance(digest, str):
            raise BundleError("Invalid manifest path/hash entry.")
        path = PurePosixPath(relative)
        if (path.is_absolute() or ".." in path.parts or "\\" in relative
                or str(path) != relative or not relative.startswith(("runtime/", "prompts/"))):
            raise BundleError(f"Unsafe manifest path: {relative}")
        if len(digest) != 64 or any(character not in "0123456789abcdef" for character in digest):
            raise BundleError(f"Invalid SHA-256 for {relative}.")
    required = {f"runtime/scripts/{name}" for name in CORE_SCRIPTS}
    required.update(f"runtime/references/{name}" for name in CORE_REFERENCES)
    required.update(f"runtime/skills/{name}/SKILL.md" for name in CORE_SKILLS)
    if not required <= set(hashes):
        raise BundleError("Pinned workflow manifest omits required core runtime files.")
    return manifest


def _managed_paths(root: Path) -> set[str]:
    paths: set[str] = set()
    for path in (root / "runtime").rglob("*"):
        relative = path.relative_to(root)
        if "__pycache__" in relative.parts or path.suffix == ".pyc":
            continue
        if path.is_file() or path.is_symlink():
            paths.add(relative.as_posix())
    paths.update(path.relative_to(root).as_posix() for path in (root / "prompts").glob("*.md"))
    return paths


def verify_bundle(root: Path) -> dict[str, Any]:
    """Verify pinned code and prompts before execution, without writing files.

    This detects accidental drift, not malicious actors who can rewrite both the
    manifest and files. No claim of user-authentication or shell sandboxing is made.
    """
    root = root.resolve()
    manifest = _read_manifest(root)
    expected = set(manifest["files"])
    actual = _managed_paths(root)
    if expected != actual:
        raise BundleError(f"Pinned bundle file set changed: missing={sorted(expected - actual)}, extra={sorted(actual - expected)}. Use an explicit upgrade or restore the pinned files.")
    for relative, digest in manifest["files"].items():
        path = root / relative
        if path.is_symlink() or not path.is_file() or not path.resolve().is_relative_to(root):
            raise BundleError(f"Pinned file is missing or escapes the project: {relative}")
        if _hash(path.read_bytes()) != digest:
            raise BundleError(f"Pinned workflow file changed: {relative}. Restore it or preview an explicit upgrade.")
    return manifest


def _install_bundle(root: Path, source_root: Path, *, replace: bool) -> dict[str, Any]:
    files, prompts = _bundle_contents(source_root)
    if (root / LOCK_FILE).exists() and not replace:
        return verify_bundle(root)
    root.mkdir(parents=True, exist_ok=True)
    if (root / "runtime").is_symlink() or (root / "prompts").is_symlink():
        raise BundleError("Runtime and prompt directories cannot be symlinks.")
    old_generated: set[str] = set()
    if (root / LOCK_FILE).exists():
        old_generated = set(_read_manifest(root).get("generated_prompts", []))
    with tempfile.TemporaryDirectory(prefix=".bundle-stage-", dir=root) as temporary:
        stage = Path(temporary) / "runtime"
        stage.mkdir()
        for relative, content in files.items():
            destination = stage / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(content)
        old_runtime = Path(temporary) / "previous-runtime"
        if (root / "runtime").exists():
            os.replace(root / "runtime", old_runtime)
        try:
            os.replace(stage, root / "runtime")
        except BaseException:
            if old_runtime.exists():
                os.replace(old_runtime, root / "runtime")
            raise
        (root / "prompts").mkdir(exist_ok=True)
        for name in old_generated - set(prompts):
            if Path(name).name != name:
                raise BundleError("Unsafe generated prompt path in prior manifest.")
            (root / "prompts" / name).unlink(missing_ok=True)
        for name, content in prompts.items():
            atomic_write_text(root / "prompts" / name, content.decode("utf-8"))
        manifest = {
            "bundle_version": BUNDLE_VERSION,
            "runtime_version": STATE_VERSION,
            "state_version": STATE_VERSION,
            "installed_at": _now(),
            "generated_prompts": sorted(prompts),
            "files": {relative: _hash((root / relative).read_bytes()) for relative in sorted(_managed_paths(root))},
        }
        atomic_write_text(root / LOCK_FILE, json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
    return verify_bundle(root)


def install_bundle(root: Path, source_root: Path) -> dict[str, Any]:
    """Install once; ordinary initialization verifies an existing pinned bundle."""
    if (root / LOCK_FILE).exists():
        return verify_bundle(root)
    with workflow_lock(root):
        return _install_bundle(root, source_root, replace=False)


def forward_to_pinned(root: Path, script_name: str, args: list[str]) -> int | None:
    """Return a forwarded process exit code, or None when local handling is due."""
    if script_name not in CORE_SCRIPTS:
        raise BundleError(f"Not a pinned core entrypoint: {script_name}")
    if args and args[0] in {"migrate", "upgrade"}:
        return None
    if args and args[0] == "init" and "--reset" in args:
        pinned_scripts = (root / "runtime" / "scripts").resolve()
        if Path(__file__).resolve().parent == pinned_scripts:
            raise BundleError("Run init --reset using the installed skill entrypoint; the project-local runtime is part of the directory being reset.")
        return None
    if not (root / LOCK_FILE).exists():
        return None
    verify_bundle(root)
    target = (root / "runtime" / "scripts" / script_name).resolve()
    local = Path(__file__).resolve().parent / script_name
    if local.resolve() == target or Path(sys.argv[0]).resolve() == target:
        return None
    return subprocess.run([sys.executable, str(target), *args], check=False).returncode


def _read_state(root: Path, *, legacy: bool = False) -> dict[str, Any]:
    if not (root / "state.yaml").is_file():
        raise BundleError("A state.yaml is required; initialize a new project before migration or upgrade.")
    from mary_workflow import read_state

    return read_state(root, allow_legacy=legacy)


def preview_migration(root: Path) -> dict[str, Any]:
    state = _read_state(root, legacy=True)
    phase = state.get("phase", "PLANNING")
    active = phase in {"EXECUTING", "REVIEWING", "DEBUGGING"}
    return {
        "operation": "migrate",
        "from_version": state.get("version"), "to_version": STATE_VERSION,
        "required": state.get("version") != STATE_VERSION,
        "phase": phase,
        "target_phase": "EXECUTING" if phase == "REVIEWING" else phase,
        "will_pause": active,
        "brief_refresh": "deferred_until_stable_phase" if active else "required",
        "preserves": ["milestones", "reports", "logs", "cycles", "legacy_ledger", "uncertainties", "authorization_history"],
        "changes": [
            "Install a versioned core runtime and prompt snapshot.",
            "Preserve the legacy ledger as historical evidence; record pending module reads.",
            "Require current worker/validation evidence for future acceptance.",
        ],
    }


def preview_upgrade(root: Path, source_root: Path | None = None) -> dict[str, Any]:
    state = _read_state(root)
    manifest = _read_manifest(root) if (root / LOCK_FILE).exists() else None
    drift = ""
    if manifest:
        try:
            verify_bundle(root)
        except BundleError as exc:
            drift = str(exc)
    changes: list[str] = []
    if source_root is not None:
        files, prompts = _bundle_contents(source_root)
        candidates = {f"runtime/{path}": content for path, content in files.items()}
        candidates.update({f"prompts/{path}": content for path, content in prompts.items()})
        changes = sorted(path for path, content in candidates.items()
                         if not (root / path).is_file() or _hash((root / path).read_bytes()) != _hash(content))
        if manifest:
            changes.extend(sorted(path for path in manifest["files"]
                                  if path.startswith("runtime/") and path not in candidates))
    active = state.get("phase") in {"EXECUTING", "REVIEWING", "DEBUGGING"}
    return {
        "operation": "upgrade", "from_version": manifest.get("runtime_version") if manifest else None,
        "to_version": STATE_VERSION, "phase": state.get("phase"),
        "requires_stop": active and state.get("status") != "stopped",
        "requires_quiescence": bool(state.get("runtime_meta", {}).get("stop_pending")),
        "detected_drift": drift, "changed_files": sorted(set(changes)),
        "preserves": ["state", "authorization_history", "reports", "logs", "cycles", "brief"],
    }


def _backup(root: Path, operation: str) -> Path:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup = root / "migrations" / f"backup-{operation}-{stamp}-{secrets.token_hex(4)}"
    backup.parent.mkdir(parents=True, exist_ok=True)

    def ignore(directory: str, names: list[str]) -> set[str]:
        return set(names) & {"migrations", ".write.lock"} if Path(directory).resolve() == root.resolve() else set()

    shutil.copytree(root, backup, ignore=ignore, symlinks=True)
    return backup


def _restore(root: Path, backup: Path) -> None:
    for path in root.iterdir():
        if path.name in {"migrations", ".write.lock"}:
            continue
        if path.is_dir() and not path.is_symlink():
            shutil.rmtree(path)
        else:
            path.unlink()
    for path in backup.iterdir():
        target = root / path.name
        if path.is_dir() and not path.is_symlink():
            shutil.copytree(path, target, symlinks=True)
        else:
            shutil.copy2(path, target, follow_symlinks=False)


def apply_migration(root: Path, source_root: Path) -> dict[str, Any]:
    """Migrate a supported legacy state with backup and rollback on failure."""
    _bundle_contents(source_root)
    with workflow_lock(root):
        preview = preview_migration(root)
        if not preview["required"]:
            raise BundleError("State is already current; preview upgrade to replace its pinned runtime.")
        if preview["from_version"] != "2.1":
            raise BundleError("Only v2.1 states have a defined non-destructive migration.")
        state = _read_state(root, legacy=True)
        backup = _backup(root, "migration")
        try:
            from mary_workflow import current_milestone, current_plan_digest, refresh_progress, write_project_brief, write_state

            metadata = state.setdefault("runtime_meta", {})
            metadata["legacy_transition"] = {
                "version": state["version"], "phase": state["phase"], "status": state["status"],
                "confirmed": state.get("final_plan_confirmed", False),
                "authorization": {key: deepcopy(value) for key, value in state.items()
                                  if key.startswith(("lease_", "run_grant_"))},
                "migrated_at": _now(), "backup": str(backup.relative_to(root)),
            }
            state["version"] = STATE_VERSION
            inventory = [path for path in state.get("project_inventory", []) if path != "(empty repository)"]
            state["project_inventory"] = inventory
            coverage = migrate_legacy_ledger(state.get("project_file_ledger", []), inventory, state.get("project_architecture", {}))
            metadata["brief"] = {
                "version": state.get("project_brief_version", 0), "coverage": coverage,
                "positioning": deepcopy(state.get("project_positioning", {})),
                "architecture": deepcopy(state.get("project_architecture", {})),
                "uncertainties": deepcopy(state.get("project_uncertainties", [])),
                "validation": deepcopy(state.get("project_validation", [])),
                "records": [], "legacy_pending": True,
            }
            metadata["plan_revision"] = max(1, int(metadata.get("plan_revision", 0)))
            metadata["frozen_plan_digest"] = current_plan_digest(state) if state.get("milestones") else ""
            metadata["execution_mode"] = "delegated"
            metadata["state_revision"] = int(metadata.get("state_revision", 0)) + 1
            metadata["requires_worker_evidence"] = True
            if preview["will_pause"]:
                if state["phase"] == "REVIEWING":
                    current = current_milestone(state)
                    if current:
                        metadata["legacy_transition"]["pending_review"] = deepcopy(current)
                        current["status"] = "pending"
                        current["review"] = ""
                    state["phase"] = "EXECUTING"
                state["status"] = "stopped"
                state["lease_status"] = "paused"
                state["lease_owner"] = ""
                state["lease_run_id"] = state.get("lease_run_id") or secrets.token_hex(12)
                state["lease_plan_digest"] = metadata["frozen_plan_digest"]
                metadata["legacy_brief_refresh_pending"] = True
            else:
                state["project_brief_status"] = "refresh_required"
            for key in tuple(state):
                if key.startswith("run_grant_"):
                    state[key] = ""
            state["updated_at"] = _now()
            refresh_progress(state)
            manifest = _install_bundle(root, source_root, replace=True)
            write_state(root, state)
            write_project_brief(root, state)
        except BaseException:
            _restore(root, backup)
            raise
        return {"preview": preview, "backup": str(backup), "manifest": manifest, "state_version": STATE_VERSION}


def apply_upgrade(root: Path, source_root: Path, *, workers_quiescent: bool = False) -> dict[str, Any]:
    """Explicitly replace a pinned bundle after a concrete diff and backup."""
    _bundle_contents(source_root)
    with workflow_lock(root):
        from mw_workers import list_tasks
        if any(task.get("active_validation") for task in list_tasks(root)):
            raise BundleError("Wait for active validation commands to shut down and record their results before upgrading.")
        preview = preview_upgrade(root, source_root)
        if preview["requires_stop"]:
            raise BundleError("Stop the active workflow and settle worker writes before applying an upgrade.")
        if preview["requires_quiescence"] and workers_quiescent is not True:
            raise BundleError("Interrupted workers may still write; verify quiescence and supply workers_quiescent=true before upgrading.")
        backup = _backup(root, "upgrade")
        try:
            manifest = _install_bundle(root, source_root, replace=True)
        except BaseException:
            _restore(root, backup)
            raise
        return {"preview": preview, "backup": str(backup), "manifest": manifest}
