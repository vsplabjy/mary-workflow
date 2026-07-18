#!/usr/bin/env python3
"""Summary artifact contract and claim validation for Mary papers."""

from __future__ import annotations

import json
from pathlib import Path
import re
from typing import Any

from mw_paper_locators import (
    SOURCE_LOCATOR_FILE,
    SourceLocatorError,
    collect_paper_notes_locators,
    evidence_resolves,
    require_resolvable_locators,
    validate_source_locator_index,
    write_source_locator_index,
)
from mw_paper_sources import extract_notes_ledger, sha256_file
from mw_runtime import atomic_write_text


SUMMARY_SCHEMA = 1
SUMMARY_CONTEXT_SCHEMA = 1
SUMMARY_FILE = "summary.md"
SUMMARY_CONTEXT_FILE = "summary-context.json"
SUMMARY_SECTIONS = ("background", "method", "experiments")
CLAIM_PREFIXES = {"background": "B", "method": "M", "experiments": "E"}

JsonObject = dict[str, Any]


class PaperSummaryError(ValueError):
    """A summary input, claim, or artifact violated the P3 contract."""


def require_summary_string(value: object, field: str) -> str:
    text = " ".join(str(value or "").split())
    if not text:
        raise PaperSummaryError(f"{field} must be non-empty.")
    return text


def extract_summary_ledger(summary_text: str) -> JsonObject:
    marker = "<!-- mary-summary:v1 -->"
    marker_index = summary_text.find(marker)
    if marker_index < 0:
        raise PaperSummaryError(f"summary.md must contain {marker}.")
    fenced = re.search(r"```json\s*(\{.*?\})\s*```", summary_text[marker_index:], flags=re.DOTALL)
    if fenced is None:
        raise PaperSummaryError("summary.md must contain a fenced JSON ledger after the schema marker.")
    try:
        payload = json.loads(fenced.group(1))
    except json.JSONDecodeError as exc:
        raise PaperSummaryError(f"summary JSON ledger is invalid: {exc}") from exc
    if not isinstance(payload, dict):
        raise PaperSummaryError("summary JSON ledger must be an object.")
    return payload


def validate_notes_input(workspace: Path, paper_id: str, read_output_fingerprint: str) -> JsonObject:
    notes_path = Path(workspace) / "paper-notes.md"
    if not notes_path.is_file():
        raise PaperSummaryError("paper-notes.md is missing.")
    if sha256_file(notes_path) != read_output_fingerprint:
        raise PaperSummaryError("paper-notes.md fingerprint does not match the completed read stage.")
    ledger = extract_notes_ledger(notes_path.read_text(encoding="utf-8"))
    if ledger.get("paper_id") != paper_id:
        raise PaperSummaryError("paper-notes paper_id does not match the paper state.")
    return ledger


def build_summary_context(
    workspace: Path,
    *,
    paper_id: str,
    source_format: str,
    source_fingerprint: str,
    read_output_fingerprint: str,
    persist_locator_index: bool,
) -> tuple[JsonObject, dict[str, list[JsonObject]]]:
    directory = Path(workspace)
    notes_ledger = validate_notes_input(directory, paper_id, read_output_fingerprint)
    try:
        if persist_locator_index:
            index, blocks, index_fingerprint = write_source_locator_index(
                directory,
                paper_id=paper_id,
                source_format=source_format,
                source_fingerprint=source_fingerprint,
            )
        else:
            index, blocks, index_fingerprint = validate_source_locator_index(
                directory,
                paper_id=paper_id,
                source_format=source_format,
                source_fingerprint=source_fingerprint,
            )
        notes_locators = collect_paper_notes_locators(notes_ledger)
        allowed_locators = require_resolvable_locators(
            notes_locators,
            field="paper-notes locators",
            source_format=source_format,
            blocks=blocks,
        )
    except SourceLocatorError as exc:
        raise PaperSummaryError(str(exc)) from exc
    context = {
        "summary_context_schema": SUMMARY_CONTEXT_SCHEMA,
        "paper_id": paper_id,
        "inputs": {
            "paper_notes": {
                "artifact": "paper-notes.md",
                "fingerprint": read_output_fingerprint,
            },
            "source": index["source"],
            "source_locators": {
                "artifact": SOURCE_LOCATOR_FILE,
                "fingerprint": index_fingerprint,
                "schema": index["source_locator_schema"],
            },
        },
        "allowed_source_locators": sorted(allowed_locators),
    }
    return context, blocks


def write_summary_context(
    workspace: Path,
    *,
    paper_id: str,
    source_format: str,
    source_fingerprint: str,
    read_output_fingerprint: str,
) -> JsonObject:
    context, _ = build_summary_context(
        workspace,
        paper_id=paper_id,
        source_format=source_format,
        source_fingerprint=source_fingerprint,
        read_output_fingerprint=read_output_fingerprint,
        persist_locator_index=True,
    )
    atomic_write_text(
        Path(workspace) / SUMMARY_CONTEXT_FILE,
        json.dumps(context, ensure_ascii=False, indent=2) + "\n",
    )
    return context


