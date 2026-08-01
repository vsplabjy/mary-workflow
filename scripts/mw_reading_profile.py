#!/usr/bin/env python3
"""Shared defaults for the learner-facing paper-reading profile."""

from __future__ import annotations

from pathlib import Path

from mw_runtime import atomic_write_text


READING_PROFILE_RELATIVE = ".mary-research/reading-profile.md"
DEFAULT_READING_PROFILE_PATH = Path(__file__).resolve().parents[1] / "defaults" / "reading-profile.md"


def default_reading_profile() -> str:
    try:
        text = DEFAULT_READING_PROFILE_PATH.read_text(encoding="utf-8")
    except OSError as exc:
        raise RuntimeError(f"Could not read the default reading profile: {exc}") from exc
    if "<!-- mary-reading-profile:v1 -->" not in text:
        raise RuntimeError("The default reading profile is missing its mary-reading-profile:v1 marker.")
    return text


def reading_profile_path(project_root: Path) -> Path:
    return Path(project_root).resolve() / READING_PROFILE_RELATIVE


def ensure_reading_profile(project_root: Path) -> tuple[Path, bool]:
    path = reading_profile_path(project_root)
    if path.exists():
        return path, False
    path.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_text(path, default_reading_profile())
    return path, True
