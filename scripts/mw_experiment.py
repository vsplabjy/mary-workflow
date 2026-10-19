#!/usr/bin/env python3
"""Lightweight experiment runs, independent of milestone state and bundle audits."""
from __future__ import annotations

import argparse
import base64
from contextlib import contextmanager
from datetime import datetime, timezone
import fcntl
import hashlib
import json
import math
import os
from pathlib import Path
import re
import signal
import subprocess
import sys
import tempfile
import threading
import time

from mw_runtime import atomic_write_text, ensure_workflow_gitignore

TERMINAL = {"completed", "failed", "stopped"}
MAX_CONFIG_BYTES = 1024 * 1024
MAX_METRICS_BYTES = 1024 * 1024


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


def identifier(value: str) -> str:
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,100}", value) or value in {".", ".."}:
        raise ValueError("Invalid run ID; use letters, numbers, dots, underscores or hyphens.")
    return value


def runs_root(project: Path) -> Path:
    project = project.resolve()
    root = project / ".mary-workflow" / "experiments"
    if not root.resolve().is_relative_to(project):
        raise ValueError("Experiment records cannot escape the project through symlinks.")
    return root


def run_path(project: Path, run_id: str) -> Path:
    return runs_root(project) / identifier(run_id)


def save(folder: Path, record: dict) -> None:
    atomic_write_text(folder / "run.json", json.dumps(record, ensure_ascii=False, indent=2) + "\n")


def read(folder: Path) -> dict:
    return json.loads((folder / "run.json").read_text(encoding="utf-8"))


