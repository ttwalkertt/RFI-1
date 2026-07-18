# TASK-017 — Reusable Admin Preference Store and Remembered Firm Context

## Status

Complete

## Objective

Add a small, reusable admin-console preference facility that preserves non-authoritative operator interface state across page navigation and browser sessions.

The first required use is to remember the most recently selected firm on the source-profile page and restore that selection when the operator returns. The same preference mechanism shall also support the pull-sources page without introducing a separate page-specific persistence implementation.

This task must preserve the distinction between:

- disposable browser-local UI preferences;
- durable operator or application configuration;
- revisioned domain configuration such as firm source profiles;
- repository evidence and acquisition state.

The remembered selection must not modify a firm source profile, create a source-profile revision, alter repository state, or become part of acquisition authority.

## Context

The current local admin console supports navigating among firms on pages such as source profiles and pull sources. Returning to a page resets the selected firm rather than restoring the operator's previous context.

RFI-1 is presently a local, single-operator application. Browser-local persistence is therefore appropriate for lightweight interface preferences that:

- affect only presentation or navigation;
- do not need to be shared with the CLI;
- do not need to follow the repository state directory;
- do not participate in backup, replay, provenance, or audit semantics;
- are safe to discard if browser storage is cleared.

A generalized server-side configuration datastore is not justified by this requirement. The task should establish a narrow admin-preference boundary while explicitly leaving durable application settings for a later evidence-backed need.

## Architectural Intent

### UI preferences are not domain configuration

The selected firm is operator navigation context. It is not:

- part of the firm's source profile;
- a retrieval locator;
- an acquisition policy;
- repository metadata;
- evidence;
- a durable application setting.

Changing the selected firm must therefore remain outside source-profile revisioning and outside the repository-owned state model.

### Use browser-native persistence behind a bounded abstraction

Use browser-local storage suitable for the current local admin console, expected to be `localStorage`, behind a small reusable preference API.

Page code should not scatter direct storage calls or invent incompatible key names and serialization behavior. The preference boundary shall centralize:

- namespace and key conventions;
- serialization and deserialization;
- missing-value behavior;
- malformed or unavailable storage handling;
- removal or replacement of stale values;
- safe fallback behavior.

The implementation must remain understandable without introducing a front-end framework or a third-party state-management dependency.

### Restore only valid current context

A remembered firm identifier is advisory UI state. On page load, the console shall validate it against the currently available firm list before selecting it.

If the remembered firm is missing, malformed, no longer available, or inaccessible, the page shall:

1. fall back deterministically to the existing default-selection behavior;
2. remain fully usable;
3. clear or replace the stale preference as appropriate;
4. avoid presenting an error as though repository or domain state were corrupt.

### Preserve a future durable-settings boundary

The implementation and durable design record shall distinguish this browser-local preference facility from a future server-side settings service that may eventually be required for values that must:

- be shared between CLI and browser;
- follow the selected `--state` directory;
- survive browser-profile changes;
- participate in backup and restore;
- be validated as operational policy;
- be available to multiple operators or processes;
- contain protected or sensitive values.

TASK-017 must not preemptively build that future service.

## Required Outcomes

### 1. Reusable admin preference facility

Provide one reusable browser-side preference component or module used by the affected admin pages.

It shall provide, at minimum, clear operations equivalent to:

- read a preference with a deterministic fallback;
- write a JSON-compatible preference value;
- remove a preference;
- tolerate missing, malformed, blocked, or unavailable browser storage.

The concrete API, module placement, and script-loading approach are implementation decisions for Codex after inspection of the existing admin-console structure.

### 2. Stable preference namespace and ownership

Define and document a stable namespace for RFI-1 admin preferences.

Keys must make ownership and scope clear. The design shall explicitly decide whether the remembered firm is:

- a console-wide current-firm preference shared by source profiles and pull sources; or
- a page-specific preference for each page.

