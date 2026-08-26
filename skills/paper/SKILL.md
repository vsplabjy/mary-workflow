---
name: paper
description: Manage Mary Workflow's v2.2 paper pipeline, perform contract-validated close reading from arXiv HTML/PDF, write readable source-grounded summaries, build linted ShanghaiTech Marp research slides, and run append-only expert Q&A with four-value source judgments. Use when the user invokes /mw-paper, asks to register or inspect a paper, read or summarize a paper, create group-meeting slides, run paper questions or a research quiz, supplies an arXiv id/URL or PDF, or applies paper stage transitions without plan/run authorization.
---

# Mary Workflow: Paper

Manage independent paper states, close reading, grounded summaries, research slides, and expert Q&A under `.mary-research/papers/`.

## Procedure

1. Work from the user's current project root; do not require `/mw-init`.
2. Use `scripts/mw_paper.py` for every state read and mutation.
3. Use `create`, `list`, `status`, and `apply-action` for low-level state operations.
4. Require a canonical paper id and SHA-256 fingerprint contract.
5. Apply stage changes only through `start_stage`, `complete_stage`, `fail_stage`, `reset_stage`, and `update_source` envelopes.
6. Preserve the dependency graph:
   - `read` has no stage dependency;
   - `summary` depends on `read`;
   - `slides` depends on `summary`;
   - `quiz` depends on `read` and `summary`, not `slides`.
7. Let source changes and stage resets mark already-started downstream stages `stale`; leave never-started stages `pending`.
8. Do not run milestone grants or leases. Paper state is independent from `.mary-workflow/` and survives `/mw-init --reset`.
9. Before producing learner-facing notes, read `references/paper-reading-contract.md` and `.mary-research/reading-profile.md` (create the profile through `/mw-init` or `ensure_reading_profile` if absent).
10. For `/mw-paper read <source>`:
   - accept a paper folder as well as an arXiv URL, HTML, or PDF; run `prepare-read --source <source>` (and `--paper-id` when needed);
   - read `artifacts/read-context.json`, `artifacts/parse-quality.json`, and all of `artifacts/source.md`;
   - when `source_bundle` is present, also read all of `reading.md`, `reading-summary.md`, `artifacts/reading-context.json`, and `artifacts/source-manifest.json`; treat PDF locators as evidence and LaTeX Markdown as the readable English organization draft;
   - if quality is blocked, show all five statuses and evidence, then stop for explicit user direction;
   - otherwise turn `reading.md` into the annotated reading surface by applying `.mary-research/reading-profile.md`: first scan every section and identify the sentences, terms, and mechanisms that exceed the learner baseline; preserve every English sentence, term, and formula, then append Chinese only in parentheses immediately after the selected original span. Put a detailed explanation in a longer, possibly multiline parenthetical annotation after the relevant English passage; never replace, delete, or rewrite English with Chinese, and never add a standalone Chinese paragraph. Do not leave the generated source draft unchanged or translate the whole paper. Retain empty `Open question` and `Reader notes` areas for post-reading reflection;
   - replace the generated `reading-summary.md` prompts with a Chinese guide grounded in both `reading.md` and `artifacts/source.md`: retain professional terminology in English, follow the paper structure, make `方法` the detailed centre (motivation, information flow, modules, objective, assumptions, and trade-offs), and keep `Related Work（简略）` and `Experiments（简略）` short;
   - write `paper-notes.md` using the exact ledger contract and run `complete-read`;
   - after local completion, resolve `本科学习` -> `科研 / 项目` -> `读论文` when no user path is specified, reuse an exact existing paper page when present or create one when absent, create or reuse its `Original paper` child page first for the full annotated `reading.md` content, then write the Chinese `reading-summary.md` guide under `## 中文概括`; never place the child page in a toggle. Remove document H1s, preserve formulas, Open question, and Reader notes blocks, write sequentially, and fetch both pages back before claiming Notion delivery. Follow `references/paper-reading-contract.md` and `skills/notion/SKILL.md` for target and protected-block rules.
11. Copy source identity and parse quality from `artifacts/read-context.json`; do not calculate or improvise those fields.
12. Keep `uncertainties` non-empty. Add every degraded or failed quality dimension to at least one uncertainty.
13. Pass `--override-quality --override-reason <reason>` only after the user explicitly accepts a displayed blocked report. Never infer consent.
14. For `/mw-paper summarize [paper-id]`:
   - run `prepare-summary`, specifying `--paper-id` when needed;
   - read `paper-notes.md`, `artifacts/summary-context.json`, and the relevant spans in `artifacts/source.md`;
   - write `summary.md` as a blog-style article for a peer who has not read the paper, with ordered Background, Method, and Experiments H2 sections;
   - make Method the longest and most explanatory section: teach the central intuition, mechanism, and information flow instead of listing components, and use LaTeX when equations help;
   - anchor key factual sentences inline with `[Bxx]`, `[Mxx]`, and `[Exx]` ids;
   - write the direct-fact ledger separately to `artifacts/summary-ledger.json`, copy `inputs` exactly from summary context, and use only `allowed_source_locators`;
   - keep interpretations, intuition, and connective reasoning in the article without inventing ledger claims; leave unresolved matters in P2 uncertainties for later expert Q&A;
   - copy each ledger claim's evidence exactly from a cited source span and do not add `direct`/`inferred` labels;
   - run `complete-summary` and report any body, anchor, locator, or evidence rejection without weakening the contract.
