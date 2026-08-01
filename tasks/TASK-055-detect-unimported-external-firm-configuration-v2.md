# TASK-055 --- Detect Unimported External Firm Configuration

## Status

Complete

## Objective

Detect when the authoritative external `firm-config/*.firm-config.json`
configuration set differs from the configuration currently materialized
into the repository and notify the operator without validating,
materializing, or otherwise changing repository state.

## Problem Statement

The repository intentionally separates authoritative external
configuration from immutable repository projections. TASK-054 introduced
an explicit **Reload Firm Profiles** action, but operators are not
informed when the external authority has diverged from the currently
imported repository state.

The operator should not have to remember whether configuration was
imported. The system should detect divergence and present a clear,
persistent reminder while continuing to operate from the last
successfully materialized projections.

## In Scope

-   Persist a deterministic fingerprint of the complete authoritative
    configuration set after every successful materialization.
-   Compare the current external fingerprint with the persisted imported
    fingerprint:
    -   at admin startup;
    -   whenever the Target Firms page is loaded;
    -   immediately after a successful reload.
-   Display repository configuration status:
    -   Current.
    -   External changes available.
    -   Unable to inspect external configuration.
-   Apply consistent semantic color coding to status indicators, including
    the existing Pull Workflow outcome badges shown alongside configuration
    status in the admin console:
    -   green for successful/current states;
    -   blue for duplicate or otherwise informational states;
    -   amber for indeterminate, external-changes-available, or other
        attention-needed states;
    -   red for failed/unable-to-inspect states.
    Text labels and accessible semantics remain authoritative; color must
    never be the only indication of status.
-   Present a persistent operator reminder with a direct path to
    **Reload Firm Profiles**.
-   Clear the reminder automatically after a successful reload when
    fingerprints match.
-   Add focused API, UI, and workflow regression coverage.

## Out of Scope

-   Automatic validation.
-   Automatic reload or materialization.
-   Background polling or filesystem watching.
-   Browser editing of external JSON.
-   Per-firm change reporting.
-   Startup writes.

## Required Invariants

-   Repository projections remain the runtime authority until explicit
    reload.
-   Detection is strictly read-only.
-   Detection never advances repository revisions or creates immutable
    projections.
-   Detection never parses or schema-validates configuration documents.
-   Validation and materialization remain exclusively owned by
    `prepare_firm_configuration(state)`.
-   Detection identifies file additions, removals, renames, and
    byte-level content changes.
-   Fingerprints are deterministic and content-based; timestamps are not
    authoritative.
-   Imported fingerprints are recorded atomically with successful
    materialization.
-   Detection failures never report configuration as current.

## Required Operator Workflow

1.  Startup performs a read-only comparison.
2.  If external configuration differs, startup proceeds normally using
    existing projections.
3.  A persistent status indicates newer external configuration is
    available.
4.  Loading Target Firms refreshes the detection state.
5.  Reload Firm Profiles performs the existing governed materialization.
6.  Successful reload records the new fingerprint and clears the
    reminder.

## Required Tests

-   Startup performs no writes.
-   Added, removed, renamed, and modified files are detected.
-   Timestamp-only changes are ignored.
-   Target Firms refreshes status.
-   Reload clears the reminder.
-   Configuration and Pull Workflow status indicators use the documented
    semantic colors while retaining readable text labels and non-color status
    semantics.
-   Existing reload semantics, pull snapshot isolation, and startup
    behavior remain unchanged.
-   Full repository validation passes.

## Verification Package

Provide operator workflow evidence, fingerprint comparison proof,
startup write-free proof, Target Firms refresh proof, reload-clear
proof, focused tests, full `make validate`, changed-file inventory,
patch, final Git status, commit hash, and pushed branch.

## Acceptance Criteria

-   Operators are automatically informed whenever authoritative
    configuration differs from the imported repository state.
-   Detection remains read-only.
-   Runtime continues using existing projections until explicit reload.
-   The reminder clears immediately after successful reload.
-   Status indicators are conveniently color coded for rapid scanning:
    successful/current is green, duplicate/informational is blue,
    indeterminate/attention is amber, and failure/inspection failure is red,
    without relying on color alone.
-   Focused tests and full validation pass.

## Completion Record

The repository now records a deterministic filename-and-byte fingerprint in SQLite in the same
transaction that publishes externally managed firm and source-profile projections. Admin startup
and the Target Firms status endpoint compare that imported value with a raw, non-parsing external
fingerprint through read-only repository access. Target Firms presents current, changes-available,
and inspection-failure states and refreshes immediately after explicit reload. Pull Workflow and
configuration status badges retain text semantics while adding the documented accessible colors.

Focused acceptance coverage, operator proof, full validation, and the commit-aware review package
are recorded in `docs/TASK-055-review.md`.
