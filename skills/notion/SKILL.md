---
name: notion
description: "Operate on Notion through the connected Notion MCP server. Use when the user invokes `/notion` or asks to search, read, create, update, move, comment on, organize, format, or query Notion pages and databases. Enforces fetch-before-write safety, schema-aware database changes, polished Notion page structure, and read-back verification."
---

# Notion

Treat the text after `/notion` as the complete task. This command is independent of
`.mary-workflow/` and `.mary-research/`; do not require `/mw-init`, open a milestone,
or mutate Mary state.

## Required References

Before the first Notion tool call in a task, read:

1. `references/mcp-playbook.md` for tool discovery, target resolution, mutation safety,
   and verification.
2. `references/page-craft.md` for page and database structure.
3. `references/personal-rules.md` for workspace language, routing, and study boundaries.

Also read `references/notion-markdown.md` before creating or changing page content.
Read `references/task-profiles.md` only when the task involves cleanup, math, papers,
slides, screenshots, study notes, deadlines, or another matching specialist profile.

## Execution Flow

1. Parse the request into an operation, target, scope, constraints, and expected result.
2. Inspect the Notion MCP tools available in the current session and their actual input
   schemas. Never invent a tool name or parameter from memory.
3. Resolve the exact workspace object. Prefer an explicit URL or ID; otherwise search,
   fetch likely matches, and disambiguate only when evidence cannot identify one target.
4. Read before writing:
   - Existing page: fetch current properties and full content.
   - Database or row: fetch/resolve the current data-source schema and exact options.
   - New page: resolve and fetch the intended parent first.
5. Choose the smallest suitable operation. Use page tools for page content, database or
   data-source tools for schemas and properties, and dedicated move/comment tools for
   those actions.
6. For content writes, determine the document type and build a polished, maintainable
   structure using the required references. Preserve meaning, source order, protected
   blocks, and existing useful structure.
7. Execute writes to the same page sequentially. Combine related local edits into one
   update when the tool supports it; never race multiple updates against one page.
8. Fetch the affected page, row, or database again and verify the requested result,
   formatting, properties, child pages, databases, formulas, links, and ordering.
9. Report the operation, verified result, and canonical Notion URL. Mention unresolved
   limitations plainly; never claim a Notion change without tool evidence.

## Operation Routing

- **Search/read**: search narrowly, fetch canonical results, answer from retrieved
  content, and include the page title and URL.
- **Create page**: resolve the parent, select a page skeleton, set a semantic icon,
  write the body once, then fetch it back.
- **Update/format page**: fetch first, prefer exact local replacements, and preserve
  every child-page, database, synced, embed, attachment, and unknown block.
- **Database query/write**: resolve the current schema, match property names and option
  names exactly, deduplicate before insert, and verify the resulting row/properties.
- **Database schema change**: use the database/data-source interface and verify the
  schema after mutation. Never edit a database block through page-content tools.
- **Move/comment/archive**: use the dedicated operation, verify the exact target first,
  and confirm the resulting parent, comment, or archived state afterward.
- **Bulk or destructive change**: enumerate the affected objects first. If the current
  request does not explicitly authorize those exact objects and action, obtain
  confirmation before mutation.

## Non-Negotiable Invariants

- Do not write to an existing object that has not been fetched in this task.
- Do not replace `<page>` with `<mention-page>` or remove protected blocks from fetched
  content. A child-page block changes hierarchy; a mention is only a link.
- Do not guess database property casing, status/select options, relations, users, dates,
  or parent IDs.
- Do not silently perform whole-page replacement when a local edit is sufficient.
- Do not put conversational meta-text in the Notion page.
- Do not fabricate URLs, IDs, tool results, uploads, sync status, or successful writes.
- If no authorized Notion MCP tool is available, explain that dependency and stop
  before pretending to act.

## Delivery Gate

Do not declare completion until the read-back proves that the requested content and
properties exist, protected structures remain, and the applicable checklist in
`references/page-craft.md` passes.
