# Governing design baseline

Eight Markdown documents at the repository root form the authoritative RFI-1 design baseline.
Seven originated with the imported baseline; `BACKLOG.md` is the repository-authored durable
record for unscheduled candidates. `README.md` remains the primary entry point. The other
governing inputs are:

- `RFI_MANIFESTO.md`
- `DESIGN_PRINCIPLES.md`
- `ARCHITECTURE.md`
- `ACQUISITION_POC_GUIDANCE.md`
- `BACKLOG.md`
- `ROADMAP.md`
- `TASKS.md`

The machine-readable provenance and integrity record is
[`docs/design-baseline.json`](design-baseline.json). The manifest distinguishes unchanged imported
documents, reconciled project records, and the repository-authored backlog.

Task tickets in `tasks/` govern implementation scope. If a ticket and the lightweight task
roadmap differ, the detailed ticket is authoritative.

TASK-018 extends the current architectural baseline with repository-owned artifact read contracts,
source-effective ordering, and isolated stored-content inspection. The durable detail is recorded
in [`artifact-query-service-and-browser.md`](artifact-query-service-and-browser.md) and
[`ADR-0014`](decisions/0014-repository-owned-artifact-query-and-isolated-preview.md).

TASK-019 corrects acquisition identity by separating immutable artifact observations from
content-addressed artifacts and run-bound acquisition attempts. Detail and browser contracts now
support exact snapshot-bound observation selection and navigation. See
[`multiple-artifact-observations.md`](multiple-artifact-observations.md) and
[`ADR-0015`](decisions/0015-multiple-immutable-artifact-observations.md).

TASK-020 selects the storage direction for a later migration: SQLite authority for structured
runtime records, content-addressed filesystem authority for immutable bytes, and unchanged public
repository/query contracts. No migration is implemented. See
[`storage_architecture_design_draft.md`](storage_architecture_design_draft.md) and
[`ADR-0016`](decisions/0016-hybrid-sqlite-structured-state.md).

TASK-021 implements that direction for fresh repositories without migrating disposable POC state.
The database owns structured application state, the content-addressed filesystem owns artifact
bytes, and verified backup/restore covers both authorities. See
[`sqlite-structured-state-repository.md`](sqlite-structured-state-repository.md) and
[`ADR-0017`](decisions/0017-fresh-sqlite-structured-state-foundation.md).

TASK-022 adds artifact-specific Form 10-Q, Form 8-K, Form 20-F, and Form 6-K retrieval while
preserving Form 10-K and the SQLite-independent acquisition boundary. See
[`additional-sec-numbered-form-adapters.md`](additional-sec-numbered-form-adapters.md) and
[`ADR-0018`](decisions/0018-artifact-specific-sec-numbered-form-adapters.md).

TASK-023 adds bounded, connected development-mailing-list evidence and a sibling browser
projection. See [`linux-kernel-mailing-list-intelligence-stream.md`](linux-kernel-mailing-list-intelligence-stream.md)
and [`ADR-0019`](decisions/0019-bounded-mailing-list-discussion-projection.md).

TASK-025 adds revisioned external and derived artifact streams, validated DAG topology, typed
schema capabilities, durable membership lineage, offline rebuild, and shared operator surfaces.
See [`revisioned-artifact-streams.md`](revisioned-artifact-streams.md) and
[`ADR-0020`](decisions/0020-revisioned-artifact-stream-dag.md).

TASK-026 makes that established subsystem operable through a progressive browser editor and one
strict, versioned canonical YAML contract shared by browser, CLI, preview, revision persistence,
and execution. See [`stream-configuration-and-yaml.md`](stream-configuration-and-yaml.md) and
[`ADR-0021`](decisions/0021-canonical-stream-definition-yaml.md).

`BACKLOG.md` cannot authorize implementation or imply sequence. Backlog candidates move into
`ROADMAP.md` or `TASKS.md` only through explicit triage and governance decisions.
