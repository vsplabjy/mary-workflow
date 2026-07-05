---
description: Initialize or reset Mary Workflow v2 in the current project.
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

3. Report the initialized v2 state, project snapshot, and current phase.
4. Tell the user the next command is `/mw-plan`.

