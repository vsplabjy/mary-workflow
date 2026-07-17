---
name: mary-workflow
description: Run a v2.1 milestone workflow from `.mary-workflow/`, including course Lecture learning and ExamPass review profiles. Use when the user invokes `/mw-init`, `/mw-plan`, `/mw-run`, `/mw-status`, `/mw-stop`, `/mw-debug`, `/mw-cycle`, `/mw-learn`, `/mw-exam`, `/mw-review`, or `/mw-slide`, or asks to run Mary workflow.
---

# Mary Workflow

Mary Workflow v2.1 keeps project-local state in `.mary-workflow/` and drives Codex through project understanding, milestone planning, authorized automatic execution/review, debug recovery, cycle archives, and audit-friendly state updates.

## Commands

User-facing command surface:

- `/mw-init`: scan the full text inventory, complete a three-pass evidence-backed understanding, execute safe validation, and submit the five-layer project brief.
- `/mw-init --reset`: remove and recreate `.mary-workflow/`.
- `/mw-plan`: persist adaptive interview rounds, freeze the draft, then stop unconfirmed in `PLANNED`.
- `/mw-run`: confirm the frozen plan, consume a one-time grant, acquire/resume the run lease, then run the automatic phase loop.
- `/mw-status`: read-only state dashboard.
- `/mw-stop`: pause while preserving state, logs, reports, and cycle.
- `/mw-debug`: manually load debug phase when the workflow is in `DEBUGGING`.
- `/mw-cycle`: archive the current cycle to `.mary-workflow/cycles/<cycle>/`, reset active short-term state, and point back to `/mw-plan`.
- `/mw-learn`: run the Course Lecture learning profile based on `skills/lecture-learning/`.
- `/mw-exam`: run the ExamPass review profile based on `skills/exam-review/`.
- `/mw-review`: compatibility alias for `/mw-exam`.
- `/mw-slide`: run the direct Slide to Lecture preparation profile.

## Runtime Rules

1. Work from the user's current project directory.
2. v2.1 state files must contain `version: 2.1`; earlier state contracts are rejected and require `/mw-init --reset`.
3. `init` defaults to Chinese, writes `.mary-workflow/project-brief.md`, then asks whether plan/run should use `zh`, `auto`, or `en`.
4. Project understanding corrections use `update_project`; do not hand-edit `state.yaml` or `project-brief.md`.
5. State updates go through `scripts/mary_workflow.py apply-action`.
6. Phase/action whitelist is enforced by the runtime:
   - incomplete brief in `PLANNING`: `submit_brief`, `update_project`
   - complete brief in `PLANNING`: `submit_brief`, `update_project`, `update_interview`, `update_state`
   - `PLANNED`: `reopen_plan`, `start_execution`
   - `EXECUTING`: `mark_task_done`, `record_error` (`resume_execution` only while stopped)
   - `REVIEWING`: `set_phase`, `record_error` (`resume_execution` only while stopped)
   - `DEBUGGING`: `enqueue_fix_task` (`resume_execution` only while stopped)
7. `/mw-plan` is blocked until the five-layer project brief is complete; it consumes the full file ledger when asking questions and splitting milestones.
8. Only a `/mw-run` render contains the plaintext one-time token. `start_execution` atomically confirms the plan and acquires the lease; stop/resume uses a separate single-use grant.
9. `log.md` stays English for grep and audit stability. User-facing explanations follow `.mary-workflow/config.yaml` `output.language`.

## Memory Model

- Long-term memory: `.mary-workflow/project-brief.md` and the `project` section in `state.yaml`.
- Cycle-local short-term memory: interview rounds, draft/active milestones, reports, logs, leases, and clarifications.
- `/mw-cycle` archives short-term memory and starts the next cycle without planning new work.

## Codex Native Commands

Autocomplete is surfaced through command-specific sub-skills under `skills/`:

- `skills/init/SKILL.md` -> `/mw-init`
- `skills/plan/SKILL.md` -> `/mw-plan`
- `skills/run/SKILL.md` -> `/mw-run`
- `skills/status/SKILL.md` -> `/mw-status`
- `skills/stop/SKILL.md` -> `/mw-stop`
- `skills/debug/SKILL.md` -> `/mw-debug`
- `skills/cycle/SKILL.md` -> `/mw-cycle`
- `skills/lecture-learning/SKILL.md` -> `/mw-learn`
- `skills/exam-review/SKILL.md` -> `/mw-exam`
- `skills/slide-to-lecture/SKILL.md` -> `/mw-slide` and the Lecture learning Stage 1
- `skills/roundtrip-screenshot/SKILL.md` -> image/PDF crop verification when needed

Command Markdown files also live under `commands/` for clients that support file-based command loading.

## File Contract

See `references/state-contract.md` for expected v2.1 files and state fields.