Prefer one console-wide firm context only if the current interaction model demonstrates that both pages represent the same operator concept. Otherwise use page-scoped keys. The decision must be documented and tested.

### 3. Source-profile firm restoration

The source-profile page shall:

- persist the operator's selected firm after a successful selection change;
- restore that firm after leaving and returning to the page;
- restore it after an ordinary browser refresh;
- validate the stored identifier against the current firm list;
- fall back safely when the preference is absent or stale;
- continue loading the correct source profile and revision history for the restored firm.

Selection restoration must not trigger a source-profile write or revision.

### 4. Pull-sources integration

Use the same preference facility on the pull-sources page.

Behavior shall be consistent with the chosen firm-context scope. If firm context is shared, navigation between source profiles and pull sources shall retain the same selected firm when that firm is available on both pages. If page-scoped, each page shall independently retain its prior valid selection.

No pull shall begin merely because a preference was restored.

### 5. Failure-safe behavior

The console shall remain functional when:

- browser storage is empty;
- the stored JSON is malformed;
- the stored value has an unexpected type;
- the stored firm no longer exists;
- storage access throws an exception;
- storage writes fail;
- the firm list is empty;
- page data loading fails independently of preference handling.

Preference failures shall not be elevated into repository, profile, or pull failures.

### 6. Explicit authority boundary

Document and, where practical, encode the rule that browser preferences are non-authoritative and disposable.

They must not be:

- read by acquisition or repository services;
- included in firm source-profile payloads;
- persisted under the RFI state directory;
- recorded in source-profile revision history;
- included in acquisition identity, replay, or provenance;
- treated as a secret store;
- required for correct server behavior.

### 7. Proportionate extension point

The preference facility should be capable of supporting later low-risk UI preferences such as filters, sort order, page size, selected tab, or collapsed panels.

Do not implement those additional preferences merely to demonstrate generality. One shared firm-context use across the affected pages is sufficient proof.

## Non-Goals

TASK-017 does not require:

- a generic server-side configuration datastore;
- SQLite or JSON application-settings persistence;
- environment or startup configuration management;
- secret or credential storage;
- user accounts or multi-user preferences;
- synchronization across browsers or devices;
- preference backup or restore;
- source-profile schema changes;
- repository schema changes;
- acquisition workflow changes;
- a front-end framework;
- a third-party state-management or configuration library;
- broad admin-console redesign;
- new firm-management behavior;
- persistence of form drafts or unsaved source-profile edits.

## Architectural Constraints

- Preserve existing source-profile revision and validation semantics.
- Preserve existing pull planning, execution, and result semantics.
- Keep preference state entirely outside repository and domain authority.
- Use a single reusable preference implementation rather than page-specific storage code.
- Avoid new production dependencies unless the existing repository architecture makes one unavoidable and the review record justifies it.
- Do not make server-rendered pages or APIs depend on browser preference availability.
- Do not allow malformed preference data to prevent page initialization.
- Do not silently select a firm that is not present in the current server-provided firm list.
- Do not perform source-profile writes or initiate pulls during restoration.
- Preserve current no-JavaScript or degraded-JavaScript behavior to the extent already supported; document any existing dependence rather than expanding scope.
- Keep preference keys and values free of secrets and unnecessary personal data.

## Acceptance Criteria

TASK-017 is complete only when all of the following are true:

