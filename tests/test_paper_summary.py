from __future__ import annotations

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
    PaperError,
    apply_paper_action,
    create_paper,
    paper_directory,
    prepare_summary,
    read_paper_state,
)
from mw_paper_locators import (  # noqa: E402
    SourceLocatorError,
    build_source_locator_index,
    evidence_resolves,
    parse_source_locator_blocks,
)
from mw_paper_sources import extract_notes_ledger, sha256_file  # noqa: E402
from tests.paper_read_helpers import write_read_fixture, write_summary_fixture  # noqa: E402


def fingerprint(character: str) -> str:
    return character * 64


def write_notes_ledger(path: Path, ledger: dict[str, object]) -> None:
    content = "<!-- mary-paper-notes:v1 -->\n```json\n" + json.dumps(ledger, ensure_ascii=False, indent=2) + "\n```\n"
    path.write_text(content, encoding="utf-8")


def complete_fixture_read(project: Path, paper_id: str, locator: str, source_fingerprint: str) -> dict[str, object]:
    apply_paper_action(project, paper_id, {"action": "start_stage", "data": {"stage": "read"}})
    workspace = paper_directory(project, paper_id)
    notes_fingerprint = write_read_fixture(
        workspace,
        paper_id=paper_id,
        locator=locator,
        source_fingerprint=source_fingerprint,
    )
    return apply_paper_action(
        project,
        paper_id,
        {
            "action": "complete_stage",
            "data": {
                "stage": "read",
                "artifact": "paper-notes.md",
                "output_fingerprint": notes_fingerprint,
            },
        },
    )


