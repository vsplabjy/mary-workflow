---
name: paper
description: Manage Mary Workflow's v2.2 paper-pipeline state skeleton. Use when the user invokes /mw-paper, registers a paper workspace, inspects paper progress, or applies validated paper stage transitions without plan/run authorization.
---

# Mary Workflow: Paper

Manage independent paper states under `.mary-research/papers/`.

## Procedure

1. Work from the user's current project root; do not require `/mw-init`.
2. Use `scripts/mw_paper.py` for every state read and mutation.
3. Support `create`, `list`, `status`, and `apply-action` in P1.
4. Require a canonical paper id and SHA-256 fingerprint contract.
5. Apply stage changes only through `start_stage`, `complete_stage`, `fail_stage`, `reset_stage`, and `update_source` envelopes.
6. Preserve the dependency graph:
   - `read` has no stage dependency;
   - `summary` depends on `read`;
   - `slides` depends on `summary`;
   - `quiz` depends on `read` and `summary`, not `slides`.
7. Let source changes and stage resets mark already-started downstream stages `stale`; leave never-started stages `pending`.
8. Do not run milestone grants or leases. Paper state is independent from `.mary-workflow/` and survives `/mw-init --reset`.
9. P1 does not produce paper notes, summaries, slides, or quiz content. Stop after the requested state operation.

See `references/paper-state-contract.md` in the plugin root for the complete schema and transition contract.
