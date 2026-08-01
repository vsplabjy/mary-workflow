#!/usr/bin/env python3
"""Shared defaults for the learner-facing paper-reading profile."""

from __future__ import annotations

from pathlib import Path

from mw_runtime import atomic_write_text


READING_PROFILE_RELATIVE = ".mary-research/reading-profile.md"

DEFAULT_READING_PROFILE = """# Paper Reading Profile

<!-- mary-reading-profile:v1 -->

This file is intentionally short and editable. It controls the learner-facing
paper reading pass; it does not change source evidence or scientific claims.

## Learner baseline

- Level: undergraduate student at ShanghaiTech University.
- Can follow standard calculus, linear algebra, programming, and introductory
  machine learning / computer-vision notation.
- Do not assume research-level background in a paper's specialist domain.
- Use the existing Notion study style as a reference: keep the author's main
  line in the foreground, and put personal extensions or tangents in a separate
  parking area.

## Language and explanation

- Keep the main prose in English.
- Keep professional terms, method names, model names, variables, citations, and
  measured values in their original English form.
- Add a concise Chinese translation in parentheses at first useful use when a
  term, method, or sentence is likely to block an English-learning reader.
- Add a short explanation of why a method is needed, what information flows
  through it, and what trade-off it introduces. Do not expand every familiar
  sentence.
- Do not translate equations, identifiers, citations, or proper names.

## Evidence and uncertainty

- Separate what the paper states from interpretation, intuition, and extension.
- Preserve exact numbers, baselines, figure/table references, and limitations.
- When a point is genuinely hard to understand or cannot be grounded from the
  available source, leave an empty `Open question` area for the learner to fill.
- Do not invent missing derivations, experiment results, or background facts.

## Current session

- Paper / goal: 
- Prerequisites to explain: 
- Terms that need translation: 
- Extensions to defer: 
"""


def reading_profile_path(project_root: Path) -> Path:
    return Path(project_root).resolve() / READING_PROFILE_RELATIVE


def ensure_reading_profile(project_root: Path) -> tuple[Path, bool]:
    path = reading_profile_path(project_root)
    if path.exists():
        return path, False
    path.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_text(path, DEFAULT_READING_PROFILE)
    return path, True

