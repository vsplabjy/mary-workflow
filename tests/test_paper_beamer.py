from __future__ import annotations

import json
from pathlib import Path
import re
import shutil
import sys
import tempfile
import unittest


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from mw_paper_artifacts import SLIDES_CONTEXT_FILE, artifact_path  # noqa: E402
from mw_paper_beamer import (  # noqa: E402
    BEAMER_ASSET_ROOT,
    BEAMER_SLIDES_FILE,
    BeamerError,
    beamer_presentation,
    install_beamer_support,
    smoke_compile_beamer,
    validate_beamer_document,
    validate_beamer_slides,
    validate_beamer_support,
)
from mw_paper_sources import sha256_file  # noqa: E402


class BeamerContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.workspace = Path(self.temp.name)
        install_beamer_support(self.workspace)
        self.source = (BEAMER_ASSET_ROOT / "slides-template.tex").read_text(encoding="utf-8")
        self.context = {
            "presentation": beamer_presentation(self.workspace),
            "claim_catalog": [
                {"claim_id": claim, "section": section}
                for claim, section in (
                    ("B01", "background"), ("M01", "method"),
                    ("M02", "method"), ("E01", "experiments"),
                )
            ],
            "figure_catalog": [],
            "figure_assets": [],
        }

    def tearDown(self) -> None:
        self.temp.cleanup()

    def lint(self, source: str | None = None) -> dict:
        return validate_beamer_document(self.workspace, self.source if source is None else source, self.context)

    def rejects(self, source: str, message: str | None = None) -> None:
        with self.assertRaisesRegex(BeamerError, message or ".*"):
            self.lint(source)

    def figure(self, *, with_asset: bool = False) -> str:
        self.context["figure_catalog"] = [{
            "figure_id": "Figure 1", "caption": "Figure 1: A & B improve 5% over x_y. Compare Figure 2.",
            "source_locators": ["html#S1.F1"],
        }]
        image = ""
        if with_asset:
            (self.workspace / "figures").mkdir(exist_ok=True)
            shutil.copyfile(BEAMER_ASSET_ROOT / "images/ShanghaiTech_Logo_RGBA.png", self.workspace / "figures/original.png")
            image = "figures/original.png"
            self.context["figure_assets"] = [{"figure_id": "Figure 1", "path": image}]
        macro = r"\MaryFigure{Figure 1}{html\#S1.F1}{Figure 1: A \& B improve 5\% over x\_y. Compare Figure 2.}{" + image + "}"
        return self.source.replace("Explain the information flow.", macro)

    def test_native_source_has_grounded_structure_and_real_layouts(self) -> None:
        report = self.lint()
        self.assertEqual(report["page_count"], 6)
        self.assertEqual(report["section_page_counts"], {"background": 1, "method": 2, "experiments": 1, "takeaways": 0})
        self.assertEqual(report["layout_page_count"], 2)
        self.assertEqual(report["referenced_claim_ids"], ["B01", "E01", "M01", "M02"])

    def test_real_native_columns_are_accepted(self) -> None:
        source = self.source.replace(
            r"\MaryColumns{Teach the central intuition.}{Explain the information flow.}",
            r"\begin{columns}[T,onlytextwidth]\begin{column}{.48\textwidth}Intuition.\end{column}"
            r"\begin{column}{.48\textwidth}Information flow.\end{column}\end{columns}",
        )
        self.assertEqual(self.lint(source)["layout_page_count"], 2)

    def test_crlf_has_the_same_page_and_lineage_metrics(self) -> None:
        self.assertEqual(self.lint(self.source.replace("\n", "\r\n")), self.lint())

    def test_exact_native_fingerprint_and_context_metadata(self) -> None:
        path = self.workspace / BEAMER_SLIDES_FILE
        path.write_text(self.source, encoding="utf-8")
        context_path = artifact_path(self.workspace, SLIDES_CONTEXT_FILE, create_parent=True)
        context_path.write_text(json.dumps(self.context), encoding="utf-8")
        result = validate_beamer_slides(self.workspace, self.context)
        self.assertEqual(result["artifact"], "slides.tex")
        self.assertEqual(result["artifact_fingerprint"], sha256_file(path))
        self.assertEqual(result["metadata"]["slides_body_fingerprint"], sha256_file(path))
        self.assertEqual(result["metadata"]["slides_context_fingerprint"], sha256_file(context_path))
        path.write_text(self.source.replace("Teach the central intuition.", "Teach the mechanism."), encoding="utf-8")
        self.assertNotEqual(validate_beamer_slides(self.workspace, self.context)["artifact_fingerprint"], result["artifact_fingerprint"])

    def test_required_page_counts_and_section_order(self) -> None:
        self.rejects(self.source.replace("% section: method\n% claims: M02", "% section: experiments\n% claims: E01", 1), "at least 2 method")
        self.rejects(self.source.replace("% section: background", "% section: experiments", 1).replace("% claims: B01", "% claims: E01", 1), "sections must progress")
        self.rejects(self.source.replace(r"\VSPtitleframe", ""), "6-24")

    def test_claims_must_be_known_matched_unique_and_hidden(self) -> None:
        for old, new, message in (
            ("% claims: M01", "% claims: M99", "unknown"),
            ("% claims: M01", "% claims: E01", "cannot cite"),
            ("% claims: M01", "% claims: M01 M01", "duplicate"),
            ("% claims: M01", "% claims: ", "invalid"),
            ("% claims: M01", "", "exactly one"),
            ("Teach the central intuition.", "Teach [M01].", "exposes"),
            ("Teach the central intuition.", r"\textbf{M01}", "exposes"),
        ):
            with self.subTest(new=new):
                self.rejects(self.source.replace(old, new, 1), message)
        self.rejects(self.source.replace(r"\VSPtitleframe", "% claims: B01\n\\VSPtitleframe"), "inside their content frame")

    def test_cover_and_closing_cannot_hide_frames_or_figures(self) -> None:
        for payload in (r"\includegraphics{/etc/passwd}", r"\begin{frame}{Injected}extra\end{frame}", r"\MaryColumns{one}{two}"):
            with self.subTest(payload=payload):
                self.rejects(self.source.replace("Paper title", payload), "inline text/math")
                self.rejects(self.source.replace(r"\VSPendframe{Thank You}", r"\VSPendframe{" + payload + "}"), "inline text/math")
        self.rejects(self.source.replace(r"\VSPendframe{Thank You}", r"\VSPendframe{}"), "non-empty closing")
        self.rejects(self.source.replace(r"\VSPendframe{Thank You}", "\\VSPendframe{Thanks}\nextra conclusion"), "outside an explicit frame")

    def test_empty_panels_do_not_count_as_layouts(self) -> None:
        self.rejects(self.source.replace("Explain the information flow.", ""), "non-empty panels")
        self.rejects(self.source.replace(r"\MaryRows", r"\textbf", 1), "real multi-panel")

    def test_displayed_code_does_not_create_real_layouts(self) -> None:
        source = self.source.replace(r"\begin{frame}{Method", r"\begin{frame}[fragile]{Method")
        source = source.replace(
            r"\MaryColumns{Teach the central intuition.}{Explain the information flow.}",
            "\\begin{lstlisting}\n\\MaryColumns{only}{printed}\n\\end{lstlisting}",
        ).replace(
            r"\MaryRows{Explain the mechanism and relevant equations.}{Explain assumptions and trade-offs.}",
            "\\begin{verbatim}\n\\MaryRows{only}{printed}\n\\end{verbatim}",
        )
        self.rejects(source, "real multi-panel")

    def test_exact_caption_escapes_original_assets_and_cross_references(self) -> None:
        source = self.figure(with_asset=True)
        report = self.lint(source)
        self.assertEqual(report["referenced_figure_ids"], ["Figure 1"])
        self.assertEqual(report["figure_placeholder_count"], 1)
        # The caption's cross-reference to Figure 2 is prose, not a second panel.
        self.assertNotIn("Figure 2", report["referenced_figure_ids"])
        self.rejects(source.replace("html\\#S1.F1", "html\\#S9.F1"), "locator does not resolve")
        self.rejects(source.replace("improve 5\\%", "improve 6\\%"), "caption does not exactly match")
        self.rejects(source.replace("{figures/original.png}", "{}"), "prepared source asset")

    def test_numbered_placeholder_is_allowed_only_when_no_original_is_prepared(self) -> None:
        source = self.figure()
        self.assertEqual(self.lint(source)["figure_placeholder_count"], 1)
        self.rejects(self.source, "at least one figure placeholder")
        self.rejects(source.replace("Teach the central intuition.", "Compare Figure 3."), "unknown figures")
        self.rejects(source.replace("Present the setup,", "See Figure 1. Present the setup,"), "without matching figure placeholders")

    def test_subfigure_suffixes_normalize_to_the_shared_catalog_case(self) -> None:
        source = self.figure().replace("Figure 1", "Figure 1A")
        self.context["figure_catalog"][0]["figure_id"] = "Figure 1A"
        self.context["figure_catalog"][0]["caption"] = self.context["figure_catalog"][0]["caption"].replace("Figure 1", "Figure 1A")
        source = source.replace("Teach the central intuition.", "See Figure 1a. Teach the central intuition.")
        self.assertEqual(self.lint(source)["referenced_figure_ids"], ["Figure 1A"])

    def test_printed_figure_macro_is_not_a_grounded_figure(self) -> None:
        source = self.figure().replace(r"\begin{frame}{Method: central", r"\begin{frame}[fragile]{Method: central")
        source = source.replace(" Compare Figure 2.", "")
        self.context["figure_catalog"][0]["caption"] = self.context["figure_catalog"][0]["caption"].replace(" Compare Figure 2.", "")
        macro = next(line for line in source.splitlines() if line.startswith(r"\MaryColumns"))
        source = source.replace(macro, "\\begin{lstlisting}\n" + macro + "\n\\end{lstlisting}")
        self.rejects(source, "without matching figure placeholders")

    def test_remote_absolute_escaping_and_symlink_media_are_rejected(self) -> None:
        for path in ("https://example.com/photo.png", "//example.com/photo.png", "data:image/png;base64,AA", "/etc/passwd", "../photo.png", "missing.png"):
            with self.subTest(path=path):
                self.rejects(self.source.replace("Teach the central intuition.", r"\includegraphics{" + path + "}"), "image")
        outside = self.workspace.parent / (self.workspace.name + "-outside.png")
        outside.write_bytes(b"placeholder")
        try:
            (self.workspace / "escape.png").symlink_to(outside)
            self.rejects(self.source.replace("Teach the central intuition.", r"\includegraphics{escape.png}"), "escapes")
        finally:
            outside.unlink()

    def test_unsafe_tex_and_all_overlay_spellings_are_rejected(self) -> None:
        payloads = (
            r"\input{other.tex}", r"\def\name{injected}", r"\csname input\endcsname{other.tex}",
            "^^5cinput{other.tex}", r"\begin{itemize}[<+->]\item one\end{itemize}",
            r"\textcolor<2->{red}{revealed}", r"\item<2-> visible",
            r"\begin{columns}\begin{column}<2->{.48\textwidth}visible\end{column}\end{columns}",
        )
        for payload in payloads:
            with self.subTest(payload=payload):
                self.rejects(self.source.replace("Teach the central intuition.", payload), "unsafe|unsupported|overlays")
        for option in ("allowframebreaks", "shrink", "t,allowframebreaks", "<2->"):
            self.rejects(self.source.replace(r"\begin{frame}{Background", r"\begin{frame}[" + option + "]{Background"), "frame options")

    def test_capacity_limits_apply_to_visible_text_lists_and_code(self) -> None:
        for payload, message in (
            ("x" * 901, "visible_characters"),
            ("\n".join("line" for _ in range(37)), "visible_lines"),
            (r"line\par " * 37, "visible_lines"),
            ("\\begin{itemize}\n" + "\\item point\n" * 9 + "\\end{itemize}", "list_items"),
            ("\\begin{lstlisting}\n" + "% displayed code\n" * 15 + "\\end{lstlisting}", "code_lines"),
        ):
            with self.subTest(message=message):
                self.rejects(self.source.replace("Teach the central intuition.", payload), message)
        self.rejects(self.source.replace("Teach the central intuition.", "\\begin{lstlisting}\n% " + "x" * 901 + "\n\\end{lstlisting}"), "visible_characters")

    def test_runtime_assets_are_fingerprinted_and_install_preserves_authored_source(self) -> None:
        path = self.workspace / "slides.tex"
        path.write_text("user-authored native source", encoding="utf-8")
        before = path.read_bytes()
        installed = install_beamer_support(self.workspace)
        self.assertEqual(installed, validate_beamer_support(self.workspace))
        self.assertEqual(path.read_bytes(), before)
        theme = self.workspace / "beamer/themes/beamerthemeVSP.sty"
        theme.write_text(theme.read_text() + "\n% user change", encoding="utf-8")
        with self.assertRaisesRegex(BeamerError, "stale"):
            validate_beamer_support(self.workspace)
        install_beamer_support(self.workspace)
        self.assertEqual(installed, validate_beamer_support(self.workspace))

    def test_existing_unmanaged_support_is_not_overwritten(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            workspace = Path(folder)
            user_file = workspace / "beamer/custom.sty"
            user_file.parent.mkdir()
            user_file.write_text("user theme", encoding="utf-8")
            with self.assertRaisesRegex(BeamerError, "not Mary-managed"):
                install_beamer_support(workspace)
            self.assertEqual(user_file.read_text(), "user theme")
            self.assertFalse((workspace / "beamer/mary-paper.tex").exists())

    @unittest.skipUnless(shutil.which("latexmk") and shutil.which("xelatex"), "XeLaTeX smoke requires latexmk and xelatex")
    def test_offline_smoke_compiles_chinese_math_and_local_original_figure(self) -> None:
        source = self.figure(with_asset=True).replace("Paper title", "论文方法与实验")
        source = source.replace("Teach the central intuition.", r"信息流：$y=f_{\theta}(x)$。")
        self.lint(source)
        (self.workspace / "slides.tex").write_text(source, encoding="utf-8")
        result = smoke_compile_beamer(self.workspace)
        self.assertEqual(result["status"], "passed")
        self.assertEqual(result["warnings"], [])
        self.assertFalse((self.workspace / "slides.pdf").exists())
        self.assertFalse((self.workspace / "build").exists())


if __name__ == "__main__":
    unittest.main()
