from __future__ import annotations

import copy
import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from mw_paper import (  # noqa: E402
    apply_paper_action,
    paper_directory,
    prepare_read,
    read_paper_state,
)
from mw_paper_sources import (  # noqa: E402
    PaperReadError,
    QUALITY_DIMENSIONS,
    acquire_source,
    html_to_normalized_source,
    pdf_to_normalized_source,
    sha256_file,
)


def good_html(label: str = "A") -> bytes:
    paragraph = (
        f"{label} This paper studies a reproducible research problem with explicit assumptions, "
        "a carefully defined method, controlled comparisons, quantitative results, and limitations. "
    ) * 18
    return f"""<!doctype html>
<html><body><article class="ltx_document">
<h1 id="title">A Contract-Tested Paper {label}</h1>
<div class="ltx_abstract"><p id="abstract">Abstract {paragraph}</p></div>
<section id="S1" class="ltx_section"><h2>1 Introduction</h2><p>{paragraph}</p></section>
<section id="S2" class="ltx_section"><h2>2 Method</h2><p>{paragraph}
<math alttext="y = f(x)"><mi>y</mi></math></p></section>
<section id="S3" class="ltx_section"><h2>3 Experiments</h2><p>{paragraph}</p>
<figure id="S3.F1"><figcaption class="ltx_caption">Figure 1: Controlled results.</figcaption></figure>
<figure id="S3.T1" class="ltx_table"><table class="ltx_tabular"><tr><td>1</td></tr></table>
<figcaption class="ltx_caption">Table 1: Quantitative results.</figcaption></figure>
</section>
<section id="S4" class="ltx_section"><h2>4 Limitations</h2><p>{paragraph}</p></section>
</article></body></html>""".encode("utf-8")


def bad_html() -> bytes:
    return b"<html><body><p>broken</p></body></html>"


def good_pdf_text() -> str:
    paragraph = (
        "This PDF page describes the problem, method, experimental protocol, numerical evidence, "
        "comparison baselines, observed limitations, and conclusions in enough detail for extraction. "
    ) * 22
    return (
        "Abstract\n" + paragraph + "\nIntroduction\n" + paragraph + "\nMethod\n"
        + paragraph + "\ny = f(x)\nExperiments\n" + paragraph
        + "\nFigure 1 Controlled results\nTable 1 Quantitative results\fConclusion\n" + paragraph
    )


def write_notes(
    workspace: Path,
    *,
    uncertainty_dimensions: list[str] | None = None,
    mutate: object = None,
) -> dict[str, object]:
    context = json.loads((workspace / "read-context.json").read_text(encoding="utf-8"))
    source_text = (workspace / "source.md").read_text(encoding="utf-8")
    locator_match = re.search(r"<!-- locator: ([^ ]+) -->", source_text)
    if locator_match is None:
        raise AssertionError("normalized source has no locator")
    locator = locator_match.group(1)
    claim = {"text": "The source supports this required research claim.", "locators": [locator]}
    required_quality_uncertainties = context["uncertainty_required_for"]
    ledger: dict[str, object] = {
        "paper_notes_schema": 1,
        "paper_id": context["paper_id"],
        "source": context["source"],
        "bibliography": {
            "title": "A Contract-Tested Paper",
            "authors": ["Mary Researcher"],
            "year": "2026",
            "venue": "arXiv",
        },
        "research": {
            "background": copy.deepcopy(claim),
            "problem": copy.deepcopy(claim),
            "contributions": [copy.deepcopy(claim)],
            "method": copy.deepcopy(claim),
            "experiments": copy.deepcopy(claim),
            "limitations": copy.deepcopy(claim),
            "conclusions": copy.deepcopy(claim),
        },
        "section_ledger": [
            {"section": "Introduction", "locators": [locator], "findings": ["A locatable finding."]}
        ],
        "parse_quality": context["parse_quality"],
        "uncertainties": [
            {
                "question": "Which source details still require manual confirmation?",
                "why_unresolved": "Close reading retains an explicit uncertainty even for clean parsing.",
                "impact": "Downstream claims must preserve this qualification.",
                "locators": [locator],
                "quality_dimensions": (
                    required_quality_uncertainties
                    if uncertainty_dimensions is None
                    else uncertainty_dimensions
                ),
            }
        ],
    }
    if callable(mutate):
        mutate(ledger)
    notes = "<!-- mary-paper-notes:v1 -->\n```json\n" + json.dumps(ledger, ensure_ascii=False, indent=2) + "\n```\n"
    (workspace / "paper-notes.md").write_text(notes, encoding="utf-8")
    return ledger


