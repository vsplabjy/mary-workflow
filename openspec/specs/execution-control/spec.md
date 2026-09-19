# Execution control

## Purpose

Keep project execution tied to an inspectable plan, actual validation evidence, and explicit coordinator acceptance across interruptions and runtime upgrades.

## Requirements

### Requirement: Frozen plan execution
The runtime SHALL bind execution to a frozen plan and explicit user authorization.

#### Scenario: Plan is not frozen
- **WHEN** execution is requested while planning is incomplete
- **THEN** the runtime refuses to start product work.

#### Scenario: Plan identity changes
- **WHEN** a submitted execution action identifies an outdated plan
- **THEN** the runtime rejects that action without accepting old work as current.

### Requirement: Evidence and independent review
The workflow SHALL require recorded validation and coordinator acceptance after review, and SHALL disclose same-agent review in compatibility mode.

#### Scenario: Implementation is submitted
- **WHEN** an implementer submits a ready result
- **THEN** the milestone still requires evidence checks and review before acceptance.

#### Scenario: Evidence becomes stale
- **WHEN** artifacts change after command evidence was recorded
- **THEN** the runtime refuses to reuse stale evidence for acceptance.

### Requirement: Pinned runtime compatibility
Projects SHALL retain their pinned runtime and prompt bundle until an explicit compatible upgrade.

#### Scenario: Installed skill is newer
- **WHEN** ordinary initialization encounters an existing project bundle
- **THEN** the runtime verifies and reuses that bundle instead of silently replacing its behavior.
