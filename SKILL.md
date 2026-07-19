---
name: mary-workflow
description: Run Mary Workflow's v2.1 milestone engine from `.mary-workflow/` and v2.2 research-paper pipeline from `.mary-research/`, including contract-validated close reading, readable source-grounded summaries, linted ShanghaiTech Marp slides, and append-only expert Q&A. Use when the user invokes `/mw-init`, `/mw-plan`, `/mw-run`, `/mw-status`, `/mw-stop`, `/mw-debug`, `/mw-cycle`, `/mw-paper`, asks to run Mary workflow, manage paper state, read or summarize a research paper, build group-meeting slides, or run a source-grounded paper quiz.
---

# Mary Workflow

Mary Workflow keeps the v2.1 milestone engine stable while v2.2 adds independent research skills. Paper state and close-reading artifacts live under `.mary-research/papers/` without changing milestone authorization semantics.

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
- `/mw-paper`: manage independent paper states, produce validated notes/summaries/slides, and run append-only expert Q&A without plan/run authorization.

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
10. `/mw-paper` uses `scripts/mw_paper.py` and `paper_state_schema: 1`; it does not read or mutate `.mary-workflow/` milestone state. Parse-quality and source-locator gates are machine enforced.
11. P5 consumes the localized `mary-shanghaitech-red` assets under `assets/marp/`, deploys a self-contained copy plus Marp VS Code registration into the target project during `prepare-slides`, and requires `slides.md` to pass the summary-claim, Figure-placeholder, layout, media, and page-capacity gate before completion.
12. P6 prioritizes paper-understanding questions grounded in P3.5 Method claims, permits only scientific-content P2 uncertainties as conditional follow-ups, requires one such Uxx only when that catalog is non-empty, excludes parse-quality uncertainties from the question pool, accepts four-value judgments with exact source excerpts, and archives all readable sessions in one append-only `quiz-log.md` under a verified hash chain.

## Memory Model

- Long-term memory: `.mary-workflow/project-brief.md` and the `project` section in `state.yaml`.
- Cycle-local short-term memory: interview rounds, draft/active milestones, reports, logs, leases, and clarifications.
- `/mw-cycle` archives short-term memory and starts the next cycle without planning new work.
- Paper memory is isolated per paper in `.mary-research/papers/<paper-id>/state.json`, survives workflow reset/cycle operations, and is not part of cycle progress.

## Codex Native Commands

Autocomplete is surfaced through command-specific sub-skills under `skills/`:

- `skills/init/SKILL.md` -> `/mw-init`
- `skills/plan/SKILL.md` -> `/mw-plan`
- `skills/run/SKILL.md` -> `/mw-run`
- `skills/status/SKILL.md` -> `/mw-status`
- `skills/stop/SKILL.md` -> `/mw-stop`
- `skills/debug/SKILL.md` -> `/mw-debug`
- `skills/cycle/SKILL.md` -> `/mw-cycle`
- `skills/paper/SKILL.md` -> `/mw-paper`

Command Markdown files also live under `commands/` for clients that support file-based command loading.

## File Contract

See `references/state-contract.md` for v2.1 milestone state, `references/paper-state-contract.md` for paper state schema 1, `references/paper-notes-contract.md` for close reading, `references/summary-contract.md` for grounded summaries, `references/slides-contract.md` for P5 slide authoring, `references/quiz-contract.md` for P6 expert Q&A, and `references/marp-assets-contract.md` for the offline presentation supply.
