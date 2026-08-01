# Mary Paper Reading Contract v1

The `read` stage produces two learner-facing Markdown files: `reading.md` and
`reading-summary.md`. `paper-notes.md` remains the locatable, machine-validated
claim ledger; it is not the reading surface.

## Workspace layout

Keep the paper workspace root readable. The root contains `reading.md`,
`reading-summary.md`, `paper-notes.md`, later stage Markdown outputs, `log.md`,
and `state.json`. Put acquired source material and machine sidecars in
`artifacts/`:

- `artifacts/source.html` or `artifacts/source.pdf` and `artifacts/source.md`;
- parse, source-bundle, and read-context JSON files;
- generated locator indexes, stage contexts, ledgers, append-only quiz head, and
  `notion-context.json`.

The runtime reads legacy root-level generated artifacts for existing paper
workspaces, but all new writes use `artifacts/`.

## Source bundle

`prepare-read --source <folder>` accepts a folder containing a paper PDF and,
when available, a LaTeX source tree. It deterministically:

- selects the largest valid PDF as the evidence source;
- follows the top-level file from `00README.json`, `main.tex`, `paper.tex`, or
  the largest `.tex` file;
- expands local `\input` and `\include` files and records the relevant source
  files in `artifacts/source-manifest.json`;
- keeps PDF-derived `artifacts/source.md` as the only source used for locatable
  evidence;
- writes a LaTeX-derived `reading.md` draft, `reading-summary.md` template,
  and `artifacts/reading-context.json`.

The folder bundle fingerprint covers the selected PDF, the LaTeX dependency
closure, referenced bibliography files, and referenced figure assets. A PDF-only
source continues to use the existing single-source path.

## Learner-facing Markdown

The file must retain `<!-- mary-reading:v1 -->` and should be edited into a
coherent paper document. The default profile is `.mary-research/reading-profile.md`.

- Keep the main prose in English and preserve original technical names,
  equations, citations, measurements, and figure/table numbers.
- Add Chinese translation in parentheses at first useful use for difficult
  terminology, methods, or sentences, not as a full Chinese translation.
- Explain the reason for a method, its information flow, and the important
  trade-off when the paper assumes specialist knowledge.
- Separate source facts from intuition and extensions; never add unsupported
  results or background claims.
- At genuinely difficult or unresolved points, retain an empty `Open question`
  block so the learner can add a question later. Do not fill it with invented
  explanation.
- Keep figures as exact numbered caption/asset references unless a real inspected
  image is available. Never invent a URL for a local asset.

## Chinese reading guide

`reading-summary.md` must retain `<!-- mary-reading-summary:v1 -->`. It is a
Chinese explanation derived from both the completed `reading.md` and the
locatable original text in `artifacts/source.md`, not a translation guessed from
the title or abstract.

- Write in Chinese, retaining professional names, model names, variables,
  equations, datasets, and fixed technical terms in English.
- Follow the paper's structure. Explain the problem and motivation first, then
  make `方法` the longest section: teach its design motivation, information flow,
  key modules, objectives, assumptions, and trade-offs in order.
- Keep `Related Work（简略）` and `Experiments（简略）` concise: state only the
  relation to prior work, evaluation setup, central comparison, and supported
  takeaway necessary to understand the method.
- Keep the required sections `一句话概括`, `背景与问题`, `方法`,
  `Related Work（简略）`, `Experiments（简略）`, and `结论与开放问题`.
- Replace every generated draft prompt. `complete-read` rejects a folder-backed
  paper until the guide is substantial Chinese prose and the Method section is
  more detailed than the Related Work and Experiments sections.

## Notion delivery

After `reading.md`, `reading-summary.md`, and `paper-notes.md` pass validation:

1. Resolve and fetch `本科学习`, then fetch its child `科研 / 项目`.
2. Resolve the `读论文` section or page under that parent. A heading/toggle is
   not itself a valid Notion parent; if it is only a section, create the paper
   page under `科研 / 项目` and keep it in that section's reading index.
3. Search for an existing page with the same paper identity. Reuse and update
   the exact page when it already exists; do not create a duplicate. If the
   existing page is elsewhere and the user explicitly requested this route,
   move it only after fetching the source and destination.
4. When the user did not specify a destination, create the page under
   `本科学习` -> `科研 / 项目` -> `读论文`. Set a semantic book/research icon
   and preserve the paper title as the Notion title rather than repeating it as
   an H1 in the body.
5. Write one Notion-flavored body in this order: a collapsed `English original`
   block containing the full `reading.md` body, then the Chinese guide from
   `reading-summary.md` under `## 中文概括`. Remove each local document's marker
   and H1, preserve equations and empty Open question blocks, and never invent
   media URLs. The English original must precede the Chinese guide.
6. Follow `skills/notion/SKILL.md`: inspect live MCP schemas, fetch every
   existing target before changing it, write a page sequentially, preserve
   protected structures, and perform the final read-back.
7. Fetch the affected page again and verify title, parent, body, formulas,
   open-question blocks, links, and preserved child structures. Record the
   canonical URL in `artifacts/notion-context.json` or the paper log.

No Notion write is considered complete without read-back evidence. If the Notion
MCP connection is unavailable, finish and retain the local artifacts, report the
dependency, and do not claim that the page was created.
