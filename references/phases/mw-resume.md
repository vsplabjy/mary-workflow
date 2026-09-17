# Mary Resume Phase

Verify a stopped active phase and the preserved run, plan revision/digest, tasks, and residual changes. Inspect unfinished worker attempts and reconcile product changes with their baselines. Do not reset unrelated user work or silently accept a worker's late result.

An explicit `/mw-run` is the resume instruction. Apply:

```json
{
  "action": "resume_execution",
  "data": {
    "plan_digest": "<current frozen plan digest>",
    "confirmation": "<actual user instruction to resume>",
    "source": "/mw-run"
  }
}
```

Preserve phase and run identity. Re-render `/mw-run`, revalidate changed dependencies, and resume applicable pending work. Plan changes require the legal revision path rather than reuse of stale authorization. Do not select a model, alter host settings, or re-run already completed external effects merely because context was compressed.
