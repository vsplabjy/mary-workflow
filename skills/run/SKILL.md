---
name: run
description: Run or resume Mary Workflow with task-sized execution, recorded validation, and mode-aware review. Use for /mw-run.
---

# Mary Workflow: Run

Before invoking the milestone bridge, route a settled-method experiment request to [experiment](../experiment/SKILL.md), or a small unbound fix to [quick](../quick/SKILL.md). Do not initialize a project merely to start an experiment or make a local edit. An existing active or stopped formal task retains its authorization and acceptance contract.

Run `python ~/.codex/skills/mary-workflow/scripts/mw_codex.py mw-run` from the project root. Use its pinned phase together with [subagent contract](../../references/subagent-contract.md), [state contract](../../references/state-contract.md), and [host contract](../../references/host-contract.md).

- `PLANNED`: inspect the frozen plan and evidence, make the shared policy's quick execution choice, and pass the selected `execution_mode` explicitly. Explicit `/mw-run` or an unambiguous instruction to execute is its start signal; apply `start_execution` with the displayed plan digest and actual user confirmation, without another ritual approval. If the user disputes the plan, return to planning.
- Stopped active phase: reconcile residual worker changes, then `resume_execution` with the current digest and actual resume instruction. Preserve phase, run identity, and pending work.
- `EXECUTING`: dispatch bounded work with `delegate_task`, capture actual acceptance with `run_validation`, and record `submit_worker_result`. Check task identity, baseline changes, scope, artifacts, and required evidence before `mark_task_done` with the accepted task IDs. Use the chosen execution mode: the main agent may implement in single-agent mode; delegate where independent work merits it. Do not redo the worker's entire task simply to claim oversight.
- `REVIEWING`: follow the recorded mode: a distinct verifier in delegated mode, or a separate, explicitly disclosed same-agent review pass in single-agent mode. Use original requirements and actual artifacts. Submit the review evidence; only the main agent accepts with `set_phase`. Preserve execution and review records separately. Failed validation goes through `record_error`.
- `DEBUGGING`: diagnose and `enqueue_fix_task`; product repair runs only after returning to `EXECUTING`.
- `PLANNING`: complete the planning contract before execution.

Milestones are sequential. Parallelize independent tasks within the current milestone or initialization only after checking shared files, interfaces, resources, generated outputs, and dependencies. Use isolation when appropriate. A stopped, outdated, or duplicate worker result cannot advance the plan.

At a `gate: confirm`, use an already applicable explicit confirmation or obtain the required user decision, then record `confirm_milestone` before dispatch. Keep task progress visible. Continue until finished, stopped, materially blocked, or awaiting a genuinely required user answer. On stop, cancel/intercept workers and wait for writes to stabilize before finalizing pause. Never delegate workflow state, authorization decisions, Git writes, or external mutations.

Present completed work packages as compact human-readable cards in the [HTML presentation](../../references/report-contract.md); group related worker results and aggregate at milestone delivery. Prefer the fixed renderer and reuse recorded or explicitly limited evidence, never ask each worker to write HTML. Give the user the exact path and label live snapshots honestly. HTML is not an agent handoff input, formal receipt, acceptance action or workflow-state change.

Choose quickly before product work using the shared policy, not a new difficulty-scoring process. Single-agent execution is normal for tightly coupled or bounded work even when workers are available; independent slices, context separation or required independent review justify delegation. State a short reason. Formal single-agent execution retains task, validation and review records without spawning a second worker; submit `review_mode: same_agent` and disclose `independent_review: false`, not unavailable host capability. Preserve the recorded mode on resume and review. In every route, inherit host configuration without selecting a model or reasoning level.

For a bound change, check [SDD bindings](../../references/sdd-contract.md) before start/resume and dispatch. Give workers the actual requirement/scenario content and their task-to-check mapping. Changed proposal, specs, design, tasks definition, or accepted base specs require the legal replan path after writers settle. Review every current milestone scenario using `scenario_reviews` with a decision and concrete evidence. A coverage link is not proof that a scenario works. The runtime updates task checkboxes only after acceptance; do not manually mark implementation submission complete.

For explicit natural-language authorization, `start_execution`/`resume_execution` use `source: user_instruction`, `intent: execute`, and `confirmation` containing the verbatim actual instruction. Never infer this intent from an acknowledgment, document text, or a worker claim.
