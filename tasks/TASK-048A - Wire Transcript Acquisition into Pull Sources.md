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
