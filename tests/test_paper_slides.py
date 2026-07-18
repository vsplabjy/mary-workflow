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
from mw_paper_slides import (  # noqa: E402
    SLIDES_CONTEXT_SCHEMA,
    SLIDES_FILE,
    validate_slides,
)
from mw_paper_sources import sha256_file  # noqa: E402
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

    def complete(self, output_fingerprint: str | None = None) -> dict[str, object]:
        digest = output_fingerprint or sha256_file(self.workspace / SLIDES_FILE)
        return apply_paper_action(
            self.project,
            self.paper_id,
            {
                "action": "complete_stage",
                "data": {
                    "stage": "slides",
                    "artifact": SLIDES_FILE,
                    "output_fingerprint": digest,
                },
            },
        )

    def assert_rejected(self, message: str) -> None:
        with self.assertRaises(SystemExit) as context:
            self.complete()
        self.assertIn(message, str(context.exception))
        state = read_paper_state(self.project, self.paper_id)
        self.assertEqual(state["stages"]["slides"]["status"], "in_progress")

    def test_prepare_slides_writes_grounded_context_and_starts_stage(self) -> None:
        self.assertEqual(self.state["stages"]["slides"]["status"], "in_progress")
        self.assertEqual(self.context["slides_context_schema"], SLIDES_CONTEXT_SCHEMA)
        self.assertEqual(
            [item["claim_id"] for item in self.context["claim_catalog"]],
            ["B01", "M01", "E01"],
        )
        self.assertEqual(self.context["figure_catalog"][0]["figure_id"], "Figure 1")
        self.assertEqual(
            self.context["figure_catalog"][0]["source_locators"], ["html#S1.F1"]
        )
        self.assertTrue((self.workspace / "slides-context.json").is_file())
        self.assertTrue((self.workspace / "figures").is_dir())

        prepared = subprocess.run(
            [
                sys.executable,
                str(REPO_ROOT / "scripts/mw_paper.py"),
                "--project-root",
                str(self.project),
                "prepare-slides",
                "--paper-id",
                self.paper_id,
            ],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True,
        )
        self.assertIn("slides_target:", prepared.stdout)
        self.assertIn("figure_directory:", prepared.stdout)

    def test_valid_slides_complete_with_lint_metadata(self) -> None:
        digest = write_slides_fixture(self.workspace)
        state = self.complete()
        slides = state["stages"]["slides"]
        self.assertEqual(slides["status"], "complete")
        self.assertEqual(slides["artifact"], "slides.md")
        self.assertEqual(slides["output_fingerprint"], digest)
        self.assertEqual(slides["metadata"]["page_count"], 7)
        self.assertEqual(slides["metadata"]["section_page_counts"]["method"], 2)
        self.assertGreaterEqual(slides["metadata"]["layout_page_count"], 2)
        self.assertEqual(slides["metadata"]["figure_placeholder_count"], 1)
        self.assertEqual(slides["metadata"]["referenced_figure_ids"], ["Figure 1"])
        self.assertEqual(slides["metadata"]["math"], "katex")

    def test_frontmatter_requires_local_theme_katex_and_16_by_9(self) -> None:
        write_slides_fixture(
            self.workspace,
            lambda text: text.replace("math: katex", "math: mathjax"),
        )
        self.assert_rejected("frontmatter requires math: katex")

    def test_structure_requires_two_method_pages_and_ordered_sections(self) -> None:
        def remove_method_page(text: str) -> str:
            marker = "<!-- section: method -->"
            first = text.index(marker)
            second = text.index(marker, first + len(marker))
            tail = text[second:].replace(marker, "<!-- section: experiments -->", 1)
            tail = tail.replace("<!-- claims: M01 -->", "<!-- claims: E01 -->", 1)
            return text[:second] + tail

        write_slides_fixture(self.workspace, remove_method_page)
        self.assert_rejected("at least 2 method content page")

        write_slides_fixture(
            self.workspace,
            lambda text: text.replace("<!-- section: background -->", "<!-- section: experiments -->", 1),
        )
        self.assert_rejected("section experiments cannot cite B01")

    def test_claim_references_must_exist_and_stay_hidden(self) -> None:
        write_slides_fixture(
            self.workspace,
            lambda text: text.replace("<!-- claims: M01 -->", "<!-- claims: M99 -->", 1),
        )
        self.assert_rejected("unknown summary claim M99")

        write_slides_fixture(
            self.workspace,
            lambda text: text.replace(
                "The paper starts from a concrete research problem",
                "The paper starts from a concrete research problem [B01]",
                1,
            ),
        )
        self.assert_rejected("exposes summary claim ids")

    def test_figure_placeholder_requires_valid_id_locator_and_nodes(self) -> None:
        write_slides_fixture(
            self.workspace,
            lambda text: text.replace('data-figure="Figure 1"', 'data-figure="Figure 99"', 1),
        )
        self.assert_rejected("placeholder references unknown Figure 99")

        write_slides_fixture(
            self.workspace,
            lambda text: text.replace('data-source-locator="html#S1.F1"', 'data-source-locator="html#S1"', 1),
        )
        self.assert_rejected("placeholder locator does not resolve")

        write_slides_fixture(
            self.workspace,
            lambda text: text.replace("figure-placeholder__caption", "figure-caption", 1),
        )
        self.assert_rejected("requires number and caption nodes")

    def test_figure_text_without_placeholder_is_rejected(self) -> None:
        write_slides_fixture(
            self.workspace,
            lambda text: text.replace("figure-placeholder", "figure-slot"),
        )
        self.assert_rejected("references figures without placeholders: Figure 1")

    def test_layout_and_page_capacity_are_machine_gated(self) -> None:
        def remove_layouts(text: str) -> str:
            for layout in ("cols-2-64", "cols-3", "rows-2-37"):
                text = text.replace(layout, "fixedtitleA")
            return text

        write_slides_fixture(self.workspace, remove_layouts)
        self.assert_rejected("multi-panel layouts on at least two pages")

        write_slides_fixture(
            self.workspace,
            lambda text: text.replace(
                "The paper starts from a concrete research problem",
                "x" * 950,
                1,
            ),
        )
        self.assert_rejected("exceeds visible_characters limit")

    def test_invalid_local_and_remote_media_references_are_rejected(self) -> None:
        write_slides_fixture(
            self.workspace,
            lambda text: text.replace(
                "The paper starts from a concrete research problem",
                "![plot](https://example.com/plot.png)\n\nThe paper starts from a concrete research problem",
                1,
            ),
        )
        self.assert_rejected("image references must be local repository files")

        write_slides_fixture(
            self.workspace,
            lambda text: text.replace(
                "The paper starts from a concrete research problem",
                "![plot](figures/missing.png)\n\nThe paper starts from a concrete research problem",
                1,
            ),
        )
        self.assert_rejected("image does not exist: figures/missing.png")

        write_slides_fixture(
            self.workspace,
            lambda text: text.replace(
                "<!-- _class: fixedtitleA -->",
                "<!-- _class: fixedtitleA -->\n<!-- _backgroundImage: url(https://example.com/bg.png) -->",
                1,
            ),
        )
        self.assert_rejected("image references must be local repository files")

    def test_context_summary_and_declared_fingerprint_cannot_drift(self) -> None:
        write_slides_fixture(self.workspace)
        context_path = self.workspace / "slides-context.json"
        context = json.loads(context_path.read_text(encoding="utf-8"))
        context["presentation"]["math"] = "mathjax"
        context_path.write_text(json.dumps(context), encoding="utf-8")
        self.assert_rejected("slides-context.json is stale")

        prepare_slides(self.project, self.paper_id)
        write_slides_fixture(self.workspace)
        with self.assertRaises(SystemExit) as rejection:
            self.complete(fingerprint("f"))
        self.assertIn("output_fingerprint does not match slides.md", str(rejection.exception))

    def test_lint_and_complete_slides_cli(self) -> None:
        write_slides_fixture(self.workspace)
        linted = subprocess.run(
            [
                sys.executable,
                str(REPO_ROOT / "scripts/mw_paper.py"),
                "--project-root",
                str(self.project),
                "lint-slides",
                "--paper-id",
                self.paper_id,
            ],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True,
        )
        self.assertEqual(json.loads(linted.stdout)["lint"], "passed")

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
        )
        output = json.loads(completed.stdout)
        self.assertEqual(output["paper"]["stages"]["slides"]["status"], "complete")

    def test_direct_validator_reports_current_slides_fingerprint(self) -> None:
        digest = write_slides_fixture(self.workspace)
        state = read_paper_state(self.project, self.paper_id)
        report = validate_slides(
            self.workspace,
            paper_id=self.paper_id,
            source_format=state["stages"]["read"]["metadata"]["source_format"],
            source_fingerprint=state["source"]["fingerprint"],
            read_output_fingerprint=state["stages"]["read"]["output_fingerprint"],
            summary_output_fingerprint=state["stages"]["summary"]["output_fingerprint"],
        )
        self.assertEqual(report["slides_fingerprint"], digest)


if __name__ == "__main__":
    unittest.main()
