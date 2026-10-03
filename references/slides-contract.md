# Mary Paper Slides Contract v2

The `slides` stage produces one selected editable source artifact: native Beamer `slides.tex` or Marp `slides.md`, both ShanghaiTech red, 16:9 research-group presentations. It consumes the completed P3.5 summary bundle and does not introduce new paper facts. Content, grounding, Figure integrity, narrative, multi-panel usage, and capacity requirements are shared; only authoring and rendering syntax differ.

## Contents

- [Backend Selection](#backend-selection)
- [Preparation](#preparation)
- [Source Preamble](#source-preamble)
- [Narrative Structure](#narrative-structure)
- [Claim References](#claim-references)
- [Figure Placeholders](#figure-placeholders)
- [VSP Layouts](#vsp-layouts)
- [Capacity and Media Lint](#capacity-and-media-lint)
- [Optional Compile Smoke](#optional-compile-smoke)
- [Human Validation Boundary](#human-validation-boundary)

## Backend Selection

For a new slide-production request, ask one separate question before calling `prepare-slides` or writing the deck: “这次汇报使用哪种制作方式？” Present `Beamer（默认，推荐）` first, describing editable XeLaTeX plus PDF export, and `Marp` second, describing Markdown plus PDF/HTML/PPTX export. Wait for the user's actual answer. A default recommendation does not authorize starting without a reply; silence and timeout are not answers. An explicit method or `--backend` in the current slide request counts as its answer. Requests to develop or maintain this integration do not trigger a deck-production question.

Run `prepare-slides --backend beamer` or `prepare-slides --backend marp` with the chosen answer. The low-level runtime defaults to `beamer`; new contexts record `presentation.backend` and `presentation.source_artifact`. An existing context with no backend is interpreted as legacy Marp and retains the `slides.md` contract until a new preparation attempt selects otherwise. Reset an already complete stage before a new attempt, including a backend change; the state graph and stage authorization rules are unchanged.

## Preparation

`prepare-slides` requires a completed, still-valid summary stage. It validates the summary bundle again, starts `slides`, materializes original visuals in `figures/`, and writes `artifacts/slides-context.json` with:

- exact `summary.md`, `artifacts/summary-ledger.json`, summary-bundle, source-index, and selected theme fingerprints;
- the allowed summary claim catalog;
- Figure ids, captions, and source locators parsed from the normalized paper;
- workspace-local original figure assets, mapped to their Figure ids when available;
- the selected backend and source artifact, required theme, format, math engine, and shared lint limits.

Read all of `summary.md`, `artifacts/summary-ledger.json`, and `artifacts/slides-context.json` before writing. Use the article for explanation and the claim ledger for factual statements. Do not hand-edit generated context or state files.

For Beamer, preparation copies the offline `assets/beamer/` support into
`<paper-workspace>/beamer/`, including the localized VSP theme and ShanghaiTech
background/logo assets. The presentation is native TeX and uses Latin Modern,
Noto CJK SC, and native LaTeX math through XeLaTeX. The theme bundle fingerprint
is snapshotted in the generated context and checked again by lint. Do not rely
on a separate `vsp-beamer` reference checkout at runtime. Read
`references/beamer-assets-contract.md` before modifying the supply.

For Marp, preparation copies the self-contained offline theme to
`<project>/.mary-research/marp/themes/mary-shanghaitech-red.css` and merges its registration into
`<project>/.vscode/settings.json`. Unrelated setting values and existing theme entries are retained;
Mary sets Marp HTML to `all`, math typesetting to `katex`, and registers its project-local theme once.
Open the target project root as the VS Code workspace, then every paper deck below it previews
without depending on the Mary plugin checkout or the Markdown file's depth. VS Code does not
inherit `.vscode` settings from directories above an independently opened workspace.

Preparation also installs `<paper-workspace>/Makefile` and the isolated
`<paper-workspace>/hypo-template-preview/Slide.tex`. Run `make slide` from the
paper workspace to export `build/slides.pdf` from the selected source: Beamer
uses latexmk/XeLaTeX and the paper-local bundle, while Marp uses the exact local
theme, `--allow-local-files`, and the paper's relative figures. Run
`make hypo-template` to compile a separate original Hypoxanthine-LaTeX style
preview into `build/hypo-template-preview.pdf`; this is a visual comparison
artifact and must never replace the grounded `slides.tex` or `slides.md` artifact. The same
targets are available through the generated `.mary-research/Makefile` dispatcher
from the project research root; pass `PAPER_ID=<paper-id>` when needed.

For a folder containing LaTeX, preparation first copies the matching
`\includegraphics` asset (rasterizing a PDF asset to PNG when needed). For every
remaining PDF-backed Figure, it renders the original source page containing that
Figure's caption. This fallback intentionally keeps the complete page rather
than claiming an unverified crop. The resulting `figure_assets` records provide
the Figure id, workspace-relative `path`, kind, and source provenance; existing
materialized files are reused deterministically. For Beamer, select only
XeLaTeX-compatible originals (PNG/JPEG, or PDF rasterized to PNG); an
unsupported original format falls back to the faithful source-PDF page rather
than requiring an unrenderable image or a fabricated replacement.

## Source Preamble

### Beamer

Start `slides.tex` with this native preamble and exactly one version marker:

```tex
\documentclass[aspectratio=169,10pt]{beamer}
\input{beamer/mary-paper.tex}
% mary-slides:beamer:v1
\title{Paper title}
\subtitle{Research-group presentation}
\author{Presenter}
\institute{ShanghaiTech University}
\date{}

\begin{document}
\VSPtitleframe
% Content frames follow.
\VSPendframe{Thank you}
\end{document}
```

The bundled `assets/beamer/slides-template.tex` supplies an authoring starting
point; it is not a completed grounded deck. Keep `aspectratio=169`, the local
`beamer/mary-paper.tex` include, and theme settings intact. Do not add overlays,
`allowframebreaks`, `shrink`, custom macro definitions, or extra TeX includes to
bypass page counting, theme integrity, or lint. Escape literal TeX-special
characters in captions and prose; use native math environments for equations.

### Marp

Start `slides.md` with these required values:

```yaml
---
marp: true
theme: mary-shanghaitech-red
size: 16:9
math: katex
paginate: true
footer: Mary Workflow · 科研组会
---
```

Add `<!-- mary-slides:v1 -->` exactly once after the frontmatter. `footer` may be customized, but the five required fields may not be changed.

## Narrative Structure

Create 6-24 pages. Keep one message per page and progress in this order:

1. title page (`\VSPtitleframe` in Beamer, `cover_e` with exactly one H1 in Marp);
2. at least one Background page;
3. at least two Method pages;
4. at least one Experiments page;
5. optional Takeaways pages;
6. closing page (`\VSPendframe{<non-empty closing text>}` in Beamer, `lastpage` with a non-empty H6 in Marp).

Mark every factual content page with exactly one hidden section and claim declaration. In Beamer, place these inside the matching native frame:

```tex
\begin{frame}{Method intuition}
% section: method
% claims: M01 M03
\MaryColumns{Explanation}{Grounded equation or original Figure}
\end{frame}
```

In Marp, use:

```markdown
<!-- section: method -->
<!-- claims: M01 M03 -->
<!-- _class: cols-2-64 -->

## Method intuition
```

Allowed sections are `background`, `method`, `experiments`, and `takeaways`. Marp structural `trans`, `toc_a`, and `toc_b` pages may omit section and claim declarations. Method must remain at least as detailed as Background and Experiments in either backend.

## Claim References

Each factual content page requires one `% claims: ...` (Beamer) or `<!-- claims: ... -->` (Marp) comment. Claim ids must exist in `artifacts/slides-context.json`:

- Background pages use only `Bxx` claims.
- Method pages use only `Mxx` claims.
- Experiments pages use only `Exx` claims.
- Takeaways may combine all three families.

Reference at least one claim from every family across the deck. Keep claim ids hidden in comments; do not display P3 markers such as `[M01]` to the audience. Claim comments prove lineage, not semantic truth. Do not add facts that exist only in `artifacts/source.md` or general knowledge.

## Figure Placeholders

When `artifacts/slides-context.json` contains figures, use at least one. Inspect
`figure_assets` before authoring: for every Figure selected for the talk that has
a matching asset record, embed that local original visual in its placeholder.
Do not download, crop, or invent a replacement image. Reserve the intended panel
with the backend's exact shape. In Beamer, use:

```tex
\MaryFigure{Figure 2}{html\#S3.F2}{Figure 2: Caption from the context catalog.}{figures/figure-2.png}
```

The four arguments are the exact Figure id, one matching source locator, the
exact context caption, and the recorded paper-local asset path. TeX-escape
locator/caption characters such as `\#`, `\&`, `\%`, and `\_`; comparison restores these to
their literal characters and normalizes whitespace. Use an empty fourth
argument only when that Figure has no `figure_assets` record. Put the macro in
the intended panel, and include one on every frame with a visible reference to
that Figure. Do not replace it with an untracked `\includegraphics` or remote
asset.

In Marp, use:

```html
<div class="rimg figure-placeholder"
     data-figure="Figure 2"
     data-source-locator="html#S3.F2">
  <img src="figures/figure-2.png" alt="Figure 2">
  <div class="figure-placeholder__number">Figure 2</div>
  <div class="figure-placeholder__caption">Figure 2: Caption from the context catalog.</div>
</div>
```

Use the exact `figure_id`, caption, and one matching locator from the context. If a local image is embedded, its path must remain inside the paper workspace and its caption must exactly match the context caption after whitespace normalization. Standard `<img>` and self-closing `<img />` syntax are accepted. Combine `figure-placeholder` with one VSP image-panel class: `limg`, `mimg`, `rimg`, `timg`, or `bimg`. Every visible reference to a paper Figure on a page must have its matching placeholder on that page.

When no `figure_assets` record is available, retain the numbered placeholder
body. P5 never downloads or fabricates paper figures.

If the context has no Figure catalog, do not invent a Figure number. Use text, equations, or tables from the grounded summary instead.

## VSP Layouts

Use at least two multi-panel pages. Select layouts according to the content rather than repeating one grid:

### Beamer

Use native `columns` with at least two `column` environments, or the localized
VSP helpers `\MaryColumns{left}{right}`, `\MaryRows{top}{bottom}`, and
`\MaryPinThree{top}{left}{right}`. Use columns for a mechanism beside its
Figure/equation, rows for a wide Figure and interpretation, and pin-three for
an overview with two supporting panels. Keep the TeX semantic; shared layout
and typography belong to the vendored theme. Avoid reducing font sizes to hide
overloaded content.

### Marp

| Class | Use |
| --- | --- |
| `cols-2`, `cols-2-64`, `cols-2-37`, `cols-2-46`, `cols-2-73` | explanation beside a Figure, equation, or comparison |
| `cols-3` | three comparable modules, stages, or findings |
| `rows-2-*` | wide Figure above/below a short interpretation |
| `pin-3` | one overview above two supporting panels |

Use `ldiv`/`mdiv`/`rdiv` for text panels and `limg`/`mimg`/`rimg` for Figure panels. Use `tdiv`/`bdiv` and `timg`/`bimg` for row layouts. Keep headings compact and avoid shrinking everything with `tinytext` to hide overloaded pages.

## Capacity and Media Lint

`lint-slides` and `complete-slides` reject:

- missing cover, Background, Method, Experiments, or closing structure;
- fewer than two multi-panel pages;
- missing, unknown, or mismatched claim references;
- visible P3 claim ids;
- unknown Figure ids, invalid Figure locators, malformed placeholders, or Figure mentions without placeholders;
- HTTP(S), data URI, absolute, escaping, or nonexistent image paths;
- more than 900 visible non-whitespace characters, 36 visible lines, 8 list items, or 14 code lines on one page;
- more than 24 total pages;
- a selected-source fingerprint that differs from the declared completion fingerprint;
- a selected theme or backend context inconsistent with the prepared attempt;
- in Beamer, overlays, frame splitting/shrinking, custom macros, additional TeX includes, or media paths that bypass the Figure contract.

These are conservative static limits. Passing them does not prove pixel-perfect layout.

## Optional Compile Smoke

Run deterministic lint without changing state:

```bash
python scripts/mw_paper.py lint-slides --paper-id <paper-id>
```

Add `--smoke-compile` to `lint-slides` or `complete-slides` only for an optional
temporary check with the selected backend's local tools. Beamer needs GNU Make,
latexmk, XeLaTeX, Latin Modern and Noto CJK SC; Marp needs `marp` or a cached
`npx @marp-team/marp-cli@4.3.1`. Smoke outputs are temporary and are not P5
delivery artifacts. Default delivery is only `slides.tex` or `slides.md` plus
its generated support. When an export is requested, use `make slide` to produce
`build/slides.pdf`. Marp also retains HTML/PPTX export support; Beamer supplies
PDF plus editable TeX and does not provide native editable PPTX.

## Human Validation Boundary

The machine proves current inputs, exact artifact identity, required structure, allowed claims, Figure-reference integrity, local media existence, exact placeholder captions, closing-page purity, and conservative page capacity. It cannot prove that the selected claims tell the best story, that prose is semantically faithful, or that every page is visually balanced. Human review remains responsible for scientific accuracy, emphasis, pacing, and final image selection.
