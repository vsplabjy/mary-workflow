---
description: Stop Mary Workflow without deleting state.
---

# /mw-stop

Stop Mary Workflow while keeping `.mary-workflow/state.yaml` and task history.

## Instructions

1. If `.mary-workflow/state.yaml` is missing, stop and tell the user to run `/mw-init` first.
2. Run:

   ```bash
   python ~/.codex/skills/mary-workflow/scripts/mary_workflow.py stop
   ```

3. Report the stopped status and current phase.

