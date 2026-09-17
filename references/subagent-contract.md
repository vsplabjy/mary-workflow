# Worker dispatch and completion contract

This contract is independent of model names, providers, context-window sizes, and
reasoning settings. Every role inherits the active host configuration. Host
capabilities select execution mechanisms; they never select a model.

## Authority and roles

The coordinator owns user interaction, authorization interpretation, the frozen
plan, workflow transitions, integration, and the final acceptance decision.
Workers perform concrete work and return verifiable artifacts. The coordinator
does not redo an implementation merely to demonstrate supervision, but must
inspect actual changes and evidence before accepting it.

| Role | Phase | Product write access | Result |
| --- | --- | --- | --- |
| `explorer` | Legal research/diagnosis phases; stable phases during required brief refresh | None | Source-grounded module summary, coverage, diagnosis, or unresolved questions |
| `implementer` | EXECUTING | Exact assigned `write_scope` | Product changes and execution evidence |
| `verifier` | REVIEWING | None | Independent review, concrete findings, evidence references |

A repair is an implementer task for an enqueued repair milestone. DEBUGGING may
dispatch diagnosis; it cannot dispatch product edits. Product writes resume only
after the legal `enqueue_fix_task` transition to EXECUTING.

Workers never directly modify `.mary-workflow/`, including `state.yaml`, formal
reports, project brief, log, prompts, or task sidecars. They can put temporary
notes and outputs in their assigned `.mary-workflow-worker/<task_id>/` directory
outside that control tree. Read-only workers may return their notes inline if
their host disallows all filesystem writes. The coordinator persists formal
records through runtime actions.

Workers do not commit, push, reset, change the Git index, publish, send messages
to third parties, or perform other external writes. The coordinator performs
such actions only within existing user authorization. Workers can add or change
tests when explicitly in scope; weakening acceptance, deleting assertions to
hide failures, and inventing test results are forbidden.

Tool restrictions or a real sandbox should enforce read/write separation when
available. Removing Edit/Write while retaining arbitrary shell access does not
create a read-only sandbox. Runtime records and hashes detect ordinary mistakes
and stale evidence; an agent with unrestricted shell access could bypass or
rewrite them. Neither hashes nor claimed worker IDs prove hostile-agent safety.

## Dispatch preparation

1. Reconcile the current phase, run, milestone, plan revision, and user decisions.
   Reuse useful conversation context; filesystem state controls transitions.
2. Identify one bounded, independently useful task and its dependencies. Keep
   tightly coupled reasoning and final acceptance with the coordinator.
3. Allocate a native worker identity. A newly spawned worker must wait for the
   dispatch envelope before product work. Register its baseline before sending
   the actual assignment; do not snapshot after a worker has started editing.
4. Call `delegate_task`. Include the returned attempt/run/revision identifiers in
   the assignment, together with exact acceptance commands and relevant context.
5. Send source files, conventions, known failures, relevant user modifications,
   and necessary interface contracts. Do not flood the worker with an unrelated
   transcript or hide information required to do the work correctly.

`agent_id` is the actual host worker identity, maintained by the coordinator. A
role name or fabricated second identity is not evidence of a separate reviewer.
An idle independent worker can be reused. A reviewer cannot share an identity
with any implementer it reviews in delegated mode.

### Dispatch action

The coordinator submits JSON through the normal `apply-action --file` interface.
Use a temporary envelope file; preserve exact commands without shell interpolation.

```json
{
  "action": "delegate_task",
  "data": {
    "task_id": "implementation-1",
    "role": "implementer",
    "agent_id": "host-worker-identity",
    "objective": "Implement the behavior in milestone-1 and preserve its acceptance contract",
    "milestone_id": "milestone-1",
    "deliverables": ["src/a.py", "tests/test_a.py"],
    "write_scope": ["src/a.py", "tests/test_a.py"],
    "read_dependencies": ["src/interfaces.py"],
    "acceptance_ids": ["check-1"]
  }
}
```

