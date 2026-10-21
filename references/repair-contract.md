# Repair budget contract

This is the maintained source for the automatic repair budget. [state-contract.md](state-contract.md) owns phases and action payloads; [subagent-contract.md](subagent-contract.md) owns dispatch and evidence. Read this once when a failure, needs-fix finding, or retry appears; do not duplicate its rules in other files.

## Budget field and freezing

Each milestone carries an optional `max_repair_rounds`. It is a non-negative integer: booleans, negative numbers, floats, numeric strings and explicit `null` are rejected. When omitted, the milestone uses the default of `2`. `0` is legal and means the first implementation is authorized but no automatic repair round may start after a failure. Serialization may preserve the omission so existing plan identities stay compatible; behavior still applies the default.

The budget binds when the plan is frozen with `update_state` (including SDD-derived plans, where the frozen `mary-task` definitions may carry the field). It cannot be changed after execution starts. Adding budget requires explicit user authorization recorded through the existing mechanisms: `request_replan` with the user's actual approval (the primary path), or — for a `gate: confirm` milestone mid-execution — `confirm_milestone` with the optional `authorize_repair_rounds` integer, which appends a recorded authorization entry and raises that origin's authorized maximum. An agent or worker may never raise its own limit by editing the frozen plan, relabeling, or self-declaring a new default.

Rounds attach to the original milestone (the lineage origin), following its `repair_of` chain: a new task id, a different agent, `retry_of`, a repair of a repair, stop/resume, or a replan does not reset or silently start a new count. Usage is persisted in `state.runtime_meta.repair_budget` — a per-origin history of `rounds_used`, `authorized_max` and `history_known`, plus a ledger of registered rounds (each with origin, reason, phase and timestamp) — and survives pause and replanning. When the history cannot be established (for example, a migrated or partially recorded project), `history_known` is false: treat it conservatively, refuse further automatic repairs and tell the user how to authorize continuing, rather than assuming zero used rounds. The status command surfaces the per-origin `used/max` count whenever rounds are used or exhausted.

The runtime also retains each origin's authorized write scope and derives an internal `budget_origin` when replanning relabels the same work. A unique overlapping historical scope carries its usage forward; ambiguous lineage is refused and requires preserving the original milestone IDs. A missing ledger in an already-running legacy plan is unknown, not zero. New plans initialize known history at freeze. Round identities include the plan revision so reused repair milestone numbers cannot accidentally reuse an earlier round. Dispatch publication persists its reservation before a worker record is exposed; interruption afterward does not grant a free repair.

Cycle archives preserve the previous ledger. A new cycle may initialize a fresh budget for unrelated work or work whose original milestone was accepted; unfinished work with overlapping scope retains its history, so archiving a stopped task does not grant free repairs. Reused milestone numbers alone do not bind an unrelated new task to an old task's exhausted budget.

## What consumes a round

One repair round = one failed attempt followed by one modified implementation and its direct re-verification. The initial implementation and its first verification never consume a round. A round is charged when repair work is authorized after:

- `record_error` followed by `enqueue_fix_task`;
- a `needs-fix` review that returns the implementation to EXECUTING;
- a worker failure or failed validation followed by a fresh redispatch of the implementation. The charge falls on the first fresh implementer dispatch after the failure; a new task id is required (task ids are never reused), and a redispatch labeled only `retry_of` does not escape the charge — it is a new round and is rejected at exhaustion. A `mark_task_done` attempt after a failed validation does not itself consume a round; completion already refuses non-passing evidence.

A failed validation ends that attempt's write authorization even while the task record stays open: the same attempt cannot rerun `run_validation`, cannot submit `ready_for_review`, and its further product writes are legal only through a fresh implementer dispatch charged to the budget. A timeout remains retryable within the same attempt like a transient tool error. This closes the free repair channel of "keep editing and re-validating on the original failed dispatch".

Register the consumed round persistently before product writes for that round begin; resuming an already-registered round does not decrement again.

The following do not consume a round:

- the initial implementation and first verification, including parallel independent initial slices;
- verifier or explorer dispatches (review and diagnosis never burn budget);
- parallel slices implementing the same already-registered round (one round, not one per slice);
- retrying transient tool errors within a live attempt, and continuing an original still-valid dispatch;
- ordinary experiment supervision or external-resource waits, which are separate authorizations, not repair rounds.

## Exhaustion and closure

When a milestone reaches its limit, the runtime rejects the action that would authorize another automatic repair round: `enqueue_fix_task`, needs-fix rework, and failed-attempt redispatch are refused while the original milestone still owns the work; the rejection names the exhausted origin and the authorization path. The phase, evidence, and every completed attempt are preserved exactly; a budget stop is never recorded as `FINISHED` or as acceptance. `run_validation` itself never consumes budget. Relabeling the same work as a quick fix or independent experiment to escape the limit is forbidden, and exhaustion authorizes no GPU, training run, or paid external service.

At exhaustion the main agent delivers the failure report required by [report-contract.md](report-contract.md): what consumed each round, the earliest confirmed cause or `UNKNOWN`, what was completed and what remains, actual check states, and the concrete next step (user authorization to add budget, a replan, or an explicit stop). Continuing requires the user's recorded authorization; stop/resume preserves the count.
