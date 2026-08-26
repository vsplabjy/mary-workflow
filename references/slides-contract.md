# Mary Paper Slides Contract v1

The `slides` stage produces one final artifact: `slides.md`, a ShanghaiTech red Marp source deck for a research-group presentation. It consumes the completed P3.5 summary bundle and does not introduce new paper facts.

## Contents

- [Preparation](#preparation)
- [Frontmatter](#frontmatter)
- [Narrative Structure](#narrative-structure)
- [Claim References](#claim-references)
- [Figure Placeholders](#figure-placeholders)
- [VSP-Marp Layouts](#vsp-marp-layouts)
- [Capacity and Media Lint](#capacity-and-media-lint)
- [Optional Compile Smoke](#optional-compile-smoke)
- [Human Validation Boundary](#human-validation-boundary)

## Preparation

`prepare-slides` requires a completed, still-valid summary stage. It validates the summary bundle again, starts `slides`, materializes original visuals in `figures/`, and writes `artifacts/slides-context.json` with:

- exact `summary.md`, `artifacts/summary-ledger.json`, summary-bundle, source-index, and theme fingerprints;
- the allowed summary claim catalog;
- Figure ids, captions, and source locators parsed from the normalized paper;
- workspace-local original figure assets, mapped to their Figure ids when available;
- the required theme, format, math engine, and lint limits.

Read all of `summary.md`, `artifacts/summary-ledger.json`, and `artifacts/slides-context.json` before writing. Use the article for explanation and the claim ledger for factual statements. Do not hand-edit generated context or state files.

Preparation also copies the self-contained offline theme to
`<project>/.mary-research/marp/themes/mary-shanghaitech-red.css` and merges its registration into
`<project>/.vscode/settings.json`. Unrelated setting values and existing theme entries are retained;
Mary sets Marp HTML to `all`, math typesetting to `katex`, and registers its project-local theme once.
Open the target project root as the VS Code workspace, then every paper deck below it previews
without depending on the Mary plugin checkout or the Markdown file's depth. VS Code does not
inherit `.vscode` settings from directories above an independently opened workspace.

Preparation also installs `<paper-workspace>/Makefile` and the isolated
`<paper-workspace>/hypo-template-preview/Slide.tex`. Run `make slide` from the
paper workspace to export `build/slides.pdf` with the exact local Marp theme,
`--allow-local-files`, and the paper's relative figures. Run
`make audit-slides` before exporting to execute static lint plus the real
Chromium image-overflow audit; `make audit` is an alias. The target calls the
Mary runtime through `MW_PAPER_SCRIPT` (default:
`$HOME/.codex/skills/mary-workflow/scripts/mw_paper.py`), so installations in a
different location can set that variable explicitly. Run
`make hypo-template` to compile a separate original Hypoxanthine-LaTeX style
preview into `build/hypo-template-preview.pdf`; this is a visual comparison
artifact and must never replace the grounded `slides.md` artifact. The same
targets are available through the generated `.mary-research/Makefile` dispatcher
from the project research root; pass `PAPER_ID=<paper-id>` when needed.
From the research root, the audit command is:

```bash
make -C .mary-research PAPER_ID=<paper-id> audit-slides
```

For a folder containing LaTeX, preparation first copies the matching
`\includegraphics` asset (rasterizing a PDF asset to PNG when needed). For every
remaining PDF-backed Figure, it renders the original source page containing that
Figure's caption. This fallback intentionally keeps the complete page rather
than claiming an unverified crop. The resulting `figure_assets` records provide
the Figure id, workspace-relative `path`, kind, and source provenance; existing
materialized files are reused deterministically.

## Frontmatter

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

1. `cover_e` title page with exactly one H1;
2. at least one Background page;
3. at least two Method pages;
4. at least one Experiments page;
5. optional Takeaways pages;
6. `lastpage` closing page with a non-empty H6.

Mark every factual content page with exactly one hidden section declaration:

```markdown
<!-- section: method -->
<!-- claims: M01 M03 -->
<!-- _class: cols-2-64 -->

## Method intuition
```

Allowed sections are `background`, `method`, `experiments`, and `takeaways`. Structural `trans`, `toc_a`, and `toc_b` pages may omit section and claim declarations. Method must remain at least as detailed as Background and Experiments.

## Claim References

Each factual content page requires one `<!-- claims: ... -->` comment. Claim ids must exist in `artifacts/slides-context.json`:

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
with this exact shape:

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

## VSP-Marp Layouts

Use at least two multi-panel pages. Select layouts according to the content rather than repeating one grid:

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
- an unloaded or zero-size rendered image, or an image that crosses any slide edge by more than 50 px;
- more than 900 visible non-whitespace characters, 36 visible lines, 8 list items, or 14 code lines on one page;
- more than 24 total pages;
- a `slides.md` fingerprint that differs from the declared completion fingerprint.

The media-path and capacity checks are static. For decks with images, `complete-slides` additionally renders a temporary bare Marp HTML document at 1280x720 and measures every `<img>` against the bounding rectangle of its own `section` in Chromium. The audit checks left, right, top, and bottom overflow independently. Overflow up to 10 px is `ok`, more than 10 px through 50 px is `review`, and more than 50 px is `fail`. Unloaded and zero-size images are always `fail`. `review` is retained in stage metadata for human inspection; `fail` blocks completion.

This audit adapts VSP-Marp C17 from `Heaticy/vsp-marp` commit `8f42f099b963d753f8aee7094e2426a915abcda8`. Mary scopes each query to the current slide and extends the original bottom-only measurement to all four image edges. Runtime code is bundled under `scripts/`; it never imports the ignored `vsp-marp/` checkout.

## Render and Overflow Checks

Run deterministic lint without changing state:

```bash
python scripts/mw_paper.py lint-slides --paper-id <paper-id>
```

After inserting or changing images, run the real overflow audit without changing state:

```bash
python scripts/mw_paper.py lint-slides --paper-id <paper-id> --audit-overflow
```

`complete-slides` runs the same audit automatically whenever `slides.md` contains an image and stores the fingerprint-bound result in slide-stage metadata. It requires Node.js, Chromium/Google Chrome, and either `marp` or the cached offline `npx @marp-team/marp-cli@4.3.1`; a missing dependency or browser timeout is an explicit rejection, never a silent skip. Image-free decks return a deterministic no-image pass without those browser dependencies.

The generated Makefiles expose the same `audit-slides` target (and `audit`
alias), so the review step is reproducible from either the paper directory or
the research root.

Add `--smoke-compile` only for the separate optional Marp compile check. Both checks write temporary HTML and delete it. HTML, PDF, and PPTX are not P5 delivery artifacts; the user exports locally.

## Human Validation Boundary

The machine proves current inputs, exact artifact identity, required structure, allowed claims, Figure-reference integrity, local media existence, exact placeholder captions, closing-page purity, conservative page capacity, image loading, and image containment within the rendered slide. It cannot prove that the selected claims tell the best story, that prose is semantically faithful, or that every page is visually balanced. Human review remains responsible for scientific accuracy, emphasis, pacing, final image selection, and all `review` measurements.
