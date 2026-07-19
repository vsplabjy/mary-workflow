# Mary Paper Expert Q&A Contract v1

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
| `quiz-context.json` | Current input fingerprints, question anchors, judgment definitions, and attempt id |
| `quiz-log.md` | Canonical append-only sequence of Q&A session records |
| `quiz-head.json` | Accepted session count, chain head, and exact log fingerprint |

Do not hand-edit any of these files. A reset starts a new attempt but retains all prior sessions in
`quiz-log.md`; old sessions remain audit history and cannot satisfy the new attempt's coverage gate.

## Question Anchors

`quiz-context.json` exposes two catalogs:

- `Uxx` anchors are derived in order from the mandatory P2 `uncertainties` array. They retain the
  original question, unresolved reason, impact, source locators, and parse-quality dimensions.
- `Mxx` anchors are the direct Method claims accepted from P3.5 `summary-ledger.json`. They retain
  claim text, exact evidence, and source locators.

Run `next-quiz-question` to choose an underused anchor. It proposes an uncertainty question first,
then a method-detail question so the current attempt can cover both families. The agent may improve
wording for the user, but the appended session must retain the selected ids.

Every session selects at least one `Uxx` or `Mxx` id. Unknown ids are rejected. Completion requires
at least one current-attempt uncertainty anchor and at least one current-attempt method anchor; one
question may combine both.

## Interactive Flow

1. Run `prepare-quiz` and read all of `quiz-context.json` plus the relevant `source.md` spans.
2. Run `next-quiz-question` and ask exactly one question in the user's language.
3. Stop and wait for the user's answer. Do not invent an answer on the user's behalf.
4. Assess the answer with one four-value judgment, a calibrated rationale, and exact source
   citations.
5. Submit the six-field payload to `append-quiz-session`; never write `quiz-log.md` directly.
6. Repeat from step 2 while the user wants more questions.
7. Run `lint-quiz`, then `complete-quiz` only when the user ends the session and both anchor families
   are covered.

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
It appends a canonical readable Markdown view containing Question, Answer, Judgment, Rationale,
Anchors, and Source citations. The complete machine record is retained in a collapsed `<details>`
block below that view; callers cannot provide or override audit fields, and the runtime rejects any
divergence between the generated view and record.

## Source Citations

Every judgment requires at least one citation with exactly `source_locator` and `evidence`:

- the locator must belong to at least one selected `Uxx` or `Mxx` anchor;
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
- deleting any prior session is rejected;
- a later correction must be a new appended session, leaving the earlier decision visible;
- resetting `quiz` preserves history and starts a new context-bound attempt.

## Completion Gate

`lint-quiz` and `complete-quiz` require:

1. current read/summary lineage and an exact `quiz-context.json`;
2. canonical `quiz-log.md` and a matching `quiz-head.json` checkpoint;
3. a valid unbroken session hash chain;
4. at least one session from the current attempt;
5. current-attempt coverage of both uncertainty and Method anchors;
6. legal four-value judgments and source-resolvable citations for every current session;
7. an `output_fingerprint` matching the exact current `quiz-log.md` bytes.

State metadata records current and historical session counts, all four judgment counts, used anchor
ids, cited locators, context/head fingerprints, and the final entry hash.

## Human Validation Boundary

The machine proves input lineage, anchor membership, exact evidence containment, append-only
history, and artifact identity. The agent and user remain responsible for the scientific quality of
questions, whether an answer is semantically entailed by the excerpts, and whether the selected
four-value judgment is fair and sufficiently nuanced.
