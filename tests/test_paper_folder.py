from __future__ import annotations

import json
from pathlib import Path
import sys
import tempfile
import unittest


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from mw_paper import create_paper, paper_directory, prepare_read  # noqa: E402
from mw_paper_artifacts import (  # noqa: E402
    READ_CONTEXT_FILE,
    READING_CONTEXT_FILE,
    SOURCE_MANIFEST_FILE,
    artifact_path,
)
from mw_paper_sources import acquire_source  # noqa: E402


def extracted_pdf_text() -> str:
    paragraph = (
        "This extracted PDF contains the problem, method, controlled experiments, "
        "limitations, equations, figures, and conclusion for a folder-source test. "
    ) * 25
    return "Abstract\n" + paragraph + "\nIntroduction\n" + paragraph + "\nMethod\n" + paragraph + "\nExperiments\n" + paragraph


class FolderReadTests(unittest.TestCase):
    def test_folder_prefers_paper_pdf_and_expands_latex_dependencies(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory) / "project"
            source = project / "paper-bundle"
            source.mkdir(parents=True)
            (source / "figure.pdf").write_bytes(b"%PDF-figure")
            (source / "paper.pdf").write_bytes(b"%PDF-paper" + b"x" * 100)
            (source / "main.tex").write_text(
                r"""\documentclass{article}
\title{A Folder Paper}
\author{A. Researcher}
\begin{document}
\begin{abstract}A short abstract.\end{abstract}
\section{Introduction}
This is the introduction.
\input{subsection}
\begin{equation}
y = f(x)
\end{equation}
\end{document}
""",
                encoding="utf-8",
            )
            (source / "subsection.tex").write_text(
                r"""\subsection{Method}
The method maps an input to an output.
""",
                encoding="utf-8",
            )

            state, report = prepare_read(
                project,
                source_locator=source,
                pdf_extractor=lambda _: extracted_pdf_text(),
            )
            workspace = paper_directory(project, state["paper_id"])
            self.assertEqual(state["paper_id"], "a-folder-paper")
            self.assertEqual(workspace.name, "a-folder-paper")
            self.assertEqual(report["source"]["input_kind"], "folder")
            self.assertEqual(report["source"]["selected_pdf"], "paper.pdf")
            self.assertEqual(report["source"]["latex_entry"], "main.tex")
            self.assertEqual(state["stages"]["read"]["status"], "in_progress")

            reading = (workspace / "reading.md").read_text(encoding="utf-8")
            self.assertIn("<!-- mary-reading:v1 -->", reading)
            self.assertIn("## Introduction", reading)
            self.assertIn("### Method", reading)
            self.assertIn("$$", reading)
            self.assertIn("<summary>Open question</summary>", reading)
            self.assertIn("<summary>Reader notes</summary>", reading)

            manifest = json.loads(artifact_path(workspace, SOURCE_MANIFEST_FILE).read_text(encoding="utf-8"))
            self.assertEqual(manifest["selected_pdf"], "paper.pdf")
            self.assertIn("subsection.tex", {item["path"] for item in manifest["files"]})

            context = json.loads(artifact_path(workspace, READ_CONTEXT_FILE).read_text(encoding="utf-8"))
            self.assertEqual(context["source_bundle"]["reading_artifact"], "reading.md")
            self.assertEqual(context["source_bundle"]["reading_summary_artifact"], "reading-summary.md")
            self.assertTrue((project / ".mary-research" / "reading-profile.md").is_file())
            self.assertTrue((workspace / "reading-summary.md").is_file())

    def test_pdf_only_folder_still_produces_a_reading_draft(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory) / "project"
            source = project / "paper-bundle"
            source.mkdir(parents=True)
            (source / "paper.pdf").write_bytes(b"%PDF-paper")
            state, report = prepare_read(
                project,
                source_locator=source,
                pdf_extractor=lambda _: extracted_pdf_text(),
            )
            workspace = paper_directory(project, state["paper_id"])
            self.assertEqual(report["source"]["latex_entry"], "")
            self.assertTrue((workspace / "reading.md").is_file())
            self.assertEqual(
                json.loads(artifact_path(workspace, READING_CONTEXT_FILE).read_text(encoding="utf-8"))["source_kind"],
                "pdf-only",
            )

    def test_prepare_read_migrates_legacy_hash_workspace_to_parsed_title(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory) / "project"
            source = project / "arxiv-export"
            source.mkdir(parents=True)
            (source / "paper.pdf").write_bytes(b"%PDF-paper" + b"x" * 100)
            (source / "main.tex").write_text(
                r"""\documentclass{article}
\title{Migrated Folder Paper}
\begin{document}Text.\end{document}
""",
                encoding="utf-8",
            )
            locator = str(source.resolve())
            acquisition = acquire_source(locator, pdf_extractor=lambda _: extracted_pdf_text())
            legacy_id = "local-" + acquisition["report"]["source"]["fingerprint"][:16]
            create_paper(project, locator, acquisition["report"]["source"]["fingerprint"], legacy_id)

            state, _ = prepare_read(
                project,
                source_locator=source,
                pdf_extractor=lambda _: extracted_pdf_text(),
            )

            self.assertEqual(state["paper_id"], "migrated-folder-paper")
            self.assertFalse((project / ".mary-research" / "papers" / legacy_id).exists())
            self.assertTrue(paper_directory(project, state["paper_id"]).is_dir())


if __name__ == "__main__":
    unittest.main()
