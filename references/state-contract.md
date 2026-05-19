# Mary Workflow State Contract

Mary Workflow stores project-local runtime files in `.mary-workflow/`.

## Directory Layout

```text
.mary-workflow/
├── config.yaml
├── state.yaml
├── prompts/
│   ├── mw-plan.md
│   ├── mw-execute.md
│   ├── mw-review.md
│   └── mw-debug.md
└── log.md
```

## `state.yaml`

```yaml
workflow:
  status: idle
  phase: PLANNING
  started_at:
  updated_at:

current:
  index: 0
  prompt_file: mw-plan.md
  task_id:

progress:
  completed: 0
  total: 0

tasks:
  - id: task-1
    status: pending
    title: "Implement the smallest useful change"

last_error:
  command: "pytest"
  stderr: "failure summary"
  returncode: "1"
  created_at: 2026-05-19T00:00:00+00:00
```

Status values:

- `idle`: initialized but not started.
- `running`: prompt execution is active.
- `stopped`: user paused the workflow.
- `completed`: all prompts have completed.

Phase values:

- `PLANNING`: convert the user's request into at most 3 concrete tasks.
- `EXECUTING`: implement the first pending task.
- `REVIEWING`: inspect the generated code and decide whether to continue.
- `DEBUGGING`: turn a command or script failure into a focused fix task.
- `FINISHED`: the user's request is complete.

Use `REVIEWING` exactly. Do not shorten this phase to `REVIEW`.

Task status values:

- `pending`: not completed yet.
- `done`: implemented and validated.

## Prompt Ordering

Core prompt files live in `.mary-workflow/prompts/`:

```text
mw-plan.md
mw-execute.md
mw-review.md
mw-debug.md
```

Additional `.md` prompts may be added later, but the MVP phase loop uses these four names directly.

## Codex Commands and Bridge

Mary Workflow exposes Codex-facing slash commands through top-level command Markdown files:

```text
commands/
├── mw-init.md
├── mw-start.md
├── mw-plan.md
├── mw-run.md
├── mw-review.md
├── mw-debug.md
├── mw-next.md
├── mw-resume.md
├── mw-status.md
└── mw-stop.md
```

The phase commands call `scripts/mw_codex.py` to render prompt and state context:

- `/mw-plan`: render `mw-plan.md`.
- `/mw-run`: render `mw-execute.md`.
- `/mw-review`: render `mw-review.md`.
- `/mw-debug`: render `mw-debug.md`.
- `/mw-next`: render the prompt for the current `workflow.phase`.
- `/mw-resume`: render the prompt for the current `workflow.phase`.
- `/mw-status`: render `state.yaml` without a phase prompt.

The bridge prints the current `state.yaml` plus the resolved phase prompt. Codex should treat that output as the active instruction context for the turn.

## Phase Prompt Guardrails

Each core prompt must enforce:

- Phase gate: read `.mary-workflow/state.yaml` first and verify `workflow.phase` matches the prompt.
- Structured output: return an action JSON envelope, `{"action":"...","data":{...}}`.
- State update boundary: update state only through `scripts/mary_workflow.py apply-action`; do not edit `state.yaml` by hand.
- Context isolation: execution should inspect and edit only files directly related to the current task unless explicitly instructed otherwise.

Supported action names:

- `update_state`: replace the task list and move to the target phase.
- `mark_task_done`: mark one task done and advance to the next task or `REVIEWING`.
- `set_phase`: move to `PLANNING`, `EXECUTING`, `REVIEWING`, `DEBUGGING`, or `FINISHED`.
- `record_error`: record failed command details and enter `DEBUGGING`.
- `enqueue_fix_task`: insert one fix task before the first pending task and return to `EXECUTING`.
