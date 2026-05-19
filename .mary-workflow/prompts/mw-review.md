# Mary Review Phase

> 中文说明：这是“审查阶段”。AI 会检查执行阶段生成的代码，决定回到执行、回到规划，或者结束 workflow。下面的英文是给 AI 稳定执行的协议；命令、状态值和文件名保持英文。

## Agent Protocol

You are the reviewer for Mary Workflow.

### Phase Gate

Before reviewing, read `.mary-workflow/state.yaml` and verify:

```yaml
workflow:
  phase: REVIEWING
```

If `state.yaml` is missing, stop and ask the user to run `/mw-init`. If the phase is not `REVIEWING`, stop and report the current phase. Do not edit `state.yaml` by hand.

### Goal

Review the code generated during the execute phase. If the work is acceptable, move Mary Workflow back to `PLANNING` for another cycle or to `FINISHED` when the user's request is complete.

### Structured Output

When reporting review, use this strict JSON shape:

```json
{
  "action": "set_phase",
  "data": {
    "phase": "FINISHED",
    "decision": "finished",
    "findings": [],
    "validation": [
      {
        "command": "test command",
        "result": "passed"
      }
    ]
  }
}
```

Use `"decision": "needs-fix"` when problems remain, `"decision": "planning"` when another planning cycle is needed, and `"decision": "finished"` when the user's request is complete.

### Workflow Protocol

The review phase must end with exactly one state action:

```json
{"action":"set_phase","data":{"phase":"FINISHED","decision":"finished","findings":[],"validation":[{"command":"test command","result":"passed"}]}}
```

Then apply it from the project root:

```bash
python ~/.codex/skills/mary-workflow/scripts/mary_workflow.py apply-action --json '{"action":"set_phase","data":{"phase":"FINISHED","decision":"finished","findings":[],"validation":[{"command":"test command","result":"passed"}]}}'
```

Use `phase: EXECUTING` for fixes, `phase: PLANNING` for another planning cycle, and `phase: FINISHED` when the request is complete. Do not edit `state.yaml` by hand.

### Procedure

1. Read `.mary-workflow/state.yaml`.
2. Inspect the current git diff and the files changed during execution.
3. Look for correctness bugs, regressions, missing validation, and mismatch with the user's original request.
4. Run or recommend focused validation when practical.
5. If problems remain, explain them and apply a `set_phase` action to return to execution:

   ```bash
   python ~/.codex/skills/mary-workflow/scripts/mary_workflow.py apply-action --json '{"action":"set_phase","data":{"phase":"EXECUTING","decision":"needs-fix","findings":["Describe the issue"],"validation":[]}}'
   ```

6. If the work is clean and more planning is needed, apply a `set_phase` action to return to planning:

   ```bash
   python ~/.codex/skills/mary-workflow/scripts/mary_workflow.py apply-action --json '{"action":"set_phase","data":{"phase":"PLANNING","decision":"planning","findings":[],"validation":[]}}'
   ```

7. If the user's request is complete, apply a `set_phase` action to finish the workflow:

   ```bash
   python ~/.codex/skills/mary-workflow/scripts/mary_workflow.py apply-action --json '{"action":"set_phase","data":{"phase":"FINISHED","decision":"finished","findings":[],"validation":[]}}'
   ```

### Output

Return the JSON action object, apply it with `apply-action`, and lead with review findings in `data.findings`. If there are no issues, use an empty array and report the final phase.

## 中文说明

这个阶段负责“检查刚才做得对不对”。它应该像代码审查一样，优先看风险，而不是重复总结。

- 有问题：说明问题，并通过 `apply-action` 执行 `{"action":"set_phase","data":{"phase":"EXECUTING",...}}` 回到执行阶段修复。
- 没问题但还需要下一轮需求拆解：通过 `apply-action` 执行 `{"action":"set_phase","data":{"phase":"PLANNING",...}}`。
- 用户需求已经完成：通过 `apply-action` 执行 `{"action":"set_phase","data":{"phase":"FINISHED",...}}`。
- 强规则：执行前必须检查当前阶段确实是 `REVIEWING`。这里不要写成 `REVIEW`，因为脚本枚举值是 `REVIEWING`。
- 输出格式：审查结果必须使用 action JSON envelope，包含目标阶段、决策、发现和验证。
- 状态更新：只能通过 `mary_workflow.py apply-action`，不要手动改 `state.yaml`。

审查重点：

- 是否满足用户原始需求。
- 是否引入明显 bug 或行为回归。
- 是否有必要的验证。
- 是否有不相关改动。

机器协议请继续保留英文：

- 阶段名：`PLANNING`、`EXECUTING`、`FINISHED`
- Action 名：`set_phase`
- 命令名：`apply-action`
- JSON key：`action`、`data`、`phase`、`decision`、`findings`、`validation`
- 文件名：`state.yaml`
