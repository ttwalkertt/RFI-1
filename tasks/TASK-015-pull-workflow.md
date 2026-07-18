# TASK-015 --- Pull Workflow

## Status

Complete

## Objective

Implement RFI's first business workflow: **Pull Workflow**.

The Pull Workflow refreshes one or more firms by attempting retrieval of
every enabled artifact configured in the firm's current source profile.

The Pull Workflow becomes the single acquisition entry point for the
GUI, CLI, and REST API. Future schedulers and automation shall invoke
this same workflow. No parallel retrieval orchestration shall be
introduced.

## Inputs

The workflow accepts one or more firm identifiers.

For each selected firm, the workflow resolves:

-   current source profile
-   current source-profile revision
-   enabled artifacts
-   retrieval configuration

The workflow snapshots the selected profile revision before execution
begins.

## Workflow

The Pull Workflow shall be implemented as one centrally located business
process.

Initial conceptual stages:

1.  Receive request
2.  Resolve firms
3.  Snapshot source-profile revisions
4.  Expand enabled artifacts
5.  Determine attemptability
6.  Execute retrieval
7.  Ingest successful artifacts through the existing repository ingress
8.  Record results
9.  Produce workflow summary

Codex may refine stage boundaries provided the conceptual flow remains
obvious.

## Attemptability

Enabled artifacts participate in the workflow.

An artifact may become:

-   Attempted
-   Skipped because configuration is incomplete
-   Failed before retrieval
-   Failed during retrieval
-   No change
-   Duplicate
-   Successful

Configuration is intentionally permissive. The workflow should attempt
retrieval whenever reasonable rather than requiring prior external
validation.

## Artifact Execution

Each artifact executes independently.

Failure of one artifact shall not terminate:

-   remaining artifacts for the same firm
-   remaining firms

## Storage

Successful retrievals shall use the existing acquisition and
repository-ingress architecture.

The workflow shall not introduce a parallel storage path.

Whole artifacts remain the authoritative stored representation.

## Interfaces

The GUI, CLI, and REST API become thin workflow initiators.

Business logic belongs to the Pull Workflow.

### CLI

-   `rfi pull --firm seagate`
-   `rfi pull --firm seagate --firm ibm`
-   `rfi pull --all-configured`

### REST API

Provide endpoints for:

-   initiating a pull
-   observing status
-   retrieving results

The API shall invoke the workflow.

### GUI

Add a new top-level **Pull Sources** tab.

The current Admin application evolves into the primary operator console.

The operator selects one, many, or all configured firms.

The workflow attempts every enabled artifact for every selected firm.

## Results

Run:

-   Completed
-   Partial
-   Failed

Firm:

-   Completed
-   Partial
-   Failed

Artifact:

-   Success
-   Duplicate
-   No change
-   Skipped
-   Configuration problem
-   Retrieval failure

Diagnostics shall be preserved.

## Logging

Every artifact receives a durable execution record.

Successful, skipped, duplicate, unchanged, and failed outcomes shall all
be recorded.

No silent failures.

## Architectural Organization

This task intentionally introduces RFI's first business workflow.

Codex shall organize related workflow concepts together where practical,
including:

-   workflow definition
-   planning
-   execution
-   result aggregation
-   contracts

The exact package structure is left to Codex.

The intent is conceptual proximity rather than a prescribed directory
layout.

Future maintenance should require understanding one coherent workflow
rather than tracing behavior across unrelated packages.

## Future Compatibility

This workflow becomes the future entry point for:

-   scheduled refresh
-   automatic refresh
-   refresh-before-analysis
-   refresh-before-report
-   API-triggered refresh

Those capabilities are outside the scope of this task.

## Implementation Resolution

Implemented one concrete, strongly typed `PullWorkflow` business capability under `rfi.pull`.
The package keeps workflow contracts, planning, execution/aggregation, and durable run persistence
conceptually adjacent without introducing a generic workflow engine.

