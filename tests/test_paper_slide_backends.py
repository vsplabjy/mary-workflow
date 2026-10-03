from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from mw_paper import (  # noqa: E402
    apply_paper_action,
    create_paper,
    paper_directory,
    prepare_summary,
    read_paper_state,
)
from mw_paper_artifacts import PARSE_QUALITY_FILE, SLIDES_CONTEXT_FILE, artifact_path  # noqa: E402
from mw_paper_slides import materialize_figure_assets  # noqa: E402
from mw_paper_sources import sha256_file  # noqa: E402
from mw_paper_summary import summary_bundle_fingerprint  # noqa: E402
from tests.paper_read_helpers import (  # noqa: E402
    write_read_fixture,
    write_slides_fixture,
    write_summary_fixture,
)


def tex_escape(value: object) -> str:
    replacements = {
        "\\": r"\textbackslash{}",
        "{": r"\{",
        "}": r"\}",
        "$": r"\$",
        "&": r"\&",
        "#": r"\#",
        "_": r"\_",
        "%": r"\%",
        "~": r"\textasciitilde{}",
        "^": r"\textasciicircum{}",
    }
    return "".join(replacements.get(character, character) for character in str(value))


def write_beamer_fixture(workspace: Path) -> str:
    context = json.loads(artifact_path(workspace, SLIDES_CONTEXT_FILE).read_text(encoding="utf-8"))
    figure = context["figure_catalog"][0]
    asset = next(
        (
            item["path"]
            for item in context.get("figure_assets", [])
            if item["figure_id"] == figure["figure_id"]
        ),
        "",
    )
    figure_command = (
        r"\MaryFigure"
        + "{" + tex_escape(figure["figure_id"]) + "}"
        + "{" + tex_escape(figure["source_locators"][0]) + "}"
        + "{" + tex_escape(figure["caption"]) + "}"
        + "{" + tex_escape(asset) + "}"
    )
    source = r"""\documentclass[aspectratio=169,10pt]{beamer}
\input{beamer/mary-paper.tex}
% mary-slides:beamer:v1
\title{Fixture Paper}
\subtitle{A grounded research presentation}
\author{Mary Research}
\institute{ShanghaiTech University}
\date{2026}

\begin{document}
\VSPtitleframe

\begin{frame}{Background and problem}
% section: background
% claims: B01
The paper starts from a concrete research problem and explains why the missing capability matters.
\begin{itemize}
  \item Existing approaches leave an important gap.
  \item The paper targets that gap directly.
\end{itemize}
\end{frame}

\begin{frame}{Method intuition}
% section: method
% claims: M01
\MaryColumns{
The mechanism maps an input $x$ to an output $y$.
\[ y=f_{\theta}(x). \]
The source figure explains how information passes through that mechanism.
}{
FIGURE_COMMAND
}
\end{frame}

\begin{frame}{Method information flow}
% section: method
% claims: M01
\MaryColumns{
\begin{block}{Input}
Represent the observation.
\end{block}
}{
\begin{block}{Output}
Apply the grounded transformation to produce the task prediction.
\end{block}
}
\end{frame}

\begin{frame}{Experimental evidence}
% section: experiments
% claims: E01
The evaluation tests whether the proposed mechanism addresses the stated problem.
\begin{itemize}
  \item Report the main comparison before secondary ablations.
  \item Separate measured facts from interpretation.
\end{itemize}
\end{frame}

\begin{frame}{Takeaways}
% section: takeaways
% claims: B01 M01 E01
A concrete gap motivates the work. The method directly targets that gap, and the experiments test the central claim.
\end{frame}

\VSPendframe{Thanks}
\end{document}
""".replace("FIGURE_COMMAND", figure_command)
    path = workspace / "slides.tex"
    path.write_text(source, encoding="utf-8")
    return sha256_file(path)


class PaperSlideBackendIntegrationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.project = Path(self.tempdir.name)
        self.paper_id = "arxiv-2401.12345v2"
        self.workspace = self.ready_paper(self.paper_id, "1")

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def test_browser_only_figure_uses_original_pdf_fallback_for_beamer(self) -> None:
        source = self.project / "source-assets"
        source.mkdir()
        (source / "main.tex").write_text(
            r"\begin{figure}\includegraphics{plot.webp}\end{figure}", encoding="utf-8"
        )
        (source / "plot.webp").write_bytes(b"original-webp")
        pdf = artifact_path(self.workspace, "artifacts/source.pdf", create_parent=True)
        pdf.write_bytes(b"source-pdf-fixture")
        artifact_path(self.workspace, PARSE_QUALITY_FILE).write_text(json.dumps({
            "source": {"input_kind": "folder", "locator": str(source),
                       "latex_entry": "main.tex", "raw_artifact": "artifacts/source.pdf"}
        }), encoding="utf-8")
        figures = [{"figure_id": "Figure 1", "source_locators": ["pdf:p2"]}]

        def render(source_pdf: Path, page: int, destination: Path) -> Path:
            self.assertEqual((source_pdf, page), (pdf, 2))
            destination.write_bytes(b"faithful-page-fixture")
            return destination

        with patch("mw_paper_slides._render_pdf_page", side_effect=render):
            beamer = materialize_figure_assets(self.workspace, figures, backend="beamer")
        self.assertEqual(beamer[0]["kind"], "pdf-page-render")
        self.assertEqual(beamer[0]["source"], "pdf:p2")
        self.assertTrue(str(beamer[0]["path"]).endswith(".png"))
        marp = materialize_figure_assets(self.workspace, figures, backend="marp")
        self.assertEqual(marp[0]["kind"], "latex-asset")
        self.assertTrue(str(marp[0]["path"]).endswith(".webp"))

    def ready_paper(self, paper_id: str, fingerprint_character: str) -> Path:
        locator = "https://arxiv.org/abs/" + paper_id.removeprefix("arxiv-")
        fingerprint = fingerprint_character * 64
        create_paper(self.project, locator, fingerprint, paper_id)
        apply_paper_action(
            self.project,
            paper_id,
            {"action": "start_stage", "data": {"stage": "read"}},
        )
        workspace = paper_directory(self.project, paper_id)
        notes_fingerprint = write_read_fixture(
            workspace,
            paper_id=paper_id,
            locator=locator,
            source_fingerprint=fingerprint,
        )
        apply_paper_action(
            self.project,
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
        prepare_summary(self.project, paper_id)
        summary_fingerprint = write_summary_fixture(workspace)
        apply_paper_action(
            self.project,
            paper_id,
            {
                "action": "complete_stage",
                "data": {
                    "stage": "summary",
                    "artifact": "summary.md",
                    "output_fingerprint": summary_fingerprint,
                },
            },
        )
        return workspace

    def cli(
        self,
        command: str,
        *arguments: str,
        paper_id: str | None = None,
        success: bool = True,
    ) -> subprocess.CompletedProcess[str]:
        completed = subprocess.run(
            [
                sys.executable,
                str(REPO_ROOT / "scripts/mw_paper.py"),
                "--project-root",
                str(self.project),
                command,
                "--paper-id",
                paper_id or self.paper_id,
                *arguments,
            ],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=30,
        )
        if success:
            self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
        else:
            self.assertNotEqual(completed.returncode, 0, completed.stdout + completed.stderr)
        return completed

    def context(self, workspace: Path | None = None) -> dict[str, object]:
        path = artifact_path(workspace or self.workspace, SLIDES_CONTEXT_FILE)
        return json.loads(path.read_text(encoding="utf-8"))

    def make_slide(self, paper_id: str | None = None) -> str:
        completed = subprocess.run(
            [
                "make",
                "-C",
                str(self.project / ".mary-research"),
                "-n",
                "slide",
                f"PAPER_ID={paper_id or self.paper_id}",
            ],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=30,
        )
        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
        return completed.stdout

    def complete_action(self, artifact: str, fingerprint: str, *, success: bool = True) -> subprocess.CompletedProcess[str]:
        return self.cli(
            "apply-action",
            "--json",
            json.dumps(
                {
                    "action": "complete_stage",
                    "data": {
                        "stage": "slides",
                        "artifact": artifact,
                        "output_fingerprint": fingerprint,
                    },
                }
            ),
            success=success,
        )

    def test_default_cli_prepares_native_beamer_source_and_build(self) -> None:
        prepared = self.cli("prepare-slides")
        presentation = self.context()["presentation"]
        self.assertEqual(presentation["backend"], "beamer")
        self.assertEqual(presentation["source_artifact"], "slides.tex")
        self.assertIn(f"slides_target: {self.workspace / 'slides.tex'}", prepared.stdout)
        self.assertEqual(read_paper_state(self.project, self.paper_id)["stages"]["slides"]["status"], "in_progress")

        write_beamer_fixture(self.workspace)
        build_command = self.make_slide()
        self.assertIn("slides.tex", build_command)
        self.assertIn("slides.pdf", build_command)
        self.assertTrue("latexmk" in build_command or "xelatex" in build_command, build_command)
        self.assertNotIn("marp-cli", build_command)

    def test_explicit_marp_cli_retains_markdown_lint_completion_and_build(self) -> None:
        self.cli("prepare-slides", "--backend", "marp")
        presentation = self.context()["presentation"]
        self.assertEqual(presentation["backend"], "marp")
        self.assertEqual(presentation["source_artifact"], "slides.md")
        digest = write_slides_fixture(self.workspace)
        lint = json.loads(self.cli("lint-slides").stdout)
        self.assertEqual(lint["lint"], "passed")
        self.assertEqual(lint["slides_fingerprint"], digest)
        self.cli("complete-slides")
        slides = read_paper_state(self.project, self.paper_id)["stages"]["slides"]
        self.assertEqual(slides["status"], "complete")
        self.assertEqual(slides["artifact"], "slides.md")
        self.assertEqual(slides["output_fingerprint"], digest)
        command = self.make_slide()
        self.assertIn("slides.md", command)
        self.assertIn("marp-cli", command)
        self.assertNotIn("latexmk", command)

    def test_invalid_backend_is_rejected_without_preparing_stage(self) -> None:
        state_before = (self.workspace / "state.json").read_bytes()
        rejected = self.cli("prepare-slides", "--backend", "invalid", success=False)
        self.assertIn("invalid choice", rejected.stderr)
        self.assertEqual((self.workspace / "state.json").read_bytes(), state_before)
        self.assertFalse(artifact_path(self.workspace, SLIDES_CONTEXT_FILE).exists())

    def test_beamer_cli_lints_and_records_the_tex_fingerprint(self) -> None:
        self.cli("prepare-slides")
        digest = write_beamer_fixture(self.workspace)
        (self.workspace / "slides.md").write_text("An unrelated legacy source.\n", encoding="utf-8")
        lint = json.loads(self.cli("lint-slides").stdout)
        self.assertEqual(lint["lint"], "passed")
        self.assertEqual(lint["slides_fingerprint"], digest)
        self.assertEqual(lint["metadata"]["page_count"], 7)
        self.assertEqual(lint["metadata"]["section_page_counts"]["method"], 2)
        self.cli("complete-slides")
        slides = read_paper_state(self.project, self.paper_id)["stages"]["slides"]
        self.assertEqual(slides["status"], "complete")
        self.assertEqual(slides["artifact"], "slides.tex")
        self.assertEqual(slides["output_fingerprint"], digest)
        self.assertNotEqual(slides["output_fingerprint"], sha256_file(self.workspace / "slides.md"))

    def test_beamer_complete_action_requires_the_selected_source_and_current_bytes(self) -> None:
        self.cli("prepare-slides")
        old_digest = write_beamer_fixture(self.workspace)
        legacy_source = self.workspace / "slides.md"
        legacy_source.write_text("A legacy slide source.\n", encoding="utf-8")
        rejected = self.complete_action("slides.md", sha256_file(legacy_source), success=False)
        self.assertIn("slides.tex", rejected.stderr)

        path = self.workspace / "slides.tex"
        path.write_text(path.read_text(encoding="utf-8") + "\n% Editorial change after lint.\n", encoding="utf-8")
        current_digest = sha256_file(path)
        self.assertNotEqual(current_digest, old_digest)
        self.cli("lint-slides")
        rejected = self.complete_action("slides.tex", old_digest, success=False)
        self.assertIn("output_fingerprint does not match", rejected.stderr)
        self.assertEqual(read_paper_state(self.project, self.paper_id)["stages"]["slides"]["status"], "in_progress")
        self.complete_action("slides.tex", current_digest)
        self.assertEqual(read_paper_state(self.project, self.paper_id)["stages"]["slides"]["output_fingerprint"], current_digest)

    def test_beamer_content_tampering_is_rejected_by_lint_and_completion(self) -> None:
        self.cli("prepare-slides")
        write_beamer_fixture(self.workspace)
        path = self.workspace / "slides.tex"
        source = path.read_text(encoding="utf-8")
        path.write_text(source.replace("% claims: M01", "% claims: M99", 1), encoding="utf-8")
        rejected = self.cli("lint-slides", success=False)
        self.assertIn("M99", rejected.stderr)
        rejected = self.cli("complete-slides", success=False)
        self.assertIn("M99", rejected.stderr)
        self.assertEqual(read_paper_state(self.project, self.paper_id)["stages"]["slides"]["status"], "in_progress")

    def test_beamer_source_selection_and_support_files_cannot_drift(self) -> None:
        self.cli("prepare-slides")
        write_beamer_fixture(self.workspace)
        write_slides_fixture(self.workspace)
        context_path = artifact_path(self.workspace, SLIDES_CONTEXT_FILE)
        context = self.context()
        context["presentation"]["source_artifact"] = "slides.md"
        context_path.write_text(json.dumps(context), encoding="utf-8")
        for command in ("lint-slides", "complete-slides"):
            with self.subTest(command=command):
                rejected = self.cli(command, success=False)
                self.assertIn("source artifact", rejected.stderr)

        self.cli("prepare-slides", "--backend", "beamer")
        support = self.workspace / "beamer" / "mary-paper.tex"
        support.write_text(support.read_text(encoding="utf-8") + "\n% Changed build support.\n", encoding="utf-8")
        self.cli("lint-slides", success=False)
        self.assertEqual(read_paper_state(self.project, self.paper_id)["stages"]["slides"]["status"], "in_progress")

    def test_legacy_context_without_backend_keeps_marp_source_selection(self) -> None:
        self.cli("prepare-slides", "--backend", "marp")
        digest = write_slides_fixture(self.workspace)
        path = artifact_path(self.workspace, SLIDES_CONTEXT_FILE)
        context = self.context()
        context["presentation"].pop("backend")
        context["presentation"].pop("source_artifact")
        path.write_text(json.dumps(context, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        makefile = self.workspace / "Makefile"
        makefile.write_text(
            makefile.read_text(encoding="utf-8").replace("$(THEME) Makefile", "$(THEME)"),
            encoding="utf-8",
        )
        (self.workspace / "slides.tex").write_text("This is not the selected source.\n", encoding="utf-8")
        lint = json.loads(self.cli("lint-slides").stdout)
        self.assertEqual(lint["slides_fingerprint"], digest)
        self.cli("complete-slides")
        slides = read_paper_state(self.project, self.paper_id)["stages"]["slides"]
        self.assertEqual(slides["artifact"], "slides.md")
        self.assertEqual(slides["output_fingerprint"], digest)

    def test_new_marp_context_rejects_the_outdated_build_target(self) -> None:
        self.cli("prepare-slides", "--backend", "marp")
        write_slides_fixture(self.workspace)
        makefile = self.workspace / "Makefile"
        makefile.write_text(
            makefile.read_text(encoding="utf-8").replace("$(THEME) Makefile", "$(THEME)"),
            encoding="utf-8",
        )
        rejected = self.cli("lint-slides", success=False)
        self.assertIn("Paper Makefile is missing or stale", rejected.stderr)
        self.assertEqual(read_paper_state(self.project, self.paper_id)["stages"]["slides"]["status"], "in_progress")

    def test_repreparing_a_backend_preserves_both_authored_sources(self) -> None:
        self.cli("prepare-slides")
        write_beamer_fixture(self.workspace)
        tex_before = (self.workspace / "slides.tex").read_bytes()
        self.cli("prepare-slides", "--backend", "marp")
        write_slides_fixture(self.workspace)
        markdown_before = (self.workspace / "slides.md").read_bytes()
        self.assertEqual((self.workspace / "slides.tex").read_bytes(), tex_before)
        self.assertIn("marp-cli", self.make_slide())
        self.cli("lint-slides")

        self.cli("prepare-slides", "--backend", "beamer")
        self.assertEqual(self.context()["presentation"]["source_artifact"], "slides.tex")
        self.assertEqual((self.workspace / "slides.tex").read_bytes(), tex_before)
        self.assertEqual((self.workspace / "slides.md").read_bytes(), markdown_before)
        self.assertNotIn("marp-cli", self.make_slide())
        self.cli("lint-slides")

    def test_switching_back_to_marp_rebuilds_a_pdf_from_the_previous_backend(self) -> None:
        self.cli("prepare-slides", "--backend", "marp")
        write_slides_fixture(self.workspace)
        for path in (
            self.workspace / "slides.md",
            self.project / ".mary-research" / "marp" / "themes" / "mary-shanghaitech-red.css",
        ):
            os.utime(path, (1000, 1000))

        self.cli("prepare-slides", "--backend", "beamer")
        write_beamer_fixture(self.workspace)
        output = self.workspace / "build" / "slides.pdf"
        output.parent.mkdir()
        output.write_bytes(b"%PDF previously built Beamer artifact\n")
        os.utime(output, (2000, 2000))

        self.cli("prepare-slides", "--backend", "marp")
        command = self.make_slide()
        self.assertIn("marp-cli", command)
        self.assertIn("slides.md", command)

    def test_summary_recompletion_stales_beamer_and_requires_fresh_context(self) -> None:
        self.cli("prepare-slides")
        digest = write_beamer_fixture(self.workspace)
        self.cli("complete-slides")
        self.cli(
            "apply-action",
            "--json",
            json.dumps({"action": "reset_stage", "data": {"stage": "summary"}}),
        )
        state = read_paper_state(self.project, self.paper_id)
        self.assertEqual(state["stages"]["slides"]["status"], "stale")
        rejected = self.cli("lint-slides", success=False)
        self.assertIn("validated read and summary", rejected.stderr)

        prepare_summary(self.project, self.paper_id)
        write_summary_fixture(self.workspace)
        summary_path = self.workspace / "summary.md"
        summary_path.write_text(
            summary_path.read_text(encoding="utf-8") + "\nThe revised evaluation clarifies the supported observation. [E01]\n",
            encoding="utf-8",
        )
        apply_paper_action(
            self.project,
            self.paper_id,
            {
                "action": "complete_stage",
                "data": {
                    "stage": "summary",
                    "artifact": "summary.md",
                    "output_fingerprint": summary_bundle_fingerprint(self.workspace),
                },
            },
        )
        rejected = self.cli("lint-slides", success=False)
        self.assertIn("stale", rejected.stderr)
        self.cli("prepare-slides", "--backend", "beamer")
        self.assertEqual(sha256_file(self.workspace / "slides.tex"), digest)
        self.cli("lint-slides")
        self.cli("complete-slides")
        slides = read_paper_state(self.project, self.paper_id)["stages"]["slides"]
        self.assertEqual(slides["artifact"], "slides.tex")
        self.assertEqual(slides["status"], "complete")
        self.assertEqual(slides["input_fingerprints"]["summary"], summary_bundle_fingerprint(self.workspace))

    def test_backend_selection_is_isolated_between_papers_in_one_project(self) -> None:
        other_id = "arxiv-2402.12345v1"
        other_workspace = self.ready_paper(other_id, "2")
        self.cli("prepare-slides", "--backend", "beamer")
        beamer_digest = write_beamer_fixture(self.workspace)
        context_before = artifact_path(self.workspace, SLIDES_CONTEXT_FILE).read_bytes()
        makefile_before = (self.workspace / "Makefile").read_bytes()

        self.cli("prepare-slides", "--backend", "marp", paper_id=other_id)
        marp_digest = write_slides_fixture(other_workspace)
        self.assertEqual(artifact_path(self.workspace, SLIDES_CONTEXT_FILE).read_bytes(), context_before)
        self.assertEqual((self.workspace / "Makefile").read_bytes(), makefile_before)
        self.assertEqual(self.context()["presentation"]["backend"], "beamer")
        self.assertEqual(self.context(other_workspace)["presentation"]["backend"], "marp")
        self.assertNotIn("marp-cli", self.make_slide())
        self.assertIn("marp-cli", self.make_slide(other_id))

        self.cli("lint-slides")
        self.cli("lint-slides", paper_id=other_id)
        self.cli("complete-slides")
        self.cli("complete-slides", paper_id=other_id)
        beamer_stage = read_paper_state(self.project, self.paper_id)["stages"]["slides"]
        marp_stage = read_paper_state(self.project, other_id)["stages"]["slides"]
        self.assertEqual(beamer_stage["artifact"], "slides.tex")
        self.assertEqual(beamer_stage["output_fingerprint"], beamer_digest)
        self.assertEqual(marp_stage["artifact"], "slides.md")
        self.assertEqual(marp_stage["output_fingerprint"], marp_digest)


if __name__ == "__main__":
    unittest.main()
