# TASK-059 --- Add Explicit Transcript Acquisition Selection Criteria

## Status

Complete

------------------------------------------------------------------------

# Summary

This task is the **second step** in the planned architectural evolution
of the earnings-call transcript acquisition pipeline.

Overall feature arc:

1.  **TASK-058 (completed)** --- Externalize transcript acquisition
    orchestration and establish one independently attributable
    deterministic trial per starting seed.
2.  **TASK-059 (this task)** --- Introduce an explicit, immutable
    acquisition selection contract while preserving existing behavior
    through the compatibility default `latest`.
3.  **Future task** --- Add bounded LLM-assisted temporary-seed recovery
    after normal learned-seed acquisition is exhausted.
4.  **Future task** --- Expose selection criteria through service and
    operator invocation paths while preserving default behavior.
5.  **Future enhancement** --- Add deterministic historical backfill by
    repeatedly invoking `first_in_date_range` while advancing a
    continuation boundary.
6.  **Future enhancement** --- Introduce stable continuation cursors
    (for example, document identity) if required for same-day ambiguity.

This task intentionally implements **only Step 2**.

**Design reference:** `docs/design/TRANSCRIPT_LLM_SEED_RECOVERY.md`

------------------------------------------------------------------------

# Objective

Introduce an explicit, immutable transcript acquisition selection
contract that defines **which** transcript qualifies for a single
acquisition request.

The identical selection contract shall propagate unchanged through:

-   acquisition orchestration;
-   every deterministic trial;
-   candidate qualification;
-   ranking and validation.

Existing callers shall require no changes. When omitted, the effective
selector shall be:

    latest

No public API or operator interface changes are introduced.

------------------------------------------------------------------------

# Motivation

TASK-058 separated **where discovery begins** (starting seed) from **how
acquisition executes** (deterministic trials and orchestration).

This task separates the remaining concern:

-   **Selection contract** --- Which transcript qualifies.
-   **Starting seed** --- Where deterministic discovery begins.

These concerns must remain independent.

------------------------------------------------------------------------

# Scope

## In Scope

-   Define a typed acquisition selection contract.
-   Attach it to the immutable acquisition target.
-   Default omitted selection to `latest`.
-   Propagate the contract unchanged through orchestration and every
    deterministic trial.
-   Apply deterministic qualification using the selection contract.
-   Extend structured diagnostics and provenance with selection
    attribution.
-   Preserve existing observable behavior.

## Out of Scope

-   HTTP/API changes.
-   Operator UI.
-   LLM integration.
-   Temporary operator seeds.
-   Backfill orchestration.
-   Continuation cursors.
-   Discovery, traversal, ranking, checkpoint, or learning changes.

------------------------------------------------------------------------

# Selection Modes

## `latest`

Preserve current behavior exactly.

This is the compatibility default.

## `first_in_date_range`

Select exactly one validated transcript satisfying:

-   inclusive `start_date`;
-   inclusive `end_date`.

Return the **earliest** validated qualifying transcript.

Ordering shall use normalized validated event dates.

If multiple qualifying artifacts share the earliest date, existing
deterministic ranking and tie-breaking rules remain authoritative.

Discovery order, URL order, page titles, and starting seeds shall not
determine the selected artifact.

Return one artifact or a structured no-match outcome.

Fiscal year and fiscal quarter remain validated metadata and may support
repository queries, reporting, and future planning, but they are **not**
acquisition selectors.

------------------------------------------------------------------------

# Required Architectural Invariants

1.  The acquisition target and selection contract are immutable for the
    acquisition attempt.
2.  Every deterministic trial receives the identical selection contract.
3.  Only the starting seed varies between trials.
4.  Omitted selection resolves to `latest`.
5.  Validation alone determines qualification.
6.  URLs, titles, discovery order, and starting seeds are advisory only.
7.  Selection does not change orchestration ownership, learned-seed
    ordering, traversal budgets, checkpoint semantics, or
    retained-anchor learning.
8.  Selection attribution appears in structured diagnostics and
    provenance.

------------------------------------------------------------------------

# Behavioral Requirements

Compatibility shall be preserved for all existing callers.

For `first_in_date_range`:

-   exactly one artifact is returned;
-   wrong-date candidates are rejected;
-   no-match is reported explicitly;
-   failed selection does not advance checkpoints or retained-anchor
    learning.

------------------------------------------------------------------------

# Testing

Add focused tests proving:

-   default compatibility (`latest`);
-   immutable propagation across trials;
-   `first_in_date_range` returns the earliest validated qualifying
    artifact;
-   same-date candidates use existing deterministic tie-breaking;
-   URLs and titles alone cannot satisfy selection;
-   conflicting URL/title dates cannot override validated artifact-content dates;
-   same-date candidates discovered from different seeds are independent of
    seed order, seed-local proposal rank, and URL-derived identities;
-   complete, partial, blocked, and failed runs have terminal selection
    diagnostics;
-   qualification counts remain exact beyond bounded diagnostic samples;
-   an inclusive `date.max` endpoint does not overflow;
-   failed selection does not alter learning or checkpoints;
-   existing transcript acquisition behavior remains unchanged.

------------------------------------------------------------------------

# Validation

Required:

-   focused TASK-059 tests;
-   TASK-058 regression suite;
-   transcript acquisition regression suite;
-   full `make validate`;
-   manual compatibility proof.

------------------------------------------------------------------------

# Review Package

Include:

-   architectural summary;
-   selection contract definition;
-   propagation path;
-   compatibility proof for `latest`;
-   proof of `first_in_date_range` behavior;
-   focused and full validation results;
-   confirmation that no public invocation path, LLM behavior, or
    backfill capability was introduced.
