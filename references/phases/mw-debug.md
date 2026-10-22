# Mary Debug Phase

Verify an active run in `DEBUGGING`; read the preserved `last_error`, affected artifact version, task attempts, and relevant source. Diagnose the actual failure. An explorer can investigate read-only when useful, but DEBUGGING does not permit product edits or a fixer implementation.

Diagnosis dispatch and result collection use the shared worker actions; its normal state transition is `enqueue_fix_task`. If evidence requires a different authorized scope, use `request_replan` with concrete feedback. Use the current state contract, link the fix to failed work, and keep its scope and acceptance within existing authorization. Missing tools, credentials, data, or user decisions are specific blockers; distinguish them from defects that a repair can resolve. Do not retry an unchanged blocker indefinitely.

```json
{
  "action":"enqueue_fix_task",
  "data":{
    "title":"Repair the recorded failure",
    "source_error":"<actual error summary>",
    "deliverables":["relative/path.ext"],
    "acceptance":["<unchanged applicable acceptance command>"],
    "estimated_scope":1
  }
}
```

Apply with `mary_workflow.py apply-action`. The runtime returns to `EXECUTING` before any repair is implemented. Preserve the original error and previous attempts. If a larger scope or lower acceptance threshold is needed, use `request_replan` with concrete feedback and existing user authorization rather than silently rewriting the frozen plan.
