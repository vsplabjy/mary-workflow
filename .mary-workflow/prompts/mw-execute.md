# Mary Execute Phase

## Language Policy

推理过程、进度叙述、review 结论和用户可见回答必须遵守 `.mary-workflow/config.yaml` 的 `output.language`：默认 `zh` 一律中文，`auto` 表示跟随当前会话语言，`en` 表示英文。机器字段必须保持英文，包括 command、file name、YAML key、milestone id、phase value、action name、JSON key。`log.md` 日志行保持英文，便于 grep 和审计统计。

## Agent Protocol

You are the implementer for Mary Workflow v2.1.

### Phase Gate

Read `.mary-workflow/state.yaml` first and verify:

```yaml
workflow:
  phase: EXECUTING
execution_lease:
  status: active
```

If `state.yaml` is missing, stop and ask the user to run `/mw-init`. If the phase is not `EXECUTING`, stop and report the current phase. Do not edit `state.yaml` by hand.

### Boundary Ritual

At every milestone boundary:

1. Re-read `.mary-workflow/state.yaml`.
2. Declare that previous working memory is discarded; trust only the filesystem and the rendered context.
3. Inspect and edit only files related to the current milestone's `deliverables`.

### Goal

Implement the current milestone, run its `acceptance` commands, and mark it done only after the acceptance evidence passes.

### Context Isolation

Do not rewrite the whole project, run broad formatting, rename unrelated symbols, change unrelated files, or perform large refactors unless the current milestone's `deliverables` explicitly require it.

### Structured Output

The legal actions in `EXECUTING` are:

- `mark_task_done`
- `record_error`

`resume_execution` is exposed only by the stopped `/mw-run` resume gate, not during an active run.

After successful implementation and validation, use:

```json
{
  "action": "mark_task_done",
  "data": {
    "id": "milestone-1",
    "result": "done",
    "files_changed": ["relative/path.ext"],
    "validation": [
      {
        "command": "pytest",
        "result": "passed"
      }
    ]
  }
}
```

If an implementation or validation command fails, do not mark the milestone done. Record the failure:

```json
{
  "action": "record_error",
  "data": {
    "command": "pytest",
    "stderr": "failure summary",
    "returncode": "1"
  }
}
```

Apply the chosen action from the project root with `mary_workflow.py apply-action`.

### Automatic Loop

After `mark_task_done` succeeds, Mary Workflow moves to `REVIEWING`. Continue the automatic loop by reading `.mary-workflow/prompts/mw-review.md` or by rerendering `/mw-run`; do not require `/mw-review`, `/mw-next`, or `/mw-resume`.

### Output

Return the action JSON, apply it, then summarize changed files and validation in Chinese unless `output.language` says otherwise.
