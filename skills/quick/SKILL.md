---
name: quick
description: Complete a small authorized fix, document edit or configuration change directly with one agent and relevant validation. Use /mw-quick or a bounded development request that does not need formal milestone/SDD acceptance.
---

# Direct work

Shared rules: [task policy](../../references/task-policy.md).

Read persisted project context first, then the affected files and relevant dependencies. Make the authorized change and inspect the actual diff; update knowledge records at delivery per the shared policy. No full-project init, inventory coverage, SDD artifacts or worker dispatch is required. Ask only for scope or decisions that cannot reasonably be inferred. Planning-only and read-only requests retain their literal limits.

Run the smallest meaningful checks affected by the change. Reuse trustworthy current test evidence; documentation edits do not require rerunning unrelated experiments. Ordinary failures can be repaired within the same authorized task and rechecked without creating DEBUGGING/fix milestones. Record the real failure and remedy in the delivery; do not weaken tests or acceptance. Report outcome, actual verification and remaining limits in chat.

Delegation follows the shared policy. Small edits need a deliberate diff review, not a manufactured second identity; a separate review is worth it for critical interfaces, migrations, evaluation-code changes or surprising results. Never call same-agent review independent.

This entry does not change or accept formal state. Work already covered by an active frozen milestone/SDD change follows that contract; do not relabel it to evade scope, stop or acceptance. For a settled-method experiment use [experiment](../experiment/SKILL.md). For cross-cutting behavior changes needing durable specifications or formal acceptance use [plan](../plan/SKILL.md). Never initialize a full workflow solely to do a small edit. Do not commit, publish or mutate external services without applicable authorization.
