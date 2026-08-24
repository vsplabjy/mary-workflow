#!/usr/bin/env python3
"""Learner-facing reading artifacts and their Notion page composition."""

from __future__ import annotations

import hashlib
from pathlib import Path
import re
from typing import Any

from mw_runtime import atomic_write_text


READING_FILE = "reading.md"
READING_MARKER = "<!-- mary-reading:v1 -->"
READING_SUMMARY_FILE = "reading-summary.md"
READING_SUMMARY_MARKER = "<!-- mary-reading-summary:v1 -->"
NOTION_READING_MARKER = "<!-- mary-notion-paper-reading:v1 -->"
NOTION_ORIGINAL_PAPER_MARKER = "<!-- mary-notion-paper-original:v1 -->"
NOTION_ORIGINAL_PAPER_TITLE = "Original paper"

SUMMARY_SECTION_HEADINGS = (
    "一句话概括",
    "背景与问题",
    "方法",
    "Related Work（简略）",
    "Experiments（简略）",
    "结论与开放问题",
)
PLACEHOLDER_PATTERN = re.compile(r"(?:\[待补充[^\]]*\]|\[请[^\]]*\]|TODO|TBD)", flags=re.IGNORECASE)
HEADING_PATTERN = re.compile(r"^##[ \t]+(.+?)[ \t]*#*[ \t]*$", flags=re.MULTILINE)
H1_PATTERN = re.compile(r"^#[ \t]+(.+?)[ \t]*#*[ \t]*$", flags=re.MULTILINE)
CJK_PATTERN = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff]")
PARENTHETICAL_CJK_PATTERN = re.compile(
    r"(?:\([^\n)]*[\u3400-\u4dbf\u4e00-\u9fff][^\n)]*\)|（[^\n）]*[\u3400-\u4dbf\u4e00-\u9fff][^\n）]*）)"
)
OPEN_QUESTION_SUMMARY = "<summary>Open question</summary>"
READER_NOTES_SUMMARY = "<summary>Reader notes</summary>"


class PaperReadingError(ValueError):
    """A learner-facing reading artifact is incomplete or malformed."""


