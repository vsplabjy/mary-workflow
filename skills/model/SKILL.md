---
name: mw-model
description: Configure and switch the Codex model provider between the existing VSP provider and DeepSeek Responses API.
---

# Mary Workflow: Model Provider

Use this skill for `/mw-model`.

Important: Codex reads `model` and `model_provider` when its app-server starts. This skill cannot hot-switch an already running session. After a terminal switch, start a new Codex session. After a switch for the VS Code sidebar, run `Developer: Reload Window` in VS Code; creating a new sidebar chat is not sufficient because the extension keeps one app-server process alive.

Run the repository helper from the installed Mary Workflow path:

```bash
python ~/.codex/skills/mary-workflow/scripts/mw_model.py status
```

Supported operations:

- `/mw-model configure`: add or update `[model_providers.deepseek]` in `~/.codex/config.toml`, write `~/.codex/models.json`, and preserve the current default provider. It never fills the API key automatically.
- `/mw-model use deepseek`: select `deepseek-v4-flash` through the DeepSeek Responses API with `model_reasoning_effort = "max"` by default, uncommenting the DeepSeek provider block and using its recorded key.
- `/mw-model use vsp`: restore the last-used VSP model and reasoning effort (recorded on every switch in `~/.codex/mary-workflow-model.json`), uncomment the VSP provider block, and comment the DeepSeek provider block. It does not fall back to a fixed model when a previous state exists.
- `/mw-model status`: show the active provider and model plus which VSP settings would be restored, without exposing credentials.
- `/mw-model install-shell`: detect the current shell and install the command plus completion explicitly.

On the first `/mw-init`, Mary Workflow detects `$SHELL` and installs the integration automatically. It is idempotent, so a later `/mw-init` repairs a missing integration without duplicating shell configuration. Fish uses autoloaded functions and completions; Bash and Zsh use a marked block in `~/.bashrc` or `~/.zshrc`.

Recommended terminal workflow:

```fish
mw-model use deepseek
codex
```

To return to VSP, exit the current Codex session first, then run `mw-model use vsp` and start `codex` again. For the VS Code sidebar, reload the VS Code window after the helper finishes. `$mary-workflow:mw-model` only invokes this skill; it is not itself a live model switch.

Per DeepSeek's official API docs (`api-docs.deepseek.com`), the Responses API exposes `deepseek-v4-flash` and `deepseek-v4-pro`. The `reasoning_effort` parameter accepts `low` / `high` / `max` (default `high`); for compatibility, `medium` and `xhigh` are mapped. `deepseek-v4-pro` currently maps `low` -> `high` and `xhigh` -> `max`, with full `low` / `high` / `max` support expected in early August 2026. The helper selects `deepseek-v4-flash` and, per user preference, sets the default effort to `max` (DeepSeek recommends `max` for complex agent workloads).

The helper records the settings actually in use before each switch in
`~/.codex/mary-workflow-model.json` (`last_vsp` / `last_deepseek`), so switching
back to VSP restores the model and reasoning effort used right before the last
DeepSeek switch instead of a hard-coded default model.

Run mw-model configure once to create the complete DeepSeek provider structure. Then manually add the key as a commented line inside the DeepSeek block: `# experimental_bearer_token = "sk-..."`. Provider sections remain in the file; the Python switcher comments the inactive provider section and preserves its key.

The API key must remain outside the repository and must never be printed in user-facing output.