1. A reusable admin preference boundary exists and is used by both source-profile and pull-sources page behavior.
2. Direct browser-storage access is centralized rather than duplicated across affected pages.
3. Preference keys use a documented RFI-1 namespace and scope.
4. Selecting a firm on the source-profile page is remembered across navigation and refresh.
5. Returning to the source-profile page restores the remembered firm when it still exists.
6. The restored firm's profile and history are loaded correctly.
7. Source-profile restoration creates no source-profile write and no new revision.
8. Pull-sources behavior uses the same preference mechanism and follows the documented shared or page-scoped firm-context decision.
9. Restoring a selection never starts a pull.
10. Missing, malformed, stale, unavailable, and write-failing storage cases fall back safely.
11. An empty firm list is handled without console failure.
12. Preference failure remains distinct from API, repository, source-profile, and pull failure.
13. No browser preference is stored under the RFI state directory or included in repository evidence.
14. No source-profile, acquisition, repository, or API authority contract is weakened.
15. Existing admin-console behavior and all prior tests continue to pass.
16. Focused automated tests cover preference serialization, restoration, stale values, malformed values, storage exceptions, and page integration.
17. Operator-facing proof demonstrates navigation and refresh behavior for at least two firms.
18. Documentation clearly distinguishes browser-local UI preferences from future durable application settings.
19. A complete, independently reviewable TASK-017 verification package is generated and validated.
20. Final Git branch, HEAD, staged, unstaged, untracked, and working-tree state are explicitly reported.

## Verification Expectations

Verification must include:

- focused tests for preference read, write, remove, namespacing, and fallback behavior;
- malformed serialized-value tests;
- unexpected-type tests;
- unavailable or exception-throwing storage tests;
- stale firm identifier tests;
- empty firm-list tests;
- source-profile page restoration tests;
- proof that restoration performs no `PUT` to a source profile;
- proof that restoration creates no profile revision;
- pull-sources page integration tests;
- proof that restoration performs no pull `POST`;
- navigation and refresh behavior tests or deterministic browser-equivalent tests;
- all existing project tests and quality gates;
- documentation and design-baseline validation;
- secret and sensitive-output scan;
- isolated-tree or clean-checkout-equivalent validation;
- review-package manifest and ZIP integrity validation.

Tests shall exercise production page scripts and server/API contracts rather than test-only substitutes that bypass the actual selection flow.

## Required Verification Package

Produce a complete TASK-017 review directory and ZIP under the repository's established review-package convention.

The package shall contain, at minimum:

- task ticket;
- executive summary;
- implementation summary;
- architecture decisions;
- alternatives considered;
- UI-preference authority-boundary record;
- preference namespace and key-scope decision;
- browser-storage failure model;
- future durable-settings boundary;
- changed-file inventory with rationale;
- cumulative task-scoped patch;
- relevant repository tree;
- exact Git branch, base, HEAD, staged, unstaged, untracked, and worktree state;
- exact focused-validation commands;
- complete raw focused-validation output;
- exact full-project validation commands;
- complete raw project-validation output;
- preference unit-test evidence;
- source-profile restoration evidence;
- no-profile-write and no-revision evidence;
- pull-sources integration evidence;
- no-implicit-pull evidence;
- stale, malformed, unavailable-storage, and empty-list failure evidence;
- operator navigation and refresh proof;
- secret and sensitive-output scan;
- machine-readable review manifest;
- package member checksums;
- ZIP checksum, member listing, and integrity evidence.

A passing summary without the raw evidence needed to independently verify behavior is insufficient.

## Documentation and Durable Design Record

Update repository documentation and create or revise an ADR if warranted.

The durable record shall explain:

- why selected-firm state is an interface preference rather than domain configuration;
- why browser-local storage is proportionate for the current local single-operator console;
- why a server-side generic configuration datastore was deferred;
- why source-profile revisioning must not capture navigation context;
- whether firm context is console-wide or page-scoped;
- how malformed and stale preference data is handled;
- what conditions would justify a future state-directory-backed settings service;
- which categories of data must never be placed in the preference store.

## Completion Record

Update this task ticket as the durable handoff record while preserving the original objective and requirements.

Add:

- implementation resolution;
- files changed with rationale;
- design decisions and alternatives considered;
- exact verification commands and results;
- operator-proof outcome;
- known limitations and deferred work;
- Architectural Status Summary.

The Architectural Status Summary shall report the status and boundaries of:

