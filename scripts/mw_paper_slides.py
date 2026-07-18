#!/usr/bin/env python3
"""Grounded Marp slide artifacts and deterministic linting for Mary papers."""

from __future__ import annotations

from html import unescape
from html.parser import HTMLParser
import json
from pathlib import Path, PurePosixPath
import re
import shutil
import subprocess
import tempfile
from typing import Any

from mw_paper_locators import SourceLocatorError, validate_source_locator_index
from mw_paper_sources import sha256_file
from mw_paper_summary import (
    PaperSummaryError,
    SUMMARY_FILE,
    SUMMARY_LEDGER_FILE,
    load_summary_ledger,
    validate_summary,
)
from mw_runtime import atomic_write_text


SLIDES_CONTEXT_SCHEMA = 1
SLIDES_FILE = "slides.md"
SLIDES_CONTEXT_FILE = "slides-context.json"
FIGURES_DIR = "figures"
THEME_NAME = "mary-shanghaitech-red"
PLUGIN_ROOT = Path(__file__).resolve().parents[1]
THEME_PATH = PLUGIN_ROOT / "assets" / "marp" / "themes" / f"{THEME_NAME}.css"
MARP_CONFIG_PATH = PLUGIN_ROOT / "assets" / "marp" / "marp.config.mjs"

REQUIRED_FRONTMATTER = {
    "marp": "true",
    "theme": THEME_NAME,
    "size": "16:9",
    "math": "katex",
    "paginate": "true",
}
SECTION_ORDER = ("background", "method", "experiments", "takeaways")
SECTION_PREFIXES = {"background": "B", "method": "M", "experiments": "E"}
LAYOUT_CLASSES = {
    "cols-2",
    "cols-2-73",
    "cols-2-64",
    "cols-2-37",
    "cols-2-46",
    "cols-3",
    "rows-2",
    "rows-2-73",
    "rows-2-64",
    "rows-2-55",
    "rows-2-37",
    "rows-2-28",
    "pin-3",
}
IMAGE_PANEL_CLASSES = {"limg", "mimg", "rimg", "timg", "bimg"}
STRUCTURAL_CLASSES = {"trans", "toc_a", "toc_b"}
MAX_PAGES = 24
MAX_VISIBLE_CHARACTERS = 900
MAX_VISIBLE_LINES = 36
MAX_LIST_ITEMS = 8
MAX_CODE_LINES = 14

ARTIFACT_MARKER = "<!-- mary-slides:v1 -->"
CLASS_PATTERN = re.compile(r"<!--\s*_class:\s*([^>]+?)\s*-->", flags=re.IGNORECASE)
SECTION_PATTERN = re.compile(
    r"<!--\s*section:\s*(background|method|experiments|takeaways)\s*-->",
    flags=re.IGNORECASE,
)
CLAIMS_PATTERN = re.compile(r"<!--\s*claims:\s*([^>]+?)\s*-->", flags=re.IGNORECASE)
CLAIM_ID_PATTERN = re.compile(r"[BME][0-9]{2,}")
VISIBLE_CLAIM_PATTERN = re.compile(r"\[([BME][0-9]{2,})\]")
COMMENT_PATTERN = re.compile(r"<!--.*?-->", flags=re.DOTALL)
HTML_TAG_PATTERN = re.compile(r"<[^>]+>")
MARKDOWN_IMAGE_PATTERN = re.compile(r"!\[[^\]]*\]\(([^)]+)\)")
CSS_URL_PATTERN = re.compile(r"url\(\s*(['\"]?)(.*?)\1\s*\)", flags=re.IGNORECASE)
FIGURE_CAPTION_PATTERN = re.compile(
    r"(?:\bfig(?:ure)?\.?|图)\s*([0-9]+(?:[a-z])?)\s*[:.\-]?\s*([^\n]{0,220})",
    flags=re.IGNORECASE,
)
FIGURE_REFERENCE_PATTERN = re.compile(
    r"(?:\bfig(?:ure)?\.?|图)\s*([0-9]+(?:[a-z])?)",
    flags=re.IGNORECASE,
)

JsonObject = dict[str, Any]


class PaperSlidesError(ValueError):
    """A slides input, reference, layout, or artifact violated the P5 contract."""


def normalize_figure_id(token: str) -> str:
    return f"Figure {token.upper()}"