Every run durably records the ticket's nine conceptual stages in order. Firm resolution is
followed by a complete source-profile snapshot before enabled items are expanded or attempted.
Artifacts and firms execute independently. Prioritized runnable candidates are attempted until an
accepted result is reached; candidate, artifact, and firm failures remain durable diagnostics and
do not terminate unrelated work.

The production composition currently registers one executable `direct_url` adapter. `feed`,
`identifier`, `listing_page`, and `discovery` remain intentionally unsupported. Enabled artifacts
using those modes participate and produce `skipped` with the exact diagnostic **“No adapter
available for this retrieval mode.”** Enabled artifacts without candidates produce
`configuration_problem`. This explicitly permits the canonical 48-artifact catalog to exceed
current adapter coverage.

The workflow translates each runnable snapshotted candidate into an immutable governed acquisition
source, then calls the existing `AcquisitionEngine`. Successful exact bytes enter only through
`AcquisitionRepository.record_success`; existing content-addressed immutable artifact storage,
retrieval ledger, document index, and checkpoints remain authoritative. The workflow journal
stores plans, progress, results, and diagnostics, never alternate artifact bytes.

The interfaces are thin initiators:

- CLI: `rfi pull --firm ...` and `rfi pull --all-configured` call `PullWorkflow.run`;
- REST: `POST /api/pulls` calls `initiate` then `execute`, while status and result endpoints read
  the durable run journal; and
- GUI: the new top-level `/pull-sources` tab uses only those REST endpoints to select firms, show
  readiness counts, launch, poll progress, and render results.

## Verification Resolution

Focused tests and the deterministic proof cover:

- the exact nine-stage order;
- multiple selected firms and `--all-configured` selection;
- source-profile revision snapshots;
- independent candidate, artifact, and firm execution;
- success, duplicate, no change, skipped, configuration problem, and retrieval failure;
- completed, partial, and failed run aggregation;
- CLI request routing, REST initiation/status/results, and GUI thin-client markers;
- exact whole-artifact ingestion through the acquisition engine and repository ingress;
- immutable artifact readback and repository integrity; and
- explicit unsupported-mode stubs.

Reproducible commands:

```sh
make task015-test
make task015-proof
make validate
make review-package
```

The complete generated review package is written to `.artifacts/review/TASK-015/`, with a hashed
archive at `.artifacts/review/TASK-015-review.zip`.

## Remaining Limitations

- Only `direct_url` has an executable adapter in this milestone.
- Runs are serialized within one composed workflow instance; there is no cross-process writer
  coordination.
- The local REST adapter uses an in-process background thread, not a durable external queue. An
  abrupt process exit can leave an inspectable `running` journal record.
- Direct URL retrieval implements current single-request behavior only; no new retry policy,
  scheduling, polling, authentication store, or discovery is introduced.
- The console is an unauthenticated local operator surface.

## Architectural Status Summary

- Pull Workflow business capability: **Complete** for durable request receipt, firm resolution,
  revision snapshotting, planning, attemptability, execution, result recording, and aggregation.
- GUI, CLI, and REST initiation: **Complete** and routed through the same workflow.
- Source-profile authority: **Complete and preserved**; every enabled artifact participates.
- Acquisition engine and repository ingress: **Complete and reused**; no alternate evidence path
  exists.
- Exact whole-artifact storage: **Complete and preserved** with duplicate/no-change distinction.
- Direct URL adapter coverage: **Usable with Limitations**.
- Feed, identifier, listing-page, and discovery coverage: **Provisional stubs** with durable,
  operator-visible skip diagnostics.
- Operational workflow hosting: **Usable with Limitations** for local single-process operation;
  scheduling and distributed/crash-recovering execution are not started.
- Next architectural milestone: add evidence-driven adapter coverage while retaining Pull Workflow
  as the sole acquisition orchestration entry point and future scheduler target.
