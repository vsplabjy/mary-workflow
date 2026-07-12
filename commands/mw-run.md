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
3. If phase is `PLANNED`, first present the rendered `Final Plan Confirmation Evidence` exactly as recorded so the user can inspect questions, answers, defaults, and milestones. Then copy the plaintext token from `Run Authorization`, apply `start_execution`, rerender, and begin execution. This action confirms the plan and acquires the run lease atomically.
4. If status is `stopped`, consume the rendered resume token with `resume_execution`, then rerender the preserved phase.
5. If phase is `EXECUTING`, implement the current milestone and apply `mark_task_done` or `record_error`.
6. If phase is `REVIEWING`, review diff and acceptance evidence, then apply `set_phase` or `record_error`.
7. If phase is `DEBUGGING`, enqueue a fix milestone with `enqueue_fix_task`.
8. If phase is `PLANNING`, stop and tell the user to complete `/mw-plan`; `/mw-run` must not bypass the interview.
9. Continue the automatic loop until the workflow reaches `FINISHED`, needs user confirmation, or is blocked.
