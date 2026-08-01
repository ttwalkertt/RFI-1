# TASK-054 Verification Report

## Result

TASK-054 is Complete. The Target Firms console can explicitly reload the complete external firm
configuration set through the same governed validation and materialization path as `rfi init`.
The browser gains no configuration-authoring, path-selection, per-firm, acquisition, or broader
initialization authority.

## Implementation and Boundary

The new fixed action is:

```http
POST /api/firm-configurations/reload
Content-Type: application/json

{}
```

The admin-server composition root retains the selected state path and owns one non-blocking lock
used only to prevent overlapping reload actions. After acquiring that guard, it calls
`prepare_firm_configuration(state)` directly. The existing loader validates the complete
`firm-config/*.firm-config.json` set, and the existing materializer publishes firm revisions,
source-profile revisions, SEC identities, configuration authorities, current pointers, and the
repository authority revision in one SQLite transaction.

`MaterializationResult` now carries the authority revision returned by
`RepositoryDatabase.advance_revision(connection)` inside that transaction. This avoids a
race-prone post-commit lookup and gives the API/UI one deterministic reference to the state created
by the reload.

The endpoint accepts only an empty JSON object. It cannot accept configuration content, paths,
directories, firm identifiers, or scope controls. Ordinary admin startup continues to call only
`validate_firm_configuration(state)`.

## Operator Workflow Evidence

The Target Firms heading includes **Reload Firm Profiles**. Confirmation states that unchanged
files may still create immutable firm and source-profile revisions and that acquisitions, retained
artifacts, observations, and historical evidence are not modified. Cancellation returns before
the API request. During the request the button is disabled and reads “Reloading Firm Profiles…”.
Success refreshes the firm list and selected current detail and reports counts plus the repository
authority revision; failure restores the button and reports the structured error.

Command:

```sh
make task054-proof
```

Result: PASS. The fixture proof performed the fixed API request against a running admin server,
without restart, and observed:

```json
{
  "before": {
    "repository_authority_revision": 1,
    "configured_hint_present": false
  },
  "response": {
    "status": "reloaded",
    "files": 1,
    "firms": 1,
    "profiles": 1,
    "external_identities": 1,
    "authority": "external-json",
    "repository_authority_revision": 2
  },
  "after": {
    "repository_authority_revision": 2,
    "configured_hint_first": true,
    "server_restarted": false
  }
}
```

## Concurrency and Pull Snapshot Evidence

A second reload request received while the first is blocked returns HTTP 409 with
`error_code=firm_configuration_reload_in_progress`. It does not enter validation or
materialization. The guard releases after success and failure, and a later reload succeeds.

The pull-isolation fixture blocks an earnings-transcript adapter only after Pull Workflow has
captured the current profile. While that acquisition remains blocked, reload completes normally,
proving there is no broad application or acquisition lock. The in-flight run retains its old
source-profile revision and old discovery hints. After the adapter is released, a subsequent pull
captures the newly current revision and the reloaded hint. New pull scheduling is therefore
affected only by the repository's existing atomic transaction boundary.

## Rollback and Preservation Evidence

Malformed JSON returns HTTP 400 with `error_code=firm_configuration_invalid` and an ordered
diagnostics array. An injected failure after projection writes but before transaction completion
leaves every firm revision, profile revision, identity, authority record, current pointer, and the
repository authority revision byte-for-byte equivalent at the relational snapshot boundary. A
later unmodified retry advances authority by exactly one and appends exactly one firm and one
profile revision, as though the failed attempt never occurred.

A retained-evidence fixture records a governed source, successful acquisition attempt, immutable
artifact, and observation before reload. Sources, attempts, observations, artifact metadata, and
the stored-byte digest are identical afterward. Existing TASK-041 regressions additionally retain
SEC workflow knowledge and reject edits to externally managed firm/profile records.

Repeated successful reloads preserve current `rfi init` behavior: each invocation advances the
repository authority revision and appends immutable firm and source-profile revisions even when
the JSON is unchanged. No no-op optimization was introduced.

## Focused Verification

Command:

```sh
make task054-test
```

Result: PASS, 73 tests. The target covers TASK-054 plus external configuration materialization,
consolidated Target Firms browsing and edit rejection, Pull Workflow and REST integration, SEC
adapter behavior, transcript hint projection, and transcript traversal semantics.

The ten direct TASK-054 tests cover UI confirmation/cancellation/in-progress markers, fixed API
scope, structured conflict and validation failures, exact authority revision, changed-hint reload
without restart, injected rollback/retry equivalence, repeated reload, startup write-freedom,
unchanged acquisition evidence, and old/new pull snapshot behavior.

## Full Validation

Command:

```sh
make validate
```

Result: PASS. The complete unit suite passed, followed by every acquisition demonstration, offline
provider proof, lint, format, type, import, documentation, design-baseline, and source-archive gate.

## Changed-File Inventory

- `src/rfi/firm_configuration.py`: returns the exact transaction authority revision in the existing
  materialization result.
- `src/rfi/admin/server.py`: adds the fixed reload action, reload-only guard, and structured
  configuration failure handling while delegating materialization unchanged.
- `src/rfi/admin/firms.html`: adds the confirmed, disabled-while-active operator workflow and
  refresh/result behavior.
- `tests/test_task054.py`: adds focused UI, API, concurrency, rollback, startup, preservation, and
  pull-snapshot acceptance evidence.
- `scripts/task054_reload_firm_profiles.py`: adds the deterministic no-restart API proof.
- `Makefile`: adds reproducible TASK-054 focused-test and proof targets.
- `docs/operator-guide.md`: documents the explicit reload authority and behavior.
- `TASKS.md`, this ticket, and `docs/design-baseline.json`: record completion and refresh governed
  roadmap metadata.
- `docs/TASK-054-review.md`: provides this review and Architectural Status Summary.

The commit-aware package contains the complete committed patch, machine-readable changed-file and
numstat inventories, Git identity/status metadata, validation logs, manifest, and integrity hash.

## Retained Limitations

- Successful reload deliberately creates revisions for unchanged files, matching `rfi init`.
- The reload conflict guard is process-local, consistent with the local single-operator admin
  surface. SQLite remains the cross-operation atomic write boundary.
- External JSON authoring, file watching, selective reload, and remote administration remain out
  of scope.

## Architectural Status Summary

- **External firm-configuration authority — Complete.** JSON remains externally authored and the
  browser remains read-only for managed firm and profile records.
- **Validation and materialization orchestration — Complete.** The UI action delegates to the
  existing complete-set loader and atomic materializer; no second implementation exists.
- **Immutable firm and source-profile projections — Complete.** Reload appends existing revision
  forms and advances identities, authorities, pointers, and authority revision transactionally.
- **Target Firms operator workflow — Complete.** Confirmation, cancellation, in-progress state,
  success refresh, exact authority revision, and actionable failures are present.
- **Reload concurrency — Complete.** Overlapping admin reloads are rejected by a reload-only guard
  that releases on all outcomes.
- **Pull Sources profile snapshot boundary — Complete.** In-flight pulls retain captured profiles;
  later pulls see the newly current revision without a broad acquisition lock.
- **Evidence preservation — Complete.** Acquisition attempts, artifacts, observations, knowledge,
  streams, and historical evidence stay outside reload authority.
- **Revision efficiency — Usable with limitations.** Unchanged files still create revisions by
  design. A likely next architectural milestone is change-aware or content-addressed no-op
  materialization under a separate task; TASK-054 does not implement it.
