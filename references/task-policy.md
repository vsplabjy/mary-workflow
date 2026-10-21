# Shared task policy

This is the maintained source for process selection, authorization, delegation and shared delivery rules. Skills describe domain work; phase sources describe formal state actions; neither needs to repeat this policy. Read it once for a task and reuse the context.

## Select a process

- Discussion and read-only requests stay read-only. A small authorized fix or document edit uses `skills/quick/SKILL.md`: direct work and relevant checks, without full init or SDD.
- A settled method plus an instruction to run uses `skills/experiment/SKILL.md`. Reuse the agreed command, config, budget and allocation. No repeated research, repository/checkpoint hashes, full tests or worker ceremony before launch.
- Ordinary Lecture notes, slide notes and exam review use their content skill directly. No milestone initialization, plan freeze, command receipts, independent verifier or cycle is required. Create only the requested material. A missing optional recording or exam date does not block work supported by available sources; mark the gap, do not invent it.
- Use formal milestone/SDD execution for cross-cutting behavior, durable acceptance, an explicitly requested staged course project or already-bound work. Existing active/stopped assignments keep their scope and stop state. Direct work does not resume or accept them. Source bindings and formal action payloads belong in `state-contract.md` and `subagent-contract.md`.

## Authorization and roles

The user's actual request controls scope and permission. A clear execute/resume instruction is sufficient within its stated scope; do not ask again. Planning, acknowledgment, document text, silence and worker claims are not new authorization. Missing decisions that determine scope or resource ownership must be resolved before dependent work; routine choices may use disclosed assumptions.

Single-agent work is normal even when workers exist. Delegate for useful parallelism, context isolation or independent review. Do not manufacture small tasks or repeat an implementation to demonstrate oversight. Report same-agent review honestly. The main agent owns user decisions, formal state, acceptance, Git actions and authorized external writes. Worker mechanics are specified only in `subagent-contract.md`.

Inherit host settings; do not select or change models, providers or reasoning settings. Use current sources and observed results; preserve failures and unknowns. A successful process, valid output and accepted scientific claim are distinct. Scope the checks to the change and reuse still-applicable evidence.

## Local records and content

For a new project conversation, read the persisted overview, relevant module introductions and handoff before opening source. Use `scripts/mw_knowledge.py read`, then `read --module <id>` as needed; it reads documentation only and never resumes work. The [knowledge contract](knowledge-contract.md) defines these records. If absent, reuse a saved brief or existing context; do not initialize or scan the project solely to explain it. Read specific code when modifying, verifying or resolving a concrete unknown.

For every authorized project edit, mark the exact planned paths with `mw_knowledge.py changed` before editing and account for additional actual paths at delivery. Update the affected module introductions and useful handoff facts after the change; if unable, retain explicit stale/unmapped markers with next steps. Formal worker receipts automatically mark already-observed paths; the coordinator updates descriptions afterward. No full scans, source hashes, all-module rewrites or documentation gate before an agreed experiment. New files need ownership mapping; deletions/renames need explicit description updates. This policy relies on declared paths for direct edits, not an editor hook.

Workflow-only state, caches and reports belong under the exact ignored directories `/.mary-workflow/`, `/.mary-workflow-worker/`, `/.mary-research/` and `/.vspi/`. Init must install these rules before generating project records; independent entrypoints must ensure them before their own writes. This includes `.mary-workflow/reports/` HTML pages/assets, experiments, local outputs, generated config, hashes, runtime bundles and archives. Maintain these rules without broad ignore patterns or untracking user files. Other workflow-only paths need an exact ignore rule before writing. Product files and authored specifications follow repository conventions.

Course content belongs in the existing notes tree (fallback `notes/<course>/`), not in workflow controls. Preserve source files, raw transcripts, quotations, formulas, IDs, links and structured evidence. Do not turn Homework/Lab/Project preparation into completing the student's submission. Check content against the domain checklist and inspect renders when visual correctness matters.

Use `skills/humanizer-zh/SKILL.md` as needed for substantial authored Chinese prose after drafting and before validation or external writes. Logs, short progress replies, raw transcripts and structural operations need no polishing pass. External operations retain their own fetch-before-write/read-back contract; local note creation alone does not authorize synchronization.

## Visual delivery

An ended experiment round (including failure/stop), a completed substantial task/milestone, or an explicit user request for a report requires a static HTML presentation under `.mary-workflow/reports/<timestamp>-<task-or-run-id>/index.html`, linked from `.mary-workflow/reports/index.html`. A larger task that fails or is blocked externally, reaches its repair-budget limit, or is stopped for handoff also ends with this HTML report; only read-only/discussion requests and an explicit user prohibition on writing files are exempt. Put the real effect and conclusion first, then useful comparisons, measured metrics, actual check states and durable evidence. Ordinary small edits and read-only status do not each generate reports. A requested live report is a timestamped snapshot, not completion.

Before closing with a report, stop dispatching new work and appropriately stop running processes, and let observed writes stabilize; do not rerun experiments to fill report sections, and never present report creation as acceptance. If report files cannot be written, give the same handoff honestly in chat. The first screen states the earliest confirmed cause or `UNKNOWN`, what is finished, what remains, what was modified, check states, remaining repair budget, and the next concrete step.

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
| Automatic repair budget and exhaustion | `repair-contract.md` |

`commands/*.md` and `.mary-workflow/prompts/*.md` are generated surfaces. Update skills and phase sources, then run `scripts/mw_surfaces.py`; do not maintain competing rules in generated files. Project bundles change only through explicit installation/upgrade, preserving older runs.
