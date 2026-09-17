---
name: stop
description: Coordinate an orderly Mary Workflow pause while preserving state, worker evidence, and recovery information. Use for /mw-stop.
---

# Mary Workflow: Stop

The user's stop request takes effect immediately: dispatch no new work and accept no additional worker result. Notify or interrupt active workers using available host tools. Inspect their residual changes against the recorded baselines; never reset unrelated user work.

Run `python ~/.codex/skills/mary-workflow/scripts/mary_workflow.py stop` to persist stopped status and invalidate active work for acceptance. Wait for worker writes to stabilize and record unresolved processes or partial artifacts; if the host cannot confirm a worker stopped, report that limitation explicitly. A late worker result must not advance the stopped run.

Report the preserved phase, milestone, run identity, unfinished work, and recovery needs. A later explicit `/mw-run` resumes the preserved lifecycle with the current plan digest. Stop does not delete state, reports, logs, or paper artifacts.
