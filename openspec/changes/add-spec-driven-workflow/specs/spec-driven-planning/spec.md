# Spec-driven planning delta

## Purpose

Make behavior changes inspectable as specifications and connect each proposed scenario to frozen implementation tasks, evidence, review and accepted specifications.

## ADDED Requirements

### Requirement: Authoritative change tasks
The workflow SHALL derive bound execution milestones from a single task source and validate scenario-to-check mappings before freeze.

#### Scenario: Valid change is bound
- **WHEN** a complete project brief and valid change artifacts are bound during planning
- **THEN** the runtime derives milestones from tasks and freezes only an exact matching plan.

#### Scenario: Scenario coverage is incomplete
- **WHEN** a changed scenario lacks a task mapping or references a nonexistent check
- **THEN** checking or binding the change reports a concrete error.

#### Scenario: No behavior changes
- **WHEN** a change explicitly declares skip_specs with a reason and no delta
- **THEN** the workflow accepts the no-spec planning path without fabricated behavioral requirements.

### Requirement: Frozen specification identity
The runtime SHALL bind change artifacts and accepted spec baselines into plan identity and reject stale execution or acceptance.

#### Scenario: Bound source changes
- **WHEN** a bound definition or its accepted baseline changes after freeze
- **THEN** execution and acceptance require legal replanning and a current binding.

#### Scenario: Task is accepted
- **WHEN** a bound milestone passes review and is accepted
- **THEN** its source checkbox reflects acceptance without changing the frozen definition identity.

### Requirement: Explicit instruction authorization
The runtime SHALL support explicit natural-language execution instructions alongside the command entrypoint, retaining their actual text and plan identity.

#### Scenario: User directly requests execution
- **WHEN** the coordinator records a real execution instruction with source user_instruction and intent execute for the current frozen plan
- **THEN** execution starts or resumes without requiring the user to repeat authorization as a command.

### Requirement: Scenario review evidence
Bound change acceptance SHALL require review decisions and concrete evidence for every current milestone scenario or delta operation reference.

#### Scenario: Review omits a scenario
- **WHEN** an otherwise passing review omits a required scenario or lacks its evidence
- **THEN** the runtime rejects acceptance.

### Requirement: Recoverable specification archive
The workflow SHALL merge only accepted finished changes into accepted specs, detect baseline conflicts and preserve resumable archive progress.

#### Scenario: Finished change is archived
- **WHEN** all bound milestones are accepted and cycle archive completes
- **THEN** the delta becomes accepted specification content and the change is archived with its evidence.

#### Scenario: Archive is interrupted or conflicts
- **WHEN** archive is interrupted or the accepted baseline conflicts with its frozen identity
- **THEN** recovery preserves recorded progress and refuses to overwrite conflicting content.

#### Scenario: Accepted product changes before archive
- **WHEN** a product artifact changes after final acceptance and before archive
- **THEN** the runtime refuses to merge until the revised work receives current evidence and acceptance.

#### Scenario: Unfinished cycle is archived
- **WHEN** a stopped quiescent unfinished cycle is archived
- **THEN** execution evidence is preserved and the change remains unmerged.

### Requirement: Existing workflow compatibility
The workflow SHALL preserve unbound legacy plans, pinned bundles and independent paper/Notion scenes.

#### Scenario: Existing unbound state is loaded
- **WHEN** an existing state without an SDD binding is loaded
- **THEN** its original lifecycle remains available without synthetic specifications or a silent bundle upgrade.
