# HTML presentation reports

This is the maintained contract for human-facing visual reports. HTML is a reading surface for the user, not an agent handoff prerequisite. Existing task results, experiment records and validation receipts remain authoritative; reporting never replaces coordination records or domain acceptance.

## When a report is required

Create an HTML report when any of these conditions applies:

- An experiment round ends: completed, failed or stopped. A round is the agreed run or comparison batch, not every training step or seed in a still-running batch. Preserve failures and partial results.
- A work package finishes with an independently useful deliverable: give the user a compact result card in HTML. Related worker results may share one delivery/report; do not create a site or a screenshot for every worker or tool call. Milestones use an aggregate report. Ordinary questions, progress messages and read-only status do not each need a report.
- The user explicitly requests a report, including while work is still running. Record the snapshot time, live status and unfinished work; do not imply completion.

Discussion-only and read-only requests remain read-only unless the user explicitly asks to create a report file; the only other exemption is an explicit user prohibition on writing files. A read-only status command does not create reports. For detached experiments, report at the next authorized completion observation/delivery; do not block launch, invent a watcher, or claim the supervisor authors a report after the chat ends. Do not mark a live run finished to trigger reporting. Reuse available evidence; never rerun experiments, access held-out inputs or consume additional GPU resources merely to populate a page.

The report itself is not acceptance: creating it never changes phase, run status, assessment or scientific claims, and it never substitutes for formal execution/review receipts. Workers do not need to read HTML to continue. If report files cannot be written (read-only host, explicit user prohibition, unavailable filesystem), give the user the same result and limitations in chat instead of promising a nonexistent file.

## Location and retention

Use this project-local layout:

```text
.mary-workflow/reports/
  index.html
  <YYYYMMDDTHHMMSSZ>-<task-or-run-id>/
    index.html
    assets/
```

Use the actual UTC creation time and a safe task/run identifier; if a name already exists, choose a new suffix rather than overwrite it. The top-level index lists reports newest first with title, time, observed status and a relative link. Each report package MUST contain its own regular `index.html`; place presentation assets inside the package. Do not use cycle IDs such as `C0` as presentation folder names: `reports/<cycle-id>/` is reserved for formal receipts. Finalized packages remain unchanged; a revised result gets a new package. The aggregate index may be updated without replacing historical entries.

If an existing aggregate index cannot be read, report generation MUST fail without replacing its bytes or dropping historical entries. An unreadable index is not an absent index. Artifact paths containing symbolic-link loops are unsafe evidence: omit them with a visible warning rather than aborting the entire report, including on Python 3.12.

Init MUST install the exact project-root ignores `/.mary-workflow/`, `/.mary-workflow-worker/`, `/.mary-research/` and `/.vspi/` before generating project records. The first rule includes reports, preview assets, experiments, local outputs, configuration, hashes, pinned runtime and cycle archives at every depth. Independent report creation without init MUST also ensure these rules before writing. Use the existing `mw_runtime.ensure_workflow_gitignore` helper, not a second ignore implementation. Any workflow-only directory outside those roots needs its exact ignore rule before creation. Never broadly ignore product `reports/`, `outputs/`, `docs/` or authored `openspec/` specifications. Preserve existing tracked files and user rules; do not untrack or delete user files automatically.

Cycle archival preserves the aggregate HTML index and presentation packages at their original locations, including assets, while formal cycle receipts retain their existing archive lifecycle. Keep the displayed summary, metrics and essential previews inside the package so clearing active analysis does not destroy the report. Links to detailed evidence must use its durable location; if an evidence path moves during archival, update the aggregate navigation or add a new report with the archive locator instead of silently leaving a broken evidence link. Reports are local/ignored by default, not automatically committed, published or synchronized.

## Content: visible result first

Default to Chinese unless the user requests another language. Preserve identifiers, paths, numbers and units. Adapt sections to the task; omit irrelevant empty sections rather than fill placeholders.

1. **First screen:** task/experiment title, snapshot time, a concise conclusion, actual state and the most informative result. Prefer the real image, screenshot, rendered view or playable clip over implementation prose.
2. **Effect and comparison:** show before/after or baseline/candidate evidence with clear labels when available. Use the same view/frame/scale where comparison requires it. Label selected samples as selected samples; do not imply exhaustive quality. If no visual artifact exists, show useful actual command output, metrics or deliverable structure, not a fabricated visualization.
3. **Metrics:** include units, sample/split, baseline when available, workload and timing denominator. Distinguish measured values from estimates. Do not invent a baseline or infer performance from parameter counts.
4. **Verification and limits:** mark each check as `通过`, `失败`, `运行中` or `未运行`, with an evidence locator and a reason for missing checks. Keep process exit, engineering validation, visual quality and scientific acceptance separate. Surface failures, missing inputs, UNKNOWNs and partial coverage.
5. **Evidence and reproduction:** actual run/task ID, relevant configuration/overrides, executable command, logs and artifact paths. Preserve existing authoritative records; the report is a readable projection, not a new source of workflow state. Redact secrets from displayed command/config excerpts.
6. **Remaining work:** concrete unresolved issues and next actions when applicable. A failed/stopped report must state what ended and what remains unsupported.