The task response contains `task_id`, generated `attempt_id`, `run_id`,
`plan_revision`, `cycle`, `execution_mode`, a milestone contract digest, assigned
paths, exact acceptance commands, baseline digest, and scratch path. Task IDs are
unique for their lifetime. A retry uses a new ID and optional `retry_of`; old
records and logs remain available. No model or provider field is used.

Acceptance IDs are `check-1`, `check-2`, etc. in frozen milestone order. Assign a
subset for parallel work if useful; their union must cover every required check.
The worker cannot supply a replacement command. A milestone's `write_scope`
(falling back to its deliverables) bounds all worker writes. Exact relative file
paths are required: no absolute paths, traversal, globs, directories, control
paths, or symlink traversal. List shared read dependencies explicitly.

Scope changes require the coordinator to follow the legal planning/revision
path. Recording a deviation is not permission to proceed. A worker that needs
another path stops the affected work and reports the reason and proposed change.

## Parallel work and artifact baselines

Milestones remain serial. Parallelize only independent work inside the current
milestone, independent exploration, or review perspectives. The runtime rejects
overlapping writer scopes and writer/read-dependency conflicts among active
tasks. The coordinator also checks shared APIs, generated files, databases,
ports, caches, test fixtures, build outputs, and external resources: file
disjointness alone does not establish independence.

Use isolated workspaces when useful and supported; integrate their patches
within the assigned coordinator workspace before its final validation. This
runtime does not schedule host workers or merge worktrees itself.

Before dispatch, the runtime records working-tree contents and file modes, plus
Git index entries. Git workspaces include tracked and nonignored untracked files;
explicit contract paths are included even if ignored. Non-Git workspaces are
walked. Workflow controls, assigned scratch, and ordinary tool-cache directories
are excluded. Symlinks are not followed. These records distinguish pre-existing
user modifications from later additions, deletions, renames (delete/add pairs),
and staged changes. They are not attribution proof when unrelated actors edit
the same workspace simultaneously; ambiguous changes require resolution.

Ignored generated files are outside general coverage unless explicitly named in
the contract. Do not claim a complete audit of arbitrary filesystem writes.
Product dependencies that matter to correctness must be named even when ignored.

All sibling product writes must stabilize **before** final command execution and
result submission. Validation binds the complete covered product snapshot, not
only the worker's own files. A changed dependency, new file, staging operation, or
later integration invalidates old evidence. Independent worker outputs may be
combined, but a milestone cannot complete while a writer is running or while a
ready implementer has been omitted from its task list.

## Command execution evidence

Workers may run exploratory checks, but acceptance requires a coordinator-owned
execution record. The coordinator requests:

```json
{
  "action": "run_validation",
  "data": {
    "task_id": "implementation-1",
    "attempt_id": "attempt-id-from-dispatch",
    "acceptance_id": "check-1",
    "timeout_seconds": 300
  }
}
```

The helper executes the exact frozen command at the project root and records:

- acceptance/task/attempt/run/revision identity and timestamp;
- exact command, working directory, exit code, status, summary, and duration;
- separate raw stdout/stderr logs and their digests;
- covered product digests before and after execution.

Only execution produces `passed`. A failed command, timeout, cancellation,
missing log, changed log, substituted command, or stale product snapshot cannot
satisfy acceptance. A command that changes covered product files must be rerun
after those writes stabilize. Put intended temporary validation outputs in the
assigned scratch or an appropriately excluded build area. Do not add exclusion
rules merely to hide product changes.

Evidence is stored as append-only files in
`.mary-workflow/tasks/<task_id>/<evidence_id>.json` with sibling raw logs. A caller
cannot import an arbitrary `passed` status through this helper. These records
establish what the cooperating local runner observed; they are not cryptographic
attestation of a trustworthy host or semantic proof that the tests are adequate.

