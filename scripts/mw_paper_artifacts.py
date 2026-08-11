#!/usr/bin/env python3
"""Stable paths and migration helpers for paper artifacts."""

from __future__ import annotations

import hashlib
from pathlib import Path
import shutil


class ArtifactLayoutError(ValueError):
    """A paper workspace contains conflicting or unsafe artifact files."""


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
LEGACY_ROOT_JSON_EXCEPTIONS = {"state.json"}


def _artifact_filenames() -> set[str]:
    """Return every source/JSON filename owned by the paper pipeline."""
    values = globals()
    return {
        str(value).split("/", 1)[1]
        for name, value in values.items()
        if name.endswith("_FILE") and isinstance(value, str) and value.startswith(f"{ARTIFACTS_DIR}/")
    } | {"source.html", "source.pdf", "source.md"}


def artifact_path(workspace: Path, relative_path: str, *, create_parent: bool = False) -> Path:
    """Return a generated-artifact path relative to one paper workspace."""
    path = Path(workspace) / relative_path
    if create_parent:
        path.parent.mkdir(parents=True, exist_ok=True)
    return path


def resolve_artifact_path(workspace: Path, relative_path: str) -> Path:
    """Resolve an artifact strictly under ``artifacts/``."""
    return artifact_path(workspace, relative_path)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def migrate_legacy_artifacts(workspace: Path) -> list[str]:
    """Move legacy root source/JSON artifacts into ``artifacts/`` safely.

    ``state.json`` remains at the workspace root because it is the paper state,
    not a generated source sidecar. Existing identical modern copies are
    deduplicated; conflicting copies fail instead of silently overwriting data.
    """
    directory = Path(workspace)
    artifacts = directory / ARTIFACTS_DIR
    artifacts.mkdir(parents=True, exist_ok=True)
    moved: list[str] = []
    managed = _artifact_filenames()
    candidates = {
        path
        for path in directory.iterdir()
        if path.is_file()
        and (
            path.name in managed
            or (path.suffix == ".json" and path.name not in LEGACY_ROOT_JSON_EXCEPTIONS)
        )
    }
    for legacy in sorted(candidates, key=lambda item: item.name):
        target = artifacts / legacy.name
        if target.exists():
            if not target.is_file() or _sha256(target) != _sha256(legacy):
                raise ArtifactLayoutError(
                    f"Conflicting artifact copies: {legacy} and {target}. "
                    "Resolve the files manually before retrying migration."
                )
            legacy.unlink()
            moved.append(f"removed duplicate {legacy.name}")
            continue
        shutil.copy2(legacy, target)
        if _sha256(target) != _sha256(legacy):
            target.unlink(missing_ok=True)
            raise ArtifactLayoutError(f"Artifact migration verification failed: {legacy}")
        legacy.unlink()
        moved.append(f"moved {legacy.name} -> {ARTIFACTS_DIR}/{legacy.name}")
    return moved


def legacy_artifacts(workspace: Path) -> list[Path]:
    """List root-level source/JSON files that violate the current layout."""
    directory = Path(workspace)
    if not directory.is_dir():
        return []
    managed = _artifact_filenames()
    return sorted(
        path
        for path in directory.iterdir()
        if path.is_file()
        and (
            path.name in managed
            or (path.suffix == ".json" and path.name not in LEGACY_ROOT_JSON_EXCEPTIONS)
        )
    )


def raw_source_file(source_format: str) -> str:
    if source_format == "html":
        return RAW_SOURCE_HTML
    if source_format == "pdf":
        return RAW_SOURCE_PDF
    raise ValueError(f"Unsupported source format: {source_format}")
