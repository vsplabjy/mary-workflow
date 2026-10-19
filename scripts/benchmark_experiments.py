#!/usr/bin/env python3
"""CPU-only measurements: launch/status latency vs legacy snapshot components.

The legacy numbers are snapshot component costs, not end-to-end agent timings.
Creates disposable projects and sparse fixtures; never runs GPUs or real data.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import statistics
import sys
import tempfile
import time
from unittest import mock

import mw_experiment as experiment
import mw_workers as workers


def stats(values):
    ordered = sorted(values)
    return {"median_ms": round(statistics.median(values), 3),
            "max_ms": round(max(values), 3), "samples_ms": [round(v, 3) for v in ordered]}


def benchmark(repeats=5):
    rows = []
    with tempfile.TemporaryDirectory(prefix="mary-experiment-benchmark-") as temporary:
        for label, count, large_bytes in [("small", 10, 0), ("large", 500, 256 * 1024 * 1024)]:
            project = Path(temporary) / label
            project.mkdir()
            for index in range(count):
                (project / f"source-{index}.py").write_text("value = 1\n" * 10)
            if large_bytes:
                with (project / "unrelated-checkpoint.pth").open("wb") as stream:
                    stream.truncate(large_bytes)
            experiment.ensure_workflow_gitignore(project)
            snapshots, launches, statuses, progress = [], [], [], []
            byte_counts, read_counts = [], []
            for attempt in range(repeats):
                counted = {"bytes": 0, "files": 0}
                original = workers._file_digest
                def measured(path):
                    counted["bytes"] += path.stat().st_size
                    counted["files"] += 1
                    return original(path)
                before = time.perf_counter()
                with mock.patch.object(workers, "_file_digest", measured):
                    workers._snapshot(project)
                snapshots.append((time.perf_counter() - before) * 1000)
                byte_counts.append(counted["bytes"])
                read_counts.append(counted["files"])
                code = "import os,pathlib; pathlib.Path(os.environ['MARY_OUTPUT_DIR'],'first-progress').write_text('1'); print('first progress',flush=True)"
                before = time.perf_counter()
                # A real guard: launch must not execute a repository snapshot or hash.
                with mock.patch.object(experiment.hashlib, "sha256", side_effect=AssertionError("launch hash")), mock.patch.object(workers, "_snapshot", side_effect=AssertionError("launch snapshot")):
                    record = experiment.start_run(project, [sys.executable, "-c", code])
                launches.append((time.perf_counter() - before) * 1000)
                deadline = time.monotonic() + 5
                marker = Path(record["output_dir"]) / "first-progress"
                while not marker.exists() and time.monotonic() < deadline:
                    time.sleep(.001)
                progress.append((time.perf_counter() - before) * 1000)
                before_status = time.perf_counter()
                observed = experiment.status(project, record["run_id"])
                statuses.append((time.perf_counter() - before_status) * 1000)
                while observed["execution_status"] not in experiment.TERMINAL and time.monotonic() < deadline:
                    time.sleep(.01)
                    observed = experiment.status(project, record["run_id"])
                if observed["execution_status"] != "completed":
                    experiment.stop_run(project, record["run_id"])
                    raise RuntimeError(f"CPU fixture did not finish: {observed}")
            rows.append({"fixture": label, "source_files": count, "unrelated_checkpoint_bytes": large_bytes,
                         "legacy_single_snapshot": stats(snapshots),
                         "legacy_snapshot_files": read_counts, "legacy_snapshot_bytes": byte_counts,
                         "fast_launch_including_handshake": stats(launches), "status": stats(statuses),
                         "cpu_first_progress_observed": stats(progress),
                         "launch_repository_snapshots": 0, "launch_content_hashes": 0})
    return {"schema": 1, "python": sys.version, "repeats": repeats, "results": rows,
            "boundary": "Local CPU fixtures, warm filesystem cache; snapshot components are not a full strict workflow or model/GPU startup measurement. Samples are not sufficient for population p95 claims."}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repeats", type=int, default=5)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if not 1 <= args.repeats <= 100:
        parser.error("repeats must be 1..100")
    result = benchmark(args.repeats)
    text = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text)
    print(text)


if __name__ == "__main__":
    main()
