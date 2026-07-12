---
description: Pause Mary Workflow v2.1 while keeping state and reports.
---

# /mw-stop

Stop Mary Workflow while keeping `.mary-workflow/state.yaml`, reports, and logs.

## Instructions

1. If `.mary-workflow/state.yaml` is missing, stop and tell the user to run `/mw-init` first.
2. Run:

   ```bash
   python ~/.codex/skills/mary-workflow/scripts/mary_workflow.py stop
   ```

3. Report stopped status, paused run lease, and current milestone. A later `/mw-run` issues a one-time resume grant.
