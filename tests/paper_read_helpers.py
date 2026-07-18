from __future__ import annotations

import json
from html import escape
from pathlib import Path
import sys


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from mw_paper_locators import parse_source_locator_blocks  # noqa: E402
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
            "raw_artifact": f"source.{source_format}",
            "normalized_artifact": "source.md",
        },
        "dimensions": dimensions,
        "gate": gate,
        "blocking_dimensions": blocking,
        "acquisition_attempts": [{"format": source_format, "locator": locator, "result": "selected"}],
    }
    locator_value = "html#S1" if source_format == "html" else "pdf:p1"
    (workspace / f"source.{source_format}").write_bytes(
        b"<html>fixture</html>" if source_format == "html" else b"%PDF-fixture"
    )
    source_text = f"<!-- mary-normalized-source:v1 -->\n<!-- locator: {locator_value} -->\nFixture source.\n"
    if source_format == "html":
        source_text += "<!-- locator: html#S1.F1 -->\nFigure 1: Fixture method overview.\n"
    else:
        source_text = source_text.rstrip() + " Figure 1: Fixture method overview.\n"
    (workspace / "source.md").write_text(source_text, encoding="utf-8")
    (workspace / "parse-quality.json").write_text(
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
    context = json.loads((workspace / "summary-context.json").read_text(encoding="utf-8"))
    source_format = context["inputs"]["source"]["format"]
    blocks = parse_source_locator_blocks(workspace / "source.md", source_format)
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
    (workspace / "summary-ledger.json").write_text(
        json.dumps(ledger, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return summary_bundle_fingerprint(workspace)


def write_slides_fixture(workspace: Path, mutate: object = None) -> str:
    context = json.loads((workspace / "slides-context.json").read_text(encoding="utf-8"))
    figure = context["figure_catalog"][0]
    figure_id = escape(figure["figure_id"], quote=True)
    figure_locator = escape(figure["source_locators"][0], quote=True)
    figure_caption = escape(figure["caption"])
    slides = f"""---
marp: true
theme: mary-shanghaitech-red
size: 16:9
math: katex
paginate: true
footer: Mary Workflow · 科研组会
---

<!-- mary-slides:v1 -->
<!-- _class: cover_e -->
<!-- _footer: "" -->
<!-- _paginate: "" -->

# Fixture Paper
###### A grounded research presentation

<div class="speaker-meta"><span>汇报人</span> Mary Research</div>

---

<!-- section: background -->
<!-- claims: B01 -->
<!-- _class: fixedtitleA -->

## Background and problem

The paper starts from a concrete research problem and motivates why the missing capability matters.

- Existing approaches leave an important gap.
- The paper targets that gap directly.

---

<!-- section: method -->
<!-- claims: M01 -->
<!-- _class: cols-2-64 -->

## Method intuition

<div class="ldiv">

The central mechanism maps an input $x$ to an output $y$:

$$y=f_\\theta(x).$$

The left panel explains the information flow; the right panel reserves the paper's visual evidence.

</div>

<div class="rimg figure-placeholder" data-figure="{figure_id}" data-source-locator="{figure_locator}">
  <div class="figure-placeholder__number">{figure_id}</div>
  <div class="figure-placeholder__caption">{figure_caption}</div>
</div>

---

<!-- section: method -->
<!-- claims: M01 -->
<!-- _class: cols-3 -->

## Method information flow

<div class="ldiv"><strong>Input</strong><br>Represent the observation.</div>
<div class="mdiv"><strong>Mechanism</strong><br>Apply the grounded transformation.</div>
<div class="rdiv"><strong>Output</strong><br>Produce the task prediction.</div>

---

<!-- section: experiments -->
<!-- claims: E01 -->
<!-- _class: rows-2-37 -->

## Experimental evidence

<div class="tdiv">The evaluation tests whether the proposed mechanism addresses the stated problem.</div>
<div class="bdiv">

- Report the main comparison before secondary ablations.
- Separate measured facts from interpretation.
- Keep the audience focused on one conclusion per page.

</div>

---

<!-- section: takeaways -->
<!-- claims: B01 M01 E01 -->
<!-- _class: cols-3 -->

## Takeaways

<div class="ldiv"><strong>Problem</strong><br>A concrete gap motivates the work.</div>
<div class="mdiv"><strong>Method</strong><br>The mechanism directly targets that gap.</div>
<div class="rdiv"><strong>Evidence</strong><br>The experiments test the central claim.</div>

---

<!-- _class: lastpage -->
<!-- _footer: "" -->
<!-- _paginate: "" -->

###### 谢谢

<div class="icons">

- **问题**：研究缺口
- **方法**：核心机制
- **实验**：证据闭环

</div>
"""
    if callable(mutate):
        slides = mutate(slides)
    (workspace / SLIDES_FILE).write_text(slides, encoding="utf-8")
    return sha256_file(workspace / SLIDES_FILE)
