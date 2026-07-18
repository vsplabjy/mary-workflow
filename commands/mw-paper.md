---
description: Manage paper state, close-read papers, write grounded summaries, or build linted Marp research slides.
argument-hint: [read|summarize|slides|create|list|status|apply-action] [source/options]
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
   - `apply-action [paper-id]`: apply one `start_stage`, `complete_stage`, `fail_stage`, `reset_stage`, or `update_source` envelope with `--json` or `--file`.
4. For `read <source>`:
   - run `python ~/.codex/skills/mary-workflow/scripts/mw_paper.py prepare-read --source <source>`;
   - inspect `read-context.json` and the full `parse-quality.json`;
   - if `gate=blocked`, report the five dimensions and evidence, then end the response without creating notes;
   - otherwise read all of `source.md`, create `paper-notes.md` per `references/paper-notes-contract.md`, and run `complete-read`.
5. A later explicit user quality override may be completed with `complete-read --override-quality --override-reason <reason>`. The initial read request is not override consent.
6. For `summarize [paper-id]`:
   - run `prepare-summary`, specifying `--paper-id` when needed;
   - read `paper-notes.md`, `summary-context.json`, and cited `source.md` spans;
   - create `summary.md` as a coherent article for a peer who has not read the paper, with Background, Method, and Experiments H2 sections;
   - make Method the longest and most explanatory section, explain intuition and mechanism rather than listing modules, and use LaTeX for useful formulas;
   - mark key factual sentences inline with `[Bxx]`, `[Mxx]`, or `[Exx]`;
   - create `summary-ledger.json` separately, containing only direct claim quadruples grounded in the paper-notes allowlist and exact source excerpts;
   - keep interpretation and connective reasoning in prose, leave unresolved points in P2 uncertainties, and do not add old `direct`/`inferred` labels;
   - run `complete-summary` and do not bypass body-anchor, locator, evidence, or dual-file fingerprint rejection.
7. Treat `.mary-research/papers/<paper-id>/state.json` as authority. Never hand-edit state or generated context/index files.
8. Do not invoke `/mw-plan`, `/mw-run`, grants, or execution leases for paper actions.
9. For `slides [paper-id]`:
   - run `prepare-slides`, specifying `--paper-id` when needed;
   - read all of `summary.md`, `summary-ledger.json`, `slides-context.json`, and `references/slides-contract.md`;
   - write `slides.md` as a clear research-group talk using the ShanghaiTech red `mary-shanghaitech-red` theme, `16:9`, and `math: katex`;
   - lead with the research problem, make Method at least two pages and the most detailed part, then present experiments and takeaways without adding facts outside the summary claim ledger;
   - add one hidden `<!-- section: ... -->` and `<!-- claims: ... -->` declaration to each factual page, keeping `[B01]`-style ids out of visible slide text;
   - use at least two VSP-Marp multi-panel layouts such as `cols-2-64`, `cols-3`, `rows-2-*`, or `pin-3` according to content shape;
   - reserve paper visuals with the exact numbered Figure placeholder contract and caption/locator from `slides-context.json`; do not download or crop figures, because the user will place screenshots in `figures/` later;
   - run `lint-slides`, fix every rejection, then run `complete-slides`; add `--smoke-compile` only when local Marp CLI is available and the user wants the optional check.
10. Do not produce `quiz-log.md`; P6 is not implemented.
