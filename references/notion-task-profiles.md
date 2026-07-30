# Notion Task Profiles

Read only the sections that match the current request, alongside the required Notion
references.

## Format Cleanup

- Fetch the complete page and classify its document type.
- List concrete defects internally: hierarchy, numbering, table misuse, formula errors,
  over-decoration, redundant title, spacing, or incorrect block type.
- Preserve meaning, useful order, information volume, images, excerpts, code display,
  and all protected structures.
- Correct headings, list indentation, tables, quotes, code languages, dividers, and
  numbered-list continuity with exact local replacements.
- Remove redundant decoration and meta-text. Do not use cleanup as permission to rewrite
  content or add unsupported facts.

## Math Rendering

- Preserve mathematical meaning; change only representation needed for Notion/KaTeX.
- Inline math uses unescaped dollar delimiters around a backtick-delimited LaTeX
  expression. Block equations use paired `$$` delimiters on separate lines.
- Use LaTeX commands for Greek letters and functions: `\mu`, `\sigma`, `\alpha`,
  `\sum`, `\prod`, `\exp`, `\log`, `\mathrm{softmax}`.
- Do not double-escape backslashes. Keep operators/model names upright with `\mathrm{}`.
- Use block equations for derivations and long definitions. Keep complex math outside
  table cells.
- Distinguish currency such as `$100` or `$3.5M` from math.
- After writing, check for escaped delimiters, naked math, doubled backslashes,
  unmatched delimiters, and equations left as plain text.

## Paper Translation and Research Notes

- Preserve paragraph order, formulas, variables, citations, figure/table numbers,
  measurements, model names, experimental settings, and ablation findings.
- Produce natural academic Chinese without deleting, extending, or speculating beyond
  the source. Keep terminology consistent and retain the English term at first use when
  useful.
- Break hard English into readable units and add a one-sentence main thread only when
  the requested page type calls for study guidance. If the user asks for page-only
  translation, write only the translation to the page.
- Keep OCR uncertainty explicit and preserve the suspect source form for checking.
- Prefer these translations where context matches: feed-forward (前馈式), Gaussian
  Splatting (高斯溅射), novel view synthesis (新视角合成), cross-view attention
  (跨视角注意力), epipolar geometry (极线几何), integer-only quantization
  (纯整数量化), off-chip memory access (片外访存), throughput (吞吐率), latency
  (延迟), and ablation study (消融实验).
- When source figures are needed and a PDF exists, use the round-trip screenshot skill;
  do not leave placeholders merely for convenience.

## Slides to Lecture Notes

Classify before writing:

- **Lecture**: produce a learnable note with formulas, why each derivation works,
  essential original diagrams, conclusions, moderate extensions, summary, and next step.
- **Homework**: transcribe prompts and add collapsible mistake-prevention cards; do not
  solve the assignment.
- **Lab/Project**: preserve requirements, constraints, and light translation; do not
  write submission code or perform the experiment.

Reuse an existing empty page when the user prepared one. Otherwise create/reuse the
canonical course-hub child. Use `<course code> Lecture <N> - <topic>` consistently.
Read `skills/slide-to-lecture/SKILL.md` for the Mary course profile when that profile is
installed. For image extraction or redaction, read `skills/roundtrip-screenshot/SKILL.md`.

Place each essential image next to its concept. For a PDF: render at high resolution,
inspect the full page, crop slightly wide, trim/pad, inspect the crop, then upload and
embed. Never use an uninspected crop. Put the complete original slides at the final
source section.

Record every explicit deadline in the course page and the existing schedule/calendar
destination using `Asia/Shanghai`, after checking for duplicates.

## Screenshot or Redaction

- Render/capture, then visually read every result before using or delivering it.
- For PDF crops, inspect the full page to establish real bounds, crop generously, trim
  whitespace, add a small border, and inspect the crop for missing labels/arrows/caption.
- For answer redaction, detect actual borders when possible, paint opaque rectangles,
  flatten the output, and zoom/read it again to prove no answer pixels remain.
- If any crop is incomplete or redaction leaks, redo it. An unread image is not evidence.

## Deadlines, Plans, and Finance

- Resolve and fetch the canonical destination database/page before writing.
- Deduplicate by the natural key, such as course + task + deadline or merchant/purpose +
  amount + date.
- Use real date fields/mentions and `Asia/Shanghai`, not unstructured date prose.
- Preserve exact database property names and types from the live schema.
- For money, use a numeric property with the database's currency format; do not store a
  formatted currency string when the schema expects a number.
