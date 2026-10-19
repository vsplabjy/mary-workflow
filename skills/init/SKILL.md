---
name: init
description: Initialize or refresh a model-independent Mary Workflow project with inventory coverage and a persisted project brief. Use for /mw-init.
---

# Mary Workflow: Init

Work from the project root. Run `python ~/.codex/skills/mary-workflow/scripts/mary_workflow.py init`, then render `python ~/.codex/skills/mary-workflow/scripts/mw_codex.py mw-init`. Follow the pinned init phase and [memory contract](../../references/memory-contract.md).

Use direct reading for small projects, module summaries for medium projects, and independent explorer shards for large projects when available. Retain a machine inventory and fingerprints; require computed coverage of the relevant inventory, not prose fields for every file. Include boundaries, uncertainties, and honest validation evidence. Workers write task scratch; the main agent submits the brief.

Apply `config.yaml` `init.ignore` and project-root `.maryignore`. Run only appropriate authorized validation; mark unavailable checks skipped with a specific reason. Present the resulting project understanding and unresolved points with a link to the complete brief. Apply supported corrections through `update_project` or `submit_brief`.

Brief submission seeds lightweight knowledge from the metadata already collected. Complete overview, relevant module introductions and handoff using the [knowledge contract](../../references/knowledge-contract.md), reusing current understanding without a second scan. Imported summaries remain incomplete until authored. Reading context in a later conversation does not require init.

Existing projects preserve state and their pinned runtime/prompt bundle. If migration is needed, preview `mary_workflow.py migrate`; apply `migrate --apply` only within the user's upgrade authorization. Do not use reset for migration. `init --reset` is only for an explicit user request to delete and recreate workflow state. During active execution, report deferred brief refresh and continue the existing lifecycle.

Init appends missing project-root `.gitignore` rules for `/.mary-workflow/`, `/.mary-workflow-worker/`, `/.mary-research/` and `/.vspi/`, preserving existing content. These directories include generated records, hashes, config, runtime bundles, archives and worker scratch. Keep other workflow-only records there or ignore their exact paths before generating them. Existing tracked files remain tracked; do not change the index automatically.

Seed `.mary-research/reading-profile.md` from `defaults/reading-profile.md` only when absent. Preserve this visible, user-editable reading preference file on later init runs; it is ignored by default with other research configuration. Paper state remains independent. Init does not install shell commands or modify host settings. Begin planning only after the project brief is complete.
