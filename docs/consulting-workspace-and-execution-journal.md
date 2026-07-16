# Consulting workspace and execution journal

TASK-008 adds the first durable operator-product layer. An investigation is one consulting problem;
its current view is a projection of append-only events. Executions, notes, exports, and status
transitions never overwrite prior history.

## Boundary and authority model

```text
Operator / JSON console
          |
          v
WorkspaceService -> IntelligenceExecutor (public TASK-007 port)
          |                    |
          |                    v
          |          ExecutionRecord (public contract)
          v
WorkspaceRepository
  - hash-chained journal
  - non-authoritative reference snapshots
  - operator annotations
  - metrics and export references
  - backup manifest
```

`rfi.workspace` imports no acquisition, source-object, knowledge, or retrieval repository. It never
opens their storage. The durable execution projection preserves identities and semantics from
public intelligence records but has `reference-snapshot-no-source-context` retention. It is audit
history, not a new authority or replay cache.

The architecture preserves six distinct classes:

- immutable source evidence remains in acquisition artifacts;
- derived knowledge remains in versioned knowledge generations;
- retrieval state remains disposable and rebuildable;
- intelligence results remain non-authoritative TASK-007 results;
- operator annotations are journal events labeled `operator-annotation`;
- transient diagnostics are redacted JSON written only to an explicit stream.

## Filesystem model and integrity

Each workspace contains:

```text
workspace.json
journal/00000000000000000001.json
journal/00000000000000000002.json
exports/export-....md
quarantine/                       # only after partial-write recovery
```

An event includes sequence, unique identity, UTC timestamp, type, investigation identity, payload,
previous-event hash, and its own canonical SHA-256 digest. Publication uses a same-directory
temporary file and atomic replacement. Verification checks metadata schema, sequence continuity,
the full hash chain, event digests, partial writes, and every journal-referenced export digest.
Opening or appending fails closed when verification fails.

An execution start is durable before intelligence invocation. A terminal completion, failure, or
interruption is appended later. An unmatched start is reported by `verify` as an open execution;
it is recoverable by appending an interrupted terminal event. A `.partial` file is never treated as
committed history. Recovery moves it to quarantine and leaves the chain unchanged.

## Execution snapshots and comparison

The default indefinite journal snapshot retains:

- original question and redacted runtime configuration;
- structured plan and retrieval queries;
- retrieval trace, index generation, package, and authority-fingerprint identities;
- source-object, derived-object, document, artifact, byte-span, and digest references;
- intelligence response, claims, claim mappings, uncertainty, contradictions, gaps, and failures;
- stage timings when supplied, total duration, evidence volume, retrieval and iteration counts;
- model calls, token usage, currency, and estimated cost when a provider supplies them.

It does not retain exact context text, bounded model input, raw model output, credentials, or
provider secrets. Unavailable timing or usage values remain `null`; the workspace never estimates
tokens or cost without provider telemetry.

Comparison is semantic and field-specific. It reports question, configuration, plan, retrieval,
evidence, reasoning, conclusion, and status changes independently plus numeric metric deltas.
Implementation wording can therefore change while evidence remains identical, or evidence can
change without being hidden by a similar final answer.

## Operator workflow

The console emits stable JSON and uses the same workspace contracts available to other front ends:

```sh
.venv/bin/python scripts/task008_workspace.py init --workspace STATE
.venv/bin/python scripts/task008_workspace.py create --workspace STATE \
  --title "Filing comparison" --purpose "Prepare an operator call"
.venv/bin/python scripts/task008_workspace.py list --workspace STATE
.venv/bin/python scripts/task008_workspace.py show --workspace STATE \
  --investigation INVESTIGATION_ID
.venv/bin/python scripts/task008_workspace.py note --workspace STATE \
  --investigation INVESTIGATION_ID --kind interpretation --text "Bounded conclusion"
.venv/bin/python scripts/task008_workspace.py compare --workspace STATE \
  --first EXECUTION_ID --second EXECUTION_ID
.venv/bin/python scripts/task008_workspace.py export --workspace STATE \
  --investigation INVESTIGATION_ID
.venv/bin/python scripts/task008_workspace.py verify --workspace STATE
.venv/bin/python scripts/task008_workspace.py backup --workspace STATE \
  --destination workspace.zip
.venv/bin/python scripts/task008_workspace.py restore --backup workspace.zip \
  --destination RESTORED_STATE
```

