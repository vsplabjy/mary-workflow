---
name: status
description: Show persisted Mary Workflow phase, current tasks, validation, and blockers without changing state. Use for /mw-status.
---

# Mary Workflow: Status

Run `python ~/.codex/skills/mary-workflow/scripts/mw_codex.py mw-status` from the project root. Report the project brief and refresh status, pinned contract version, current cycle and phase, frozen plan revision/digest, authorization, run status and identity, current milestone, worker attempts, validation, independent review, and blockers when those records are available.

Present phase-local progress from persisted records. A host TodoList is a view, not another source of task truth. Do not claim a pending worker completed or a skipped command passed. This command is read-only: do not renew authorization, create tasks, or modify state.
