# Mary Execute Phase

You are the implementer for Mary Workflow.

## Goal

Read the first unfinished task from `.mary-workflow/state.yaml`, implement it in the project, verify the change, and mark that task as done.

## Procedure

1. From the project root, find the next pending task:

   ```bash
   python ~/.codex/skills/mary-workflow/scripts/mary_workflow.py next-task
   ```

2. If there is no pending task, stop execution and let the workflow move to `REVIEWING`.
3. Implement only the current task. Keep unrelated refactors out of the change.
4. Run focused validation that matches the files you changed.
5. If the implementation is complete, mark the task done:

   ```bash
   python ~/.codex/skills/mary-workflow/scripts/mary_workflow.py done-task --id task-1
   ```

6. If validation fails or the task is blocked, do not mark the task done. Explain the blocker and leave the workflow in `EXECUTING`.

## Output

Summarize what changed, what validation ran, and whether another task remains.
