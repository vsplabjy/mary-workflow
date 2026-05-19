---
description: Start Mary Workflow and set the project to the planning phase.
---

# /mw-start

Start Mary Workflow for the current project.

## Instructions

1. If `.mary-workflow/state.yaml` is missing, stop and tell the user to run `/mw-init`.
2. Run:

   ```bash
   python ~/.codex/skills/mary-workflow/scripts/mary_workflow.py start
   ```

3. Report the workflow status, phase, current prompt, and progress.
4. Do not plan or edit project code in this command. The next command should usually be `/mw-plan`.

