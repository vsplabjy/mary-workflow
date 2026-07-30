---
description: Run Mary Workflow Notion MCP operations with verified, polished page and database output.
argument-hint: [Notion request, target, and constraints]
---

# /mw-notion

Run the Mary Workflow Notion profile. `$ARGUMENTS` is the requested Notion operation,
target, and constraints.

## Instructions

1. Load `skills/notion/SKILL.md` and the root `references/notion-*.md` files it marks as
   required for this task.
2. Inspect the currently connected Notion MCP tools and their schemas before use.
3. Resolve and fetch existing targets before any write. For databases, resolve the live
   schema and use exact property/option names.
4. Apply the requested operation with the smallest safe change and the Notion page-craft
   rules. Preserve protected blocks and do not issue parallel updates to the same page.
5. Fetch the result again, run the delivery checklist, and return the verified Notion URL.

If `$ARGUMENTS` is empty, ask for the concrete Notion operation and target. If Notion MCP
is unavailable or unauthorized, state that blocker and do not fabricate a result.

This command uses the Mary Workflow command surface but does not require or mutate
`.mary-workflow/` milestone state unless the user explicitly plans the Notion work as a
milestone.
