#!/usr/bin/env python3
"""Deterministic source-locator indexing for Mary paper artifacts."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
from typing import Any

from mw_paper_sources import SOURCE_FORMATS, sha256_file, valid_locator
from mw_runtime import atomic_write_text


SOURCE_LOCATOR_SCHEMA = 1
SOURCE_LOCATOR_FILE = "source-locators.json"
LOCATOR_MARKER = re.compile(r"^\s*<!-- locator: ([^ ]+) -->\s*$")

JsonObject = dict[str, Any]
LocatorBlocks = dict[str, list[JsonObject]]


class SourceLocatorError(ValueError):
    """A source locator could not be indexed or resolved."""


def normalize_span_text(value: str) -> str:
    return " ".join(value.split())


def parse_source_locator_blocks(source_path: Path, source_format: str) -> LocatorBlocks:
    if source_format not in SOURCE_FORMATS:
        raise SourceLocatorError("source format must be html or pdf.")
    path = Path(source_path)
    if not path.is_file():
        raise SourceLocatorError(f"Normalized source is missing: {path}")
    lines = path.read_text(encoding="utf-8").splitlines()
    markers: list[tuple[int, str]] = []
    for line_index, line in enumerate(lines):
        match = LOCATOR_MARKER.fullmatch(line)
        if match is None:
            continue
        locator = match.group(1)
        if not valid_locator(locator, source_format):
            raise SourceLocatorError(f"Invalid {source_format} locator marker: {locator}.")
        markers.append((line_index, locator))
    if not markers:
        raise SourceLocatorError("source.md contains no resolvable locator markers.")

    blocks: LocatorBlocks = {}
    for marker_index, (line_index, locator) in enumerate(markers):
        next_line = markers[marker_index + 1][0] if marker_index + 1 < len(markers) else len(lines)
        content = normalize_span_text("\n".join(lines[line_index + 1 : next_line]))
        if not content:
            raise SourceLocatorError(f"Source locator {locator} resolves to an empty span.")
        blocks.setdefault(locator, []).append(
            {
                "line_start": line_index + 2,
                "line_end": next_line,
                "content": content,
            }
        )
    return blocks


def build_source_locator_index(
    workspace: Path,
    *,
    paper_id: str,
    source_format: str,
    source_fingerprint: str,
) -> tuple[JsonObject, LocatorBlocks]:
    source_path = Path(workspace) / "source.md"
    blocks = parse_source_locator_blocks(source_path, source_format)
    index = {
        "source_locator_schema": SOURCE_LOCATOR_SCHEMA,
        "paper_id": paper_id,
        "source": {
            "artifact": "source.md",
            "artifact_fingerprint": sha256_file(source_path),
            "format": source_format,
            "source_fingerprint": source_fingerprint,
        },
        "locators": {
            locator: [
                {
                    "line_start": span["line_start"],
                    "line_end": span["line_end"],
                    "content_fingerprint": hashlib.sha256(span["content"].encode("utf-8")).hexdigest(),
                    "preview": span["content"][:240],
                }
                for span in spans
            ]
            for locator, spans in sorted(blocks.items())
        },
    }
    return index, blocks


def write_source_locator_index(
    workspace: Path,
    *,
    paper_id: str,
    source_format: str,
    source_fingerprint: str,
) -> tuple[JsonObject, LocatorBlocks, str]:
    index, blocks = build_source_locator_index(
        workspace,
        paper_id=paper_id,
        source_format=source_format,
        source_fingerprint=source_fingerprint,
    )
    index_path = Path(workspace) / SOURCE_LOCATOR_FILE
    atomic_write_text(index_path, json.dumps(index, ensure_ascii=False, indent=2) + "\n")
    return index, blocks, sha256_file(index_path)


def validate_source_locator_index(
    workspace: Path,
    *,
    paper_id: str,
    source_format: str,
    source_fingerprint: str,
) -> tuple[JsonObject, LocatorBlocks, str]:
    index_path = Path(workspace) / SOURCE_LOCATOR_FILE
    if not index_path.is_file():
        raise SourceLocatorError(f"{SOURCE_LOCATOR_FILE} is missing; run prepare-summary first.")
    try:
        stored = json.loads(index_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise SourceLocatorError(f"{SOURCE_LOCATOR_FILE} is invalid: {exc}") from exc
    expected, blocks = build_source_locator_index(
        workspace,
        paper_id=paper_id,
        source_format=source_format,
        source_fingerprint=source_fingerprint,
    )
    if stored != expected:
        raise SourceLocatorError(f"{SOURCE_LOCATOR_FILE} is stale or does not match source.md.")
    return stored, blocks, sha256_file(index_path)


def require_resolvable_locators(
    value: object,
    *,
    field: str,
    source_format: str,
    blocks: LocatorBlocks,
) -> list[str]:
    if not isinstance(value, list) or not value:
        raise SourceLocatorError(f"{field} must be a non-empty locator array.")
    locators: list[str] = []
    for item in value:
        locator = " ".join(str(item or "").split())
        if not valid_locator(locator, source_format):
            raise SourceLocatorError(f"{field} contains invalid {source_format} locator: {locator or '(empty)'}.")
        if locator not in blocks:
            raise SourceLocatorError(f"{field} locator does not resolve in source.md: {locator}.")
        if locator in locators:
            raise SourceLocatorError(f"{field} contains duplicate locator: {locator}.")
        locators.append(locator)
    return locators


def evidence_resolves(evidence: str, locators: list[str], blocks: LocatorBlocks) -> bool:
    needle = normalize_span_text(evidence)
    return any(needle in span["content"] for locator in locators for span in blocks[locator])


def collect_paper_notes_locators(ledger: JsonObject) -> list[str]:
    collected: list[str] = []

    def add(value: object) -> None:
        if isinstance(value, list):
            for locator in value:
                text = str(locator or "").strip()
                if text and text not in collected:
                    collected.append(text)

    research = ledger.get("research", {})
    if isinstance(research, dict):
        for name, claim in research.items():
            claims = claim if name == "contributions" and isinstance(claim, list) else [claim]
            for item in claims:
                if isinstance(item, dict):
                    add(item.get("locators"))
    for field in ("section_ledger", "uncertainties"):
        entries = ledger.get(field, [])
        if isinstance(entries, list):
            for entry in entries:
                if isinstance(entry, dict):
                    add(entry.get("locators"))
    return collected
