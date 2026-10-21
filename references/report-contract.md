# HTML presentation reports

This is the maintained contract for user-facing visual reports. The main agent creates and verifies the report as part of delivery; it does not replace experiment records, formal execution/review receipts or domain acceptance.

## When a report is required

Create an HTML report when any of these conditions applies:

- An experiment round ends: completed, failed or stopped. A round is the agreed run or comparison batch, not every training step or seed in a still-running batch. Preserve failures and partial results.
- A substantial task or milestone finishes: it has an independently useful deliverable and an observable effect or acceptance result. Routine small edits, ordinary questions and progress messages do not each need a report.
- A larger task or run ends without success: it fails, is blocked by missing external resources or authorization, exhausts its automatic repair budget, or is stopped for handoff. Report the failure/closure the same way as completion; a fake `FINISHED` or silent abandonment is not an alternative.
- The user explicitly requests a report, including while work is still running. Record the snapshot time, live status and unfinished work; do not imply completion.

Discussion-only and read-only requests remain read-only unless the user explicitly asks to create a report file; the only other exemption is an explicit user prohibition on writing files. A read-only status command does not create reports. For detached experiments, report at the next authorized completion observation/delivery; do not block launch, invent a watcher, or claim the supervisor authors a report after the chat ends. Do not mark a live run finished to trigger reporting. Reuse available evidence; never rerun experiments, access held-out inputs or consume additional GPU resources merely to populate a page.

Before writing a closure report, stop dispatching new work, appropriately stop or interrupt owned running processes, and let observed writes stabilize; report what could not be stopped and who owns it. The report itself is not acceptance: creating it never changes phase, run status, assessment or scientific claims, and it never substitutes for formal execution/review receipts. If the report file cannot be written (read-only host, explicit user prohibition, unavailable filesystem), deliver the same closure content honestly in chat — earliest confirmed cause or `UNKNOWN`, finished vs unfinished work, actual changes, check states, remaining repair budget and the next concrete step — instead of promising a file that does not exist or an unsupervised automatic report service.

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

For a failure, blockage, budget exhaustion or stop handoff, the first screen states the earliest confirmed cause (or `UNKNOWN` with what was ruled out), what finished and what remains unsupported, actual modified paths, each check's real state (`通过/失败/运行中/未运行`), remaining repair budget when a budget applies, and the concrete next step (user authorization, replan, or explicit stop). Do not relabel the closure as acceptance or completion.

## Fast local viewing and verification

- Deliver static UTF-8 HTML with a viewport declaration, readable contrast and responsive layout. Inline essential CSS. Core content MUST be present in the HTML, not fetched at runtime.
- Opening `index.html` through `file://` MUST show the report without a server, build step, login, package installation or network access. No CDN fonts, remote scripts or mandatory external chart libraries. Use relative local asset/navigation links; escape untrusted text rather than executing log/config content as HTML.
- Show thumbnails/selected previews first; defer large images and use video controls with `preload="metadata"` or `none`. Avoid autoplay and embedding entire checkpoints, datasets or full logs. Retain original large artifacts in their existing location; copy only small, useful presentation assets.
- Open the actual page in a browser, inspect the first screen and relevant comparisons, and exercise local navigation/media used by the report. Verify local asset links. Record what was actually checked; if browser/media support is unavailable, state the exact limit instead of claiming visual verification.
- Final delivery MUST include the exact report path or clickable link, the main finding, and any material verification limit. A report-generation failure is a delivery issue, not permission to change experiment/acceptance state or claim the report exists.
