#!/usr/bin/env python3
"""Source acquisition and read-ledger validation for Mary Workflow papers."""

from __future__ import annotations

import hashlib
from html import unescape
from html.parser import HTMLParser
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.parse import quote, unquote, urlparse
from urllib.request import Request, urlopen

from mw_runtime import atomic_write_text


PARSE_QUALITY_SCHEMA = 1
PAPER_NOTES_SCHEMA = 1
QUALITY_DIMENSIONS = ("text", "structure", "equations", "figures", "tables")
QUALITY_STATUSES = {"pass", "degraded", "failed", "not_applicable"}
SOURCE_FORMATS = {"html", "pdf"}
MAX_SOURCE_BYTES = 64 * 1024 * 1024
USER_AGENT = "mary-workflow/2.2 (single-paper research pipeline)"

JsonObject = dict[str, Any]
FetchResult = tuple[bytes, str, str]
Fetcher = Callable[[str], FetchResult]
PdfExtractor = Callable[[bytes], str]


class PaperReadError(ValueError):
    """Source acquisition or the paper-notes contract failed."""


def sha256_bytes(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def atomic_write_bytes(path: Path, content: bytes) -> None:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{destination.name}.", suffix=".tmp", dir=destination.parent
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, destination)
    finally:
        try:
            temporary.unlink()
        except FileNotFoundError:
            pass


def fetch_url(url: str) -> FetchResult:
    request = Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "text/html,application/pdf;q=0.9,*/*;q=0.1",
        },
    )
    try:
        with urlopen(request, timeout=45) as response:
            content_length = response.headers.get("Content-Length")
            if content_length and int(content_length) > MAX_SOURCE_BYTES:
                raise PaperReadError(f"Source exceeds the {MAX_SOURCE_BYTES // (1024 * 1024)} MiB limit.")
            chunks: list[bytes] = []
            total = 0
            while True:
                chunk = response.read(1024 * 1024)
                if not chunk:
                    break
                total += len(chunk)
                if total > MAX_SOURCE_BYTES:
                    raise PaperReadError(f"Source exceeds the {MAX_SOURCE_BYTES // (1024 * 1024)} MiB limit.")
                chunks.append(chunk)
            return b"".join(chunks), response.headers.get_content_type(), response.geturl()
    except HTTPError as exc:
        raise PaperReadError(f"HTTP {exc.code} for {url}") from exc
    except URLError as exc:
        raise PaperReadError(f"Could not fetch {url}: {exc.reason}") from exc


def extract_pdf_text(content: bytes) -> str:
    executable = shutil.which("pdftotext")
    if executable is None:
        raise PaperReadError("PDF fallback requires Poppler pdftotext on PATH.")
    with tempfile.TemporaryDirectory(prefix="mw-paper-pdf-") as directory:
        pdf_path = Path(directory) / "source.pdf"
        pdf_path.write_bytes(content)
        try:
            completed = subprocess.run(
                [executable, "-layout", "-enc", "UTF-8", str(pdf_path), "-"],
                check=False,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=120,
            )
        except subprocess.TimeoutExpired as exc:
            raise PaperReadError("pdftotext timed out after 120 seconds.") from exc
    if completed.returncode != 0:
        message = completed.stderr.decode("utf-8", errors="replace").strip()
        raise PaperReadError(f"pdftotext failed: {message or f'exit {completed.returncode}'}")
    text = completed.stdout.decode("utf-8", errors="replace")
    if not text.strip():
        raise PaperReadError("pdftotext produced no text.")
    return text


def clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", unescape(value)).strip()


