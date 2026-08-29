from __future__ import annotations

import json
from pathlib import Path
import sys


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from mw_paper_locators import parse_source_locator_blocks  # noqa: E402
from mw_paper_artifacts import (  # noqa: E402
    NORMALIZED_SOURCE_FILE,
    PARSE_QUALITY_FILE,
    SLIDES_CONTEXT_FILE,
    SOURCE_LOCATOR_FILE,
    SUMMARY_CONTEXT_FILE,
    SUMMARY_LEDGER_FILE,
    artifact_path,
    raw_source_file,
)
from mw_paper_sources import QUALITY_DIMENSIONS, quality_gate, sha256_file, write_read_context  # noqa: E402
from mw_paper_summary import summary_bundle_fingerprint  # noqa: E402
from mw_paper_slides import SLIDES_FILE  # noqa: E402


def write_read_fixture(
    workspace: Path,
    *,
    paper_id: str,
    locator: str,
    source_fingerprint: str,
    source_format: str = "html",
    statuses: dict[str, str] | None = None,
) -> str:
    workspace.mkdir(parents=True, exist_ok=True)
    selected_statuses = statuses or {
        "text": "pass",
        "structure": "pass",
        "equations": "not_applicable",
        "figures": "not_applicable",
        "tables": "not_applicable",
    }
    dimensions = {
        name: {
            "status": selected_statuses[name],
            "score": 100 if selected_statuses[name] in {"pass", "not_applicable"} else 50,
            "metrics": {"fixture": True},
            "evidence": [f"Fixture evidence for {name}."],
        }
        for name in QUALITY_DIMENSIONS
    }
    gate, blocking = quality_gate(dimensions)
    report = {
        "parse_quality_schema": 1,
        "source": {
            "locator": locator,
            "resolved_locator": locator,
            "format": source_format,
            "fingerprint": source_fingerprint,
            "raw_artifact": raw_source_file(source_format),
            "normalized_artifact": NORMALIZED_SOURCE_FILE,
        },
        "dimensions": dimensions,
        "gate": gate,
        "blocking_dimensions": blocking,
        "acquisition_attempts": [{"format": source_format, "locator": locator, "result": "selected"}],
    }
    locator_value = "html#S1" if source_format == "html" else "pdf:p1"
    artifact_path(workspace, raw_source_file(source_format), create_parent=True).write_bytes(
        b"<html>fixture</html>" if source_format == "html" else b"%PDF-fixture"
    )
    source_text = f"<!-- mary-normalized-source:v1 -->\n<!-- locator: {locator_value} -->\nFixture source.\n"
    if source_format == "html":
        source_text += "<!-- locator: html#S1.F1 -->\nFigure 1: Fixture method overview.\n"
    else:
        source_text = source_text.rstrip() + " Figure 1: Fixture method overview.\n"
    artifact_path(workspace, NORMALIZED_SOURCE_FILE, create_parent=True).write_text(source_text, encoding="utf-8")
    artifact_path(workspace, PARSE_QUALITY_FILE, create_parent=True).write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    context = write_read_context(workspace, paper_id, locator)
    degraded = [name for name in QUALITY_DIMENSIONS if selected_statuses[name] == "degraded"]
    claim = {"text": "Evidence-backed fixture claim.", "locators": [locator_value]}
    ledger = {
        "paper_notes_schema": 1,
        "paper_id": paper_id,
        "source": context["source"],
        "bibliography": {
            "title": "Fixture Paper",
            "authors": ["Fixture Author"],
            "year": "2026",
            "venue": "Fixture Venue",
        },
        "research": {
            "background": claim,
            "problem": claim,
            "contributions": [claim],
            "method": claim,
            "experiments": claim,
            "limitations": claim,
            "conclusions": claim,
        },
        "section_ledger": [
            {"section": "Fixture Section", "locators": [locator_value], "findings": ["Fixture finding."]}
        ],
        "parse_quality": context["parse_quality"],
        "uncertainties": [
            {
                "question": "Which details remain uncertain?",
                "why_unresolved": "The fixture preserves an explicit uncertainty contract.",
                "impact": "The uncertainty must be checked before downstream claims are trusted.",
                "locators": [locator_value],
                "quality_dimensions": degraded,
            }
        ],
    }
    notes = "<!-- mary-paper-notes:v1 -->\n```json\n" + json.dumps(ledger, ensure_ascii=False, indent=2) + "\n```\n"
    (workspace / "paper-notes.md").write_text(notes, encoding="utf-8")
    return sha256_file(workspace / "paper-notes.md")


