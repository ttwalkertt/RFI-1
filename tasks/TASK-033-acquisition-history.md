# TASK-033 — Compact Acquisition History

## Status

Ready

## Objective

Replace the selected mailing-list stream’s single-run **Latest Acquisition Summary** presentation with a compact **Acquisition History** that preserves and displays the 50 most recent acquisition runs.

The resulting history must make repeated acquisitions easy to scan without expanding the operator console vertically.

## Execution Context

This task will be implemented independently on two already-created branches:

- `task-033-openai`
- `task-033-glm`

For each attempt, assume:

- the correct branch already exists and is checked out;
- this task ticket is already committed and pushed on that branch;
- branch creation, branch switching, rebasing, merging, and pushing are out of scope;
- the implementation should be committed to the current branch when complete.

The two attempts must remain independently reviewable and comparable.

## Current Behavior

On the Linux Mailing Lists operator page, the selected stream contains a multi-line card labeled **Latest Acquisition Summary** / **Last acquisition summary**. It presents only the most recent acquisition run, including acquisition time, completion/status information, direct-message count, context-message count, and explanatory text. The current layout is illustrated in the supplied operator-console reference image. fileciteturn0file0

## Required Behavior

### 1. Rename the section

Change the user-facing section title from **Latest Acquisition Summary** or **Last acquisition summary** to:

> **Acquisition History**

Remove obsolete user-facing wording that implies the section contains only one run.

### 2. Retain the 50 most recent entries

The selected stream must expose the 50 most recent acquisition-run records available to the application.

Requirements:

- retain no more than 50 history entries per stream;
- order entries newest first;
- when a 51st entry is added, discard the oldest retained entry;
- preserve history across application restart using the project’s existing durable state mechanism;
- do not reinterpret, merge, or synthesize separate acquisition runs;
- do not change acquisition execution, run outcome semantics, evidence retention, repository coverage, queue behavior, or terminal-history behavior.

If the existing persistence layer already retains suitable run records, reuse it rather than introducing a second source of truth.

### 3. Render each acquisition as one compact line

Render each retained acquisition entry as a single visual row. A row may wrap only under genuinely constrained viewport width; it must not be designed as a multi-row detail card.

Each row must communicate, using existing canonical values where available:

- acquisition date and time;
- terminal run result or status;
- boundary/completeness classification;
- direct-message count;
- context-message count.

Use concise labels and existing visual/status conventions. The design must remain readable at the project’s supported desktop viewport and must not require expanding an entry to understand these fields.

### 4. Empty and short-history states

- With no completed acquisition records, show a clear empty state under **Acquisition History**.
- With fewer than 50 records, show all available records.
- The page must remain functional while an acquisition is queued or running.

## Scope Boundaries

### In scope

- the durable representation or bounded retrieval of acquisition-run history, if needed;
- server/API projection changes needed to expose the history;
- the Linux Mailing Lists operator-console rendering for this section;
- focused automated tests;
- concise operator-facing documentation only if existing documentation describes the replaced single-run behavior.

### Out of scope

- changes to acquisition algorithms or source adapters;
- changes to message, discussion, relationship, or artifact retention;
- changes to stream-health or repository-coverage calculations;
- changes to fetch-queue or terminal-history semantics;
- pagination, filtering, search, sorting controls, expansion panels, or a separate history page;
- redesign of unrelated cards or navigation;
- schema migrations unrelated to retaining or projecting the acquisition history;
- generalized UI component refactoring unless directly necessary for this task;
- dependency upgrades or unrelated cleanup.

## Compatibility and Data Rules

- Existing persisted state must continue to load.
- If legacy state contains only the prior latest-run representation, degrade safely: show the available record and begin accumulating bounded history without corrupting or rejecting the state.
- Preserve canonical status and count meanings; presentation changes must not alter domain semantics.
- Do not derive history from process-local queue events when durable acquisition-run records are available.
- Avoid duplicating durable run data solely for the UI unless the repository’s current architecture requires an explicit projection.

