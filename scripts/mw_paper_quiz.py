#!/usr/bin/env python3
"""Append-only, source-grounded expert Q&A sessions for Mary papers."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import stat
from typing import Any

from mw_paper_locators import (
    SourceLocatorError,
    evidence_resolves,
    validate_source_locator_index,
)
from mw_paper_sources import sha256_file
from mw_paper_summary import (
    PaperSummaryError,
    SUMMARY_FILE,
    SUMMARY_LEDGER_FILE,
    load_summary_ledger,
    validate_notes_input,
    validate_summary,
)
from mw_runtime import atomic_write_text


QUIZ_CONTEXT_SCHEMA = 2
QUIZ_HEAD_SCHEMA = 1
QUIZ_SESSION_SCHEMA = 1
QUIZ_CONTEXT_FILE = "quiz-context.json"
QUIZ_LOG_FILE = "quiz-log.md"
QUIZ_HEAD_FILE = "quiz-head.json"
QUIZ_LOG_HEADER = "<!-- mary-quiz-log:v1 -->\n# Expert Q&A Log\n\n"
QUIZ_SESSION_MARKER = "<!-- mary-quiz-session:v1 -->"
QUIZ_RECORD_OPEN = '<details class="mary-quiz-record">\n<summary>Machine record</summary>\n\n'
QUIZ_RECORD_CLOSE = "</details>\n\n"
GENESIS_HASH = "0" * 64
JUDGMENTS = ("supported", "partially-supported", "unsupported", "uncertain")
JUDGMENT_DEFINITIONS = {
    "supported": "The answer's material assertions are fully supported by the cited paper spans.",
    "partially-supported": "The cited paper supports part of the answer, but a material qualification or step is missing.",
    "unsupported": "The cited paper does not support at least one material assertion in the answer.",
    "uncertain": "The available paper text or parse quality is insufficient to decide support confidently.",
}
SESSION_INPUT_FIELDS = (
    "question",
    "anchors",
    "answer",
    "judgment",
    "rationale",
    "citations",
)
SESSION_FIELDS = (
    "quiz_session_schema",
    "paper_id",
    "session_id",
    "recorded_at",
    "context_fingerprint",
    *SESSION_INPUT_FIELDS,
    "previous_entry_hash",
    "entry_hash",
)
HEAD_FIELDS = (
    "quiz_head_schema",
    "paper_id",
    "session_count",
    "last_entry_hash",
    "log_fingerprint",
)
FINGERPRINT_PATTERN = re.compile(r"^[0-9a-f]{64}$")
UNCERTAINTY_ID_PATTERN = re.compile(r"^U[0-9]{2,}$")
METHOD_ID_PATTERN = re.compile(r"^M[0-9]{2,}$")
CJK_PATTERN = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff]")

JsonObject = dict[str, Any]


class PaperQuizError(ValueError):
    """A quiz context, session, citation, or append-only invariant failed."""


def require_quiz_string(value: object, field: str, *, minimum: int = 1) -> str:
    if not isinstance(value, str):
        raise PaperQuizError(f"{field} must be a string.")
    text = " ".join(value.split())
    if len(text) < minimum:
        raise PaperQuizError(f"{field} must contain at least {minimum} non-whitespace character(s).")
    return text


def canonical_hash(payload: JsonObject) -> str:
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def session_entry_hash(session: JsonObject) -> str:
    return canonical_hash({field: session[field] for field in SESSION_FIELDS if field != "entry_hash"})


def render_quiz_session(session: JsonObject) -> str:
    ordered = {field: session[field] for field in SESSION_FIELDS}
    uncertainty_ids = ", ".join(f"`{value}`" for value in session["anchors"]["uncertainty_ids"])
    method_ids = ", ".join(f"`{value}`" for value in session["anchors"]["method_claim_ids"])
    citations = "".join(
        f"- `{citation['source_locator']}`\n  > {citation['evidence']}\n"
        for citation in session["citations"]
    )
    return (
        f"{QUIZ_SESSION_MARKER}\n"
        f"## {session['session_id']} · {session['judgment']}\n\n"
        f"**Question:** {session['question']}\n\n"
        f"**Answer:** {session['answer']}\n\n"
        f"**Judgment:** `{session['judgment']}`\n\n"
        f"**Rationale:** {session['rationale']}\n\n"
        f"**Uncertainty anchors:** {uncertainty_ids or '(none)'}\n\n"
        f"**Method anchors:** {method_ids or '(none)'}\n\n"
        "**Source citations:**\n\n"
        f"{citations}\n"
        f"{QUIZ_RECORD_OPEN}"
        "```json\n"
        + json.dumps(ordered, ensure_ascii=False, indent=2)
        + f"\n```\n\n{QUIZ_RECORD_CLOSE}"
    )


def render_quiz_log(sessions: list[JsonObject]) -> str:
    return QUIZ_LOG_HEADER + "".join(render_quiz_session(session) for session in sessions)


def parse_quiz_log(text: str) -> list[JsonObject]:
    if not text.startswith(QUIZ_LOG_HEADER):
        raise PaperQuizError("quiz-log.md header or schema marker is invalid.")
    pattern = re.compile(
        re.escape(QUIZ_SESSION_MARKER)
        + r"\n.*?"
        + re.escape(QUIZ_RECORD_OPEN)
        + r"```json\n(.*?)\n```\n\n"
        + re.escape(QUIZ_RECORD_CLOSE),
        flags=re.DOTALL,
    )
    sessions: list[JsonObject] = []
    for match in pattern.finditer(text[len(QUIZ_LOG_HEADER) :]):
        try:
            payload = json.loads(match.group(1))
        except json.JSONDecodeError as exc:
            raise PaperQuizError(f"quiz-log.md contains invalid session JSON: {exc}") from exc
        if not isinstance(payload, dict):
            raise PaperQuizError("quiz-log.md session payload must be a JSON object.")
        sessions.append(payload)
    if render_quiz_log(sessions) != text:
        raise PaperQuizError(
            "quiz-log.md is not canonical append-only history; existing text was changed or removed."
        )
    return sessions


def require_string_array(
    value: object,
    field: str,
    *,
    pattern: re.Pattern[str] | None = None,
    allow_empty: bool = False,
) -> list[str]:
    if not isinstance(value, list) or (not value and not allow_empty):
        qualifier = "an array" if allow_empty else "a non-empty array"
        raise PaperQuizError(f"{field} must be {qualifier} of strings.")
    result: list[str] = []
    for item in value:
        if not isinstance(item, str):
            raise PaperQuizError(f"{field} must contain strings only.")
        text = " ".join(item.split())
        if not text or (pattern is not None and pattern.fullmatch(text) is None):
            raise PaperQuizError(f"{field} contains an invalid value: {text or '(empty)'}. ")
        if text in result:
            raise PaperQuizError(f"{field} contains duplicate value: {text}.")
        result.append(text)
    return result


def validate_session_shape(session: JsonObject, *, paper_id: str, position: int) -> None:
    if tuple(session) != SESSION_FIELDS:
        missing = [field for field in SESSION_FIELDS if field not in session]
        extra = [field for field in session if field not in SESSION_FIELDS]
        raise PaperQuizError(
            f"quiz session {position} fields/order mismatch; missing={missing}, extra={extra}."
        )
    if session.get("quiz_session_schema") != QUIZ_SESSION_SCHEMA:
        raise PaperQuizError(f"quiz session {position} must use quiz_session_schema {QUIZ_SESSION_SCHEMA}.")
    if session.get("paper_id") != paper_id:
        raise PaperQuizError(f"quiz session {position} paper_id does not match the paper workspace.")
    expected_id = f"Q{position:03d}"
    if session.get("session_id") != expected_id:
        raise PaperQuizError(f"quiz session {position} must use session_id {expected_id}.")
    require_quiz_string(session.get("recorded_at"), f"{expected_id}.recorded_at", minimum=10)
    if FINGERPRINT_PATTERN.fullmatch(str(session.get("context_fingerprint") or "")) is None:
        raise PaperQuizError(f"{expected_id}.context_fingerprint must be a SHA-256 digest.")
    require_quiz_string(session.get("question"), f"{expected_id}.question", minimum=8)
    require_quiz_string(session.get("answer"), f"{expected_id}.answer", minimum=1)
    if session.get("judgment") not in JUDGMENTS:
        raise PaperQuizError(f"{expected_id}.judgment must be one of: {', '.join(JUDGMENTS)}.")
    require_quiz_string(session.get("rationale"), f"{expected_id}.rationale", minimum=8)
    validate_anchor_shape(session.get("anchors"), f"{expected_id}.anchors")
    validate_citation_shape(session.get("citations"), f"{expected_id}.citations")
    for field in ("previous_entry_hash", "entry_hash"):
        if FINGERPRINT_PATTERN.fullmatch(str(session.get(field) or "")) is None:
            raise PaperQuizError(f"{expected_id}.{field} must be a SHA-256 digest.")


def validate_anchor_shape(value: object, field: str) -> tuple[list[str], list[str]]:
    if not isinstance(value, dict) or set(value) != {"uncertainty_ids", "method_claim_ids"}:
        raise PaperQuizError(f"{field} must contain exactly uncertainty_ids and method_claim_ids.")
    uncertainty_ids = require_string_array(
        value["uncertainty_ids"],
        f"{field}.uncertainty_ids",
        pattern=UNCERTAINTY_ID_PATTERN,
        allow_empty=True,
    )
    method_ids = require_string_array(
        value["method_claim_ids"],
        f"{field}.method_claim_ids",
        pattern=METHOD_ID_PATTERN,
        allow_empty=True,
    )
    if not uncertainty_ids and not method_ids:
        raise PaperQuizError(f"{field} must select at least one uncertainty or method claim.")
    return uncertainty_ids, method_ids


def validate_citation_shape(value: object, field: str) -> list[JsonObject]:
    if not isinstance(value, list) or not value:
        raise PaperQuizError(f"{field} must be a non-empty citation array.")
    citations: list[JsonObject] = []
    seen: set[tuple[str, str]] = set()
    for index, citation in enumerate(value):
        if not isinstance(citation, dict) or set(citation) != {"source_locator", "evidence"}:
            raise PaperQuizError(
                f"{field}[{index}] must contain exactly source_locator and evidence."
            )
        locator = require_quiz_string(citation["source_locator"], f"{field}[{index}].source_locator")
        evidence = require_quiz_string(citation["evidence"], f"{field}[{index}].evidence", minimum=8)
        if len(evidence) > 500:
            raise PaperQuizError(f"{field}[{index}].evidence must contain at most 500 characters.")
        key = (locator, evidence)
        if key in seen:
            raise PaperQuizError(f"{field} contains a duplicate citation for {locator}.")
        seen.add(key)
        citations.append({"source_locator": locator, "evidence": evidence})
    return citations


def validate_quiz_chain(sessions: list[JsonObject], *, paper_id: str) -> None:
    previous_hash = GENESIS_HASH
    for position, session in enumerate(sessions, start=1):
        validate_session_shape(session, paper_id=paper_id, position=position)
        if session["previous_entry_hash"] != previous_hash:
            raise PaperQuizError(
                f"quiz session {session['session_id']} breaks the append-only previous-entry chain."
            )
        expected_hash = session_entry_hash(session)
        if session["entry_hash"] != expected_hash:
            raise PaperQuizError(
                f"quiz session {session['session_id']} content or judgment was changed after append."
            )
        previous_hash = expected_hash


def build_quiz_head(workspace: Path, *, paper_id: str, sessions: list[JsonObject]) -> JsonObject:
    log_path = Path(workspace) / QUIZ_LOG_FILE
    return {
        "quiz_head_schema": QUIZ_HEAD_SCHEMA,
        "paper_id": paper_id,
        "session_count": len(sessions),
        "last_entry_hash": sessions[-1]["entry_hash"] if sessions else GENESIS_HASH,
        "log_fingerprint": sha256_file(log_path),
    }


def load_quiz_head(path: Path) -> JsonObject:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise PaperQuizError(f"quiz-head.json is invalid: {exc}") from exc
    if not isinstance(payload, dict) or tuple(payload) != HEAD_FIELDS:
        raise PaperQuizError("quiz-head.json fields/order do not match the append-only contract.")
    if payload.get("quiz_head_schema") != QUIZ_HEAD_SCHEMA:
        raise PaperQuizError(f"quiz-head.json must use quiz_head_schema {QUIZ_HEAD_SCHEMA}.")
    return payload


def initialize_quiz_history(workspace: Path, *, paper_id: str) -> tuple[list[JsonObject], JsonObject]:
    directory = Path(workspace)
    log_path = directory / QUIZ_LOG_FILE
    head_path = directory / QUIZ_HEAD_FILE
    if log_path.is_symlink() or head_path.is_symlink():
        raise PaperQuizError("Quiz history files must not be symbolic links.")
    if not log_path.exists() and not head_path.exists():
        atomic_write_text(log_path, QUIZ_LOG_HEADER)
        head = build_quiz_head(directory, paper_id=paper_id, sessions=[])
        atomic_write_text(head_path, json.dumps(head, ensure_ascii=False, indent=2) + "\n")
        return [], head
    if not log_path.is_file() or not head_path.is_file():
        raise PaperQuizError(
            "Append-only quiz history is incomplete; quiz-log.md and quiz-head.json must both exist."
        )
    return validate_quiz_history(directory, paper_id=paper_id)


def validate_quiz_history(workspace: Path, *, paper_id: str) -> tuple[list[JsonObject], JsonObject]:
    directory = Path(workspace)
    log_path = directory / QUIZ_LOG_FILE
    head_path = directory / QUIZ_HEAD_FILE
    if log_path.is_symlink() or head_path.is_symlink():
        raise PaperQuizError("Quiz history files must not be symbolic links.")
    if not log_path.is_file() or not head_path.is_file():
        raise PaperQuizError("Quiz history is missing; run prepare-quiz first.")
    sessions = parse_quiz_log(log_path.read_text(encoding="utf-8"))
    validate_quiz_chain(sessions, paper_id=paper_id)
    stored_head = load_quiz_head(head_path)
    expected_head = build_quiz_head(directory, paper_id=paper_id, sessions=sessions)
    if stored_head != expected_head:
        raise PaperQuizError(
            "quiz-log.md append-only history differs from quiz-head.json; deletion or amendment is forbidden."
        )
    return sessions, stored_head


def build_quiz_context(
    workspace: Path,
    *,
    paper_id: str,
    quiz_attempt: int,
    source_format: str,
    source_fingerprint: str,
    read_output_fingerprint: str,
    summary_output_fingerprint: str,
) -> tuple[JsonObject, dict[str, list[JsonObject]]]:
    directory = Path(workspace)
    try:
        notes = validate_notes_input(directory, paper_id, read_output_fingerprint)
        summary_validation = validate_summary(
            directory,
            paper_id=paper_id,
            source_format=source_format,
            source_fingerprint=source_fingerprint,
            read_output_fingerprint=read_output_fingerprint,
        )
        summary_ledger = load_summary_ledger(directory / SUMMARY_LEDGER_FILE)
        _, blocks, locator_fingerprint = validate_source_locator_index(
            directory,
            paper_id=paper_id,
            source_format=source_format,
            source_fingerprint=source_fingerprint,
        )
    except (PaperSummaryError, SourceLocatorError) as exc:
        raise PaperQuizError(str(exc)) from exc
    if summary_validation["summary_bundle_fingerprint"] != summary_output_fingerprint:
        raise PaperQuizError(
            "Current summary.md + summary-ledger.json bytes do not match the completed summary stage."
        )
    if not isinstance(quiz_attempt, int) or isinstance(quiz_attempt, bool) or quiz_attempt < 1:
        raise PaperQuizError("quiz_attempt must be a positive integer.")

    scientific_uncertainty_catalog = []
    source_quality_notes = []
    for uncertainty in notes["uncertainties"]:
        quality_dimensions = uncertainty["quality_dimensions"]
        if quality_dimensions:
            source_quality_notes.append(
                {
                    "note_id": f"SQ{len(source_quality_notes) + 1:02d}",
                    "why_unresolved": uncertainty["why_unresolved"],
                    "impact": uncertainty["impact"],
                    "source_locators": uncertainty["locators"],
                    "quality_dimensions": quality_dimensions,
                }
            )
            continue
        scientific_uncertainty_catalog.append(
            {
                "uncertainty_id": f"U{len(scientific_uncertainty_catalog) + 1:02d}",
                "question": uncertainty["question"],
                "why_unresolved": uncertainty["why_unresolved"],
                "impact": uncertainty["impact"],
                "source_locators": uncertainty["locators"],
            }
        )
    method_claim_catalog = [
        {
            "claim_id": claim["claim_id"],
            "claim_text": claim["claim_text"],
            "evidence": claim["evidence"],
            "source_locators": claim["source_locators"],
        }
        for claim in summary_ledger["claims"]
        if str(claim.get("claim_id") or "").startswith("M")
    ]
    if not method_claim_catalog:
        raise PaperQuizError("Quiz preparation requires a non-empty method-claim catalog.")

    metadata = summary_validation["metadata"]
    context = {
        "quiz_context_schema": QUIZ_CONTEXT_SCHEMA,
        "paper_id": paper_id,
        "quiz_attempt": quiz_attempt,
        "inputs": {
            "paper_notes": {
                "artifact": "paper-notes.md",
                "fingerprint": read_output_fingerprint,
            },
            "summary": {
                "artifact": SUMMARY_FILE,
                "fingerprint": metadata["summary_body_fingerprint"],
            },
            "summary_ledger": {
                "artifact": SUMMARY_LEDGER_FILE,
                "fingerprint": metadata["summary_ledger_fingerprint"],
            },
            "summary_bundle": {"fingerprint": summary_output_fingerprint},
            "source": {
                "artifact": "source.md",
                "artifact_fingerprint": sha256_file(directory / "source.md"),
                "format": source_format,
                "source_fingerprint": source_fingerprint,
            },
            "source_locators": {
                "artifact": "source-locators.json",
                "fingerprint": locator_fingerprint,
            },
        },
        "judgments": JUDGMENT_DEFINITIONS,
        "scientific_uncertainty_catalog": scientific_uncertainty_catalog,
        "source_quality_notes": source_quality_notes,
        "method_claim_catalog": method_claim_catalog,
        "completion_requirements": {
            "minimum_current_sessions": 1,
            "require_method_claim_anchor": True,
            "require_scientific_uncertainty_anchor": bool(scientific_uncertainty_catalog),
            "citations_must_be_exact_source_excerpts": True,
        },
    }
    return context, blocks


def write_quiz_context(
    workspace: Path,
    *,
    paper_id: str,
    quiz_attempt: int,
    source_format: str,
    source_fingerprint: str,
    read_output_fingerprint: str,
    summary_output_fingerprint: str,
) -> JsonObject:
    directory = Path(workspace)
    context, _ = build_quiz_context(
        directory,
        paper_id=paper_id,
        quiz_attempt=quiz_attempt,
        source_format=source_format,
        source_fingerprint=source_fingerprint,
        read_output_fingerprint=read_output_fingerprint,
        summary_output_fingerprint=summary_output_fingerprint,
    )
    initialize_quiz_history(directory, paper_id=paper_id)
    atomic_write_text(
        directory / QUIZ_CONTEXT_FILE,
        json.dumps(context, ensure_ascii=False, indent=2) + "\n",
    )
    return context


def validate_quiz_context(
    workspace: Path,
    *,
    paper_id: str,
    quiz_attempt: int,
    source_format: str,
    source_fingerprint: str,
    read_output_fingerprint: str,
    summary_output_fingerprint: str,
) -> tuple[JsonObject, dict[str, list[JsonObject]], str]:
    context_path = Path(workspace) / QUIZ_CONTEXT_FILE
    if not context_path.is_file():
        raise PaperQuizError("quiz-context.json is missing; run prepare-quiz first.")
    try:
        stored = json.loads(context_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise PaperQuizError(f"quiz-context.json is invalid: {exc}") from exc
    expected, blocks = build_quiz_context(
        workspace,
        paper_id=paper_id,
        quiz_attempt=quiz_attempt,
        source_format=source_format,
        source_fingerprint=source_fingerprint,
        read_output_fingerprint=read_output_fingerprint,
        summary_output_fingerprint=summary_output_fingerprint,
    )
    if stored != expected:
        raise PaperQuizError("quiz-context.json is stale or does not match current inputs/attempt.")
    return stored, blocks, sha256_file(context_path)


def validate_session_input(
    payload: object,
    *,
    context: JsonObject,
    blocks: dict[str, list[JsonObject]],
) -> JsonObject:
    if not isinstance(payload, dict) or set(payload) != set(SESSION_INPUT_FIELDS):
        missing = [field for field in SESSION_INPUT_FIELDS if not isinstance(payload, dict) or field not in payload]
        extra = [field for field in payload if field not in SESSION_INPUT_FIELDS] if isinstance(payload, dict) else []
        raise PaperQuizError(
            f"quiz session input fields/order mismatch; missing={missing}, extra={extra}."
        )
    question = require_quiz_string(payload["question"], "session.question", minimum=8)
    answer = require_quiz_string(payload["answer"], "session.answer")
    judgment = str(payload["judgment"] or "").strip()
    if judgment not in JUDGMENTS:
        raise PaperQuizError(f"session.judgment must be one of: {', '.join(JUDGMENTS)}.")
    rationale = require_quiz_string(payload["rationale"], "session.rationale", minimum=8)
    uncertainty_ids, method_ids = validate_anchor_shape(payload["anchors"], "session.anchors")
    uncertainty_catalog = {
        item["uncertainty_id"]: item
        for item in context["scientific_uncertainty_catalog"]
    }
    method_catalog = {item["claim_id"]: item for item in context["method_claim_catalog"]}
    unknown_uncertainties = sorted(set(uncertainty_ids) - set(uncertainty_catalog))
    unknown_methods = sorted(set(method_ids) - set(method_catalog))
    if unknown_uncertainties:
        raise PaperQuizError(f"session anchors unknown uncertainty ids: {', '.join(unknown_uncertainties)}.")
    if unknown_methods:
        raise PaperQuizError(f"session anchors unknown method claim ids: {', '.join(unknown_methods)}.")

    allowed_locators: set[str] = set()
    for anchor_id in uncertainty_ids:
        allowed_locators.update(uncertainty_catalog[anchor_id]["source_locators"])
    for anchor_id in method_ids:
        allowed_locators.update(method_catalog[anchor_id]["source_locators"])
    citations = validate_citation_shape(payload["citations"], "session.citations")
    for index, citation in enumerate(citations):
        locator = citation["source_locator"]
        if locator not in allowed_locators:
            raise PaperQuizError(
                f"session.citations[{index}] locator {locator} is not backed by the selected anchors."
            )
        if locator not in blocks or not evidence_resolves(citation["evidence"], [locator], blocks):
            raise PaperQuizError(
                f"session.citations[{index}] evidence does not resolve under {locator} in source.md."
            )
    return {
        "question": question,
        "anchors": {
            "uncertainty_ids": uncertainty_ids,
            "method_claim_ids": method_ids,
        },
        "answer": answer,
        "judgment": judgment,
        "rationale": rationale,
        "citations": citations,
    }


def append_quiz_block(path: Path, block: str) -> None:
    flags = os.O_WRONLY | os.O_APPEND | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(Path(path), flags)
    try:
        if not stat.S_ISREG(os.fstat(descriptor).st_mode):
            raise PaperQuizError("quiz-log.md must be a regular file.")
        content = block.encode("utf-8")
        offset = 0
        while offset < len(content):
            written = os.write(descriptor, content[offset:])
            if written <= 0:
                raise OSError("Could not append the complete quiz session.")
            offset += written
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def append_quiz_session(
    workspace: Path,
    *,
    paper_id: str,
    context: JsonObject,
    blocks: dict[str, list[JsonObject]],
    payload: object,
    recorded_at: str,
) -> JsonObject:
    directory = Path(workspace)
    sessions, _ = validate_quiz_history(directory, paper_id=paper_id)
    normalized = validate_session_input(payload, context=context, blocks=blocks)
    context_fingerprint = sha256_file(directory / QUIZ_CONTEXT_FILE)
    session: JsonObject = {
        "quiz_session_schema": QUIZ_SESSION_SCHEMA,
        "paper_id": paper_id,
        "session_id": f"Q{len(sessions) + 1:03d}",
        "recorded_at": require_quiz_string(recorded_at, "recorded_at", minimum=10),
        "context_fingerprint": context_fingerprint,
        **normalized,
        "previous_entry_hash": sessions[-1]["entry_hash"] if sessions else GENESIS_HASH,
        "entry_hash": "",
    }
    session["entry_hash"] = session_entry_hash(session)
    updated_sessions = [*sessions, session]
    append_quiz_block(directory / QUIZ_LOG_FILE, render_quiz_session(session))
    head = build_quiz_head(directory, paper_id=paper_id, sessions=updated_sessions)
    atomic_write_text(
        directory / QUIZ_HEAD_FILE,
        json.dumps(head, ensure_ascii=False, indent=2) + "\n",
    )
    return session


def next_quiz_question(context: JsonObject, sessions: list[JsonObject], *, context_fingerprint: str) -> JsonObject:
    current = [session for session in sessions if session["context_fingerprint"] == context_fingerprint]
    uncertainty_usage = {
        item["uncertainty_id"]: 0
        for item in context["scientific_uncertainty_catalog"]
    }
    method_usage = {item["claim_id"]: 0 for item in context["method_claim_catalog"]}
    for session in current:
        for anchor_id in session["anchors"]["uncertainty_ids"]:
            if anchor_id in uncertainty_usage:
                uncertainty_usage[anchor_id] += 1
        for anchor_id in session["anchors"]["method_claim_ids"]:
            if anchor_id in method_usage:
                method_usage[anchor_id] += 1

    has_method_coverage = any(method_usage.values())
    has_uncertainty_coverage = any(uncertainty_usage.values())
    unused_methods = [anchor_id for anchor_id, count in method_usage.items() if count == 0]
    unused_uncertainties = [
        anchor_id for anchor_id, count in uncertainty_usage.items() if count == 0
    ]
    if unused_methods and not has_method_coverage:
        kind = "method"
        anchor_id = min(unused_methods)
    elif unused_uncertainties and not has_uncertainty_coverage:
        kind = "uncertainty"
        anchor_id = min(unused_uncertainties)
    elif unused_methods:
        kind = "method"
        anchor_id = min(unused_methods)
    elif unused_uncertainties:
        kind = "uncertainty"
        anchor_id = min(unused_uncertainties)
    else:
        kind = "method"
        anchor_id = min(method_usage, key=lambda value: (method_usage[value], value))

    if kind == "uncertainty":
        item = next(
            entry
            for entry in context["scientific_uncertainty_catalog"]
            if entry["uncertainty_id"] == anchor_id
        )
        question = item["question"]
        anchors = {"uncertainty_ids": [anchor_id], "method_claim_ids": []}
        locators = item["source_locators"]
    else:
        item = next(entry for entry in context["method_claim_catalog"] if entry["claim_id"] == anchor_id)
        claim_text = item["claim_text"]
        if CJK_PATTERN.search(claim_text):
            question = (
                f"论文指出：“{claim_text}”请结合论文的方法流程说明：这句话具体意味着什么、"
                "对应哪个环节，以及理解它为什么有助于把握论文的核心贡献？"
            )
        else:
            question = (
                f'The paper states: "{claim_text}" Explain what this means, where it fits in '
                "the method pipeline, and how it helps clarify the paper's core contribution."
            )
        anchors = {"uncertainty_ids": [], "method_claim_ids": [anchor_id]}
        locators = item["source_locators"]
    return {
        "question": question,
        "anchors": anchors,
        "source_locator_hints": locators,
        "current_session_count": len(current),
    }


def validate_quiz(
    workspace: Path,
    *,
    paper_id: str,
    quiz_attempt: int,
    source_format: str,
    source_fingerprint: str,
    read_output_fingerprint: str,
    summary_output_fingerprint: str,
) -> JsonObject:
    directory = Path(workspace)
    context, blocks, context_fingerprint = validate_quiz_context(
        directory,
        paper_id=paper_id,
        quiz_attempt=quiz_attempt,
        source_format=source_format,
        source_fingerprint=source_fingerprint,
        read_output_fingerprint=read_output_fingerprint,
        summary_output_fingerprint=summary_output_fingerprint,
    )
    sessions, head = validate_quiz_history(directory, paper_id=paper_id)
    current = [session for session in sessions if session["context_fingerprint"] == context_fingerprint]
    if not current:
        raise PaperQuizError("quiz-log.md requires at least one session for the current quiz attempt.")

    used_uncertainties: set[str] = set()
    used_methods: set[str] = set()
    cited_locators: set[str] = set()
    judgment_counts = {judgment: 0 for judgment in JUDGMENTS}
    for session in current:
        payload = {field: session[field] for field in SESSION_INPUT_FIELDS}
        validate_session_input(payload, context=context, blocks=blocks)
        used_uncertainties.update(session["anchors"]["uncertainty_ids"])
        used_methods.update(session["anchors"]["method_claim_ids"])
        cited_locators.update(citation["source_locator"] for citation in session["citations"])
        judgment_counts[session["judgment"]] += 1
    if not used_methods:
        raise PaperQuizError("Current quiz attempt must include at least one method-claim-anchored session.")
    if (
        context["completion_requirements"]["require_scientific_uncertainty_anchor"]
        and not used_uncertainties
    ):
        raise PaperQuizError(
            "Current quiz attempt must include at least one scientific-uncertainty-anchored session."
        )

    return {
        "quiz_log_fingerprint": sha256_file(directory / QUIZ_LOG_FILE),
        "metadata": {
            "quiz_context_schema": QUIZ_CONTEXT_SCHEMA,
            "quiz_context": QUIZ_CONTEXT_FILE,
            "quiz_context_fingerprint": context_fingerprint,
            "quiz_head": QUIZ_HEAD_FILE,
            "quiz_head_fingerprint": sha256_file(directory / QUIZ_HEAD_FILE),
            "session_count": len(current),
            "history_session_count": len(sessions),
            "last_entry_hash": head["last_entry_hash"],
            "judgment_counts": judgment_counts,
            "uncertainty_anchor_ids": sorted(used_uncertainties),
            "method_claim_anchor_ids": sorted(used_methods),
            "cited_locators": sorted(cited_locators),
        },
    }
