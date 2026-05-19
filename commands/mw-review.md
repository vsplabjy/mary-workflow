---
description: Review Mary Workflow changes and decide the next phase.
---

# /mw-review

Load Mary Workflow's review phase and inspect the completed work.

## Instructions

1. From the user's current project root, render the review context:

   ```bash
   python ~/.codex/skills/mary-workflow/scripts/mw_codex.py mw-review
   ```

2. Treat the rendered output as the active instruction context for this turn.
3. Follow the loaded `mw-review.md` protocol exactly:
   - read `.mary-workflow/state.yaml`;
   - verify `workflow.phase` is `REVIEWING`;
   - inspect the relevant diff and validation evidence;
   - lead with review findings;
   - output an `{"action":"set_phase","data":{...}}` JSON object;
   - apply it through `mary_workflow.py apply-action`.
4. Use `EXECUTING` for fixes, `PLANNING` for another planning cycle, and `FINISHED` when the user request is complete.

