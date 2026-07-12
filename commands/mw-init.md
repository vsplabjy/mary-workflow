---
description: Initialize or reset Mary Workflow v2.1 in the current project.
argument-hint: [--reset]
---

# /mw-init

Initialize Mary Workflow in the current project directory.

## Instructions

1. Run from the user's current project root:

   ```bash
   python ~/.codex/skills/mary-workflow/scripts/mary_workflow.py init
   ```

2. If `$ARGUMENTS` contains `--reset`, run:

   ```bash
   python ~/.codex/skills/mary-workflow/scripts/mary_workflow.py init --reset
   ```

3. Report the project brief path, current cycle, project snapshot, and current phase in Chinese by default.
4. Ask whether the user wants later plan/run output in `zh`, `auto`, or `en`; if they answer, apply `update_project` with `language`.
5. On an existing v2.1 project, refresh core prompts while preserving state; earlier state contracts require `--reset`.
6. Tell the user the next command is `/mw-plan`.
