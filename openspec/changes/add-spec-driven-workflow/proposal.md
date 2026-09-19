# Add spec-driven planning

## Why

Mary already binds execution to plans and evidence, but requirements live mainly in clarification text and milestones. A maintained behavior specification and explicit scenario-to-evidence mapping make proposed changes and review coverage inspectable.

## What Changes

- Add local accepted specs and change artifacts, with one authoritative task source.
- Bind specification/base identities into plan identity and detect drift.
- Require scenario-level review for bound changes and merge only accepted deltas during recoverable cycle archive.
- Accept explicit natural-language execution instructions while preserving the distinction between acknowledgment and authorization.
- Keep unbound legacy plans, independent research/Notion workflows and pinned bundles compatible.

## Capabilities

### New Capabilities

- `spec-driven-planning`: source-derived plans, scenario traceability, bound review and recoverable spec archive.

### Modified Capabilities

None. Execution authorization, review and pinned-bundle guarantees in `execution-control` remain; the new capability defines the added SDD behavior.

## Impact

Core runtime, worker evidence contracts, pinned bundle contents, maintained skills/phases, generated command surfaces and local regression tests. Python standard library remains sufficient; OpenSpec CLI is optional and full CLI/store/schema compatibility is not claimed.
