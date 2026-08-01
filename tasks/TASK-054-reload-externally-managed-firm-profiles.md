# TASK-054 — Reload Externally Managed Firm Profiles

## Status

Ready

## Objective

Add an explicit operator action to the Target Firms console that reloads the complete set of
externally managed `firm-config/*.firm-config.json` files into the repository-owned firm and
source-profile projections.

The action shall use the same governed validation and atomic materialization path as `rfi init`
without granting the browser unrelated repository-initialization authority.

## Problem Statement

Ordinary admin startup intentionally validates external firm configuration without updating its
persisted projections. This preserves the TASK-048B startup invariant, but an operator who edits a
firm configuration must currently leave the browser and run `rfi init` before a pull can use the
new profile revision.

The Target Firms page already identifies external JSON as the configuration authority and is the
natural operator surface for making this explicit write. A narrowly scoped reload action should
remove the hidden command-line step while preserving the established configuration ownership,
revision, validation, and transaction contracts.

## In Scope

- Add a **Reload Firm Profiles** button at the top of the Target Firms page.
- Require operator confirmation before materialization.
- Add one narrow admin API action for reloading the complete external firm-configuration set.
- Reuse `prepare_firm_configuration(state)` as the authoritative implementation path.
- Return a structured summary of configurations, firm revisions, source-profile revisions, and
  external identities materialized.
- Refresh the firm list and the selected firm's current identity and source profile after success.
- Present actionable validation and persistence failures in the Target Firms page.
- Add focused API, UI, transaction, and workflow regression coverage.

## Out of Scope

- Editing external JSON in the browser.
- Accepting a configuration document, file path, directory, or firm selection from the request.
- Reloading only one firm.
- Watching files or automatically reloading on change.
- Changing ordinary admin startup's read-only behavior.
- Changing `rfi init` semantics or creating a second materialization implementation.
- Running acquisitions, pulls, or network requests as part of reload.
- Cancelling, restarting, or changing the profile snapshot of an already-running pull.
- Suppressing unchanged revisions or redesigning revision identity.
- Adding authentication, remote administration, or broader initialization controls.

## Required Operator Workflow

1. The Target Firms heading exposes a **Reload Firm Profiles** button.
2. Activating it presents a confirmation that reload is a repository write and may create new
   immutable firm and source-profile revisions, including for unchanged files.
3. After confirmation, the button is disabled and communicates that reload is in progress.
4. The server validates the complete external configuration set before mutation.
5. If validation succeeds, the server materializes the complete set in one transaction.
6. The page reports the structured result and refreshes the firm list plus any selected current
   firm and profile.
7. If validation or persistence fails, the page reports the failure and retains the prior visible
   and durable state.

The operator must not need to restart the admin server after a successful reload. Pulls initiated
after reload shall snapshot the newly current source-profile revision.

## API Contract

Add a state-relative action equivalent to:

```http
POST /api/firm-configurations/reload
```

The request has no body parameters that influence configuration location or scope.

A successful response shall identify the action and expose the existing
`MaterializationResult` counts, for example:

```json
{
  "status": "reloaded",
  "files": 23,
  "firms": 23,
  "profiles": 23,
  "external_identities": 21,
  "authority": "external-json"
}
```

Exact field names may follow established repository naming, but the response must remain explicit
and testable. Configuration validation errors shall be structured client errors rather than
generic internal-server failures. Unexpected persistence failures shall remain server errors.

## Required Invariants

- External JSON remains the authority for externally managed firms and profiles.
- The firm and source-profile browser remains read-only for externally managed records.
- `prepare_firm_configuration(state)` remains the single orchestration path for explicit reload.
- The complete configuration set is validated before mutation.
- Firm revisions, source-profile revisions, external SEC identities, configuration authorities,
  current pointers, and the repository authority revision advance atomically.
- Any failure rolls back the complete materialization transaction.
- Historical revision JSON, identifiers, chains, and pointers are never rewritten.
- Existing artifact bytes, acquisition attempts, observations, knowledge, and stream state are not
  modified by reload.
- Ordinary admin startup continues to call validation without materialization.
- An already-running pull retains its captured profile snapshot; only later pulls see the reload.
- The endpoint cannot select arbitrary filesystem paths or accept configuration content.
- Existing local-default server binding and security headers remain unchanged.

## Known Limitation Retained by This Task

The existing explicit materialization path creates new firm and source-profile revisions on every
successful invocation, including when authoritative files are unchanged. TASK-054 shall disclose
that behavior in the confirmation text and preserve it. Change-aware no-op materialization is a
separate architectural decision and is not required here.

## Required Tests

### UI workflow

- The button is present at the top of Target Firms with the exact operator-facing label.
- Cancellation performs no request and no write.
- Confirmation disables the action while the request is active.
- Success refreshes the list and selected current firm/profile and displays materialization counts.
- Failure restores the action and presents an actionable message.

### API and materialization

- The endpoint accepts only `POST` at the fixed route.
- The endpoint invokes the established complete-set materialization path.
- A changed source-scoped discovery hint appears in the current projected source profile after
  reload without restarting the server.
- A subsequent Pull Sources run snapshots that new source-profile revision and hint.
- The endpoint accepts no path, file, firm, or configuration scope from the browser.

### Failure and atomicity

- Malformed JSON, schema violations, missing managed files, duplicate identities, and conflicting
  domains produce useful client-visible diagnostics and zero writes.
- An injected mid-materialization failure rolls back firms, profiles, identities, authorities,
  current pointers, and repository revision advancement.
- Existing artifacts, acquisition history, and observations are unchanged after success and
  failure cases.

### Compatibility

- Repeated successful reload preserves the current init-equivalent immutable-history behavior.
- Ordinary first and repeated admin startup still perform no materialization writes.
- Externally managed firm and source-profile edit APIs remain rejected.
- Existing Target Firms browsing, Pull Sources, SEC adapters, and transcript adapters remain
  compatible.
- Full repository validation passes.

## Verification Package

Provide:

- before/after operator workflow evidence;
- API request and structured response examples;
- proof that the implementation delegates to `prepare_firm_configuration`;
- proof that an edited discovery hint becomes current without server restart;
- proof that a later pull snapshots the new revision while an in-flight pull remains unchanged;
- transaction rollback evidence;
- proof that reload does not alter acquisition evidence or other durable subsystems;
- focused test commands and results;
- full `make validate` result;
- changed-file inventory and patch;
- final Git status, commit hash, and pushed branch.

## Acceptance Criteria

TASK-054 is complete when:

- the Target Firms page provides the explicit confirmed reload action;
- the action reloads the complete external firm-configuration set through the existing governed
  materialization path;
- successful reload is immediately visible to Target Firms and subsequent pulls without an admin
  restart;
- failures are actionable and cannot partially update repository state;
- ordinary admin startup remains read-only;
- configuration authority, immutable history, pull snapshots, acquisition evidence, and unrelated
  subsystem boundaries remain intact;
- unchanged-file revision creation is accurately disclosed and otherwise unchanged;
- focused tests and full validation pass;
- implementation and review evidence are committed and pushed on a task branch without merging.

## Required Architectural Status Summary

The completed review shall report the status and responsibility of:

- external firm-configuration authority;
- validation and materialization orchestration;
- immutable firm and source-profile projections;
- Target Firms operator workflow;
- Pull Sources profile snapshot boundary;
- retained limitations and the next architectural milestone.
