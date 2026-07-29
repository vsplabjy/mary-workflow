# Notion MCP Playbook

## First Call in a Task

1. Inspect the Notion MCP tools exposed in the current session.
2. Read the actual input schema for the tools needed by the request.
3. Identify which tools handle search/fetch, page creation/update, database or
   data-source operations, moves, comments, users, and attachments.
4. Use the discovered names and schemas. Examples such as `notion-search`,
   `notion-fetch`, or `notion-update-page` are illustrative, not guaranteed names.

## Resolve Targets

- Prefer a page/database URL or ID supplied by the user.
- Without one, search using exact titles and relevant scope, then fetch likely matches.
- Do not choose between equally plausible results. Present the titles/parents/URLs and
  ask the user to disambiguate.
- For a new page, identify and fetch the parent. Do not create unrequested top-level
  pages just because a parent is missing.

## Read and Search

- Fetch the canonical object before summarizing it. Search snippets are discovery
  evidence, not the full page.
- For questions spanning several pages, state which pages were read and ground the
  answer in those pages.
- Return canonical titles and URLs so the result can be checked.

## Create a Page

1. Resolve the parent and check for an existing same-purpose page.
2. Choose a title without a decorative leading emoji and set a semantic page icon.
3. Select the matching skeleton from `page-craft.md`.
4. Write coherent content in one operation when practical.
5. Fetch the created page and verify parent, title, icon, body, links, and blocks.

## Update a Page

1. Fetch full properties and body.
2. Identify exact, unique source text for local replacement. Preserve whitespace,
   escaping, closing tags, and protected block markup from the fetch result.
3. Prefer local edits. Use whole-page replacement only for an empty page, an unusable
   page whose protected content is preserved, or an explicit full-rewrite request.
4. Consolidate related edits and do not update the same page concurrently.
5. Fetch again and compare the requested areas plus all protected structures.

## Databases and Rows

1. Decide what one row represents.
2. Resolve/fetch the live data-source schema before querying or writing.
3. Use property names with exact spelling and casing. Use existing select/status option
   names unless the user explicitly requests a schema change.
4. Deduplicate on the appropriate natural key, such as title plus date, before insert.
5. Use typed values: checkbox boolean, select/status string, multi-select string array,
   relation/person URL or ID as required by the actual schema, and `null` to clear.
6. Supply date start/end/time-zone fields exactly as the current MCP schema requires.
7. Use database/data-source tools for schema operations. A `<database>` page block is
   not a substitute for a schema call.
8. Re-fetch the row and schema as applicable.

## Move, Comment, and Archive

- Move through a parent/move operation; adding a link to the destination is not a move.
- Comment through the comment interface and verify the comment is attached to the
  intended object.
- For archive/delete or bulk changes, enumerate exact targets first. Proceed directly
  only when the current user request explicitly names or unambiguously selects those
  targets and action.

## Attachments and Images

- Do not invent a `file-X` reference or upload URL.
- When cropping from a PDF, use `../roundtrip-screenshot/SKILL.md`: render, inspect the
  full page, crop generously, inspect the crop, then upload/embed.
- Place images next to the text they explain and include a caption.
- Put a complete source PDF in the final source section when the task calls for it.

## Failure Recovery

| Symptom | Likely cause | Recovery |
| --- | --- | --- |
| Update rejected | Protected/database block changed | Re-fetch and restore the exact block |
| Replacement not found | Source text is stale or not exact | Re-fetch and select a unique exact span |
| Property rejected | Casing, type, date, or option mismatch | Resolve the live schema again |
| Child page moved/disappeared | `<page>` was removed or changed | Restore/re-parent it, then verify |
| Formula rendered as text | Delimiters or backslashes are wrong | Apply the math profile and re-fetch |
| Tool unavailable/unauthorized | MCP is absent or lacks access | Report the dependency; do not simulate |
