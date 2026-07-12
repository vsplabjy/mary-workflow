---
name: plan
description: Run the adaptive interview gate, then plan Mary Workflow milestones. Use when the user invokes /mw-plan or asks Mary to split a request into workflow milestones.
---

# Mary Workflow: Plan

Load Mary Workflow's planning phase and create milestone state.

## Procedure

1. Work from the user's current project root.
2. Render planning context:

   ```bash
   python ~/.codex/skills/mary-workflow/scripts/mw_codex.py mw-plan
   ```

3. Treat the rendered output as active instruction context.
4. Follow persisted interview state: ask only boundary-changing questions, resolve answers, revise when requested, then freeze the exact draft in `PLANNED`. Every default or assumption, including with interview disabled, must be displayed and explicitly confirmed before freezing.
5. End after questions or after displaying the frozen plan. `/mw-run` itself confirms and starts that plan.
6. Do not edit product code, run acceptance commands, invoke `/mw-run`, or emit `start_execution` during planning.
