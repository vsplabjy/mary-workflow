---
name: plan
description: Plan Mary Workflow milestones. Use when the user invokes /mw-plan or asks Mary to split a request into workflow milestones.
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
4. Follow `mw-plan.md`: verify `PLANNING`, create 1 to 7 milestones with `deliverables`, `acceptance`, and `estimated_scope`, output `update_state`, and apply it with `mary_workflow.py apply-action`.
5. Do not edit product code during planning.

