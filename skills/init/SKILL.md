---
name: init
description: Initialize or reset Mary Workflow v2 in the current project. Use when the user invokes /mw-init or asks to initialize Mary workflow.
---

# Mary Workflow: Init

Initialize the project-local `.mary-workflow/` workspace.

## Procedure

1. Work from the user's current project root.
2. Run:

   ```bash
   python ~/.codex/skills/mary-workflow/scripts/mary_workflow.py init
   ```

3. If the user passes `--reset`, run `init --reset`.
4. Report the current phase, project snapshot, and tell the user the next step is `/mw-plan`.

