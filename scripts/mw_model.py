#!/usr/bin/env python3
"""Switch Codex between the configured VSP and DeepSeek providers.

The command keeps provider sections intact, stores the original top-level model
settings once, and writes only the fields required by DeepSeek's Codex guide.
It intentionally never prints or stores the API key in the repository.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import tempfile
from typing import Any


DEEPSEEK_MODEL = "deepseek-v4-flash"
DEEPSEEK_PROVIDER = "deepseek"
DEEPSEEK_BASE_URL = "https://api.deepseek.com/"
MANAGED_TOP_LEVEL_KEYS = {
    "model",
    "model_provider",
    "preferred_auth_method",
    "forced_login_method",
    "model_reasoning_effort",
    "model_catalog_json",
}
DEEPSEEK_CONFLICT_KEYS = {
    "model_context_window",
    "model_auto_compact_token_limit",
    "model_auto_compact_token_limit_scope",
    "base_instructions",
    "model_instructions_file",
    "compact_prompt",
    "experimental_compact_prompt_file",
    "service_tier",
    "model_verbosity",
    "model_reasoning_summary",
    "plan_mode_reasoning_effort",
    "experimental_use_unified_exec_tool",
}
STATE_FILENAME = "mary-workflow-model.json"


def codex_home() -> Path:
    return Path(os.environ.get("CODEX_HOME", str(Path.home() / ".codex"))).expanduser()


def config_path() -> Path:
    return codex_home() / "config.toml"


def models_path() -> Path:
    return codex_home() / "models.json"


def state_path() -> Path:
    return codex_home() / STATE_FILENAME


def _strip_jsonc_comments(text: str) -> str:
    result: list[str] = []
    index = 0
    in_string = False
    escaped = False
    while index < len(text):
        char = text[index]
        if in_string:
            result.append(char)
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            index += 1
            continue
        if char == '"':
            in_string = True
            result.append(char)
            index += 1
        elif text[index : index + 2] == "//":
            newline = text.find("\n", index)
            if newline == -1:
                break
            result.append("\n")
            index = newline + 1
        elif text[index : index + 2] == "/*":
            end = text.find("*/", index + 2)
            if end == -1:
                raise ValueError("Unterminated JSONC block comment")
            index = end + 2
        else:
            result.append(char)
            index += 1
    return "".join(result)


def read_deepseek_api_key(opencode_path: Path | None = None) -> str:
    configured_path = opencode_path or (
        Path(os.environ.get("XDG_CONFIG_HOME", str(Path.home() / ".config")))
        / "opencode"
        / "opencode.jsonc"
    )
    if configured_path.exists():
        payload = json.loads(_strip_jsonc_comments(configured_path.read_text(encoding="utf-8")))
        provider = payload.get("provider", {}).get(DEEPSEEK_PROVIDER, {})
        key = provider.get("options", {}).get("apiKey")
        if isinstance(key, str) and key.strip():
            return key.strip()
    key = os.environ.get("DEEPSEEK_API_KEY", "").strip()
    if key:
        return key
    raise SystemExit(
        f"没有找到 DeepSeek API key。请检查 {configured_path}，或设置 DEEPSEEK_API_KEY。"
    )


def _top_level_key(line: str) -> str | None:
    stripped = line.strip()
    if not stripped or stripped.startswith("#") or stripped.startswith("[") or "=" not in stripped:
        return None
    return stripped.split("=", 1)[0].strip().strip('"').strip("'")


def _leading_assignments(lines: list[str]) -> dict[str, str]:
    values: dict[str, str] = {}
    for line in lines:
        if line.lstrip().startswith("["):
            break
        key = _top_level_key(line)
        if key:
            values[key] = line.split("=", 1)[1].strip()
    return values


def _toml_string(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)


def _replace_config(
    path: Path,
    assignments: dict[str, str],
    remove_top_level_keys: set[str],
    provider_block: list[str] | None = None,
) -> None:
    original = path.read_text(encoding="utf-8") if path.exists() else ""
    lines = original.splitlines()
    first_section = next((index for index, line in enumerate(lines) if line.lstrip().startswith("[")), len(lines))
    leading: list[str] = []
    for line in lines[:first_section]:
        key = _top_level_key(line)
        if key in remove_top_level_keys:
            continue
        leading.append(line)
    while leading and not leading[-1].strip():
        leading.pop()
    prefix = [f"{key} = {value}" for key, value in assignments.items()]
    new_lines = prefix + ([""] if prefix and leading else []) + leading

    index = first_section
    current_section: str | None = None
    provider_inserted = False
    while index < len(lines):
        line = lines[index]
        stripped = line.strip()
        if stripped.startswith("["):
            if (
                provider_block
                and current_section == "[model_providers.vsp_lab_api]"
                and not provider_inserted
            ):
                while new_lines and not new_lines[-1].strip():
                    new_lines.pop()
                new_lines.extend(["", *provider_block, ""])
                provider_inserted = True
            if stripped == "[model_providers.deepseek]":
                index += 1
                while index < len(lines) and not lines[index].lstrip().startswith("["):
                    index += 1
                current_section = None
                while new_lines and not new_lines[-1].strip():
                    new_lines.pop()
                continue
            current_section = stripped
        new_lines.append(line)
        index += 1

    while new_lines and not new_lines[-1].strip():
        new_lines.pop()
    if provider_block and not provider_inserted:
        new_lines.extend(["", *provider_block])
    text = "\n".join(new_lines) + "\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    mode = path.stat().st_mode if path.exists() else 0o600
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False) as handle:
        temporary = Path(handle.name)
        handle.write(text)
        handle.flush()
        os.fsync(handle.fileno())
    os.chmod(temporary, mode)
    os.replace(temporary, path)


def _write_json_atomic(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False) as handle:
        temporary = Path(handle.name)
        json.dump(payload, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    os.chmod(temporary, 0o600)
    os.replace(temporary, path)


def _model_entry(slug: str, display_name: str, description: str, priority: int) -> dict[str, Any]:
    return {
        "slug": slug,
        "prefer_websockets": False,
        "support_verbosity": True,
        "default_verbosity": "low",
        "apply_patch_tool_type": "freeform",
        "web_search_tool_type": "text",
        "input_modalities": ["text"],
        "supports_parallel_tool_calls": True,
        "tool_mode": None,
        "multi_agent_version": "v2",
        "use_responses_lite": False,
        "include_skills_usage_instructions": False,
        "auto_review_model_override": None,
        "context_window": 1048576,
        "max_context_window": 1048576,
        "effective_context_window_percent": 95,
        "auto_compact_token_limit": None,
        "reasoning_summary_format": "experimental",
        "default_reasoning_summary": "none",
        "display_name": display_name,
        "description": description,
        "default_reasoning_level": "high",
        "supported_reasoning_levels": [
            {"effort": "low", "description": "Fast responses with lighter reasoning"},
            {"effort": "high", "description": "Extra high reasoning depth for complex problems"},
            {"effort": "max", "description": "Maximum reasoning depth for the hardest problems"},
        ],
        "shell_type": "shell_command",
        "visibility": "list",
        "minimal_client_version": "0.144.0",
        "supported_in_api": True,
        "availability_nux": None,
        "upgrade": None,
        "priority": priority,
    }


def write_model_catalog(path: Path) -> None:
    payload: dict[str, Any] = {"models": []}
    if path.exists():
        try:
            loaded = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(loaded, dict) and isinstance(loaded.get("models"), list):
                payload = loaded
        except (OSError, json.JSONDecodeError):
            pass
    models = [item for item in payload["models"] if not str(item.get("slug", "")).startswith("deepseek-")]
    models.extend(
        [
            _model_entry(DEEPSEEK_MODEL, "DeepSeek-V4-Flash", "Latest frontier agentic coding model.", 1),
            _model_entry("deepseek-v4-pro", "DeepSeek-V4-Pro", "Most capable frontier agentic coding model.", 2),
        ]
    )
    payload["models"] = models
    _write_json_atomic(path, payload)


def _read_state(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _save_original_state(config: Path, state: Path) -> dict[str, Any]:
    existing = _read_state(state)
    if existing.get("original_top_level"):
        return existing
    lines = config.read_text(encoding="utf-8").splitlines() if config.exists() else []
    original = {key: value for key, value in _leading_assignments(lines).items() if key in MANAGED_TOP_LEVEL_KEYS or key in DEEPSEEK_CONFLICT_KEYS}
    payload = {"version": 1, "original_top_level": original}
    _write_json_atomic(state, payload)
    return payload


def _current_top_level(config: Path) -> dict[str, str]:
    lines = config.read_text(encoding="utf-8").splitlines() if config.exists() else []
    return _leading_assignments(lines)


def _deepseek_assignments() -> dict[str, str]:
    catalog = "~/.codex/models.json" if "CODEX_HOME" not in os.environ else str(models_path())
    return {
        "model": _toml_string(DEEPSEEK_MODEL),
        "model_provider": _toml_string(DEEPSEEK_PROVIDER),
        "preferred_auth_method": _toml_string("apikey"),
        "forced_login_method": _toml_string("api"),
        "model_reasoning_effort": _toml_string("high"),
        "model_catalog_json": _toml_string(catalog),
    }


def switch_deepseek(config: Path | None = None, state: Path | None = None, catalog: Path | None = None) -> None:
    target_config = config or config_path()
    target_state = state or state_path()
    target_catalog = catalog or models_path()
    api_key = read_deepseek_api_key()
    _save_original_state(target_config, target_state)
    write_model_catalog(target_catalog)
    _replace_config(
        target_config,
        _deepseek_assignments(),
        MANAGED_TOP_LEVEL_KEYS | DEEPSEEK_CONFLICT_KEYS,
        [
            "[model_providers.deepseek]",
            'name = "deepseek"',
            f'base_url = "{DEEPSEEK_BASE_URL}"',
            'wire_api = "responses"',
            f"experimental_bearer_token = {_toml_string(api_key)}",
        ],
    )
    print(f"已切换到 DeepSeek：{DEEPSEEK_MODEL}（API key 未输出）")


def configure_deepseek(config: Path | None = None, state: Path | None = None, catalog: Path | None = None) -> None:
    """Install/update the provider while keeping the current default model."""
    target_config = config or config_path()
    target_state = state or state_path()
    target_catalog = catalog or models_path()
    api_key = read_deepseek_api_key()
    _save_original_state(target_config, target_state)
    write_model_catalog(target_catalog)
    current = _current_top_level(target_config)
    assignment_order = (
        "model",
        "model_provider",
        "preferred_auth_method",
        "forced_login_method",
        "model_reasoning_effort",
        "model_catalog_json",
    )
    _replace_config(
        target_config,
        {key: current[key] for key in assignment_order if key in current},
        MANAGED_TOP_LEVEL_KEYS,
        [
            "[model_providers.deepseek]",
            'name = "deepseek"',
            f'base_url = "{DEEPSEEK_BASE_URL}"',
            'wire_api = "responses"',
            f"experimental_bearer_token = {_toml_string(api_key)}",
        ],
    )
    print("已在 Codex 中添加/更新 DeepSeek provider；当前默认模型保持不变。")


def switch_vsp(config: Path | None = None, state: Path | None = None) -> None:
    target_config = config or config_path()
    target_state = state or state_path()
    saved = _read_state(target_state)
    original = saved.get("original_top_level", {})
    current = _current_top_level(target_config)
    if not original:
        original = {
            "model": current.get("model", '"gpt-5.6-luna"'),
            "model_provider": current.get("model_provider", '"vsp_lab_api"'),
            "model_reasoning_effort": current.get("model_reasoning_effort", '"high"'),
        }
    assignments = {
        key: value
        for key, value in original.items()
        if key in MANAGED_TOP_LEVEL_KEYS or key in DEEPSEEK_CONFLICT_KEYS
    }
    assignments.setdefault("model_provider", '"vsp_lab_api"')
    assignments.setdefault("model", '"gpt-5.6-luna"')
    assignments.setdefault("model_reasoning_effort", '"high"')
    _replace_config(
        target_config,
        assignments,
        MANAGED_TOP_LEVEL_KEYS | DEEPSEEK_CONFLICT_KEYS,
        None,
    )
    print(f"已切换回 VSP：{assignments['model']}")


def status() -> None:
    current = _current_top_level(config_path())
    model = current.get("model", "(未设置)")
    provider = current.get("model_provider", "(未设置)")
    print(f"Codex 当前 provider: {provider}")
    print(f"Codex 当前 model: {model}")
    normalized_provider = provider.strip('"')
    normalized_model = model.strip('"')
    if normalized_provider == DEEPSEEK_PROVIDER and normalized_model not in {
        "deepseek-v4-flash",
        "deepseek-v4-pro",
    }:
        print("警告：DeepSeek provider 与当前 model 不匹配；请运行 mw-model use deepseek。")
    print(f"DeepSeek catalog: {'已安装' if models_path().exists() else '未安装'}")


def _fish_quote(value: str) -> str:
    return "'" + value.replace("'", "\\'") + "'"


def _write_if_changed(path: Path, content: str) -> bool:
    if path.exists() and path.read_text(encoding="utf-8") == content:
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return True


def _rc_block(path: Path, content: str, marker: str) -> bool:
    begin = f"# >>> {marker} >>>"
    end = f"# <<< {marker} <<<"
    existing = path.read_text(encoding="utf-8") if path.exists() else ""
    pattern = re.compile(rf"(?ms)^{re.escape(begin)}$.*?^{re.escape(end)}$\n?")
    block = f"{begin}\n{content.rstrip()}\n{end}\n"
    if pattern.search(existing):
        updated = pattern.sub(block, existing, count=1)
    else:
        separator = "" if not existing or existing.endswith("\n\n") else "\n"
        updated = existing + separator + block
    if updated == existing:
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(updated, encoding="utf-8")
    return True


def install_shell_integration(force: bool = False) -> str:
    shell = Path(os.environ.get("SHELL", "")).name
    config_root = Path(os.environ.get("XDG_CONFIG_HOME", str(Path.home() / ".config")))
    script = str(Path(__file__).resolve())
    if shell == "fish":
        if not shutil.which("fish"):
            return "检测到 Fish，但系统中没有找到 fish 可执行文件。"
        fish_root = config_root / "fish"
        function_path = fish_root / "functions" / "mw-model.fish"
        completion_path = fish_root / "completions" / "mw-model.fish"
        _write_if_changed(
            function_path,
            "function mw-model --description 'Switch Codex between VSP and DeepSeek'\n"
            f"    command python3 {_fish_quote(script)} $argv\n"
            "end\n",
        )
        _write_if_changed(
            completion_path,
            "complete -c mw-model -f -n '__fish_use_subcommand' -a 'status configure use install-shell'\n"
            "complete -c mw-model -f -n '__fish_seen_subcommand_from use' -a 'deepseek vsp'\n",
        )
        return f"已检测 shell=fish，并配置 mw-model 及补全：{function_path}"

    if shell == "bash":
        bashrc = Path.home() / ".bashrc"
        content = (
            "mw_model() { command python3 "
            f"{shlex.quote(script)} \"$@\"; }}\n"
            "alias mw-model=mw_model\n"
            "_mw_model_complete() {\n"
            "    local current=\"${COMP_WORDS[COMP_CWORD]}\"\n"
            "    if [[ ${COMP_CWORD} -eq 1 ]]; then\n"
            "        COMPREPLY=( $(compgen -W 'status configure use install-shell' -- \"$current\") )\n"
            "    elif [[ ${COMP_CWORD} -eq 2 && ${COMP_WORDS[1]} == use ]]; then\n"
            "        COMPREPLY=( $(compgen -W 'deepseek vsp' -- \"$current\") )\n"
            "    fi\n"
            "}\n"
            "complete -F _mw_model_complete mw-model"
        )
        _rc_block(bashrc, content, "mary-workflow mw-model")
        return f"已检测 shell=bash，并配置 mw-model：{bashrc}（新终端生效）"

    if shell == "zsh":
        zshrc = Path.home() / ".zshrc"
        content = (
            "mw_model() { command python3 "
            f"{shlex.quote(script)} \"$@\"; }}\n"
            "alias mw-model=mw_model\n"
            "_mw_model() {\n"
            "    if (( CURRENT == 2 )); then\n"
            "        compadd status configure use install-shell\n"
            "    elif [[ $words[2] == use ]]; then\n"
            "        compadd deepseek vsp\n"
            "    fi\n"
            "}\n"
            "(( $+functions[compdef] )) && compdef _mw_model mw-model"
        )
        _rc_block(zshrc, content, "mary-workflow mw-model")
        return f"已检测 shell=zsh，并配置 mw-model：{zshrc}（新终端生效）"

    if force and shutil.which("fish"):
        os.environ["SHELL"] = "fish"
        return install_shell_integration()
    return f"当前 shell={shell or '(unknown)'}，未写入 shell 配置；支持 fish、bash、zsh。"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Switch Codex between VSP and DeepSeek")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("status", help="show the active Codex provider and model").set_defaults(func=lambda _: status())
    subparsers.add_parser("configure", help="add or update DeepSeek without changing the default").set_defaults(
        func=lambda _: configure_deepseek()
    )
    use = subparsers.add_parser("use", help="select a provider")
    use.add_argument("provider", choices=("deepseek", "vsp"))
    use.set_defaults(func=lambda args: switch_deepseek() if args.provider == "deepseek" else switch_vsp())
    install = subparsers.add_parser("install-shell", help="install Fish function and completion")
    install.add_argument("--force", action="store_true")
    install.set_defaults(func=lambda args: print(install_shell_integration(force=args.force)))
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    args.func(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