def extract_figure_catalog(blocks: dict[str, list[JsonObject]]) -> list[JsonObject]:
    catalog: dict[str, JsonObject] = {}
    for locator, spans in sorted(blocks.items()):
        for span in spans:
            content = str(span.get("content") or "")
            for match in FIGURE_CAPTION_PATTERN.finditer(content):
                figure_id = normalize_figure_id(match.group(1))
                caption = " ".join(match.group(0).split())[:280]
                item = catalog.setdefault(
                    figure_id,
                    {"figure_id": figure_id, "caption": caption, "source_locators": []},
                )
                if locator not in item["source_locators"]:
                    item["source_locators"].append(locator)
    return [catalog[key] for key in sorted(catalog, key=lambda value: (len(value), value))]


def build_slides_context(
    workspace: Path,
    *,
    paper_id: str,
    source_format: str,
    source_fingerprint: str,
    read_output_fingerprint: str,
    summary_output_fingerprint: str,
) -> JsonObject:
    directory = Path(workspace)
    try:
        summary_validation = validate_summary(
            directory,
            paper_id=paper_id,
            source_format=source_format,
            source_fingerprint=source_fingerprint,
            read_output_fingerprint=read_output_fingerprint,
        )
        ledger = load_summary_ledger(directory / SUMMARY_LEDGER_FILE)
    except PaperSummaryError as exc:
        raise PaperSlidesError(str(exc)) from exc
    if summary_validation["summary_bundle_fingerprint"] != summary_output_fingerprint:
        raise PaperSlidesError(
            "Current summary.md + summary-ledger.json bytes do not match the completed summary stage."
        )
    claim_catalog = [
        {
            "claim_id": claim["claim_id"],
            "section": {
                "B": "background",
                "M": "method",
                "E": "experiments",
            }[claim["claim_id"][0]],
            "claim_text": claim["claim_text"],
        }
        for claim in ledger["claims"]
    ]
    try:
        _, blocks, locator_fingerprint = validate_source_locator_index(
            directory,
            paper_id=paper_id,
            source_format=source_format,
            source_fingerprint=source_fingerprint,
        )
    except SourceLocatorError as exc:
        raise PaperSlidesError(str(exc)) from exc
    if not THEME_PATH.is_file():
        raise PaperSlidesError(f"Localized Marp theme is missing: {THEME_PATH}")

    metadata = summary_validation["metadata"]
    return {
        "slides_context_schema": SLIDES_CONTEXT_SCHEMA,
        "paper_id": paper_id,
        "inputs": {
            "summary": {
                "artifact": SUMMARY_FILE,
                "fingerprint": metadata["summary_body_fingerprint"],
            },
            "summary_ledger": {
                "artifact": SUMMARY_LEDGER_FILE,
                "fingerprint": metadata["summary_ledger_fingerprint"],
            },
            "summary_bundle": {"fingerprint": summary_output_fingerprint},
            "source_locators": {
                "artifact": "source-locators.json",
                "fingerprint": locator_fingerprint,
            },
        },
        "presentation": {
            "theme": THEME_NAME,
            "theme_fingerprint": sha256_file(THEME_PATH),
            "size": "16:9",
            "math": "katex",
            "figure_directory": FIGURES_DIR,
            "lint_limits": {
                "max_pages": MAX_PAGES,
                "max_visible_characters_per_page": MAX_VISIBLE_CHARACTERS,
                "max_visible_lines_per_page": MAX_VISIBLE_LINES,
                "max_list_items_per_page": MAX_LIST_ITEMS,
                "max_code_lines_per_page": MAX_CODE_LINES,
            },
        },
        "claim_catalog": claim_catalog,
        "figure_catalog": extract_figure_catalog(blocks),
    }


def write_slides_context(
    workspace: Path,
    *,
    paper_id: str,
    source_format: str,
    source_fingerprint: str,
    read_output_fingerprint: str,
    summary_output_fingerprint: str,
) -> JsonObject:
    directory = Path(workspace)
    context = build_slides_context(
        directory,
        paper_id=paper_id,
        source_format=source_format,
        source_fingerprint=source_fingerprint,
        read_output_fingerprint=read_output_fingerprint,
        summary_output_fingerprint=summary_output_fingerprint,
    )
    atomic_write_text(
        directory / SLIDES_CONTEXT_FILE,
        json.dumps(context, ensure_ascii=False, indent=2) + "\n",
    )
    (directory / FIGURES_DIR).mkdir(exist_ok=True)
    return context


