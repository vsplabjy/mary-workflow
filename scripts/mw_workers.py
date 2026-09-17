#!/usr/bin/env python3
"""Model-independent worker records and locally executed acceptance evidence.

The coordinator calls these helpers under its workflow mutation lock. These are
audit and mistake-prevention controls, not a sandbox against arbitrary shell
access. Workers submit envelopes; they never write this control directory.
"""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import secrets
import signal
import stat
import subprocess
import time
from typing import Any

from mw_runtime import atomic_write_text, workflow_lock


class WorkerError(ValueError):
    """A dispatch or evidence record does not satisfy the worker contract."""


Json = dict[str, Any]
_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,95}\Z")
_CONTROL = {".git", ".mary-workflow", ".mary-workflow-worker"}
_CACHE = {"__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache"}
_OPEN = {"running", "ready_for_review"}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _digest(value: object) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                     separators=(",", ":")).encode()).hexdigest()


def _file_digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            value.update(chunk)
    return value.hexdigest()


def _id(value: object, field: str) -> str:
    text = str(value or "")
    if not _ID.fullmatch(text) or text in {".", ".."}:
        raise WorkerError(f"{field} must be a simple nonempty identifier.")
    return text


def _storage(root: Path) -> Path:
    root = Path(root).absolute()
    if root.is_symlink() or (root / "tasks").is_symlink():
        raise WorkerError("Workflow task storage must not be a symlink.")
    return root / "tasks"


def validate_relative_path(value: object) -> str:
    """Validate an exact product path without touching the filesystem."""
    name = str(value or "")
    parts = PurePosixPath(name).parts
    if (not parts or name.startswith("/") or "\\" in name
            or any(part in {".", ".."} for part in name.split("/"))
            or any(char in name for char in "*?[]\x00")
            or parts[0] in _CONTROL or any(part in _CACHE for part in parts)):
        raise WorkerError(f"Unsafe or non-exact product path: {name!r}.")
    return PurePosixPath(name).as_posix()


def _path(project: Path, value: object) -> str:
    name = validate_relative_path(value)
    parts = PurePosixPath(name).parts
    cursor = project
    for part in parts:
        cursor = cursor / part
        if cursor.is_symlink():
            raise WorkerError(f"Symlink is outside worker path contract: {name}.")
    if cursor.exists() and not cursor.is_file():
        raise WorkerError(f"Worker paths must name files, not directories: {name}.")
    return name


def _paths(project: Path, values: object, field: str) -> list[str]:
    if not isinstance(values, list):
        raise WorkerError(f"{field} must be a list of exact relative file paths.")
    result = [_path(project, value) for value in values]
    if len(set(result)) != len(result):
        raise WorkerError(f"{field} contains duplicate paths.")
    return sorted(result)


def _task_dir(root: Path, task_id: object) -> Path:
    path = _storage(root) / _id(task_id, "task_id")
    if path.is_symlink():
        raise WorkerError("Task directory must not be a symlink.")
    return path


def _read_json(path: Path) -> Json:
    if path.is_symlink():
        raise WorkerError(f"Control record must not be a symlink: {path.name}.")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise WorkerError(f"Cannot read worker record {path.name}: {exc}") from exc
    if not isinstance(value, dict):
        raise WorkerError(f"Worker record {path.name} must be an object.")
    return value


def _save(root: Path, task: Json) -> None:
    path = _task_dir(root, task["task_id"]) / "task.json"
    if path.is_symlink():
        raise WorkerError("Task record must not be a symlink.")
    atomic_write_text(path, json.dumps(task, indent=2, ensure_ascii=False) + "\n")


def _result(root: Path, task: Json) -> Json:
    result = _read_json(_task_dir(root, task["task_id"]) / "result.json")
    if _digest(result) != task.get("result_digest"):
        raise WorkerError("Worker result record changed after submission.")
    if any(result.get(field) != task.get(field)
           for field in ("task_id", "attempt_id", "run_id", "plan_revision", "cycle", "execution_mode")):
        raise WorkerError("Worker result identity does not match dispatch.")
    return result


def _immutable(path: Path, value: Json) -> None:
    with path.open("x", encoding="utf-8") as handle:
        json.dump(value, handle, indent=2, ensure_ascii=False)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    path.chmod(0o444)


def list_tasks(root: Path) -> list[Json]:
    """Read coordinator-owned task records without scanning product files."""
    storage = _storage(root)
    if not storage.exists():
        return []
    return [_read_json(_task_dir(root, path.name) / "task.json")
            for path in sorted(storage.iterdir())
            if path.is_dir() and (path / "task.json").exists()]


def _revision(state: Json) -> object:
    return state.get("runtime_meta", {}).get("plan_revision", state.get("plan_revision", 0))


