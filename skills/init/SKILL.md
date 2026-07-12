---
name: init
description: Initialize or reset Mary Workflow v2.1 in the current project. Use when the user invokes /mw-init or asks to initialize Mary workflow.
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
4. Report the project brief path, current cycle, project snapshot, and current phase in Chinese by default.
5. Ask whether later plan/run output should use `zh`, `auto`, or `en`; if the user answers, apply `update_project` with `language`.
6. On an existing v2.1 project, refresh core prompts while preserving state; earlier state contracts require `--reset`.
7. Tell the user the next step is `/mw-plan`.
