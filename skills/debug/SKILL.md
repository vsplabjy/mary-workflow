---
name: debug
description: Enqueue a focused Mary Workflow fix milestone from the latest error. Use when the user invokes /mw-debug.
---

# Mary Workflow: Debug

Load Mary Workflow's debug phase and turn `last_error` into a repair milestone.

## Procedure

1. Work from the user's current project root.
2. Render debug context:

   ```bash
   python ~/.codex/skills/mary-workflow/scripts/mw_codex.py mw-debug
   ```

3. Treat the rendered output as active instruction context.
4. Follow `mw-debug.md`: verify `DEBUGGING`, inspect `last_error`, output one `enqueue_fix_task` action, and apply it with `mary_workflow.py apply-action`.
5. If the workflow is not in `DEBUGGING`, report the current phase and do not mutate state.