def _binding(state: Json) -> Json:
    return {"run_id": state.get("lease_run_id", ""),
            "plan_revision": _revision(state), "cycle": state.get("cycle", "C0"),
            "execution_mode": state.get("runtime_meta", {}).get("execution_mode", "delegated")}


def _milestone(state: Json, milestone_id: str) -> Json:
    for milestone in state.get("milestones", []):
        if milestone.get("id") == milestone_id:
            return milestone
    raise WorkerError(f"Unknown milestone {milestone_id!r}.")


def _checks(milestone: Json) -> list[Json]:
    checks = []
    for number, item in enumerate(milestone.get("acceptance", []), 1):
        if not isinstance(item, str) or not item.strip():
            raise WorkerError("Milestone acceptance must contain nonempty exact commands.")
        checks.append({"id": f"check-{number}", "command": item, "required": True})
    return checks


def _current(root: Path, state: Json, data: Json, *, statuses: set[str] | None = None) -> Json:
    task = _read_json(_task_dir(root, data.get("task_id")) / "task.json")
    if not data.get("attempt_id") or data["attempt_id"] != task["attempt_id"]:
        raise WorkerError("attempt_id is required and must match the active dispatch.")
    for key in ("run_id", "plan_revision", "cycle", "execution_mode", "milestone_id"):
        if key in data and data[key] != task.get(key):
            raise WorkerError(f"Submitted {key} does not match the dispatch.")
    if state.get("status") == "stopped":
        raise WorkerError("Workflow is stopped; preserve the result and resume before accepting it.")
    for key, expected in _binding(state).items():
        if task.get(key) != expected:
            raise WorkerError(f"Stale worker result: {key} changed; dispatch a new task.")
    if task.get("milestone_id"):
        if task["milestone_id"] != state.get("current_milestone_id"):
            raise WorkerError("Stale worker result: current milestone changed.")
        milestone = _milestone(state, task["milestone_id"])
        if task["milestone_digest"] != _digest({key: milestone.get(key, [])
                                               for key in ("deliverables", "write_scope", "read_dependencies", "acceptance")}):
            raise WorkerError("Stale worker result: milestone contract changed.")
    if task.get("status") not in (statuses if statuses is not None else _OPEN):
        raise WorkerError(f"Task is {task.get('status')}; duplicate or late submission rejected.")
    return task


def _snapshot(project: Path, extra: list[str] | None = None) -> Json:
    """Track file contents/modes plus index entries, including existing edits.

    Git repositories include tracked and nonignored untracked files. Explicit
    contract paths are included even when ignored. Non-Git workspaces are walked.
    Cache/scratch/control directories are excluded; no symlinks are followed.
    """
    index: dict[str, list[str]] = {}
    try:
        found = subprocess.run(["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard"],
                               cwd=project, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                               timeout=20, check=False)
        if found.returncode:
            raise OSError("not a git workspace")
        names = set(os.fsdecode(name) for name in found.stdout.split(b"\0") if name)
        stages = subprocess.run(["git", "ls-files", "--stage", "-z"], cwd=project,
                                stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                                timeout=20, check=True)
        for entry in stages.stdout.split(b"\0"):
            if entry:
                metadata, name = os.fsdecode(entry).split("\t", 1)
                index.setdefault(name, []).append(metadata)
    except (OSError, subprocess.SubprocessError):
        names = set()
        for parent, dirs, files in os.walk(project, followlinks=False):
            dirs[:] = [name for name in dirs if name not in _CONTROL | _CACHE
                       and not (Path(parent) / name).is_symlink()]
            names.update((Path(parent) / name).relative_to(project).as_posix() for name in files)
    names.update(extra or [])
    result: Json = {}
    for name in sorted(names):
        parts = PurePosixPath(name).parts
        if not parts or parts[0] in _CONTROL or any(part in _CACHE for part in parts):
            continue
        path = project / name
        # Avoid following symlinked parents even for newly substituted directories.
        if any((project.joinpath(*parts[:count])).is_symlink() for count in range(1, len(parts))):
            result[name] = {"kind": "symlink-parent", "index": index.get(name, [])}
        elif path.is_symlink():
            result[name] = {"kind": "symlink", "target": os.readlink(path), "index": index.get(name, [])}
        elif path.is_file():
            result[name] = {"kind": "file", "sha256": _file_digest(path),
                            "mode": stat.S_IMODE(path.stat().st_mode), "index": index.get(name, [])}
        elif path.exists():
            result[name] = {"kind": "directory", "index": index.get(name, [])}
        elif name in index:
            result[name] = {"kind": "deleted", "index": index[name]}
    return result


def _extra(root: Path, state: Json) -> list[str]:
    return sorted({path for task in list_tasks(root)
                   if all(task.get(key) == value for key, value in _binding(state).items())
                   for path in task["write_scope"] + task["read_dependencies"] + task["deliverables"]})


