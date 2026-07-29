---
description: Read, create, update, organize, or format Notion content through Notion MCP.
argument-hint: <Notion request, target, and constraints>
---

# /notion

Carry out `$ARGUMENTS` as a Notion task.

1. Load `skills/notion/SKILL.md` and every reference it marks as required for this task.
2. Do not require `.mary-workflow/`, `/mw-init`, planning, or a run token.
3. Inspect the currently connected Notion MCP tools and their schemas before use.
4. Resolve and fetch existing targets before any write. For databases, resolve the live
   schema and use exact property/option names.
5. Apply the requested operation with the smallest safe change and the Notion page-craft
   rules. Preserve protected blocks and do not issue parallel updates to the same page.
6. Fetch the result again, run the delivery checklist, and return the verified Notion URL.

If `$ARGUMENTS` is empty, ask for the concrete Notion operation and target. If Notion MCP
is unavailable or unauthorized, state that blocker and do not fabricate a result.