## Implementation Guidance

Locate the existing end-to-end path for the current latest-run summary before changing code:

1. durable run record or ledger;
2. state/repository query or projection;
3. API/view model;
4. operator-console template/component;
5. relevant tests and fixtures.

Make the smallest coherent change across that path. Prefer an explicit bounded-history contract over UI-only truncation, so the 50-entry invariant is independently testable.

Do not hard-code mock history in the UI.

## Acceptance Criteria

The task is complete only when all of the following are true:

1. The selected-stream section is titled **Acquisition History**.
2. The obsolete latest-summary title no longer appears in the applicable UI.
3. Each acquisition run is represented by one compact row containing the required date/time, result/status, completeness/boundary classification, direct count, and context count.
4. Rows are ordered newest first.
5. At most 50 entries are returned/rendered per stream.
6. Adding a 51st run retains the newest 50 and removes the oldest.
7. History survives restart through the existing durable-state path.
8. Existing state with zero, one, or fewer than 50 records renders correctly.
9. Existing acquisition, queue, stream-health, repository-coverage, and evidence behavior remains unchanged.
10. The full validation suite passes.

## Required Tests

Add or update automated tests at the appropriate layers. At minimum, prove:

### Domain/persistence or projection

- zero history entries;
- one history entry;
- multiple entries returned newest first;
- exactly 50 entries retained/returned;
- insertion of a 51st entry removes only the oldest;
- histories are isolated by stream;
- history survives save/reload or repository reopen;
- legacy state containing only the previous latest-run representation still loads safely, where applicable.

### API/view model

- the selected stream exposes the bounded history collection;
- required row fields preserve their canonical values;
- no obsolete single-summary contract remains unless retained temporarily for documented compatibility.

### UI

- **Acquisition History** is rendered;
- obsolete latest-summary wording is absent;
- zero-entry empty state renders;
- one and multiple history rows render;
- a representative row contains all required fields;
- no more than 50 rows render;
- newest-first order is visible in rendered output;
- queue/running-state rendering remains intact.

### Regression

Run the existing focused mailing-list/operator-console tests and the repository’s full validation command.

## Required Manual Review

Perform a live operator-console review using representative persisted data.

Capture evidence for these cases:

1. **Empty history** — heading and empty state.
2. **Single entry** — one compact row with every required field.
3. **Several entries** — clear newest-first scanability.
4. **More than 50 generated entries** — exactly 50 visible, with the oldest excluded.
5. **Restart** — the same retained history remains after stopping and restarting the application.
6. **Concurrent activity** — queued or running acquisition activity does not break or replace the durable history display.

Review the page at the project’s normal desktop viewport and at one narrower supported width. Confirm that each entry is designed as one row and that any wrapping is responsive rather than a return to the previous multi-line card layout.

## Verification Package

Before committing, produce a concise verification package in the repository’s normal review-artifact location. Include:

- branch name and final commit SHA;
- changed-file list;
- short implementation summary;
- exact focused-test commands and complete outputs;
- exact full-validation command and complete output;
- test counts;
- before/after screenshots at the normal desktop viewport;
- screenshots or rendered evidence for the empty, multi-entry, 50-entry, and restart cases;
- a brief statement confirming that acquisition semantics and unrelated operator-console sections were not changed;
- `git status --short` after the commit;
- any assumptions or limitations.

Do not include generated caches, local state databases, credentials, or unrelated artifacts in the commit.

## Completion Report

The final response must state:

- commit SHA;
- files changed;
- where the 50-entry bound is enforced;
- how persistence and legacy-state compatibility were handled;
- focused and full validation results;
- manual-review evidence produced;
- verification-package path;
- any deviations from this ticket.

## Comparison Discipline

Because this task is being executed by two models, do not broaden scope or add optional features. Record noteworthy design choices and assumptions in the completion report, but do not modify this ticket or the scoring criteria during implementation.