- admin preference facility;
- source-profile page firm context;
- pull-sources page firm context;
- source-profile revision authority;
- pull authority;
- repository and acquisition authority;
- future durable application settings;
- secret and credential storage.

## Codex Execution Constraints

- Work only within the RFI-1 repository and the prepared TASK-017 branch.
- Read the governing project documents, current admin-console scripts/templates, source-profile APIs, pull APIs, TASK-014 through TASK-016 completion records, and existing test/review-package conventions before designing changes.
- Treat this ticket as an architectural requirement, not as an implementation recipe.
- Prefer existing page and script conventions over parallel front-end infrastructure.
- Keep changes scoped to reusable UI preferences and remembered firm context.
- Do not introduce a generalized server-side settings subsystem.
- Do not commit, push, merge, delete branches, or perform repository cleanup unless explicitly instructed.
- Do not mark the task Done until every required verification artifact exists and every required validation passes.
- If the implementation reveals that browser-local persistence cannot satisfy the stated behavior without violating an established invariant, stop and report the conflict rather than widening scope silently.

## Implementation Resolution

TASK-017 is implemented as one dependency-free packaged browser module served by the existing
local administration server. `admin_preferences.js` owns the stable
`rfi.admin.preferences.v1` namespace, JSON serialization/deserialization, missing-value fallback,
value validation, stale/malformed removal, storage discovery, and exception-safe read, write, and
remove behavior. Source Profiles and Pull Sources contain no direct browser-storage access.

The selected firm is a console-wide context stored at
`rfi.admin.preferences.v1.current_firm`. Both pages use the same stable server-provided `firm_id`
concept in the adjacent configure-then-pull workflow, so page-scoped keys would create competing
contexts. Source Profiles gives a valid explicit URL `firm_id` precedence, then restores a valid
preference, then chooses the first canonical-name/ID-sorted firm. Pull Sources restores a valid
configured firm as the initial single selection. Empty lists select nothing. Every restored value
is checked against the page's current API response before use.

Restoration performs reads only. Profile publication remains an explicit PUT and pull initiation
an explicit POST. The production preference module is not read by Python services and preference
values never enter the state directory, source-profile payload/revisions, acquisition identity,
repository evidence, replay, or provenance.

## Files Changed with Rationale

- `src/rfi/admin/admin_preferences.js`: reusable preference and firm-context boundary.
- `src/rfi/admin/source_profiles.html`: valid shared-firm restore/persist around existing profile
  and history GET behavior.
- `src/rfi/admin/pull_sources.html`: valid shared-firm initial selection with no launch coupling.
- `src/rfi/admin/server.py`, `pyproject.toml`: serve and package the production JavaScript module.
- `tests/test_task017.py`, `tests/task017_browser_harness.js`: execute packaged production page
  scripts against real server/API contracts, including failure, empty-list, no-write, and no-pull
  assertions.
- `scripts/task017_admin_preferences.py`: deterministic two-firm navigation/refresh operator proof.
- `docs/decisions/0013-browser-local-admin-preferences.md`, `docs/admin-preferences.md`,
  `README.md`: durable decision, authority, failure, operations, and future-settings records.
- `scripts/generate_task017_review.py`, `Makefile`: focused/full/isolated validation and complete
  self-verifying TASK-017 evidence packaging.
- `scripts/check_baseline.py`: recognizes the new packaged production file.
- `TASKS.md`: records the authorized milestone as complete after explicit finalization approval.
- `tasks/TASK-017-admin-preference-store.md`: durable implementation and verification handoff.

## Design Decisions and Alternatives Considered

- Browser `localStorage` is proportionate for disposable state in the current local single-operator
  console. Cookies would unnecessarily involve server transport; URL state alone does not survive
  ordinary navigation; a framework or third-party manager adds no value at this scale.
- One console-wide key was selected over page-scoped keys because both pages express the same firm
  identity and operator context. The pull page remains multi-select; a checked firm becomes the
  latest context, while restoration selects only that firm and never launches.
