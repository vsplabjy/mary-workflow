---
description: Load the Mary planning prompt and create up to three workflow tasks.
argument-hint: [request]
---

# /mw-plan

Load Mary Workflow's planning phase and use the user's latest request, plus `$ARGUMENTS` when provided, to create the task list.

## Instructions

1. From the user's current project root, render the planning context:

   ```bash
   python ~/.codex/skills/mary-workflow/scripts/mw_codex.py mw-plan
   ```

2. Treat the rendered output as the active instruction context for this turn.
3. Follow the loaded `mw-plan.md` protocol exactly:
   - read `.mary-workflow/state.yaml`;
   - verify `workflow.phase` is `PLANNING`;
   - create 1 to 3 concrete tasks;
   - output an `{"action":"update_state","data":{...}}` JSON object;
   - apply it through `mary_workflow.py apply-action`.
4. Do not edit product code during planning unless the user explicitly asked for planning artifacts.

