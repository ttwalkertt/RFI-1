# TASK-037 --- Quarantine Message-ID Byte Conflicts and Continue Acquisition

## Status

**Complete**

------------------------------------------------------------------------

# Objective

Implement durable quarantine and operator visibility for immutable
Message-ID byte conflicts while allowing mailing-list acquisition to
continue safely.

This task preserves the existing fail-closed canonical Message-ID
invariant. It changes acquisition behavior so that a single
quarantinable conflict no longer aborts an otherwise successful
acquisition run.

Assume the operator has already created and checked out the `TASK-037`
branch.

------------------------------------------------------------------------

# Scope

Implement a conflict-quarantine workflow for canonical Message-ID
registration conflicts.

When a fetched RFC822 artifact normalizes to an existing Message-ID but
produces different immutable bytes:

1.  Preserve the existing canonical registration.
2.  Retain the candidate bytes as an immutable artifact.
3.  Create durable conflict evidence.
4.  Record the message outcome as conflicted/skipped.
5.  Continue processing remaining discovered messages.
6.  Complete the acquisition run as `completed_with_conflicts` (or
    equivalent) rather than failing the entire run.

------------------------------------------------------------------------

# Architectural Goals

-   Preserve immutable repository semantics.
-   Preserve canonical Message-ID uniqueness.
-   Never overwrite existing canonical artifacts.
-   Never discard conflicting evidence.
-   Continue acquisition safely after quarantinable conflicts.
-   Make conflicts durable and operator-visible.
-   Maintain deterministic repeat acquisition.

Only this explicitly classified conflict is recoverable. All unrelated
repository failures shall continue to fail the acquisition.

------------------------------------------------------------------------

# In Scope

## Conflict quarantine

Persist:

-   canonical artifact reference
-   candidate artifact reference
-   normalized Message-ID
-   artifact hashes
-   acquisition run
-   acquisition source
-   timestamps
-   conflict status
-   diagnostic reason

## Acquisition behavior

Continue processing remaining discovered messages after quarantining a
conflict.

## Operator visibility

Expose unresolved conflicts through the operator interface.

## Idempotency

Repeated observation of the same canonical/candidate pair shall update
durable evidence without duplicating artifacts or conflict cases.

------------------------------------------------------------------------

# Explicit Non-Goals

-   Canonical artifact replacement
-   Conflict resolution policy
-   Automatic candidate promotion
-   Generic artifact conflict framework
-   Repository invariant changes
-   Relaxation of immutable storage rules

------------------------------------------------------------------------

# Required Design Review

Before implementation provide:

-   interception point within acquisition
-   quarantine data model
-   workflow state changes
-   operator visibility design
-   idempotency strategy
-   repeat-acquisition behavior
-   failure classification

## Design Review (Approved Implementation Basis)

- **Interception point:** `MailingListAcquisitionService.acquire()` handles the
  per-message exception raised by `MailingListRepository.retain_message()` only
  when its details prove that conflicting candidate bytes were retained and a
  Message-ID quarantine case was recorded. No broader error-code catch is used.
- **Quarantine data model:** retain the Message-ID-specific conflict authority
  and add unresolved status, first/last observation timestamps, and an
  occurrence count. A conflicted run item references the candidate artifact and
  document, has no canonical message reference, and is classified as
  `conflicted`.
- **Workflow state:** conflicted items are omitted from canonical derived
  message/discussion projection, acquisition continues with later planned
  messages, and the run lifecycle is `completed_with_conflicts`.
- **Operator visibility:** unresolved cases are returned by the mailing-list
  query service and existing Linux mailing-list result API, then rendered in the
  acquisition summary with canonical/candidate artifact diagnostics.
- **Idempotency:** quarantine document, attempt, and conflict identities derive
  from the normalized Message-ID and candidate content hash. Re-observing the
  same canonical/candidate artifact pair updates the case's last-observed time
  and occurrence count without duplicating bytes, artifacts, or cases.
- **Repeat acquisition:** each run records its own conflicted/skipped outcome;
  the canonical registration remains unchanged and other messages continue.
- **Failure classification:** only a `message_id_conflict` carrying the
  repository's explicit retained-and-quarantined marker is recoverable. Legacy
  conflicts, publication-time conflicts, storage/integrity failures,
  cancellation, and every unrelated repository failure retain existing
  fail-closed behavior.

------------------------------------------------------------------------

# Acceptance Criteria

Demonstrate:

1.  Canonical artifact remains unchanged.
2.  Candidate bytes are retained immutably.
3.  Candidate receives no canonical Message-ID registration.
4.  Remaining messages continue processing.
5.  Run completes with conflicts rather than failing.
6.  Conflict becomes durable and operator-visible.
7.  Repeated acquisition creates no duplicate artifacts.
8.  Repeated acquisition creates no duplicate conflict cases.
9.  Non-conflict repository failures still fail the run.
10. Existing cancellation behavior remains unchanged.

------------------------------------------------------------------------

# Required Validation

Provide evidence for:

-   focused unit tests
-   acquisition continuation after conflict
-   immutable artifact retention
-   canonical registration preservation
-   operator conflict visibility
-   repeated acquisition idempotency
-   full repository validation

------------------------------------------------------------------------

# Required Review Package

Include:

-   architectural summary
-   workflow diagram
-   conflict lifecycle
-   canonical and candidate artifact evidence
-   acquisition continuation evidence
-   operator screenshots or diagnostics
-   validation results
-   known limitations

------------------------------------------------------------------------

# Git Instructions

Assume the operator has already created and checked out the `TASK-037`
branch.

Required:

-   implement the task
-   run validation
-   update the task ticket
-   commit task-related changes

Do not:

-   merge
-   rebase
-   push
-   create or delete branches
-   perform repository cleanup

------------------------------------------------------------------------

# Success Definition

RFI preserves immutable Message-ID semantics while allowing acquisition
to complete in the presence of quarantinable historical byte conflicts.
Operators receive durable evidence for later investigation without
interrupting the remainder of the acquisition run.

------------------------------------------------------------------------

# Completion Evidence

- Localized interception and failure classification implemented in the
  per-message mailing-list acquisition loop.
- Exact conflicting RFC822 bytes retained under stable, content-derived
  quarantine document identity.
- Canonical registration remains unchanged and the candidate receives no
  canonical registration.
- Durable unresolved conflict case records canonical/candidate references,
  hashes (through artifact identity), source, run, timestamps, status, reason,
  and repeat observation count.
- Per-run `conflicted_skipped` observations and manifest conflict diagnostics
  preserve the message outcome while later messages continue.
- Linux mailing-list result API and operator console expose unresolved conflict
  diagnostics as **Completed with conflicts**.
- Repeat acquisition creates neither duplicate artifact bytes nor duplicate
  conflict cases.
- Non-conflict repository failure and cancellation behavior remain unchanged.
- Focused `tests.test_task023`: 17 tests passed.
- Full `make validate`: 379 tests passed; proof scripts, lint, format,
  typecheck, documentation, baseline, and source-archive integrity all passed.
- Review package: `docs/task-037-review.md`.
