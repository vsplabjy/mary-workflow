---
description: Manage paper state, close-read and summarize papers, build Marp slides, or run grounded expert Q&A.
argument-hint: [read|summarize|slides|quiz|create|list|status|apply-action] [source/options]
---

# /mw-paper

Manage project-local paper workspaces without entering the milestone workflow authorization flow.

## Instructions

1. Work from the user's current project root. `/mw-init` is not required.
2. Route low-level `$ARGUMENTS` to the paper runtime:

   ```bash
   python ~/.codex/skills/mary-workflow/scripts/mw_paper.py <subcommand> <options>
   ```

3. Supported state subcommands:
   - no arguments: run `list`;
   - `list`: list registered paper ids;
   - `status [paper-id]`: run `status`, adding `--paper-id` when supplied;
   - `create --source <locator> --fingerprint <sha256> [--paper-id <id>]`: create an independent paper state;
   - `apply-action [paper-id]`: apply one `start_stage`, `complete_stage`, `fail_stage`, `reset_stage`, or `update_source` envelope with `--json` or `--file`;
   - `migrate-artifacts [paper-id]`: move legacy root-level `source.*` and generated `.json` files into `artifacts/`, preserving root `state.json` and refusing conflicts.
4. For `read <source>` (the source may be a folder containing a PDF and optional LaTeX tree):
   - run `python ~/.codex/skills/mary-workflow/scripts/mw_paper.py prepare-read --source <source>`;
   - inspect `artifacts/read-context.json`, the full `artifacts/parse-quality.json`, and all of `artifacts/source.md`;
   - for a folder source, inspect `reading.md`, `reading-summary.md`, `artifacts/reading-context.json`, and `artifacts/source-manifest.json`; the PDF-derived `artifacts/source.md` remains the evidence source and `reading.md` is the English learner-facing draft;
   - if `gate=blocked`, report the five dimensions and evidence, then end the response without creating notes;
   - otherwise refine `reading.md` according to `references/paper-reading-contract.md`: use `reading-profile.md` to scan every section for reader-blocking terms, sentences, and mechanisms; retain every English original span and append Chinese only in parentheses immediately after the selected span. Place detailed help in a longer parenthetical annotation after its English passage, never as a replacement or standalone Chinese paragraph. Do not submit an unchanged source draft or a full translation; retain the empty `Open question` and `Reader notes` areas;
   - create `paper-notes.md` per `references/paper-notes-contract.md`, run `complete-read`, then create/update and read back the Notion paper page under `本科学习/科研 / 项目/读论文` when the user did not specify another path. First create or reuse the `Original paper` child page for annotated `reading.md`, then write the Chinese guide from `reading-summary.md` on the paper page; never use a toggle. Follow `skills/notion/SKILL.md` for schema discovery, fetch-before-write, protected blocks, sequential writes, and verification.
5. A later explicit user quality override may be completed with `complete-read --override-quality --override-reason <reason>`. The initial read request is not override consent.
6. For `summarize [paper-id]`:
   - run `prepare-summary`, specifying `--paper-id` when needed;
   - read `paper-notes.md`, `artifacts/summary-context.json`, and cited `artifacts/source.md` spans;
   - create `summary.md` as a coherent article for a peer who has not read the paper, with Background, Method, and Experiments H2 sections;
   - make Method the longest and most explanatory section, explain intuition and mechanism rather than listing modules, and use LaTeX for useful formulas;
   - mark key factual sentences inline with `[Bxx]`, `[Mxx]`, or `[Exx]`;
   - create `artifacts/summary-ledger.json` separately, containing only direct claim quadruples grounded in the paper-notes allowlist and exact source excerpts;
   - keep interpretation and connective reasoning in prose, leave unresolved points in P2 uncertainties, and do not add old `direct`/`inferred` labels;
   - run `complete-summary` and do not bypass body-anchor, locator, evidence, or dual-file fingerprint rejection.
