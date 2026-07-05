# Mary Workflow v2 State Contract

Mary Workflow stores runtime files in `.mary-workflow/`.

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
├── reports/
│   └── milestone-1.md
└── log.md
```

## State Version

`state.yaml` must contain:

```yaml
version: 2
```

Mary Workflow v2 rejects v1 state files. Use `/mw-init --reset` to recreate old projects.

## Core State Shape

```yaml
version: 2

workflow:
  status: idle
  phase: PLANNING
  started_at:
  updated_at:

project:
  root: "/path/to/project"
  structure:
    - "README.md"
  tech_stack:
    - "python"
  test_commands:
    - "pytest"

current:
  index: 0
  prompt_file: mw-plan.md
  milestone_id:

progress:
  completed: 0
  total: 0

execution_lease:
  owner:
  milestone_id:
  started_at:

milestones:
  - id: milestone-1
    status: pending
    title: "Implement one independently verifiable slice"
    deliverables:
      - "src/module.py"
    acceptance:
      - "pytest"
    estimated_scope: 2
    gate: auto
    review: ""

audit:
  action_counts:
    update_state: 0
    mark_task_done: 0
    set_phase: 0
    record_error: 0
    enqueue_fix_task: 0
  rejected_actions: 0
  phase_history:
    - "PLANNING -> EXECUTING (envelope: update_state)"
```

## Phase Values

- `PLANNING`: convert the user goal into 1 to 7 milestones.
- `EXECUTING`: implement the current milestone.
- `REVIEWING`: review current milestone evidence and diff.
- `DEBUGGING`: convert `last_error` into a focused fix milestone.
- `FINISHED`: all milestones are complete.

## Action Whitelist

The runtime rejects illegal envelopes:

- `PLANNING`: `update_state`
- `EXECUTING`: `mark_task_done`, `record_error`
- `REVIEWING`: `set_phase`, `record_error`
- `DEBUGGING`: `enqueue_fix_task`
- `FINISHED`: no mutating actions

Rejected envelopes are logged as `rejected ...`, counted in `audit.rejected_actions`, and returned with legal actions for the current phase.

## Milestone Schema

`update_state` accepts:

```json
{
  "action": "update_state",
  "data": {
    "phase": "EXECUTING",
    "milestones": [
      {
        "id": "milestone-1",
        "title": "Concrete milestone",
        "deliverables": ["relative/path.ext"],
        "acceptance": ["pytest"],
        "estimated_scope": 2,
        "gate": "auto"
      }
    ]
  }
}
```

Rules:

- 1 to 7 milestones.
- `deliverables`, `acceptance`, and `estimated_scope` are required.
- `estimated_scope <= 5`, counting non-test files only.
- Every milestone must be independently verifiable.
- `gate` is `auto` or `confirm`.

## Command Surface

v2 exposes six commands:

```text
/mw-init
/mw-plan
/mw-run
/mw-status
/mw-stop
/mw-debug
```

Removed v1 commands:

```text
/mw-start
/mw-next
/mw-resume
/mw-review
```

`/mw-run` renders the current phase and resumes from the current milestone, so it absorbs next/resume/review behavior.

