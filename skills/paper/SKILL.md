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
9. For `/mw-paper read <source>`:
   - run `prepare-read --source <source>` (and `--paper-id` when needed);
   - read `read-context.json`, `parse-quality.json`, and all of `source.md`;
   - if quality is blocked, show all five statuses and evidence, then stop for explicit user direction;
   - otherwise write `paper-notes.md` using the exact ledger contract and run `complete-read`.
10. Copy source identity and parse quality from `read-context.json`; do not calculate or improvise those fields.
11. Keep `uncertainties` non-empty. Add every degraded or failed quality dimension to at least one uncertainty.
12. Pass `--override-quality --override-reason <reason>` only after the user explicitly accepts a displayed blocked report. Never infer consent.
13. For `/mw-paper summarize [paper-id]`:
   - run `prepare-summary`, specifying `--paper-id` when needed;
   - read `paper-notes.md`, `summary-context.json`, and the relevant spans in `source.md`;
   - write `summary.md` as a blog-style article for a peer who has not read the paper, with ordered Background, Method, and Experiments H2 sections;
   - make Method the longest and most explanatory section: teach the central intuition, mechanism, and information flow instead of listing components, and use LaTeX when equations help;
   - anchor key factual sentences inline with `[Bxx]`, `[Mxx]`, and `[Exx]` ids;
   - write the direct-fact ledger separately to `summary-ledger.json`, copy `inputs` exactly from summary context, and use only `allowed_source_locators`;
   - keep interpretations, intuition, and connective reasoning in the article without inventing ledger claims; leave unresolved matters in P2 uncertainties for later expert Q&A;
   - copy each ledger claim's evidence exactly from a cited source span and do not add `direct`/`inferred` labels;
   - run `complete-summary` and report any body, anchor, locator, or evidence rejection without weakening the contract.
14. For `/mw-paper slides [paper-id]`:
   - run `prepare-slides`, specifying `--paper-id` when needed;
   - keep the generated project-local theme and VS Code registration intact, and open the target project root as the workspace when previewing a nested deck;
   - read all of `summary.md`, `summary-ledger.json`, `slides-context.json`, and `references/slides-contract.md`;
   - write `slides.md` with `mary-shanghaitech-red`, `16:9`, and `math: katex` frontmatter;
   - turn the summary into a talk rather than copying paragraphs: establish the problem, teach method intuition and information flow across at least two Method pages, then show experiments and takeaways;
   - use only summary-ledger facts, attach valid hidden claim comments to factual pages, and keep claim ids invisible to the audience;
   - use at least two suitable VSP multi-panel layouts, varying columns, rows, or pin-3 according to the material;
   - use exact context-backed Figure placeholders with visible paper Figure numbers and captions; do not fetch, crop, or fabricate figures;
   - run `lint-slides`, repair every structure, reference, placeholder, media, or capacity error, and run `complete-slides` only after lint passes;
   - use `--smoke-compile` only as an optional temporary Marp check; do not deliver generated HTML, PDF, or PPTX.
15. Treat `assets/marp/` as the localized offline theme used by P5. Read `references/marp-assets-contract.md` before modifying it.
16. For `/mw-paper quiz [paper-id]`:
   - run `prepare-quiz`, then read `quiz-context.json` and `references/quiz-contract.md`;
   - use `next-quiz-question` to cover P2 Uxx uncertainties and P3.5 Mxx Method claims, ask one question in the user's language, and wait for the user's answer;
   - classify only as `supported`, `partially-supported`, `unsupported`, or `uncertain`, with a concise rationale and an exact excerpt from an anchor-backed `source.md` locator;
   - append the six-field record through `append-quiz-session`; never hand-edit, truncate, delete, or rejudge existing `quiz-log.md` sessions;
   - record a correction as a new session, preserving the earlier answer and judgment;
   - after the user ends Q&A and both anchor families are covered, run `lint-quiz` and `complete-quiz`.

Read `references/paper-notes-contract.md` before producing notes, `references/summary-contract.md` before producing a summary, `references/slides-contract.md` before producing slides, and `references/quiz-contract.md` before expert Q&A. See `references/paper-state-contract.md` for state transitions and `references/marp-assets-contract.md` for the offline presentation assets.