7. Treat `.mary-research/papers/<paper-id>/state.json` as authority. Never hand-edit state or generated context/index files.
8. Do not invoke `/mw-plan`, `/mw-run`, grants, or execution leases for paper actions.
9. For `slides [paper-id]`:
   - run `prepare-slides`, specifying `--paper-id` when needed;
   - use the generated paper-local `Makefile` or the `.mary-research/Makefile` dispatcher: `make slide` creates `build/slides.pdf` from the current `slides.md`, while `make hypo-template` creates `build/hypo-template-preview.pdf` from the isolated original Hypoxanthine-LaTeX preview without replacing the main slide; pass `PAPER_ID=<paper-id>` at the research root when needed;
   - treat the emitted `workspace_theme` and `vscode_settings` as generated project support: open the target project root in VS Code so every nested paper deck resolves the offline theme;
   - read all of `summary.md`, `artifacts/summary-ledger.json`, `artifacts/slides-context.json`, and `references/slides-contract.md`;
   - write `slides.md` as a clear research-group talk using the ShanghaiTech red `mary-shanghaitech-red` theme, `16:9`, and `math: katex`;
   - lead with the research problem, make Method at least two pages and the most detailed part, then present experiments and takeaways without adding facts outside the summary claim ledger;
   - add one hidden `<!-- section: ... -->` and `<!-- claims: ... -->` declaration to each factual page, keeping `[B01]`-style ids out of visible slide text;
   - use at least two VSP-Marp multi-panel layouts such as `cols-2-64`, `cols-3`, `rows-2-*`, or `pin-3` according to content shape;
   - reserve paper visuals with the exact numbered Figure placeholder contract and caption/locator from `artifacts/slides-context.json`. `prepare-slides` automatically collects original visuals into `figures/` and records their matching paths in `figure_assets`; always embed a selected Figure's recorded local asset inside its placeholder. A LaTeX asset is preferred and the source-PDF page is the fallback. Do not fetch from the network or fabricate a replacement;
   - run `lint-slides`, fix every rejection, then run `complete-slides`; add `--smoke-compile` only when local Marp CLI is available and the user wants the optional check.
10. For `quiz [paper-id]`:
   - run `prepare-quiz`, specifying `--paper-id` when needed, then read `artifacts/quiz-context.json` and `references/quiz-contract.md`;
   - run `next-quiz-question`, then use its Mxx anchor and the Method prose in `summary.md` to ask exactly one localized question that teaches the paper's intuition, mechanism, information flow, design rationale, or consequences;
   - never turn `source_quality_notes` into questions: PDF column order, parser reliability, formula extraction, missing image pixels, table alignment, and workflow contracts are audit concerns rather than paper-understanding quiz topics;
   - scientific Uxx uncertainties are eligible only when their `quality_dimensions` are empty; ask one after the first Method question when the content catalog is non-empty, while parse-quality SQxx notes remain non-selectable;
   - judge the answer as exactly `supported`, `partially-supported`, `unsupported`, or `uncertain`; do not translate the result into binary correct/incorrect language;
   - write a concise correct answer in the user's language from the selected anchors, relevant summary prose, and cited source spans, including when the user says next/skip/end; copy at least one exact source excerpt and explain the judgment with calibrated reasoning;
   - submit the seven-field session through `append-quiz-session`; never edit, truncate, rejudge, or regenerate `quiz-log.md`/`artifacts/quiz-head.json` directly;
   - repeat one question at a time while the user continues; corrections are new sessions and never replace history;
   - keep every Question, User answer, Judgment with rationale, Correct answer, and Paper sources in that order in the single generated `quiz-log.md`; context/head files are internal validation sidecars;
   - when the user ends the Q&A, run `lint-quiz` and then `complete-quiz`; cover at least one current-attempt Method anchor and, only when the scientific-content catalog is non-empty, at least one Uxx anchor.
