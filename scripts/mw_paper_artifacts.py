#!/usr/bin/env python3
"""Stable paths for generated, machine-oriented paper artifacts."""

from __future__ import annotations

from pathlib import Path


ARTIFACTS_DIR = "artifacts"
RAW_SOURCE_HTML = f"{ARTIFACTS_DIR}/source.html"
RAW_SOURCE_PDF = f"{ARTIFACTS_DIR}/source.pdf"
NORMALIZED_SOURCE_FILE = f"{ARTIFACTS_DIR}/source.md"
PARSE_QUALITY_FILE = f"{ARTIFACTS_DIR}/parse-quality.json"
READ_CONTEXT_FILE = f"{ARTIFACTS_DIR}/read-context.json"
SOURCE_MANIFEST_FILE = f"{ARTIFACTS_DIR}/source-manifest.json"
READING_CONTEXT_FILE = f"{ARTIFACTS_DIR}/reading-context.json"
SOURCE_LOCATOR_FILE = f"{ARTIFACTS_DIR}/source-locators.json"
SUMMARY_CONTEXT_FILE = f"{ARTIFACTS_DIR}/summary-context.json"
SUMMARY_LEDGER_FILE = f"{ARTIFACTS_DIR}/summary-ledger.json"
SLIDES_CONTEXT_FILE = f"{ARTIFACTS_DIR}/slides-context.json"
QUIZ_CONTEXT_FILE = f"{ARTIFACTS_DIR}/quiz-context.json"
QUIZ_HEAD_FILE = f"{ARTIFACTS_DIR}/quiz-head.json"
NOTION_CONTEXT_FILE = f"{ARTIFACTS_DIR}/notion-context.json"


def artifact_path(workspace: Path, relative_path: str, *, create_parent: bool = False) -> Path:
    """Return a generated-artifact path relative to one paper workspace."""
    path = Path(workspace) / relative_path
    if create_parent:
        path.parent.mkdir(parents=True, exist_ok=True)
    return path


def resolve_artifact_path(workspace: Path, relative_path: str) -> Path:
    """Resolve a v2.3 artifact, accepting legacy root files for old workspaces."""
    modern = artifact_path(workspace, relative_path)
    if modern.is_file():
        return modern
    legacy = Path(workspace) / Path(relative_path).name
    return legacy if legacy.is_file() else modern


def raw_source_file(source_format: str) -> str:
    if source_format == "html":
        return RAW_SOURCE_HTML
    if source_format == "pdf":
        return RAW_SOURCE_PDF
    raise ValueError(f"Unsupported source format: {source_format}")
