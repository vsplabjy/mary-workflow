---
name: paper
description: Manage Mary Workflow's v2.2 paper pipeline, perform contract-validated close reading from arXiv HTML/PDF, and produce source-grounded three-part summaries. Use when the user invokes /mw-paper, asks to register or inspect a paper, read a paper closely, summarize a completed paper read, supplies an arXiv id/URL or PDF, or applies paper stage transitions without plan/run authorization.
---

# Mary Workflow: Paper

Manage independent paper states, close reading, and grounded summaries under `.mary-research/papers/`.

## Procedure

1. Work from the user's current project root; do not require `/mw-init`.
2. Use `scripts/mw_paper.py` for every state read and mutation.
3. Use `create`, `list`, `status`, and `apply-action` for low-level state operations.
4. Require a canonical paper id and SHA-256 fingerprint contract.
5. Apply stage changes only through `start_stage`, `complete_stage`, `fail_stage`, `reset_stage`, and `update_source` envelopes.
6. Preserve the dependency graph:
   - `read` has no stage dependency;
   - `summary` depends on `read`;
   - `slides` depends on `summary`;
   - `quiz` depends on `read` and `summary`, not `slides`.
7. Let source changes and stage resets mark already-started downstream stages `stale`; leave never-started stages `pending`.
8. Do not run milestone grants or leases. Paper state is independent from `.mary-workflow/` and survives `/mw-init --reset`.
9. For `/mw-paper read <source>`:
   - run `prepare-read --source <source>` (and `--paper-id` when needed);
   - read `read-context.json`, `parse-quality.json`, and all of `source.md`;
   - if quality is blocked, show all five statuses and evidence, then stop for explicit user direction;
   - otherwise write `paper-notes.md` using the exact ledger contract and run `complete-read`.
10. Copy source identity and parse quality from `read-context.json`; do not calculate or improvise those fields.
11. Keep `uncertainties` non-empty. Add every degraded or failed quality dimension to at least one uncertainty.
12. Pass `--override-quality --override-reason <reason>` only after the user explicitly accepts a displayed blocked report. Never infer consent.
13. For `/mw-paper summarize [paper-id]`:
   - run `prepare-summary`, specifying `--paper-id` when needed;
   - read `paper-notes.md`, `summary-context.json`, and the relevant spans in `source.md`;
   - write `summary.md` with ordered background, method, and experiments claim arrays;
   - copy `inputs` exactly from summary context and use only `allowed_source_locators`;
   - copy each claim's evidence exactly from a cited source span;
   - run `complete-summary` and report any rejected claim without weakening the contract.
14. Do not generate `slides.md` or `quiz-log.md`; those stages are not implemented yet.

Read `references/paper-notes-contract.md` before producing notes and `references/summary-contract.md` before producing a summary. See `references/paper-state-contract.md` for state transitions.
