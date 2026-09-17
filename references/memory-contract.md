# Project memory and coverage

This contract is independent of the model, provider, context window, and host.
The project works without host memory, subagents, hooks, or a native task list.
Use available worker capabilities to reduce reading latency, without making a
worker's identity or model part of the project record or completion criteria.

## Authority and working context

- The user's current instructions and confirmed decisions define scope and authorization.
- `state.yaml` defines the phase, active task, accepted plan, and brief revision.
- `project-brief.md` is the rendered project understanding, derived from state.
- Source files, artifacts, and actual validation output determine implementation facts.
- Conversation context and host memory help locate and reuse relevant information.
  They do not silently override project decisions or current implementation evidence.

Keep useful working context at a milestone boundary. Check the current state,
task, plan revision, deliverables, and outstanding validation. Reread affected
material after an interruption, compression, plan change, or external edit; do
not declare previous working memory discarded. If the brief conflicts with
current source, record the discrepancy and correct the brief from evidence.

Host memory is optional and external to this contract. Running the workflow,
refreshing a brief, or finishing a cycle does not authorize a host-memory write.
Project facts, preferences, and decisions remain in project records unless the
user separately requests a host-memory update.

## Inventory and module coverage

The runtime generates the inventory and file fingerprints using the configured
exclusions. Agents do not replace that inventory with their own file list.
Small projects can be read directly; medium projects benefit from module
summaries; large independent modules can be assigned to explorers. Choose using
text volume, coupling, and task scope, not a fixed file-count threshold.

Replace a hand-authored record for every file with this `coverage` object:

```json
{
  "modules": [
    {
      "id": "core",
      "summary": "Parses source records and exposes the normalized data contract.",
      "files": ["src/core.py"],
      "read_files": ["src/core.py"],
      "boundary_files": [],
      "depends_on": []
    },
    {
      "id": "api",
      "summary": "Serves normalized records using the core contract.",
      "files": ["src/api.py"],
      "read_files": ["src/api.py", "src/core.py"],
      "boundary_files": ["src/core.py"],
      "depends_on": ["core"]
    }
  ]
}
```

Each inventory path has exactly one owning module through `files`. Shared
cross-module references use `boundary_files`; they do not create second owners.
Paths are canonical project-relative paths. `read_files` lists owned or boundary
files whose contents have been inspected. Ownership, boundary references, read
records, and dependency references are checked against the actual inventory and
module IDs. Module IDs remain stable across revisions where the responsibility
remains the same.

`normalize_coverage(value, inventory)` in `scripts/mw_brief.py` computes
`unread_files`, `inventory_count`, `covered_count`, and `complete`. Agent-supplied
values for these fields are ignored. Missing inventory ownership, duplicate
owners, unknown paths, and invalid dependencies fail validation. A declared
boundary file must also be read by the module that references it. Incomplete
coverage can be retained as exploration progress, but cannot complete a brief.

This checks coverage records; it does not prove comprehension. Explorers return
summaries and evidence to task staging areas. The main agent checks cross-module
relationships and integrates the accepted result through the runtime. It remains
responsible for conflicting summaries, missing coverage, and unexplained claims.

## Incremental refresh

An initial submission has this complete outer shape. Replace example content with
inspected facts. An empty inventory uses empty module lists. `records`,
`uncertainties`, and `validation` may be empty when there is no corresponding claim.

```json
{
  "action": "submit_brief",
  "data": {
    "mode": "initial",
    "positioning": {
      "purpose": "Parse user-provided records.",
      "audience": "Application callers.",
      "problem": "Reject malformed records consistently.",
      "differentiators": "Explicit local validation and errors."
    },
    "architecture": {
      "modules": [{"name": "parser", "responsibility": "Validate records", "files": ["parser.py"]}],
      "dependency_graph": [],
      "data_flow": ["Text input -> validation -> parsed record"],
      "state_management": ["No persistent application state"]
    },
    "coverage": {
      "modules": [{"id": "parser", "summary": "Reviewed parser input and error paths.", "files": ["parser.py"], "read_files": ["parser.py"], "boundary_files": [], "depends_on": []}]
    },
    "records": [],
    "uncertainties": [],
    "validation": []
  }
}
```

Validation entries require `kind`, `command`, `status` (`passed`, `failed`, or
`skipped`), `summary`, and `duration`. An uncertainty entry requires `topic`,
`status` (`inferred` or `unresolved`), and `detail`. A correction uses
`mode: correction` with the same full shape and preserves existing record history.
Disclosed plan assumptions belong in frozen clarifications even when no extra
interview question was necessary.

