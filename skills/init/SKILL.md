---
name: init
description: Initialize or reset Mary Workflow v2.1 in the current project. Use when the user invokes /mw-init or asks to initialize Mary workflow.
---

# Mary Workflow: Init

Initialize the project-local `.mary-workflow/` workspace.

## Procedure

1. Work from the user's current project root.
2. Run:

   ```bash
   python ~/.codex/skills/mary-workflow/scripts/mary_workflow.py init
   ```

3. If the user passes `--reset`, run `init --reset`.
4. Render init understanding context:

   ```bash
   python ~/.codex/skills/mary-workflow/scripts/mw_codex.py mw-init
   ```

5. Follow `mw-init.md`: complete the full three-pass read, execute safe build/test/run validation, write the full envelope to `.mary-workflow/analysis/submit-brief.json`, and apply the machine-validated `submit_brief` with `--file`.
6. Present the entire `.mary-workflow/project-brief.md` to the user, then ask for factual corrections and `zh`/`auto`/`en` preference.
7. Apply `config.yaml` `init.ignore` and project-root `.maryignore` before treating the remaining inventory as exhaustive.
8. On an existing v2.1 project, preserve state and refresh prompts. Detect drift only in `PLANNING`, `PLANNED`, or `FINISHED`; in active execution phases report that the brief check was skipped. Earlier contracts require `--reset`.
9. Seed `.mary-research/reading-profile.md` from the versioned workflow default `defaults/reading-profile.md` only when it is absent. The project copy is a visible, user-editable Markdown file for paper-reading language, prerequisite, explanation-depth, evidence, and open-question preferences; preserve it on later init runs. It is intentionally Git-trackable while other `.mary-research/` artifacts stay ignored.
10. Do not hand off to `/mw-plan` until `project_brief_status: complete`.
