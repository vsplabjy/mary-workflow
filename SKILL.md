---
name: mary-workflow
description: Run a minimal project-local prompt workflow from `.mary-workflow/`. Use when the user invokes `/mw-init`, `/mw-start`, `/mw-next`, `/mw-resume`, `/mw-status`, `/mw-stop`, `/mw-plan`, `/mw-run`, `/mw-review`, `/mw-debug`, or asks to run Mary workflow.
---

# Mary Workflow

Mary Workflow is a small workflow. It keeps project-local state in `.mary-workflow/` and drives the agent through `PLANNING`, `EXECUTING`, `REVIEWING`, and `DEBUGGING` phases.

## Commands

Use `scripts/mary_workflow.py` for deterministic state operations:

```bash
python ~/.codex/skills/mary-workflow/scripts/mary_workflow.py <command>
```

- `/mw-init`: create `.mary-workflow/` with `config.yaml`, `state.yaml`, `prompts/`, and `log.md`.
- `/mw-start`: set the workflow to `PLANNING` and select `mw-plan.md`.
- `/mw-next`: load the prompt matching `workflow.phase`.
- `/mw-resume`: alias of `/mw-next`.
- `/mw-status`: show current status, phase, progress, prompt file, and task list.
- `/mw-stop`: set the workflow status to `stopped` and append a log entry.
- `/mw-plan`: load `mw-plan.md` as the current Codex instruction context.
- `/mw-run`: load `mw-execute.md` as the current Codex instruction context.
- `/mw-review`: load `mw-review.md` as the current Codex instruction context.
- `/mw-debug`: load `mw-debug.md` as the current Codex instruction context.

## Runtime Rules

1. Before any command, work from the user's current project directory.
2. If `.mary-workflow/` is missing, run `/mw-init` when the user asked to initialize; otherwise tell the user to run `/mw-init`.
3. For state-only operations, use `scripts/mary_workflow.py`.
4. Prompts may be bilingual: keep the English `Agent Protocol` as the execution contract and use Chinese `中文说明` sections for human explanation.
5. Machine-facing names stay in English: command names, file names, YAML keys, task ids, and phase values.
6. Every phase prompt must gate on `.mary-workflow/state.yaml` before acting and stop on phase mismatch.
7. Every phase prompt must use an action JSON envelope for user-visible structured output: `{"action":"...","data":{...}}`.
8. Never hand-edit `.mary-workflow/state.yaml` during phase execution; update state through `scripts/mary_workflow.py apply-action`.
9. The core phase prompts are:

   - `PLANNING`: `.mary-workflow/prompts/mw-plan.md`
   - `EXECUTING`: `.mary-workflow/prompts/mw-execute.md`
   - `REVIEWING`: `.mary-workflow/prompts/mw-review.md`
   - `DEBUGGING`: `.mary-workflow/prompts/mw-debug.md`

10. Append important user-visible events to `.mary-workflow/log.md`.
11. User-facing output should follow the user's conversation language.

## Codex Native Commands

The Codex plugin manifest lives at `.codex-plugin/plugin.json`. It exposes Mary Workflow metadata and this skill to Codex.

Native slash command entries live in the plugin root `commands/` directory. Codex discovers those Markdown files by filename:

- `commands/mw-init.md` -> `/mw-init`
- `commands/mw-start.md` -> `/mw-start`
- `commands/mw-plan.md` -> `/mw-plan`
- `commands/mw-run.md` -> `/mw-run`
- `commands/mw-review.md` -> `/mw-review`
- `commands/mw-debug.md` -> `/mw-debug`
- `commands/mw-next.md` -> `/mw-next`
- `commands/mw-resume.md` -> `/mw-resume`
- `commands/mw-status.md` -> `/mw-status`
- `commands/mw-stop.md` -> `/mw-stop`

`plugin.json` remains metadata. Command behavior is defined by the Markdown files above, and phase prompt loading is handled by `scripts/mw_codex.py`.

When the user invokes `/mw-plan`, `/mw-run`, `/mw-review`, `/mw-debug`, `/mw-next`, `/mw-resume`, or `/mw-status`:

1. Run the bridge from the project root:

   ```bash
   python ~/.codex/skills/mary-workflow/scripts/mw_codex.py mw-plan
   ```

   Replace `mw-plan` with `mw-run`, `mw-review`, `mw-debug`, `mw-next`, `mw-resume`, or `mw-status` as needed.

2. Treat the bridge output as the active phase instruction context for this turn.
3. For `/mw-status`, report the rendered state without mutating it.
4. For phase aliases, execute the loaded phase prompt normally.
5. Use `mary_workflow.py apply-action` for state updates.

Alias mapping:

- `/mw-plan` -> `PLANNING` -> `.mary-workflow/prompts/mw-plan.md`
- `/mw-run` -> `EXECUTING` -> `.mary-workflow/prompts/mw-execute.md`
- `/mw-review` -> `REVIEWING` -> `.mary-workflow/prompts/mw-review.md`
- `/mw-debug` -> `DEBUGGING` -> `.mary-workflow/prompts/mw-debug.md`
- `/mw-next` -> current `workflow.phase` -> matching prompt
- `/mw-resume` -> current `workflow.phase` -> matching prompt
- `/mw-status` -> current `workflow.phase` -> state context only

## Prompt Execution

When executing a prompt:

1. Read `.mary-workflow/state.yaml`.
2. Verify `workflow.phase` matches the prompt being executed.
3. Read `.mary-workflow/prompts/<current prompt>`.
4. Treat the prompt as the active user task.
5. Complete the phase with normal Codex engineering discipline.
6. Use `mary_workflow.py apply-action` with the prompt's action JSON to update phase and task state.
7. Report the action JSON object, then add a brief human summary when useful.

## Phase Commands

- Planning writes up to 3 tasks and enters execution:

  ```bash
  python ~/.codex/skills/mary-workflow/scripts/mary_workflow.py apply-action --json '{"action":"update_state","data":{"phase":"EXECUTING","tasks":[{"id":"task-1","title":"Task one"},{"id":"task-2","title":"Task two"}]}}'
  ```

- Execution reads the first pending task and marks completed work done:

  ```bash
  python ~/.codex/skills/mary-workflow/scripts/mary_workflow.py next-task
  python ~/.codex/skills/mary-workflow/scripts/mary_workflow.py apply-action --json '{"action":"mark_task_done","data":{"id":"task-1","result":"done","files_changed":[],"validation":[]}}'
  ```

- Review moves to the next phase:

  ```bash
  python ~/.codex/skills/mary-workflow/scripts/mary_workflow.py apply-action --json '{"action":"set_phase","data":{"phase":"FINISHED","decision":"finished","findings":[],"validation":[]}}'
  ```

- Debug turns stderr into a fix task:

  ```bash
  python ~/.codex/skills/mary-workflow/scripts/mary_workflow.py record-error --command "pytest" --stderr "failure summary" --returncode 1
  python ~/.codex/skills/mary-workflow/scripts/mary_workflow.py apply-action --json '{"action":"enqueue_fix_task","data":{"title":"Fix pytest failure","source_error":"failure summary"}}'
  ```

## File Contract

See `references/state-contract.md` for the expected `.mary-workflow/` files and state fields.
