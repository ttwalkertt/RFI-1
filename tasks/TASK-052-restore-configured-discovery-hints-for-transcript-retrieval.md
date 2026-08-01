# TASK-052 --- Restore Configured Discovery Hints for Transcript Retrieval

## Status

Done

## Objective

Restore the existing firm-configured retrieval-hint path for
discovery-based earnings-call transcript acquisition.

An operator must be able to provide a bounded discovery hint for a
configured firm's earnings transcript source, and the Pull Sources
workflow must preserve and deliver that hint to the selected transcript
adapter.

The task must determine where the previously established hint contract
was lost and repair the narrowest appropriate configuration, projection,
or adapter boundary.

## Problem Statement

The Amazon earnings transcript source currently exposes only:

``` json
"earnings_transcript": {
  "discovery_class": "extended"
}
```

A bounded transcript pull exhausted `max_links_per_page` without
producing a candidate URL. A known firm-specific transcript listing
could constrain discovery without increasing search bounds, but the
current external firm configuration does not expose an evident path for
supplying that hint to the adapter.

Earlier source-profile and retrieval-candidate contracts included
discovery and adapter hints. TASK-048A also required the transcript
adapter to honor existing firm source-profile configuration. This
appears to be a lost configuration projection rather than a request for
broader search.

## In Scope

-   Inspect the external firm-config schema for transcript discovery
    configuration.
-   Trace configuration from JSON through runtime projection into the
    adapter request.
-   Restore the existing discovery-hint contract or equivalent
    authoritative representation.
-   Preserve configured hints through validation, planning, adapter
    invocation, and diagnostics.
-   Ensure the adapter uses configured hints before consuming general
    search breadth.
-   Add an Amazon configuration example using a firm-specific transcript
    listing URL.
-   Add regression coverage proving the hint is preserved and consumed.

## Out of Scope

-   Increasing search budgets or discovery limits.
-   Unbounded web search.
-   Hard-coding Amazon or any transcript provider.
-   Treating configured hints as provenance or canonical identity.
-   Redesigning the entire firm configuration schema.
-   Changing TASK-051 indeterminate coverage semantics.

## Required Semantics

-   Configuration hints must remain configuration, not provenance.
-   Missing hints preserve current behavior.
-   Invalid hints fail visibly.
-   Valid hints constrain discovery but do not bypass validation.

## Required Investigation

Determine: 1. Whether the original retrieval-hint contract still exists.
2. Where it is lost (schema, projection, planner, or adapter). 3.
Whether hints are accepted but ignored. 4. The single authoritative
location for the repair.

## Required Tests

-   Configured hint survives loading.
-   Runtime projection preserves the hint.
-   Adapter receives the hint unchanged.
-   Discovery is constrained by the hint.
-   Validation behavior is unchanged.
-   Missing and invalid hint cases.
-   TASK-051 indeterminate semantics remain intact.
-   Full validation passes.

## Live Proof

Using Amazon: - Configure a transcript discovery hint. - Demonstrate
that diagnostics show the hint being supplied and used. - Demonstrate
that no search bounds were increased. - Demonstrate successful
acquisition or accurate structured diagnostics.

## Review Actions

Review: - Schema. - Configuration loader. - Runtime projection. - Pull
Sources planner. - Adapter request construction. - Adapter discovery
logic. - Diagnostics. - Regression coverage.

## Verification Package

Include: - Root cause. - Configuration flow. - Files changed. -
Before/after examples. - Adapter request evidence. - Live proof. -
Focused tests. - Full validation. - Final Git status.

## Acceptance Criteria

-   A supported transcript discovery hint exists in external firm
    configuration.
-   The adapter demonstrably consumes it.
-   Search budgets are unchanged.
-   Validation and provenance contracts remain intact.
-   Amazon executes using configuration rather than hard-coded behavior and either acquires a
    validated transcript or rejects candidates with accurate structured diagnostics.
-   Full validation passes.

## Completion Record

### Root Cause

The canonical runtime contract, `RetrievalCandidate.discovery_hints`, and the transcript adapter's
URL-hint handling still existed. The external firm schema exposed only `discovery_class` for an
earnings-transcript source, and `_profile()` therefore had no source-scoped hint to project. In
addition, bounded discovery submitted general search queries before traversing URL hints.

### Authoritative Configuration Shape

`sources.earnings_transcript.discovery_hints` is the source-scoped authoring field. It is an
optional, unique, maximum-eight array of credential-free HTTP(S) URLs. It projects into the existing
`RetrievalCandidate.discovery_hints` field; no parallel runtime model was introduced. Firm-level
`source_hints` retain their existing general-orientation behavior and are not the authority added by
this task.

### Implementation Summary

- The packaged and operator schema validate the transcript-only field.
- External configuration projection places source-scoped values first and unchanged in the
  canonical candidate.
- Pull Sources' existing dataclass serialization delivers the candidate to the selected adapter.
- Bounded transcript discovery traverses URL hints before search and skips search when a hint
  already proposes candidates.
- Diagnostics report configured hint count, successfully fetched hint pages, and
  `not_supplied`, `used`, or `unusable` status.
- All hinted candidates still pass the existing host, date, media, transcript, and firm validation.

### Verification Results

- `make task052-test`: PASS, 26 focused and adjacent regression tests.
- `make validate`: PASS, full repository validation.
- `make task052-proof`: PASS as a bounded live proof execution. The configured Amazon URL was
  fetched first; `search_queries=0`, `configured_hint_status=used`, and the unchanged extended
  policy stopped at `max_links_per_page=30`. No candidate was admitted, and coverage remained
  `indeterminate` with accurate structured diagnostics.
- `config/discovery-policies.json` and `docs/discovery-policies-v1.schema.json` are unchanged.

The reproducible verification report is `docs/TASK-052-review.md`.
