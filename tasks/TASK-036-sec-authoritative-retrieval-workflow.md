# TASK-036 --- SEC End-to-End Retrieval Stack (Vertical Slice 1)

## Status

**Complete**

------------------------------------------------------------------------

# Objective

Implement the first narrow vertical slice of the SEC-specific retrieval
subsystem.

This task exists to prove the architecture and workflow of a complete
SEC retrieval stack. It intentionally favors end-to-end correctness and
architectural clarity over framework generalization. The resulting
implementation should establish the reference workflow that future
acquisition systems will be evaluated against.

Assume the operator has already created and checked out the `TASK-036`
branch.

------------------------------------------------------------------------

# SEC Retrieval Workflow

The primary deliverable of this task is a functioning SEC retrieval
workflow.

``` text
Target Firm
    ↓
Determine SEC applicability
    ↓
Load existing SEC source knowledge
    ↓
Validate existing source
        │
        ├── Verified → Continue
        │
        └── Missing / Stale
                ↓
        Resolve authoritative SEC identity
                ↓
        Persist verified source knowledge
    ↓
Determine filing policy
    ↓
Enumerate candidate filings
    ↓
Select deterministic filing
    ↓
Retrieve exact SEC document bytes
    ↓
Validate retrieved identity and metadata
    ↓
Canonical immutable repository ingestion
    ↓
Emit operator-visible workflow outcome
```

This workflow is the architectural contract for the SEC subsystem.
Existing verified source knowledge shall always be used first.
Authoritative resolution shall occur only when required by policy or
observed anomalies.

------------------------------------------------------------------------

# Scope

Implement an independently invocable SEC retrieval workflow capable of:

1.  Starting from an existing target firm.
2.  Resolving or reusing SEC issuer identity.
3.  Retrieving a bounded filing class (10‑K is sufficient).
4.  Ingesting retrieved artifacts into the existing immutable
    repository.
5.  Producing complete operator diagnostics.
6.  Executing repeatedly with deterministic, idempotent results.

------------------------------------------------------------------------

# Architectural Goals

-   Deterministic-first retrieval.
-   Authoritative issuer resolution.
-   Durable SEC source knowledge.
-   Immutable repository ingestion.
-   Explicit workflow state transitions.
-   Fail-closed conflict handling.
-   Operator-visible outcomes.
-   Idempotent execution.

Do not introduce speculative generic acquisition abstractions. Reuse
existing repository primitives whenever appropriate.

------------------------------------------------------------------------

# In Scope

## SEC issuer resolution

Support:

-   Direct issuer
-   Parent issuer
-   Non-applicable firm
-   Unresolved identity

## SEC source knowledge

Maintain durable SEC source records including:

-   Legal issuer
-   CIK
-   Filing regime
-   Verification status
-   Verification timestamp

## Deterministic retrieval

Retrieve filings using verified SEC identity with deterministic
selection.

## Artifact ingestion

Use the existing immutable repository mechanisms.

## Workflow outcomes

Differentiate at minimum:

-   Success
-   Success with source bootstrap
-   Non-applicable
-   No qualifying filing
-   Source ambiguity
-   Source conflict
-   Retrieval failure
-   Cancelled

## Source reconciliation

Automatically permit:

-   Missing source creation
-   Verification refresh
-   Metadata refresh

Fail closed on conflicting issuer identity, competing CIKs, or
conflicting parent relationships.

------------------------------------------------------------------------

# Explicit Non-Goals

-   Generic acquisition framework
-   Investor Relations retrieval
-   Web discovery
-   RSS
-   Patent retrieval
-   Broad SEC filing coverage
-   Complete historical ingestion
-   Scheduling
-   Acquisition plans

------------------------------------------------------------------------

# Required Design Review

Before implementation, provide:

-   Repository reconnaissance
-   Workflow description
-   Lifecycle states
-   Source model
-   Failure analysis
-   Reconciliation policy
-   Repository integration points
-   Explicit non-goals

------------------------------------------------------------------------

# Acceptance Criteria

Demonstrate:

1.  Verified source → retrieve → ingest.
2.  Missing source → bootstrap → persist → retrieve.
3.  Validation refresh path.
4.  Conflicting issuer identity fails closed.
5.  Non-applicable firm produces explicit outcome.
6.  Repeat execution creates no duplicate artifacts.
7.  Cancellation leaves bounded inspectable state.

