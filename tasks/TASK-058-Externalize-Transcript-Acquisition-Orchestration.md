# TASK-058 --- Externalize Transcript Acquisition Orchestration

## Status

Complete

------------------------------------------------------------------------

# Summary

This task is the **first step** in a planned architectural evolution of
the earnings-call transcript acquisition pipeline.

It establishes the orchestration and execution boundaries required for
future enhancements while intentionally preserving all existing
observable behavior.

The planned follow-on work is:

1.  **TASK-058 (this task)** --- Externalize transcript acquisition
    orchestration by separating learned-seed sequencing from
    deterministic acquisition trials.
2.  **Future task** --- Introduce explicit acquisition selection
    criteria while defaulting to the current `latest` behavior so
    existing callers remain unchanged.
3.  **Future task** --- Add bounded LLM-assisted temporary-seed recovery
    after normal deterministic acquisition has exhausted learned FIFO
    seeds.
4.  **Future task** --- Expose acquisition selection criteria through
    public service and operator invocation paths while preserving
    existing defaults.
5.  **Future enhancement** --- Add date-driven and fiscal-period-driven
    historical backfill using the established selection framework.

This task intentionally implements **only Step 1**.

**Design reference:**

`/docs/design/TRANSCRIPT_LLM_SEED_RECOVERY.md`

------------------------------------------------------------------------

# Objective

Refactor transcript acquisition so that the deterministic discovery
implementation executes exactly one deterministic acquisition trial for
one starting seed, while a new orchestration layer owns sequencing of
learned FIFO seeds.

This task is an architectural refactoring only. Observable acquisition
behavior, retrieval results, learning, checkpoint advancement, traversal
limits, validation semantics, diagnostics, and operator experience shall
remain unchanged.

------------------------------------------------------------------------

# Motivation

The current implementation conceptually treats the learned FIFO seed set
as a single discovery invocation.

Future work requires treating each starting seed as an independently
attributable deterministic acquisition trial.

External orchestration provides:

-   explicit trial boundaries;
-   per-seed provenance;
-   deterministic trial diagnostics;
-   clean insertion of bounded LLM-assisted recovery;
-   explicit acquisition selection criteria; and
-   future historical backfill support.

------------------------------------------------------------------------

# Scope

## In Scope

-   Create an orchestration layer that iterates learned FIFO seeds in
    FIFO order.
-   Execute one deterministic acquisition trial per seed.
-   Terminate immediately after the first validated acquisition.
-   Aggregate trial outcomes into a single acquisition result.
-   Refactor deterministic acquisition into a reusable single-seed
    trial.
-   Preserve all externally observable behavior.

## Explicitly Out of Scope

-   Temporary operator-supplied seeds.
-   LLM invocation.
-   Selection criteria.
-   HTTP API changes.
-   Discovery, ranking, validation, or learning changes.
-   Historical backfill.

------------------------------------------------------------------------

# Required Architectural Invariants

1.  Every deterministic acquisition trial accepts exactly one starting
    seed.
2.  Learned FIFO sequencing is performed exclusively by the
    orchestration layer.
3.  Every deterministic trial executes the existing traversal,
    retrieval, ranking, and validation implementation.
4.  Deterministic trials never determine which seed executes next.
5.  Orchestration alone owns acquisition completion, learning after
    validated success, checkpoint advancement, and overall acquisition
    status.
6.  Existing observable acquisition behavior remains unchanged.

------------------------------------------------------------------------

# Behavioral Requirements

Normal acquisition shall continue to:

-   execute learned FIFO seeds in the existing order;
-   terminate on the first validated transcript;
-   apply retained-anchor learning exactly as today;
-   advance checkpoints exactly as today; and
-   produce equivalent operator-visible results.

------------------------------------------------------------------------

# Diagnostics

Each deterministic trial shall produce an independently attributable
structured outcome.

The orchestration layer shall aggregate trial outcomes while preserving:

-   starting seed;
-   traversal diagnostics;
-   validation outcome; and
-   acquisition termination reason.

------------------------------------------------------------------------

# Testing

Add focused regression tests proving:

-   learned FIFO ordering is unchanged;
-   one deterministic trial executes per learned seed;
-   successful acquisition terminates remaining trials;
-   failed trials do not advance learning;
-   successful acquisition performs existing retained-anchor learning;
-   checkpoint behavior is unchanged; and
-   overall acquisition behavior is unchanged.

------------------------------------------------------------------------

# Validation

Required verification:

-   Focused orchestration tests.
-   Existing transcript acquisition regression suite.
-   Full `make validate`.
-   Manual proof demonstrating identical acquisition behavior before and
    after refactoring.

------------------------------------------------------------------------

# Review Package

Include:

-   architectural summary;
-   files changed;
-   orchestration responsibilities;
-   deterministic trial responsibilities;
-   focused test evidence;
-   full validation results;
-   manual verification evidence; and
-   confirmation that no observable acquisition behavior changed.