def _changes(before: Json, after: Json) -> list[str]:
    return sorted(path for path in set(before) | set(after) if before.get(path) != after.get(path))


def _scope_check(root: Path, state: Json, task: Json, snapshot: Json) -> list[str]:
    baseline = _read_json(_task_dir(root, task["task_id"]) / "baseline.json")
    if _digest(baseline) != task["baseline_digest"]:
        raise WorkerError("Dispatch baseline record changed.")
    changed = _changes(baseline, snapshot)
    own = set(task["write_scope"])
    others = {path for peer in list_tasks(root)
              if peer["task_id"] != task["task_id"] and peer["status"] in _OPEN | {"accepted"}
              and peer["milestone_id"] == task["milestone_id"]
              and all(peer.get(key) == value for key, value in _binding(state).items())
              for path in peer["write_scope"]}
    deviations = sorted(set(changed) - own - others)
    if deviations:
        raise WorkerError("Out-of-scope changes require coordinator resolution: " + ", ".join(deviations))
    # Index mutation is prohibited even when the working-tree file is in scope.
    staged = [name for name in changed
              if baseline.get(name, {}).get("index", []) != snapshot.get(name, {}).get("index", [])]
    if staged:
        raise WorkerError("Git index changed during task; coordinator must resolve: " + ", ".join(staged))
    for path in task["write_scope"] + task["read_dependencies"] + task["deliverables"]:
        _path(root.parent, path)
    return sorted(set(changed) & own)


def create_task(root: Path, state: Json, data: Json) -> Json:
    """Register one dispatch before spawning its worker; IDs cannot be reused."""
    role = str(data.get("role", ""))
    allowed = {"implementer": {"EXECUTING"}, "verifier": {"REVIEWING"},
               "explorer": {"PLANNING", "PLANNED", "EXECUTING", "REVIEWING", "DEBUGGING", "FINISHED"}}
    if role not in allowed or state.get("phase") not in allowed[role]:
        raise WorkerError(f"Cannot dispatch role {role!r} in phase {state.get('phase')}.")
    if state.get("status") == "stopped":
        raise WorkerError("Cannot dispatch while workflow is stopped.")
    if role != "explorer" and not state.get("lease_run_id"):
        raise WorkerError("Execution workers require an active run_id.")
    project = Path(root).parent
    task_id = _id(data.get("task_id"), "task_id")
    destination = _task_dir(root, task_id)
    if destination.exists():
        raise WorkerError("task_id already exists; retry with a new task_id and retry_of.")
    agent_id = str(data.get("agent_id") or "").strip()
    if not agent_id or not str(data.get("objective") or "").strip():
        raise WorkerError("Dispatch requires agent_id and objective.")
    milestone_id = str(data.get("milestone_id", state.get("current_milestone_id", "")) or "")
    if role != "explorer" and not milestone_id:
        raise WorkerError("Implementer/verifier requires the current milestone.")
    if milestone_id and milestone_id != state.get("current_milestone_id"):
        raise WorkerError("Only the current milestone may dispatch workers.")
    milestone = _milestone(state, milestone_id) if milestone_id else {}
    deliverables = _paths(project, data.get("deliverables", milestone.get("deliverables", [])), "deliverables")
    scope = _paths(project, data.get("write_scope", deliverables if role == "implementer" else []), "write_scope")
    dependencies = _paths(project, data.get("read_dependencies", milestone.get("read_dependencies", [])), "read_dependencies")
    if role != "implementer" and scope:
        raise WorkerError("Explorer/verifier must have empty product write_scope.")
    if role == "implementer":
        permitted = _paths(project, milestone.get("write_scope", milestone.get("deliverables", [])), "milestone write_scope")
        if set(scope) - set(permitted) or set(deliverables) - set(permitted):
            raise WorkerError("Worker write scope/deliverables exceed the frozen milestone scope.")
    for peer in list_tasks(root):
        if peer["status"] != "running" and not (role == "implementer" and peer["status"] == "ready_for_review"):
            continue
        overlap = ((set(scope) & (set(peer["write_scope"]) | set(peer["read_dependencies"])))
                   | (set(dependencies) & set(peer["write_scope"])))
        if overlap:
            raise WorkerError("Concurrent write/dependency conflict with " + peer["task_id"] + ": " + ", ".join(sorted(overlap)))
    checks = _checks(milestone)
    selected = data.get("acceptance_ids", [check["id"] for check in checks])
    if (not isinstance(selected, list) or not all(isinstance(item, str) for item in selected)
            or set(selected) - {check["id"] for check in checks}):
        raise WorkerError("acceptance_ids must select existing milestone acceptance IDs.")
    reviews = data.get("reviews_task_ids", [])
    if (not isinstance(reviews, list) or not all(isinstance(item, str) for item in reviews)
            or len(set(reviews)) != len(reviews)):
        raise WorkerError("reviews_task_ids must be a unique list.")
    if role == "verifier":
        if not reviews:
            raise WorkerError("Verifier requires reviews_task_ids.")
        for reviewed_id in reviews:
            reviewed = _read_json(_task_dir(root, reviewed_id) / "task.json")
            _current(root, state, reviewed, statuses={"ready_for_review", "accepted"})
            same_agent = state.get("runtime_meta", {}).get("execution_mode") == "single_agent"
            if reviewed["role"] != "implementer" or (reviewed["agent_id"] == agent_id and not same_agent):
                raise WorkerError("Verifier must be independent of every reviewed implementer.")
    elif reviews:
        raise WorkerError("Only a verifier may have reviews_task_ids.")
    task: Json = {"schema_version": 1, "task_id": task_id,
                  "attempt_id": _id(data.get("attempt_id", "attempt-" + secrets.token_hex(6)), "attempt_id"),
                  **_binding(state), "milestone_id": milestone_id,
                  "milestone_digest": _digest({key: milestone.get(key, []) for key in ("deliverables", "write_scope", "read_dependencies", "acceptance")}),
                  "role": role, "agent_id": agent_id, "objective": str(data["objective"]),
                  "review_mode": "same_agent" if state.get("runtime_meta", {}).get("execution_mode") == "single_agent" else "independent",
                  "deliverables": deliverables, "write_scope": scope, "read_dependencies": dependencies,
                  "acceptance": [check for check in checks if check["id"] in selected],
                  "reviews_task_ids": reviews, "retry_of": str(data.get("retry_of") or ""),
                  "status": "running", "created_at": _now(), "validation": [],
                  "scratch": f".mary-workflow-worker/{task_id}"}
    baseline = _snapshot(project, _extra(root, state) + scope + dependencies + deliverables)
    scratch_root = project / ".mary-workflow-worker"
    if scratch_root.is_symlink() or (scratch_root / task_id).is_symlink():
        raise WorkerError("Worker scratch must not be a symlink.")
    (scratch_root / task_id).mkdir(parents=True, exist_ok=True)
    destination.mkdir(parents=True)
    _immutable(destination / "baseline.json", baseline)
    task["baseline_digest"] = _digest(baseline)
    _save(root, task)
    return task


