# Mary Workflow Course Learning Profile

Use this prompt with `skills/lecture-learning/SKILL.md` as the governing content contract. This profile adds learning-content boundaries; it does not add a new state phase or action.

## Language Policy

Reasoning, progress updates, review conclusions, and user-visible responses must follow `.mary-workflow/config.yaml` `output.language`: `zh` means Chinese, `auto` follows the current session, and `en` means English. Machine fields remain English, including command names, file names, YAML keys, milestone ids, phase values, action names, and JSON keys. `log.md` remains English for grep and audit stability.

## Scope Gate

The user's request defines the learning scope. Confirm or infer only the minimum needed to identify the course, one Lecture or bounded topic, available local sources, transcript status, the existing local Course Hub/Lecture note, and today's single 8–25 minute block. Surface every inference before the plan is frozen. One Lecture or one bounded topic is one milestone; do not silently combine unrelated Lectures, exams, homework, or projects.

## Local Delivery Contract

- Local files are the default source of truth and delivery target.
- Reuse the project's existing course/notes tree. If none exists, use a project-local path such as `notes/<course>/`; keep generated notes, raw transcripts, source indexes, and local schedule records together according to the existing structure.
- `.mary-workflow/` is reserved for workflow state, plans, reports, logs, and cycle archives. Do not put the Lecture note or transcript there.
- Every content file changed by the milestone must appear as a relative path in `deliverables`. Do not invent external page ids, URLs, or synchronization results.
- Only use another destination when the user explicitly names it in the current request. Keep the local files as the working record unless the user explicitly requests a separate export or synchronization step.

## Phase Gate

Read `.mary-workflow/state.yaml` before any content work. If it is missing, stop and require `/mw-init`.

- `FINISHED`: stop and require `/mw-cycle`; do not edit learning files.
- `PLANNING`: route through `/mw-plan`. Ask or resolve the normal interview, freeze 1–3 bounded milestones, and do not execute content or acceptance commands here.
- `PLANNED`: show the exact persisted plan and wait for `/mw-run`. Do not consume the grant from this profile.
- `EXECUTING`: require an active execution lease, work only on the current milestone, and use only `mark_task_done` or `record_error`.
- `REVIEWING`: inspect only the current diff, milestone deliverables, acceptance evidence, and report. Use only `set_phase` or `record_error`; do not edit content or use `update_state`.
- `DEBUGGING`: route through `/mw-debug` and enqueue one focused fix; do not resume content work from this profile.
- A stopped run is resumed only through the `/mw-run` resume gate. Preserve the phase and lease; do not create a new plan.

The shared phase prompt and renderer are authoritative for action envelopes. Never invent a learning-specific action, bypass the phase whitelist, hand-edit `state.yaml`, or treat a missing transcript/source as permission to guess.

## Boundary Ritual

At every milestone boundary:

1. Re-read `.mary-workflow/state.yaml` and the current milestone.
2. Discard prior working memory and trust only the current filesystem and rendered context.
3. Read and edit only files related to the current milestone's `deliverables`.
4. Keep raw source and raw transcript files unchanged; write corrections and classroom additions to the derived Lecture note with the required markers.

## Execution Route

1. Inspect the local Course Hub note, local child notes, syllabus/schedule, and Source Index.
2. Classify the material and run the Slide to Lecture foundation.
3. Reuse or create the raw recording Markdown file in the existing local structure and required naming/location.
4. When a transcript exists, correct it against slides and fuse only recording-only additions with `🎙` markers; preserve the raw transcript byte-for-byte.
5. Review local parent/ordering links, formulas, images, deadlines, uncertainty markers, summary, next action, and the exact milestone scope.

Record missing inputs as a gate. Do not fabricate a PDF, image, transcript, source link, deadline, or completed file.

## Acceptance Evidence

Before `mark_task_done`, verify the local relative paths, Lecture-learning checklist, source availability, raw-file preservation, and one next 8–25 minute action. The result must state:

- changed local files and their roles;
- which checklist items passed;
- which inputs were unavailable and the resulting gate or placeholder;
- the exact course/Lecture/topic boundary; and
- the next single learning action.

If validation fails, use `record_error` with the failing command, concise stderr, and return code. Do not mark the milestone done.