- Invalid readable values are removed when possible, then deterministic fallback is used. Blocked
  storage or failed cleanup/write is harmless and never shown as repository/domain failure.
- A generic server settings datastore was deferred. It becomes appropriate only when a value must
  follow `--state`, be shared with CLI, participate in backup/restore, coordinate operators or
  processes, or become validated policy. Secrets require a separate protected facility.

## Verification Commands and Results

The exact complete outputs are retained in `.artifacts/review/TASK-017/validation/`.

- `PYTHONPATH=src .venv/bin/python -m unittest tests.test_task017 -v` — PASS, 3 focused
  production-script/server-contract tests.
- `PYTHONPATH=src .venv/bin/python scripts/task017_admin_preferences.py` — PASS; two firms,
  navigation, refresh, correct profile/history reads, byte-identical revision state, zero profile
  PUT, and zero pull POST.
- `PYTHONPATH=src .venv/bin/python -m unittest tests.test_task014 -v` — PASS.
- `PYTHONPATH=src .venv/bin/python -m unittest tests.test_task015 -v` — PASS.
- `git diff --check` — PASS.
- `.venv/bin/python scripts/check_docs.py` — PASS.
- `.venv/bin/python scripts/check_baseline.py` — PASS.
- `env -u RFI_SEC_USER_AGENT -u SEC_API_IO_API_KEY make validate` — PASS, including the complete
  project suite and all established proof, lint, format, type, import, docs, baseline, and build
  gates.
- Copied-tree validation without Git, state, artifacts, caches, or local environment contents —
  PASS for the full test suite, TASK-017 proof, quality policies, docs, and baseline.
- `.venv/bin/python scripts/generate_task017_review.py` — PASS; sensitive-output scan, manifest,
  member checksums, ZIP listing, ZIP checksum, and integrity proof all passed.

## Operator-Proof Outcome

The deterministic browser-equivalent proof executes the exact production module and inline page
scripts against a live local instance of the real administration server. It restores Western
Digital on Source Profiles, refreshes and reloads the same profile and history, changes shared
context to Seagate, and restores Seagate on Pull Sources. It also proves stale fallback, malformed
and unexpected values, storage exceptions/write failure, and empty firm lists. The source-profile
state tree is byte-identical before and after restoration; observed profile PUT, revision-creating
POST, and pull POST counts are all zero.

## Known Limitations and Deferred Work

- Preferences do not synchronize across browser profiles or devices and disappear when browser
  storage is cleared.
- Pull Sources can restore only firms present in its configured-firms response; no source profile
  is created merely to make a remembered firm available there.
- The local console remains unauthenticated and single-operator.
- Durable cross-interface settings, multi-operator preference identity, backup/restore, and secret
  storage remain deliberately unimplemented.

## Architectural Status Summary

| Subsystem | Status | Boundary after TASK-017 |
| --- | --- | --- |
| Admin preference facility | Complete | Disposable browser-local JSON preferences behind one packaged module; no server authority. |
| Source Profiles firm context | Complete | Valid shared context restores correct profile/history using GET only. |
| Pull Sources firm context | Complete | Valid shared configured firm restores as selection; launch remains explicit. |
| Source-profile revision authority | Complete, unchanged | Only explicit validated PUT publishes a revision. |
| Pull authority | Complete, unchanged | Only explicit POST initiates the shared workflow. |
| Repository/acquisition authority | Complete, unchanged | Browser preferences never enter state, evidence, identity, replay, or provenance. |
| Future durable application settings | Not started | Requires evidence for CLI/state/backup/multi-process or policy needs. |
| Secret and credential storage | Not started and explicitly excluded | Browser preference storage is never a secret facility. |

Architectural change: the console now has an explicit non-authoritative preference layer rather
than page-specific incidental state. Next milestone: gather operational evidence before adding
other low-risk UI preferences or authorizing any durable settings capability.
