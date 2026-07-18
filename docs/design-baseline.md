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

`BACKLOG.md` cannot authorize implementation or imply sequence. Backlog candidates move into
`ROADMAP.md` or `TASKS.md` only through explicit triage and governance decisions.