class ArxivHTMLExtractor(HTMLParser):
    """Extract locatable semantic blocks from arXiv's LaTeXML HTML."""

    BLOCK_TAGS = {
        "h1",
        "h2",
        "h3",
        "h4",
        "h5",
        "h6",
        "p",
        "li",
        "figcaption",
        "caption",
        "tr",
    }
    SKIP_TAGS = {"script", "style", "nav", "header", "footer", "noscript"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.blocks: list[JsonObject] = []
        self.title = ""
        self.abstract_seen = False
        self.section_count = 0
        self.math_count = 0
        self.math_preserved = 0
        self.figure_count = 0
        self.figure_caption_count = 0
        self.table_count = 0
        self.table_caption_count = 0
        self.table_row_count = 0
        self._float_kinds: list[str] = []
        self._skip_depth = 0
        self._section_ids: list[str] = []
        self._block_tag = ""
        self._block_kind = ""
        self._block_anchor = ""
        self._block_owner = ""
        self._chunks: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = {name: value or "" for name, value in attrs}
        classes = set(attributes.get("class", "").split())
        if tag in self.SKIP_TAGS:
            self._skip_depth += 1
            return
        if self._skip_depth:
            return
        if tag == "section":
            self._section_ids.append(attributes.get("id", ""))
            if "ltx_section" in classes:
                self.section_count += 1
        if "ltx_abstract" in classes:
            self.abstract_seen = True
        if tag == "figure":
            float_kind = "table" if "ltx_table" in classes else "figure"
            self._float_kinds.append(float_kind)
            if float_kind == "table":
                self.table_count += 1
            else:
                self.figure_count += 1
        if tag == "math":
            self.math_count += 1
            alt_text = clean_text(attributes.get("alttext", ""))
            if alt_text:
                self.math_preserved += 1
                if self._block_tag:
                    self._chunks.append(f" {alt_text} ")
        if tag in {"td", "th"} and self._block_tag == "tr":
            self._chunks.append(" | ")
        is_latex_caption = "ltx_caption" in classes
        if tag in self.BLOCK_TAGS or is_latex_caption:
            self._flush_block()
            self._block_tag = tag
            self._block_kind = "caption" if is_latex_caption else tag
            self._block_anchor = attributes.get("id", "") or next(
                (anchor for anchor in reversed(self._section_ids) if anchor), ""
            )
            self._block_owner = self._float_kinds[-1] if self._float_kinds else ""

    def handle_endtag(self, tag: str) -> None:
        if tag in self.SKIP_TAGS:
            if self._skip_depth:
                self._skip_depth -= 1
            return
        if self._skip_depth:
            return
        if tag == self._block_tag:
            self._flush_block()
        if tag == "figure" and self._float_kinds:
            self._float_kinds.pop()
        if tag == "section" and self._section_ids:
            self._section_ids.pop()

    def handle_data(self, data: str) -> None:
        if not self._skip_depth and self._block_tag:
            self._chunks.append(data)

    def close(self) -> None:
        super().close()
        self._flush_block()

    def _flush_block(self) -> None:
        if not self._block_tag:
            return
        text = clean_text(" ".join(self._chunks))
        if text:
            anchor = self._block_anchor or f"block-{len(self.blocks) + 1}"
            self.blocks.append({"kind": self._block_kind, "text": text, "anchor": anchor})
            if self._block_kind == "h1" and not self.title:
                self.title = text
            is_table_caption = self._block_owner == "table" or bool(
                re.match(r"^table\b", text, flags=re.IGNORECASE)
            )
            if self._block_tag == "figcaption" and not is_table_caption:
                self.figure_caption_count += 1
            if self._block_kind in {"caption", "figcaption"} and is_table_caption:
                self.table_caption_count += 1
            if self._block_tag == "tr" and self._block_owner == "table":
                self.table_row_count += 1
        self._block_tag = ""
        self._block_kind = ""
        self._block_anchor = ""
        self._block_owner = ""
        self._chunks = []


def quality_dimension(status: str, score: int, metrics: JsonObject, *evidence: str) -> JsonObject:
    if status not in QUALITY_STATUSES:
        raise PaperReadError(f"Invalid quality status: {status}")
    return {
        "status": status,
        "score": max(0, min(100, int(score))),
        "metrics": metrics,
        "evidence": [item for item in evidence if item],
    }


def text_quality(text: str) -> JsonObject:
    compact = re.sub(r"\s+", "", text)
    character_count = len(compact)
    replacement_count = text.count("\ufffd")
    replacement_ratio = replacement_count / max(1, character_count)
    if character_count < 800 or replacement_ratio > 0.02:
        status, score = "failed", 20
    elif character_count < 2500 or replacement_ratio > 0.005:
        status, score = "degraded", 60
    else:
        status, score = "pass", 100
    return quality_dimension(
        status,
        score,
        {"characters": character_count, "replacement_ratio": round(replacement_ratio, 6)},
        f"Extracted {character_count} non-whitespace characters.",
        f"Unicode replacement ratio is {replacement_ratio:.4%}.",
    )


def bounded_ratio(numerator: int, denominator: int) -> float:
    return min(1.0, numerator / max(1, denominator))


def html_to_normalized_source(content: bytes) -> tuple[str, dict[str, JsonObject]]:
    decoded = content.decode("utf-8", errors="replace")
    extractor = ArxivHTMLExtractor()
    extractor.feed(decoded)
    extractor.close()
    body_text = "\n".join(str(block["text"]) for block in extractor.blocks)

    text_dimension = text_quality(body_text)
    if not extractor.title or (extractor.section_count == 0 and not extractor.abstract_seen):
        structure_status, structure_score = "failed", 20
    elif extractor.section_count < 2 or not extractor.abstract_seen:
        structure_status, structure_score = "degraded", 60
    else:
        structure_status, structure_score = "pass", 100
    structure_dimension = quality_dimension(
        structure_status,
        structure_score,
        {
            "title_present": bool(extractor.title),
            "abstract_present": extractor.abstract_seen,
            "sections": extractor.section_count,
        },
        f"Title present: {bool(extractor.title)}.",
        f"Detected {extractor.section_count} semantic sections; abstract present: {extractor.abstract_seen}.",
    )

    if extractor.math_count == 0:
        equations_dimension = quality_dimension(
            "not_applicable", 100, {"elements": 0, "preserved": 0}, "No HTML math elements detected."
        )
    else:
        math_ratio = bounded_ratio(extractor.math_preserved, extractor.math_count)
        status = "pass" if math_ratio >= 0.8 else "degraded" if math_ratio >= 0.3 else "failed"
        equations_dimension = quality_dimension(
            status,
            round(math_ratio * 100),
            {"elements": extractor.math_count, "preserved": extractor.math_preserved},
            f"Preserved text for {extractor.math_preserved}/{extractor.math_count} math elements.",
        )

    if extractor.figure_count == 0:
        figures_dimension = quality_dimension(
            "not_applicable", 100, {"figures": 0, "captions": 0}, "No HTML figure elements detected."
        )
    else:
        figure_ratio = bounded_ratio(extractor.figure_caption_count, extractor.figure_count)
        status = "degraded" if figure_ratio > 0 else "failed"
        figures_dimension = quality_dimension(
            status,
            60 if figure_ratio > 0 else 0,
            {
                "figures": extractor.figure_count,
                "captions": extractor.figure_caption_count,
                "visuals_extracted": 0,
            },
            f"Captured {extractor.figure_caption_count}/{extractor.figure_count} figure captions.",
            "HTML normalization does not download or inspect figure pixels.",
        )

    if extractor.table_count == 0:
        tables_dimension = quality_dimension(
            "not_applicable", 100, {"tables": 0, "captions": 0}, "No HTML table elements detected."
        )
    else:
        table_ratio = bounded_ratio(extractor.table_caption_count, extractor.table_count)
        if extractor.table_row_count == 0:
            status, score = "failed", 0
        elif table_ratio >= 0.8:
            status, score = "pass", 90
        else:
            status, score = "degraded", 60
        tables_dimension = quality_dimension(
            status,
            score,
            {
                "tables": extractor.table_count,
                "captions": extractor.table_caption_count,
                "rows": extractor.table_row_count,
            },
            f"Captured {extractor.table_caption_count}/{extractor.table_count} table captions.",
            f"Captured {extractor.table_row_count} table rows.",
        )

    lines = ["<!-- mary-normalized-source:v1 -->", "", f"# {extractor.title or 'Untitled paper'}", ""]
    for block in extractor.blocks:
        lines.append(f"<!-- locator: html#{block['anchor']} -->")
        kind = str(block["kind"])
        text = str(block["text"])
        if kind.startswith("h") and len(kind) == 2 and kind[1].isdigit():
            level = min(6, max(2, int(kind[1]) + 1))
            lines.append(f"{'#' * level} {text}")
        elif kind in {"figcaption", "caption"}:
            lines.append(f"> {text}")
        elif kind == "li":
            lines.append(f"- {text}")
        elif kind == "tr":
            lines.append(f"{text} |")
        else:
            lines.append(text)
        lines.append("")
    dimensions = {
        "text": text_dimension,
        "structure": structure_dimension,
        "equations": equations_dimension,
        "figures": figures_dimension,
        "tables": tables_dimension,
    }
    return "\n".join(lines).rstrip() + "\n", dimensions


def pdf_to_normalized_source(content: bytes, extractor: PdfExtractor = extract_pdf_text) -> tuple[str, dict[str, JsonObject]]:
    extracted = extractor(content)
    pages = [page.strip() for page in extracted.split("\f") if page.strip()]
    if not pages:
        pages = [extracted.strip()]
    body_text = "\n".join(pages)
    text_dimension = text_quality(body_text)

    abstract_present = bool(re.search(r"(?im)^\s*abstract\b", body_text))
    heading_matches = re.findall(
        r"(?im)^\s*(?:\d+(?:\.\d+)*\s+)?(?:introduction|background|method(?:ology)?|"
        r"experiments?|results?|discussion|conclusion|related work|appendix)\s*$",
        body_text,
    )
    section_count = len(heading_matches)
    if not abstract_present and section_count == 0:
        structure_status, structure_score = "failed", 20
    elif not abstract_present or section_count < 2:
        structure_status, structure_score = "degraded", 60
    else:
        structure_status, structure_score = "pass", 90
    structure_dimension = quality_dimension(
        structure_status,
        structure_score,
        {"abstract_present": abstract_present, "recognized_headings": section_count, "pages": len(pages)},
        f"Detected {len(pages)} text pages.",
        f"Recognized {section_count} section headings; abstract present: {abstract_present}.",
    )

    equation_lines = len(
        re.findall(r"(?m)^.*(?:[=\u2211\u220f\u222b\u2264\u2265]|\b(?:argmax|argmin)\b).*$", body_text)
    )
    equations_dimension = (
        quality_dimension(
            "degraded",
            55,
            {"equation_like_lines": equation_lines},
            f"Detected {equation_lines} equation-like lines; PDF text extraction cannot preserve equation semantics reliably.",
        )
        if equation_lines
        else quality_dimension(
            "not_applicable", 100, {"equation_like_lines": 0}, "No equation-like lines detected in PDF text."
        )
    )

    figure_captions = len(re.findall(r"(?im)^\s*fig(?:ure)?\.?\s*\d+\b", body_text))
    figures_dimension = (
        quality_dimension(
            "degraded",
            50,
            {"captions": figure_captions, "visuals_extracted": 0},
            f"Detected {figure_captions} figure captions; pdftotext does not extract visual content.",
        )
        if figure_captions
        else quality_dimension(
            "not_applicable", 100, {"captions": 0, "visuals_extracted": 0}, "No figure captions detected."
        )
    )

    table_captions = len(re.findall(r"(?im)^\s*table\s*\d+\b", body_text))
    tables_dimension = (
        quality_dimension(
            "degraded",
            50,
            {"captions": table_captions},
            f"Detected {table_captions} table captions; PDF column alignment may be lossy.",
        )
        if table_captions
        else quality_dimension("not_applicable", 100, {"captions": 0}, "No table captions detected.")
    )

    lines = ["<!-- mary-normalized-source:v1 -->", ""]
    for page_number, page in enumerate(pages, start=1):
        lines.extend(
            [
                f"<!-- locator: pdf:p{page_number} -->",
                f"## Page {page_number}",
                "",
                page,
                "",
            ]
        )
    dimensions = {
        "text": text_dimension,
        "structure": structure_dimension,
        "equations": equations_dimension,
        "figures": figures_dimension,
        "tables": tables_dimension,
    }
    return "\n".join(lines).rstrip() + "\n", dimensions


def quality_gate(dimensions: dict[str, JsonObject]) -> tuple[str, list[str]]:
    blocking = [name for name in QUALITY_DIMENSIONS if dimensions[name]["status"] == "failed"]
    return ("blocked" if blocking else "pass"), blocking


def build_acquisition(
    locator: str,
    final_locator: str,
    source_format: str,
    content: bytes,
    normalized_source: str,
    dimensions: dict[str, JsonObject],
    attempts: list[JsonObject],
) -> JsonObject:
    gate, blocking = quality_gate(dimensions)
    return {
        "raw": content,
        "normalized_source": normalized_source,
        "report": {
            "parse_quality_schema": PARSE_QUALITY_SCHEMA,
            "source": {
                "locator": locator,
                "resolved_locator": final_locator,
                "format": source_format,
                "fingerprint": sha256_bytes(content),
                "raw_artifact": f"source.{source_format}",
                "normalized_artifact": "source.md",
            },
            "dimensions": dimensions,
            "gate": gate,
            "blocking_dimensions": blocking,
            "acquisition_attempts": attempts,
        },
    }


def parse_source_candidate(
    locator: str,
    final_locator: str,
    source_format: str,
    content: bytes,
    attempts: list[JsonObject],
    pdf_extractor: PdfExtractor,
) -> JsonObject:
    if source_format == "html":
        normalized, dimensions = html_to_normalized_source(content)
    elif source_format == "pdf":
        if not content.startswith(b"%PDF-"):
            raise PaperReadError("PDF source does not start with a PDF signature.")
        normalized, dimensions = pdf_to_normalized_source(content, pdf_extractor)
    else:
        raise PaperReadError(f"Unsupported source format: {source_format}")
    return build_acquisition(locator, final_locator, source_format, content, normalized, dimensions, attempts)


def detect_source_format(locator: str, content_type: str, content: bytes) -> str:
    suffix = Path(urlparse(locator).path).suffix.lower()
    if content.startswith(b"%PDF-") or content_type == "application/pdf" or suffix == ".pdf":
        return "pdf"
    prefix = content[:500].lower()
    if content_type in {"text/html", "application/xhtml+xml"} or suffix in {".html", ".htm"}:
        return "html"
    if b"<html" in prefix or b"<!doctype html" in prefix:
        return "html"
    raise PaperReadError("Source must be arXiv HTML, an HTML document, or a PDF.")


def acquire_source(
    locator: str,
    *,
    arxiv_id: str | None = None,
    fetcher: Fetcher = fetch_url,
    pdf_extractor: PdfExtractor = extract_pdf_text,
) -> JsonObject:
    source_locator = str(locator or "").strip()
    if not source_locator:
        raise PaperReadError("Source locator must be non-empty.")
    attempts: list[JsonObject] = []

    if arxiv_id:
        encoded_id = quote(arxiv_id, safe="/")
        html_url = f"https://arxiv.org/html/{encoded_id}"
        html_candidate: JsonObject | None = None
        try:
            content, content_type, final_url = fetcher(html_url)
            source_format = detect_source_format(final_url, content_type, content)
            if source_format != "html":
                raise PaperReadError(f"Expected HTML but received {source_format}.")
            attempts.append({"format": "html", "locator": html_url, "result": "selected"})
            html_candidate = parse_source_candidate(
                source_locator, final_url, "html", content, attempts, pdf_extractor
            )
            core_failed = any(
                html_candidate["report"]["dimensions"][name]["status"] == "failed"
                for name in ("text", "structure")
            )
            if not core_failed:
                return html_candidate
            attempts[-1]["result"] = "unusable"
            attempts[-1]["reason"] = "text or structure quality failed"
        except PaperReadError as exc:
            attempts.append({"format": "html", "locator": html_url, "result": "failed", "reason": str(exc)})

        pdf_url = f"https://arxiv.org/pdf/{encoded_id}"
        try:
            content, content_type, final_url = fetcher(pdf_url)
            source_format = detect_source_format(final_url, content_type, content)
            if source_format != "pdf":
                raise PaperReadError(f"Expected PDF but received {source_format}.")
            attempts.append({"format": "pdf", "locator": pdf_url, "result": "selected"})
            return parse_source_candidate(source_locator, final_url, "pdf", content, attempts, pdf_extractor)
        except PaperReadError as exc:
            attempts.append({"format": "pdf", "locator": pdf_url, "result": "failed", "reason": str(exc)})
            if html_candidate is not None:
                html_candidate["report"]["acquisition_attempts"] = attempts
                return html_candidate
            raise PaperReadError(f"arXiv HTML and PDF acquisition both failed: {exc}") from exc

    parsed = urlparse(source_locator)
    if parsed.scheme in {"http", "https"}:
        content, content_type, final_url = fetcher(source_locator)
    else:
        local_path = Path(unquote(parsed.path) if parsed.scheme == "file" else source_locator).expanduser().resolve()
        if not local_path.is_file():
            raise PaperReadError(f"Local source does not exist: {local_path}")
        if local_path.stat().st_size > MAX_SOURCE_BYTES:
            raise PaperReadError(f"Source exceeds the {MAX_SOURCE_BYTES // (1024 * 1024)} MiB limit.")
        content = local_path.read_bytes()
        content_type = ""
        final_url = str(local_path)
    source_format = detect_source_format(final_url, content_type, content)
    attempts.append({"format": source_format, "locator": final_url, "result": "selected"})
    return parse_source_candidate(source_locator, final_url, source_format, content, attempts, pdf_extractor)


def persist_acquisition(workspace: Path, acquisition: JsonObject) -> JsonObject:
    directory = Path(workspace)
    directory.mkdir(parents=True, exist_ok=True)
    report = acquisition["report"]
    raw_path = directory / report["source"]["raw_artifact"]
    atomic_write_bytes(raw_path, acquisition["raw"])
    atomic_write_text(directory / "source.md", acquisition["normalized_source"])
    atomic_write_text(directory / "parse-quality.json", json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    return report


def write_read_context(workspace: Path, paper_id: str, source_locator: str) -> JsonObject:
    directory = Path(workspace)
    report, report_fingerprint = load_quality_report(directory)
    context = {
        "read_context_schema": 1,
        "paper_id": paper_id,
        "source": {
            "locator": source_locator,
            "fingerprint": report["source"]["fingerprint"],
            "format": report["source"]["format"],
            "artifact": "source.md",
        },
        "parse_quality": {
            "report": "parse-quality.json",
            "report_fingerprint": report_fingerprint,
            "gate": report["gate"],
            "dimensions": {
                name: report["dimensions"][name]["status"] for name in QUALITY_DIMENSIONS
            },
        },
        "uncertainty_required_for": [
            name
            for name in QUALITY_DIMENSIONS
            if report["dimensions"][name]["status"] in {"degraded", "failed"}
        ],
    }
    atomic_write_text(directory / "read-context.json", json.dumps(context, ensure_ascii=False, indent=2) + "\n")
    return context


def require_nonempty_string(value: object, field: str) -> str:
    text = " ".join(str(value or "").split())
    if not text:
        raise PaperReadError(f"paper-notes field {field} must be non-empty.")
    return text


def require_string_list(value: object, field: str) -> list[str]:
    if not isinstance(value, list) or not value:
        raise PaperReadError(f"paper-notes field {field} must be a non-empty array.")
    return [require_nonempty_string(item, f"{field}[]") for item in value]


def extract_notes_ledger(notes_text: str) -> JsonObject:
    marker = "<!-- mary-paper-notes:v1 -->"
    marker_index = notes_text.find(marker)
    if marker_index < 0:
        raise PaperReadError(f"paper-notes.md must contain {marker}.")
    fenced = re.search(r"```json\s*(\{.*?\})\s*```", notes_text[marker_index:], flags=re.DOTALL)
    if fenced is None:
        raise PaperReadError("paper-notes.md must contain a fenced JSON ledger after the schema marker.")
    try:
        payload = json.loads(fenced.group(1))
    except json.JSONDecodeError as exc:
        raise PaperReadError(f"paper-notes JSON ledger is invalid: {exc}") from exc
    if not isinstance(payload, dict):
        raise PaperReadError("paper-notes JSON ledger must be an object.")
    return payload


def valid_locator(locator: str, source_format: str) -> bool:
    if source_format == "html":
        return bool(re.fullmatch(r"html#[A-Za-z0-9_.:-]+", locator))
    return bool(re.fullmatch(r"pdf:p[1-9][0-9]*", locator))


def validate_locators(value: object, field: str, source_format: str) -> list[str]:
    locators = require_string_list(value, field)
    invalid = [locator for locator in locators if not valid_locator(locator, source_format)]
    if invalid:
        raise PaperReadError(
            f"paper-notes field {field} contains invalid {source_format} locators: {', '.join(invalid)}."
        )
    return locators


def validate_claim(value: object, field: str, source_format: str) -> None:
    if not isinstance(value, dict):
        raise PaperReadError(f"paper-notes field {field} must be an object.")
    if set(value) != {"text", "locators"}:
        raise PaperReadError(f"paper-notes field {field} must contain exactly text and locators.")
    require_nonempty_string(value.get("text"), f"{field}.text")
    validate_locators(value.get("locators"), f"{field}.locators", source_format)


def load_quality_report(workspace: Path) -> tuple[JsonObject, str]:
    report_path = Path(workspace) / "parse-quality.json"
    if not report_path.is_file():
        raise PaperReadError("parse-quality.json is missing; run prepare-read first.")
    try:
        report = json.loads(report_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise PaperReadError(f"parse-quality.json is invalid: {exc}") from exc
    if not isinstance(report, dict) or report.get("parse_quality_schema") != PARSE_QUALITY_SCHEMA:
        raise PaperReadError(f"parse-quality.json must use parse_quality_schema {PARSE_QUALITY_SCHEMA}.")
    dimensions = report.get("dimensions")
    if not isinstance(dimensions, dict) or set(dimensions) != set(QUALITY_DIMENSIONS):
        raise PaperReadError(f"parse-quality dimensions must be exactly: {', '.join(QUALITY_DIMENSIONS)}.")
    for name in QUALITY_DIMENSIONS:
        item = dimensions[name]
        if not isinstance(item, dict) or item.get("status") not in QUALITY_STATUSES:
            raise PaperReadError(f"parse-quality dimension {name} has an invalid status.")
        if not isinstance(item.get("evidence"), list) or not item["evidence"]:
            raise PaperReadError(f"parse-quality dimension {name} requires evidence.")
    expected_gate, expected_blocking = quality_gate(dimensions)
    if report.get("gate") != expected_gate or report.get("blocking_dimensions") != expected_blocking:
        raise PaperReadError("parse-quality gate does not match the five-dimensional matrix.")
    return report, sha256_file(report_path)


def validate_paper_notes(
    workspace: Path,
    *,
    expected_paper_id: str,
    expected_locator: str,
    expected_source_fingerprint: str,
    override: object = None,
) -> JsonObject:
    directory = Path(workspace)
    notes_path = directory / "paper-notes.md"
    if not notes_path.is_file():
        raise PaperReadError("paper-notes.md is missing.")
    ledger = extract_notes_ledger(notes_path.read_text(encoding="utf-8"))
    expected_top_level = {
        "paper_notes_schema",
        "paper_id",
        "source",
        "bibliography",
        "research",
        "section_ledger",
        "parse_quality",
        "uncertainties",
    }
    if set(ledger) != expected_top_level:
        missing = sorted(expected_top_level - set(ledger))
        extra = sorted(set(ledger) - expected_top_level)
        raise PaperReadError(f"paper-notes top-level fields mismatch; missing={missing}, extra={extra}.")
    if ledger.get("paper_notes_schema") != PAPER_NOTES_SCHEMA:
        raise PaperReadError(f"paper_notes_schema must be {PAPER_NOTES_SCHEMA}.")
    if ledger.get("paper_id") != expected_paper_id:
        raise PaperReadError("paper-notes paper_id does not match the paper state.")

    report, report_fingerprint = load_quality_report(directory)
    report_source = report["source"]
    if report_source.get("fingerprint") != expected_source_fingerprint:
        raise PaperReadError("parse-quality source fingerprint does not match the current paper source.")
    source_format = str(report_source.get("format") or "")
    if source_format not in SOURCE_FORMATS:
        raise PaperReadError("parse-quality source format must be html or pdf.")

    source = ledger.get("source")
    if not isinstance(source, dict):
        raise PaperReadError("paper-notes source must be an object.")
    expected_source = {
        "locator": expected_locator,
        "fingerprint": expected_source_fingerprint,
        "format": source_format,
        "artifact": "source.md",
    }
    if source != expected_source:
        raise PaperReadError("paper-notes source must exactly match the current acquired source.")

    bibliography = ledger.get("bibliography")
    if not isinstance(bibliography, dict):
        raise PaperReadError("paper-notes bibliography must be an object.")
    if set(bibliography) != {"title", "authors", "year", "venue"}:
        raise PaperReadError("paper-notes bibliography fields must be exactly title, authors, year, and venue.")
    for field in ("title", "year", "venue"):
        require_nonempty_string(bibliography.get(field), f"bibliography.{field}")
    require_string_list(bibliography.get("authors"), "bibliography.authors")

    research = ledger.get("research")
    expected_research = {
        "background",
        "problem",
        "contributions",
        "method",
        "experiments",
        "limitations",
        "conclusions",
    }
    if not isinstance(research, dict) or set(research) != expected_research:
        raise PaperReadError(f"paper-notes research fields must be exactly: {', '.join(sorted(expected_research))}.")
    for field in ("background", "problem", "method", "experiments", "limitations", "conclusions"):
        validate_claim(research[field], f"research.{field}", source_format)
    contributions = research.get("contributions")
    if not isinstance(contributions, list) or not contributions:
        raise PaperReadError("paper-notes research.contributions must be a non-empty array.")
    for index, contribution in enumerate(contributions):
        validate_claim(contribution, f"research.contributions[{index}]", source_format)

    section_ledger = ledger.get("section_ledger")
    if not isinstance(section_ledger, list) or not section_ledger:
        raise PaperReadError("paper-notes section_ledger must be a non-empty array.")
    for index, section in enumerate(section_ledger):
        if not isinstance(section, dict):
            raise PaperReadError(f"paper-notes section_ledger[{index}] must be an object.")
        if set(section) != {"section", "locators", "findings"}:
            raise PaperReadError(
                f"paper-notes section_ledger[{index}] must contain exactly section, locators, and findings."
            )
        require_nonempty_string(section.get("section"), f"section_ledger[{index}].section")
        validate_locators(section.get("locators"), f"section_ledger[{index}].locators", source_format)
        require_string_list(section.get("findings"), f"section_ledger[{index}].findings")

    parse_quality = ledger.get("parse_quality")
    if not isinstance(parse_quality, dict):
        raise PaperReadError("paper-notes parse_quality must be an object.")
    expected_quality = {
        "report": "parse-quality.json",
        "report_fingerprint": report_fingerprint,
        "gate": report["gate"],
        "dimensions": {name: report["dimensions"][name]["status"] for name in QUALITY_DIMENSIONS},
    }
    if parse_quality != expected_quality:
        raise PaperReadError("paper-notes parse_quality must exactly mirror parse-quality.json.")

    uncertainties = ledger.get("uncertainties")
    if not isinstance(uncertainties, list) or not uncertainties:
        raise PaperReadError("paper-notes uncertainties must be a non-empty array.")
    covered_quality_dimensions: set[str] = set()
    for index, uncertainty in enumerate(uncertainties):
        if not isinstance(uncertainty, dict):
            raise PaperReadError(f"paper-notes uncertainties[{index}] must be an object.")
        if set(uncertainty) != {
            "question",
            "why_unresolved",
            "impact",
            "locators",
            "quality_dimensions",
        }:
            raise PaperReadError(
                f"paper-notes uncertainties[{index}] has an invalid field set."
            )
        for field in ("question", "why_unresolved", "impact"):
            require_nonempty_string(uncertainty.get(field), f"uncertainties[{index}].{field}")
        validate_locators(uncertainty.get("locators"), f"uncertainties[{index}].locators", source_format)
        dimensions = uncertainty.get("quality_dimensions", [])
        if not isinstance(dimensions, list) or any(name not in QUALITY_DIMENSIONS for name in dimensions):
            raise PaperReadError(f"paper-notes uncertainties[{index}].quality_dimensions is invalid.")
        covered_quality_dimensions.update(dimensions)
    uncertain_quality = {
        name
        for name in QUALITY_DIMENSIONS
        if report["dimensions"][name]["status"] in {"degraded", "failed"}
    }
    missing_uncertainties = sorted(uncertain_quality - covered_quality_dimensions)
    if missing_uncertainties:
        raise PaperReadError(
            "Every degraded or failed quality dimension must be acknowledged by an uncertainty: "
            + ", ".join(missing_uncertainties)
        )

    gate = report["gate"]
    override_record: JsonObject | None = None
    if gate == "blocked":
        if not isinstance(override, dict) or override.get("confirmed_by") != "user":
            raise PaperReadError(
                "Read completion is blocked by parse quality. Explicit user override and reason are required."
            )
        reason = require_nonempty_string(override.get("reason"), "quality_override.reason")
        if len(reason) < 10:
            raise PaperReadError("quality override reason must contain at least 10 characters.")
        override_record = {
            "quality_override_schema": 1,
            "confirmed_by": "user",
            "reason": reason,
            "blocking_dimensions": report["blocking_dimensions"],
            "parse_quality_report_fingerprint": report_fingerprint,
        }
        decision = "overridden"
    else:
        if override is not None:
            raise PaperReadError("Quality override is only legal when parse-quality gate is blocked.")
        decision = "pass"

    return {
        "notes_fingerprint": sha256_file(notes_path),
        "quality": {
            "decision": decision,
            "source_format": source_format,
            "report": "parse-quality.json",
            "report_fingerprint": report_fingerprint,
            "blocking_dimensions": report["blocking_dimensions"],
        },
        "override_record": override_record,
    }
