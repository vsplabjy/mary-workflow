---
name: context
description: Read or maintain a docs-first project overview, module introductions and handoff using explicit changed paths, without initialization, source scans or hashes. Use /mw-context or when starting a new conversation about an existing project.
---

# Project context

Read the [shared policy](../../references/task-policy.md) and [knowledge contract](../../references/knowledge-contract.md).

From the user's project root, use the installed `scripts/mw_knowledge.py read`. This reads only persisted context, requires no init, writes nothing and resumes nothing. Read overview, module index and handoff first, then `read --module <id>` for relevant introductions. Open specific code only for implementation, verification or a concrete unknown. Do not scan the repository to answer what a documented project does.

If context is missing, reuse an existing persisted brief with `import-brief`, or author a minimal overview and relevant modules from available knowledge using `update`. Imported summaries are incomplete until enriched; never call init just to obtain context. A read-only request does not authorize creating records. Do not fabricate a full-project coverage claim from partial mapping.

Before an authorized edit, call `changed --files <exact planned paths> --reason <why>`; include newly discovered changes before finishing. Update affected module introductions and handoff after the change. If time or context is limited, leave the stale marker and explicit next steps. Formal worker receipts automatically mark observed paths stale; the coordinator then updates introductions, without scanning again. Unchanged modules need no rewrite. Experiment launch does not wait for documentation maintenance; record run IDs in handoff only when useful.

Use `update --data <authored-json> --expected-revision <revision-from-read>` for changes. No implicit commit, external sync, experiment restart, formal acceptance or bundle upgrade is authorized by reading or maintaining context.
