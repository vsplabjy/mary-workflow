#!/usr/bin/env python3
"""Readable summary artifacts and grounded claim validation for Mary papers."""

from __future__ import annotations

import hashlib
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


SUMMARY_LEDGER_SCHEMA = 1
SUMMARY_CONTEXT_SCHEMA = 1
SUMMARY_FILE = "summary.md"
SUMMARY_LEDGER_FILE = "summary-ledger.json"
SUMMARY_CONTEXT_FILE = "summary-context.json"
SUMMARY_SECTIONS = ("background", "method", "experiments")
CLAIM_PREFIXES = {"background": "B", "method": "M", "experiments": "E"}
PREFIX_SECTIONS = {prefix: section for section, prefix in CLAIM_PREFIXES.items()}
SECTION_HEADING_ALIASES = {
    "background": {"background", "背景", "背景 / background", "背景（background）"},
    "method": {"method", "方法", "方法 / method", "方法（method）"},
    "experiments": {"experiments", "实验", "实验 / experiments", "实验（experiments）"},
}
SECTION_HEADING_PATTERN = re.compile(r"^##[ \t]+(.+?)[ \t]*#*[ \t]*$", flags=re.MULTILINE)
BODY_CLAIM_REF_PATTERN = re.compile(r"\[([A-Z][0-9]{2,})\]")
CLAIM_ID_PATTERN = re.compile(r"([BME])([0-9]{2,})")

JsonObject = dict[str, Any]


class PaperSummaryError(ValueError):
    """A summary input, claim, or artifact violated the P3.5 contract."""


def require_summary_string(value: object, field: str) -> str:
    text = " ".join(str(value or "").split())
    if not text:
        raise PaperSummaryError(f"{field} must be non-empty.")
    return text


def load_summary_ledger(path: Path) -> JsonObject:
    if not path.is_file():
        raise PaperSummaryError(f"{SUMMARY_LEDGER_FILE} is missing.")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise PaperSummaryError(f"{SUMMARY_LEDGER_FILE} is invalid: {exc}") from exc
    if not isinstance(payload, dict):
        raise PaperSummaryError(f"{SUMMARY_LEDGER_FILE} must contain a JSON object.")
    return payload


def summary_bundle_fingerprint(workspace: Path) -> str:
    """Fingerprint the exact bytes of both summary-stage output artifacts."""
    directory = Path(workspace)
    digest = hashlib.sha256()
    digest.update(b"mary-summary-bundle:v1\n")
    for filename in (SUMMARY_FILE, SUMMARY_LEDGER_FILE):
        data = (directory / filename).read_bytes()
        encoded_name = filename.encode("utf-8")
        digest.update(len(encoded_name).to_bytes(4, "big"))
        digest.update(encoded_name)
        digest.update(len(data).to_bytes(8, "big"))
        digest.update(data)
    return digest.hexdigest()


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
    source_format: str,
    blocks: dict[str, list[JsonObject]],
    allowed_locators: set[str],
) -> tuple[str, str, list[str]]:
    if not isinstance(value, dict):
        raise PaperSummaryError(f"{field} must be a claim object.")
    expected_fields = {"claim_id", "claim_text", "evidence", "source_locators"}
    if set(value) != expected_fields:
        raise PaperSummaryError(f"{field} must contain exactly: {', '.join(sorted(expected_fields))}.")
    claim_id = require_summary_string(value.get("claim_id"), f"{field}.claim_id")
    identifier = CLAIM_ID_PATTERN.fullmatch(claim_id)
    if identifier is None:
        raise PaperSummaryError(f"{field}.claim_id must match Bxx, Mxx, or Exx with at least two digits.")
    section = PREFIX_SECTIONS[identifier.group(1)]
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
    return claim_id, section, locators


def canonical_section_heading(value: str) -> str | None:
    normalized = " ".join(value.strip().split()).casefold()
    for section, aliases in SECTION_HEADING_ALIASES.items():
        if normalized in aliases:
            return section
    return None


def parse_blog_sections(summary_text: str) -> dict[str, str]:
    embedded_ledger_tokens = (
        "<!-- mary-summary:v1 -->",
        '"summary_schema"',
        '"summary_ledger_schema"',
    )
    if any(token in summary_text for token in embedded_ledger_tokens):
        raise PaperSummaryError(
            "summary.md must be blog prose only; move the machine ledger to summary-ledger.json."
        )
    headings = list(SECTION_HEADING_PATTERN.finditer(summary_text))
    sections: dict[str, str] = {}
    order: list[str] = []
    for index, heading in enumerate(headings):
        section = canonical_section_heading(heading.group(1))
        if section is None:
            raise PaperSummaryError(
                "summary.md may contain only Background/背景, Method/方法, and Experiments/实验 H2 headings."
            )
        if section in sections:
            raise PaperSummaryError(f"summary.md contains a duplicate {section} section heading.")
        body_end = headings[index + 1].start() if index + 1 < len(headings) else len(summary_text)
        body = summary_text[heading.end() : body_end].strip()
        if not body:
            raise PaperSummaryError(f"summary.md section {section} must be non-empty.")
        sections[section] = body
        order.append(section)
    if tuple(order) != SUMMARY_SECTIONS:
        raise PaperSummaryError(
            f"summary.md H2 sections must be ordered exactly: {', '.join(SUMMARY_SECTIONS)}."
        )
    return sections


