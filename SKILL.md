---
name: mary-workflow
description: Run Mary Workflow's v2.1 milestone engine from `.mary-workflow/`, course Lecture learning and ExamPass review profiles, the v2.2 research-paper pipeline from `.mary-research/`, and schema-aware Notion MCP operations. Use when the user invokes `/mw-init`, `/mw-plan`, `/mw-run`, `/mw-status`, `/mw-stop`, `/mw-debug`, `/mw-cycle`, `/mw-learn`, `/mw-exam`, `/mw-review`, `/slide-learning`, `/mw-paper`, or `/mw-notion`; asks to run Mary Workflow; or needs course learning, exam review, paper reading, grounded summaries, group-meeting slides, source-grounded paper Q&A, or polished Notion page/database work.
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
- `/mw-learn`: run the Course Lecture learning profile based on `skills/lecture-learning/`.
- `/mw-exam`: run the ExamPass review profile based on `skills/exam-review/`.
- `/mw-review`: compatibility alias for `/mw-exam`.
- `/slide-learning`: run the direct Slide to Lecture preparation profile.
- `/mw-paper`: manage independent paper states, produce validated notes/summaries/slides, and run append-only expert Q&A without plan/run authorization.
- `/mw-notion`: execute a natural-language Notion MCP request with fetch-before-write safety, page-craft rules, and read-back verification.
- `/mw-model`: configure or switch Codex between the existing VSP provider and DeepSeek Responses API.

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
11. Folder-backed `/mw-paper read` keeps PDF locators in `artifacts/source.md`, expands an available LaTeX source into annotated English-first `reading.md`, requires meaningful Chinese help selected from `.mary-research/reading-profile.md` plus a source-grounded Chinese `reading-summary.md` with a detailed Method explanation, keeps generated source/JSON sidecars in `artifacts/`, and completes the Notion create/update plus read-back pass described in `references/paper-reading-contract.md` (the `Original paper` child page first, then the Chinese guide on the paper page by default under `本科学习` -> `科研 / 项目` -> `读论文`). Legacy root source/JSON files are migrated by `migrate-artifacts` or the next preparation command; `state.json` remains the root state exception.
12. P5 consumes the localized `mary-shanghaitech-red` assets under `assets/marp/`, deploys a self-contained copy plus Marp VS Code registration into the target project during `prepare-slides`, writes a paper-local `Makefile` and a `.mary-research/Makefile` dispatcher, and requires `slides.md` to pass the summary-claim, Figure-placeholder, layout, media, and page-capacity gate before completion. `make slide` exports the Marp deck with the built-in Mary theme.
13. P6 prioritizes paper-understanding questions grounded in P3.5 Method claims, permits only scientific-content P2 uncertainties as conditional follow-ups, requires one such Uxx only when that catalog is non-empty, excludes parse-quality uncertainties from the question pool, and archives Question, User answer, four-value Judgment, source-grounded Correct answer, and Paper sources in one append-only `quiz-log.md` under a verified hash chain.
14. `/mw-notion` uses the standard Mary command/skill/reference layout but remains independent of milestone and paper state. It requires an authorized Notion MCP connection, inspects live tool schemas, fetches existing targets before writes, applies the Notion references, and verifies mutations by fetching the result again.
15. The first `/mw-init` detects the current terminal shell and installs the `mw-model` command integration idempotently for Fish, Bash, or Zsh.

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
- `skills/lecture-learning/SKILL.md` -> `/mw-learn`
- `skills/exam-review/SKILL.md` -> `/mw-exam`
- `skills/slide-to-lecture/SKILL.md` -> `/slide-learning` and the Lecture learning Stage 1
- `skills/roundtrip-screenshot/SKILL.md` -> image/PDF crop verification when needed
- `skills/paper/SKILL.md` -> `/mw-paper`
- `skills/notion/SKILL.md` -> `/mw-notion`
- `skills/model/SKILL.md` -> `/mw-model`

Command Markdown files also live under `commands/` for clients that support file-based command loading.

## File Contract

See `references/state-contract.md` for v2.1 milestone state, `references/paper-state-contract.md` for paper state schema 1, `references/paper-notes-contract.md` for close reading, `references/summary-contract.md` for grounded summaries, `references/slides-contract.md` for P5 slide authoring, `references/quiz-contract.md` for P6 expert Q&A, `references/marp-assets-contract.md` for the offline presentation supply, and `references/notion-*.md` for Notion MCP and page-craft contracts.