def _fresh_state(root: Path, fallback: Json) -> Json:
    if (root / "state.yaml").exists():
        # Lazy import keeps the evidence helpers independently testable.
        from mary_workflow import read_state
        return read_state(root)
    return fallback


def _terminate(process: subprocess.Popen) -> None:
    try:
        if os.name == "posix":
            os.killpg(process.pid, signal.SIGKILL)
        else:
            process.kill()
    except ProcessLookupError:
        pass
    process.wait()


def run_validation(root: Path, state: Json, data: Json) -> Json:
    """Execute a frozen acceptance command without blocking workflow stop.

    Initial/final record mutations hold the coordinator lock; the subprocess does
    not. Actual state and cancellation are rechecked during and after execution.
    The caller must apply host permissions to the plan-authorized shell command.
    """
    with workflow_lock(root):
        state = _fresh_state(root, state)
        task = _current(root, state, data)
        if task.get("active_validation"):
            raise WorkerError("A validation is already running for this task.")
        if "result" in data or "exit_code" in data:
            raise WorkerError("Validation status is recorded by execution, never supplied by a worker.")
        check = next((item for item in task["acceptance"] if item["id"] == data.get("acceptance_id")), None)
        if not check or ("command" in data and data["command"] != check["command"]):
            raise WorkerError("Validation must use an assigned acceptance ID and its exact frozen command.")
        try:
            timeout = float(data.get("timeout_seconds", 300))
        except (TypeError, ValueError) as exc:
            raise WorkerError("timeout_seconds must be a finite positive number.") from exc
        if not 0 < timeout <= 86400:
            raise WorkerError("timeout_seconds must be between 0 and 86400.")
        before = _snapshot(root.parent, _extra(root, state))
        _scope_check(root, state, task, before)
        evidence_id = "check-" + secrets.token_hex(10)
        directory = _task_dir(root, task["task_id"])
        stdout = directory / (evidence_id + ".stdout.log")
        stderr = directory / (evidence_id + ".stderr.log")
        started = time.monotonic()
        with stdout.open("xb") as out, stderr.open("xb") as err:
            process = subprocess.Popen(check["command"], shell=True, cwd=root.parent,
                                       stdout=out, stderr=err, start_new_session=True)
        task["active_validation"] = {
            "evidence_id": evidence_id, "pid": process.pid,
            "process_group_id": process.pid, "isolated_process_group": os.name == "posix",
            "coordinator_pid": os.getpid(), "platform": os.name,
            "acceptance_id": check["id"], "command": check["command"],
            "cwd": str(root.parent.resolve()), "snapshot_digest": _digest(before),
            "started_at": _now(),
        }
        _save(root, task)
    timed_out = False
    interruption = ""
    try:
        while process.poll() is None:
            remaining = timeout - (time.monotonic() - started)
            if remaining <= 0:
                timed_out = True
                _terminate(process)
                break
            try:
                process.wait(timeout=min(remaining, 0.25))
            except subprocess.TimeoutExpired:
                with workflow_lock(root):
                    try:
                        _current(root, _fresh_state(root, state), data)
                    except WorkerError as exc:
                        interruption = str(exc)
                if interruption:
                    _terminate(process)
                    break
    except BaseException:
        _terminate(process)
        raise
    duration_ms = round((time.monotonic() - started) * 1000)
    with workflow_lock(root):
        fresh = _fresh_state(root, state)
        try:
            current = _current(root, fresh, data)
        except WorkerError as exc:
            interruption = str(exc)
            current = _read_json(directory / "task.json")
        after = _snapshot(root.parent, _extra(root, fresh))
        evidence: Json = {"schema_version": 1, "evidence_id": evidence_id,
                          "task_id": task["task_id"], "attempt_id": task["attempt_id"],
                          **{key: task[key] for key in _binding(state)},
                          "acceptance_id": check["id"], "command": check["command"],
                          "cwd": str(root.parent.resolve()), "exit_code": process.returncode,
                          "result": "cancelled" if interruption else ("timeout" if timed_out else ("passed" if process.returncode == 0 else "failed")),
                          "summary": interruption or ("Timed out" if timed_out else f"Process exited {process.returncode}"),
                          "duration_ms": duration_ms, "created_at": _now(),
                          "snapshot_digest": _digest(before), "after_snapshot_digest": _digest(after),
                          "stdout": stdout.name, "stderr": stderr.name,
                          "stdout_sha256": _file_digest(stdout), "stderr_sha256": _file_digest(stderr)}
        stdout.chmod(0o444)
        stderr.chmod(0o444)
        _immutable(directory / (evidence_id + ".json"), evidence)
        current.pop("active_validation", None)
        current["validation"].append(evidence_id)
        _save(root, current)
    return evidence


