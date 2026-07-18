---
description: Manage the v2.2 paper-pipeline state skeleton independently from plan/run.
argument-hint: [create|list|status|apply-action] [options]
---

# /mw-paper

Manage project-local paper workspaces without entering the milestone workflow authorization flow.

## Instructions

1. Work from the user's current project root. `/mw-init` is not required.
2. Route `$ARGUMENTS` to the P1 runtime:

   ```bash
   python ~/.codex/skills/mary-workflow/scripts/mw_paper.py <subcommand> <options>
   ```

3. Supported P1 subcommands:
   - no arguments: run `list`;
   - `list`: list registered paper ids;
   - `status [paper-id]`: run `status`, adding `--paper-id` when supplied;
   - `create --source <locator> --fingerprint <sha256> [--paper-id <id>]`: create an independent paper state;
   - `apply-action [paper-id]`: apply one `start_stage`, `complete_stage`, `fail_stage`, `reset_stage`, or `update_source` envelope with `--json` or `--file`.
4. Treat `.mary-research/papers/<paper-id>/state.json` as authority. Never hand-edit it.
5. Do not invoke `/mw-plan`, `/mw-run`, grants, or execution leases for paper actions.
6. P1 implements state only. If the user asks to read, summarize, generate slides, or run a quiz, report the recorded stage status and stop; do not fabricate stage artifacts before their implementation milestone.
