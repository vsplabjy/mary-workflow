# Mary Resume Phase

Verify a stopped active phase and the preserved run, plan revision/digest, tasks, and residual changes. Inspect unfinished worker attempts and reconcile product changes with their baselines. Do not reset unrelated user work or silently accept a worker's late result.

An explicit `/mw-run` or an unambiguous user instruction to resume authorizes resumption. For `/mw-run`, apply:

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

For a natural-language resume use `source: user_instruction`, `intent: execute`, and the verbatim instruction. A bound SDD change must still match its frozen artifact and base-spec hashes. Drift requires a legal replan after residual workers settle; never silently rebind during resume or reuse previous scenario verdicts for revised requirements.