------------------------------------------------------------------------

# Required Validation

Provide evidence for:

-   Focused unit tests
-   Integration tests
-   Bootstrap path
-   Verified-source path
-   Conflict handling
-   Non-applicable path
-   Cancellation
-   Idempotency
-   Repository validation

------------------------------------------------------------------------

# Required Review Package

Include:

-   Architectural design summary
-   Workflow state diagram
-   Before/after SEC source knowledge
-   Bootstrap evidence
-   Deterministic retrieval evidence
-   Immutable artifact evidence
-   Conflict evidence
-   Validation results
-   Known limitations
-   Recommendations for future architectural generalization

------------------------------------------------------------------------

# Git Instructions

Assume the operator has already created and checked out the `TASK-036`
branch.

Required:

-   Implement the task.
-   Run all required validation.
-   Commit all task-related implementation, tests, and documentation.

Do **not**:

-   Merge
-   Rebase
-   Delete branches
-   Perform repository cleanup
-   Push additional branches

------------------------------------------------------------------------

# Success Definition

RFI contains a complete SEC-specific end-to-end retrieval workflow for a
bounded filing class that demonstrates deterministic retrieval, safe
source bootstrap and validation, immutable ingestion, explicit operator
outcomes, and produces evidence to guide future acquisition
architecture.

------------------------------------------------------------------------

# Completion Evidence

## Implemented architecture

The `rfi.sec` package is an SEC-specific workflow façade. It composes the existing firm catalog,
bounded SEC provider, artifact-specific Form 10-K adapter, acquisition engine, and immutable
repository. Schema v8 adds only durable SEC source knowledge and SEC workflow journals. No generic
acquisition framework or SEC branch was added to the Pull Workflow.

The complete design, lifecycle, failure analysis, reconciliation policy, integration points,
explicit non-goals, limitations, and required Architectural Status Summary are recorded in
`docs/sec-authoritative-retrieval-workflow.md`.

## Acceptance scenarios

- Verified source → retrieve → ingest: `test_verified_source_is_used_without_resolution`.
- Missing source → bootstrap → persist → retrieve:
  `test_missing_source_bootstraps_retrieves_and_repeat_is_idempotent`.
- Validation refresh: `test_stale_source_refreshes_metadata_without_identity_change`.
- Conflicting identity: `test_conflicting_cik_fails_closed_before_ingestion`.
- Ambiguity and parent representation:
  `test_ambiguity_is_explicit_and_parent_source_is_supported`.
- Non-applicable: `test_non_applicable_is_explicit_and_does_not_retrieve`.
- No qualifying filing: `test_no_qualifying_filing_is_distinct`.
- Cancellation: `test_cancellation_is_durable_bounded_and_inspectable`.
- Idempotency and immutable integrity: the bootstrap/repeat test proves one artifact identity and
  `AcquisitionRepository.verify_integrity()` returns `PASS`.

## Validation

Ordinary validation removed live SEC runtime identities and used checked-in fixtures.

- Focused: `env -u RFI_SEC_USER_AGENT -u SEC_API_IO_API_KEY PYTHONPATH=src .venv/bin/python -m
  unittest tests.test_task036 tests.test_task016 tests.test_task022 tests.test_task021 -v` — PASS,
  38 tests.
- Full: `env -u RFI_SEC_USER_AGENT -u SEC_API_IO_API_KEY make validate` — PASS after the required
  local-loopback permission for existing admin integration tests; 377 repository tests plus every
  proof, quality, documentation, baseline, and build check.

## Review package

The reproducible package is generated by `scripts/generate_task036_review.py` at
`.artifacts/review/TASK-036-review.zip`, with a SHA-256 sidecar and ZIP integrity report.

## Known limitations

- The production resolver verifies explicit direct CIK identifiers; parent and non-applicable
  decisions require an authoritative resolver result supplied through the public contract.
- SEC selection uses recent submissions only and exact unamended Form 10-K policy.
- Cancellation is boundary-based and does not interrupt an active bounded HTTP request or atomic
  repository transaction.
- Repeated retrieval retains immutable observations/attempts while deduplicating artifact bytes.
