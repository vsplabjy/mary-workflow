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

`prepare-slides` requires a completed, still-valid summary stage. It validates the summary bundle again, starts `slides`, creates `figures/`, and writes `slides-context.json` with:

- exact `summary.md`, `summary-ledger.json`, summary-bundle, source-index, and theme fingerprints;
- the allowed summary claim catalog;
- Figure ids, captions, and source locators parsed from the normalized paper;
- the required theme, format, math engine, and lint limits.

Read all of `summary.md`, `summary-ledger.json`, and `slides-context.json` before writing. Use the article for explanation and the claim ledger for factual statements. Do not hand-edit generated context or state files.

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

Each factual content page requires one `<!-- claims: ... -->` comment. Claim ids must exist in `slides-context.json`:

- Background pages use only `Bxx` claims.
- Method pages use only `Mxx` claims.
- Experiments pages use only `Exx` claims.
- Takeaways may combine all three families.

Reference at least one claim from every family across the deck. Keep claim ids hidden in comments; do not display P3 markers such as `[M01]` to the audience. Claim comments prove lineage, not semantic truth. Do not add facts that exist only in `source.md` or general knowledge.

## Figure Placeholders

When `slides-context.json` contains figures, use at least one. Do not download, crop, invent, or embed paper images. Reserve the intended panel with this exact shape:

```html
<div class="rimg figure-placeholder"
     data-figure="Figure 2"
     data-source-locator="html#S3.F2">
  <div class="figure-placeholder__number">Figure 2</div>
  <div class="figure-placeholder__caption">Figure 2: Caption from the context catalog.</div>
</div>
```

Use the exact `figure_id`, caption, and one matching locator from the context. Combine `figure-placeholder` with one VSP image-panel class: `limg`, `mimg`, `rimg`, `timg`, or `bimg`. Every visible reference to a paper Figure on a page must have its matching placeholder on that page.

After delivery, the user may replace the placeholder body with a screenshot under `figures/` and export locally. The P5 acceptance artifact itself deliberately retains numbered placeholders.

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
- more than 900 visible non-whitespace characters, 36 visible lines, 8 list items, or 14 code lines on one page;
- more than 24 total pages;
- a `slides.md` fingerprint that differs from the declared completion fingerprint.

These are conservative static limits. Passing them does not prove pixel-perfect layout.

## Optional Compile Smoke

Run deterministic lint without changing state:

```bash
python scripts/mw_paper.py lint-slides --paper-id <paper-id>
```

Add `--smoke-compile` to `lint-slides` or `complete-slides` only when `marp` or a cached `npx @marp-team/marp-cli@4.3.1` is available. The smoke test writes temporary HTML and deletes it. HTML, PDF, and PPTX are not P5 delivery artifacts; the user exports locally.

## Human Validation Boundary

The machine proves current inputs, exact artifact identity, required structure, allowed claims, Figure-reference integrity, local media existence, and conservative page capacity. It cannot prove that the selected claims tell the best story, that prose is semantically faithful, or that every page is visually balanced. Human review remains responsible for scientific accuracy, emphasis, pacing, and final image selection.
