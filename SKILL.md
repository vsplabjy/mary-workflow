---
name: mary-workflow
description: Run a minimal project-local prompt workflow from `.mary-workflow/`. Use when the user invokes `/mw:init`, `/mw:start`, `/mw:next`, `/mw:resume`, `/mw:status`, `/mw:stop`, or asks to run Mary workflow.
---

# Mary Workflow

Mary Workflow is a small three-phase workflow. It keeps project-local state in `.mary-workflow/` and drives the agent through `PLANNING`, `EXECUTING`, and `REVIEWING` phases.

## Commands

Use `scripts/mary_workflow.py` for deterministic state operations:

```bash
python ~/.codex/skills/mary-workflow/scripts/mary_workflow.py <command>
```

- `/mw:init`: create `.mary-workflow/` with `config.yaml`, `state.yaml`, `prompts/`, and `log.md`.
- `/mw:start`: set the workflow to `PLANNING` and select `mw-plan.md`.
- `/mw:next` or `/mw:resume`: execute the prompt for the current phase.
- `/mw:status`: show current status, phase, progress, prompt file, and task list.
- `/mw:stop`: set the workflow status to `stopped` and append a log entry.

## Runtime Rules

1. Before any command, work from the user's current project directory.
2. If `.mary-workflow/` is missing, run `/mw:init` when the user asked to initialize; otherwise tell the user to run `/mw:init`.
3. For state-only operations, use `scripts/mary_workflow.py`.
4. The core phase prompts are:

   - `PLANNING`: `.mary-workflow/prompts/mw-plan.md`
   - `EXECUTING`: `.mary-workflow/prompts/mw-execute.md`
   - `REVIEWING`: `.mary-workflow/prompts/mw-review.md`

5. Append important user-visible events to `.mary-workflow/log.md`.
6. User-facing output should follow the user's conversation language.

## Prompt Execution

When executing a prompt:

1. Read `.mary-workflow/state.yaml`.
2. Read `.mary-workflow/prompts/<current prompt>`.
3. Treat the prompt as the active user task.
4. Complete the phase with normal Codex engineering discipline.
5. Use `mary_workflow.py` commands from the prompt to update phase and task state.
6. Report the result and the next phase, if any.

## Phase Commands

- Planning writes up to 3 tasks and enters execution:

  ```bash
  python ~/.codex/skills/mary-workflow/scripts/mary_workflow.py plan --task "Task one" --task "Task two"
  ```

- Execution reads the first pending task and marks completed work done:

  ```bash
  python ~/.codex/skills/mary-workflow/scripts/mary_workflow.py next-task
  python ~/.codex/skills/mary-workflow/scripts/mary_workflow.py done-task --id task-1
  ```

- Review moves to the next phase:

  ```bash
  python ~/.codex/skills/mary-workflow/scripts/mary_workflow.py set-phase PLANNING
  python ~/.codex/skills/mary-workflow/scripts/mary_workflow.py set-phase FINISHED
  ```

## File Contract

See `references/state-contract.md` for the expected `.mary-workflow/` files and state fields.
