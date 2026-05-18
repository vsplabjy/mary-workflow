#!/usr/bin/env python3
"""Tiny runtime helper for Mary Workflow.

This script intentionally avoids third-party dependencies. It writes a simple
YAML-shaped state file and parses only the fields it owns.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path
import re
import shutil
import sys


WORKFLOW_DIR = ".mary-workflow"
PROMPTS_DIR = "prompts"
VALID_PHASES = {"PLANNING", "EXECUTING", "REVIEWING", "FINISHED"}
PHASE_PROMPTS = {
    "PLANNING": "mw-plan.md",
    "EXECUTING": "mw-execute.md",
    "REVIEWING": "mw-review.md",
}
CORE_PROMPT_ORDER = {
    "mw-plan.md": 0,
    "mw-execute.md": 1,
    "mw-review.md": 2,
}

Task = dict[str, str]
State = dict[str, object]


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


def default_state(status: str = "idle") -> State:
    return {
        "status": status,
        "phase": "PLANNING",
        "started_at": "",
        "updated_at": now_iso(),
        "current_index": 0,
        "current_prompt": "",
        "current_task_id": "",
        "completed": 0,
        "total": 0,
        "tasks": [],
    }


def parse_value(value: str) -> str:
    value = value.strip()
    if not value:
        return ""
    if value.startswith('"') and value.endswith('"'):
        return value[1:-1].replace('\\"', '"').replace("\\\\", "\\")
    return value


def quote_value(value: object) -> str:
    text = " ".join(str(value).split())
    return '"' + text.replace("\\", "\\\\").replace('"', '\\"') + '"'


def read_state(root: Path) -> State:
    state_path = root / "state.yaml"
    if not state_path.exists():
        return default_state()

    state = default_state()
    tasks: list[Task] = []
    section = ""
    current_task: Task | None = None
    for raw_line in state_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.rstrip()
        if not line or line.lstrip().startswith("#"):
            continue
        if not line.startswith(" ") and line.endswith(":"):
            section = line[:-1]
            current_task = None
            continue
        if section == "tasks":
            if line.startswith("  - "):
                current_task = {}
                tasks.append(current_task)
                rest = line[4:].strip()
                if rest:
                    set_key_value(current_task, rest)
                continue
            if current_task is not None and line.startswith("    "):
                set_key_value(current_task, line.strip())
                continue

        match = re.match(r"^\s{2}([a-z_]+):\s*(.*)$", line)
        if not match:
            continue
        key, value = match.groups()
        value = parse_value(value)
        if section == "workflow" and key in {"status", "phase", "started_at", "updated_at"}:
            state[key] = value
        elif section == "current" and key == "index":
            state["current_index"] = int(value or 0)
        elif section == "current" and key == "prompt_file":
            state["current_prompt"] = value
        elif section == "current" and key == "task_id":
            state["current_task_id"] = value
        elif section == "progress" and key in {"completed", "total"}:
            state[key] = int(value or 0)

    state["tasks"] = tasks
    return state


def set_key_value(target: Task, text: str) -> None:
    if ":" not in text:
        return
    key, value = text.split(":", 1)
    target[key.strip()] = parse_value(value)


def write_state(root: Path, state: State) -> None:
    tasks = state_tasks(state)
    lines = [
        "workflow:",
        f"  status: {state['status']}",
        f"  phase: {state['phase']}",
        f"  started_at: {state['started_at']}",
        f"  updated_at: {state['updated_at']}",
        "",
        "current:",
        f"  index: {state['current_index']}",
        f"  prompt_file: {state['current_prompt']}",
        f"  task_id: {state['current_task_id']}",
        "",
        "progress:",
        f"  completed: {state['completed']}",
        f"  total: {state['total']}",
        "",
        "tasks:",
    ]
    for task in tasks:
        lines.extend(
            [
                f"  - id: {task['id']}",
                f"    status: {task['status']}",
                f"    title: {quote_value(task['title'])}",
            ]
        )
    (root / "state.yaml").write_text("\n".join(lines) + "\n", encoding="utf-8")


def state_tasks(state: State) -> list[Task]:
    tasks = state.get("tasks")
    if isinstance(tasks, list):
        return [task for task in tasks if isinstance(task, dict)]
    return []


def append_log(root: Path, message: str) -> None:
    log_path = root / "log.md"
    with log_path.open("a", encoding="utf-8") as handle:
        handle.write(f"- {now_iso()} {message}\n")


def require_root(cwd: Path) -> Path:
    root = workflow_root(cwd)
    if not root.exists():
        raise SystemExit("Mary Workflow is not initialized. Run /mw:init first.")
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


def set_phase(state: State, root: Path, phase: str) -> None:
    phase = phase.upper()
    if phase not in VALID_PHASES:
        allowed = ", ".join(sorted(VALID_PHASES))
        raise SystemExit(f"Invalid phase: {phase}. Expected one of: {allowed}.")
    state["phase"] = phase
    state["updated_at"] = now_iso()
    state["status"] = "completed" if phase == "FINISHED" else "running"
    sync_prompt_for_phase(state, root)


def refresh_task_progress(state: State) -> None:
    tasks = state_tasks(state)
    state["completed"] = sum(1 for task in tasks if task.get("status") == "done")
    state["total"] = len(tasks)
    next_task = first_pending_task(state)
    state["current_task_id"] = next_task.get("id", "") if next_task else ""


def first_pending_task(state: State) -> Task | None:
    for task in state_tasks(state):
        if task.get("status") != "done":
            return task
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


def cmd_init(args: argparse.Namespace) -> int:
    root = workflow_root(Path.cwd())
    root.mkdir(exist_ok=True)
    (root / PROMPTS_DIR).mkdir(exist_ok=True)

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

    seeded = seed_core_prompts(root)
    examples = write_example_prompts(root) if args.with_examples else 0
    prompts = prompt_files(root)

    state = read_state(root)
    state["phase"] = "PLANNING"
    state["status"] = "idle"
    state["updated_at"] = now_iso()
    sync_prompt_for_phase(state, root)
    refresh_task_progress(state)
    write_state(root, state)

    log_path = root / "log.md"
    if not log_path.exists():
        log_path.write_text("# Mary Workflow Log\n\n", encoding="utf-8")
    append_log(root, "initialized workflow")
    print(f"Initialized {WORKFLOW_DIR} with {len(prompts)} prompt(s).")
    if seeded:
        print(f"Seeded {seeded} core prompt(s).")
    if examples:
        print(f"Seeded {examples} example prompt(s).")
    return 0


def cmd_start(args: argparse.Namespace) -> int:
    root = require_root(Path.cwd())
    prompts = prompt_files(root)
    if not prompts:
        raise SystemExit("No prompt files found in .mary-workflow/prompts/.")
    state = read_state(root)
    state["started_at"] = state["started_at"] or now_iso()
    set_phase(state, root, "PLANNING")
    refresh_task_progress(state)
    write_state(root, state)
    append_log(root, f"started workflow at {state['current_prompt']}")
    print_status(state)
    return 0


def cmd_status(args: argparse.Namespace) -> int:
    root = require_root(Path.cwd())
    state = read_state(root)
    refresh_task_progress(state)
    write_state(root, state)
    print_status(state)
    return 0


def cmd_plan(args: argparse.Namespace) -> int:
    root = require_root(Path.cwd())
    titles = [title.strip() for title in args.task if title.strip()]
    if not titles:
        raise SystemExit("Provide at least one --task.")
    if len(titles) > 3:
        raise SystemExit("Mary Workflow accepts at most 3 tasks per plan.")

    state = read_state(root)
    tasks = [{"id": f"task-{index}", "status": "pending", "title": title} for index, title in enumerate(titles, start=1)]
    state["tasks"] = tasks
    state["started_at"] = state["started_at"] or now_iso()
    refresh_task_progress(state)
    set_phase(state, root, "EXECUTING")
    write_state(root, state)
    append_log(root, f"planned {len(tasks)} task(s)")
    print_status(state)
    return 0


def cmd_next_task(args: argparse.Namespace) -> int:
    root = require_root(Path.cwd())
    state = read_state(root)
    task = first_pending_task(state)
    if not task:
        set_phase(state, root, "REVIEWING")
        write_state(root, state)
        print("No pending tasks. Phase moved to REVIEWING.")
        return 0
    state["current_task_id"] = task["id"]
    set_phase(state, root, "EXECUTING")
    write_state(root, state)
    print(f"{task['id']}: {task['title']}")
    return 0


def cmd_done_task(args: argparse.Namespace) -> int:
    root = require_root(Path.cwd())
    state = read_state(root)
    target_id = args.id or str(state.get("current_task_id") or "")
    if not target_id:
        task = first_pending_task(state)
        target_id = task["id"] if task else ""
    if not target_id:
        raise SystemExit("No pending task to mark done.")

    tasks = state_tasks(state)
    for task in tasks:
        if task.get("id") == target_id:
            task["status"] = "done"
            break
    else:
        raise SystemExit(f"Task not found: {target_id}")

    refresh_task_progress(state)
    next_task = first_pending_task(state)
    if next_task:
        set_phase(state, root, "EXECUTING")
    else:
        set_phase(state, root, "REVIEWING")
    write_state(root, state)
    append_log(root, f"marked {target_id} done")
    print_status(state)
    return 0


def cmd_set_phase(args: argparse.Namespace) -> int:
    root = require_root(Path.cwd())
    state = read_state(root)
    set_phase(state, root, args.phase)
    refresh_task_progress(state)
    write_state(root, state)
    append_log(root, f"set phase to {state['phase']}")
    print_status(state)
    return 0


def cmd_complete_current(args: argparse.Namespace) -> int:
    root = require_root(Path.cwd())
    prompts = prompt_files(root)
    if not prompts:
        raise SystemExit("No prompt files found in .mary-workflow/prompts/.")

    state = read_state(root)
    current_index = int(state["current_index"]) + 1
    state["updated_at"] = now_iso()
    if current_index >= len(prompts):
        set_phase(state, root, "FINISHED")
        append_log(root, "completed final prompt")
    else:
        state["current_index"] = current_index
        state["current_prompt"] = prompts[current_index]
        state["status"] = "running"
        append_log(root, f"advanced to {state['current_prompt']}")

    write_state(root, state)
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
    prompt = state["current_prompt"] or "(none)"
    task_id = state["current_task_id"] or "(none)"
    print(f"status: {state['status']}")
    print(f"phase: {state['phase']}")
    print(f"progress: {state['completed']}/{state['total']}")
    print(f"current_prompt: {prompt}")
    print(f"current_task: {task_id}")
    tasks = state_tasks(state)
    if tasks:
        print("tasks:")
        for task in tasks:
            print(f"  - {task['id']} [{task['status']}] {task['title']}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Mary Workflow runtime helper")
    subparsers = parser.add_subparsers(dest="command", required=True)

    init_parser = subparsers.add_parser("init", help="create .mary-workflow")
    init_parser.add_argument("--with-examples", action="store_true", help="create two starter prompts")
    init_parser.set_defaults(func=cmd_init)

    subparsers.add_parser("start", help="start workflow").set_defaults(func=cmd_start)
    subparsers.add_parser("status", help="show status").set_defaults(func=cmd_status)

    plan_parser = subparsers.add_parser("plan", help="write up to 3 tasks and enter EXECUTING")
    plan_parser.add_argument("--task", action="append", default=[], help="task title; repeat up to 3 times")
    plan_parser.set_defaults(func=cmd_plan)

    subparsers.add_parser("next-task", help="print first pending task").set_defaults(func=cmd_next_task)

    done_parser = subparsers.add_parser("done-task", help="mark a task done")
    done_parser.add_argument("--id", help="task id; defaults to current task or first pending task")
    done_parser.set_defaults(func=cmd_done_task)

    phase_parser = subparsers.add_parser("set-phase", help="set workflow phase")
    phase_parser.add_argument("phase", help="PLANNING, EXECUTING, REVIEWING, or FINISHED")
    phase_parser.set_defaults(func=cmd_set_phase)

    subparsers.add_parser("complete-current", help="advance current prompt file").set_defaults(func=cmd_complete_current)
    subparsers.add_parser("stop", help="stop workflow").set_defaults(func=cmd_stop)
    return parser


def main(argv: list[str]) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
