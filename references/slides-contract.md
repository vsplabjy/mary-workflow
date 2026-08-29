# Mary Paper Slides Contract v2

The `slides` stage produces editable `slides.tex` plus the verified export
`build/slides.pdf`. It consumes the completed P3.5 summary bundle and may not
introduce paper facts outside the summary claim ledger.

## Preparation

`prepare-slides` revalidates the summary, starts `slides`, materializes original
paper visuals under `figures/`, and writes `artifacts/slides-context.json` with:

- fingerprints for `summary.md`, `artifacts/summary-ledger.json`, the source
  locator index, and the pinned Beamer runtime;
- the allowed Bxx, Mxx, and Exx claim catalog;
- Figure ids, exact captions, source locators, and any materialized local assets;
- the required theme, engine, page format, build entrypoints, and lint limits.

Read `summary.md`, `artifacts/summary-ledger.json`, and
`artifacts/slides-context.json` before authoring. Do not hand-edit generated
context or state files.

Preparation deploys the pinned runtime to `<project>/.mary-research/beamer/` and
installs Makefiles at the research root and paper workspace. The runtime is
derived from `Heaticy/vsp-beamer` commit
`e7bf4e5e5588ee10a386e6c79668e50f9b749124`; it is Linux-only and uses GNU Make,
`latexmk`, XeLaTeX, Latin Modern, and system Noto CJK SC fonts.

## Required TeX Shape

Start with the exact preamble and marker:

```tex
\documentclass[aspectratio=169,10pt]{beamer}
\usepackage[UTF8,fontset=none]{ctex}
\usetheme{mary-shanghaitech-red}

% mary-slides:v2
\title[Short title]{Full title}
\subtitle{Subtitle}
\VSPsetspeaker[汇报人]{Name}{Institute}
\date{}

\begin{document}
\VSPtitleframe
```

End with one non-empty closing frame and the document terminator:

```tex
\VSPendframe{谢谢}
\end{document}
```

Keep equations as native TeX. Do not add Marp directives, Markdown slide
separators, HTML layout wrappers, CSS, remote resources, or Node-based tooling.

## Narrative And Claims

Create 6-24 pages in this order: title, Background, at least two Method pages,
Experiments, optional Takeaways, and closing. Method must be at least as detailed
as Background and Experiments.

Every factual `frame` needs exactly one section and claim declaration:

```tex
\begin{frame}{Method intuition}
% mary-section: method
% mary-claims: M01 M03
...
\end{frame}
```

Allowed sections are `background`, `method`, `experiments`, and `takeaways`.
Background uses Bxx, Method uses Mxx, Experiments uses Exx, and Takeaways may
combine families. Reference every family across the deck. Keep ids in comments;
never show `[M01]`-style anchors to the audience. A contents frame may use
`% mary-structural` and omit section/claim declarations.

## Figures

Use at least one catalog Figure when the context provides any. Pair a structured
locator comment with one `\MaryFigure` call:

```tex
% mary-figure: {"figure_id":"Figure 2","source_locator":"html#S3.F2"}
\MaryFigure{figures/figure-2.png}{Figure 2}{Figure 2: Exact context caption.}
```

The three macro arguments are local asset path, Figure id, and exact caption.
Escape TeX-special characters without changing the visible caption. If
`figure_assets` contains the Figure, use that exact path. If no asset exists,
leave the first argument empty so the theme renders an explicit numbered
placeholder:

```tex
\MaryFigure{}{Figure 2}{Figure 2: Exact context caption.}
```

Do not download, crop, trace, redraw, or fabricate paper figures. Direct
`\includegraphics` paths must be local, workspace-contained, existent, and use
`keepaspectratio`.

## Layout And Capacity

Use Beamer `columns` or equivalent paired minipages on at least two pages. Choose
widths from the material: roughly `.48/.48` for balanced comparisons,
`.58/.38` for explanation beside a narrow visual, `.28/.68` for a wide Figure,
or three `.32` columns for comparable stages. Keep theme logic out of
`slides.tex`; do not solve density by applying global font shrinkage.

Static lint rejects missing structure, invalid claims, stale context/runtime,
malformed Figure metadata, mismatched captions/assets, unsafe media, fewer than
two multi-panel pages, more than 900 visible non-whitespace characters, 36
visible lines, 8 list items, or 14 code lines on a content page.

## Build And Audit

Run static lint without changing state:

```bash
python scripts/mw_paper.py lint-slides --paper-id <paper-id>
```

Compile and run the PDF audit without completing the stage:

```bash
python scripts/mw_paper.py lint-slides --paper-id <paper-id> --audit-pdf
```

Equivalent generated Makefile targets are:

```bash
make audit-slides
make slide
```

`make slide` uses `latexmk -xelatex`, rejects `Overfull`, missing characters,
LaTeX errors, font warnings, and package warnings, then writes
`build/slides.pdf`. `make audit-slides` additionally checks PDF text/image boxes,
text-image and text-text overlap, blank pages, and rasterized page content.

`complete-slides` always rebuilds and audits the PDF. Completion stores a
fingerprint-bound PDF audit containing the exact `slides.tex` hash, PDF hash,
page count, engine, and artifact paths. Compilation is not optional.

## Human Validation Boundary

The machine proves input lineage, source identity, required structure, claim and
Figure integrity, local media safety, conservative capacity, clean compilation,
page-count agreement, and common PDF geometry failures. Human review remains
responsible for scientific faithfulness, narrative emphasis, pacing, readable
figure details, and subtle visual balance across every rasterized page.