Execution is exposed through `WorkspaceService` because construction of a real executor is a
composition-root decision. The workspace starts the journal entry, invokes only the public
`IntelligenceExecutor`, captures metrics, and appends the terminal record. The fixture proof is:

```sh
make task008-proof
```

## Export, backup, restore, and retention

Markdown export contains conclusions, uncertainty, evidence gaps, package references, operator
notes, and a JSON appendix with provenance and claim mappings. Its digest and relative path become
an append-only event.

Backup is allowed only outside the workspace. A ZIP contains all durable workspace files plus a
manifest with relative path, byte size, and SHA-256 for every file. Backup publication occurs only
after readback verification. Restore rejects an invalid archive or existing destination, extracts
only safe relative paths into staging, verifies the restored workspace, and atomically publishes
it.

Committed journal/reference snapshots are retained indefinitely in TASK-008. Exports and backups
are operator-managed and remain integrity checked. Quarantined partial files are diagnostic
evidence and may be removed under a future explicit retention policy. Transient diagnostics are
not placed in the workspace, and credential-like fields are redacted before emission.

## Failure semantics

- Planner, model, unsupported-claim, retrieval, missing-evidence, and stale-index conditions from
  TASK-007 remain in the frozen result and trace.
- Executor exceptions append `execution-failed`; keyboard interruption appends
  `execution-interrupted` before propagating.
- Missing terminal events remain visible as open executions.
- Corrupt metadata, journal events, chains, or exports fail open/append/backup.
- Partial journal files fail integrity until quarantined; committed events remain unchanged.
- Invalid or oversized annotations append nothing.
- Backup inside the workspace, archive corruption, unsafe restore paths, and overwrite of an
  existing restore target fail explicitly.
- Missing upstream evidence is never replaced by a journal copy; the historical reference remains
  inspectable and new execution fails or returns incomplete through governed contracts.

## Limitations

The workspace is single-writer and local. Replay and file enumeration are adequate for the POC,
not proven at large scale. Hash chaining detects accidental or partial modification but is not a
signed audit ledger. Exports are functional Markdown, not polished client deliverables. There is no
authentication, collaboration, scheduling, external integration, GUI, incremental backup,
automatic retention compaction, or upstream availability monitor. Model and retrieval quality
remain those of TASK-006/007 and are not improved by workspace persistence.

## Architectural Status Summary

- **Repository foundation — Complete.** Task governance, validation, baseline checks, and review
  packaging remain active.
- **Acquisition — Complete contracts; usable with limitations.** Deterministic provider execution
  and the accepted native EDGAR corpus exist; scheduling and broad provider operations do not.
- **Immutable evidence — Complete.** Exact artifact bytes and identities remain the only source
  authority; the workspace stores references only.
- **Source objects — Usable with Limitations.** Stable SEC SGML structures and exact spans exist;
  semantic body sections and broader formats remain absent.
- **Derived knowledge — Usable with Limitations.** Versioning, correction, uncertainty, and
  provenance are established over a narrow filing ontology.
- **Governed retrieval — Complete contracts; provisional quality.** Typed retrieval, evidence
  packages, traceability, rebuild, and fail-closed state exist; semantic ranking quality and scale
  remain unproven.
- **Model-guided intelligence — Complete contracts; usable with limitations.** Bounded planning,
  grounded claims, explicit inference, uncertainty, and failure semantics exist; frontier-model
  and semantic-entailment quality remain provisional.
- **Consulting workspace — Complete for the POC.** Investigations can be created, reopened,
  inspected, annotated, rerun, compared, and exported through stable Python and JSON-console
  contracts. Presentation polish and multi-user operation remain deferred.
- **Execution journal and logging — Complete for the POC.** Start-before-execute history,
  hash-chained append-only records, reference retention, failure visibility, redacted transient
  diagnostics, and metrics are implemented. Concurrency and signed audit guarantees are absent.
- **Operational hardening — Usable with Limitations.** Integrity verification, partial-write
  recovery, bounded export, self-verifying backup, staged restore, failure proofs, and full
  repository validation are established. Cloud durability, scheduling, monitoring, and
  performance-at-scale are not.

TASK-008 introduces the sixth layer: durable operator workflow state. It is not a sixth repository
authority. The next architectural milestone should evaluate POC fitness with live operator work,
frontier-model and retrieval quality, broader source semantics, and deployment/scale requirements
before selecting a production product architecture.
