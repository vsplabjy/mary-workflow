# Mary Workflow ExamPass Profile

Use this prompt with `skills/exam-review/SKILL.md` as the governing content contract. This profile adds exam-review content boundaries; it does not add a new state phase or action.

## Language Policy

Reasoning, progress updates, review conclusions, and user-visible responses must follow `.mary-workflow/config.yaml` `output.language`: `zh` means Chinese, `auto` follows the current session, and `en` means English. Machine fields remain English, including command names, file names, YAML keys, milestone ids, phase values, action names, and JSON keys. `log.md` remains English for grep and audit stability.

## Scope Gate

Confirm the course, exam identity/type, exact scope, exam date or remaining days, today's single 25-minute block, and review mode. Modes are `平衡模式` (default), `考试模式`, and `深度模式`; recommend exam mode when `<= 3` days remain. One chapter, one whole-exam package, or one mock-exam package is one bounded milestone. Do not silently add chapters, homework solutions, unrelated source material, or a new exam.

## Local Delivery Contract

- Local files are the default source of truth and delivery target.
- Reuse the project's existing course/notes tree. If none exists, use a project-local path such as `notes/<course>/`; keep review notes, the course Mistake Log, source index, and local schedule records in that tree.
- `.mary-workflow/` is reserved for workflow state, plans, reports, logs, and cycle archives. Do not put review content or the Mistake Log there.
- Every content file changed by the milestone must appear as a relative path in `deliverables`. Do not invent external page ids, URLs, calendar events, or synchronization results.
- Only use another destination when the user explicitly names it in the current request. Keep the local review files as the working record unless the user explicitly requests a separate export or synchronization step.

## Phase Gate

Read `.mary-workflow/state.yaml` before any review work. If it is missing, stop and require `/mw-init`.

- `FINISHED`: stop and require `/mw-cycle`; do not edit review files.
- `PLANNING`: route through `/mw-plan`. Confirm scope/date/mode, freeze 1–3 bounded milestones, and do not execute content or acceptance commands here.
- `PLANNED`: show the exact persisted plan and wait for `/mw-run`. Do not consume the grant from this profile.
- `EXECUTING`: require an active execution lease, work only on the current milestone, and use only `mark_task_done` or `record_error`.
- `REVIEWING`: inspect only the current diff, milestone deliverables, acceptance evidence, and report. Use only `set_phase` or `record_error`; do not edit content or use `update_state`.
- `DEBUGGING`: route through `/mw-debug` and enqueue one focused fix; do not resume review work from this profile.
- A stopped run is resumed only through the `/mw-run` resume gate. Preserve the phase and lease; do not create a new plan.

The shared phase prompt and renderer are authoritative for action envelopes. Never invent an exam-specific action, bypass the phase whitelist, hand-edit `state.yaml`, or treat missing scope/source/date information as permission to guess.

## Boundary Ritual

At every milestone boundary:

1. Re-read `.mary-workflow/state.yaml` and the current milestone.
2. Discard prior working memory and trust only the current filesystem and rendered context.
3. Read and edit only files related to the current milestone's `deliverables`.
4. Keep source notes unchanged; write reconstructed review material, mistakes, and answer sections only in the scoped local files.

## Execution Route

1. Locate and reuse local Course Hub, Lecture notes, slides/handouts, existing review notes, local schedule, and course Mistake Log.
2. Generate only the requested chapter review, whole-exam package, mock papers, or Mistake Log entries.
3. Label importance, explain formulas and exam use, compare confusing concepts, add self-tests, and add error checks.
4. Update the local Mistake Log and repeated-error reminders; record exam dates in the local Course Hub and existing local schedule file when one exists.
5. Review scope, local naming/parentage, source attribution, answer separation, cram card, and the exact mode/date assumptions.

Keep answers separate from question blocks. Do not solve a student's live homework as part of review. Do not widen the confirmed exam scope silently.

## Acceptance Evidence

Before `mark_task_done`, verify the local relative paths, exact exam scope/date/mode, importance labels, formulas, self-tests, Mistake Log linkage, answer separation, and one next 25-minute action. The result must state:

- changed local files and their roles;
- the confirmed scope, date/remaining days, and mode;
- which ExamPass checklist items passed;
- which inputs were unavailable and the resulting gate or placeholder; and
- the next single learning action.

If validation fails, use `record_error` with the failing command, concise stderr, and return code. Do not mark the milestone done.
