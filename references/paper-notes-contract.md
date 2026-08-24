# Mary Paper Notes Contract v1

`paper-notes.md` is the only valid output of the `read` stage. It is a Markdown container with one machine-validated JSON ledger. Do not replace required fields with prose headings or free-form notes.

## Preparation Artifacts

`prepare-read` creates these files in `.mary-research/papers/<paper-id>/`:

| File | Purpose |
| --- | --- |
| `source.html` or `source.pdf` | Immutable bytes selected for this read attempt |
| `source.md` | Locatable normalized text used by the agent |
| `parse-quality.json` | Deterministic five-dimensional parse assessment |
| `read-context.json` | Exact identity and quality fields to copy into the ledger |

The source fingerprint hashes the selected raw HTML or PDF bytes. `read-context.json` is derived from the other three artifacts and must not be edited.

## Ledger Shape

Start `paper-notes.md` with the schema marker and one fenced JSON object:

````markdown
<!-- mary-paper-notes:v1 -->
```json
{
  "paper_notes_schema": 1,
  "paper_id": "arxiv-2401.12345v2",
  "source": {
    "locator": "https://arxiv.org/abs/2401.12345v2",
    "fingerprint": "<source-sha256>",
    "format": "html",
    "artifact": "source.md"
  },
  "bibliography": {
    "title": "Paper title",
    "authors": ["First Author"],
    "year": "2024",
    "venue": "arXiv"
  },
  "research": {
    "background": {"text": "...", "locators": ["html#S1"]},
    "problem": {"text": "...", "locators": ["html#S1"]},
    "contributions": [
      {"text": "...", "locators": ["html#S1"]}
    ],
    "method": {"text": "...", "locators": ["html#S2"]},
    "experiments": {"text": "...", "locators": ["html#S3"]},
    "limitations": {"text": "...", "locators": ["html#S4"]},
    "conclusions": {"text": "...", "locators": ["html#S5"]}
  },
  "section_ledger": [
    {
      "section": "1 Introduction",
      "locators": ["html#S1"],
      "findings": ["..."]
    }
  ],
  "parse_quality": {
    "report": "parse-quality.json",
    "report_fingerprint": "<parse-quality-sha256>",
    "gate": "pass",
    "dimensions": {
      "text": "pass",
      "structure": "pass",
      "equations": "pass",
      "figures": "degraded",
      "tables": "not_applicable"
    }
  },
  "uncertainties": [
    {
      "question": "What visual detail is unavailable in the normalized figure text?",
      "why_unresolved": "The selected parser retained the caption but not all visual encodings.",
      "impact": "Claims based on the figure geometry require checking the original source.",
      "locators": ["html#S3.F1"],
      "quality_dimensions": ["figures"]
    }
  ]
}
```
````

Additional Markdown may follow the ledger, but downstream stages treat the JSON object as authority.

## Required Research Fields

Every research claim contains exactly `text` and a non-empty `locators` array. The required claims are:

- `background`
- `problem`
- one or more `contributions`
- `method`
- `experiments`
- `limitations`
- `conclusions`

For a theoretical paper without empirical experiments, `experiments.text` must describe the actual evaluation or proof strategy instead of being empty. Unknown bibliography facts must be stated plainly and added to `uncertainties`.

## Locators

- HTML ledger locators use `html#<anchor>` from `source.md` comments.
- PDF ledger locators use `pdf:p<N>` page markers from `source.md`.
- Every claim, section entry, and uncertainty must have at least one locator.
- Do not invent an anchor or page that is absent from `source.md`.

## Five-Dimensional Parse Quality

The exact dimensions are:

| Dimension | What it measures |
| --- | --- |
| `text` | readable body-text coverage and decoding integrity |
| `structure` | title, abstract, sections, and page/heading recovery |
| `equations` | retention of equation text or semantics |
| `figures` | figure discovery, captions, and visual availability |
| `tables` | table discovery, captions, and alignment retention |

Each dimension has one status in `parse-quality.json`:

- `pass`: usable without a parse-specific warning;
- `degraded`: usable with a mandatory matching uncertainty;
- `failed`: unreliable and blocks read completion by default;
- `not_applicable`: no evidence that the paper uses the dimension.

The ledger's `parse_quality` object must exactly copy `read-context.json`. Any `degraded` or `failed` dimension must appear in at least one uncertainty's `quality_dimensions`.

## Block And Override

Any `failed` dimension sets the report gate to `blocked`. When blocked:

1. Show the five-dimensional report and blocking evidence to the user.
2. Stop without writing or completing `paper-notes.md` unless the user explicitly accepts the risk.
3. Prefer retrying with a better source before requesting an override.
4. Only after explicit user confirmation, run `complete-read --override-quality --override-reason <reason>`.

The CLI requires a non-trivial reason, records `confirmed_by: user`, writes `quality-override-<attempt>.json`, stores its fingerprint in paper state, and logs the decision. An agent must never infer override consent from silence or from the original read request.

## Rejection Rules

`complete-read` rejects the artifact when any of these is true:

- schema marker, JSON ledger, or exact top-level fields are invalid;
- paper id, source locator, source format, or source fingerprint differs from current state;
- a required bibliography, research, section, or uncertainty field is empty;
- `uncertainties` is empty;
- a locator has the wrong HTML/PDF form;
- quality report path, fingerprint, gate, dimension set, or statuses differ from `parse-quality.json`;
- a degraded or failed dimension has no uncertainty;
- the quality gate is blocked without explicit override;
- the declared output fingerprint differs from the actual `paper-notes.md` bytes.

Rejected completion uses the normal paper rejection path: audit count increments, the reason is appended to `log.md`, and the read stage remains `in_progress`.