14. For `/mw-paper slides [paper-id]`:
   - run `prepare-slides`, specifying `--paper-id` when needed;
   - keep acquired source files and all generated JSON sidecars under `artifacts/`; use `migrate-artifacts` for legacy workspaces and never create root-level `source.*` or generated `.json` files;
   - use the generated paper-local `Makefile` or the `.mary-research/Makefile` dispatcher: `make slide` exports the current Marp deck, while `make hypo-template` creates a separate original Hypoxanthine-LaTeX visual comparison under `build/` without replacing `slides.md`; pass `PAPER_ID=<paper-id>` at the research root when needed;
   - keep the generated project-local theme and VS Code registration intact, and open the target project root as the workspace when previewing a nested deck;
   - read all of `summary.md`, `artifacts/summary-ledger.json`, `artifacts/slides-context.json`, and `references/slides-contract.md`;
   - write `slides.md` with `mary-shanghaitech-red`, `16:9`, and `math: katex` frontmatter;
   - turn the summary into a talk rather than copying paragraphs: establish the problem, teach method intuition and information flow across at least two Method pages, then show experiments and takeaways;
   - use only summary-ledger facts, attach valid hidden claim comments to factual pages, and keep claim ids invisible to the audience;
   - use at least two suitable VSP multi-panel layouts, varying columns, rows, or pin-3 according to the material;
   - inspect `figure_assets` in `artifacts/slides-context.json`. `prepare-slides` automatically materializes usable original visuals under `figures/`: it prefers the matching LaTeX asset and otherwise renders the original PDF page containing the figure caption. For every selected Figure with a `figure_assets` entry, automatically insert its relative HTML `<img src="figures/...">` node inside the matching exact Figure placeholder. Never replace it with a fabricated diagram or a network-fetched image; retain a numbered placeholder only when that Figure has no materialized asset;
   - after inserting or changing an image, run `lint-slides --audit-overflow`; repair every structure, reference, placeholder, media, capacity, unloaded-image, or image-overflow failure, and inspect every 10-50 px `review` result;
   - run `complete-slides` only after lint passes; it automatically repeats the Chromium four-edge image audit for image-bearing decks and records the fingerprint-bound result;
   - use `--smoke-compile` only as an optional temporary Marp check; do not deliver generated HTML, PDF, or PPTX.
15. Treat `assets/marp/` as the localized offline theme used by P5. Read `references/marp-assets-contract.md` before modifying it.
16. For `/mw-paper quiz [paper-id]`:
   - run `prepare-quiz`, then read `artifacts/quiz-context.json` and `references/quiz-contract.md`;
   - use `next-quiz-question` to select P3.5 Mxx Method claims in order, then read the matching Method prose and ask one pedagogical paper-understanding question in the user's language;
   - never ask about entries under `source_quality_notes`, parser reliability, PDF column ordering, extraction quality, or workflow artifacts; Uxx questions must be scientific-content uncertainties only, and cover one after the first Method question when that catalog is non-empty;
   - wait for the user's answer instead of inventing one;
   - classify only as `supported`, `partially-supported`, `unsupported`, or `uncertain`, then write a concise correct answer in the user's language using only the selected anchors, relevant summary prose, and cited source spans; produce it even when the user skips or ends the quiz;
   - add a calibrated judgment rationale and at least one exact excerpt from an anchor-backed `artifacts/source.md` locator, then append the seven-field record through `append-quiz-session`; never hand-edit, truncate, delete, or rejudge existing `quiz-log.md` sessions;
   - record a correction as a new session, preserving the earlier answer and judgment;
   - keep each Question, User answer, Judgment with rationale, Correct answer, and Paper sources in that order in the single readable `quiz-log.md`; context/head are internal sidecars;
   - after the user ends Q&A, run `lint-quiz` and `complete-quiz` once at least one Method anchor is covered plus one scientific Uxx when that catalog is non-empty; parse-quality-only papers complete method-only.

Read `references/paper-notes-contract.md` before producing notes, `references/summary-contract.md` before producing a summary, `references/slides-contract.md` before producing slides, and `references/quiz-contract.md` before expert Q&A. See `references/paper-state-contract.md` for state transitions and `references/marp-assets-contract.md` for the offline presentation assets.
