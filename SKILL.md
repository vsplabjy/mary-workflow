---
name: mary-workflow
description: Coordinate model-independent project work with persisted context, plans, delegated implementation, evidence-based review, and resumable milestones. Use /mw-context for docs-first project handoff; /mw-init, /mw-plan, /mw-run, /mw-status, /mw-stop, /mw-debug, /mw-cycle for formal work; course learning, /mw-paper, /mw-notion and /mw-humanize for content; /mw-experiment for settled-method trials and /mw-quick for small changes.
---

# Mary Workflow

Mary Workflow 3.0 separates coordination, worker deliverables, and runtime validation. Shared execution choices and host-setting rules are maintained in the policy below.

## Shared policy

Read [task-policy.md](references/task-policy.md) once, then load only the relevant skill. It owns process selection, authorization, delegation, local records and shared delivery rules. Use direct work for bounded changes, experiment runs for settled methods, and formal milestones for explicit staged acceptance or already-bound work. Ordinary course notes and review are direct content tasks.

Deliver compact human-readable HTML result cards for completed work packages, with aggregate reports at experiment-round end, milestone completion or an explicit report request, per [report-contract.md](references/report-contract.md). Prefer the fixed `scripts/mw_report.py` renderer when available. HTML is for the user, never a required agent handoff input. Reports/assets stay under the init-ignored `.mary-workflow/reports/`; reporting does not imply experiment or scientific acceptance.

## Routing

Work from the user's project root. Load only the relevant subskill:

| Request | Skill | Result |
| --- | --- | --- |
| `/mw-context`, new conversation about an existing project | `skills/context/SKILL.md` | docs-first overview, module introductions, handoff and incremental updates |
| `/mw-experiment`, settled-method experiment runs | `skills/experiment/SKILL.md` | immediate run, status, stop, comparison and explicit audit |
| `/mw-quick`, small bounded changes | `skills/quick/SKILL.md` | direct work with relevant checks |
| `/mw-init` | `skills/init/SKILL.md` | inventory, module coverage, project brief |
| `/mw-plan` | `skills/plan/SKILL.md` | necessary clarification and frozen plan |
| `/mw-run` | `skills/run/SKILL.md` | task-sized execution, evidence, mode-aware review, acceptance |
| `/mw-status` | `skills/status/SKILL.md` | read-only progress |
| `/mw-stop` | `skills/stop/SKILL.md` | coordinated pause and recovery record |
| `/mw-debug` | `skills/debug/SKILL.md` | diagnosis and a focused queued fix |
| `/mw-cycle` | `skills/cycle/SKILL.md` | incremental brief refresh and cycle archive |
| `/mw-learn` | `skills/lecture-learning/SKILL.md` | Slide to Lecture, raw transcript, classroom additions |
| `/mw-exam`, `/mw-review` | `skills/exam-review/SKILL.md` | chapter/exam review, self-tests, Mistake Log |
| `/slide-learning` | `skills/slide-to-lecture/SKILL.md` | source-grounded slide notes |
| `/mw-paper` | `skills/paper/SKILL.md` | independent research state, reading, summary, slides, quiz |
| `/mw-humanize`, `humanizer-zh`, Chinese prose polishing | `skills/humanizer-zh/SKILL.md` | natural wording with facts, voice, and evidence preserved |
| `/mw-notion` | `skills/notion/SKILL.md` | schema-aware external operations with read-back |

For precise image/PDF crops load `skills/roundtrip-screenshot/SKILL.md` when needed.

## Independent scenes

Paper state remains `paper_state_schema: 1` under `.mary-research/papers/`. Source locators, parse quality, downstream invalidation, slide compilation/render checks, and the append-only quiz hash chain stay authoritative for paper work. Paper actions do not require milestone initialization or run authorization. Read the paper skill and its content contracts; delegate bounded content work while the main agent owns paper state and external writes.

Course learning and exam review normally run directly with local content deliverables and their content checklists. Explicit staged projects or already-bound course tasks use the formal lifecycle. Preserve raw sources and transcripts; do not invent missing lecture material or classify notes as code. Notion operations remain independent, require actual connector capability, and retain fetch-before-write and read-back verification. Workers can prepare content or gather evidence; the main agent performs authorized external mutations and Git writes.

## Versioned sources and upgrades

Skills and shared references are maintained sources. `commands/*.md` are generated from subskills; `.mary-workflow/prompts/*.md` are generated from `references/phases/*.md`. Run `python scripts/mw_surfaces.py --check` to detect drift, or omit `--check` to regenerate. Do not hand-edit generated surfaces.

A project pins its runtime and prompt compatibility together. Generated project prompts are a versioned copy, not an independently maintained policy source; use the pinned bundle consistently. Ordinary init preserves an existing bundle. Use `mary_workflow.py migrate` to preview a 2.1 state migration and `migrate --apply` to apply it with backup. Use `upgrade` / `upgrade --apply` for explicit bundle upgrades. Do not reset a project merely to upgrade.

The old model-setting command is retired. Host model settings and shell integration are outside workflow ownership; neither init nor a worker may change them.
