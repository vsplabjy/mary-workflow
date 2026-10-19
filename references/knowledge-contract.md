# Lightweight project knowledge

## Reading and authority

At a new project conversation, first read `.mary-workflow/knowledge/overview.md`, the relevant `modules/<id>.md` and `handoff.md`. Prefer the canonical reader below: it always renders `index.json`, so a process interruption cannot leave the reader using an older Markdown projection. It reads this one record, not code, Git diff, inventory, source hashes or all module files. The overview includes a short module index, status and unmapped changes; fetch detailed introductions only as needed.

```bash
python /path/to/mary-workflow/scripts/mw_knowledge.py read
python /path/to/mary-workflow/scripts/mw_knowledge.py read --module training
```

The index is the maintained structured source; Markdown files are generated views with their revision. If interrupted, `render` repairs views without reading source. Ordinary reads never write or lock. Files live under the existing exact ignored directory `.mary-workflow/`; they persist across local conversations but do not transfer to another machine unless explicitly exported. No host-global instruction, watcher or automatic session hook is installed. The Mary skill supplies the reading rule; hosts that do not invoke Mary must be told to read these documents.

These descriptions explain the project; they do not replace formal state, source truth, experiment results or USER_STOP. Reading handoff never authorizes resumption. `current` means the author updated the introduction against declared changes, not that tests passed or undocumented external edits were detected. `UNKNOWN`, `incomplete`, `stale` and unmapped changes remain visible. No helper can detect unreported shell/editor changes without a hook or scan; the agent must report its actual changed paths.

## What to record

- Overview: project purpose, current capability, architecture/data flow and major limitations. A short module index is generated automatically.
- Module: stable id, exact owned files, optional shared boundary files and dependency ids; responsibility, entrypoints, interfaces (inputs/outputs and consumers), constraints/design decisions, verification/use commands and known gaps. Use explicit UNKNOWN where knowledge is unavailable. Do not require an essay for every file.
- Handoff: current task and completed work, key decisions and reasons, pending work/blockers, relevant validation/results and record paths, current run/stop state with its authoritative record path, next useful action. Do not paste logs or duplicate full formal state.

Existing formal `submit_brief` seeds incomplete module introductions from in-memory coverage/positioning once, adding no scan. Later brief refreshes mark known changed paths stale and preserve richer authored text. Older brief metadata can be reused explicitly with `import-brief` (reads saved state only). Missing docs are not a reason to call full init. Legacy pinned bundles stay valid; new/explicitly upgraded bundles carry this additive profile. This helper can also be used directly from the installed skill without upgrading a project.

## Updating only affected knowledge

Before editing, mark the intended exact paths. This makes interruptions conservative. Account for additional actual changes at delivery. Deleted and renamed files use their old/new exact paths; update the affected ownership lists. No glob expansion, inventory traversal, source read or content hashing occurs.

```bash
python /path/to/mary-workflow/scripts/mw_knowledge.py changed \
  --files src/train.py configs/train.yaml --reason 'Adjust training schedule'
```

Owners, modules listing shared boundary files, and transitive dependents become stale. Unknown paths remain in `unmapped_files`; assigning ownership alone does not silently clear that warning. Update only the affected introductions; dependent modules can confirm that their interface remains valid without rewriting unrelated text. If unable to finish, retain stale status and add a short handoff. This must not block a previously authorized experiment launch.

An update payload contains optional `overview`, `handoff`, `modules` and `resolved_unmapped_files`. New introductions include all six description fields, an id and optional file/dependency mappings. Existing introductions accept just the changed fields, retaining the others; do not copy or rewrite unchanged descriptions. `reviewed_files` must exactly acknowledge that module's pending paths, including dependency changes. Imported placeholders remain incomplete until authored. Use the revision from `read` to prevent a late update from clearing a newer stale marker. Example (initial revision 0):

```json
{
  "overview": "Project purpose, architecture and current capability...",
  "handoff": "Completed ...; next ...; validation ...; no run started.",
  "modules": [{
    "id": "training",
    "files": ["src/train.py", "configs/train.yaml"],
    "boundary_files": [], "depends_on": [], "reviewed_files": [],
    "responsibility": "Optimize the model and save resumable checkpoints.",
    "entrypoints": "src/train.py; configuration in configs/train.yaml.",
    "interfaces": "Input: dataset and model. Output: checkpoints and metrics. Consumers: evaluation.",
    "constraints": "Checkpoint schema ...; schedule decision ...",
    "verification": "Known invocation ...; last check ...; unrun checks ...",
    "known_gaps": "UNKNOWN: production throughput has not been measured."
  }]
}
```

```bash
python /path/to/mary-workflow/scripts/mw_knowledge.py update \
  --data /tmp/authored-context.json --expected-revision 0
```

For previously unmapped paths, list them in `resolved_unmapped_files` after documenting their owner. For deliberate deletion of an unmapped file, also list it in `removed_files` and explain the deletion in `handoff`; the helper does not check filesystem existence. No automatic module deletion is performed. Lifecycle acceptance is separate. Formal worker result submission reuses already-observed paths to mark stale, including failed/blocked changes; the coordinator maintains docs after the receipt. Direct changes follow the same declared-path rule through the skill policy. Documentation-only projection writes do not recursively invalidate themselves. This is incremental bookkeeping, not another validation gate.
