---
description: Convert the latest Mary Workflow error into a focused fix task.
argument-hint: [error-summary]
---

# /mw-debug

Load Mary Workflow's debug phase and convert `last_error` into a repair task.

## Instructions

1. From the user's current project root, render the debug context:

   ```bash
   python ~/.codex/skills/mary-workflow/scripts/mw_codex.py mw-debug
   ```

2. Treat the rendered output as the active instruction context for this turn.
3. Follow the loaded `mw-debug.md` protocol exactly:
   - read `.mary-workflow/state.yaml`;
   - verify `workflow.phase` is `DEBUGGING`;
   - inspect `last_error`;
   - output one `{"action":"enqueue_fix_task","data":{...}}` JSON object;
   - apply it through `mary_workflow.py apply-action`.
4. If `$ARGUMENTS` contains new error details but the workflow is not yet in `DEBUGGING`, first record the error with `mary_workflow.py record-error`, then load this command again.

