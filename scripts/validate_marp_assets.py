#!/usr/bin/env python3
"""Validate the localized Mary Marp theme and its offline asset closure."""

from __future__ import annotations

import json
from pathlib import Path
import re


REPO_ROOT = Path(__file__).resolve().parents[1]
ASSET_ROOT = REPO_ROOT / "assets" / "marp"
THEME_PATH = ASSET_ROOT / "themes" / "mary-shanghaitech-red.css"
THEME_SOURCE_PATH = ASSET_ROOT / "themes" / "mary-shanghaitech-red.source.css"
CONFIG_PATH = ASSET_ROOT / "marp.config.mjs"
ENGINE_PATH = ASSET_ROOT / "marp-engine.cjs"
PREVIEW_PATH = ASSET_ROOT / "templates" / "offline-preview.md"
VSCODE_SETTINGS_PATH = REPO_ROOT / ".vscode" / "settings.json"
PROVENANCE = "/* vendored from VSPlab/vsp-marp @ d3ac970, localized 2026-07 */"
URL_PATTERN = re.compile(r"url\(\s*(['\"]?)(.*?)\1\s*\)", flags=re.IGNORECASE)


class MarpAssetError(ValueError):
    """The P4 asset tree violates its offline contract."""


def require_file(path: Path, *, minimum_size: int = 1) -> None:
    if not path.is_file():
        raise MarpAssetError(f"Missing Marp asset: {path.relative_to(REPO_ROOT)}")
    if path.stat().st_size < minimum_size:
        raise MarpAssetError(f"Marp asset is unexpectedly small: {path.relative_to(REPO_ROOT)}")


def validate_marp_assets() -> dict[str, object]:
    for path in (
        THEME_PATH,
        THEME_SOURCE_PATH,
        CONFIG_PATH,
        ENGINE_PATH,
        PREVIEW_PATH,
        VSCODE_SETTINGS_PATH,
    ):
        require_file(path)

    css = THEME_PATH.read_text(encoding="utf-8")
    lines = css.splitlines()
    if not lines or lines[0] != "/* @theme mary-shanghaitech-red */":
        raise MarpAssetError("The localized CSS must declare the mary-shanghaitech-red theme.")
    if len(lines) < 2 or lines[1] != PROVENANCE:
        raise MarpAssetError("The localized CSS must retain the pinned VSP-Marp provenance comment.")
    embedded_urls: list[str] = []
    for match in URL_PATTERN.finditer(css):
        value = match.group(2).strip()
        if not value.startswith("data:"):
            raise MarpAssetError(f"Compiled theme URL is not self-contained: {value[:80]}")
        embedded_urls.append(value)

    source_css = THEME_SOURCE_PATH.read_text(encoding="utf-8")
    source_lines = source_css.splitlines()
    if source_lines[:2] != lines[:2]:
        raise MarpAssetError("Source and compiled themes must retain the same identity and provenance.")
    resolved_urls: list[str] = []
    for match in URL_PATTERN.finditer(source_css):
        value = match.group(2).strip()
        if value.startswith(("data:", "#")):
            raise MarpAssetError(f"Theme source must keep a relative asset URL: {value[:80]}")
        if value.startswith(("http://", "https://", "//")):
            raise MarpAssetError(f"Theme source contains a remote URL: {value}")
        target = (THEME_PATH.parent / value).resolve()
        try:
            target.relative_to(ASSET_ROOT.resolve())
        except ValueError as exc:
            raise MarpAssetError(f"Theme URL escapes assets/marp: {value}") from exc
        require_file(target)
        resolved_urls.append(value)

    katex_fonts = sorted((ASSET_ROOT / "fonts" / "katex").glob("*.woff2"))
    if len(katex_fonts) != 20:
        raise MarpAssetError(f"Expected 20 KaTeX WOFF2 files, found {len(katex_fonts)}.")
    for font in katex_fonts:
        require_file(font, minimum_size=3000)

    noto_fonts = sorted((ASSET_ROOT / "fonts" / "noto-cjk-sc").glob("*.woff2"))
    if [path.name for path in noto_fonts] != [
        "NotoSansCJKsc-Bold.woff2",
        "NotoSansCJKsc-Regular.woff2",
    ]:
        raise MarpAssetError("The complete Noto CJK SC regular/bold pair is required.")
    for font in noto_fonts:
        require_file(font, minimum_size=10_000_000)

    config = CONFIG_PATH.read_text(encoding="utf-8")
    if "allowLocalFiles: true" not in config or "mary-shanghaitech-red.css" not in config:
        raise MarpAssetError("Marp config must register local files and the localized theme.")
    engine = ENGINE_PATH.read_text(encoding="utf-8")
    if 'katexFontPath: "../fonts/katex/"' not in engine:
        raise MarpAssetError("Marp engine must route KaTeX to the local font directory.")

    vscode_settings = json.loads(VSCODE_SETTINGS_PATH.read_text(encoding="utf-8"))
    expected_theme = "./assets/marp/themes/mary-shanghaitech-red.css"
    if vscode_settings.get("markdown.marp.themes") != [expected_theme]:
        raise MarpAssetError("VS Code must register exactly the localized Mary Marp theme.")
    if vscode_settings.get("markdown.marp.html") != "all":
        raise MarpAssetError("VS Code must allow the template HTML used by VSP-Marp layouts.")
    if vscode_settings.get("markdown.marp.mathTypesetting") != "katex":
        raise MarpAssetError("VS Code must use KaTeX for the offline preview.")
    registered_theme = (REPO_ROOT / expected_theme).resolve()
    try:
        registered_theme.relative_to(REPO_ROOT.resolve())
    except ValueError as exc:
        raise MarpAssetError("VS Code theme registration escapes the workspace.") from exc
    if registered_theme != THEME_PATH.resolve():
        raise MarpAssetError("VS Code theme registration does not resolve to the compiled theme.")
    preview = PREVIEW_PATH.read_text(encoding="utf-8")
    required_preview_tokens = (
        "theme: mary-shanghaitech-red",
        "math: katex",
        "上海科技大学科研组会",
        "\\mathcal{L}",
        "_class: cover_e",
        "_class: toc_b",
    )
    missing_tokens = [token for token in required_preview_tokens if token not in preview]
    if missing_tokens:
        raise MarpAssetError(f"Offline preview is missing required tokens: {missing_tokens}")

    return {
        "theme": str(THEME_PATH.relative_to(REPO_ROOT)),
        "resolved_local_urls": len(resolved_urls),
        "embedded_urls": len(embedded_urls),
        "katex_fonts": len(katex_fonts),
        "noto_fonts": len(noto_fonts),
        "remote_urls": 0,
    }


def main() -> int:
    print(json.dumps(validate_marp_assets(), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