# Recording evidence always means executing the command, never importing claims.
record_validation = run_validation


def _absent_pid(pid: object, *, group: bool, label: str) -> int:
    if isinstance(pid, bool) or not isinstance(pid, int) or not 1 < pid <= 2**31 - 1:
        raise WorkerError(f"Recovery requires a valid recorded {label}; inspect the receipt without guessing a PID.")
    try:
        (os.killpg if group else os.kill)(pid, 0)
    except ProcessLookupError:
        return pid
    except PermissionError as exc:
        raise WorkerError(f"Cannot prove recorded {label} {pid} absent: permission denied; do not clear the receipt.") from exc
    except OSError as exc:
        raise WorkerError(f"Cannot prove recorded {label} {pid} absent: {exc}; do not clear the receipt.") from exc
    raise WorkerError(f"Recorded {label} {pid} still exists (or its ID was reused). Stop or wait for it through its owner; recovery will not kill it.")


def recover_validation(root: Path, state: Json, data: Json) -> Json:
    """Resolve a crashed runner's receipt only after its known processes vanish.

    Recovery is administrative: it can run while stopped or on an old run. It
    never authorizes execution or reconstructs a passing result. Live/reused PIDs,
    inaccessible processes, unsupported platforms, and incomplete legacy receipts
    are refused conservatively; no process is killed by this function.
    """
    with workflow_lock(root):
        state = _fresh_state(root, state)
        directory = _task_dir(root, data.get("task_id"))
        task = _read_json(directory / "task.json")
        if not data.get("attempt_id") or data["attempt_id"] != task["attempt_id"]:
            raise WorkerError("Recovery attempt_id must match the recorded dispatch.")
        for key in ("run_id", "plan_revision", "cycle", "execution_mode", "milestone_id"):
            if key in data and data[key] != task.get(key):
                raise WorkerError(f"Recovery {key} does not match the recorded dispatch.")
        receipt = task.get("active_validation")
        if not isinstance(receipt, dict) or not receipt:
            raise WorkerError("Task has no active_validation receipt to recover.")
        original_id = _id(receipt.get("evidence_id"), "active_validation.evidence_id")
        if (os.name != "posix" or not hasattr(os, "killpg") or receipt.get("platform") != "posix"
                or receipt.get("isolated_process_group") is not True):
            raise WorkerError("Cannot prove process absence for this platform or legacy receipt; inspect it through the original host without clearing it speculatively.")
        if receipt.get("process_group_id") != receipt.get("pid"):
            raise WorkerError("Recorded validation group is not its isolated leader; manual host diagnosis required.")
        coordinator_pid = _absent_pid(receipt.get("coordinator_pid"), group=False, label="coordinator PID")
        process_id = _absent_pid(receipt.get("pid"), group=False, label="validation PID")
        process_group = _absent_pid(receipt.get("process_group_id"), group=True, label="validation process group")
        check = next((check for check in task["acceptance"] if check["id"] == receipt.get("acceptance_id")), None)
        if not check or receipt.get("command") != check["command"]:
            raise WorkerError("Recovery receipt must identify the exact assigned acceptance command.")
        if receipt.get("cwd") != str(root.parent.resolve()):
            raise WorkerError("Recovery receipt working directory differs from the project; inspect the original host.")
        logs: Json = {}
        missing = []
        for stream in ("stdout", "stderr"):
            path = directory / f"{original_id}.{stream}.log"
            if path.is_symlink() or (path.exists() and not path.is_file()):
                raise WorkerError("Recovery log must be an ordinary file inside its task directory.")
            logs[stream] = path.name
            logs[stream + "_sha256"] = _file_digest(path) if path.is_file() else None
            if not path.is_file():
                missing.append(stream)
        original_evidence = directory / (original_id + ".json")
        if original_evidence.is_symlink() or (original_evidence.exists() and not original_evidence.is_file()):
            raise WorkerError("Original evidence reference is not an ordinary task record.")
        evidence_id = "recovery-" + secrets.token_hex(10)
        evidence: Json = {
            "schema_version": 1, "kind": "validation_crash_recovery", "evidence_id": evidence_id,
            "original_evidence_id": original_id,
            **{key: task[key] for key in ("task_id", "attempt_id", "run_id", "plan_revision", "cycle", "execution_mode")},
            "acceptance_id": check["id"], "command": check["command"], "cwd": receipt["cwd"],
            "result": "interrupted", "exit_code": None, "duration_ms": None,
            "summary": "Recovered interrupted validation after recorded coordinator, process and group were absent; no successful outcome inferred.",
            "reason": str(data.get("reason") or "Coordinator crashed before final evidence persistence."),
            "created_at": _now(), "started_at": receipt.get("started_at"),
            "snapshot_digest": receipt.get("snapshot_digest"),
            "after_snapshot_digest": _digest(_snapshot(root.parent, _extra(root, state))),
            "coordinator_pid": coordinator_pid, "pid": process_id, "process_group_id": process_group,
            "absence_verified": True, "missing_logs": missing, **logs,
            "original_evidence_sha256": _file_digest(original_evidence) if original_evidence.is_file() else None,
        }
        _immutable(directory / (evidence_id + ".json"), evidence)
        for stream in ("stdout", "stderr"):
            path = directory / logs[stream]
            if path.is_file():
                path.chmod(0o444)
        task.setdefault("validation", []).append(evidence_id)
        task.pop("active_validation")
        status = "cancelled" if state.get("status") == "stopped" or task.get("status") == "cancelled" else "failed"
        task.update(status=status, recovered_at=_now(), recovery_evidence_id=evidence_id,
                    recovery_reason=evidence["reason"])
        _save(root, task)
        return {**task, "recovery_evidence": evidence}


