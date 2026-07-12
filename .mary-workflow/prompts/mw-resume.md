# Mary Resume Phase

## Language Policy

推理过程、进度叙述、review 结论和用户可见回答必须遵守 `.mary-workflow/config.yaml` 的 `output.language`：默认 `zh` 一律中文，`auto` 表示跟随当前会话语言，`en` 表示英文。机器字段必须保持英文，包括 command、file name、YAML key、milestone id、phase value、action name、JSON key。`log.md` 日志行保持英文，便于 grep 和审计统计。

## Agent Protocol

You are the `/mw-run` resume gate for Mary Workflow v2.1.

### Phase Gate

Read `.mary-workflow/state.yaml` and verify:

- phase is `EXECUTING`, `REVIEWING`, or `DEBUGGING`
- workflow status is `stopped`
- `execution_lease.status` is `paused`

If any condition differs, stop without editing product files.

### Resume Action

Copy the plaintext token from this render's `Run Authorization` block:

```json
{
  "action": "resume_execution",
  "data": {
    "token": "<copy token from this render's Run Authorization block>"
  }
}
```

The token is single-use and `state.yaml` stores only its digest. Apply the action with `mary_workflow.py apply-action`, never expose the token in user-visible output or logs, then rerender `/mw-run` to continue the preserved phase and run lease.
