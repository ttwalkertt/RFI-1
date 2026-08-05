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

1.  Every acquisition SHALL be orchestrated as bounded deterministic resolution phases. Normal
    acquisition SHALL begin with one consolidated phase containing canonical learned FIFO seeds
    in FIFO order. A configured fallback, when present, is a separate conditional phase sharing
    the same run-level resource context. Operator and recovery invocations remain exact
    single-seed phases.

2.  The LLM SHALL NOT be invoked unless deterministic acquisition fails
    to validate the requested transcript.

3.  Every LLM-proposed URL SHALL be treated only as a temporary starting
    seed.

4.  Every temporary seed SHALL execute the same exact-seed deterministic resolver used by
    operator seed injection with an explicitly selected registered provider. It SHALL NOT
    activate normal learned seeds or the configured fallback, infer a provider from URL shape, or
    silently use firm configuration to select one.

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

10. The acquisition target (firm, canonical artifact, and selection criteria) and explicitly
    selected provider SHALL remain constant for every recovery invocation. Only the starting seed
    may vary between its deterministic trials.

11. Selection criteria SHALL default to the existing "latest" behavior until
    explicitly supplied by future callers.

------------------------------------------------------------------------

# Normal Acquisition

The acquisition orchestrator owns learned-seed sequencing and canonicalization.

Normal acquisition executes one consolidated learned-seed resolution phase. It fetches each
canonical learned seed at most once, classifies transcript documents for direct validation, and
extracts only immediate transcript-document links from listing pages. It does not recursively
traverse listing graphs.

Document classification uses the repository's explicit structural transcript assessment. That
assessment is limited to media type, document signature, JavaScript-shell evidence,
transcript/earnings terminology, and speaker/section structure. Firm identity, event date,
selection, checkpoint, persistence, and learning remain downstream validator or engine concerns
and cannot change page role.

If learned resolution does not produce a validated `latest` result, the orchestrator may execute
one configured archive fallback phase. Both phases share one run-level page, byte, host, redirect,
elapsed, and unique-candidate resource context.

On the first validated `latest` success, the orchestrator performs the existing learning and
checkpoint behavior and terminates. Range selection continues to use its existing global terminal
reduction. The LLM is never invoked during successful normal acquisition.

------------------------------------------------------------------------

# Recovery Path

Only after deterministic acquisition fails:

1.  Produce complete structured diagnostics.
2.  Supply bounded diagnostics to the LLM.
3.  Request one temporary starting URL.
4.  Execute the same exact-seed deterministic resolver used by operator injection.
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

Each acquisition phase is deterministic for a fixed:

-   acquisition target;
-   repository state;
-   acquisition policy; and
-   starting seed.

Only temporary-seed selection between failed deterministic phases is
LLM-assisted.

------------------------------------------------------------------------

# Diagnostics

Every deterministic acquisition phase SHALL produce complete structured
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

1. Refactor acquisition into an explicit orchestration layer, a bounded consolidated normal
   resolution phase, and a reusable exact-seed resolver for operator and recovery invocations.
2. Introduce explicit acquisition selection criteria with a default of `latest`.
3. Add bounded LLM-assisted temporary-seed recovery.
4. Expose selection criteria through external invocation paths while preserving default behavior.
5. Add date-driven and period-driven historical backfill capabilities as a separate enhancement.