def _evidence(root: Path, task: Json, evidence_id: object, digest: str) -> Json:
    key = _id(evidence_id, "evidence_id")
    if key not in task["validation"]:
        raise WorkerError("Evidence is not registered to this task.")
    directory = _task_dir(root, task["task_id"])
    evidence = _read_json(directory / (key + ".json"))
    if any(evidence.get(field) != task[field] for field in ("task_id", "attempt_id", "run_id", "plan_revision", "cycle", "execution_mode")):
        raise WorkerError("Evidence identity does not match the dispatch.")
    check = next((check for check in task["acceptance"] if check["id"] == evidence.get("acceptance_id")), None)
    if not check or evidence.get("command") != check["command"]:
        raise WorkerError("Evidence command does not match frozen acceptance.")
    for stream in ("stdout", "stderr"):
        name = evidence.get(stream)
        if name != key + f".{stream}.log":
            raise WorkerError("Invalid validation log reference.")
        path = directory / name
        if path.is_symlink() or not path.is_file() or _file_digest(path) != evidence.get(stream + "_sha256"):
            raise WorkerError("Missing or changed raw validation log.")
    if evidence.get("snapshot_digest") != digest or evidence.get("after_snapshot_digest") != digest:
        raise WorkerError("Validation evidence is stale or its command changed product files; rerun after writes stabilize.")
    return evidence


