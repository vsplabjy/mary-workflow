# Mary Paper State Contract v1

The paper pipeline is independent from the v2.1 milestone state machine. It reuses common envelope, atomic-write, and append-log primitives but never uses plan/run grants or execution leases.

## Directory Layout

```text
.mary-research/
└── papers/
    └── <paper-id>/
        ├── state.json
        ├── log.md
        ├── source.html or source.pdf
        ├── source.md
        ├── parse-quality.json
        ├── read-context.json
        ├── paper-notes.md
        ├── source-locators.json
        ├── summary-context.json
        ├── summary.md
        ├── summary-ledger.json
        ├── slides-context.json
        ├── slides.md
        ├── figures/
        ├── quiz-context.json
        ├── quiz-log.md
        └── quiz-head.json
```

`/mw-paper` may create this directory before `/mw-init`. The main workflow remains authoritative only through `.mary-workflow/state.yaml`; each paper is authoritative through its own `state.json`. `/mw-init --reset` and `/mw-cycle` do not delete `.mary-research/`, and the v2.1 project scanner excludes it.

## Identity

- `paper_state_schema` is the integer `1` and is versioned independently from the plugin and workflow schemas.
- `paper_id` is a canonical, path-safe lowercase id with at most 128 characters.
- arXiv locators normalize to `arxiv-<identifier>`, retaining an explicit `vN` revision when present.
- Changing an arXiv locator to a different identifier or `vN` revision requires a separate paper workspace.
- non-arXiv inputs default to `local-<first-16-source-sha256>`.
- path separators, `..`, and non-canonical ids are rejected.

## Fingerprints

Every fingerprint is a lowercase 64-character SHA-256 hex digest:

- `source.fingerprint` identifies the acquired source revision;
- each stage snapshots `input_fingerprints` when it starts;
- each completed stage requires `output_fingerprint`;
- a stage cannot complete if its snapshotted inputs no longer match current upstream fingerprints.

Low-level `create` accepts a precomputed source fingerprint. `prepare-read` acquires the source, hashes the selected raw HTML/PDF bytes, and updates or creates the paper state with that fingerprint.

## Stage Graph

```text
read ──> summary ──> slides
  └────────┴───────> quiz
```

The exact dependencies are:

| Stage | Required completed inputs |
| --- | --- |
| `read` | current source fingerprint |
| `summary` | `read` output |
| `slides` | `summary` output |
| `quiz` | `read` and `summary` outputs |

`quiz` deliberately does not depend on `slides`.

## Stage Status

Each stage uses one of:

- `pending`: never started or explicitly reset;
- `in_progress`: started with a current input snapshot;
- `complete`: valid output fingerprint exists;
- `failed`: the latest attempt failed with an error;
- `stale`: a source or upstream reset invalidated an already-started stage.

Legal transition paths are:

```text
pending|failed|stale --start_stage--> in_progress
in_progress --complete_stage--> complete
in_progress --fail_stage--> failed
in_progress|complete|failed|stale --reset_stage--> pending
```

A complete stage must be reset before rerun. Dependencies must be complete before a stage starts.

The `read` stage has an additional P2 completion gate: `artifact` must be `paper-notes.md`, its byte fingerprint must match `output_fingerprint`, and the ledger must pass `references/paper-notes-contract.md`. A successful read stores parse-quality decision metadata.

The `summary` stage has a P3.5 completion gate: `artifact` remains `summary.md`, while the stage output fingerprint covers both `summary.md` and `summary-ledger.json`. The article must pass the three-section and bidirectional-anchor rules; every direct ledger claim must pass `references/summary-contract.md`, and its evidence and locators must resolve against the current source index.

The `slides` stage has a P5 completion gate: `artifact` must be `slides.md`, its byte fingerprint must match `output_fingerprint`, and the current summary bundle plus generated `slides-context.json` must pass `references/slides-contract.md`. The lint enforces the ShanghaiTech Marp/KaTeX frontmatter, research-talk structure, summary-claim references, resolvable Figure placeholders, local media, multi-panel usage, and conservative per-page capacity. Marp compilation is optional and creates no persistent export artifact.

The `quiz` stage has a P6 completion gate: `artifact` must be `quiz-log.md`, its byte fingerprint must match `output_fingerprint`, and the current read/summary lineage plus `quiz-context.json` must pass `references/quiz-contract.md`. Current-attempt sessions must cover at least one P2 uncertainty and one P3.5 Method claim, use a four-value judgment, and cite exact resolvable source excerpts. `quiz-log.md` is append-only across attempts; its session hash chain and `quiz-head.json` checkpoint reject deletion, answer edits, and rejudgment.

## Stale Propagation

- Changing `source.fingerprint` marks an already-started `read` stale and cascades through `summary`, `slides`, and `quiz`.
- Resetting `read` stales already-started `summary`, `slides`, and `quiz`.
- Resetting `summary` stales already-started `slides` and `quiz`.
- Resetting `slides` or `quiz` has no downstream effect.
- A stage that has never started remains `pending`; it is not mislabeled stale because no artifact exists to invalidate.
- Stale stages retain prior lineage for audit until the next `start_stage`, which clears invalid output fields and snapshots current inputs.

## Action Envelopes

Start a stage:

```json
{"action":"start_stage","data":{"stage":"read"}}
```

Complete a stage:

```json
{
  "action": "complete_stage",
  "data": {
    "stage": "read",
    "output_fingerprint": "<sha256>",
    "artifact": "paper-notes.md"
  }
}
```

For `read`, use `complete-read` rather than constructing this envelope manually. The command computes the notes fingerprint and enforces the parse-quality gate. A blocked report requires explicit user confirmation and a reason; the accepted override is recorded in `quality-override-<attempt>.json`, stage metadata, and `log.md`. Use `prepare-slides`, `lint-slides`, and `complete-slides` for the P5 artifact. Use `prepare-quiz`, `next-quiz-question`, `append-quiz-session`, `lint-quiz`, and `complete-quiz` for P6; never hand-edit or replace its append-only files.

Fail or reset a stage:

```json
{"action":"fail_stage","data":{"stage":"read","error":"parser unavailable"}}
```

```json
{"action":"reset_stage","data":{"stage":"summary"}}
```

Update the source revision:

```json
{
  "action": "update_source",
  "data": {
    "locator": "https://arxiv.org/abs/2401.12345v2",
    "fingerprint": "<sha256>"
  }
}
```

Rejected envelopes increment `audit.rejected_actions`, append the rejection reason to the paper log, atomically persist the unchanged domain state plus audit count, and exit nonzero.
