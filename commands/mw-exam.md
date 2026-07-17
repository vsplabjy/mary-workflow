---
description: Start the Mary Workflow ExamPass flow for chapter, whole-exam, mistake-log, or mock-exam review.
argument-hint: [course/exam/scope/date/mode]
---

# /mw-exam

Start or resume a bounded exam-review run. `$ARGUMENTS` should contain the course, exam identity, scope, date, and optional mode.

## Instructions

1. Require `.mary-workflow/state.yaml`; if absent, run `/mw-init` first.
2. Render the specialized context:

   ```bash
   python ~/.codex/skills/mary-workflow/scripts/mw_codex.py mw-exam
   ```

3. Load `skills/exam-review/SKILL.md`; use the sibling Slide skill for missing diagrams and the round-trip skill for image crops.
4. Follow the rendered Mary phase. In `PLANNING`, confirm scope/date/mode and freeze the plan; in `PLANNED`, show exact evidence and wait for `/mw-run`; in an active run, execute only the current milestone and apply the normal action envelope.
5. Treat Notion pages, mistake-log entries, calendar events, and local source paths as deliverables. Keep the review scope exact and never silently widen it.
6. End with evidence for page placement, importance labels, formulas, self-tests, mistake-log linkage, and one next 25-minute action.

Use `/mw-run`, `/mw-stop`, `/mw-status`, and `/mw-cycle` for the shared Mary lifecycle.
