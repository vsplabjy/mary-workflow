---
description: Resume Mary Workflow from the current phase.
---

# /mw-resume

Resume Mary Workflow from the current `workflow.phase`. This is an alias of `/mw-next`.

## Instructions

1. From the user's current project root, render the current phase context:

   ```bash
   python ~/.codex/skills/mary-workflow/scripts/mw_codex.py mw-resume
   ```

2. Treat the rendered output as the active instruction context for this turn.
3. Follow the loaded phase prompt exactly and update state only through `mary_workflow.py apply-action`.
4. If the current phase is `FINISHED`, report that the workflow is already complete and do not mutate state.

