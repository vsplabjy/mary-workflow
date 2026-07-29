# Mary Paper Summary Contract v1

The `summary` stage produces two coupled artifacts:

- `summary.md`: readable blog-style prose for a peer who has not read the paper;
- `summary-ledger.json`: a machine-validated ledger of direct factual claims used by the prose.

The stage output fingerprint covers the exact bytes of both files. Neither file is complete without the other.

## Contents

- [Preparation Artifacts](#preparation-artifacts)
- [Writing Contract](#writing-contract)
- [Body Anchors](#body-anchors)
- [Claim Ledger](#claim-ledger)
- [Source Locator Contract](#source-locator-contract)
- [Machine Validation](#machine-validation)
- [Human Validation Boundary](#human-validation-boundary)

## Preparation Artifacts

`prepare-summary` requires a completed, P2-validated `read` stage and creates:

| File | Purpose |
| --- | --- |
| `source-locators.json` | Deterministic index of every locator marker in `source.md` |
| `summary-context.json` | Exact input fingerprints and locators accepted by `paper-notes.md` |

Read `paper-notes.md`, `summary-context.json`, and the relevant spans of `source.md` before writing either output. Never invent or hand-edit the generated context/index files.

## Writing Contract

Write `summary.md` as an article, not a form, ledger dump, or sequence of bullet-point claims. The intended reader is a researcher in the broad field who has not read the paper.

The article may start with one H1 title. It must then contain exactly these three H2 sections in order, using either the English or Chinese heading:

1. `## Background` or `## 背景`
2. `## Method` or `## 方法`
3. `## Experiments` or `## 实验`

All three sections must contain prose. Make Method the longest and most explanatory section. Explain the method's intuition, mechanism, information flow, and why its design addresses the problem; do not merely enumerate module names. Use LaTeX delimiters such as `$...$` or `$$...$$` when equations clarify the method.

Use direct paper facts where needed, then connect them into a coherent explanation. Interpretations, intuition, comparisons, and transitions belong in the article, but must be written with calibrated language rather than promoted into ledger claims. Material that cannot be stated confidently stays in `paper-notes.md` uncertainties for later expert Q&A.

Example body shape:

```markdown
# Why this method works

## Background

The paper studies ... [B01] This matters because ...

## Method

The central idea is ... [M01] Intuitively, the update
$h_{t+1}=f(h_t,x_t)$ lets ...

### Optimization

The authors optimize ... [M02] In practical terms, ...

## Experiments

The evaluation covers ... [E01] The reported result suggests ...
```

Do not embed JSON, the old `<!-- mary-summary:v1 -->` marker, or a machine ledger in `summary.md`.

## Body Anchors

Anchor factual sentences inline with claim ids such as `[B01]`, `[M03]`, or `[E02]`.

- `Bxx` anchors belong in Background.
- `Mxx` anchors belong in Method.
- `Exx` anchors belong in Experiments.
- Every id in `summary-ledger.json` must appear in `summary.md` at least once.
- Every claim-like anchor in `summary.md` must exist in `summary-ledger.json`.
- Put an anchor on the same line as meaningful prose; a standalone `[M01]` is invalid.

An anchor establishes traceability, not semantic truth. Multiple sentences may cite the same direct claim, and one sentence may cite more than one claim.

## Claim Ledger

Write `summary-ledger.json` as a standalone JSON object:

```json
{
  "summary_ledger_schema": 1,
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
  "claims": [
    {
      "claim_id": "B01",
      "claim_text": "The paper studies ...",
      "evidence": "Exact normalized source excerpt ...",
      "source_locators": ["html#S1"]
    },
    {
      "claim_id": "M01",
      "claim_text": "The proposed method ...",
      "evidence": "Exact normalized source excerpt ...",
      "source_locators": ["html#S2"]
    },
    {
      "claim_id": "E01",
      "claim_text": "The evaluation reports ...",
      "evidence": "Exact normalized source excerpt ...",
      "source_locators": ["html#S3"]
    }
  ]
}
```

Copy `inputs` exactly from `summary-context.json`. The ledger contains only direct facts from the paper and requires at least one `Bxx`, `Mxx`, and `Exx` claim. Do not add `direct`, `inferred`, `kind`, confidence, commentary, or other classification fields.

Every claim contains exactly four fields:

| Field | Contract |
| --- | --- |
| `claim_id` | globally unique `Bxx`, `Mxx`, or `Exx`; at least two digits |
| `claim_text` | non-empty direct factual assertion with at least 10 characters |
| `evidence` | exact 8-500 character excerpt from normalized `source.md` |
| `source_locators` | non-empty, duplicate-free array of allowed canonical locators |

## Source Locator Contract

Canonical locator forms are:

- HTML/TeX-derived source: `html#<anchor>` for a section, paragraph, equation, table, or figure label;
- PDF-derived source: `pdf:p<N>` for a positive page number.

`summary-context.json` permits only locators in the intersection of:

1. locators already accepted by the validated `paper-notes.md` ledger;
2. locators that resolve to a non-empty span in the current `source.md`.

Whitespace is normalized before evidence matching. The exact evidence excerpt must occur within at least one span addressed by its `source_locators`; citing a real locator that contains different text is rejected.

## Machine Validation

`complete-summary` performs these checks before `summary -> complete`:

1. Rebuild and compare the current source locator index.
2. Verify paper notes, source, context, index, and raw-source lineage.
3. Require the exact ledger top-level fields and exact four-field claim tuple.
4. Require globally unique valid ids and at least one background, method, and experiment claim.
5. Resolve every locator and restrict it to the paper-notes-backed allowlist.
6. Match every evidence excerpt inside at least one cited source span.
7. Require exactly the three ordered, non-empty article sections.
8. Require every ledger id in the body and reject every unknown body id.
9. Require anchor prefixes to match their article sections and reject standalone anchors.
10. Match the declared output fingerprint to the exact `summary.md` plus `summary-ledger.json` bundle.

On success, state metadata records body and ledger fingerprints, claim and anchor counts, per-section counts, cited locators, and context/index fingerprints.

## Human Validation Boundary

The machine proves artifact identity, lineage, locator existence, excerpt containment, and bidirectional anchoring. It does not prove that `claim_text` is entailed by the excerpt, that the prose uses a claim correctly, or that the article explains the method well. Human review and the later expert-Q&A stage remain responsible for semantic truth, nuance, and writing quality.

Rejected completion increments the paper rejection audit, appends the reason to `log.md`, and leaves the summary stage `in_progress`.