class SourceAcquisitionTests(unittest.TestCase):
    def test_html_parser_emits_five_passing_dimensions_and_locators(self) -> None:
        normalized, dimensions = html_to_normalized_source(good_html())
        self.assertEqual(tuple(dimensions), QUALITY_DIMENSIONS)
        self.assertEqual(dimensions["text"]["status"], "pass")
        self.assertEqual(dimensions["structure"]["status"], "pass")
        self.assertEqual(dimensions["equations"]["status"], "pass")
        self.assertEqual(dimensions["figures"]["status"], "degraded")
        self.assertEqual(dimensions["tables"]["status"], "pass")
        self.assertIn("<!-- locator: html#S2 -->", normalized)
        self.assertIn("y = f(x)", normalized)

    def test_latexml_equation_layout_table_is_not_a_scientific_table(self) -> None:
        html = good_html().replace(
            b"</section>",
            b'<table class="ltx_equation ltx_eqn_table"><tr><td>x = 1</td></tr></table></section>',
            1,
        )
        _, dimensions = html_to_normalized_source(html)
        self.assertEqual(dimensions["tables"]["metrics"]["tables"], 1)
        self.assertEqual(dimensions["tables"]["metrics"]["rows"], 1)

    def test_arxiv_html_is_preferred_without_pdf_request(self) -> None:
        requested: list[str] = []

        def fetcher(url: str) -> tuple[bytes, str, str]:
            requested.append(url)
            return good_html(), "text/html", url

        acquired = acquire_source("https://arxiv.org/abs/2401.00001", arxiv_id="2401.00001", fetcher=fetcher)
        self.assertEqual(requested, ["https://arxiv.org/html/2401.00001"])
        self.assertEqual(acquired["report"]["source"]["format"], "html")
        self.assertEqual(acquired["report"]["gate"], "pass")

    def test_arxiv_pdf_fallback_when_html_is_unavailable(self) -> None:
        requested: list[str] = []

        def fetcher(url: str) -> tuple[bytes, str, str]:
            requested.append(url)
            if "/html/" in url:
                raise PaperReadError("HTTP 404")
            return b"%PDF-fixture", "application/pdf", url

        acquired = acquire_source(
            "arXiv:2401.00002",
            arxiv_id="2401.00002",
            fetcher=fetcher,
            pdf_extractor=lambda _: good_pdf_text(),
        )
        self.assertEqual(
            requested,
            ["https://arxiv.org/html/2401.00002", "https://arxiv.org/pdf/2401.00002"],
        )
        self.assertEqual(acquired["report"]["source"]["format"], "pdf")
        self.assertEqual(acquired["report"]["acquisition_attempts"][0]["result"], "failed")

    def test_arxiv_pdf_fallback_when_html_core_quality_fails(self) -> None:
        requested: list[str] = []

        def fetcher(url: str) -> tuple[bytes, str, str]:
            requested.append(url)
            if "/html/" in url:
                return bad_html(), "text/html", url
            return b"%PDF-fixture", "application/pdf", url

        acquired = acquire_source(
            "2401.00003",
            arxiv_id="2401.00003",
            fetcher=fetcher,
            pdf_extractor=lambda _: good_pdf_text(),
        )
        self.assertEqual(acquired["report"]["source"]["format"], "pdf")
        self.assertEqual(acquired["report"]["acquisition_attempts"][0]["result"], "unusable")
        self.assertEqual(len(requested), 2)

    def test_pdf_quality_marks_lossy_scientific_elements_degraded(self) -> None:
        _, dimensions = pdf_to_normalized_source(b"%PDF-fixture", lambda _: good_pdf_text())
        self.assertEqual(dimensions["text"]["status"], "pass")
        self.assertEqual(dimensions["structure"]["status"], "pass")
        self.assertEqual(dimensions["equations"]["status"], "degraded")
        self.assertEqual(dimensions["figures"]["status"], "degraded")
        self.assertEqual(dimensions["tables"]["status"], "degraded")

    def test_bad_html_has_blocked_quality_gate(self) -> None:
        normalized, dimensions = html_to_normalized_source(bad_html())
        self.assertTrue(normalized)
        blocking = [name for name in QUALITY_DIMENSIONS if dimensions[name]["status"] == "failed"]
        self.assertEqual(blocking, ["text", "structure"])


class ReadContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.project = Path(self.tempdir.name)
        self.source_path = self.project / "paper.html"
        self.source_path.write_bytes(good_html())
        self.state, self.report = prepare_read(self.project, source_locator=self.source_path)
        self.paper_id = self.state["paper_id"]
        self.workspace = paper_directory(self.project, self.paper_id)

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def complete(self, override: dict[str, str] | None = None) -> dict[str, object]:
        data: dict[str, object] = {
            "stage": "read",
            "artifact": "paper-notes.md",
            "output_fingerprint": sha256_file(self.workspace / "paper-notes.md"),
        }
        if override is not None:
            data["quality_override"] = override
        return apply_paper_action(
            self.project,
            self.paper_id,
            {"action": "complete_stage", "data": data},
        )

    def test_prepare_read_writes_artifacts_and_starts_stage(self) -> None:
        self.assertEqual(self.state["stages"]["read"]["status"], "in_progress")
        self.assertEqual(self.report["source"]["format"], "html")
        for filename in ("source.html", "source.md", "parse-quality.json", "read-context.json"):
            self.assertTrue((self.workspace / filename).is_file(), filename)
        context = json.loads((self.workspace / "read-context.json").read_text(encoding="utf-8"))
        self.assertEqual(context["paper_id"], self.paper_id)
        self.assertEqual(context["source"]["fingerprint"], self.state["source"]["fingerprint"])
        self.assertEqual(set(context["parse_quality"]["dimensions"]), set(QUALITY_DIMENSIONS))

    def test_prepare_read_source_change_restarts_with_stale_lineage(self) -> None:
        first_fingerprint = self.state["source"]["fingerprint"]
        self.source_path.write_bytes(good_html("B"))
        state, _ = prepare_read(self.project, source_locator=self.source_path, paper_id=self.paper_id)
        self.assertNotEqual(state["source"]["fingerprint"], first_fingerprint)
        self.assertEqual(state["stages"]["read"]["status"], "in_progress")
        self.assertEqual(state["stages"]["read"]["attempts"], 2)
        self.assertEqual(
            state["stages"]["read"]["input_fingerprints"],
            {"source": state["source"]["fingerprint"]},
        )

    def test_valid_ledger_completes_read_and_records_quality_metadata(self) -> None:
        write_notes(self.workspace)
        state = self.complete()
        read = state["stages"]["read"]
        self.assertEqual(read["status"], "complete")
        self.assertEqual(read["artifact"], "paper-notes.md")
        self.assertEqual(read["metadata"]["decision"], "pass")
        self.assertEqual(read["metadata"]["source_format"], "html")
        self.assertEqual(read["output_fingerprint"], sha256_file(self.workspace / "paper-notes.md"))

    def test_empty_uncertainty_is_rejected_without_changing_stage(self) -> None:
        write_notes(self.workspace, mutate=lambda ledger: ledger.__setitem__("uncertainties", []))
        with self.assertRaises(SystemExit) as context:
            self.complete()
        self.assertIn("uncertainties must be a non-empty array", str(context.exception))
        state = read_paper_state(self.project, self.paper_id)
        self.assertEqual(state["stages"]["read"]["status"], "in_progress")
        self.assertEqual(state["audit"]["rejected_actions"], 1)

    def test_empty_required_research_field_is_rejected(self) -> None:
        def mutate(ledger: dict[str, object]) -> None:
            ledger["research"]["method"]["text"] = ""  # type: ignore[index]

        write_notes(self.workspace, mutate=mutate)
        with self.assertRaises(SystemExit) as context:
            self.complete()
        self.assertIn("research.method.text must be non-empty", str(context.exception))

    def test_declared_notes_fingerprint_must_match_artifact(self) -> None:
        write_notes(self.workspace)
        with self.assertRaises(SystemExit) as context:
            apply_paper_action(
                self.project,
                self.paper_id,
                {
                    "action": "complete_stage",
                    "data": {
                        "stage": "read",
                        "artifact": "paper-notes.md",
                        "output_fingerprint": "f" * 64,
                    },
                },
            )
        self.assertIn("does not match paper-notes.md", str(context.exception))

    def test_every_degraded_dimension_requires_an_uncertainty(self) -> None:
        pdf_path = self.project / "second.pdf"
        pdf_path.write_bytes(b"%PDF-second-fixture")
        state, report = prepare_read(
            self.project,
            source_locator=pdf_path,
            pdf_extractor=lambda _: good_pdf_text(),
        )
        self.assertEqual(report["gate"], "pass")
        workspace = paper_directory(self.project, state["paper_id"])
        write_notes(workspace, uncertainty_dimensions=[])
        with self.assertRaises(SystemExit) as context:
            apply_paper_action(
                self.project,
                state["paper_id"],
                {
                    "action": "complete_stage",
                    "data": {
                        "stage": "read",
                        "artifact": "paper-notes.md",
                        "output_fingerprint": sha256_file(workspace / "paper-notes.md"),
                    },
                },
            )
        self.assertIn("Every degraded or failed quality dimension", str(context.exception))
        self.assertIn("equations", str(context.exception))

    def test_source_and_quality_identity_mismatches_are_rejected(self) -> None:
        def mutate_source(ledger: dict[str, object]) -> None:
            ledger["source"]["fingerprint"] = "f" * 64  # type: ignore[index]

        write_notes(self.workspace, mutate=mutate_source)
        with self.assertRaises(SystemExit) as context:
            self.complete()
        self.assertIn("source must exactly match", str(context.exception))

        def mutate_quality(ledger: dict[str, object]) -> None:
            ledger["parse_quality"]["dimensions"]["text"] = "degraded"  # type: ignore[index]

        write_notes(self.workspace, mutate=mutate_quality)
        with self.assertRaises(SystemExit) as context:
            self.complete()
        self.assertIn("parse_quality must exactly mirror", str(context.exception))

    def test_override_is_rejected_when_quality_passes(self) -> None:
        write_notes(self.workspace)
        with self.assertRaises(SystemExit) as context:
            self.complete({"confirmed_by": "user", "reason": "The user explicitly accepted this risk."})
        self.assertIn("only legal when parse-quality gate is blocked", str(context.exception))

    def test_four_tamper_attempts_are_rejected_and_audited_cumulatively(self) -> None:
        write_notes(self.workspace, mutate=lambda ledger: ledger.__setitem__("uncertainties", []))
        with self.assertRaises(SystemExit) as context:
            self.complete()
        self.assertIn("uncertainties must be a non-empty array", str(context.exception))

        def mutate_quality(ledger: dict[str, object]) -> None:
            ledger["parse_quality"]["dimensions"]["text"] = "degraded"  # type: ignore[index]

        write_notes(self.workspace, mutate=mutate_quality)
        with self.assertRaises(SystemExit) as context:
            self.complete()
        self.assertIn("parse_quality must exactly mirror", str(context.exception))

        write_notes(self.workspace)
        with self.assertRaises(SystemExit) as context:
            apply_paper_action(
                self.project,
                self.paper_id,
                {
                    "action": "complete_stage",
                    "data": {
                        "stage": "read",
                        "artifact": "paper-notes.md",
                        "output_fingerprint": "f" * 64,
                    },
                },
            )
        self.assertIn("does not match paper-notes.md", str(context.exception))

        write_notes(self.workspace)
        with self.assertRaises(SystemExit) as context:
            self.complete({"confirmed_by": "user", "reason": "The user explicitly accepted this risk."})
        self.assertIn("only legal when parse-quality gate is blocked", str(context.exception))

        state = read_paper_state(self.project, self.paper_id)
        self.assertEqual(state["stages"]["read"]["status"], "in_progress")
        self.assertEqual(state["audit"]["action_counts"]["complete_stage"], 0)
        self.assertEqual(state["audit"]["rejected_actions"], 4)

    def test_complete_read_cli_validates_and_finishes(self) -> None:
        write_notes(self.workspace)
        completed = subprocess.run(
            [
                sys.executable,
                str(REPO_ROOT / "scripts/mw_paper.py"),
                "--project-root",
                str(self.project),
                "complete-read",
                "--paper-id",
                self.paper_id,
            ],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True,
        )
        self.assertEqual(json.loads(completed.stdout)["paper"]["stages"]["read"]["status"], "complete")


class QualityOverrideTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.project = Path(self.tempdir.name)
        source_path = self.project / "broken.html"
        source_path.write_bytes(bad_html())
        self.state, self.report = prepare_read(self.project, source_locator=source_path)
        self.paper_id = self.state["paper_id"]
        self.workspace = paper_directory(self.project, self.paper_id)
        write_notes(self.workspace)

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def completion_payload(self, override: object = None) -> dict[str, object]:
        data: dict[str, object] = {
            "stage": "read",
            "artifact": "paper-notes.md",
            "output_fingerprint": sha256_file(self.workspace / "paper-notes.md"),
        }
        if override is not None:
            data["quality_override"] = override
        return {"action": "complete_stage", "data": data}

    def test_blocked_quality_requires_explicit_override(self) -> None:
        self.assertEqual(self.report["gate"], "blocked")
        self.assertEqual(self.report["blocking_dimensions"], ["text", "structure"])
        with self.assertRaises(SystemExit) as context:
            apply_paper_action(self.project, self.paper_id, self.completion_payload())
        self.assertIn("Explicit user override", str(context.exception))
        state = read_paper_state(self.project, self.paper_id)
        self.assertEqual(state["stages"]["read"]["status"], "in_progress")

    def test_explicit_override_records_reason_file_and_state_fingerprint(self) -> None:
        state = apply_paper_action(
            self.project,
            self.paper_id,
            self.completion_payload(
                {"confirmed_by": "user", "reason": "The user inspected the original source and accepted the risk."}
            ),
        )
        metadata = state["stages"]["read"]["metadata"]
        self.assertEqual(metadata["decision"], "overridden")
        override_path = self.workspace / metadata["override_artifact"]
        self.assertTrue(override_path.is_file())
        self.assertEqual(metadata["override_fingerprint"], sha256_file(override_path))
        override = json.loads(override_path.read_text(encoding="utf-8"))
        self.assertEqual(override["confirmed_by"], "user")
        self.assertEqual(override["blocking_dimensions"], ["text", "structure"])


if __name__ == "__main__":
    unittest.main()
