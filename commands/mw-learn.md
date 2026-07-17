---
description: Start the Mary Workflow course Lecture learning flow with slides and lecture-transcript fusion.
argument-hint: [course/Lecture/topic and available sources]
---

# /mw-learn

Start or resume a bounded course-learning run. `$ARGUMENTS` is the Lecture/topic and source context.

## Instructions

1. Require `.mary-workflow/state.yaml`; if absent, run `/mw-init` first.
2. Render the specialized context:

   ```bash
   python ~/.codex/skills/mary-workflow/scripts/mw_codex.py mw-learn
   ```

3. Load `skills/lecture-learning/SKILL.md`, then its sibling `slide-to-lecture` skill. Load `roundtrip-screenshot` only when cropping or screenshot verification is needed.
4. Follow the rendered Mary phase. In `PLANNING`, use the normal interview and freeze a bounded Lecture plan; in `PLANNED`, show the exact plan and wait for `/mw-run`; in an active run, execute only the current milestone and apply the normal action envelope.
5. Treat Notion page IDs/URLs, calendar events, and local source paths as deliverables. Do not invent code changes or claim a raw transcript exists when it was not supplied.
6. End with the Lecture acceptance checklist and exactly one next 8–25 minute action.

Use `/mw-run` to execute a planned learning run, `/mw-stop` to pause, `/mw-status` to inspect it, and `/mw-cycle` before starting a new finished learning round.
