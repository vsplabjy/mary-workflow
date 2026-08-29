#!/usr/bin/env python3
"""Validate Mary's pinned, offline VSP-Beamer runtime bundle."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re


REPO_ROOT = Path(__file__).resolve().parents[1]
ASSET_ROOT = REPO_ROOT / "assets" / "beamer"
THEME_ROOT = ASSET_ROOT / "themes"
RUNTIME_FILES = (
    THEME_ROOT / "beamerthemeVSP.sty",
    THEME_ROOT / "beamerthememary-shanghaitech-red.sty",
    ASSET_ROOT / "assets" / "shanghaitech-master.png",
    ASSET_ROOT / "assets" / "ShanghaiTech_Logo_RGBA.png",
    ASSET_ROOT / "assets" / "ShanghaiTech_Name_RGBA.png",
    ASSET_ROOT / "LICENSE.vsp-beamer",
)
UPSTREAM_COMMIT = "e7bf4e5e5588ee10a386e6c79668e50f9b749124"


class BeamerAssetError(ValueError):
    """The localized Beamer runtime is missing or internally inconsistent."""


def bundle_fingerprint(files: tuple[Path, ...] = RUNTIME_FILES) -> str:
    digest = hashlib.sha256()
    for path in files:
        relative = path.relative_to(ASSET_ROOT).as_posix().encode("utf-8")
        digest.update(len(relative).to_bytes(4, "big"))
        digest.update(relative)
        payload = path.read_bytes()
        digest.update(len(payload).to_bytes(8, "big"))
        digest.update(payload)
    return digest.hexdigest()


def validate_beamer_assets() -> dict[str, object]:
    for path in RUNTIME_FILES:
        if not path.is_file():
            raise BeamerAssetError(f"Missing Beamer runtime asset: {path.relative_to(REPO_ROOT)}")
        if path.stat().st_size < 100:
            raise BeamerAssetError(
                f"Beamer runtime asset is unexpectedly small: {path.relative_to(REPO_ROOT)}"
            )

    shared = (THEME_ROOT / "beamerthemeVSP.sty").read_text(encoding="utf-8")
    entry = (THEME_ROOT / "beamerthememary-shanghaitech-red.sty").read_text(
        encoding="utf-8"
    )
    preview = (ASSET_ROOT / "templates" / "offline-preview.tex").read_text(
        encoding="utf-8"
    )
    if "VSP requires XeLaTeX" not in shared or "Noto CJK system fonts" not in shared:
        raise BeamerAssetError("Shared VSP-Beamer theme lost its XeLaTeX/Noto CJK contract.")
    if UPSTREAM_COMMIT not in entry:
        raise BeamerAssetError("Mary Beamer entry theme must retain the pinned upstream commit.")
    if "[red,report,nosectionpages,shtu]" not in entry or "\\MaryFigure" not in entry:
        raise BeamerAssetError("Mary Beamer entry theme is missing required options or Figure API.")
    if re.search(r"https?://|//[A-Za-z0-9]", shared + entry + preview):
        raise BeamerAssetError("Beamer runtime source must not contain remote dependencies.")
    required_preview = (
        "\\documentclass[aspectratio=169,10pt]{beamer}",
        "\\usetheme{mary-shanghaitech-red}",
        "\\VSPtitleframe",
        "\\begin{columns}",
        "\\VSPendframe",
    )
    missing = [token for token in required_preview if token not in preview]
    if missing:
        raise BeamerAssetError(f"Offline Beamer preview is missing required tokens: {missing}")
    return {
        "theme": "assets/beamer/themes/beamerthememary-shanghaitech-red.sty",
        "upstream_commit": UPSTREAM_COMMIT,
        "runtime_files": len(RUNTIME_FILES),
        "remote_dependencies": 0,
        "bundle_fingerprint": bundle_fingerprint(),
    }


if __name__ == "__main__":
    print(json.dumps(validate_beamer_assets(), ensure_ascii=False, indent=2))
