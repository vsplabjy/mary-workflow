---
name: init
description: Initialize or refresh a model-independent Mary Workflow project with inventory coverage and a persisted project brief. Use for /mw-init.
---

# Mary Workflow: Init

Work from the project root. Run `python ~/.codex/skills/mary-workflow/scripts/mary_workflow.py init`, then render `python ~/.codex/skills/mary-workflow/scripts/mw_codex.py mw-init`. Follow the pinned init phase and [memory contract](../../references/memory-contract.md).

Use direct reading for small projects, module summaries for medium projects, and independent explorer shards for large projects when available. Retain a machine inventory and fingerprints; require computed coverage of the relevant inventory, not prose fields for every file. Include boundaries, uncertainties, and honest validation evidence. Workers write task scratch; the main agent submits the brief.

Apply `config.yaml` `init.ignore` and project-root `.maryignore`. Run only appropriate authorized validation; mark unavailable checks skipped with a specific reason. Present the resulting project understanding and unresolved points with a link to the complete brief. Apply supported corrections through `update_project` or `submit_brief`.

Existing projects preserve state and their pinned runtime/prompt bundle. If migration is needed, preview `mary_workflow.py migrate`; apply `migrate --apply` only within the user's upgrade authorization. Do not use reset for migration. `init --reset` is only for an explicit user request to delete and recreate workflow state. During active execution, report deferred brief refresh and continue the existing lifecycle.

Seed `.mary-research/reading-profile.md` from `defaults/reading-profile.md` only when absent. Preserve this visible, user-editable, Git-trackable reading preference file on later init runs. Paper state remains independent. Init does not install shell commands or modify host settings. Begin planning only after the project brief is complete.
