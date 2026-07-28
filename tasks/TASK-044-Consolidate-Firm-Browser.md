# TASK-044 --- Consolidate Firm Browser and Remove Firm Source Profiles

## Status

Done

## Objective

Make **Target Firms** the single operator interface for browsing and
inspecting firm configuration.

Eliminate the separate **Firm Source Profiles** page by integrating its
read-only information into the Target Firms detail panel using
collapsible sections. This is a presentation and navigation improvement
only.

## Scope

### Consolidate the UI

Retain: - Search - Filters - Firm list - Detail panel - Edit/Create
Revision - Retire

Remove the standalone **Firm Source Profiles** page.

### Integrate acquisition profile information

Embed the current read-only acquisition profile beneath the firm
identity.

Preserve: - External JSON filename - Read-only indication - Operator
notes - Acquisition categories - Enabled/disabled state -
Deterministic/semi-deterministic classification - Candidate counts -
Source-profile revision history

No editing capability is added.

### Organize with collapsible sections

Suggested top-level sections: - Identity - Names - Classification -
Discovery - Acquisition Profile - Revision History

Each section shall expand/collapse independently.

Default expanded: - Identity - Classification - Acquisition Profile

Default collapsed: - Discovery - Revision History - Large acquisition
categories

### Configuration authority

Clearly indicate externally managed configuration and the JSON filename.

## Explicit Non-Goals

-   No acquisition workflow changes
-   No JSON schema changes
-   No repository format changes
-   No editing of externally managed profiles
-   No External Sources redesign
-   No persistence or validation changes

## Acceptance Criteria

-   Target Firms exposes all information formerly available from Firm
    Source Profiles.
-   Firm Source Profiles is removed from navigation and routing.
-   Operators can inspect a firm's acquisition profile without leaving
    Target Firms.
-   External JSON ownership remains obvious.
-   Existing search/filter behavior is unchanged.

## Verification

Provide evidence of: 1. Browsing multiple firms. 2. Expand/collapse
behavior. 3. Correct acquisition profile rendering. 4. External JSON
authority/read-only display. 5. Firm Source Profiles removal. 6. Focused
UI tests passing. 7. Full validation passing.

### Follow-up authority repair

Removed browser-driven creation of new target firms, including the blank editor path and
`POST /api/firms`. Existing-firm revision and retirement remain available only where permitted;
externally managed firms remain inspect-only. Verification additionally covers the absent creation
control and route, permitted revision behavior, invalid external JSON rejection, idempotent reload,
and first materialization of a previously unseen firm from valid `*.firm-config.json` authority.

Repair verification completed 2026-07-27:

- `PYTHONPATH=src .venv/bin/python -m unittest tests.test_task044 tests.test_task011 tests.test_task041`
  — 25 tests passed.
- `make validate` — passed.
