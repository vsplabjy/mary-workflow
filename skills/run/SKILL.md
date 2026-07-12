---
name: run
description: Run or resume Mary Workflow automatic milestone execution. Use when the user invokes /mw-run.
---

# Mary Workflow: Run

Run the current Mary Workflow phase. This replaces `/mw-next`, `/mw-resume`, and `/mw-review`.

## Procedure

1. Work from the user's current project root.
2. Render current run context:

   ```bash
   python ~/.codex/skills/mary-workflow/scripts/mw_codex.py mw-run
   ```

3. Treat the rendered output as active instruction context.
4. Execute the loaded phase:
   - `PLANNED`: present `Final Plan Confirmation Evidence` exactly as recorded, then copy the plaintext token from `Run Authorization`, apply `start_execution`, rerender, and continue. This confirms the inspected plan and acquires the run lease.
   - stopped active phase: apply `resume_execution` with the rendered resume token, then rerender the preserved phase.
   - `EXECUTING`: implement current milestone and apply `mark_task_done` or `record_error`.
   - `REVIEWING`: review diff and acceptance evidence, then apply `set_phase` or `record_error`.
   - `DEBUGGING`: enqueue a fix milestone with `enqueue_fix_task`.
   - `PLANNING`: stop and require completion of `/mw-plan`; do not bypass the interview.
5. Continue until `FINISHED`, blocked, stopped, or a `gate: confirm` milestone requires the user.
