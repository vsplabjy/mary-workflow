---
name: stop
description: Coordinate an orderly Mary Workflow pause while preserving state, worker evidence, and recovery information. Use for /mw-stop.
---

# Mary Workflow: Stop

For an experiment stop request, resolve the actual run ID and call `scripts/mw_experiment.py stop <run-id>` immediately. Do not initialize or stop an unrelated milestone workflow. Preserve USER_STOP and logs; report unresolved remote/native jobs using their actual scheduler. If the user means all running work, enumerate and stop the authorized active experiment runs as well as the formal workflow.

The user's stop request takes effect immediately: dispatch no new work and accept no additional worker result. Notify or interrupt active workers using available host tools. Inspect their residual changes against the recorded baselines; never reset unrelated user work.

Run `python ~/.codex/skills/mary-workflow/scripts/mary_workflow.py stop` to persist stopped status and invalidate active work for acceptance. Wait for worker writes to stabilize and record unresolved processes or partial artifacts; if the host cannot confirm a worker stopped, report that limitation explicitly. A late worker result must not advance the stopped run.

Report the preserved phase, milestone, run identity, unfinished work, and recovery needs. For a larger task or run, also deliver the stop-handoff HTML report required by the [report contract](../../references/report-contract.md): first screen with the earliest confirmed cause or `UNKNOWN`, finished vs unfinished work, actual changes, check states, remaining repair budget and the next step. Generate it only after dispatch stopped and writes stabilized; if report files cannot be written, give the same handoff honestly in chat. A later explicit `/mw-run` resumes the preserved lifecycle with the current plan digest. Stop does not delete state, reports, logs, or paper artifacts.
