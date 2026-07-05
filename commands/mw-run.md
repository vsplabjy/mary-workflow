---
description: Run or resume Mary Workflow automatic milestone execution.
---

# /mw-run

Run the current Mary Workflow phase. This command replaces `/mw-next`, `/mw-resume`, and `/mw-review`.

## Instructions

1. From the project root, render current run context:

   ```bash
   python ~/.codex/skills/mary-workflow/scripts/mw_codex.py mw-run
   ```

2. Treat the rendered output as active instruction context.
3. If phase is `EXECUTING`, implement the current milestone and apply `mark_task_done` or `record_error`.
4. If phase is `REVIEWING`, review diff and acceptance evidence, then apply `set_phase` or `record_error`.
5. If phase is `DEBUGGING`, enqueue a fix milestone with `enqueue_fix_task`.
6. Continue the automatic loop until the workflow reaches `FINISHED`, needs user confirmation, or is blocked.

