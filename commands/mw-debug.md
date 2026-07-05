---
description: Load Mary Workflow debug phase and enqueue a focused fix milestone.
argument-hint: [error-summary]
---

# /mw-debug

Load Mary Workflow's debug phase.

## Instructions

1. From the project root, render debug context:

   ```bash
   python ~/.codex/skills/mary-workflow/scripts/mw_codex.py mw-debug
   ```

2. Treat the rendered output as active instruction context.
3. Follow `mw-debug.md`: verify `workflow.phase: DEBUGGING`, inspect `last_error`, output one `enqueue_fix_task` action, and apply it with `mary_workflow.py apply-action`.
4. If the workflow is not in `DEBUGGING`, report the current phase and do not mutate state.

