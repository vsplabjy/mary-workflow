---
name: mary-workflow
description: Coordinate model-independent project work with persisted plans, delegated implementation, evidence-based review, and resumable milestones. Use for /mw-init, /mw-plan, /mw-run, /mw-status, /mw-stop, /mw-debug, /mw-cycle, course Lecture learning, exam review, /mw-paper research reading and presentations, or /mw-notion operations.
---

# Mary Workflow

Mary Workflow 3.0 separates coordination, worker deliverables, and runtime validation. It does not select a model, provider, reasoning effort, context window, or service tier. Every agent inherits the user's host configuration. Capabilities determine the execution route; model names do not.

## Shared contract

- User instructions define scope and authorization and take precedence over workflow defaults. Explicit authorization persists; do not ask for it again without a material scope or plan change. Discussion agreement alone does not start execution.
- The main agent coordinates, communicates with the user, integrates evidence, and applies state actions. Delegate concrete implementation, investigation, and independent verification when the host supports workers and the work benefits from delegation. Do not manufacture microtasks. Workers never accept their own delivery or mutate workflow control files.
- Read [references/subagent-contract.md](references/subagent-contract.md) before dispatch or review. A worker result is a claim to check against the actual artifact and recorded validation, not completion authority.
- Read [references/memory-contract.md](references/memory-contract.md) for initialization, refresh, or recovery. Reuse working context; verify current state and changed inputs. Persisted state defines the workflow, the brief records project understanding, and source/artifact evidence establishes implementation facts. Resolve stale brief entries instead of overriding observed facts.
- Only the main agent changes control state, using `scripts/mary_workflow.py apply-action`; the runtime enforces phase, plan version, task identity, scope, and required evidence. Its checks prevent protocol mistakes, not arbitrary shell writes by an agent with filesystem access.
- Freeze an inspectable plan before execution. Explicit `/mw-run` starts or resumes it using its digest and the actual user instruction. Retain run identity and pause state. Read [references/state-contract.md](references/state-contract.md) for legal actions and exact payloads.
- Ask only questions that change scope, acceptance, or important choices. Use structured questions if available; plain text is a complete fallback. No quota of questions, files, or milestones. Ordinary implementation details within authorized scope do not require another approval.
- Progress lists reflect persisted tasks and validation; they are not a second plan. Explain current work, findings, and blockers in the user's language. Natural-language logs may use that language; machine action names, phase values, keys, and event types stay stable English.
- Follow [references/host-contract.md](references/host-contract.md) for capability discovery, compatible fallback, and optional hooks. No hook, native memory, goal tool, or worker API is required for portability. Never fabricate independent review when only one agent was available.

## Routing

Work from the user's project root. Load only the relevant subskill:

| Request | Skill | Result |
| --- | --- | --- |
| `/mw-init` | `skills/init/SKILL.md` | inventory, module coverage, project brief |
| `/mw-plan` | `skills/plan/SKILL.md` | necessary clarification and frozen plan |
| `/mw-run` | `skills/run/SKILL.md` | dispatch, evidence, independent review, acceptance |
| `/mw-status` | `skills/status/SKILL.md` | read-only progress |
| `/mw-stop` | `skills/stop/SKILL.md` | coordinated pause and recovery record |
| `/mw-debug` | `skills/debug/SKILL.md` | diagnosis and a focused queued fix |
| `/mw-cycle` | `skills/cycle/SKILL.md` | incremental brief refresh and cycle archive |
| `/mw-learn` | `skills/lecture-learning/SKILL.md` | Slide to Lecture, raw transcript, classroom additions |
| `/mw-exam`, `/mw-review` | `skills/exam-review/SKILL.md` | chapter/exam review, self-tests, Mistake Log |
| `/slide-learning` | `skills/slide-to-lecture/SKILL.md` | source-grounded slide notes |
| `/mw-paper` | `skills/paper/SKILL.md` | independent research state, reading, summary, slides, quiz |
| `/mw-notion` | `skills/notion/SKILL.md` | schema-aware external operations with read-back |

For image/PDF crops also use `skills/roundtrip-screenshot/SKILL.md` and inspect each rendered result.

## Independent scenes

Paper state remains `paper_state_schema: 1` under `.mary-research/papers/`. Source locators, parse quality, downstream invalidation, slide compilation/render checks, and the append-only quiz hash chain stay authoritative for paper work. Paper actions do not require milestone initialization or run authorization. Read the paper skill and its content contracts; delegate bounded content work while the main agent owns paper state and external writes.

Course learning and exam review use the milestone lifecycle with local content deliverables and source/content acceptance. Preserve raw sources and transcripts; do not invent missing lecture material or classify notes as code. Notion operations remain independent, require actual connector capability, and retain fetch-before-write and read-back verification. Workers can prepare content or gather evidence; the main agent performs authorized external mutations and Git writes.

## Versioned sources and upgrades

Skills and shared references are maintained sources. `commands/*.md` are generated from subskills; `.mary-workflow/prompts/*.md` are generated from `references/phases/*.md`. Run `python scripts/mw_surfaces.py --check` to detect drift, or omit `--check` to regenerate. Do not hand-edit generated surfaces.

A project pins its runtime and prompt compatibility together. Generated project prompts are a versioned copy, not an independently maintained policy source; use the pinned bundle consistently. Ordinary init preserves an existing bundle. Use `mary_workflow.py migrate` to preview a 2.1 state migration and `migrate --apply` to apply it with backup. Use `upgrade` / `upgrade --apply` for explicit bundle upgrades. Do not reset a project merely to upgrade.

The old model-setting command is retired. Host model settings and shell integration are outside workflow ownership; neither init nor a worker may change them.
