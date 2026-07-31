---
description: Configure or switch Codex between the existing VSP provider and DeepSeek Responses API.
argument-hint: [status|configure|use deepseek|use vsp|install-shell]
---

# /mw-model

Run the model provider helper:

```bash
python ~/.codex/skills/mary-workflow/scripts/mw_model.py $ARGUMENTS
```

Use `configure` first to migrate the DeepSeek provider from OpenCode while keeping VSP as the default. Use `use deepseek` or `use vsp` only when changing the default for future Codex sessions. Never print the API key.

Provider/model changes are read at Codex startup and do not affect the current session. For a reliable switch, run `mw-model use deepseek` or `mw-model use vsp` in Fish after exiting Codex, then start a new `codex` session.

The first `/mw-init` detects the current `$SHELL` and installs `mw-model` plus completion for Fish, Bash, or Zsh. Run `/mw-model install-shell` to repair the integration manually.