@contextmanager
def locked(folder: Path):
    folder.mkdir(parents=True, exist_ok=True)
    with (folder / ".lock").open("a") as stream:
        fcntl.flock(stream, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(stream, fcntl.LOCK_UN)


def process_identity(pid: int | None) -> str | None:
    """Linux PID + boot ID + start ticks. Zombies count as exited."""
    if not pid:
        return None
    try:
        stat = Path(f"/proc/{pid}/stat").read_text()
        fields = stat[stat.rfind(")") + 2:].split()
        if fields[0] == "Z":
            return None
        boot = Path("/proc/sys/kernel/random/boot_id").read_text().strip()
        return f"{boot}:{pid}:{fields[19]}"
    except (OSError, IndexError):
        return None


def alive(pid: int | None, identity: str | None) -> bool:
    return bool(identity and process_identity(pid) == identity)


def status(project: Path, run_id: str) -> dict:
    folder = run_path(project, run_id)
    result = read(folder)
    if result["execution_status"] not in TERMINAL:
        if not alive(result.get("supervisor_pid"), result.get("supervisor_identity")):
            result["execution_status"] = "unknown"
            result["observation"] = "Supervisor absent; reconcile the recorded child before retrying."
    result["stop_requested"] = (folder / "USER_STOP").exists()
    return result


def code_version(project: Path) -> str | None:
    try:
        result = subprocess.run(["git", "rev-parse", "HEAD"], cwd=project,
                                capture_output=True, text=True, timeout=1)
        return result.stdout.strip() if result.returncode == 0 else None
    except (OSError, subprocess.TimeoutExpired):
        return None


def start_run(project: Path, argv: list[str], *, run_id: str | None = None,
              config: Path | None = None, resource: str | None = None,
              timeout: float | None = None, output_dir: Path | None = None,
              metrics_file: Path | None = None) -> dict:
    started = time.monotonic()
    if not sys.platform.startswith("linux"):
        raise ValueError("Experiment process supervision currently requires Linux /proc.")
    project = project.resolve()
    if not project.is_dir() or not argv:
        raise ValueError("A project directory and executable argv are required.")
    if timeout is not None and (not math.isfinite(timeout) or timeout <= 0):
        raise ValueError("Timeout must be a finite positive number.")
    if resource is not None and (not resource.strip() or len(resource.encode()) > 128):
        raise ValueError("Resource must be a nonempty identifier of at most 128 bytes.")
    config_info = None
    config_bytes = None
    if config:
        config = (project / config).resolve()
        stat = config.stat()
        if not config.is_file():
            raise ValueError("Config must be a regular file.")
        config_info = {"path": str(config), "size": stat.st_size, "mtime_ns": stat.st_mtime_ns}
        if stat.st_size <= MAX_CONFIG_BYTES:
            with config.open("rb") as stream:
                config_bytes = stream.read(MAX_CONFIG_BYTES + 1)
            if len(config_bytes) > MAX_CONFIG_BYTES:
                raise ValueError("Config grew beyond the snapshot limit; retry with a stable config.")
            config_info["snapshot"] = "config.snapshot"
        else:
            config_info["snapshot"] = None
            config_info["note"] = "Larger than snapshot limit; content was not read."
    ensure_workflow_gitignore(project)
    root = runs_root(project)
    root.mkdir(parents=True, exist_ok=True)
    run_id = identifier(run_id or (datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S") + "-" + os.urandom(4).hex()))
    folder = root / run_id
    # Exclusive creation makes concurrent requests using the same ID fail closed.
    folder.mkdir()
    output = (project / output_dir).resolve() if output_dir else folder / "output"
    try:
        output.mkdir(parents=True, exist_ok=False)
    except BaseException:
        folder.rmdir()
        raise
    with locked(folder):
        if config_bytes is not None:
            (folder / "config.snapshot").write_bytes(config_bytes)
        record = {
            "experiment_schema": 1, "run_id": run_id, "argv": argv,
            "cwd": str(project), "created_at": now(), "execution_status": "starting",
            "assessment_status": "unreviewed", "provenance_status": "partial",
            "provenance_note": "Commit is a reference only; working tree and dependencies were not content-audited.",
            "git_commit": code_version(project), "config": config_info,
            "resource": resource, "timeout_seconds": timeout, "output_dir": str(output),
            "metrics_file": str((project / metrics_file).resolve()) if metrics_file else str(output / "metrics.json"),
            "stdout": str(folder / "stdout.log"), "stderr": str(folder / "stderr.log"),
            "exit_code": None, "stop_reason": None,
        }
        save(folder, record)
        # The supervisor survives the launching CLI and owns wait()/exit status.
        with (folder / "supervisor.log").open("ab") as log:
            supervisor = subprocess.Popen(
                [sys.executable, str(Path(__file__).resolve()), "--project", str(project), "_supervise", run_id],
                stdin=subprocess.DEVNULL, stdout=log, stderr=log, start_new_session=True,
            )
        threading.Thread(target=supervisor.wait, daemon=True).start()
        record.update(supervisor_pid=supervisor.pid, supervisor_identity=process_identity(supervisor.pid))
        record["launch_prepare_ms"] = round((time.monotonic() - started) * 1000, 3)
        save(folder, record)
    # Bounded startup handshake, not an experiment-completion wait.
    deadline = time.monotonic() + 3
    while time.monotonic() < deadline:
        result = status(project, run_id)
        if result["execution_status"] != "starting":
            return result
        time.sleep(0.02)
    return status(project, run_id)


@contextmanager
def resource_claim(resource: str | None, owner: dict):
    if not resource:
        yield
        return
    directory = Path(tempfile.gettempdir()) / f"mary-experiment-resources-{os.getuid()}"
    directory.mkdir(mode=0o700, exist_ok=True)
    key = base64.urlsafe_b64encode(resource.encode()).decode().rstrip("=")
    with (directory / (key + ".lock")).open("a+") as stream:
        try:
            fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise ValueError(f"Resource already claimed by another Mary experiment: {resource}") from exc
        stream.seek(0)
        previous = stream.read()
        if previous:
            peer = json.loads(previous)
            peer_folder = Path(peer["record_dir"])
            if (peer_folder / "run.json").exists():
                peer_record = read(peer_folder)
                if alive(peer_record.get("pid"), peer_record.get("process_identity")):
                    raise ValueError(f"Resource still has a live child from {peer_record['run_id']}: {resource}")
        stream.seek(0)
        stream.truncate()
        json.dump(owner, stream)
        stream.flush()
        try:
            yield
        finally:
            fcntl.flock(stream, fcntl.LOCK_UN)


def terminate(pid: int, identity: str | None) -> bool:
    if not alive(pid, identity):
        return False
    try:
        os.killpg(pid, signal.SIGTERM)
        deadline = time.monotonic() + 1
        while alive(pid, identity) and time.monotonic() < deadline:
            time.sleep(0.02)
        # Descendants may remain after the group leader exits.
        os.killpg(pid, signal.SIGKILL)
    except ProcessLookupError:
        pass
    return True


def supervise(project: Path, run_id: str) -> None:
    folder = run_path(project, run_id)
    with locked(folder):
        record = read(folder)
        if record["execution_status"] != "starting":
            return  # duplicate supervisor invocations cannot restart a run
        if (folder / "USER_STOP").exists():
            record.update(execution_status="stopped", stop_reason="USER_STOP", ended_at=now())
            save(folder, record)
            return
        if record.get("supervisor_pid") != os.getpid() or not alive(os.getpid(), record.get("supervisor_identity")):
            return  # only the supervisor registered by the launcher owns startup
    child = None
    try:
        with resource_claim(record.get("resource"), {"record_dir": str(folder)}):
            with locked(folder):
                record = read(folder)
                if (folder / "USER_STOP").exists():
                    record.update(execution_status="stopped", stop_reason="USER_STOP", ended_at=now())
                    save(folder, record)
                    return
                child_started = time.monotonic()
                env = os.environ.copy()
                env.update(MARY_RUN_ID=run_id, MARY_OUTPUT_DIR=record["output_dir"])
                with (folder / "stdout.log").open("ab") as out, (folder / "stderr.log").open("ab") as err:
                    child = subprocess.Popen(record["argv"], cwd=record["cwd"], env=env,
                                             stdin=subprocess.DEVNULL, stdout=out, stderr=err,
                                             start_new_session=True)
                record.update(pid=child.pid, process_identity=process_identity(child.pid),
                              execution_status="running", started_at=now())
                record["process_spawn_ms"] = round((time.monotonic() - child_started) * 1000, 3)
                save(folder, record)
            reason = None
            while child.poll() is None:
                if (folder / "USER_STOP").exists():
                    reason = "USER_STOP"
                elif record["timeout_seconds"] and time.monotonic() - child_started >= record["timeout_seconds"]:
                    reason = "TIMEOUT"
                if reason:
                    terminate(child.pid, record["process_identity"])
                    break
                time.sleep(0.1)
            exit_code = child.wait()
            with locked(folder):
                record = read(folder)
                # A stop arriving with normal exit must not be lost.
                if (folder / "USER_STOP").exists():
                    reason = "USER_STOP"
                record.update(exit_code=exit_code, ended_at=now(), stop_reason=reason,
                              execution_status=("stopped" if reason == "USER_STOP" else
                                                "failed" if reason or exit_code else "completed"),
                              process_elapsed_ms=round((time.monotonic() - child_started) * 1000, 3))
                save(folder, record)
    except Exception as exc:
        if child is not None and child.poll() is None:
            terminate(child.pid, process_identity(child.pid))
            child.wait()
        with locked(folder):
            record = read(folder)
            record.update(execution_status="failed", ended_at=now(), error=str(exc))
            save(folder, record)


def stop_run(project: Path, run_id: str) -> dict:
    folder = run_path(project, run_id)
    if not (folder / "run.json").exists():
        raise ValueError("Unknown run ID.")
    with locked(folder):
        record = read(folder)
        if record["execution_status"] in TERMINAL:
            return record
        atomic_write_text(folder / "USER_STOP", now() + "\n")
        # If the supervisor crashed, only act on the exact recorded child.
        if not alive(record.get("supervisor_pid"), record.get("supervisor_identity")):
            terminate(record.get("pid"), record.get("process_identity"))
            record.update(execution_status="stopped", stop_reason="USER_STOP", ended_at=now(),
                          observation="Supervisor absent; exit code unavailable.")
            save(folder, record)
    deadline = time.monotonic() + 3
    while time.monotonic() < deadline:
        result = status(project, run_id)
        if result["execution_status"] in TERMINAL:
            return result
        time.sleep(0.02)
    return status(project, run_id)


def metrics(record: dict) -> dict:
    path = Path(record["metrics_file"])
    try:
        if not path.is_file():
            raise ValueError("Metrics file is missing or not a regular file.")
        if path.stat().st_size > MAX_METRICS_BYTES:
            raise ValueError("Metrics file exceeds 1 MiB.")
        with path.open("rb") as stream:
            raw = stream.read(MAX_METRICS_BYTES + 1)
        if len(raw) > MAX_METRICS_BYTES:
            raise ValueError("Metrics file grew beyond 1 MiB.")
        values = json.loads(raw)
        if not isinstance(values, dict):
            raise ValueError("Metrics must be a JSON object.")
        if any(isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) for v in values.values()):
            raise ValueError("Metrics must be finite numbers.")
        return {"metrics": values, "metrics_status": "observed" if values else "missing"}
    except (OSError, ValueError) as exc:
        return {"metrics": {}, "metrics_status": "unavailable", "metrics_error": str(exc)}


def compare(project: Path, run_ids: list[str]) -> dict:
    rows = []
    for run_id in run_ids:
        record = status(project, run_id)
        rows.append({**record, **metrics(record)})
    return {"runs": rows, "assessment_status": "unreviewed",
            "note": "Observed metrics only; check configuration, data, evaluation and budgets before drawing conclusions."}


def audit(project: Path, run_id: str, artifacts: list[Path]) -> dict:
    folder = run_path(project, run_id)
    record = status(project, run_id)
    if record["execution_status"] not in TERMINAL:
        raise ValueError("Audit requires an exited run; do not hash actively written outputs.")
    if not artifacts:
        raise ValueError("Specify individual artifact files; no recursive default audit.")
    entries = []
    for artifact in artifacts:
        path = (project / artifact).resolve()
        if not path.is_file():
            raise ValueError(f"Not a regular artifact file: {path}")
        before = path.stat()
        digest = hashlib.sha256()
        with path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
        after = path.stat()
        if (before.st_size, before.st_mtime_ns, before.st_ino) != (after.st_size, after.st_mtime_ns, after.st_ino):
            raise ValueError(f"Artifact changed during audit: {path}")
        entries.append({"path": str(path), "size": after.st_size, "sha256": digest.hexdigest()})
    result = {"created_at": now(), "run_id": run_id, "artifacts": entries,
              "assessment_status": "integrity_recorded", "provenance_status": record["provenance_status"],
              "note": "Post-run file integrity only; does not establish launch-time identity or scientific acceptance."}
    destination = folder / ("audit-" + str(time.time_ns()) + ".json")
    atomic_write_text(destination, json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", type=Path, default=Path.cwd())
    sub = parser.add_subparsers(dest="action", required=True)
    run = sub.add_parser("run")
    run.add_argument("--id")
    run.add_argument("--config", type=Path)
    run.add_argument("--resource")
    run.add_argument("--timeout", type=float)
    run.add_argument("--output-dir", type=Path)
    run.add_argument("--metrics-file", type=Path)
    run.add_argument("command", nargs=argparse.REMAINDER, help="-- executable arg ... (no shell interpolation)")
    for action in ("status", "stop", "_supervise"):
        command = sub.add_parser(action)
        command.add_argument("run_id")
    sub.add_parser("list")
    command = sub.add_parser("compare")
    command.add_argument("run_ids", nargs="+")
    command = sub.add_parser("audit")
    command.add_argument("run_id")
    command.add_argument("--artifact", type=Path, action="append", required=True)
    args = parser.parse_args(argv)
    project = args.project.resolve()
    try:
        if args.action == "run":
            command = args.command[1:] if args.command[:1] == ["--"] else args.command
            result = start_run(project, command, run_id=args.id, config=args.config,
                               resource=args.resource, timeout=args.timeout, output_dir=args.output_dir,
                               metrics_file=args.metrics_file)
        elif args.action == "_supervise":
            supervise(project, args.run_id)
            return 0
        elif args.action == "status":
            result = status(project, args.run_id)
        elif args.action == "stop":
            result = stop_run(project, args.run_id)
        elif args.action == "compare":
            result = compare(project, args.run_ids)
        elif args.action == "audit":
            result = audit(project, args.run_id, args.artifact)
        else:
            result = [status(project, path.parent.name) for path in sorted(runs_root(project).glob("*/run.json"))]
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 1 if args.action == "run" and result["execution_status"] in {"failed", "unknown"} else 0
    except (OSError, ValueError) as exc:
        parser.exit(2, f"experiment: {exc}\n")


if __name__ == "__main__":
    raise SystemExit(main())
