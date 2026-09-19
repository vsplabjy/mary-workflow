# Design

## Context

See proposal.md for motivation. Existing `mary_workflow.py` freezes milestones and clarification identity; `mw_workers.py` records validation and review; `mw_bundle.py` pins runtime and phase sources. The execution-control baseline was derived from those implementations and existing runtime/worker/bundle contracts, not from planned SDD behavior.

## Decisions

- Use local `openspec/specs` and `openspec/changes` artifacts. A Python module parses the bounded format without a mandatory external CLI, keeping existing installation requirements.
- Make numbered tasks with `mary-task` JSON the single source for execution milestones. Structured metadata avoids ambiguous natural-language parsing; frozen state is a mapping and evidence record, not a second editable plan.
- Store opt-in binding in existing `runtime_meta.sdd`. Old unbound states remain valid. Source and base hashes participate in frozen identity; checkbox progress does not.
- Treat coverage as traceability. Actual command receipts, artifact identity, reviewer scenario decisions and coordinator acceptance remain required.
- Accept natural-language execution only through explicit source/intent/actual-text fields. The coordinator interprets user intent; runtime validation cannot authenticate a speaker or infer language semantics.
- Merge accepted deltas at FINISHED cycle archive with conflict detection and recoverable SDD/cycle journals. Recheck the accepted product fingerprint before merge; changed accepted products require replanning and renewed evidence. Unfinished stopped work retains its unmerged change.

## Risks and trade-offs

- Format support is narrower than OpenSpec CLI: document and reject unsupported assumptions rather than silently emulating stores/custom schemas.
- Hashes detect cooperating workflow drift, not hostile agents with unrestricted filesystem access.
- Scenario mappings and evidence strings can be misleading: reviewers must inspect behavior and the actual test/source evidence.
- Archive spans multiple files: journal progress and verify expected content before resuming writes.

## Migration and validation

Ship the parser and contract in the pinned bundle; ordinary init preserves old bundles. Explicit upgrades back up the prior bundle. Exercise parsing, source-derived freeze, drift, review coverage, explicit instruction authorization, interrupted/conflicting archive and legacy unbound behavior in local tests. Run generated-surface consistency and the full existing suite. These tests do not establish real-host or external-connector behavior.
