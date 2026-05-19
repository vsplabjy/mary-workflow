---
description: Show Mary Workflow state without mutating it.
---

# /mw-status

Show the current Mary Workflow state.

## Instructions

1. From the user's current project root, render the status context:

   ```bash
   python ~/.codex/skills/mary-workflow/scripts/mw_codex.py mw-status
   ```

2. Report the current status, phase, progress, current prompt, current task, and task list.
3. Do not mutate `.mary-workflow/state.yaml`.

