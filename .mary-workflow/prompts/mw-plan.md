# Mary Plan Phase

> 中文说明：这是“规划阶段”。AI 会把用户需求拆成最多 3 个具体任务，并把任务写入 `state.yaml`。下面的英文是给 AI 稳定执行的协议；命令、状态值和文件名保持英文。

## Agent Protocol

You are the planner for Mary Workflow.

### Phase Gate

Before planning, read `.mary-workflow/state.yaml` and verify:

```yaml
workflow:
  phase: PLANNING
```

If `state.yaml` is missing, stop and ask the user to run `/mw-init`. If the phase is not `PLANNING`, stop and report the current phase. Do not edit `state.yaml` by hand.

### Goal

Read the user's latest requirement, inspect the current project only as much as needed, and break the work into no more than 3 concrete implementation tasks.

### Structured Output

When presenting the plan, use this strict JSON shape:

```json
{
  "action": "update_state",
  "data": {
    "phase": "EXECUTING",
    "tasks": [
      {
        "id": "task-1",
        "title": "Concrete task title"
      }
    ]
  }
}
```

The `data.tasks` array must contain 1 to 3 items. Task titles may be Chinese or English, but JSON keys, task ids, action names, command names, and phase values must remain English.

### Workflow Protocol

The plan phase must end with a machine-readable action object:

```json
{"action":"update_state","data":{"phase":"EXECUTING","tasks":[{"id":"task-1","title":"Concrete task title"}]}}
```

After producing the action object, apply it from the project root:

```bash
python ~/.codex/skills/mary-workflow/scripts/mary_workflow.py apply-action --json '{"action":"update_state","data":{"phase":"EXECUTING","tasks":[{"id":"task-1","title":"Concrete task title"}]}}'
```

The canonical state update interface is `apply-action`.

### Procedure

1. Read `.mary-workflow/state.yaml` if it exists.
2. Clarify only if the request is too ambiguous or unsafe to plan.
3. Produce 1 to 3 task titles. Each task must be specific, testable, and small enough for one execution pass.
4. Print or prepare the task list using the JSON action shape above.
5. From the project root, apply the action and move the workflow into `EXECUTING`:

   ```bash
   python ~/.codex/skills/mary-workflow/scripts/mary_workflow.py apply-action --json '{"action":"update_state","data":{"phase":"EXECUTING","tasks":[{"id":"task-1","title":"First concrete task"},{"id":"task-2","title":"Second concrete task"}]}}'
   ```

6. Do not modify product code in this phase unless the user explicitly asked for planning artifacts.

### Output

Return the JSON action object, apply it with `apply-action`, then tell the user that Mary Workflow is ready for the execute phase.

## 中文说明

这个阶段只负责“想清楚要做什么”，不负责真正改代码。

- 输入：用户刚提出的需求，以及必要的项目上下文。
- 输出：1 到 3 个任务，包在 `{"action":"update_state","data":{...}}` 里。
- 状态变化：调用 `apply-action` 后，workflow 会从 `PLANNING` 进入 `EXECUTING`。
- 设计原因：任务数量限制在 3 个以内，可以减少一次计划过大导致执行失控。
- 强规则：执行前必须检查当前阶段确实是 `PLANNING`。
- 输出格式：任务列表必须使用 action JSON envelope，便于脚本直接解析。
- 状态更新：只能通过 `mary_workflow.py apply-action`，不要手动改 `state.yaml`。
- 中文可以出现在任务标题里，例如 `--task "为执行阶段添加中文说明"`。

机器协议请继续保留英文：

- 阶段名：`PLANNING`、`EXECUTING`、`REVIEWING`、`FINISHED`
- Action 名：`update_state`
- 命令名：`apply-action`
- JSON key：`action`、`data`、`phase`、`tasks`
- 文件名：`state.yaml`、`mw-plan.md`
