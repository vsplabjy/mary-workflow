---
description: Execute the first pending Mary Workflow task.
---

# /mw-run

Load Mary Workflow's execution phase and complete the first pending task.

## Instructions

1. From the user's current project root, render the execution context:

   ```bash
   python ~/.codex/skills/mary-workflow/scripts/mw_codex.py mw-run
   ```

2. Treat the rendered output as the active instruction context for this turn.
3. Follow the loaded `mw-execute.md` protocol exactly:
   - read `.mary-workflow/state.yaml`;
   - verify `workflow.phase` is `EXECUTING`;
   - inspect only files related to the current task;
   - implement and validate the task;
   - output an `{"action":"mark_task_done","data":{...}}` JSON object only after success;
   - apply it through `mary_workflow.py apply-action`.
4. If implementation or validation is blocked, leave the workflow in `EXECUTING` and explain the blocker.

