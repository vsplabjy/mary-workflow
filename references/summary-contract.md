# Mary Paper Summary Contract v1

`summary.md` is the only valid output of the `summary` stage. It contains three ordered claim sections grounded in P2 paper notes and resolvable source spans.

## Contents

- [Preparation Artifacts](#preparation-artifacts)
- [Source Locator Contract](#source-locator-contract)
- [Summary Ledger](#summary-ledger)
- [Claim Quadruple](#claim-quadruple)
- [Machine Validation](#machine-validation)
- [Rejection Rules](#rejection-rules)

## Preparation Artifacts

`prepare-summary` requires a completed, P2-validated `read` stage and creates:

| File | Purpose |
| --- | --- |
| `source-locators.json` | Deterministic index of every locator marker in `source.md` |
| `summary-context.json` | Exact input fingerprints and locators accepted by `paper-notes.md` |

The command refuses a paper-notes locator that has valid syntax but does not exist in `source.md`. It then starts or resumes the `summary` state.

## Source Locator Contract

HTML and PDF use separate canonical forms:

- HTML: `html#<anchor>`
- PDF: `pdf:p<N>` where `N` is a positive page number

`source-locators.json` records:

- paper id;
- `source.md` fingerprint, source format, and raw source fingerprint;
- one or more spans for each locator;
- each span's line range, normalized-content SHA-256, and preview.

Duplicate HTML anchors are represented as multiple spans under one locator. A locator resolves only when at least one non-empty span exists. The stored index must exactly match a fresh parse of the current `source.md` before summary completion.

`summary-context.json` restricts summary claims to locators that satisfy both conditions:

1. the locator resolves in `source.md`;
2. the locator already appears in the validated `paper-notes.md` ledger.

This prevents the summary stage from introducing an unreviewed source region while still grounding every assertion in the original paper rather than only in prior prose.

## Summary Ledger

Start `summary.md` with the schema marker and one fenced JSON object:

````markdown
<!-- mary-summary:v1 -->
```json
{
  "summary_schema": 1,
  "paper_id": "arxiv-2401.12345v2",
  "inputs": {
    "paper_notes": {
      "artifact": "paper-notes.md",
      "fingerprint": "<paper-notes-sha256>"
    },
    "source": {
      "artifact": "source.md",
      "artifact_fingerprint": "<source-md-sha256>",
      "format": "html",
      "source_fingerprint": "<raw-source-sha256>"
    },
    "source_locators": {
      "artifact": "source-locators.json",
      "fingerprint": "<locator-index-sha256>",
      "schema": 1
    }
  },
  "sections": {
    "background": [
      {
        "claim_id": "B01",
        "claim_text": "The paper studies ...",
        "evidence": "Exact normalized source excerpt ...",
        "source_locators": ["html#S1"]
      }
    ],
    "method": [
      {
        "claim_id": "M01",
        "claim_text": "The proposed method ...",
        "evidence": "Exact normalized source excerpt ...",
        "source_locators": ["html#S2"]
      }
    ],
    "experiments": [
      {
        "claim_id": "E01",
        "claim_text": "The evaluation reports ...",
        "evidence": "Exact normalized source excerpt ...",
        "source_locators": ["html#S3"]
      }
    ]
  }
}
```
````

The top-level fields and section order are exact. Each of `background`, `method`, and `experiments` must contain at least one claim.

## Claim Quadruple

Every claim contains exactly four fields:

| Field | Contract |
| --- | --- |
| `claim_id` | globally unique; `Bxx`, `Mxx`, or `Exx` matching its section |
| `claim_text` | non-empty summary assertion with at least 10 characters |
| `evidence` | exact 8-500 character excerpt from normalized `source.md` |
| `source_locators` | non-empty, duplicate-free array of allowed canonical locators |

Whitespace is normalized before evidence matching. Evidence must occur within at least one span addressed by `source_locators`; citing a real locator that does not contain the excerpt is rejected.

The machine proves identity, lineage, locator existence, and excerpt containment. It cannot prove that `claim_text` is a logically correct interpretation of the excerpt; that semantic judgment remains visible for human review.

## Machine Validation

`complete-summary` performs these checks before `summary -> complete`:

1. Recompute `source-locators.json` from current `source.md` and compare it exactly with the stored index.
2. Verify `paper-notes.md`, `source.md`, locator-index, and raw-source fingerprints against current state/context.
3. Recompute the set of locators accepted by paper notes.
4. Require the exact three-section ledger and exact claim quadruple fields.
5. Validate claim ID prefix and global uniqueness.
6. Resolve every locator to a non-empty source span.
7. Require every locator to have appeared in paper notes.
8. Match normalized evidence under at least one cited span.
9. Match declared `summary.md` fingerprint to its actual bytes.

On success, summary stage metadata records claim totals, per-section counts, cited-locator count, and context/index fingerprints.

## Rejection Rules

Completion is rejected when any of these is true:

- read is incomplete, stale, or lacks P2 source-format metadata;
- paper-notes bytes differ from the completed read fingerprint;
- a paper-notes locator is syntactically valid but absent from `source.md`;
- locator index or summary context is missing, tampered, or stale;
- schema, paper id, inputs, section names, or section order differs from the contract;
- any required section is empty;
- a claim is not the exact four-field tuple;
- claim id has the wrong prefix or duplicates another id;
- locator syntax is invalid, locator is absent, or locator was not accepted by paper notes;
- evidence is too short/long or absent from all cited spans;
- output fingerprint differs from `summary.md`.

Rejected completion increments the normal paper rejection audit, appends the reason to `log.md`, and leaves the summary stage `in_progress`.