class SourceLocatorContractTests(unittest.TestCase):
    def test_html_index_records_duplicate_spans_lines_and_fingerprints(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            (workspace / "source.md").write_text(
                "<!-- mary-normalized-source:v1 -->\n"
                "<!-- locator: html#S1 -->\nFirst evidence block.\n"
                "<!-- locator: html#S1 -->\nSecond evidence block.\n"
                "<!-- locator: html#S2 -->\nThird evidence block.\n",
                encoding="utf-8",
            )
            index, blocks = build_source_locator_index(
                workspace,
                paper_id="local-fixture",
                source_format="html",
                source_fingerprint=fingerprint("1"),
            )
            self.assertEqual(index["source_locator_schema"], 1)
            self.assertEqual(len(index["locators"]["html#S1"]), 2)
            self.assertEqual(index["locators"]["html#S1"][0]["line_start"], 3)
            self.assertEqual(len(index["locators"]["html#S1"][0]["content_fingerprint"]), 64)
            self.assertTrue(evidence_resolves("Second evidence block.", ["html#S1"], blocks))

    def test_pdf_page_locators_are_machine_resolvable(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "source.md"
            source.write_text(
                "<!-- locator: pdf:p1 -->\nPage one evidence.\n"
                "<!-- locator: pdf:p2 -->\nPage two evidence.\n",
                encoding="utf-8",
            )
            blocks = parse_source_locator_blocks(source, "pdf")
            self.assertEqual(sorted(blocks), ["pdf:p1", "pdf:p2"])
            self.assertTrue(evidence_resolves("Page two evidence.", ["pdf:p2"], blocks))

    def test_invalid_or_empty_locator_span_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "source.md"
            source.write_text("<!-- locator: html#bad/path -->\nEvidence.\n", encoding="utf-8")
            with self.assertRaisesRegex(SourceLocatorError, "Invalid html locator"):
                parse_source_locator_blocks(source, "html")
            source.write_text("<!-- locator: html#S1 -->\n", encoding="utf-8")
            with self.assertRaisesRegex(SourceLocatorError, "empty span"):
                parse_source_locator_blocks(source, "html")


class SummaryContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.project = Path(self.tempdir.name)
        self.locator = "https://arxiv.org/abs/2401.12345v2"
        self.paper_id = "arxiv-2401.12345v2"
        create_paper(self.project, self.locator, fingerprint("1"), self.paper_id)
        complete_fixture_read(self.project, self.paper_id, self.locator, fingerprint("1"))
        self.state, self.context = prepare_summary(self.project, self.paper_id)
        self.workspace = paper_directory(self.project, self.paper_id)

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def complete(self, output_fingerprint: str | None = None) -> dict[str, object]:
        digest = output_fingerprint or sha256_file(self.workspace / "summary.md")
        return apply_paper_action(
            self.project,
            self.paper_id,
            {
                "action": "complete_stage",
                "data": {
                    "stage": "summary",
                    "artifact": "summary.md",
                    "output_fingerprint": digest,
                },
            },
        )

    def test_prepare_summary_writes_context_and_locator_index(self) -> None:
        self.assertEqual(self.state["stages"]["summary"]["status"], "in_progress")
        self.assertEqual(self.context["summary_context_schema"], 1)
        self.assertEqual(self.context["allowed_source_locators"], ["html#S1"])
        self.assertTrue((self.workspace / "source-locators.json").is_file())
        self.assertTrue((self.workspace / "summary-context.json").is_file())
        index = json.loads((self.workspace / "source-locators.json").read_text(encoding="utf-8"))
        self.assertEqual(index["source"]["source_fingerprint"], fingerprint("1"))
        self.assertEqual(index["locators"]["html#S1"][0]["preview"], "Fixture source.")

    def test_valid_three_section_summary_completes_with_claim_metadata(self) -> None:
        write_summary_fixture(self.workspace)
        state = self.complete()
        summary = state["stages"]["summary"]
        self.assertEqual(summary["status"], "complete")
        self.assertEqual(summary["artifact"], "summary.md")
        self.assertEqual(summary["metadata"]["claim_count"], 3)
        self.assertEqual(
            summary["metadata"]["section_claim_counts"],
            {"background": 1, "method": 1, "experiments": 1},
        )
        self.assertEqual(summary["metadata"]["cited_locator_count"], 1)

    def test_claim_must_contain_exact_quadruple(self) -> None:
        def mutate(ledger: dict[str, object]) -> None:
            ledger["sections"]["method"][0].pop("evidence")  # type: ignore[index]

        write_summary_fixture(self.workspace, mutate)
        with self.assertRaises(SystemExit) as context:
            self.complete()
        self.assertIn("claim_id, claim_text, evidence, source_locators", str(context.exception))

    def test_claim_id_prefix_and_global_uniqueness_are_enforced(self) -> None:
        def wrong_prefix(ledger: dict[str, object]) -> None:
            ledger["sections"]["method"][0]["claim_id"] = "B02"  # type: ignore[index]

        write_summary_fixture(self.workspace, wrong_prefix)
        with self.assertRaises(SystemExit) as context:
            self.complete()
        self.assertIn("must match M", str(context.exception))

        def duplicate(ledger: dict[str, object]) -> None:
            ledger["sections"]["method"][0]["claim_id"] = "M01"  # type: ignore[index]
            ledger["sections"]["method"].append(dict(ledger["sections"]["method"][0]))  # type: ignore[index]

        write_summary_fixture(self.workspace, duplicate)
        with self.assertRaises(SystemExit) as context:
            self.complete()
        self.assertIn("Duplicate summary claim_id", str(context.exception))

    def test_all_three_ordered_sections_are_required(self) -> None:
        def mutate(ledger: dict[str, object]) -> None:
            sections = ledger["sections"]  # type: ignore[assignment]
            ledger["sections"] = {
                "method": sections["method"],
                "background": sections["background"],
                "experiments": sections["experiments"],
            }

        write_summary_fixture(self.workspace, mutate)
        with self.assertRaises(SystemExit) as context:
            self.complete()
        self.assertIn("ordered exactly: background, method, experiments", str(context.exception))

    def test_locator_must_resolve_and_be_accepted_by_paper_notes(self) -> None:
        def nonexistent(ledger: dict[str, object]) -> None:
            ledger["sections"]["background"][0]["source_locators"] = ["html#missing"]  # type: ignore[index]

        write_summary_fixture(self.workspace, nonexistent)
        with self.assertRaises(SystemExit) as context:
            self.complete()
        self.assertIn("does not resolve in source.md", str(context.exception))

        with (self.workspace / "source.md").open("a", encoding="utf-8") as handle:
            handle.write("<!-- locator: html#S2 -->\nAdditional source evidence.\n")
        self.state, self.context = prepare_summary(self.project, self.paper_id)

        def outside_notes(ledger: dict[str, object]) -> None:
            claim = ledger["sections"]["background"][0]  # type: ignore[index]
            claim["source_locators"] = ["html#S2"]
            claim["evidence"] = "Additional source evidence."

        write_summary_fixture(self.workspace, outside_notes)
        with self.assertRaises(SystemExit) as context:
            self.complete()
        self.assertIn("were not accepted by paper-notes.md", str(context.exception))

    def test_evidence_must_be_exactly_resolvable_under_cited_locator(self) -> None:
        def mutate(ledger: dict[str, object]) -> None:
            ledger["sections"]["experiments"][0]["evidence"] = "Invented evidence absent from source."  # type: ignore[index]

        write_summary_fixture(self.workspace, mutate)
        with self.assertRaises(SystemExit) as context:
            self.complete()
        self.assertIn("evidence does not resolve", str(context.exception))

    def test_summary_inputs_and_output_fingerprint_cannot_drift(self) -> None:
        def mutate(ledger: dict[str, object]) -> None:
            ledger["inputs"]["paper_notes"]["fingerprint"] = fingerprint("f")  # type: ignore[index]

        write_summary_fixture(self.workspace, mutate)
        with self.assertRaises(SystemExit) as context:
            self.complete()
        self.assertIn("inputs must exactly copy", str(context.exception))

        write_summary_fixture(self.workspace)
        with self.assertRaises(SystemExit) as context:
            self.complete(fingerprint("f"))
        self.assertIn("does not match summary.md", str(context.exception))

    def test_tampered_locator_index_is_rejected(self) -> None:
        write_summary_fixture(self.workspace)
        index_path = self.workspace / "source-locators.json"
        payload = json.loads(index_path.read_text(encoding="utf-8"))
        payload["locators"]["html#S1"][0]["preview"] = "tampered"
        index_path.write_text(json.dumps(payload), encoding="utf-8")
        with self.assertRaises(SystemExit) as context:
            self.complete()
        self.assertIn("source-locators.json is stale", str(context.exception))

    def test_complete_summary_cli_finishes_valid_artifact(self) -> None:
        write_summary_fixture(self.workspace)
        completed = subprocess.run(
            [
                sys.executable,
                str(REPO_ROOT / "scripts/mw_paper.py"),
                "--project-root",
                str(self.project),
                "complete-summary",
                "--paper-id",
                self.paper_id,
            ],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True,
        )
        output = json.loads(completed.stdout)
        self.assertEqual(output["paper"]["stages"]["summary"]["status"], "complete")


class SummaryInputGateTests(unittest.TestCase):
    def test_prepare_summary_requires_completed_p2_read(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            state, _ = create_paper(project, "/tmp/paper.pdf", fingerprint("1"))
            with self.assertRaisesRegex(PaperError, "read stage to be complete"):
                prepare_summary(project, state["paper_id"])

    def test_prepare_summary_rejects_unresolved_paper_notes_locator(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            locator = "https://arxiv.org/abs/2401.99999v1"
            paper_id = "arxiv-2401.99999v1"
            create_paper(project, locator, fingerprint("2"), paper_id)
            apply_paper_action(project, paper_id, {"action": "start_stage", "data": {"stage": "read"}})
            workspace = paper_directory(project, paper_id)
            write_read_fixture(
                workspace,
                paper_id=paper_id,
                locator=locator,
                source_fingerprint=fingerprint("2"),
            )
            notes_path = workspace / "paper-notes.md"
            ledger = extract_notes_ledger(notes_path.read_text(encoding="utf-8"))
            ledger["research"]["background"]["locators"] = ["html#missing"]
            write_notes_ledger(notes_path, ledger)
            apply_paper_action(
                project,
                paper_id,
                {
                    "action": "complete_stage",
                    "data": {
                        "stage": "read",
                        "artifact": "paper-notes.md",
                        "output_fingerprint": sha256_file(notes_path),
                    },
                },
            )
            with self.assertRaisesRegex(PaperError, "does not resolve in source.md"):
                prepare_summary(project, paper_id)


if __name__ == "__main__":
    unittest.main()
