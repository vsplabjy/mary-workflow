---
description: Show Mary Workflow v2.1 state without mutating it.
---

# /mw-status

Show current Mary Workflow state.

## Instructions

1. From the project root, render status context:

   ```bash
   python ~/.codex/skills/mary-workflow/scripts/mw_codex.py mw-status
   ```

2. Report current cycle, phase, interview status/round, final-plan confirmation, lease status/run id, grant purpose/fingerprint, current milestone, action counts, rejected envelope count, and phase history. Never expose a plaintext grant token.
3. Do not mutate `.mary-workflow/state.yaml`.
