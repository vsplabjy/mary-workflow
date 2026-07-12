---
name: status
description: Show Mary Workflow v2.1 status without mutating state. Use when the user invokes /mw-status.
---

# Mary Workflow: Status

Show current Mary Workflow state.

## Procedure

1. Work from the user's current project root.
2. Render status context:

   ```bash
   python ~/.codex/skills/mary-workflow/scripts/mw_codex.py mw-status
   ```

3. Report current cycle, phase, interview status/round, final-plan confirmation, lease status/run id, grant purpose/fingerprint, current milestone, action counts, rejected envelope count, and phase history. Never expose a plaintext grant token.
4. Do not mutate `.mary-workflow/state.yaml`.
