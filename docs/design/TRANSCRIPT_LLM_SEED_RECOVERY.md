# LLM-Assisted Transcript Seed Recovery

**Status:** Design Reference

## Related Documents

-   `DESIGN_PRINCIPLES.md`
-   `ARCHITECTURE.md`
-   `ACQUISITION_POC_GUIDANCE.md`

------------------------------------------------------------------------

# Purpose

This document defines the bounded LLM-assisted recovery mechanism for
the earnings-call transcript acquisition pipeline.

Its purpose is to improve acquisition robustness **without changing the
deterministic architecture**.

The objective is **not** to make the LLM better at locating transcripts.
The objective is to allow the LLM to propose an improved starting
location after deterministic acquisition has exhausted its normal
search.

------------------------------------------------------------------------

# Goals

This design SHALL:

-   preserve deterministic acquisition as the primary retrieval
    mechanism;
-   preserve all existing traversal, ranking, validation, and checkpoint
    behavior;
-   improve recovery from difficult transcript sources that cannot be
    reached reliably from existing learned seeds;
-   preserve complete provenance for every LLM interaction and
    deterministic acquisition trial;
-   bound both execution and diagnostic context.

------------------------------------------------------------------------

# Architectural Invariants

The following invariants are mandatory.

1.  Every acquisition SHALL be orchestrated as an ordered sequence of independent deterministic trials. Normal acquisition SHALL begin by executing one deterministic trial for each learned FIFO seed in FIFO order.

2.  The LLM SHALL NOT be invoked unless deterministic acquisition fails
    to validate the requested transcript.

3.  Every LLM-proposed URL SHALL be treated only as a temporary starting
    seed.

4.  Every temporary seed SHALL execute the same single-seed deterministic trial implementation used by normal learned-seed acquisition.

5.  Validation SHALL determine success. A supplied seed URL is never
    considered authoritative.

6.  The final transcript may be discovered at a different, but related,
    URL.

7.  Successful acquisitions SHALL continue to update retained FIFO seeds
    exclusively through the existing evidence-based learning rules.

8.  LLM-proposed URLs SHALL NOT become learned seeds merely because they
    were proposed.

9.  Acquisition SHALL terminate after successful validation or after the
    configured temporary-seed trial limit.

10. The acquisition target (firm, canonical artifact, and selection criteria)
    SHALL remain constant for every trial. Only the starting seed may vary.

11. Selection criteria SHALL default to the existing "latest" behavior until
    explicitly supplied by future callers.

------------------------------------------------------------------------

# Normal Acquisition

The acquisition orchestrator owns learned-seed sequencing.

For each learned FIFO seed, the orchestrator executes one independent deterministic trial.

Each trial:

1. Executes deterministic traversal from exactly one starting seed.
2. Ranks candidate artifacts.
3. Validates candidates against the immutable acquisition target.
4. Produces an independently attributable trial outcome.

On the first validated success, the orchestrator performs the existing learning and checkpoint behavior and terminates. The LLM is never invoked during successful normal acquisition.

------------------------------------------------------------------------

# Recovery Path

Only after deterministic acquisition fails:

1.  Produce complete structured diagnostics.
2.  Supply bounded diagnostics to the LLM.
3.  Request one temporary starting URL.
4.  Execute the same single-seed deterministic trial implementation.
5.  Validate normally.
6.  If unsuccessful, repeat using cumulative bounded diagnostics.

No more than three temporary-seed trials are permitted.

------------------------------------------------------------------------

# Responsibilities

## LLM

The LLM is responsible only for proposing one temporary starting URL.

## Deterministic Trial

The deterministic trial remains solely responsible for:

-   traversal;
-   candidate generation;
-   candidate ranking;
-   validation;
-   checkpoint advancement;
-   retained-anchor learning;
-   provenance generation; and
-   structured diagnostics.

------------------------------------------------------------------------

# Learning

Temporary LLM-proposed URLs are transient operator assistance.

Repository learning occurs only through the existing evidence-based
retained-seed mechanisms.

------------------------------------------------------------------------

# Determinism Boundary

Each acquisition trial is deterministic for a fixed:

-   acquisition target;
-   repository state;
-   acquisition policy; and
-   starting seed.

Only temporary-seed selection between failed deterministic trials is
LLM-assisted.

------------------------------------------------------------------------

# Diagnostics

Every deterministic acquisition trial SHALL produce complete structured
diagnostics.

Those diagnostics become the bounded context supplied to the LLM for the
next temporary-seed proposal.

------------------------------------------------------------------------

# Non-goals

This design does not:

-   replace deterministic discovery;
-   permit LLM-directed crawling;
-   allow the LLM to traverse links;
-   allow the LLM to rank or validate candidates;
-   bypass repository policy;
-   expand traversal budgets;
-   weaken evidence, provenance, or diagnostics;
-   create permanent discovery rules from LLM proposals.


------------------------------------------------------------------------

# Future Evolution

The expected implementation sequence is:

1. Refactor acquisition into an explicit orchestration layer and reusable single-seed deterministic trials while preserving current behavior.
2. Introduce explicit acquisition selection criteria with a default of `latest`.
3. Add bounded LLM-assisted temporary-seed recovery.
4. Expose selection criteria through external invocation paths while preserving default behavior.
5. Add date-driven and period-driven historical backfill capabilities as a separate enhancement.
