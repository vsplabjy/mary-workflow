---
name: plan
description: Clarify material uncertainties and freeze independently verifiable milestones. Use for /mw-plan or a Mary Workflow planning request.
---

# Mary Workflow: Plan

This is the formal milestone planning entry. For a small unbound request, offer a concise plan in context and use [quick](../quick/SKILL.md) when execution is authorized; full project initialization is unnecessary. For a settled method and an instruction to run, use [experiment](../experiment/SKILL.md) without repeating research or requiring SDD artifacts. Planning-only requests still do not authorize execution.

Run `python ~/.codex/skills/mary-workflow/scripts/mw_codex.py mw-plan` from the project root. Use the pinned phase and [state contract](../../references/state-contract.md).

For this formal entry, require a complete project brief and follow [shared task policy](../../references/task-policy.md). Split by dependencies and independently verifiable results; record requirements, assumptions, deliverables, checks and optional confirmation gates. `estimated_scope` is descriptive, not a cap. Freeze the inspectable draft in `PLANNED` using the state contract.

When setting the optional per-milestone `max_repair_rounds` (non-negative integer, default `2` when omitted, `0` = no automatic repair after a failure), follow the [repair contract](../../references/repair-contract.md): the value freezes with the plan, counts failures per original milestone without reset across retries/agents/replans, and can only be raised after start with recorded user authorization. Tell the user what the chosen limit means for automatic fixes.

When the exact check dependencies are known, declare `validation_inputs` before freezing; see [validation inputs](../../references/subagent-contract.md#validation-inputs-and-ownership-audits). Include actual code/test/config/fixture dependencies, not only changed files. Omit the field for an unknown or open-ended dependency set; it cannot be narrowed after running a check.

## Spec-driven planning

For cross-cutting behavior changes or explicitly requested formal specification/acceptance, follow the [SDD contract](../../references/sdd-contract.md). Read relevant accepted specs and source first; describe observable changes using Requirement / Scenario. Author `proposal.md`, delta specs, optional `design.md`, and `tasks.md` in one change directory. Scale detail to the change. A pure refactor/docs change can explicitly use `skip_specs: true` with a reason; do not invent behavioral requirements.

Run `mary_workflow.py sdd-check <change-id>` for read-only validation and source-derived milestones/coverage. Record clarifications and those exact milestones through `update_interview`; apply `bind_change` with `data.change_id`, then freeze with `update_state` matching the source. Fix missing scenarios, unknown references, and missing check mappings before freezing. Display scope, spec changes, acceptance, and assumptions. For revised scope use the legal reopen/replan route before rebinding. Never edit frozen change artifacts to evade their binding.
