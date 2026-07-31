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
