# Governing design baseline

The seven Markdown documents imported at the repository root are the authoritative RFI-1 design
baseline. `README.md` remains the primary entry point. The other governing inputs are:

- `RFI_MANIFESTO.md`
- `DESIGN_PRINCIPLES.md`
- `ARCHITECTURE.md`
- `ACQUISITION_POC_GUIDANCE.md`
- `ROADMAP.md`
- `TASKS.md`

The machine-readable provenance and integrity record is
[`docs/design-baseline.json`](design-baseline.json). Six documents are byte-for-byte source
copies. `TASKS.md` contains the narrowly scoped TASK-001 reconciliation recorded in that manifest
and in the generated review package's document change audit.

Task tickets in `tasks/` govern implementation scope. If a ticket and the lightweight task
roadmap differ, the detailed ticket is authoritative.
