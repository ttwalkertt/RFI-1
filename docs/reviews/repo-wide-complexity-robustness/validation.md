# Validation results

## Focused tests

The combined focused command ran 121 tests. 118 passed in the initial restricted environment and
three local HTTP tests errored only because loopback `bind(2)` was denied by the sandbox. The exact
three tests were rerun with ephemeral loopback binding permitted: **3 tests passed**. No focused
repository assertion failed.

Covered areas:

- SQLite authority, rollback, integrity, backup/restore, and stale cursors;
- configuration export/import/reset;
- persistent discovery anchors and migrations;
- pull planning, progress, REST/CLI/UI integration, outcome aggregation;
- mailing-list queue progress, cancellation, restart, and durable history;
- StockAnalysis provider parsing, bounded retry, identity, replay, and selection;
- explicit provider seed injection and persisted provider learning;
- commit-aware review-package generation and verification.

## Review probes

- Profile revision anchor survival: **FAIL (confirmed defect)** — r1 anchor count 1; derived r2
  source anchor count 0.
- Hybrid backup overlap: **FAIL (confirmed defect)** — backup reported `PASS`; restore rejected the
  resulting archive as containing an orphan relative to the archived database.
- Interrupted pull reopen: **LIMITATION confirmed** — persisted status remains `running`, matching
  existing documentation and showing no reconciliation.

These failures are intended review evidence, not failures of the probe tooling.

## Full validation

`make validate`: **PASS** (exit status 0). This exercised the complete unit-test discovery plus the
repository's proof, lint, format, type-check, import, documentation, baseline, and build gates. It
was run with ephemeral loopback binding permitted because the suite contains local HTTP tests.

## Static/package checks

- Metrics and probes were regenerated from the reviewed tree: **PASS**.
- Both generated JSON artifacts parse with `python -m json.tool`: **PASS**.
- `git diff --check`: **PASS**.
- Review scripts passed the repository lint, format, and type-check gates as part of
  `make validate`: **PASS**.
- Final scope inspection found only the review document, evidence package, and two read-only review
  scripts: **PASS**.

The post-commit status and pushed commit identity are reported in the task handoff rather than
embedded here, avoiding a self-referential artifact hash.
