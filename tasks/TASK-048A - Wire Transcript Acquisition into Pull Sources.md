# TASK-048A --- Wire Transcript Acquisition into Pull Sources

## Status

Done

## Objective

Complete the operational integration of TASK-048 by wiring the
earnings-call transcript retriever into the existing
configuration-backed Pull Sources workflow.

## In Scope

-   Register the TASK-048 retriever as a Pull Sources adapter.
-   Honor the existing firm source-profile configuration.
-   Display the configured enable/disable state in the operator console.
-   Execute enabled transcript sources through the normal pull queue.
-   Preserve all existing repository, acquisition, and interval
    contracts.

## Out of Scope

-   Firm editor or CRUD UI.
-   New persistence.
-   Changes to the TASK-047 acquisition contract.
-   Changes to repository ownership of identities, artifacts, or
    observations.

## Required Invariants

-   Firm configuration remains JSON/configuration-backed.
-   The operator console is read-only with respect to firm source
    configuration.
-   Existing pull behavior is unchanged for all other source families.

## Verification

-   Focused integration tests.
-   Pull Sources regression tests.
-   Full `make validate`.
-   Live proof showing an enabled transcript source executes through the
    normal Pull Sources workflow without dedicated scripts.

## Architectural Status Summary

-   **Configuration projection — Complete.** Firm JSON selects only a named
    `discovery_class`; identity, aliases, domains, and existing IR hints are projected
    read-only into a transient discovery candidate.
-   **Repository discovery policy — Complete.** Versioned JSON owns the bounded
    `shallow`, `standard`, and `extended` limits and is validated against its schema.
-   **Transcript discovery and Pull Sources execution — Complete.** The production
    Pull Sources registry selects the transcript adapter for `discovery` candidates,
    executes bounded search/traversal, and hands candidate URLs to the TASK-048
    validator and ordinary repository ingress.
-   **Coverage and retained evidence — Usable with limitations.** Successful artifacts
    retain normal provenance. Policy exhaustion remains indeterminate and identifies
    the exhausted budget; discovery locations are operational and are not written back
    into firm JSON.
-   **Operator surface — Complete.** Existing source-profile and Pull Sources views
    remain read-only; no editor, CRUD route, or persistence authority was added.
-   **Next milestone.** A separately governed discovery adapter for other artifact
    families, including press releases, can reuse the named policy selection without
    changing firm configuration ownership.
