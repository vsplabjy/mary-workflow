from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from mw_paper import (  # noqa: E402
    apply_paper_action,
    create_paper,
    paper_directory,
    prepare_slides,
    prepare_summary,
    read_paper_state,
)
from mw_paper_artifacts import PARSE_QUALITY_FILE, SLIDES_CONTEXT_FILE, artifact_path  # noqa: E402
from mw_paper_slides import (  # noqa: E402
    HYPO_PREVIEW_FILE,
    PAPER_MAKEFILE,
    PAPER_MAKEFILE_MARKER,
    PROJECT_BEAMER_RELATIVE,
    PROJECT_THEME_RELATIVE,
    RESEARCH_MAKEFILE,
    RESEARCH_MAKEFILE_MARKER,
    SLIDES_CONTEXT_SCHEMA,
    SLIDES_FILE,
    PaperSlidesError,
    install_project_beamer_support,
    materialize_figure_assets,
    validate_slides,
    validate_slides_document,
)
from tests.paper_read_helpers import (  # noqa: E402
    write_read_fixture,
    write_slides_fixture,
    write_summary_fixture,
)


def fingerprint(character: str) -> str:
    return character * 64


class SlidesContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.project = Path(self.tempdir.name)
        self.locator = "https://arxiv.org/abs/2401.12345v2"
        self.paper_id = "arxiv-2401.12345v2"
        create_paper(self.project, self.locator, fingerprint("1"), self.paper_id)
        apply_paper_action(
            self.project,
            self.paper_id,
            {"action": "start_stage", "data": {"stage": "read"}},
        )
        self.workspace = paper_directory(self.project, self.paper_id)
        notes_fingerprint = write_read_fixture(
            self.workspace,
            paper_id=self.paper_id,
            locator=self.locator,
            source_fingerprint=fingerprint("1"),
        )
        apply_paper_action(
            self.project,
            self.paper_id,
            {
                "action": "complete_stage",
                "data": {
                    "stage": "read",
                    "artifact": "paper-notes.md",
                    "output_fingerprint": notes_fingerprint,
                },
            },
        )
        prepare_summary(self.project, self.paper_id)
        summary_fingerprint = write_summary_fixture(self.workspace)
        apply_paper_action(
            self.project,
            self.paper_id,
            {
                "action": "complete_stage",
                "data": {
                    "stage": "summary",
                    "artifact": "summary.md",
                    "output_fingerprint": summary_fingerprint,
                },
            },
        )
        self.state, self.context = prepare_slides(self.project, self.paper_id)

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def validate_current(self) -> dict[str, object]:
        state = read_paper_state(self.project, self.paper_id)
        return validate_slides(
            self.workspace,
            paper_id=self.paper_id,
            source_format=state["stages"]["read"]["metadata"]["source_format"],
            source_fingerprint=state["source"]["fingerprint"],
            read_output_fingerprint=state["stages"]["read"]["output_fingerprint"],
            summary_output_fingerprint=state["stages"]["summary"]["output_fingerprint"],
        )

    def assert_document_rejected(self, message: str, mutate: object) -> None:
        write_slides_fixture(self.workspace, mutate)
        context = json.loads(artifact_path(self.workspace, SLIDES_CONTEXT_FILE).read_text(encoding="utf-8"))
        with self.assertRaisesRegex(PaperSlidesError, message):
            validate_slides_document(
                self.workspace,
                (self.workspace / SLIDES_FILE).read_text(encoding="utf-8"),
                context,
            )

    def test_prepare_slides_installs_beamer_runtime_and_makefiles(self) -> None:
        self.assertEqual(self.state["stages"]["slides"]["status"], "in_progress")
        self.assertEqual(self.context["slides_context_schema"], SLIDES_CONTEXT_SCHEMA)
        self.assertEqual(self.context["presentation"]["engine"], "xelatex")
        self.assertEqual(self.context["presentation"]["math"], "tex")
        self.assertEqual(self.context["presentation"]["source_artifact"], "slides.tex")
        self.assertEqual(
            [item["claim_id"] for item in self.context["claim_catalog"]],
            ["B01", "M01", "E01"],
        )
        self.assertEqual(self.context["figure_catalog"][0]["figure_id"], "Figure 1")
        self.assertTrue((self.workspace / PAPER_MAKEFILE).is_file())
        self.assertTrue((self.workspace / HYPO_PREVIEW_FILE).is_file())
        self.assertTrue((self.project / RESEARCH_MAKEFILE).is_file())
        self.assertTrue((self.project / PROJECT_THEME_RELATIVE).is_file())
        self.assertTrue((self.project / PROJECT_BEAMER_RELATIVE / "assets" / "shanghaitech-master.png").is_file())

        paper_makefile = (self.workspace / PAPER_MAKEFILE).read_text(encoding="utf-8")
        research_makefile = (self.project / RESEARCH_MAKEFILE).read_text(encoding="utf-8")
        self.assertIn(PAPER_MAKEFILE_MARKER, paper_makefile)
        self.assertIn("latexmk", paper_makefile)
        self.assertIn("-xelatex", paper_makefile)
        self.assertIn("--audit-pdf", paper_makefile)
        self.assertNotIn("marp", paper_makefile.casefold())
        self.assertIn(RESEARCH_MAKEFILE_MARKER, research_makefile)
        self.assertIn("PAPER_ID ?=", research_makefile)
        self.assertIn('--project-root "$(PROJECT_ROOT)"', research_makefile)

    def test_valid_beamer_source_passes_grounding_and_layout_lint(self) -> None:
        digest = write_slides_fixture(self.workspace)
        report = self.validate_current()
        metadata = report["metadata"]
        self.assertEqual(report["slides_fingerprint"], digest)
        self.assertEqual(metadata["page_count"], 7)
        self.assertEqual(metadata["section_page_counts"]["method"], 2)
        self.assertGreaterEqual(metadata["layout_page_count"], 2)
        self.assertEqual(metadata["figure_placeholder_count"], 1)
        self.assertEqual(metadata["engine"], "xelatex")

    def test_preamble_structure_claims_and_capacity_are_gated(self) -> None:
        self.assert_document_rejected(
            "requires exactly one theme",
            lambda text: text.replace(
                r"\usetheme{mary-shanghaitech-red}", r"\usetheme{default}", 1
            ),
        )
        self.assert_document_rejected(
            "unknown summary claim M99",
            lambda text: text.replace("% mary-claims: M01", "% mary-claims: M99", 1),
        )
        self.assert_document_rejected(
            "exposes summary claim ids",
            lambda text: text.replace(
                "The paper starts from a concrete research problem",
                "The paper starts from a concrete research problem [B01]",
                1,
            ),
        )
        self.assert_document_rejected(
            "Beamer multi-panel layouts",
            lambda text: text.replace(r"\begin{columns}", r"\begin{singlecolumn}").replace(
                r"\end{columns}", r"\end{singlecolumn}"
            ),
        )
        self.assert_document_rejected(
            "exceeds visible_characters limit",
            lambda text: text.replace(
                "The paper starts from a concrete research problem", "x" * 950, 1
            ),
        )

    def test_figure_contract_requires_exact_locator_caption_and_asset(self) -> None:
        self.assert_document_rejected(
            "references unknown Figure 99",
            lambda text: text.replace('"figure_id":"Figure 1"', '"figure_id":"Figure 99"', 1),
        )
        self.assert_document_rejected(
            "locator does not resolve",
            lambda text: text.replace('"source_locator":"html#S1.F1"', '"source_locator":"html#S1"', 1),
        )
        self.assert_document_rejected(
            "caption does not exactly match Figure 1 context",
            lambda text: text.replace("Figure 1: Fixture method overview.", "Altered caption", 1),
        )

        image = self.workspace / "figures" / "figure-1-source.png"
        image.write_bytes(b"source-png")
        context = json.loads(
            artifact_path(self.workspace, SLIDES_CONTEXT_FILE).read_text(encoding="utf-8")
        )
        context["figure_assets"] = [
            {"figure_id": "Figure 1", "path": "figures/figure-1-source.png"}
        ]
        write_slides_fixture(self.workspace)
        source = (self.workspace / SLIDES_FILE).read_text(encoding="utf-8")
        with self.assertRaisesRegex(PaperSlidesError, "must embed its prepared source asset"):
            validate_slides_document(self.workspace, source, context)
        source = source.replace(
            r"\MaryFigure{}{Figure 1}",
            r"\MaryFigure{figures/figure-1-source.png}{Figure 1}",
        )
        validate_slides_document(self.workspace, source, context)

    def test_direct_images_must_be_local_and_keep_aspect_ratio(self) -> None:
        insertion = (
            r"\includegraphics[width=.5\linewidth]{figures/missing.png}"
            + "\nThe paper starts from a concrete research problem"
        )
        self.assert_document_rejected(
            "includegraphics must use keepaspectratio",
            lambda text: text.replace("The paper starts from a concrete research problem", insertion, 1),
        )
        insertion = (
            r"\includegraphics[width=.5\linewidth,keepaspectratio]{https://example.com/a.png}"
            + "\nThe paper starts from a concrete research problem"
        )
        self.assert_document_rejected(
            "image references must be local repository files",
            lambda text: text.replace("The paper starts from a concrete research problem", insertion, 1),
        )

    def test_prepare_materializes_latex_figure_asset(self) -> None:
        source_root = self.project / "paper-source"
        (source_root / "assets").mkdir(parents=True)
        (source_root / "assets" / "overview.png").write_bytes(b"source-png")
        (source_root / "main.tex").write_text(
            r"\begin{figure}\includegraphics{assets/overview}\caption{Pipeline}\end{figure}",
            encoding="utf-8",
        )
        artifact_path(self.workspace, PARSE_QUALITY_FILE).write_text(
            json.dumps(
                {
                    "source": {
                        "input_kind": "folder",
                        "locator": str(source_root),
                        "latex_entry": "main.tex",
                        "raw_artifact": "artifacts/source.pdf",
                    }
                }
            ),
            encoding="utf-8",
        )
        assets = materialize_figure_assets(
            self.workspace, [{"figure_id": "Figure 1", "source_locators": ["pdf:p1"]}]
        )
        self.assertEqual(assets[0]["path"], "figures/figure-1-source.png")
        self.assertEqual((self.workspace / assets[0]["path"]).read_bytes(), b"source-png")

    def test_runtime_and_generated_build_support_cannot_drift(self) -> None:
        write_slides_fixture(self.workspace)
        (self.project / PROJECT_THEME_RELATIVE).write_text("stale", encoding="utf-8")
        with self.assertRaisesRegex(PaperSlidesError, "Beamer runtime is stale"):
            self.validate_current()
        prepare_slides(self.project, self.paper_id)
        (self.workspace / PAPER_MAKEFILE).unlink()
        with self.assertRaisesRegex(PaperSlidesError, "Paper Makefile is missing or stale"):
            self.validate_current()

    def test_prepare_upgrades_legacy_mary_marp_makefiles(self) -> None:
        (self.workspace / PAPER_MAKEFILE).write_text(
            "# mary-paper-build:v1\nlegacy managed file\n", encoding="utf-8"
        )
        (self.project / RESEARCH_MAKEFILE).write_text(
            "# mary-research-build:v1\nlegacy managed file\n", encoding="utf-8"
        )
        prepare_slides(self.project, self.paper_id)
        self.assertIn(
            PAPER_MAKEFILE_MARKER,
            (self.workspace / PAPER_MAKEFILE).read_text(encoding="utf-8"),
        )
        self.assertIn(
            RESEARCH_MAKEFILE_MARKER,
            (self.project / RESEARCH_MAKEFILE).read_text(encoding="utf-8"),
        )

    def test_complete_slides_compiles_and_audits_real_pdf(self) -> None:
        write_slides_fixture(self.workspace)
        completed = subprocess.run(
            [
                sys.executable,
                str(REPO_ROOT / "scripts/mw_paper.py"),
                "--project-root",
                str(self.project),
                "complete-slides",
                "--paper-id",
                self.paper_id,
            ],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True,
            timeout=240,
        )
        output = json.loads(completed.stdout)
        slides = output["paper"]["stages"]["slides"]
        self.assertEqual(slides["status"], "complete")
        self.assertEqual(slides["artifact"], "slides.tex")
        self.assertEqual(output["pdf_audit"]["status"], "passed")
        self.assertEqual(output["pdf_audit"]["page_count"], 7)
        self.assertTrue((self.workspace / "build" / "slides.pdf").is_file())


class ProjectBeamerInstallTests(unittest.TestCase):
    def test_install_is_idempotent_and_preserves_unrelated_files(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            unrelated = project / ".mary-research" / "keep.txt"
            unrelated.parent.mkdir(parents=True)
            unrelated.write_text("keep", encoding="utf-8")
            first = install_project_beamer_support(project)
            second = install_project_beamer_support(project)
            self.assertEqual(first, second)
            self.assertEqual(unrelated.read_text(encoding="utf-8"), "keep")
            self.assertTrue((project / PROJECT_THEME_RELATIVE).is_file())
            self.assertEqual(len(first["runtime_files"]), 6)


if __name__ == "__main__":
    unittest.main()
