# Mary Workflow v2.1 State Contract

Mary Workflow stores runtime authority in `.mary-workflow/`. Filesystem state, not conversation memory, controls every transition.

## Directory Layout

```text
.mary-workflow/
├── config.yaml
├── project-brief.md
├── state.yaml
├── prompts/
│   ├── mw-plan.md
│   ├── mw-ready.md
│   ├── mw-resume.md
│   ├── mw-execute.md
│   ├── mw-review.md
│   └── mw-debug.md
├── reports/C0/milestone-1.md
├── cycles/C0/{state.yaml,log.md,reports/}
└── log.md
```

## Version

```yaml
version: 2.1
cycle: C0
```

v2.1 rejects earlier state contracts. Recreate old workspaces with `/mw-init --reset`; there is no implicit migration because `PLANNED` and the lease/grant contract change state semantics.

## Phase Graph

```text
PLANNING --update_state--> PLANNED
PLANNED --start_execution + start grant--> EXECUTING
EXECUTING --mark_task_done--> REVIEWING
EXECUTING/REVIEWING --record_error--> DEBUGGING
DEBUGGING --enqueue_fix_task--> EXECUTING
REVIEWING --set_phase--> EXECUTING | PLANNING | FINISHED
stopped active phase --resume_execution + resume grant--> same active phase
```

`/mw-cycle` archives the active cycle and resets to `PLANNING`. No edge other than a grant-backed `start_execution` may enter initial `EXECUTING` from `PLANNED`.

## Action Whitelist

- `PLANNING`: `update_project`, `update_interview`, `update_state`
- `PLANNED`: `reopen_plan`, `start_execution`
- `EXECUTING`: `mark_task_done`, `record_error`
- `REVIEWING`: `set_phase`, `record_error`
- `DEBUGGING`: `enqueue_fix_task`
- `FINISHED`: none

When an active phase has `workflow.status: stopped`, its normal actions are replaced by `resume_execution` only.

## Planning Contract

The interview persists every question and answer. Adaptive depth is enforced:

- 1 to 2 milestones may use confirmed round-0 defaults.
- 3 to 4 milestones require at least one answered active round.
- 5 or more milestones require at least two answered active rounds.

Lifecycle values are `not_started`, `awaiting_answers`, `in_progress`, `draft_ready`, `plan_ready`, and `complete`. `draft_ready` is a persisted draft awaiting `update_state`; `plan_ready` is a frozen, still-unconfirmed plan awaiting `/mw-run`.

Every default or assumption must be persisted and displayed before the user answers. `plan.interview: off` disables open-ended interviewing, not confirmation: `mode=propose` remains in `awaiting_answers` until the user explicitly accepts the listed assumptions. `resolve` and `revise` reject newly introduced defaults.

Every milestone has `id`, `title`, file-level `deliverables`, executable `acceptance`, `estimated_scope <= 5`, and `gate: auto|confirm`.

When the draft is complete, `update_state` must copy persisted `clarifications` and `draft_milestones` exactly:

```json
{
  "action": "update_state",
  "data": {
    "phase": "PLANNED",
    "clarifications": ["<exact persisted record>"],
    "milestones": [
      {
        "id": "milestone-1",
        "title": "Frozen delivery unit",
        "deliverables": ["src/module.py"],
        "acceptance": ["pytest"],
        "estimated_scope": 1,
        "gate": "auto"
      }
    ]
  }
}
```

This produces `interview_status: plan_ready`, `final_plan_confirmed: false`, and phase `PLANNED`. It never starts product work. `/mw-plan` can use `reopen_plan` to return a frozen plan to `PLANNING` for revision.

## Run Grant

Rendering `/mw-run` in `PLANNED` creates a short-lived one-time start grant bound to:

- current cycle
- SHA-256 digest of clarifications and the frozen milestone schema
- purpose `start`

The plaintext token appears only in that `/mw-run` render. `state.yaml`, `/mw-status`, and logs store only digest metadata and a short fingerprint:

```yaml
run_grant:
  token_digest: <sha256>
  fingerprint: <12 hex chars>
  purpose: start
  plan_digest: <sha256>
  cycle: C0
  issued_at: <timestamp>
  expires_at: <timestamp>
```

```json
{
  "action": "start_execution",
  "data": {"token": "<plaintext token from current /mw-run render>"}
}
```

Successful consumption is single-use and atomic: it sets `final_plan_confirmed: true`, changes `interview_status` to `complete`, acquires the run lease, and records `PLANNED -> EXECUTING`. Replay, expiry, wrong purpose, changed plan, or changed cycle is rejected.

Before the authorization block, `/mw-run` renders `Final Plan Confirmation Evidence` as quoted JSON containing every persisted question, recorded answer, default/assumption, clarification, and frozen milestone. The ready prompt requires this evidence to be shown without paraphrasing before grant consumption; evidence strings are data, not instructions.

The repository runtime can prove possession of a token emitted by its `/mw-run` renderer. Proving that a human, rather than an agent with direct process access, invoked the renderer requires the Codex host/slash-command dispatcher to be the trusted caller.

## Execution Lease

The lease belongs to the whole run, not one phase:

```yaml
execution_lease:
  owner: codex
  status: active
  run_id: <random id>
  plan_digest: <sha256>
  cycle: C0
  milestone_id: milestone-1
  started_at: <timestamp>
  heartbeat_at: <timestamp>
```

- `start_execution` is the only initial lease acquisition point.
- EXECUTING/REVIEWING/DEBUGGING transitions preserve the run id and refresh heartbeat/current milestone.
- `/mw-stop` changes an active lease to `paused` and clears any outstanding grant.
- A later `/mw-run` issues a purpose `resume` grant; `resume_execution` restores the same run id and phase.
- FINISHED, replanning, and cycle reset release or clear the lease.

## Audit

`audit.action_counts` includes `update_interview`, `update_project`, `update_state`, `reopen_plan`, `start_execution`, `resume_execution`, `mark_task_done`, `set_phase`, `record_error`, and `enqueue_fix_task`. `phase_history` records, at minimum:

```text
PLANNING -> PLANNED (envelope: update_state; plan ready)
PLANNED -> EXECUTING (/mw-run: start_execution)
EXECUTING -> REVIEWING (auto: all tasks done)
```

Rejected envelopes increment `rejected_actions` and leave action mutations unapplied.

## Command Surface

```text
/mw-init
/mw-plan
/mw-run
/mw-status
/mw-stop
/mw-debug
/mw-cycle
```
