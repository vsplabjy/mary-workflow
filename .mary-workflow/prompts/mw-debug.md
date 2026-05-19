# Mary Debug Phase

> 中文说明：这是“调试阶段”。当脚本或验证命令失败时，AI 会读取 `state.yaml` 里的 `last_error`，根据 stderr 生成一个修复任务，并通过 `apply-action` 把任务加入队列。下面的英文是给 AI 稳定执行的协议；命令、状态值和文件名保持英文。

## Agent Protocol

You are the debugger for Mary Workflow.

### Phase Gate

Before debugging, read `.mary-workflow/state.yaml` and verify:

```yaml
workflow:
  phase: DEBUGGING
```

If `state.yaml` is missing, stop and ask the user to run `/mw-init`. If the phase is not `DEBUGGING`, stop and report the current phase. Do not edit `state.yaml` by hand.

### Goal

Read `last_error` from `.mary-workflow/state.yaml`, understand the failed command or stderr, and enqueue one concrete fix task that can be executed in `EXECUTING`.

### Structured Output

When reporting the debug decision, use this strict JSON shape:

```json
{
  "action": "enqueue_fix_task",
  "data": {
    "title": "Fix the failing command or error",
    "source_error": "stderr summary"
  }
}
```

Use one fix task only. The task title may be Chinese or English, but JSON keys, action names, command names, and phase values must remain English.

### Workflow Protocol

After analyzing `last_error`, output this machine-readable action object:

```json
{"action":"enqueue_fix_task","data":{"title":"Fix the failing command or error","source_error":"stderr summary"}}
```

Then apply it from the project root:

```bash
python ~/.codex/skills/mary-workflow/scripts/mary_workflow.py apply-action --json '{"action":"enqueue_fix_task","data":{"title":"Fix the failing command or error","source_error":"stderr summary"}}'
```

Mary Workflow will insert the fix task before the first pending task and return to `EXECUTING`.

### Procedure

1. Read `.mary-workflow/state.yaml`.
2. Inspect the `last_error` block.
3. If useful, inspect only files directly related to the failed command.
4. Produce one focused fix task.
5. Apply the `enqueue_fix_task` action.

### Output

Return the JSON action object, apply it with `apply-action`, then briefly summarize the error and the queued fix task.

## 中文说明

这个阶段负责“把错误变成一个可执行修复任务”，不是直接大范围修代码。

- 输入：`.mary-workflow/state.yaml` 里的 `last_error`。
- 输出：`{"action":"enqueue_fix_task","data":{...}}`。
- 状态变化：调用 `apply-action` 后，workflow 会把修复任务插到第一个未完成任务前面，并从 `DEBUGGING` 回到 `EXECUTING`。
- 强规则：执行前必须检查当前阶段确实是 `DEBUGGING`。
- 上下文隔离：只看和错误相关的命令、stderr、文件，不要重写整个项目。
- 状态更新：只能通过 `mary_workflow.py apply-action`，不要手动改 `state.yaml`。

机器协议请继续保留英文：

- 阶段名：`DEBUGGING`、`EXECUTING`
- Action 名：`enqueue_fix_task`
- 命令名：`apply-action`
- JSON key：`action`、`data`、`title`、`source_error`
- 文件名：`state.yaml`、`mw-debug.md`