def submit_result(root: Path, state: Json, data: Json) -> Json:
    """Receive an immutable worker envelope, but do not accept the milestone."""
    task = _current(root, state, data, statuses={"running"})
    if task.get("active_validation"):
        raise WorkerError("Wait for active validation before submitting a result.")
    status = data.get("status")
    if status not in {"ready_for_review", "blocked", "failed"}:
        raise WorkerError("Worker status must be ready_for_review, blocked, or failed.")
    if not str(data.get("summary") or "").strip():
        raise WorkerError("Worker result requires a concrete summary.")
    for field in ("files_changed", "validation", "scope_deviations", "blockers", "uncertainties"):
        if not isinstance(data.get(field, []), list):
            raise WorkerError(f"{field} must be a list.")
    if status in {"blocked", "failed"} and not data.get("blockers"):
        raise WorkerError("Blocked/failed result requires concrete blockers and attempted remedies.")
    snapshot = _snapshot(root.parent, _extra(root, state))
    issues: list[str] = []
    observed_deviations: list[str] = []
    if status == "ready_for_review":
        actual = _scope_check(root, state, task, snapshot)
        declared = _paths(root.parent, data.get("files_changed", []), "files_changed")
        if actual != declared:
            raise WorkerError(f"files_changed differs from dispatch baseline; actual paths: {actual}.")
        if data.get("scope_deviations"):
            raise WorkerError("Resolve scope_deviations explicitly before receiving a ready result.")
    else:
        # Preserve failure diagnostics, including unsafe reported strings, without
        # using any caller-provided path to read filesystem data. Observed paths
        # come exclusively from our snapshots; failures can never be accepted.
        baseline = _read_json(_task_dir(root, task["task_id"]) / "baseline.json")
        if _digest(baseline) != task["baseline_digest"]:
            raise WorkerError("Dispatch baseline record changed; preserve the raw envelope for coordinator diagnosis.")
        peers = {path for peer in list_tasks(root)
                 if peer["task_id"] != task["task_id"] and peer["milestone_id"] == task["milestone_id"]
                 and peer["status"] in _OPEN | {"accepted"}
                 and all(peer.get(key) == value for key, value in _binding(state).items())
                 for path in peer["write_scope"]}
        actual = sorted(set(_changes(baseline, snapshot)) - peers)
        observed_deviations = sorted(set(actual) - set(task["write_scope"]))
        try:
            _scope_check(root, state, task, snapshot)
        except WorkerError as exc:
            issues.append(str(exc))
        try:
            declared = _paths(root.parent, data.get("files_changed", []), "files_changed")
            if actual != declared:
                issues.append("Reported files_changed differs from observed product snapshot.")
        except WorkerError as exc:
            issues.append(str(exc))
    validation = data.get("validation", [])
    if not all(isinstance(item, str) for item in validation):
        raise WorkerError("validation must list evidence IDs returned by run_validation.")
    if len(set(validation)) != len(validation):
        raise WorkerError("Duplicate validation evidence IDs.")
    digest = _digest(snapshot)
    for evidence_id in validation:
        try:
            _evidence(root, task, evidence_id, digest)
        except WorkerError as exc:
            if status == "ready_for_review":
                raise
            issues.append(str(exc))
    if task["role"] == "verifier" and status == "ready_for_review":
        if task["review_mode"] == "same_agent" and data.get("review_mode") != "same_agent":
            raise WorkerError("Single-agent review must explicitly declare review_mode=same_agent; independence is unavailable.")
        if data.get("decision") not in {"passed", "needs-fix"} or not isinstance(data.get("findings"), list):
            raise WorkerError("Verifier requires decision=passed|needs-fix and a findings list.")
        if data["decision"] == "needs-fix" and not data["findings"]:
            raise WorkerError("A needs-fix decision requires concrete findings.")
    result: Json = {"schema_version": 1, "task_id": task["task_id"], "attempt_id": task["attempt_id"],
                    **_binding(state), "status": status, "summary": str(data["summary"]),
                    "files_changed": actual, "validation": validation,
                    "scope_deviations": data.get("scope_deviations", []),
                    "blockers": data.get("blockers", []), "uncertainties": data.get("uncertainties", []),
                    "snapshot_digest": digest, "submitted_at": _now()}
    if status != "ready_for_review":
        result.update(reported_files_changed=data.get("files_changed", []),
                      observed_scope_deviations=observed_deviations, contract_issues=issues)
    if task["role"] == "verifier" and status == "ready_for_review":
        result.update(decision=data["decision"], findings=data["findings"],
                      review_mode=task["review_mode"], reviews_task_ids=task["reviews_task_ids"])
    _immutable(_task_dir(root, task["task_id"]) / "result.json", result)
    task.update(status=status, submitted_at=result["submitted_at"], result_digest=_digest(result))
    _save(root, task)
    return {**task, "result": result}