## Fixed rendering, not another workflow

Use `scripts/mw_report.py` when available in the installed skill or pinned bundle. Give it a short presentation description referencing existing results/evidence; do not ask each worker to write HTML/CSS, screenshots or a global index. No new worker envelope, task state, knowledge record or agent is required. A single task needs only a title and summary; add evidence and actual results when available.

```bash
python /path/to/mary-workflow/scripts/mw_report.py \
  --project . --input .mary-workflow/analysis/report.json --name task-result
```

```json
{
  "title": "任务结果",
  "summary": "先写给人看的结论，不把未知写成成功",
  "tasks": [".mary-workflow/tasks/implementation-1/result.json"],
  "verification": ".mary-workflow/analysis/verification.json",
  "metrics": [{"name": "实际度量", "value": 1, "unit": "声明实际单位"}],
  "artifacts": ["outputs/selected-preview.png"],
  "next_steps": ["列出仍需处理的事项"]
}
```

The example is a format illustration, not executed evidence. All referenced paths are project-relative. `tasks` also accepts existing result dictionaries (`summary`, `files_changed`, `validation`, `blockers`, `uncertainties`); omit irrelevant fields. `verification` may reference a `run_validation` receipt or an existing `{"checks":[...]}` record with the actual `command`/`argv`, integer `exit_code`, and `stdout`/`stderr` log paths. Logs are relative to that record. A status string alone is not proof; missing, contradictory or altered evidence stays visible. Rendered check states describe recorded command results, not a fresh product audit or scientific acceptance. The local cooperating writer is still part of the trust boundary.

A record identifying a command and an explicit failure, timeout, cancellation or interruption remains `失败` even when its exit code is unknown. Explain an interrupted validation as incomplete with an unknown exit code, not as an unexecuted check or proof that the product failed. Preserve readable, size-bounded logs whose supplied digests match; identify missing or altered streams without hiding the other available stream. Unknown or malformed exit codes never establish `通过`.

A card without its own attached receipt does not mean its commands were never executed; global command records remain separate and are not automatically attributed to every card. Long titles, summaries and hashes must wrap on narrow screens, including in the aggregate index.

The renderer reuses exact ignore rules, creates a new immutable report package, snapshots small selected evidence, and preserves the aggregate index. It executes no validation, browser, training, external write or workflow transition. Supply already-observed results; do not repeat checks to fill the page. Full visual or narrative artifacts may extend the fixed presentation when needed, without changing the authoritative records.

Plain text cards use the fixed layout with per-report link/status checks. Reuse an actual template layout check for unchanged plain text; this is not a claim that each card was visually inspected. New images/media/comparisons, layout changes and substantial reports still need inspection of the actual surface. Do not automatically rerun a browser for every worker.

## Fast local viewing and verification

- Deliver static UTF-8 HTML with a viewport declaration, readable contrast and responsive layout. Inline essential CSS. Core content MUST be present in the HTML, not fetched at runtime.
- Opening `index.html` through `file://` MUST show the report without a server, build step, login, package installation or network access. No CDN fonts, remote scripts or mandatory external chart libraries. Use relative local asset/navigation links; escape untrusted text rather than executing log/config content as HTML.
- Show thumbnails/selected previews first; defer large images and use video controls with `preload="metadata"` or `none`. Avoid autoplay and embedding entire checkpoints, datasets or full logs. Retain original large artifacts in their existing location; copy only small, useful presentation assets.
- For template/layout changes, new visual comparisons/media and substantial reports, open the actual page in a browser, inspect the first screen and exercise the local navigation/media used. Unchanged plain text cards may reuse the template layout check, but still verify their own local links and evidence states. Record the exact check scope; if browser/media support is unavailable, say so rather than claim visual verification.
- Final delivery MUST include the exact report path or clickable link, the main finding, and any material verification limit. A report-generation failure is a delivery issue, not permission to change experiment/acceptance state or claim the report exists.
