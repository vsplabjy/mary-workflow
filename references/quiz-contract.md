# Mary Paper Expert Q&A Contract v3

The `quiz` stage runs an interactive expert Q&A grounded in the completed close-reading and
summary artifacts. Its final artifact is `quiz-log.md`; it does not depend on `slides`.

## Contents

- [Preparation](#preparation)
- [Question Anchors](#question-anchors)
- [Interactive Flow](#interactive-flow)
- [Four-Value Judgment](#four-value-judgment)
- [Session Payload](#session-payload)
- [Source Citations](#source-citations)
- [Append-Only History](#append-only-history)
- [Completion Gate](#completion-gate)
- [Human Validation Boundary](#human-validation-boundary)

## Preparation

`prepare-quiz` requires completed, current `read` and `summary` stages. It revalidates
`paper-notes.md`, the summary bundle, and `source-locators.json`, then starts the `quiz` attempt and
creates:

| File | Purpose |
| --- | --- |
| `quiz-context.json` | Internal input fingerprints, pedagogical anchors, source-quality notes, and attempt id |
| `quiz-log.md` | The only delivered artifact: canonical append-only readable Q&A sessions |
| `quiz-head.json` | Accepted session count, chain head, and exact log fingerprint |

Do not hand-edit any of these files. A reset starts a new attempt but retains all prior sessions in
`quiz-log.md`; old sessions remain audit history and cannot satisfy the new attempt's coverage gate.
`quiz-context.json` and `quiz-head.json` are internal validation sidecars. Every question actually
asked, user answer, four-value judgment, correct answer, judgment rationale, and source citation is
archived together in the single `quiz-log.md` file.

## Question Anchors

The quiz exists to deepen the user's understanding of the paper; parser, PDF, and workflow
meta-questions are outside its scope.

`quiz-context.json` separates pedagogical anchors from source-processing audit notes:

- `Mxx` anchors are the direct Method claims accepted from P3.5 `summary-ledger.json`. They retain
  claim text, exact evidence, and source locators. These are the primary question source.
- conditional `Uxx` anchors come only from scientific-content uncertainties whose
  `quality_dimensions` array is empty. They retain the research question, unresolved reason,
  impact, and source locators.
- uncertainties tied to PDF/HTML parsing dimensions are converted to non-selectable `SQxx` entries
  under `source_quality_notes`. Structure recovery, column order, formula extraction, missing image
  pixels, and table alignment are audit information and must never become user quiz questions.

Run `next-quiz-question` to choose an underused Method anchor in ledger order. It asks a Method
question first, then covers one scientific Uxx when that catalog is non-empty, before returning to
later Method details. The agent must
read the Method prose in `summary.md` and turn the selected claim into a pedagogical question about
intuition, information flow, design rationale, optimization, or consequences; do not merely recite
the raw claim template.

Every session selects at least one `Mxx` or scientific `Uxx` id. Unknown ids and `SQxx` audit ids
are rejected. Completion always requires at least one current-attempt Method anchor. It additionally
requires at least one scientific Uxx anchor when `scientific_uncertainty_catalog` is non-empty;
parse-quality-only papers therefore use method-only completion.

## Interactive Flow

1. Run `prepare-quiz` and read all of `quiz-context.json` plus the relevant `source.md` spans.
2. Run `next-quiz-question`, use the selected Mxx claim plus `summary.md` Method prose to ask exactly
   one paper-understanding question in the user's language. Never ask about parser reliability,
   PDF column order, extraction quality, or artifact contracts.
3. Stop and wait for the user's answer. Do not invent an answer on the user's behalf.
4. Assess the answer with one four-value judgment, write a concise source-grounded correct answer
   in the user's language, add a calibrated rationale, and copy exact source citations. A skipped
   answer such as "next question" still requires the correct answer.
5. Submit the seven-field payload to `append-quiz-session`; never write `quiz-log.md` directly.
6. Repeat from step 2 while the user wants more questions.
7. Run `lint-quiz`, then `complete-quiz` only when the user ends the session, at least one Method
   anchor is covered, and one scientific Uxx is covered when the content catalog is non-empty.

## Four-Value Judgment

Use exactly one of these values. Do not collapse them to binary correct/incorrect wording.

| Value | Meaning |
| --- | --- |
| `supported` | The answer's material assertions are fully supported by the cited paper spans |
| `partially-supported` | Some material content is supported, but an important step or qualification is missing |
| `unsupported` | At least one material assertion is not supported by the cited paper spans |
| `uncertain` | The available text, evidence, or parse quality is insufficient for a confident decision |

`unsupported` means unsupported by this paper evidence, not necessarily false in the wider field.
`uncertain` is a valid outcome and must not be forced into another class.

## Session Payload

Submit one JSON object through `append-quiz-session --json`, `--file`, or stdin:

```json
{
  "question": "How does the optimization step preserve the intended representation?",
  "anchors": {
    "uncertainty_ids": [],
    "method_claim_ids": ["M03"]
  },
  "answer": "The user's answer, recorded without silent correction.",
  "judgment": "partially-supported",
  "correct_answer": "The source-grounded answer the user should retain after this question.",
  "rationale": "The answer identifies the update but omits the constraint stated by the paper.",
  "citations": [
    {
      "source_locator": "html#S3.E2",
      "evidence": "Exact normalized excerpt copied from source.md"
    }
  ]
}
```

The runtime owns `session_id`, timestamp, context fingerprint, previous-entry hash, and entry hash.
It appends a canonical readable Markdown view in this order: Question, User answer, Judgment with
its rationale, Correct answer, and Paper sources. Anchors remain in the collapsed machine record
rather than interrupting the readable study archive. Callers cannot provide or override audit
fields, and the runtime rejects any divergence between the generated view and record.

## Source Citations

Every judgment and correct answer share at least one citation with exactly `source_locator` and
`evidence`:

- the locator must belong to at least one selected `Mxx` or scientific `Uxx` anchor;
- the locator must resolve in the current `source.md` index;
- evidence must be an exact normalized 8-500 character excerpt within that locator's span;
- duplicate locator/excerpt pairs are rejected.

These checks prove traceability and excerpt containment. They do not prove that the judgment's
semantic interpretation is correct.

## Append-Only History

Each accepted session hashes all of its immutable fields and points to the previous session hash.
`quiz-head.json` records the accepted chain head, count, and whole-log fingerprint. Before every
append, lint, or completion, the runtime reconstructs the canonical log and verifies both the hash
chain and head checkpoint.

Consequences:

- there is no update, replace, delete, or rejudge command;
- changing a prior question, answer, judgment, rationale, citation, or hash is rejected;
- changing a schema 2 correct answer is rejected because it is part of the session hash;
- deleting any prior session is rejected;
- a later correction must be a new appended session, leaving the earlier decision visible;
- resetting `quiz` preserves history and starts a new context-bound attempt.

Existing schema 1 sessions remain byte-for-byte canonical and valid, but do not gain fabricated
answer keys retroactively. New appends use `quiz_session_schema: 2` and require `correct_answer`;
mixed schema 1 → schema 2 history remains one uninterrupted hash chain.

## Completion Gate

`lint-quiz` and `complete-quiz` require:

1. current read/summary lineage and an exact `quiz-context.json`;
2. canonical `quiz-log.md` and a matching `quiz-head.json` checkpoint;
3. a valid unbroken session hash chain;
4. at least one session from the current attempt;
5. current-attempt coverage of at least one Method anchor, plus one scientific Uxx when
   `scientific_uncertainty_catalog` is non-empty;
6. schema 2 correct answers, legal four-value judgments, and source-resolvable citations for every
   current session;
7. an `output_fingerprint` matching the exact current `quiz-log.md` bytes.

State metadata records current and historical session counts, all four judgment counts, used anchor
ids, cited locators, context/head fingerprints, and the final entry hash.

## Human Validation Boundary

The machine proves input lineage, anchor membership, exact evidence containment, append-only
history, required answer-key presence, and artifact identity. The agent and user remain responsible
for the scientific quality of questions and correct answers, whether they are semantically entailed
by the excerpts, and whether the selected four-value judgment is fair and sufficiently nuanced.