Long validation runs do not hold the workflow write lock. The helper checks stop,
cancellation, revision and run identity while executing, kills the local command
process group on cancellation/timeout, and preserves its partial logs. The
coordinator must apply ordinary host permissions before executing a command.

## Worker result envelope

The worker returns this envelope; the coordinator checks it and submits the
`submit_worker_result` action. `ready_for_review` means the worker's work is ready
for inspection, never that the milestone is accepted.

```json
{
  "action": "submit_worker_result",
  "data": {
    "task_id": "implementation-1",
    "attempt_id": "attempt-id-from-dispatch",
    "status": "ready_for_review",
    "summary": "Implemented the agreed behavior; required check completed",
    "files_changed": ["src/a.py", "tests/test_a.py"],
    "validation": ["evidence-id-from-run_validation"],
    "scope_deviations": [],
    "blockers": [],
    "uncertainties": []
  }
}
```

`files_changed` must match actual differences from the dispatch baseline.
Validation contains registered evidence IDs, not agent-authored status objects.
`scope_deviations` must be resolved before a ready result can be submitted.
`blocked` and `failed` require concrete blockers, attempted remedies, and the relevant error text or
minimal reproducer where available. Lack of a GPU, fixture, credential, tool, or
authorized action is recorded honestly. A required unrun check cannot become a
pass; optional investigations may be described as skipped with a reason in the
summary or uncertainty record.

Failed/blocked attempts preserve both reported and observed changed files,
reported and observed scope deviations, and concrete contract issues. Invalid
reported paths or evidence references are retained as diagnostic text without
following them. This allows the coordinator to retain the error scene before
`record_error` or `request_replan`; such an attempt can never satisfy acceptance.

A submitted result is immutable. If product content changes afterward, retain
the old attempt and create a new dispatch. Do not overwrite evidence, silently
edit a returned result, or repeatedly regenerate claims until their shape passes.

## Independent review and coordinator acceptance

After receiving all implementation results, the coordinator calls
`mark_task_done` with the current milestone ID and every participating task ID:

```json
{"action":"mark_task_done","data":{"id":"milestone-1","task_ids":["implementation-1"]}}
```

The runtime requires current bindings, matching actual paths, ready results,
intact raw logs and passing evidence for every exact required command before
entering REVIEWING. It does not accept the worker's process narration as proof.

In REVIEWING, dispatch `role: verifier`, empty `write_scope`, a distinct native
`agent_id`, and `reviews_task_ids: ["implementation-1"]`. Give the reviewer the
original goal, acceptance, actual changes, relevant source and validation logs.
Do not present the implementer's conclusion as the answer it is expected to
confirm. The reviewer checks substantive correctness, scope, test adequacy, and
unresolved concerns. It may reuse intact evidence; duplicating every successful
command is unnecessary unless a concern justifies it.

The verifier returns the standard result envelope with:

```json
{
  "files_changed": [],
  "validation": [],
  "decision": "passed",
  "findings": []
}
```

`needs-fix` requires concrete findings with relevant paths or evidence. The
coordinator resolves them using the phase/action whitelist; reviewers cannot
rewrite the task list or fix product code while reviewing. A passed review must
refer to the same product snapshot and implementer tasks. The coordinator then
uses `set_phase` with `verifier_task_id`, the appropriate next phase, and the
accepted decision. Execution and review evidence are retained separately.

Only the coordinator decides that the user's requirement is satisfied. It must
check actual changes, coverage of required validation, the independent findings,
scope deviations and remaining uncertainties before applying the action.

## Failure, stop and recovery

- An incomplete but recoverable worker may resume with its context while its
  dispatch remains current. Retry transient tool errors within a bounded budget.
- A failed path requires preserved diagnosis and an appropriate repair task.
  Avoid infinite retries, silent fallback to a different model, and weaker tests.
