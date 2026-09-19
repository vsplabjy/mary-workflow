---
name: plan
description: Clarify material uncertainties and freeze independently verifiable milestones. Use for /mw-plan or a Mary Workflow planning request.
---

# Mary Workflow: Plan

Run `python ~/.codex/skills/mary-workflow/scripts/mw_codex.py mw-plan` from the project root. Use the pinned phase and [state contract](../../references/state-contract.md).

Require a complete project brief. Reuse prior answers and relevant context; verify evidence affected by changes. Ask only questions that can alter scope, acceptance, or important choices. Use the host's structured question tool when available, otherwise concise plain text. Do not impose a minimum interview count. Missing information that determines authorization must be answered before dependent work; routine implementation choices may use disclosed assumptions.

Split by dependency and independently verifiable delivery. `estimated_scope` reports expected non-test file count; it is not a cap. Do not invent extra milestones. Record the user's actual requirements, meaningful assumptions, deliverables, acceptance, and optional confirmation gates. Freeze the inspectable draft in `PLANNED` and display it. Existing authorization should not be requested again; a planning-only request never authorizes execution.

Planning may author change artifacts but does not edit product implementation files, run milestone acceptance, or start execution. An explicit `/mw-run` or unambiguous instruction to execute confirms and starts the frozen plan. Persist only real answers; never convert timeout, silence, a default choice, or discussion agreement into execution authorization.

## Spec-driven planning

For core code changes follow the [SDD contract](../../references/sdd-contract.md). Read relevant accepted specs and source first; describe observable changes using Requirement / Scenario. Author `proposal.md`, delta specs, optional `design.md`, and `tasks.md` in one change directory. Scale detail to the change. A pure refactor/docs change can explicitly use `skip_specs: true` with a reason; do not invent behavioral requirements.

Run `mary_workflow.py sdd-check <change-id>` for read-only validation and source-derived milestones/coverage. Record clarifications and those exact milestones through `update_interview`; apply `bind_change` with `data.change_id`, then freeze with `update_state` matching the source. Fix missing scenarios, unknown references, and missing check mappings before freezing. Display scope, spec changes, acceptance, and assumptions. For revised scope use the legal reopen/replan route before rebinding. Never edit frozen change artifacts to evade their binding.
