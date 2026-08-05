# TASK-065 --- Require Explicit Transcript Provider for Seed Injection

## Objective

Require transcript seed injection requests to explicitly identify the
transcript provider implementation instead of relying on implicit
URL-based provider selection.

This task establishes an explicit provider contract for transcript
acquisition and aligns transcript-learning inspection with that persisted
provider authority. It does **not** change transcript search behavior,
provider-specific URL acceptance, or learning order/retention policy.

## Background

Transcript acquisition is evolving toward a bounded, provider-owned
resolution model.

The current seed injection API accepts only a URL and relies on
orchestration to determine which transcript provider should receive the
request. This unnecessarily couples provider dispatch to URL
interpretation.

Provider selection should instead be an explicit operator decision.

The provider implementation should then determine whether the supplied
URL is valid for that provider and how it should be processed.

## In Scope

-   Require a `provider` field in the transcript seed injection request.
-   Validate the provider through the existing
    `TranscriptProviderRegistry`.
-   Pass the provider through the existing acquisition workflow into the
    existing `AdapterAcquisitionTrial.provider`.
-   Remove URL-based provider selection from orchestration.
-   Include the authoritative persisted provider association in every
    provider-backed transcript-learning inspection entry.
-   Preserve explicit provider association from successful seed injection
    through durable learning and read-only inspection.
-   Update operator Help, endpoint documentation, curl examples, proof
    scripts, and API documentation.

## Explicitly Out of Scope

-   StockAnalysis archive/document URL acceptance.
-   Transcript discovery changes.
-   Bounded resolution behavior.
-   Learning ranking, ordering, retention, or eviction policy.
-   Checkpoint behavior.
-   Replay behavior.
-   Selector behavior.
-   Repository-state repair.
-   Search-provider abstractions.
-   LLM behavior.
-   Provider filters, query parameters, or provider path segments on the
    learning-inspection endpoint.
-   Provider migration or backfill inferred from URLs.

Provider-local URL acceptance will be addressed separately.

## Public API Contract

``` json
{
  "firm_id": "...",
  "canonical_artifact_id": "earnings_transcript",
  "provider": "stockanalysis",
  "starting_seed": "https://..."
}
```

Requirements:

-   `provider` is required.
-   It must be a non-empty string.
-   It must resolve through the existing provider registry.
-   Unknown providers fail using the existing invalid-request
    client-error vocabulary.
-   Provider selection comes only from the request body.
-   Provider selection shall not be accepted from query parameters.
-   URL-based provider inference is prohibited.

## Architectural Requirements

Provider dispatch follows:

    request
        ↓
    provider registry
        ↓
    selected provider
        ↓
    provider-local URL validation

The orchestration layer shall not inspect URL structure to choose a
provider.

## Required Invariants

Preserve:

-   provider registry contracts;
-   acquisition adapter contracts;
-   existing persistence models and repository retention semantics;
-   checkpoints;
-   learning ranking, ordering, and eviction behavior;
-   selectors;
-   replay.

Only explicit provider dispatch and exposure of its existing authoritative
learning association change.

## Operator Help

Update:

-   endpoint Help;
-   request examples;
-   curl examples;
-   API documentation;
-   proof scripts;
-   normative review documentation.

All examples shall use the required `provider` field.

## Review Requirements

Demonstrate:

-   one provider-selection path;
-   no URL inference;
-   no firm-configuration fallback;
-   no duplicate provider-dispatch mechanism;
-   unchanged acquisition behavior beyond explicit provider dispatch.

## Validation

-   Missing provider rejected.
-   Blank provider rejected.
-   Unknown provider rejected.
-   Registry resolution verified.
-   Provider propagated to `AdapterAcquisitionTrial.provider`.
-   No orchestration URL inference.
-   Query-based provider selection rejected.
-   Direct transcript injection succeeds with the correct provider.
-   Existing failure/success learning behavior unchanged.
-   Help/documentation validation.
-   TASK-060 regressions.
-   TASK-063 regressions.
-   Full `make validate`.

## Complexity Review

