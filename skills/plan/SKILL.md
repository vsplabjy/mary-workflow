---
name: plan
description: Clarify material uncertainties and freeze independently verifiable milestones. Use for /mw-plan or a Mary Workflow planning request.
---

# Mary Workflow: Plan

Run `python ~/.codex/skills/mary-workflow/scripts/mw_codex.py mw-plan` from the project root. Use the pinned phase and [state contract](../../references/state-contract.md).

Require a complete project brief. Reuse prior answers and relevant context; verify evidence affected by changes. Ask only questions that can alter scope, acceptance, or important choices. Use the host's structured question tool when available, otherwise concise plain text. Do not impose a minimum interview count. Missing information that determines authorization must be answered before dependent work; routine implementation choices may use disclosed assumptions.

Split by dependency and independently verifiable delivery. `estimated_scope` reports expected non-test file count; it is not a cap. Do not invent extra milestones. Record the user's actual requirements, meaningful assumptions, deliverables, acceptance, and optional confirmation gates. Freeze the inspectable draft in `PLANNED` and display it. Existing authorization should not be requested again; a planning-only request never authorizes execution.

Planning does not edit product files, run milestone acceptance, or start execution. An explicit `/mw-run` confirms and starts the frozen plan. Persist only real answers; never convert timeout, silence, a default choice, or discussion agreement into execution authorization.