def write_summary_fixture(workspace: Path, mutate: object = None) -> str:
    context = json.loads(artifact_path(workspace, SUMMARY_CONTEXT_FILE).read_text(encoding="utf-8"))
    source_format = context["inputs"]["source"]["format"]
    blocks = parse_source_locator_blocks(artifact_path(workspace, NORMALIZED_SOURCE_FILE), source_format)
    locator = context["allowed_source_locators"][0]
    evidence = blocks[locator][0]["content"][:120]
    claim = {
        "claim_id": "",
        "claim_text": "A grounded fixture claim with enough detail.",
        "evidence": evidence,
        "source_locators": [locator],
    }
    ledger = {
        "summary_ledger_schema": 1,
        "paper_id": context["paper_id"],
        "inputs": context["inputs"],
        "claims": [
            {**claim, "claim_id": "B01"},
            {**claim, "claim_id": "M01"},
            {**claim, "claim_id": "E01"},
        ],
    }
    if callable(mutate):
        mutate(ledger)
    summary = (
        "# A readable fixture summary\n\n"
        "## Background\n\n"
        "The paper begins from a concrete, evidence-backed research problem. [B01]\n\n"
        "## Method\n\n"
        "The method addresses that problem through a grounded mechanism rather than a list of components. [M01]\n\n"
        "Intuitively, the fixture maps an input $x$ to an output $y$ with $y=f(x)$, "
        "which leaves room to explain why each step matters.\n\n"
        "## Experiments\n\n"
        "The evaluation reports a directly supported experimental observation. [E01]\n"
    )
    (workspace / "summary.md").write_text(summary, encoding="utf-8")
    artifact_path(workspace, SUMMARY_LEDGER_FILE, create_parent=True).write_text(
        json.dumps(ledger, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return summary_bundle_fingerprint(workspace)


def write_slides_fixture(workspace: Path, mutate: object = None) -> str:
    context = json.loads(artifact_path(workspace, SLIDES_CONTEXT_FILE).read_text(encoding="utf-8"))
    figure = context["figure_catalog"][0]
    figure_id = figure["figure_id"]
    figure_locator = figure["source_locators"][0]

    def tex_escape(value: str) -> str:
        escaped = value
        for source, target in (
            ("\\", r"\textbackslash{}"),
            ("&", r"\&"),
            ("%", r"\%"),
            ("$", r"\$"),
            ("#", r"\#"),
            ("_", r"\_"),
            ("{", r"\{"),
            ("}", r"\}"),
        ):
            escaped = escaped.replace(source, target)
        return escaped

    figure_caption = tex_escape(figure["caption"])
    figure_metadata = json.dumps(
        {"figure_id": figure_id, "source_locator": figure_locator},
        ensure_ascii=False,
        separators=(",", ":"),
    )
    slides = rf"""\documentclass[aspectratio=169,10pt]{{beamer}}
\usepackage[UTF8,fontset=none]{{ctex}}
\usetheme{{mary-shanghaitech-red}}

% mary-slides:v2
\title[Fixture Paper]{{Fixture Paper}}
\subtitle{{A grounded research presentation}}
\VSPsetspeaker[汇报人]{{Mary Research}}{{ShanghaiTech University}}
\date{{}}

\begin{{document}}
\VSPtitleframe

\section{{Background}}
\begin{{frame}}{{Background and problem}}
% mary-section: background
% mary-claims: B01
The paper starts from a concrete research problem and motivates why the missing capability matters.
\begin{{itemize}}
  \item Existing approaches leave an important gap.
  \item The paper targets that gap directly.
\end{{itemize}}
\end{{frame}}

\section{{Method}}
\begin{{frame}}{{Method intuition}}
% mary-section: method
% mary-claims: M01
\begin{{columns}}[T,onlytextwidth]
  \begin{{column}}{{.43\textwidth}}
    The central mechanism maps an input $x$ to an output $y$:
    \[y=f_\theta(x).\]
    The information flow explains why each stage matters.
  \end{{column}}
  \begin{{column}}{{.53\textwidth}}
    % mary-figure: {figure_metadata}
    \MaryFigure{{}}{{{tex_escape(figure_id)}}}{{{figure_caption}}}
  \end{{column}}
\end{{columns}}
\end{{frame}}

\begin{{frame}}{{Method information flow}}
% mary-section: method
% mary-claims: M01
\begin{{columns}}[T,onlytextwidth]
  \begin{{column}}{{.32\textwidth}}\textbf{{Input}}\\Represent the observation.\end{{column}}
  \begin{{column}}{{.32\textwidth}}\textbf{{Mechanism}}\\Apply the grounded transformation.\end{{column}}
  \begin{{column}}{{.32\textwidth}}\textbf{{Output}}\\Produce the task prediction.\end{{column}}
\end{{columns}}
\end{{frame}}

\section{{Experiments}}
\begin{{frame}}{{Experimental evidence}}
% mary-section: experiments
% mary-claims: E01
The evaluation tests whether the proposed mechanism addresses the stated problem.
\begin{{itemize}}
  \item Report the main comparison before secondary ablations.
  \item Separate measured facts from interpretation.
  \item Keep the audience focused on one conclusion per page.
\end{{itemize}}
\end{{frame}}

\section{{Takeaways}}
\begin{{frame}}{{Takeaways}}
% mary-section: takeaways
% mary-claims: B01 M01 E01
\begin{{columns}}[T,onlytextwidth]
  \begin{{column}}{{.32\textwidth}}\textbf{{Problem}}\\A concrete gap motivates the work.\end{{column}}
  \begin{{column}}{{.32\textwidth}}\textbf{{Method}}\\The mechanism targets that gap.\end{{column}}
  \begin{{column}}{{.32\textwidth}}\textbf{{Evidence}}\\Experiments test the central claim.\end{{column}}
\end{{columns}}
\end{{frame}}

\VSPendframe{{谢谢}}
\end{{document}}
"""
    if callable(mutate):
        slides = mutate(slides)
    (workspace / SLIDES_FILE).write_text(slides, encoding="utf-8")
    return sha256_file(workspace / SLIDES_FILE)