def validate_body_anchors(
    sections: dict[str, str], claim_sections: dict[str, str]
) -> tuple[dict[str, int], dict[str, int]]:
    reference_counts = {claim_id: 0 for claim_id in claim_sections}
    section_anchor_counts: dict[str, int] = {}
    for section in SUMMARY_SECTIONS:
        section_anchor_counts[section] = 0
        expected_prefix = CLAIM_PREFIXES[section]
        for line_number, line in enumerate(sections[section].splitlines(), start=1):
            references = BODY_CLAIM_REF_PATTERN.findall(line)
            if not references:
                continue
            prose = BODY_CLAIM_REF_PATTERN.sub("", line)
            prose = re.sub(r"[`*_>#-]", "", prose).strip()
            if len(prose) < 8:
                raise PaperSummaryError(
                    f"summary.md {section} line {line_number} has an isolated claim anchor; "
                    "place it inline with a factual sentence."
                )
            for claim_id in references:
                if claim_id not in claim_sections:
                    raise PaperSummaryError(f"summary.md references unknown claim_id {claim_id}.")
                if not claim_id.startswith(expected_prefix):
                    raise PaperSummaryError(
                        f"summary.md claim anchor {claim_id} is in {section}, but its prefix belongs to "
                        f"{claim_sections[claim_id]}."
                    )
                reference_counts[claim_id] += 1
                section_anchor_counts[section] += 1
    missing = sorted(claim_id for claim_id, count in reference_counts.items() if count == 0)
    if missing:
        raise PaperSummaryError(
            f"Every summary-ledger claim_id must be cited in summary.md; missing: {', '.join(missing)}."
        )
    return reference_counts, section_anchor_counts


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
        raise PaperSummaryError(f"{SUMMARY_FILE} is missing.")
    ledger_path = directory / SUMMARY_LEDGER_FILE
    ledger = load_summary_ledger(ledger_path)
    context, blocks, context_fingerprint = validate_summary_context(
        directory,
        paper_id=paper_id,
        source_format=source_format,
        source_fingerprint=source_fingerprint,
        read_output_fingerprint=read_output_fingerprint,
    )
    expected_top_level = {"summary_ledger_schema", "paper_id", "inputs", "claims"}
    if set(ledger) != expected_top_level:
        missing = sorted(expected_top_level - set(ledger))
        extra = sorted(set(ledger) - expected_top_level)
        raise PaperSummaryError(
            f"summary-ledger top-level fields mismatch; missing={missing}, extra={extra}."
        )
    if ledger.get("summary_ledger_schema") != SUMMARY_LEDGER_SCHEMA:
        raise PaperSummaryError(f"summary_ledger_schema must be {SUMMARY_LEDGER_SCHEMA}.")
    if ledger.get("paper_id") != paper_id:
        raise PaperSummaryError("summary-ledger paper_id does not match the paper state.")
    if ledger.get("inputs") != context["inputs"]:
        raise PaperSummaryError("summary-ledger inputs must exactly copy summary-context.json.")

    claims = ledger.get("claims")
    if not isinstance(claims, list) or not claims:
        raise PaperSummaryError("summary-ledger claims must be a non-empty array.")
    allowed_locators = set(context["allowed_source_locators"])
    claim_sections: dict[str, str] = {}
    section_counts = {section: 0 for section in SUMMARY_SECTIONS}
    cited_locators: set[str] = set()
    for index, claim in enumerate(claims):
        claim_id, section, locators = validate_claim(
            claim,
            field=f"claims[{index}]",
            source_format=source_format,
            blocks=blocks,
            allowed_locators=allowed_locators,
        )
        if claim_id in claim_sections:
            raise PaperSummaryError(f"Duplicate summary claim_id: {claim_id}.")
        claim_sections[claim_id] = section
        section_counts[section] += 1
        cited_locators.update(locators)
    empty_claim_sections = [section for section, count in section_counts.items() if count == 0]
    if empty_claim_sections:
        raise PaperSummaryError(
            "summary-ledger requires at least one direct claim for each section; missing: "
            + ", ".join(empty_claim_sections)
            + "."
        )

    summary_text = summary_path.read_text(encoding="utf-8")
    body_sections = parse_blog_sections(summary_text)
    reference_counts, section_anchor_counts = validate_body_anchors(body_sections, claim_sections)
    body_section_characters = {
        section: len(re.sub(r"\s+", "", BODY_CLAIM_REF_PATTERN.sub("", body_sections[section])))
        for section in SUMMARY_SECTIONS
    }

    return {
        "summary_bundle_fingerprint": summary_bundle_fingerprint(directory),
        "metadata": {
            "summary_ledger_schema": SUMMARY_LEDGER_SCHEMA,
            "summary_body_artifact": SUMMARY_FILE,
            "summary_body_fingerprint": sha256_file(summary_path),
            "summary_ledger_artifact": SUMMARY_LEDGER_FILE,
            "summary_ledger_fingerprint": sha256_file(ledger_path),
            "claim_count": len(claim_sections),
            "section_claim_counts": section_counts,
            "body_claim_reference_count": sum(reference_counts.values()),
            "section_anchor_counts": section_anchor_counts,
            "body_section_characters": body_section_characters,
            "cited_locator_count": len(cited_locators),
            "summary_context": SUMMARY_CONTEXT_FILE,
            "summary_context_fingerprint": context_fingerprint,
            "source_locators": SOURCE_LOCATOR_FILE,
            "source_locators_fingerprint": context["inputs"]["source_locators"]["fingerprint"],
        },
    }
