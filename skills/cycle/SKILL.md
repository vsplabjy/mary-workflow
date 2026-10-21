---
name: cycle
description: Refresh changed project understanding incrementally and archive a completed Mary Workflow cycle. Use for /mw-cycle.
---

# Mary Workflow: Cycle

Run `python ~/.codex/skills/mary-workflow/scripts/mary_workflow.py cycle` from the project root.

If it reports `refresh_required`, render `mw-init` and use the [memory contract](../../references/memory-contract.md). Read added/modified files, account for deletions and affected dependencies, submit an incremental brief update with explicit retained entries and superseded facts, then run `cycle` again. The runtime computes coverage and merges a complete brief; do not manually resubmit every unchanged file description.

Report the archive path, new cycle, and project brief version. Preserve facts and confirmed project preferences/decisions; archive task-local execution, review, and retry evidence. Do not overwrite host memory or auto-start unrelated work. The next task can be planned with `/mw-plan`.

The aggregate `.mary-workflow/reports/index.html` and presentation packages containing their own `index.html` remain at their original paths across cycle archival; formal receipts still move to the cycle archive. Follow the [report contract](../../references/report-contract.md): keep essential previews inside each package and use durable evidence locations, not transient analysis links. Do not treat preservation of a presentation as fresh acceptance.

Reuse the reviewed changes to update affected lightweight module introductions and handoff per the [knowledge contract](../../references/knowledge-contract.md). Brief refresh preserves richer authored introductions and leaves affected ones stale until updated. No additional scan or hash is needed for these descriptions.

For a bound SDD change, `FINISHED` permits merging its accepted delta into `openspec/specs/` and archiving the change with the cycle evidence. The runtime checks the frozen baseline and uses a recoverable archive journal; resolve conflicts instead of overwriting newer specs. A stopped unfinished cycle archives execution evidence only and leaves its change unmerged for later work. Never treat archival as acceptance. See the [SDD contract](../../references/sdd-contract.md).
