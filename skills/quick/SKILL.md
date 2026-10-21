---
name: quick
description: Complete a small authorized fix, document edit or configuration change directly with one agent and relevant validation. Use /mw-quick or a bounded development request that does not need formal milestone/SDD acceptance.
---

# Direct work

Shared rules: [task policy](../../references/task-policy.md).

Read persisted project context first, then the affected files and relevant dependencies. Follow the shared policy's explicit-path knowledge update/stale rule, make the authorized change and inspect the actual diff. No full-project init, inventory coverage, SDD artifacts or worker dispatch is required. Single-agent execution is a normal choice even when workers exist. Ask only for scope or decisions that cannot reasonably be inferred. Planning-only and read-only requests retain their literal limits.

Run the smallest meaningful checks affected by the change. Reuse trustworthy current test evidence; documentation edits do not require rerunning unrelated experiments. Ordinary failures can be repaired within the same authorized task without formal DEBUGGING/fix milestones, but the [repair budget](../../references/repair-contract.md) still applies: default exactly two automatic repair rounds, initial implementation excluded, or the user's explicit override (including zero). Before each repair batch, record its reason and consumed round in the current task's local record; preserve the count and evidence across handoff. At exhaustion stop automatic product edits and report the unresolved work; only explicit user authorization permits an increase. This direct-work limit is an agent obligation, not a sandbox-enforced runtime counter. Do not weaken tests or acceptance. Record the real failure, remedy, actual verification and remaining limits in delivery. Keep durable module/handoff facts in the knowledge records; leave stale status visible if the introduction cannot be completed now.

When the user explicitly requests a report, or the direct task has a substantial independently useful deliverable, apply the [HTML report contract](../../references/report-contract.md) before delivery and include its exact path; a failed or abandoned larger direct task closes the same way, after stopping work and letting writes stabilize. A routine small edit alone does not trigger a report. Preserve read-only/discussion boundaries; do not create report files unless authorized.

Delegate only when independent work or context isolation merits it. A separate review is useful for critical interfaces, migrations, evaluation-code changes or surprising results; small edits need a deliberate diff review, not a manufactured second identity. Do not claim independent review when the same agent reviewed its own work.

This entry does not change or accept formal state. Work already covered by an active frozen milestone/SDD change follows that contract; do not relabel it to evade scope, stop or acceptance. For a settled-method experiment use [experiment](../experiment/SKILL.md). For cross-cutting behavior changes needing durable specifications or formal acceptance use [plan](../plan/SKILL.md). Never initialize a full workflow solely to do a small edit. Do not commit, publish or mutate external services without applicable authorization.
