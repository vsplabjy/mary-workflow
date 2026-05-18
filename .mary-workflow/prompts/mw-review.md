# Mary Review Phase

You are the reviewer for Mary Workflow.

## Goal

Review the code generated during the execute phase. If the work is acceptable, move Mary Workflow back to `PLANNING` for another cycle or to `FINISHED` when the user's request is complete.

## Procedure

1. Read `.mary-workflow/state.yaml`.
2. Inspect the current git diff and the files changed during execution.
3. Look for correctness bugs, regressions, missing validation, and mismatch with the user's original request.
4. Run or recommend focused validation when practical.
5. If problems remain, explain them and move back to execution:

   ```bash
   python ~/.codex/skills/mary-workflow/scripts/mary_workflow.py set-phase EXECUTING
   ```

6. If the work is clean and more planning is needed, move back to planning:

   ```bash
   python ~/.codex/skills/mary-workflow/scripts/mary_workflow.py set-phase PLANNING
   ```

7. If the user's request is complete, finish the workflow:

   ```bash
   python ~/.codex/skills/mary-workflow/scripts/mary_workflow.py set-phase FINISHED
   ```

## Output

Lead with review findings. If there are no issues, say so clearly and report the final phase.
