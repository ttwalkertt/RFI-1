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

`BACKLOG.md` cannot authorize implementation or imply sequence. Backlog candidates move into
`ROADMAP.md` or `TASKS.md` only through explicit triage and governance decisions.