- New task IDs identify retried attempts; retain `retry_of` for traceability.
- On `/mw-stop`, stop new dispatches, mark running task records cancelled, interrupt
  native host workers, settle their writes, and only then report a stable pause.
  Cancelling a record alone does not terminate a remote/native worker.
- Preserve ready results already submitted before the stop. On resume they may
  be reused only if their run, revision and product snapshot still match. Rework
  and replanning invalidate these ready records too; a pause is not a replan.
- Results from cancelled attempts, previous runs, previous revisions, other
  milestones, or changed milestone contracts cannot advance workflow state.
- On crash or timeout, inspect actual residual changes before continuing. Never
  discard an entire workspace or reset user changes to clean up a worker.
- A crashed validation coordinator may leave `active_validation` after its local
  process exits. Use `recover_validation` with the task and attempt identifiers:

  ```json
  {"action":"recover_validation","data":{"task_id":"implementation-1","attempt_id":"attempt-id-from-dispatch","reason":"Coordinator exited before persisting completion"}}
  ```

  This administrative action can run while paused; it grants no execution
  permission. Recovery requires the recorded coordinator PID, validation PID and
  isolated POSIX process group to be absent. A live or reused identity, denied
  process inspection, unsupported platform, or insufficient legacy receipt is
  refused conservatively. The helper never kills an unknown process or guesses
  that a missing coordinator means validation passed. Let the process owner stop
  or reap live processes, then retry inspection.

  Original stdout/stderr and any finished evidence remain intact. A separate
  immutable recovery record stores `result: interrupted`, unknown exit code and
  duration, observed log hashes and process-absence evidence. The task becomes
  failed or cancelled, its active receipt is cleared, and further implementation
  or validation requires a new attempt. Missing logs are recorded explicitly.
- On resume, reconcile the stopped state and actual files, obtain the legal
  resume transition, then dispatch new attempts as needed. Preserve useful
  context and original scope; do not repeat completed external side effects.

## Capability fallback and other scenarios

Delegation is the normal mode when the host supports workers. Independent
workers are an execution mechanism, not a requirement to fabricate for tiny or
tightly coupled work. If workers are unavailable, the coordinator explicitly
starts in `execution_mode: single_agent`, uses separate implementation and review
passes, and the verifier envelope must contain `review_mode: same_agent`.
The resulting record reports `independent_review: false`. This fallback never
pretends that a renamed identity is an independent reviewer.

Paper, course, experiment, document and external-application work can reuse these
role boundaries, dispatch shape, evidence discipline and recovery rules. Their
own lifecycle and domain checks remain authoritative: a paper source locator,
rendered slide inspection or external read-back is not replaced by an unrelated
shell check. The milestone helper API persists milestone workers only; do not
create a dummy milestone to force an independent paper or application lifecycle
into it. Use the scene's existing runtime to store its domain evidence.

## Runtime integration

`scripts/mw_workers.py` uses the Python standard library and exposes:

```python
create_task(root, state, data) -> dict
run_validation(root, state, data) -> dict
record_validation(root, state, data) -> dict  # alias: executes, never imports claims
recover_validation(root, state, data) -> dict  # diagnostic only, never a pass
submit_result(root, state, data) -> dict
verify_milestone_evidence(root, state, milestone, data) -> dict
verify_review_evidence(root, state, milestone, data) -> dict
accept_tasks(root, state, task_ids) -> None
list_tasks(root) -> list[dict]
cancel_tasks(root, reason="stopped", *, include_ready=True) -> list[str]
validate_relative_path(value) -> str
```

`root` is the project's `.mary-workflow/`. The coordinator serializes task and
state mutations with the workflow lock. `run_validation` manages its own short
initial/final locks and must not be wrapped in an outer lock around the command.
Accept records only after all transition checks, while the old current milestone
and run binding still exist. Close records and persist the state in the same
coordinator critical section. `WorkerError` provides actionable contract errors.
