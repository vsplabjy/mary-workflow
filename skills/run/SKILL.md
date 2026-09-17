---
name: run
description: Run or resume Mary Workflow by coordinating workers, recorded validation, and independent review. Use for /mw-run.
---

# Mary Workflow: Run

Run `python ~/.codex/skills/mary-workflow/scripts/mw_codex.py mw-run` from the project root. Use its pinned phase together with [subagent contract](../../references/subagent-contract.md), [state contract](../../references/state-contract.md), and [host contract](../../references/host-contract.md).

- `PLANNED`: inspect the frozen plan and evidence. Explicit `/mw-run` is its start signal; apply `start_execution` with the displayed plan digest and actual user confirmation, without another ritual approval. If the user disputes the plan, return to planning.
- Stopped active phase: reconcile residual worker changes, then `resume_execution` with the current digest and actual resume instruction. Preserve phase, run identity, and pending work.
- `EXECUTING`: dispatch bounded work with `delegate_task`, capture actual acceptance with `run_validation`, and record `submit_worker_result`. Check task identity, baseline changes, scope, artifacts, and required evidence before `mark_task_done` with the accepted task IDs. The main agent coordinates; workers implement. Do not redo the worker's entire task simply to claim oversight.
- `REVIEWING`: use a separate verifier with the original requirements and actual artifacts. Submit its evidence; only the main agent accepts with `set_phase`. Preserve execution and review records separately. Failed validation goes through `record_error`.
- `DEBUGGING`: diagnose and `enqueue_fix_task`; product repair runs only after returning to `EXECUTING`.
- `PLANNING`: complete the planning contract before execution.

Milestones are sequential. Parallelize independent tasks within the current milestone or initialization only after checking shared files, interfaces, resources, generated outputs, and dependencies. Use isolation when appropriate. A stopped, outdated, or duplicate worker result cannot advance the plan.

At a `gate: confirm`, use an already applicable explicit confirmation or obtain the required user decision, then record `confirm_milestone` before dispatch. Keep task progress visible. Continue until finished, stopped, materially blocked, or awaiting a genuinely required user answer. On stop, cancel/intercept workers and wait for writes to stabilize before finalizing pause. Never delegate workflow state, authorization decisions, Git writes, or external mutations.

If workers are unavailable, follow the explicit compatibility route in the contracts: start with `execution_mode: single_agent`, perform a separate review pass, and submit its `review_mode: same_agent`. Report the lack of independent-agent review; never pretend a second agent ran. In every route, inherit host configuration without selecting a model or reasoning level.