A cycle refresh instead uses
`{"action":"submit_brief","data":{"mode":"cycle_refresh","update":{...}}}`.
The `update` object contains the delta described below. At this external boundary,
`reviewed_changed_files` exactly matches the state's prefixed machine entries,
such as `modified:src/core.py`, `added:src/new.py`, or `deleted:src/old.py`.
The runtime checks these entries before converting them to plain paths for the
internal merge helper. The example below shows that helper's plain-path input.

Keep fingerprints and the machine-generated changed-file list, including deleted
paths. Refresh a brief using its current version; do not rewrite all unchanged
sections by hand. `merge_brief_update(existing, update, inventory, changed_files)`
returns a new brief without mutating its inputs or writing state.

The internal `existing` shape is:

```text
{version, coverage, positioning, architecture, uncertainties, validation, records}
```

The delta shape is:

```json
{
  "base_version": 3,
  "updated_modules": [
    {
      "id": "core",
      "summary": "Parses source records with explicit schema errors.",
      "files": ["src/core.py"],
      "read_files": ["src/core.py"],
      "boundary_files": [],
      "depends_on": [],
      "reread_files": ["src/core.py"],
      "review_evidence": "Inspected the schema-error change and its callers."
    },
    {
      "id": "api",
      "summary": "Serves normalized records using the core contract.",
      "files": ["src/api.py"],
      "read_files": ["src/api.py", "src/core.py"],
      "boundary_files": ["src/core.py"],
      "depends_on": ["core"],
      "reread_files": ["src/core.py"],
      "reviewed_dependencies": ["core"],
      "review_evidence": "Checked the error handler against the new core behavior."
    }
  ],
  "deleted_modules": [],
  "retained_modules": [],
  "reviewed_changed_files": ["src/core.py"]
}
```

An unchanged module is explicitly retained as
`{"id":"docs","evidence":"Fingerprint unchanged; no affected dependencies."}`.
Every old module must appear in exactly one of updated, deleted, or retained.
Unknown IDs in deletion or retention fail. Updated entries are complete module
records; unchanged brief sections are carried forward automatically.

Changed owned files, changed boundary files, and transitive module dependencies
mark a module affected. Deleting or reassigning modules also triggers dependent
review. An affected module cannot be retained merely because its own file hash
did not change. Supply its updated record, `review_evidence`, `reread_files` for
extant changed owned/boundary files, and `reviewed_dependencies` for affected old
or current dependencies. Removing a dependency still requires recording that it
was reviewed. The aggregate `reviewed_changed_files` must exactly account for
machine changes, including deletions; an empty agent claim is insufficient.

`read_files` preserves cumulative reading coverage; `reread_files` identifies the
current refresh's actual rereads. A targeted dependency check need not repeat the
entire original module read. The runtime retains refresh evidence with the base
revision, retained-module reasons, deleted modules, and affected module IDs.

Optional `positioning`, `architecture`, `uncertainties`, and `validation` fields
replace only their respective section. The main runtime validates their existing
schemas and checks architecture paths against the new inventory before accepting
the result. Unknowns and factual limits are preserved when their section is absent;
do not remove an uncertainty just because work moved into a new cycle.

## Durable project records

`records` contains facts, preferences, and decisions. Each record requires `kind`
(`fact`, `preference`, or `decision`) and `text`; `id` and `source` are optional.
Use stable IDs for records that may need superseding. Record provenance with a
source when available, and distinguish confirmed decisions from unresolved ideas.
Unresolved ideas belong in the uncertainty section until confirmed.

Incremental updates append `record_updates`; they do not replace record history:

```json
{
  "record_updates": [
    {
      "id": "decision-8",
      "kind": "decision",
      "text": "Use the local cache with explicit revision checks.",
      "source": "User-confirmed project decision",
      "supersedes": ["decision-3"]
    }
  ]
}
```

The earlier record remains available. A superseding record needs an ID and can
only reference existing earlier IDs; duplicate IDs, unknown references, and
cycles are rejected. The absence of host memory never prevents using these
project records. No record authorizes actions beyond the user's applicable scope.

## Legacy migration

`migrate_legacy_ledger(ledger, inventory, architecture=None)` groups paths by
directory and reuses relevant historical architecture descriptions. It includes
new inventory paths, records how many had historical ledger entries, and marks
all reads pending. Migration does not claim a fresh read or erase the original
ledger, uncertainty list, brief history, or validation history. The main runtime
backs up legacy state and selects the legitimate refresh path; after explicit
verification, normal module coverage becomes the maintained representation.
An old `(empty repository)` sentinel is discarded; an empty repository has an
empty machine inventory and no fictitious source file to read.

The helpers raise `BriefError` for invalid input. The state runtime converts this
to its normal action error, keeps state unchanged on rejection, and owns atomic
persistence of the merged result and its generated brief.
