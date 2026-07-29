#!/usr/bin/env python3
"""Shared persistence and envelope primitives for Mary runtimes."""

from __future__ import annotations

import json
import os
from pathlib import Path
import re
import secrets
import stat
from typing import Any


JsonObject = dict[str, Any]


class EnvelopeError(ValueError):
    """An action envelope could not be parsed or validated."""


def parse_json_payload(raw: str) -> object:
    """Parse a direct, fenced, or embedded JSON value."""
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass

    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", raw, flags=re.DOTALL)
    if fenced:
        try:
            return json.loads(fenced.group(1))
        except json.JSONDecodeError as exc:
            raise EnvelopeError(f"Invalid fenced JSON action: {exc}") from exc

    candidate = extract_first_json_object(raw)
    if candidate:
        try:
            return json.loads(candidate)
        except json.JSONDecodeError as exc:
            raise EnvelopeError(f"Invalid embedded JSON action: {exc}") from exc
    raise EnvelopeError("Invalid JSON action: no JSON object found.")


def extract_first_json_object(raw: str) -> str | None:
    """Return the first balanced JSON-looking object in arbitrary text."""
    start = raw.find("{")
    if start == -1:
        return None
    depth = 0
    in_string = False
    escaped = False
    for index, char in enumerate(raw[start:], start=start):
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            continue
        if char == '"':
            in_string = True
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return raw[start : index + 1]
    return None


def require_json_object(payload: object) -> JsonObject:
    """Require the outer JSON action value to be an object."""
    if not isinstance(payload, dict):
        raise EnvelopeError("JSON action must be an object.")
    return payload


def action_envelope_parts(payload: JsonObject) -> tuple[str, JsonObject]:
    """Normalize an action name and require object-shaped action data."""
    action = str(payload.get("action", "")).strip()
    data = payload.get("data", {})
    if not isinstance(data, dict):
        raise EnvelopeError("Action data must be an object.")
    return action, data


def atomic_write_text(path: Path, content: str, *, encoding: str = "utf-8") -> None:
    """Durably write text to a same-directory temporary file, then replace."""
    destination = Path(path)
    temporary: Path | None = None
    descriptor: int | None = None
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL

    for _ in range(100):
        candidate = destination.parent / f".{destination.name}.{secrets.token_hex(8)}.tmp"
        try:
            descriptor = os.open(candidate, flags, 0o666)
        except FileExistsError:
            continue
        temporary = candidate
        break
    else:
        raise FileExistsError(f"Could not allocate a temporary file for {destination}.")

    try:
        if destination.exists():
            os.fchmod(descriptor, stat.S_IMODE(destination.stat().st_mode))
        handle = os.fdopen(descriptor, "w", encoding=encoding)
        descriptor = None
        with handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, destination)
    finally:
        if descriptor is not None:
            os.close(descriptor)
        if temporary is not None:
            try:
                temporary.unlink()
            except FileNotFoundError:
                pass


def append_log_entry(
    path: Path,
    message: str,
    *,
    timestamp: str,
    header: str,
    encoding: str = "utf-8",
) -> None:
    """Create a Markdown log when missing and append one timestamped entry."""
    log_path = Path(path)
    if not log_path.exists():
        atomic_write_text(log_path, header, encoding=encoding)
    with log_path.open("a", encoding=encoding) as handle:
        handle.write(f"- {timestamp} {message}\n")
