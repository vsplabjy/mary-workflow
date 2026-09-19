# Spec-driven development contract

Mary uses a local, bounded subset of the [OpenSpec spec-driven format](https://github.com/Fission-AI/OpenSpec/blob/main/schemas/spec-driven/schema.yaml), inspired by its [change/spec separation](https://github.com/Fission-AI/OpenSpec/blob/main/docs/concepts.md). Specification files define observable behavior; `.mary-workflow/` retains authorization, execution, evidence and acceptance. No Node or OpenSpec CLI is required. This is not a full OpenSpec implementation: stores, custom schemas, alternate planning homes and concurrent change execution are outside this contract.

## Sources and scope

```text
openspec/
  specs/<capability>/spec.md                 # accepted behavior
  changes/<change-id>/
    proposal.md                             # why, what, capabilities, impact
    design.md                               # optional decisions and tradeoffs
    tasks.md                                # authoritative task definitions
    .openspec.yaml                          # optional skip_specs/skip_reason
    specs/<capability>/spec.md               # proposed behavior delta
.mary-workflow/                              # execution state and evidence
```

Use this flow by default for core code changes. Existing unbound states remain valid; do not silently convert their frozen plans. Paper and Notion retain independent state and authorization. Read source and relevant accepted specs before authoring a baseline; do not label aspirations as current behavior. Keep artifact length proportional to scope. A design document is useful for cross-cutting, migration, or material architectural decisions; it is not mandatory for every small change.

Proposal records motivation, changed capabilities and affected surfaces. Base specs use `## Purpose` and `## Requirements`. Each requirement uses `### Requirement: Name`, normative SHALL/MUST language, and one or more `#### Scenario: Name` sections with WHEN/THEN statements. Names must identify their scope unambiguously.

Delta specs use `## ADDED Requirements`, `## MODIFIED Requirements`, `## REMOVED Requirements`, or `## RENAMED Requirements`. Added/modified blocks contain complete requirements and scenarios; modification replaces the whole existing block. Removal includes `**Reason**` and `**Migration**`. A rename uses:

```markdown
## RENAMED Requirements
- FROM: `### Requirement: Old name`
- TO: `### Requirement: New name`
```

Capability directories may be nested; scenario references preserve the full capability path. Renaming and modifying the same requirement in one delta is not supported; split those operations into successive changes. An existing capability Purpose, if repeated in a delta, must match its accepted Purpose. New capabilities include a meaningful `## Purpose`. Do not change accepted specs during implementation to bypass the baseline. Pure refactors or documentation changes without behavior deltas can use a change-local `.openspec.yaml`:

```yaml
skip_specs: true
skip_reason: Documentation wording only; observable behavior is unchanged.
```

The reason is required and no delta may accompany this exception. The coordinator checks the claim against actual scope; a boolean cannot establish absence of behavioral changes.

## Single task definition and traceability

Each numbered checkbox maps to one milestone and is immediately followed by its machine-readable `mary-task` block. The checkbox supplies the title; do not duplicate a different title inside JSON. IDs identify execution milestones. Exact relative deliverables, acceptance commands, scope and dependencies follow the state/worker contracts.

````markdown
## 1. Export

- [ ] 1.1 Implement export and verify the CSV acceptance test

```mary-task
{
  "id": "milestone-1",
  "deliverables": ["src/export.py", "tests/test_export.py"],
  "acceptance": ["python -m unittest discover -s tests -p test_export.py"],
  "estimated_scope": 1,
  "gate": "auto",
  "covers": {
    "export::Export data::Successful export": ["check-1"]
  }
}
```
````

`write_scope` and `read_dependencies` are optional. Acceptance IDs correspond to command order (`check-1`, `check-2`, ...). Every added/modified scenario must map to at least one real command ID in a task; unknown references and unknown check IDs are errors. Removals use `capability::REMOVED::Requirement name`; renames use `capability::RENAMED::Old name`. Those operations need task/check mappings and review too. For a no-behavior-delta change use an empty `covers` object.

A mapping declares a review obligation. It does not prove command adequacy, semantic correctness, or successful execution. Keep source/render/external checks required by a scene; never represent an unavailable real experiment with a passing synthetic substitute.

## Bind, freeze and revise

1. Read the brief, relevant accepted specs and current implementation. Write the inspectable change artifacts within planning scope.
2. Run `mary_workflow.py sdd-check <change-id>`. This read-only command returns the source-derived milestones and structural coverage; it does not mutate state or authorize work.
3. Use `update_interview` for real clarifications and the returned exact draft. Apply `{"action":"bind_change","data":{"change_id":"<change-id>"}}` in PLANNING with a complete brief.
4. Freeze with `update_state` matching the source. `runtime_meta.sdd` binds the change files, accepted spec baseline and traceability into plan identity. Milestones are execution mappings, not independently authored task definitions.
5. Start/resume only on actual explicit authorization. `/mw-run` works as before; unambiguous natural language uses `source: user_instruction`, `intent: execute`, and the verbatim actual instruction in `confirmation`.

Checkboxes are runtime progress, excluded from the task definition digest. Only accepted milestones count as complete and synchronize the checkboxes. A manually checked task grants no acceptance. Workers cannot modify frozen planning artifacts; report necessary changes to the coordinator.

Changes to proposal, design, specs, task definition or accepted baseline invalidate the binding. From PLANNED use `reopen_plan`; from active phases use `request_replan` after workers quiesce. Recheck, bind and freeze the revised definition before execution. Preserve old evidence and plan history without treating them as proof for changed requirements. Reuse a user's existing authorization when it still applies; material scope/acceptance decisions require the actual applicable instruction.

## Review, archive and recovery

Provide reviewers complete relevant specifications plus implementation and command evidence. Each SDD verifier result includes `scenario_reviews`: a list of `{scenario, decision, evidence}`, with exact scenario/operation references, `passed|needs-fix`, and concrete nonempty evidence pointers. Every reference of the current milestone is reviewed; an overall pass requires all of them to pass. The coordinator still inspects evidence and performs acceptance through runtime actions.

At accepted FINISHED, `cycle` checks the frozen baseline before merging delta requirements into accepted specs and archiving the change. Recoverable SDD and cycle archive journals preserve planned writes, evidence-copy progress and archive state across interruption. The runtime also checks the accepted product fingerprint before merging: post-acceptance product edits require new evidence through `request_replan` from bound, not-yet-archived FINISHED. Conflict is an actionable failure, never permission to overwrite unrelated spec changes. Retry the same cycle operation after resolving the reported interruption/conflict; do not delete journal records to manufacture completion.

Specification archival precedes the incremental brief refresh. Once that merge
has completed, its acceptance describes the recorded product snapshot. Later
product edits are preserved, reported as `sdd_post_archive_changes`, and included
in the brief refresh before the next cycle; they do not inherit that acceptance.
This lets an interrupted refresh finish without pretending later edits passed
the archived tests. Before the merge, product drift requires `request_replan`
and fresh evidence. Explorers can report during replanning and archive refresh
even when the old active change binding no longer exists.

A stopped unfinished cycle may archive execution evidence after the existing quiescence and brief-refresh checks. It leaves the change unmerged and does not mark pending tasks complete. A fresh cycle can explicitly bind that remaining change. Only the coordinator performs control-state updates, archive integration and authorized Git writes.
