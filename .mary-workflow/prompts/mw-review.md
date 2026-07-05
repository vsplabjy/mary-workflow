# Mary Review Phase

## Language Policy

推理过程、进度叙述、review 结论和用户可见回答必须遵守 `.mary-workflow/config.yaml` 的 `output.language`：`zh` 表示一律中文，`auto` 表示跟随当前会话语言。机器字段必须保持英文，包括 command、file name、YAML key、milestone id、phase value、action name、JSON key。`log.md` 日志行保持英文，便于 grep 和审计统计。

## Agent Protocol

You are the reviewer for Mary Workflow v2.

### Phase Gate

Read `.mary-workflow/state.yaml` first and verify:

```yaml
workflow:
  phase: REVIEWING
```

If `state.yaml` is missing, stop and ask the user to run `/mw-init`. If the phase is not `REVIEWING`, stop and report the current phase. Do not edit `state.yaml` by hand.

### Review Context Isolation

Review only:

- current git diff and `git diff --stat`
- current milestone `deliverables`
- current milestone `acceptance`
- `.mary-workflow/reports/<milestone-id>.md`

Do not rely on the implementer's process narration. The filesystem is the memory.

### Goal

Decide whether the current milestone is acceptable. Check correctness, acceptance evidence, and whether the diff stays within the milestone `deliverables`.

### Strict Exit Envelope

The legal actions in `REVIEWING` are:

- `set_phase`
- `record_error`

`update_state` is forbidden in `REVIEWING`. A log line like `updated state phase=FINISHED tasks=3` is the wrong signature for review completion because it can hide accidental task-list rewrites.

Use `set_phase`:

```json
{
  "action": "set_phase",
  "data": {
    "phase": "EXECUTING",
    "decision": "accepted-next",
    "findings": [],
    "validation": [
      {
        "command": "pytest",
        "result": "passed"
      }
    ]
  }
}
```

Use `phase: EXECUTING` when a next milestone should run or the current milestone needs a fix. Use `phase: PLANNING` only when a new planning cycle is required. Use `phase: FINISHED` only when all milestones are done and accepted.

If an acceptance command fails during review, use `record_error` instead of `set_phase`.

### Procedure

1. Re-read `.mary-workflow/state.yaml`.
2. Read the current milestone's deliverables and acceptance commands.
3. Inspect `git diff --stat`; if it touches files outside deliverables, reject the milestone.
4. Run or verify acceptance commands when practical.
5. Apply exactly one legal action.
6. If `set_phase` moves to `EXECUTING`, continue `/mw-run` automatic execution for the next milestone unless a `gate: confirm` milestone requires user confirmation.

### Output

Lead with findings. Return and apply the action JSON. Include no `update_state` action in this phase.

