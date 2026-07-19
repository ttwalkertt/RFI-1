# Pull Workflow

TASK-015 introduces RFI's first durable business workflow. `PullWorkflow` is the sole acquisition
orchestration path for the CLI, local REST API, and the **Pull Sources** operator-console tab.
Future schedulers and automation should initiate this workflow rather than call adapters or the
acquisition engine directly.

## Business flow and durable state

Every run records the same ordered stages:

1. receive request;
2. resolve firms;
3. snapshot source-profile revisions;
4. expand every enabled artifact;
5. determine attemptability;
6. execute retrieval;
7. ingest successful artifacts;
8. record results; and
9. summarize execution.

The durable run record lives in the selected application's SQLite `pull_runs` table. It
preserves the request, exact profile snapshot, inspectable plan, ordered stage events, per-candidate
diagnostics, per-artifact results, per-firm aggregation, and run summary. Progress/status reads do
not depend on a live HTTP request or browser state.

The snapshot is taken before artifact planning and execution. A later source-profile publication
therefore cannot alter an already-planned run. Explicitly selected firms without a saved profile
use the documented canonical defaults and receive configuration-problem results for enabled items
without candidates. `--all-configured` selects only firms with a saved profile revision.

## Planning and attemptability

The source profile remains authoritative. Every enabled artifact participates. Retrieval
candidates retain profile priority order, and the workflow attempts runnable candidates until one
produces success, duplicate, or no change. A failed candidate does not prevent a later candidate,
artifact, or firm from executing.

Executable adapter coverage is selected through explicit artifact-semantic capability
declarations:

- any canonical artifact configured with `direct_url` is runnable through `DirectUrlAdapter`;
- canonical `sec_10k` configured with `identifier` is runnable through the artifact-specific
  `SecForm10KAdapter`; and
- remaining feed, identifier, listing-page, and discovery combinations remain explicit stubs.

An enabled item without a candidate is a `configuration_problem`. An item whose candidates all
use unsupported modes is `skipped` with the durable diagnostic:

> No adapter available for this retrieval mode.

This is intentional. The canonical 48-artifact catalog can evolve adapter coverage incrementally
without expanding TASK-015 into dozens of retrieval implementations or fabricating support.

## Acquisition and repository ingress

For each runnable candidate, the workflow first selects exactly one declared retrieval capability,
then translates the snapshotted firm, artifact, profile revision, candidate, and adapter identity
into a governed acquisition `SourceProfile`. It registers that source in the existing
`AcquisitionRepository`, projects only the already-selected source adapter into the
mechanism-keyed `AdapterRegistry`, and invokes the existing `AcquisitionEngine`. Retrieval
capability uniqueness is determined by canonical artifact identity plus candidate mode, not by the
downstream acquisition mechanism. Distinct artifact-semantic adapters may therefore share a
mechanism without creating a multiple-match policy; overlapping artifact/mode claims still fail
closed during registry construction.

Adapters return exact `RetrievalResult` bytes. `AcquisitionEngine` calls the existing public
repository ingress, which derives content-addressed artifact identity, stores immutable whole
bytes outside SQLite, and transactionally publishes metadata, attempt/observation history,
document projection, and source checkpoints. The workflow does not know or use the repository's
private artifact layout and creates no alternate evidence store.

The repository receipt distinguishes an idempotent retry within one engine run from a newly
observed attempt whose exact artifact bytes already exist. A distinct successful pull appends an
immutable observation even when content is unchanged. This permits the workflow to report
`no_change` and `duplicate` honestly while retaining the existing immutable artifact identity,
stored bytes, and successful retrieval ledger contract.

## Aggregation semantics

Artifact outcomes are `success`, `duplicate`, `no_change`, `skipped`,
`configuration_problem`, and `retrieval_failure`. Configuration and retrieval failures are the
failure-bearing outcomes. A firm or run is:

- `completed` when it has no failure-bearing artifact or all selected firms completed;
- `failed` when every artifact (or every selected firm) failed; and
- `partial` when successful/accepted work and failures coexist.

Unsupported-mode skips are explicit accepted results, not silent failures. A firm with no enabled
artifacts completes with zero artifact attempts.

In the Pull Sources browser, artifact-level `configuration_problem` outcomes that carry both the
firm and canonical artifact identity are repair links. The ordinary same-tab link targets
`/source-profiles?firm_id=...&artifact_id=...`; other statuses remain presentation-only. This keeps
pull results read-only while routing configuration work to the existing source-profile authority
and retaining normal browser history behavior. A completed run is recorded as
`/pull-sources?run_id=...`; loading that history URL rehydrates the durable results, so Back from
the editor returns to the result that initiated the repair.

## Interfaces

### CLI

```sh
rfi pull --firm seagate
rfi pull --firm seagate --firm ibm
rfi pull --all-configured
```

Use `--state PATH` to select application state. The CLI prints the complete JSON-compatible typed
result. Completed runs exit zero; partial or failed business runs exit one; invalid application or
request state exits two.

### REST API

- `GET /api/pulls/firms` lists configured firms and enabled/runnable/incomplete counts.
- `POST /api/pulls` accepts `{"firm_ids":["seagate"]}` or `{"all_configured":true}` and returns
  `202 Accepted` with a run ID and status/result URLs.
- `GET /api/pulls/{run_id}` reads durable progress.
- `GET /api/pulls/{run_id}/results` reads the complete durable plan, snapshots, and results.

The local HTTP adapter starts the workflow in a background thread so the browser can poll durable
stage progress. It contains no retrieval planning or repository calls.

### Operator console

The existing console has one top-level **Pull Sources** tab at `/pull-sources`. It lists only firms
with saved profiles, supports one/many/all selection, displays enabled/runnable/incomplete counts,
shows registered adapter capabilities, launches the REST workflow initiator, polls status, and
renders adapter identity, filing provenance, diagnostics, and terminal results. It is not a second
application.

## Verification and limitations

Run:

```sh
make task015-test
make task015-proof
make validate
make review-package
```

The proof demonstrates ordered stages, multi-firm execution, revision snapshots, independent
artifact and firm failure, all artifact outcomes, completed/partial/failed runs, exact whole-byte
ingress, repository integrity, and the unsupported-mode stub.

The current workflow is intentionally single-process and serializes runs within one composed
workflow instance. The local REST background runner is not a durable external job queue; an
abrupt process exit can leave a durable `running` record for operator diagnosis. There is no
scheduler, polling, added retry policy, concurrency manager, cross-process writer lock, OCR,
chunking, embeddings, semantic search, report generation, or automatic refresh.

## Architectural Status Summary

- Pull Workflow business capability: **Complete** for request, planning, execution, durable
  results, aggregation, and shared initiation.
- Interface integration: **Complete** for CLI, local REST API, and the existing operator console.
- Direct URL retrieval: **Usable with Limitations** for exact whole-artifact HTTP(S) retrieval.
- Identifier-based canonical Form 10-K retrieval: **Complete** for latest unamended primary filing.
- Remaining retrieval capability combinations: **Provisional stubs** with explicit
  operator-visible skip results.
- Acquisition engine and repository ingress: **Complete and reused**; no parallel evidence path
  was introduced.
- Operational execution: **Usable with Limitations** as a local single-process workflow, not a
  distributed or crash-recovering job system.
- Next architectural milestone: expand adapter coverage from observed source behavior, then allow
  future schedulers and refresh initiators to invoke this unchanged business workflow.
