---
description: Run the Mary Workflow prompt for the current phase.
---

# /mw-next

Resume Mary Workflow from the current `workflow.phase`.

## Instructions

1. From the user's current project root, render the current phase context:

   ```bash
   python ~/.codex/skills/mary-workflow/scripts/mw_codex.py mw-next
   ```

2. Treat the rendered output as the active instruction context for this turn.
3. Follow the loaded phase prompt exactly and update state only through `mary_workflow.py apply-action`.
4. If the current phase is `FINISHED`, report that the workflow is already complete and do not mutate state.