def verify_milestone_evidence(root: Path, state: Json, milestone: Json, data: Json) -> Json:
    """Validate every required exact check against current product and raw logs."""
    task_ids = data.get("task_ids")
    if (not isinstance(task_ids, list) or not task_ids or not all(isinstance(item, str) for item in task_ids)
            or len(set(task_ids)) != len(task_ids)):
        raise WorkerError("Milestone completion requires a nonempty unique task_ids list.")
    if milestone.get("id") != state.get("current_milestone_id"):
        raise WorkerError("Only the current milestone can be completed.")
    snapshot = _snapshot(root.parent, _extra(root, state))
    digest = _digest(snapshot)
    peers = [task for task in list_tasks(root)
             if task["role"] == "implementer" and task["milestone_id"] == milestone["id"]
             and all(task.get(key) == value for key, value in _binding(state).items())]
    if any(task["status"] == "running" for task in peers):
        raise WorkerError("Implementation workers are still running; settle every writer before completion.")
    unreviewed = {task["task_id"] for task in peers if task["status"] == "ready_for_review"} - set(task_ids)
    if unreviewed:
        raise WorkerError("Completion omits implementation tasks: " + ", ".join(sorted(unreviewed)))
    covered: set[str] = set()
    validation = []
    files: set[str] = set()
    for task_id in task_ids:
        task = _read_json(_task_dir(root, task_id) / "task.json")
        _current(root, state, task, statuses={"ready_for_review", "accepted"})
        if task["role"] != "implementer" or task["milestone_id"] != milestone["id"]:
            raise WorkerError("Milestone evidence must come from its implementer tasks.")
        _scope_check(root, state, task, snapshot)
        result = _result(root, task)
        if result.get("status") != "ready_for_review" or result.get("snapshot_digest") != digest:
            raise WorkerError("Worker result is stale or not ready for review; dispatch a new attempt.")
        files.update(result["files_changed"])
        for evidence_id in result["validation"]:
            evidence = _evidence(root, task, evidence_id, digest)
            if evidence["result"] != "passed" or evidence["exit_code"] != 0:
                raise WorkerError("Required validation did not pass: " + evidence["acceptance_id"])
            covered.add(evidence["acceptance_id"])
            validation.append(evidence)
    missing = {check["id"] for check in _checks(milestone)} - covered
    if missing:
        raise WorkerError("Missing executed passing acceptance evidence: " + ", ".join(sorted(missing)))
    return {"task_ids": task_ids, "files_changed": sorted(files), "validation": validation,
            "snapshot_digest": digest}


def verify_review_evidence(root: Path, state: Json, milestone: Json, data: Json) -> Json:
    """Require a separate worker's current, product-preserving review."""
    task = _read_json(_task_dir(root, data.get("verifier_task_id")) / "task.json")
    _current(root, state, task, statuses={"ready_for_review", "accepted"})
    if task["role"] != "verifier" or task["milestone_id"] != milestone.get("id"):
        raise WorkerError("Review requires an independent verifier task for the current milestone.")
    summary = verify_milestone_evidence(root, state, milestone, {"task_ids": task["reviews_task_ids"]})
    result = _result(root, task)
    if (result.get("status") != "ready_for_review" or result.get("decision") != "passed"
            or result.get("snapshot_digest") != summary["snapshot_digest"]):
        raise WorkerError("Verifier has not passed the current product snapshot.")
    if task["baseline_digest"] != summary["snapshot_digest"]:
        raise WorkerError("Product changed during independent review; dispatch a fresh review.")
    for reviewed_id in task["reviews_task_ids"]:
        reviewed = _read_json(_task_dir(root, reviewed_id) / "task.json")
        if reviewed["agent_id"] == task["agent_id"] and result.get("review_mode") != "same_agent":
            raise WorkerError("An implementer cannot approve its own work.")
    return {**summary, "verifier_task_id": task["task_id"], "review": result,
            "independent_review": result.get("review_mode") == "independent"}


def accept_tasks(root: Path, state: Json, task_ids: list[str]) -> None:
    """Close verified records while the coordinator still holds current binding.

    Call only after all transition validation, before advancing the milestone or
    clearing run_id. The outer coordinator serializes this with the state write.
    """
    tasks = []
    for task_id in task_ids:
        task = _read_json(_task_dir(root, task_id) / "task.json")
        _current(root, state, task, statuses={"ready_for_review", "accepted"})
        tasks.append(task)
    for task in tasks:
        if task["status"] == "accepted":
            continue  # Recover a state-write failure after task records closed.
        task.update(status="accepted", accepted_at=_now())
        _save(root, task)


def cancel_tasks(root: Path, reason: str = "stopped", *, include_ready: bool = True) -> list[str]:
    """Cancel active dispatches; the host must also interrupt actual workers.

    A pause may preserve previously submitted ready records using include_ready
    false. Those records still require identical run/revision/product snapshots
    when resumed. Rework/replanning invalidates all open results by default.
    """
    cancelled = []
    for task in list_tasks(root):
        if task["status"] == "running" or (task["status"] == "ready_for_review"
                                             and (include_ready or task.get("active_validation"))):
            task.update(status="cancelled", cancelled_at=_now(), cancel_reason=reason)
            _save(root, task)
            cancelled.append(task["task_id"])
    return cancelled
