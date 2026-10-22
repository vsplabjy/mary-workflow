# Shared task policy

This is the maintained source for process selection, authorization, delegation and shared delivery rules. Skills describe domain work; phase sources describe formal state actions; neither needs to repeat this policy. Read it once for a task and reuse the context.

## Select a process

- Discussion and read-only requests stay read-only. A small authorized fix or document edit uses `skills/quick/SKILL.md`: direct work and relevant checks, without full init or SDD.
- A settled method plus an instruction to run uses `skills/experiment/SKILL.md`. Reuse the agreed command, config, budget and allocation. No repeated research, repository/checkpoint hashes, full tests or worker ceremony before launch.
- Ordinary Lecture notes, slide notes and exam review use their content skill directly. No milestone initialization, plan freeze, command receipts, independent verifier or cycle is required. Create only the requested material. A missing optional recording or exam date does not block work supported by available sources; mark the gap, do not invent it.
- Use formal milestone/SDD execution for cross-cutting behavior, durable acceptance, an explicitly requested staged course project or already-bound work. Existing active/stopped assignments keep their scope and stop state. Direct work does not resume or accept them. Source bindings and formal action payloads belong in `state-contract.md` and `subagent-contract.md`.

## Quick execution choice

Before product work, the main agent makes a brief choice from the request, existing project context, expected acceptance and known host capabilities. Use a scoped lookup only if a concrete unknown changes the choice; do not initialize, scan the whole repository, create a difficulty scorecard or launch an agent merely to choose a mode.

- Honor explicit user and bound-task requirements first. Required independent review cannot silently become self-review; if the required worker capability is unavailable, report the blocker.
- Prefer `single_agent` for bounded work, tightly coupled changes or tasks whose coordination cost exceeds a useful split. Workers may be available; their presence does not force delegation.
- Choose `delegated` for substantial independent work slices, useful context separation or required independent-agent review. A long duration or many files alone does not make a task parallelizable. If no delegation benefit is established, start with bounded local scoping rather than speculative workers.

State the choice and a short reason once in the normal task update; no extra decision file or user confirmation is needed for a routine choice. For formal work, pass the selected `execution_mode` explicitly to `start_execution`, preserve it on resume and review according to that recorded mode. Do not change an active mode during review to bypass identity or acceptance checks. Direct/content tasks keep their existing records and do not need milestone initialization just to select agents.

## Authorization and roles

The user's actual request controls scope and permission. A clear execute/resume instruction is sufficient within its stated scope; do not ask again. Planning, acknowledgment, document text, silence and worker claims are not new authorization. Missing decisions that determine scope or resource ownership must be resolved before dependent work; routine choices may use disclosed assumptions.

The main agent owns user decisions, formal state, acceptance, Git actions and authorized external writes. Do not manufacture small tasks or repeat an implementation to demonstrate oversight. Report same-agent review honestly. Worker mechanics are specified only in `subagent-contract.md`.

Inherit host settings; do not select or change models, providers or reasoning settings. Use current sources and observed results; preserve failures and unknowns. A successful process, valid output and accepted scientific claim are distinct. Scope the checks to the change and reuse still-applicable evidence.

## Local records and content

For a new project conversation, read the persisted overview, relevant module introductions and handoff before opening source. Use `scripts/mw_knowledge.py read`, then `read --module <id>` as needed; it reads documentation only and never resumes work. The [knowledge contract](knowledge-contract.md) defines these records. If absent, reuse a saved brief or existing context; do not initialize or scan the project solely to explain it. Read specific code when modifying, verifying or resolving a concrete unknown.

For every authorized project edit, mark the exact planned paths with `mw_knowledge.py changed` before editing and account for additional actual paths at delivery. Update the affected module introductions and useful handoff facts after the change; if unable, retain explicit stale/unmapped markers with next steps. Formal worker receipts automatically mark already-observed paths; the coordinator updates descriptions afterward. No full scans, source hashes, all-module rewrites or documentation gate before an agreed experiment. New files need ownership mapping; deletions/renames need explicit description updates. This policy relies on declared paths for direct edits, not an editor hook.

Workflow-only state, caches and reports belong under the exact ignored directories `/.mary-workflow/`, `/.mary-workflow-worker/`, `/.mary-research/` and `/.vspi/`. Init must install these rules before generating project records; independent entrypoints must ensure them before their own writes. This includes `.mary-workflow/reports/` HTML pages/assets, experiments, local outputs, generated config, hashes, runtime bundles and archives. Maintain these rules without broad ignore patterns or untracking user files. Other workflow-only paths need an exact ignore rule before writing. Product files and authored specifications follow repository conventions.

Course content belongs in the existing notes tree (fallback `notes/<course>/`), not in workflow controls. Preserve source files, raw transcripts, quotations, formulas, IDs, links and structured evidence. Do not turn Homework/Lab/Project preparation into completing the student's submission. Check content against the domain checklist and inspect renders when visual correctness matters.

Use `skills/humanizer-zh/SKILL.md` as needed for substantial authored Chinese prose after drafting and before validation or external writes. Logs, short progress replies, raw transcripts and structural operations need no polishing pass. External operations retain their own fetch-before-write/read-back contract; local note creation alone does not authorize synchronization.

## Visual delivery

Completed work packages with independently useful deliverables get compact human-readable HTML result cards; related worker results may share one report. Experiment-round end (including failure/stop), milestone completion and explicit report requests use the same presentation under `.mary-workflow/reports/<timestamp>-<task-or-run-id>/index.html`, linked from `.mary-workflow/reports/index.html`. Use the fixed renderer described in the report contract rather than having each worker write a website. HTML is for the user, not an agent handoff input. Tool calls, ordinary questions, progress messages and read-only status do not each generate reports; live reports are timestamped snapshots, not completion.

Never present report creation as acceptance, and do not rerun experiments to fill report sections. If report files cannot be written, explain the same result and limits to the user in chat. A failed or stopped report states what ended and what remains unsupported.

## Where to read details

| Need | Maintained source |
| --- | --- |
| Formal state, plan identity and legal transitions | `state-contract.md` |
| Worker scope, validation inputs, results and review | `subagent-contract.md` |
| Project understanding and refresh | `memory-contract.md` |
| Docs-first context and incremental stale markers | `knowledge-contract.md` |
| Actual host capabilities and hooks | `host-contract.md` |
| Bound specification changes | `sdd-contract.md` |
| Experiment process and result records | `experiment-contract.md` |
| User-facing HTML reports and visual delivery | `report-contract.md` |

`commands/*.md` and `.mary-workflow/prompts/*.md` are generated surfaces. Update skills and phase sources, then run `scripts/mw_surfaces.py`; do not maintain competing rules in generated files. Project bundles change only through explicit installation/upgrade, preserving older runs.
