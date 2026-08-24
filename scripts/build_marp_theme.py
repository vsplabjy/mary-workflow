#!/usr/bin/env python3
"""Build the directory-independent Mary Marp theme from local assets."""

from __future__ import annotations

import argparse
import base64
from pathlib import Path
import re


REPO_ROOT = Path(__file__).resolve().parents[1]
THEME_ROOT = REPO_ROOT / "assets" / "marp" / "themes"
SOURCE_PATH = THEME_ROOT / "mary-shanghaitech-red.source.css"
OUTPUT_PATH = THEME_ROOT / "mary-shanghaitech-red.css"
URL_PATTERN = re.compile(r"url\(\s*(['\"]?)(.*?)\1\s*\)", flags=re.IGNORECASE)
MIME_TYPES = {
    ".otf": "font/otf",
    ".png": "image/png",
    ".woff": "font/woff",
    ".woff2": "font/woff2",
}


class MarpThemeBuildError(ValueError):
    """The source theme cannot be compiled into a self-contained theme."""


def build_theme() -> tuple[str, int]:
    source = SOURCE_PATH.read_text(encoding="utf-8")
    embedded_count = 0

    def embed(match: re.Match[str]) -> str:
        nonlocal embedded_count
        value = match.group(2).strip()
        if value.startswith("data:"):
            return match.group(0)
        if value.startswith(("#", "http://", "https://", "//")):
            raise MarpThemeBuildError(f"Theme source URL is not a local asset: {value}")

        asset = (SOURCE_PATH.parent / value).resolve()
        try:
            asset.relative_to((REPO_ROOT / "assets" / "marp").resolve())
        except ValueError as exc:
            raise MarpThemeBuildError(f"Theme source URL escapes assets/marp: {value}") from exc
        if not asset.is_file():
            raise MarpThemeBuildError(f"Theme source asset does not exist: {value}")

        mime_type = MIME_TYPES.get(asset.suffix.lower())
        if mime_type is None:
            raise MarpThemeBuildError(f"Unsupported Marp asset type: {asset.suffix}")
        payload = base64.b64encode(asset.read_bytes()).decode("ascii")
        embedded_count += 1
        return f'url("data:{mime_type};base64,{payload}")'

    compiled = URL_PATTERN.sub(embed, source)
    if not compiled.endswith("\n"):
        compiled += "\n"
    return compiled, embedded_count


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="Fail if the checked-in compiled theme differs from deterministic output.",
    )
    args = parser.parse_args()

    compiled, embedded_count = build_theme()
    if args.check:
        current = OUTPUT_PATH.read_text(encoding="utf-8") if OUTPUT_PATH.is_file() else None
        if current != compiled:
            raise SystemExit("Compiled Marp theme is stale; run scripts/build_marp_theme.py.")
    else:
        OUTPUT_PATH.write_text(compiled, encoding="utf-8")
    print(f"embedded_urls={embedded_count}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