def validate_slides_context(
    workspace: Path,
    *,
    paper_id: str,
    source_format: str,
    source_fingerprint: str,
    read_output_fingerprint: str,
    summary_output_fingerprint: str,
) -> tuple[JsonObject, str]:
    context_path = Path(workspace) / SLIDES_CONTEXT_FILE
    if not context_path.is_file():
        raise PaperSlidesError(f"{SLIDES_CONTEXT_FILE} is missing; run prepare-slides first.")
    try:
        stored = json.loads(context_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise PaperSlidesError(f"{SLIDES_CONTEXT_FILE} is invalid: {exc}") from exc
    expected = build_slides_context(
        workspace,
        paper_id=paper_id,
        source_format=source_format,
        source_fingerprint=source_fingerprint,
        read_output_fingerprint=read_output_fingerprint,
        summary_output_fingerprint=summary_output_fingerprint,
    )
    if stored != expected:
        raise PaperSlidesError(f"{SLIDES_CONTEXT_FILE} is stale or does not match current inputs.")
    return stored, sha256_file(context_path)


def parse_frontmatter(text: str) -> tuple[dict[str, str], str]:
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        raise PaperSlidesError("slides.md must begin with YAML frontmatter.")
    try:
        end = next(index for index, line in enumerate(lines[1:], start=1) if line.strip() == "---")
    except StopIteration as exc:
        raise PaperSlidesError("slides.md frontmatter is not closed by ---.") from exc
    frontmatter: dict[str, str] = {}
    for line in lines[1:end]:
        if not line.strip():
            continue
        if ":" not in line:
            raise PaperSlidesError(f"slides.md frontmatter line is not key: value: {line}")
        key, value = line.split(":", 1)
        key = key.strip()
        value = value.strip()
        if not key or key in frontmatter:
            raise PaperSlidesError(f"slides.md frontmatter has an empty or duplicate key: {key}")
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
            value = value[1:-1]
        frontmatter[key] = value
    for key, expected in REQUIRED_FRONTMATTER.items():
        if frontmatter.get(key, "").casefold() != expected.casefold():
            raise PaperSlidesError(f"slides.md frontmatter requires {key}: {expected}.")
    return frontmatter, "\n".join(lines[end + 1 :]).strip()


def page_classes(page: str) -> set[str]:
    classes: set[str] = set()
    for declaration in CLASS_PATTERN.findall(page):
        classes.update(declaration.split())
    return classes


def page_claims(page: str, page_number: int) -> list[str]:
    declarations = CLAIMS_PATTERN.findall(page)
    if len(declarations) != 1:
        raise PaperSlidesError(
            f"slides.md page {page_number} must contain exactly one <!-- claims: ... --> declaration."
        )
    tokens = [token for token in re.split(r"[\s,]+", declarations[0].strip()) if token]
    if not tokens or any(CLAIM_ID_PATTERN.fullmatch(token) is None for token in tokens):
        raise PaperSlidesError(f"slides.md page {page_number} has an invalid claims declaration.")
    if len(set(tokens)) != len(tokens):
        raise PaperSlidesError(f"slides.md page {page_number} has duplicate claim references.")
    return tokens


class SlideHTMLInspector(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.placeholders: list[JsonObject] = []
        self.image_sources: list[str] = []
        self._active: JsonObject | None = None
        self._depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = {name: value or "" for name, value in attrs}
        classes = set(attributes.get("class", "").split())
        if tag == "img":
            self.image_sources.append(attributes.get("src", ""))
        if self._active is not None:
            self._depth += 1
            if "figure-placeholder__number" in classes:
                self._active["has_number_node"] = True
            if "figure-placeholder__caption" in classes:
                self._active["has_caption_node"] = True
            return
        if tag == "div" and "figure-placeholder" in classes:
            self._active = {
                "figure_id": attributes.get("data-figure", ""),
                "source_locator": attributes.get("data-source-locator", ""),
                "classes": sorted(classes),
                "has_number_node": False,
                "has_caption_node": False,
                "text": [],
            }
            self._depth = 1

    def handle_endtag(self, tag: str) -> None:
        if self._active is None:
            return
        self._depth -= 1
        if self._depth == 0:
            self._active["text"] = " ".join(" ".join(self._active["text"]).split())
            self.placeholders.append(self._active)
            self._active = None

    def handle_data(self, data: str) -> None:
        if self._active is not None:
            self._active["text"].append(data)

    def close(self) -> None:
        super().close()
        if self._active is not None:
            raise PaperSlidesError("slides.md contains an unclosed figure-placeholder div.")


def validate_media_reference(workspace: Path, reference: str, page_number: int) -> None:
    value = reference.strip().strip("<>")
    if not value:
        raise PaperSlidesError(f"slides.md page {page_number} contains an empty image reference.")
    if re.match(r"^(?:https?:)?//", value, flags=re.IGNORECASE) or value.startswith("data:"):
        raise PaperSlidesError(
            f"slides.md page {page_number} image references must be local repository files: {value[:80]}"
        )
    path = PurePosixPath(value.replace("\\", "/"))
    if path.is_absolute() or ".." in path.parts:
        raise PaperSlidesError(f"slides.md page {page_number} has an unsafe image reference: {value}")
    target = (Path(workspace) / path.as_posix()).resolve()
    try:
        target.relative_to(Path(workspace).resolve())
    except ValueError as exc:
        raise PaperSlidesError(f"slides.md page {page_number} image escapes the paper workspace: {value}") from exc
    if not target.is_file():
        raise PaperSlidesError(f"slides.md page {page_number} image does not exist: {value}")


def visible_page_metrics(page: str) -> JsonObject:
    without_comments = COMMENT_PATTERN.sub("", page)
    without_tags = HTML_TAG_PATTERN.sub(" ", without_comments)
    visible = unescape(without_tags)
    compact = re.sub(r"\s+", "", visible)
    visible_lines = [line for line in visible.splitlines() if line.strip()]
    list_items = len(re.findall(r"(?m)^\s*(?:[-*+]|\d+[.)])\s+", visible))
    code_lines = 0
    in_code = False
    for line in visible.splitlines():
        if line.strip().startswith("```"):
            in_code = not in_code
        elif in_code and line.strip():
            code_lines += 1
    return {
        "visible_characters": len(compact),
        "visible_lines": len(visible_lines),
        "list_items": list_items,
        "code_lines": code_lines,
    }


def validate_page_capacity(page: str, page_number: int) -> JsonObject:
    metrics = visible_page_metrics(page)
    limits = {
        "visible_characters": MAX_VISIBLE_CHARACTERS,
        "visible_lines": MAX_VISIBLE_LINES,
        "list_items": MAX_LIST_ITEMS,
        "code_lines": MAX_CODE_LINES,
    }
    for field, limit in limits.items():
        if metrics[field] > limit:
            raise PaperSlidesError(
                f"slides.md page {page_number} exceeds {field} limit: {metrics[field]} > {limit}."
            )
    return metrics


def validate_slides_document(workspace: Path, text: str, context: JsonObject) -> JsonObject:
    _, body = parse_frontmatter(text)
    if body.count(ARTIFACT_MARKER) != 1:
        raise PaperSlidesError(f"slides.md must contain exactly one {ARTIFACT_MARKER} marker.")
    pages = [page.strip() for page in re.split(r"(?m)^---[ \t]*$", body)]
    if any(not page for page in pages):
        raise PaperSlidesError("slides.md contains an empty slide.")
    if len(pages) < 6 or len(pages) > MAX_PAGES:
        raise PaperSlidesError(f"slides.md must contain 6-{MAX_PAGES} slides; found {len(pages)}.")

    claim_sections = {item["claim_id"]: item["section"] for item in context["claim_catalog"]}
    figure_catalog = {item["figure_id"]: item for item in context["figure_catalog"]}
    section_counts = {section: 0 for section in SECTION_ORDER}
    section_sequence: list[str] = []
    referenced_claims: set[str] = set()
    referenced_figures: set[str] = set()
    layout_pages = 0
    placeholder_count = 0
    page_metrics: list[JsonObject] = []

    for index, page in enumerate(pages):
        page_number = index + 1
        classes = page_classes(page)
        headings_h1 = re.findall(r"(?m)^#[ \t]+\S.*$", page)
        headings_h2 = re.findall(r"(?m)^##[ \t]+\S.*$", page)
        if index == 0:
            if "cover_e" not in classes or len(headings_h1) != 1:
                raise PaperSlidesError("slides.md first slide must be a cover_e page with exactly one H1 title.")
            if SECTION_PATTERN.search(page) or CLAIMS_PATTERN.search(page):
                raise PaperSlidesError("slides.md cover page must not declare a content section or claims.")
        elif index == len(pages) - 1:
            if "lastpage" not in classes or not re.search(r"(?m)^######[ \t]+\S", page):
                raise PaperSlidesError("slides.md last slide must use lastpage with a non-empty H6 closing title.")
            if SECTION_PATTERN.search(page) or CLAIMS_PATTERN.search(page):
                raise PaperSlidesError("slides.md last page must not declare a content section or claims.")
        else:
            section_matches = [value.casefold() for value in SECTION_PATTERN.findall(page)]
            is_structural = bool(classes & STRUCTURAL_CLASSES)
            if is_structural and not section_matches:
                if CLAIMS_PATTERN.search(page):
                    raise PaperSlidesError(
                        f"slides.md structural page {page_number} must not declare claims without a section."
                    )
            else:
                if len(section_matches) != 1:
                    raise PaperSlidesError(
                        f"slides.md content page {page_number} requires exactly one section declaration."
                    )
                section = section_matches[0]
                section_counts[section] += 1
                section_sequence.append(section)
                if len(headings_h2) != 1:
                    raise PaperSlidesError(
                        f"slides.md content page {page_number} must contain exactly one H2 title."
                    )
                claims = page_claims(page, page_number)
                for claim_id in claims:
                    if claim_id not in claim_sections:
                        raise PaperSlidesError(
                            f"slides.md page {page_number} references unknown summary claim {claim_id}."
                        )
                    expected_prefix = SECTION_PREFIXES.get(section)
                    if expected_prefix and not claim_id.startswith(expected_prefix):
                        raise PaperSlidesError(
                            f"slides.md page {page_number} section {section} cannot cite {claim_id}."
                        )
                    referenced_claims.add(claim_id)
        if VISIBLE_CLAIM_PATTERN.search(COMMENT_PATTERN.sub("", page)):
            raise PaperSlidesError(
                f"slides.md page {page_number} exposes summary claim ids; keep them in <!-- claims: ... -->."
            )

        if classes & LAYOUT_CLASSES:
            layout_pages += 1
        inspector = SlideHTMLInspector()
        inspector.feed(page)
        inspector.close()
        page_placeholder_ids: set[str] = set()
        for placeholder in inspector.placeholders:
            figure_id = placeholder["figure_id"]
            if figure_id not in figure_catalog:
                raise PaperSlidesError(
                    f"slides.md page {page_number} placeholder references unknown {figure_id or 'figure'}."
                )
            if placeholder["source_locator"] not in figure_catalog[figure_id]["source_locators"]:
                raise PaperSlidesError(
                    f"slides.md page {page_number} placeholder locator does not resolve for {figure_id}."
                )
            if not set(placeholder["classes"]) & IMAGE_PANEL_CLASSES:
                raise PaperSlidesError(
                    f"slides.md page {page_number} figure-placeholder must use an image panel class."
                )
            if not placeholder["has_number_node"] or not placeholder["has_caption_node"]:
                raise PaperSlidesError(
                    f"slides.md page {page_number} placeholder requires number and caption nodes."
                )
            if figure_id not in placeholder["text"]:
                raise PaperSlidesError(
                    f"slides.md page {page_number} placeholder must visibly display {figure_id}."
                )
            page_placeholder_ids.add(figure_id)
            referenced_figures.add(figure_id)
            placeholder_count += 1

        page_figure_ids = {
            normalize_figure_id(token) for token in FIGURE_REFERENCE_PATTERN.findall(page)
        }
        unknown_figures = sorted(page_figure_ids - set(figure_catalog))
        if unknown_figures:
            raise PaperSlidesError(
                f"slides.md page {page_number} references unknown figures: {', '.join(unknown_figures)}."
            )
        missing_placeholders = sorted(page_figure_ids - page_placeholder_ids)
        if missing_placeholders:
            raise PaperSlidesError(
                f"slides.md page {page_number} references figures without placeholders: "
                + ", ".join(missing_placeholders)
                + "."
            )

        media_references = [match.group(1).split()[0] for match in MARKDOWN_IMAGE_PATTERN.finditer(page)]
        media_references.extend(match.group(2).strip() for match in CSS_URL_PATTERN.finditer(page))
        media_references.extend(inspector.image_sources)
        for reference in media_references:
            validate_media_reference(workspace, reference, page_number)
        page_metrics.append({"page": page_number, **validate_page_capacity(page, page_number)})

    ranks = [SECTION_ORDER.index(section) for section in section_sequence]
    if ranks != sorted(ranks):
        raise PaperSlidesError("slides.md sections must progress background -> method -> experiments -> takeaways.")
    for required, minimum in (("background", 1), ("method", 2), ("experiments", 1)):
        if section_counts[required] < minimum:
            raise PaperSlidesError(
                f"slides.md requires at least {minimum} {required} content page(s)."
            )
    if section_counts["method"] < max(section_counts["background"], section_counts["experiments"]):
        raise PaperSlidesError("slides.md must keep Method at least as detailed as Background and Experiments.")
    if layout_pages < 2:
        raise PaperSlidesError("slides.md must use VSP-Marp multi-panel layouts on at least two pages.")
    if figure_catalog and placeholder_count == 0:
        raise PaperSlidesError("slides.md must include at least one placeholder from the Figure catalog.")
    missing_claim_families = [
        prefix for prefix in ("B", "M", "E") if not any(claim.startswith(prefix) for claim in referenced_claims)
    ]
    if missing_claim_families:
        raise PaperSlidesError(
            "slides.md must cite background, method, and experiment claim families; missing: "
            + ", ".join(missing_claim_families)
            + "."
        )

    return {
        "page_count": len(pages),
        "section_page_counts": section_counts,
        "layout_page_count": layout_pages,
        "claim_reference_count": len(referenced_claims),
        "referenced_claim_ids": sorted(referenced_claims),
        "figure_placeholder_count": placeholder_count,
        "referenced_figure_ids": sorted(referenced_figures),
        "page_metrics": page_metrics,
    }


def validate_slides(
    workspace: Path,
    *,
    paper_id: str,
    source_format: str,
    source_fingerprint: str,
    read_output_fingerprint: str,
    summary_output_fingerprint: str,
) -> JsonObject:
    directory = Path(workspace)
    slides_path = directory / SLIDES_FILE
    if not slides_path.is_file():
        raise PaperSlidesError(f"{SLIDES_FILE} is missing.")
    context, context_fingerprint = validate_slides_context(
        directory,
        paper_id=paper_id,
        source_format=source_format,
        source_fingerprint=source_fingerprint,
        read_output_fingerprint=read_output_fingerprint,
        summary_output_fingerprint=summary_output_fingerprint,
    )
    report = validate_slides_document(
        directory,
        slides_path.read_text(encoding="utf-8"),
        context,
    )
    return {
        "slides_fingerprint": sha256_file(slides_path),
        "metadata": {
            "slides_context_schema": SLIDES_CONTEXT_SCHEMA,
            "slides_context": SLIDES_CONTEXT_FILE,
            "slides_context_fingerprint": context_fingerprint,
            "theme": THEME_NAME,
            "theme_fingerprint": context["presentation"]["theme_fingerprint"],
            "math": "katex",
            "size": "16:9",
            **report,
        },
    }


def run_marp_smoke(workspace: Path) -> JsonObject:
    directory = Path(workspace)
    slides_path = directory / SLIDES_FILE
    marp = shutil.which("marp")
    if marp:
        command = [marp]
    else:
        npx = shutil.which("npx")
        if npx is None:
            raise PaperSlidesError("Marp smoke compile requires marp or npx on PATH.")
        command = [npx, "--offline", "--yes", "@marp-team/marp-cli@4.3.1"]
    with tempfile.TemporaryDirectory(prefix="mary-marp-smoke-") as temporary:
        output = Path(temporary) / "slides.html"
        completed = subprocess.run(
            [
                *command,
                "--config-file",
                str(MARP_CONFIG_PATH),
                str(slides_path),
                "--output",
                str(output),
            ],
            cwd=directory,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=90,
            check=False,
        )
        if completed.returncode != 0 or not output.is_file():
            detail = " ".join((completed.stderr or completed.stdout).split())[-500:]
            raise PaperSlidesError(f"Optional Marp smoke compile failed: {detail or 'no output'}")
    return {"status": "passed", "runner": Path(command[0]).name}