Confirm:

-   one provider-selection mechanism;
-   no new provider abstractions;
-   no URL inference;
-   no provider-specific HTTP-layer logic;
-   no behavioral change beyond explicit provider dispatch.

## Approved Add-On --- Persisted Provider in Learning Inspection

The active TASK-065 milestone also aligns transcript learning inspection with
explicit provider selection.

### Existing Endpoint and Response Shape

Keep the existing endpoint unchanged:

    GET /api/transcript-acquisitions/learning/{firm_id}

Do not add a provider path segment, provider query parameter, or alternate
endpoint. Preserve the existing response envelope and field vocabulary. Add
only the provider information needed to make each retained learning entry
independently dispatchable and explainable:

``` json
{
  "provider": "stockanalysis",
  "requested_url": "https://..."
}
```

Unknown-firm and empty-learning behavior remain unchanged.

### Authority, Persistence, and Compatibility

-   Returned provider association must come from persisted authoritative
    learning state.
-   The read path must not infer or reconstruct provider from URL structure.
-   The read path must not derive provider from current firm configuration.
-   Successful seed injection must persist its explicitly selected provider
    with resulting learning.
-   Failed injection must create no learning entry or provider association.
-   Learning entries associated with different providers for one firm must
    remain distinguishable.
-   Existing learning ordering and bounded-retention behavior remain
    unchanged.
-   Inspection remains read-only and must not change repository revision or
    any repository state.
-   Before persistence changes, inspect the existing learning-row schema and
    repository contracts. Reuse an authoritative persisted provider field if
    one exists. Otherwise add only the smallest explicit persistence change.
-   Define, test, and document a deliberate compatibility rule for historical
    rows lacking provider information. Do not parse URLs or consult current
    configuration to backfill or repair them. Fail closed or expose absence
    according to existing repository compatibility conventions.

Provider association may be added to the persistence contract only as needed
for this inspection authority. This add-on does not change what URL is learned,
learning ranking, order, retention bound, eviction, StockAnalysis URL
acceptance, search, candidate extraction, checkpoint, replay, or selectors.

### Operator Help and Documentation

Update every operator-facing and normative description of transcript learning
inspection to:

-   show `provider` in populated learning entries;
-   explain that it is the persisted provider association used for dispatch;
-   state that it is not inferred from the URL or current firm configuration;
-   preserve and document unknown-firm and empty-learning behavior;
-   update response examples, Help completeness tests, API documentation,
    proofs, architectural review, and review-package evidence.

### Add-On Validation

Demonstrate:

1.  Seed injection with `provider=stockanalysis` persists that provider with
    the learning entry.
2.  Learning inspection returns the persisted provider unchanged.
3.  Failed injection creates no provider-associated learning.
4.  Learning reads do not infer provider from URL shape.
5.  Learning reads do not substitute current firm configuration.
6.  Two learning entries for one firm with different providers remain
    distinguishable.
7.  Existing ordering and retention bounds remain unchanged.
8.  Inspection remains read-only and does not change repository revision or
    state.
9.  Unknown-firm and empty-learning behavior remain unchanged.
10. TASK-061 learning-inspection regressions remain green.

Retain all original TASK-065 validation, including TASK-060 and TASK-063
regressions and full `make validate`.

### Add-On Review and Complexity Evidence

The architectural review and final package must cover both explicit provider
dispatch and persisted learning association. Include schema and compatibility
evidence if persistence changes, the final response shape, the explicit rule
for older provider-less rows, Help/documentation validation, all add-on tests,
TASK-061 regressions, original TASK-065 regressions, and full validation.

Confirm:

-   one provider-selection and dispatch mechanism;
-   one authoritative persisted provider association per provider-backed
    learning entry;
-   no URL inference or current-configuration substitution on reads;
-   no alternate registry, learning endpoint, provider filter, or duplicate
    abstraction;
-   no behavior change to learning order, ranking, retention, eviction, or
    acquisition concerns outside the approved provider association.

Regenerate the complete review package from the completed final branch head
after the updated ticket and implementation are committed.
