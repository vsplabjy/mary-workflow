# Notion Page Craft

The goal is a clear, maintainable page that communicates its purpose and next action
within a few seconds. Information structure is more important than decoration.

## Preserve Meaning and Structure

- Preserve the original meaning, useful order, and information volume unless the user
  explicitly asks for editorial changes.
- Keep a clear existing page mostly intact. Regroup only when the current structure is
  genuinely hard to follow.
- Prefer an exact local replacement over a whole-page rewrite.
- Never add conversation such as "I organized this for you" to the page body.
- Preserve child pages, databases, synced blocks, embeds, files, and unknown blocks.

## Choose the Document Type

### Learning or Lecture Note

1. Opening callout: topic, textbook/pages, and one to three learning threads.
2. Administrative details and deadlines as to-dos with date mentions.
3. Numbered H2/H3 content with KaTeX, derivation reasons, and relevant original images.
4. Short conclusion or mistake callout per major section; long extensions in toggles.
5. Summary, next 8-25 minute action, and the original source/PDF at the end.

### Project or Engineering Document

1. Opening callout: purpose, current status, and owner when known.
2. Goals and scope.
3. Architecture or process, using an existing diagram or Mermaid when useful.
4. Ordered operating steps with language-tagged code and expected results.
5. Results/metrics, known issues, to-dos, related pages, and attachments.

### Report or Retrospective

Lead with the conclusion, then cover background and objective, method/process,
results/evidence, problems and repairs, conclusion, and next steps.

### Hub or Index

Start with how to use the page, then group real child pages by topic, include useful
database views and a compact common-links table. Prefer a small curated index over a
large undifferentiated link dump.

### Tutorial or Experiment Record

Use prerequisites/environment, numbered steps and commands, expected output per step,
collapsible failure notes, results, and an artifact checklist. Do not perform the
student's assignment, lab code, or experiment for them.

## Titles and Rhythm

- The Notion page title already acts as H1. Do not repeat it as an H1 in the body.
- Use H2 for major sections and H3 for subsections. Do not skip heading levels.
- Keep paragraphs around two to five lines and split long passages by meaning.
- Use one consistent heading style. Semantic/number icons can aid scanning, but avoid
  decorating every line.
- Put derivations, extensions, long logs, and Q&A in toggles when they interrupt the
  main reading path.
- Use dividers only between major modules.
- Add a table of contents when the page is longer than roughly three screens.
- Use bullets for parallel points, ordered lists for procedures, and to-dos for actions.

## Callouts and Color Semantics

Keep three to six callouts on a normal page and no more than one or two per screen.
Every callout has a semantic icon; color never substitutes for heading structure.

| Meaning | Color | Typical icon |
| --- | --- | --- |
| Page orientation/reference | `blue_bg` or `gray_bg` | compass/book/link |
| Conclusion or memory cue | `purple_bg` | idea/brain |
| Verified/recommended | `green_bg` | check |
| Warning or common mistake | `yellow_bg` | warning |
| Prohibition or danger | `red_bg` | stop |
| Ordered operation/tooling | `orange_bg` | tool |

Use bold for ordinary emphasis. Reserve inline color for a small number of comparison
terms. Do not bold entire paragraphs or fill the page with colored blocks.

## Icons

- Set a semantic icon on every new page. Move a decorative leading title emoji to the
  icon field so the title remains plain text.
- Use consistent icons for sibling pages: course, lecture, assignment, experiment,
  report, hub, plan, and attachment pages should each be visually recognizable.
- Covers are optional. Add one only when a relevant, inspectable image improves a hub or
  object page.

## Simple Tables

Use a simple table for static comparisons, parameters, terminology, or a list of fewer
than about 15 rows that does not need filtering.

- Enable a header row; use a header column only for a true comparison matrix.
- Keep at most five columns. Split a wider table or use a database.
- Make the first column the key and order remaining columns from conclusion to detail.
- Use fit-to-page for wide comparison tables and stable widths for key columns.
- Cells contain inline rich text only. Put complex formulas and multi-block material
  below the table.
- Do not promise merged cells through the API; that remains a UI action.

## Databases

Use a database when entries grow over time, need filtering/sorting/grouping, require
multiple views, have their own pages, or need relations/rollups.

1. Define what one row represents.
2. Use a specific title property, not an unexplained default `Name`.
3. Add only three to seven useful properties in addition to title.
4. Use typed fields: status/select for state, date for time, number with currency format
   for money, multi-select for tags, relation for linked entities, and rollup only for a
   real aggregate.
5. Give the default view the current actionable slice; add all/calendar/board views only
   when they serve a workflow.
6. Fetch the live schema before every write, use exact property/option names, and check
   for an existing row before creating one.
7. Use database/data-source operations for schema changes. Preserve an existing
   `<database>` block during page-content edits.

## Code, Media, Dates, and Math

- Add a language to every code block. Use inline code only for code-level identifiers,
  commands, functions, signals, and paths.
- Prefer the relevant original slide/paper/product image over a redrawn substitute.
  Place it next to the explanation and give it a caption.
- Use Mermaid only when no suitable original diagram exists and the relationship merits
  a diagram. Quote node text containing special characters.
- Embed a complete source PDF in the final source section when appropriate.
- Use date mentions with the correct time zone for deadlines, not plain text dates.
- Apply the math profile in `references/notion-task-profiles.md`; keep complex equations out of tables.

## Ordered-List Continuity

Notion may restart numbering after an image, equation, code block, table, or paragraph.
Indent supporting blocks under the owning list item. If continuity still cannot be
preserved, use explicit `Step 1`, `Step 2`, and so on. A procedural page must not show
several meaningless `1.` items.

## Delivery Checklist

- [ ] Exact target and parent were verified?
- [ ] New page has a semantic icon and a plain title?
- [ ] Body does not repeat the page title as H1?
- [ ] H2/H3 hierarchy is logical and a long page has a table of contents?
- [ ] Callout count and colors follow one semantic system?
- [ ] Tables are readable, at most five columns, and contain only inline content?
- [ ] Database schema/property casing/options were fetched and inserts deduplicated?
- [ ] Formulas render, delimiters close, and complex math stays outside tables?
- [ ] Ordered steps remain continuous after embedded blocks?
- [ ] Code blocks have languages and inline code is restrained?
- [ ] Child pages, databases, synced blocks, embeds, files, and unknown blocks remain?
- [ ] Images/PDFs are real, captioned, and placed with their related content?
- [ ] Deadlines use date mentions with the right time zone?
- [ ] Meaning and required information were preserved?
- [ ] A final fetch verified the visible result and properties?
