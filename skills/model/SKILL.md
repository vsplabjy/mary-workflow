---
name: mw-model
description: Configure and switch the Codex model provider between the existing VSP provider and DeepSeek Responses API.
---

# Mary Workflow: Model Provider

Use this skill for `/mw-model`.

Run the repository helper from the installed Mary Workflow path:

```bash
python ~/.codex/skills/mary-workflow/scripts/mw_model.py status
```

Supported operations:

- `/mw-model configure`: read the existing OpenCode DeepSeek provider, add or update `[model_providers.deepseek]` in `~/.codex/config.toml`, write `~/.codex/models.json`, and preserve the current default provider.
- `/mw-model use deepseek`: select `deepseek-v4-flash` through the DeepSeek Responses API.
- `/mw-model use vsp`: restore the top-level model settings captured before DeepSeek was enabled.
- `/mw-model status`: show the active provider and model without exposing credentials.
- `/mw-model install-shell`: install the Fish function and completion explicitly.

DeepSeek's current Responses API only supports `deepseek-v4-flash`; do not select `deepseek-v4-pro` until the provider documentation confirms it is available.

The API key must remain outside the repository and must never be printed in user-facing output.
