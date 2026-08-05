# TASK-065 --- Require Explicit Transcript Provider for Seed Injection

## Objective

Require transcript seed injection requests to explicitly identify the
transcript provider implementation instead of relying on implicit
URL-based provider selection.

This task establishes an explicit provider contract for transcript
acquisition. It does **not** change transcript search behavior or
provider-specific URL acceptance.

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
-   Update operator Help, endpoint documentation, curl examples, proof
    scripts, and API documentation.

## Explicitly Out of Scope

-   StockAnalysis archive/document URL acceptance.
-   Transcript discovery changes.
-   Bounded resolution behavior.
-   Learning policy.
-   Checkpoint behavior.
-   Replay behavior.
-   Selector behavior.
-   Repository-state repair.
-   Search-provider abstractions.
-   LLM behavior.

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
-   persistence;
-   checkpoints;
-   learning;
-   selectors;
-   replay.

Only provider dispatch changes.

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