def validate_summary_context(
    workspace: Path,
    *,
    paper_id: str,
    source_format: str,
    source_fingerprint: str,
    read_output_fingerprint: str,
) -> tuple[JsonObject, dict[str, list[JsonObject]], str]:
    context_path = Path(workspace) / SUMMARY_CONTEXT_FILE
    if not context_path.is_file():
        raise PaperSummaryError(f"{SUMMARY_CONTEXT_FILE} is missing; run prepare-summary first.")
    try:
        stored = json.loads(context_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise PaperSummaryError(f"{SUMMARY_CONTEXT_FILE} is invalid: {exc}") from exc
    expected, blocks = build_summary_context(
        workspace,
        paper_id=paper_id,
        source_format=source_format,
        source_fingerprint=source_fingerprint,
        read_output_fingerprint=read_output_fingerprint,
        persist_locator_index=False,
    )
    if stored != expected:
        raise PaperSummaryError(f"{SUMMARY_CONTEXT_FILE} is stale or does not match current inputs.")
    return stored, blocks, sha256_file(context_path)


def validate_claim(
    value: object,
    *,
    field: str,
    section: str,
    source_format: str,
    blocks: dict[str, list[JsonObject]],
    allowed_locators: set[str],
) -> tuple[str, list[str]]:
    if not isinstance(value, dict):
        raise PaperSummaryError(f"{field} must be a claim object.")
    expected_fields = {"claim_id", "claim_text", "evidence", "source_locators"}
    if set(value) != expected_fields:
        raise PaperSummaryError(f"{field} must contain exactly: {', '.join(sorted(expected_fields))}.")
    claim_id = require_summary_string(value.get("claim_id"), f"{field}.claim_id")
    prefix = CLAIM_PREFIXES[section]
    if not re.fullmatch(rf"{prefix}[0-9]{{2,}}", claim_id):
        raise PaperSummaryError(f"{field}.claim_id must match {prefix} followed by at least two digits.")
    claim_text = require_summary_string(value.get("claim_text"), f"{field}.claim_text")
    if len(claim_text) < 10:
        raise PaperSummaryError(f"{field}.claim_text must contain at least 10 characters.")
    evidence = require_summary_string(value.get("evidence"), f"{field}.evidence")
    if len(evidence) < 8 or len(evidence) > 500:
        raise PaperSummaryError(f"{field}.evidence must contain 8-500 characters.")
    try:
        locators = require_resolvable_locators(
            value.get("source_locators"),
            field=f"{field}.source_locators",
            source_format=source_format,
            blocks=blocks,
        )
    except SourceLocatorError as exc:
        raise PaperSummaryError(str(exc)) from exc
    outside_notes = [locator for locator in locators if locator not in allowed_locators]
    if outside_notes:
        raise PaperSummaryError(
            f"{field}.source_locators were not accepted by paper-notes.md: {', '.join(outside_notes)}."
        )
    if not evidence_resolves(evidence, locators, blocks):
        raise PaperSummaryError(f"{field}.evidence does not resolve under its cited source locators.")
    return claim_id, locators


def validate_summary(
    workspace: Path,
    *,
    paper_id: str,
    source_format: str,
    source_fingerprint: str,
    read_output_fingerprint: str,
) -> JsonObject:
    directory = Path(workspace)
    summary_path = directory / SUMMARY_FILE
    if not summary_path.is_file():
        raise PaperSummaryError("summary.md is missing.")
    context, blocks, context_fingerprint = validate_summary_context(
        directory,
        paper_id=paper_id,
        source_format=source_format,
        source_fingerprint=source_fingerprint,
        read_output_fingerprint=read_output_fingerprint,
    )
    ledger = extract_summary_ledger(summary_path.read_text(encoding="utf-8"))
    expected_top_level = {"summary_schema", "paper_id", "inputs", "sections"}
    if set(ledger) != expected_top_level:
        missing = sorted(expected_top_level - set(ledger))
        extra = sorted(set(ledger) - expected_top_level)
        raise PaperSummaryError(f"summary top-level fields mismatch; missing={missing}, extra={extra}.")
    if ledger.get("summary_schema") != SUMMARY_SCHEMA:
        raise PaperSummaryError(f"summary_schema must be {SUMMARY_SCHEMA}.")
    if ledger.get("paper_id") != paper_id:
        raise PaperSummaryError("summary paper_id does not match the paper state.")
    if ledger.get("inputs") != context["inputs"]:
        raise PaperSummaryError("summary inputs must exactly copy summary-context.json.")

    sections = ledger.get("sections")
    if not isinstance(sections, dict) or tuple(sections) != SUMMARY_SECTIONS:
        raise PaperSummaryError(f"summary sections must be ordered exactly: {', '.join(SUMMARY_SECTIONS)}.")
    allowed_locators = set(context["allowed_source_locators"])
    claim_ids: set[str] = set()
    section_counts: JsonObject = {}
    cited_locators: set[str] = set()
    for section in SUMMARY_SECTIONS:
        claims = sections.get(section)
        if not isinstance(claims, list) or not claims:
            raise PaperSummaryError(f"summary section {section} must be a non-empty claim array.")
        section_counts[section] = len(claims)
        for index, claim in enumerate(claims):
            claim_id, locators = validate_claim(
                claim,
                field=f"sections.{section}[{index}]",
                section=section,
                source_format=source_format,
                blocks=blocks,
                allowed_locators=allowed_locators,
            )
            if claim_id in claim_ids:
                raise PaperSummaryError(f"Duplicate summary claim_id: {claim_id}.")
            claim_ids.add(claim_id)
            cited_locators.update(locators)

    return {
        "summary_fingerprint": sha256_file(summary_path),
        "metadata": {
            "summary_schema": SUMMARY_SCHEMA,
            "claim_count": len(claim_ids),
            "section_claim_counts": section_counts,
            "cited_locator_count": len(cited_locators),
            "summary_context": SUMMARY_CONTEXT_FILE,
            "summary_context_fingerprint": context_fingerprint,
            "source_locators": SOURCE_LOCATOR_FILE,
            "source_locators_fingerprint": context["inputs"]["source_locators"]["fingerprint"],
        },
    }