def sha256_file(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def reading_title(reading_markdown: str) -> str:
    match = H1_PATTERN.search(reading_markdown)
    return " ".join(match.group(1).split()) if match else "Paper Reading"


def strip_document_title(markdown: str, marker: str) -> str:
    """Remove a Mary marker and its optional first H1 for a Notion page body."""
    text = markdown.replace(marker, "", 1).strip()
    match = H1_PATTERN.search(text)
    if match is not None and not text[: match.start()].strip():
        text = text[match.end() :].lstrip("\n")
    return text.strip()


def reading_summary_template(reading_markdown: str) -> str:
    title = reading_title(reading_markdown)
    return f"""{READING_SUMMARY_MARKER}

# {title} - 中文论文导读

## 一句话概括

[待补充：用中文概括论文解决的问题、核心想法与主要结论；专业名词保持 English。]

## 背景与问题

[待补充：解释任务背景、已有方法的缺口，以及作者为何需要这个设计。]

## 方法

### 设计动机

[待补充：从 `reading.md` 和 `artifacts/source.md` 解释每个关键设计的原因。]

### 信息流与关键步骤

[待补充：按输入、表示、模块交互、输出的顺序详细讲解 Method；保留公式和 English technical terms。]

### 关键模块、训练目标与权衡

[待补充：说明组件作用、loss 或优化目标、适用条件和 trade-offs。]

## Related Work（简略）

[待补充：只交代论文与最相关方向的关系，不展开综述。]

## Experiments（简略）

[待补充：只说明 datasets、主要比较和作者声称的结论；不要复述全部指标。]

## 结论与开放问题

[待补充：概括 takeaways，并保留需要回看原文或图表才能回答的问题。]
"""


def write_reading_summary_draft(workspace: Path, reading_markdown: str) -> Path:
    path = Path(workspace) / READING_SUMMARY_FILE
    atomic_write_text(path, reading_summary_template(reading_markdown))
    return path


def _section_bodies(markdown: str) -> dict[str, str]:
    matches = list(HEADING_PATTERN.finditer(markdown))
    sections: dict[str, str] = {}
    for index, match in enumerate(matches):
        heading = " ".join(match.group(1).split())
        end = matches[index + 1].start() if index + 1 < len(matches) else len(markdown)
        sections[heading] = markdown[match.end() : end].strip()
    return sections


def validate_reading_summary(workspace: Path) -> dict[str, Any]:
    path = Path(workspace) / READING_SUMMARY_FILE
    if not path.is_file():
        raise PaperReadingError(f"{READING_SUMMARY_FILE} is missing.")
    text = path.read_text(encoding="utf-8")
    if READING_SUMMARY_MARKER not in text:
        raise PaperReadingError(f"{READING_SUMMARY_FILE} must contain {READING_SUMMARY_MARKER}.")
    if PLACEHOLDER_PATTERN.search(text):
        raise PaperReadingError(f"{READING_SUMMARY_FILE} still contains a draft placeholder.")
    sections = _section_bodies(text)
    missing = [heading for heading in SUMMARY_SECTION_HEADINGS if not sections.get(heading)]
    if missing:
        raise PaperReadingError(
            f"{READING_SUMMARY_FILE} requires non-empty sections: {', '.join(missing)}."
        )
    method_text = sections["方法"]
    method_cjk = len(CJK_PATTERN.findall(method_text))
    total_cjk = len(CJK_PATTERN.findall(text))
    if total_cjk < 300 or method_cjk < 150:
        raise PaperReadingError(
            f"{READING_SUMMARY_FILE} must provide a Chinese explanation with at least 300 Chinese "
            "characters overall and 150 in 方法."
        )
    if len(method_text) <= len(sections["Related Work（简略）"]) or len(method_text) <= len(sections["Experiments（简略）"]):
        raise PaperReadingError(
            f"{READING_SUMMARY_FILE} must explain 方法 in more detail than Related Work and Experiments."
        )
    return {
        "artifact": READING_SUMMARY_FILE,
        "fingerprint": sha256_file(path),
        "title": reading_title(text),
    }


def validate_reading_document(workspace: Path) -> dict[str, Any]:
    """Reject an unchanged English draft before it is delivered as a reading aid."""
    path = Path(workspace) / READING_FILE
    if not path.is_file():
        raise PaperReadingError(f"{READING_FILE} is missing.")
    text = path.read_text(encoding="utf-8")
    if READING_MARKER not in text:
        raise PaperReadingError(f"{READING_FILE} must contain {READING_MARKER}.")
    annotations = PARENTHETICAL_CJK_PATTERN.findall(text)
    annotation_text = "".join(annotations)
    chinese_characters = len(CJK_PATTERN.findall(annotation_text))
    if len(annotations) < 2 or chinese_characters < 60:
        raise PaperReadingError(
            f"{READING_FILE} must contain at least two Chinese parenthetical annotations and 60 Chinese characters."
        )
    remaining_text = PARENTHETICAL_CJK_PATTERN.sub("", text)
    if CJK_PATTERN.search(remaining_text):
        raise PaperReadingError(
            f"{READING_FILE} may contain Chinese only inside parenthetical annotations after the original English."
        )
    if OPEN_QUESTION_SUMMARY not in text or READER_NOTES_SUMMARY not in text:
        raise PaperReadingError(
            f"{READING_FILE} must retain empty Open question and Reader notes areas for post-reading reflection."
        )
    return {
        "artifact": READING_FILE,
        "fingerprint": sha256_file(path),
        "annotations": len(annotations),
        "chinese_characters": chinese_characters,
    }


def render_notion_reading_page(reading_markdown: str, summary_markdown: str) -> str:
    """Build the parent Notion page body, leaving the annotated paper to a child page."""
    chinese = strip_document_title(summary_markdown, READING_SUMMARY_MARKER)
    if not chinese:
        raise PaperReadingError("reading-summary.md has no body to place in Notion.")
    return (
        f"{NOTION_READING_MARKER}\n\n"
        "## 中文概括\n\n"
        f"{chinese}\n"
    )


def render_notion_original_paper_page(reading_markdown: str) -> str:
    """Build the annotated original-paper child page without its local document H1."""
    english = strip_document_title(reading_markdown, READING_MARKER)
    if not english:
        raise PaperReadingError("reading.md has no body to place in Notion.")
    return f"{NOTION_ORIGINAL_PAPER_MARKER}\n\n{english}\n"
