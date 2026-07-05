---
name: mary-workflow
description: Run a v2 milestone workflow from `.mary-workflow/`. Use when the user invokes `/mw-init`, `/mw-plan`, `/mw-run`, `/mw-status`, `/mw-stop`, `/mw-debug`, or asks to run Mary workflow.
---

# Mary Workflow

Mary Workflow v2 keeps project-local state in `.mary-workflow/` and drives Codex through milestone planning, automatic execution/review, debug recovery, and audit-friendly state updates.

## Commands

Use `scripts/mary_workflow.py` for deterministic state operations:

```bash
python ~/.codex/skills/mary-workflow/scripts/mary_workflow.py <command>
```

User-facing command surface:

- `/mw-init`: create `.mary-workflow/`, seed prompts, detect project structure/tech/test commands, and create v2 state.
- `/mw-init --reset`: remove and recreate `.mary-workflow/`.
- `/mw-plan`: render the planning context and write 1 to 7 milestones.
- `/mw-run`: automatic main loop for current phase: execute, review, debug, or resume from the current milestone.
- `/mw-status`: read-only state dashboard.
- `/mw-stop`: pause while preserving state, logs, and reports.
- `/mw-debug`: manually load debug phase when the workflow is in `DEBUGGING`.

Removed v1 commands: `/mw-start`, `/mw-next`, `/mw-resume`, and `/mw-review`.

## Runtime Rules

1. Work from the user's current project directory.
2. If `.mary-workflow/` is missing, run `/mw-init` only when the user asks to initialize; otherwise tell the user to run `/mw-init`.
3. v2 state files must contain `version: 2`; v1 state files are rejected and require `/mw-init --reset`.
4. State updates go through `scripts/mary_workflow.py apply-action`; prompts must not hand-edit `state.yaml`.
5. Phase/action whitelist is enforced by the runtime:
   - `PLANNING`: `update_state`
   - `EXECUTING`: `mark_task_done`, `record_error`
   - `REVIEWING`: `set_phase`, `record_error`
   - `DEBUGGING`: `enqueue_fix_task`
6. Rejected envelopes are logged in `log.md`, counted in state audit data, and must be corrected in the same turn.
7. `log.md` stays English for grep and audit stability. User-facing explanations follow `.mary-workflow/config.yaml` `output.language`.

## Milestone Planning

`update_state` accepts 1 to 7 milestones. Every milestone must include:

- `deliverables`: file-level deliverable list.
- `acceptance`: executable acceptance commands.
- `estimated_scope`: estimated changed non-test file count, maximum `5`.

Each milestone must be independently verifiable. `gate: confirm` can mark a manual confirmation point; `gate: auto` is the default.

## Context Isolation

The filesystem is the source of memory. At every milestone boundary, `mw_codex.py` renders a fresh context package from authority files:

- `.mary-workflow/state.yaml`
- current milestone definition
- project snapshot
- legal action whitelist
- review evidence such as `git diff --stat`

Execution should inspect only current milestone deliverables. Review should inspect only diff, acceptance evidence, deliverables, and `.mary-workflow/reports/<milestone-id>.md`.

## Codex Native Commands

The Codex plugin manifest lives at `.codex-plugin/plugin.json`. Autocomplete is surfaced through command-specific sub-skills under `skills/`:

- `skills/init/SKILL.md` -> `/mw-init`
- `skills/plan/SKILL.md` -> `/mw-plan`
- `skills/run/SKILL.md` -> `/mw-run`
- `skills/status/SKILL.md` -> `/mw-status`
- `skills/stop/SKILL.md` -> `/mw-stop`
- `skills/debug/SKILL.md` -> `/mw-debug`

Command Markdown files also live under `commands/` for clients that support file-based command loading.

## Prompt Execution

When executing a phase prompt:

1. Read `.mary-workflow/state.yaml`.
2. Verify `workflow.phase` matches the prompt.
3. Follow the phase action whitelist.
4. Apply exactly one legal action via `mary_workflow.py apply-action`.
5. Report the action JSON, then summarize outcome and next phase.

## File Contract

See `references/state-contract.md` for expected v2 files and state fields.

