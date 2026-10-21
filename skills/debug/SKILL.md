---
name: debug
description: Diagnose the latest Mary Workflow failure and queue a focused repair without editing product files in DEBUGGING. Use for /mw-debug.
---

# Mary Workflow: Debug

Run `python ~/.codex/skills/mary-workflow/scripts/mw_codex.py mw-debug` from the project root. Verify `DEBUGGING` and read the recorded error, failing command, artifact version, and relevant files. Delegate a bounded read-only diagnosis when useful; diagnostic workers return evidence and proposed scope, not product edits.

Apply `enqueue_fix_task` through `mary_workflow.py apply-action` using the pinned debug phase and [state contract](../../references/state-contract.md). The repair must link to the failed work, remain within existing authorization, and preserve acceptance. Before enqueueing, check the milestone's remaining repair rounds ([repair contract](../../references/repair-contract.md)): when `max_repair_rounds` is exhausted the runtime rejects another automatic repair — preserve the diagnosis, stop, and hand off with the failure HTML report; continuing needs recorded user authorization, a replan, or an explicit stop. Do not weaken validation or silently enlarge scope. A material scope change uses `request_replan` with concrete feedback, after host workers have stopped writing. Fix implementation starts only after the runtime returns to `EXECUTING`.

If the phase is different, explain the legal next action. Preserve the original failure and all attempts. Environment/input blockers require a specific recovery need; they are not an invitation to retry forever.

An exhausted budget is a decision point, not a dead end for evidence: record the earliest confirmed cause or `UNKNOWN`, what each round changed, check states and remaining work in the closure report per the [report contract](../../references/report-contract.md). Never relabel the milestone as finished or accepted.
