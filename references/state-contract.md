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
│   └── mw-review.md
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
```

Additional `.md` prompts may be added later, but the MVP phase loop uses these three names directly.

## Phase Prompt Guardrails

Each core prompt must enforce:

- Phase gate: read `.mary-workflow/state.yaml` first and verify `workflow.phase` matches the prompt.
- Structured output: return a strict JSON object for task plans, execution results, or review decisions.
- State update boundary: update state only through `scripts/mary_workflow.py`; do not edit `state.yaml` by hand.
- Context isolation: execution should inspect and edit only files directly related to the current task unless explicitly instructed otherwise.
