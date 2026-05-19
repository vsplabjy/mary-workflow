---
description: Initialize Mary Workflow in the current project.
argument-hint: [--with-examples]
---

# /mw-init

Initialize Mary Workflow in the current project directory.

## Instructions

1. Run the runtime helper from the user's current project root:

   ```bash
   python ~/.codex/skills/mary-workflow/scripts/mary_workflow.py init
   ```

2. If the user explicitly asked for example prompts in `$ARGUMENTS`, run:

   ```bash
   python ~/.codex/skills/mary-workflow/scripts/mary_workflow.py init --with-examples
   ```

3. Report the initialized `.mary-workflow/` files and the current phase.
4. Tell the user that `/mw-start` starts planning, and `/mw-plan` can load the planning prompt directly.

