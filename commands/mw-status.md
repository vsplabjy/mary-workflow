---
description: Show Mary Workflow v2 state without mutating it.
---

# /mw-status

Show current Mary Workflow state.

## Instructions

1. From the project root, render status context:

   ```bash
   python ~/.codex/skills/mary-workflow/scripts/mw_codex.py mw-status
   ```

2. Report status, phase, current milestone, milestone review states, action counts, rejected envelope count, and phase history.
3. Do not mutate `.mary-workflow/state.yaml`.

