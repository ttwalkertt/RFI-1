# TASK-028 — Linux Kernel Mailing-List Stream Workflow

## Status

Complete

## Purpose

Deliver the actual RFI-1 operator outcome for Linux kernel mailing-list intelligence:

> An operator can select a Linux kernel mailing list, define a bounded evidence scope, create the required durable configuration, retrieve and inspect a real bounded sample, and leave the repository ready for repeatable acquisition.

This task is not another incremental revision of the existing generic Streams form.

It must replace the current operator-facing sequence of separately configuring an “External Source” and then configuring a generic stream with one coherent, start-to-finish Linux kernel mailing-list workflow.

The existing source, stream, revision, acquisition, artifact, provenance, and repository contracts remain the underlying architecture. They must not be forced onto the operator as prerequisite concepts or low-level form mechanics.

---

## Problem Statement

The current administration experience exposes internal configuration structure rather than the operator’s intended task.

The operator is currently expected to understand and coordinate concepts such as:

- External Sources;
- Lore-specific source configuration hidden behind a generic source label;
- stream identity;
- artifact schema;
- governed-source references;
- revisions;
- enablement;
- validation;
- preview;
- refresh behavior; and
- execution eligibility.

The current Streams screen is not an acceptable foundation for the primary mailing-list workflow.

Observed defects include:

1. a required `stream_id` can block the form while being hidden under an advanced section;
2. the operator must configure a Lore source separately before creating the stream that actually uses it;
3. low-level repository identity and schema terminology dominate the normal path;
4. “New Stream” and “Refresh” provide no reliable operator-visible acknowledgement, result, or state transition;
5. a generic Refresh action does not explain what state is being reloaded or whether unsaved work is at risk;
6. placeholder examples are being used where persistent contextual explanation is required;
7. the operator cannot reliably predict what an action will do or verify what the system actually did;
8. validation and persistence concepts are presented before the operator has a coherent task model;
9. successful completion is not demonstrated by showing real mailing-list messages and thread context;
10. the workflow currently optimizes for the internal data model rather than the project’s actual acquisition goal.

These are functional product defects, not cosmetic preferences.

---

## Required User Outcome

Starting from an initialized RFI-1 repository, an operator who does not know the implementation history must be able to:

1. open a clearly named Linux kernel mailing-list area;
2. choose a known Lore archive or enter a supported Lore archive URL;
3. understand what mailing list will be used and whether it is reachable;
4. provide a human-readable stream name;
5. define a bounded starting point and optional supported relevance controls;
6. review the complete intended behavior before persistence;
7. create the required governed source and stream configuration through one operator action;
8. run a bounded live test against Lore;
9. inspect actual retrieved messages, including subject, sender, date, source link, and discussion/thread context;
10. distinguish clearly between validation, saving, testing, and later acquisition;
11. receive immediate and durable feedback for every action;
12. recover from ordinary errors without consulting source code or guessing at internal identifiers;
13. return later and understand the saved mailing-list stream and its readiness state.

The normal workflow must not require the operator to manually create, copy, or coordinate internal repository identifiers.

---

## Product Direction

### The Workflow Is the Product Surface

The primary application surface shall be centered on the operator task:

> Add and verify a Linux kernel mailing-list stream.

Acceptable navigation names include:

- **Linux Mailing Lists**
- **Kernel Mailing Lists**

The primary action shall use concrete language such as:

- **Add mailing list**
- **Create mailing-list stream**

Do not lead with “External Sources.”

Do not require the operator to visit a separate generic External Sources screen before the mailing-list workflow can succeed.

### Preserve the Architecture Behind the Workflow

RFI-1 may continue to persist distinct internal records for:

- governed external source;
- stream definition;
- immutable stream revision;
- acquisition/test run;
- retrieved artifacts;
- observations or memberships;
- provenance and source references.

The operator-facing workflow must coordinate those records through established public services and repository contracts.

Do not create a second persistence authority, browser-only configuration model, or mailing-list-specific shadow database.

### Task-Specific Experience, Not Generic Form Repair

This task shall not be satisfied by:

- rearranging the existing generic Streams fields;
- exposing more tooltips;
- adding placeholders;
- renaming the current External Sources form;
- adding a wizard shell around the same low-level fields;
- making only the `stream_id` visible;
- adding toast messages while retaining the two-screen workflow;
- documenting the current form more thoroughly;
- proving only fixture-backed service behavior;
- or claiming that the generic editor is “flexible.”

The required result is a coherent, concrete Linux kernel mailing-list acquisition workflow.

---

## Required Workflow

Codex shall design the exact presentation, but the delivered workflow must provide the following operator stages and outcomes.

### 1. Choose Mailing List

The operator can:

- select from a discoverable set of known Linux kernel Lore archives; or
- enter a supported `lore.kernel.org` mailing-list archive URL.

The interface must show a human-readable archive name and canonical URL.

The workflow must validate that the selected archive is structurally supported and reachable before claiming readiness.

Raw internal source IDs must not be the primary selector labels.

### 2. Name and Describe the Stream

The operator provides:

- a human-readable stream name;
- an optional description.

RFI-1 generates stable internal identity through a deterministic, visible, collision-safe policy.

The normal workflow must not require the operator to invent or understand `stream_id`, `source_profile_id`, artifact schema identifiers, or revision-row identifiers.

An advanced view may expose generated identities for inspection where useful, but hidden advanced state must never be the cause of an unexplained validation failure.

### 3. Define a Bounded Scope

The workflow must expose only the supported controls needed for a safe initial mailing-list evidence stream.

At minimum, provide:

- an explicit starting point or bounded initial selection;
- a hard maximum for the initial test/acquisition;
- supported subject or keyword criteria where already backed by production contracts;
- supported sender or participant criteria where already backed by production contracts;
- supported connected-discussion expansion controls where already backed by production contracts.

The default path must be safe and bounded.

The interface must not offer or imply unbounded Lore mirroring.

Do not expose arbitrary executable predicates, generic policy rows, raw JSON/YAML, or schema-level filter construction in the normal workflow.

### 4. Review Before Persistence

Before creation, show a concise operator review containing at least:

- mailing-list name;
- canonical Lore archive URL;
- stream name;
- bounded starting scope;
- active relevance controls;
- discussion-context behavior;
- hard limits;
- records that will be created;
- actions that will and will not occur.

The review must distinguish:

- validation;
- persistence;
- bounded live test;
- later normal acquisition.

No state may be persisted merely by entering the review stage.

### 5. Create and Test

Provide one clearly dominant action that creates the required durable configuration and performs the bounded verification flow.

The operator must see distinct progress states for:

- validating archive;
- creating or resolving governed source;
- creating stream revision;
- retrieving bounded sample;
- reconstructing or evaluating discussion context;
- storing evidence;
- completing verification.

A failure at any stage must be shown with:

- the stage that failed;
- a plain-language explanation;
- whether durable state was created;
- whether retry is safe;
- the available recovery action.

Do not report overall success if later stages fail.

Do not leave ambiguous partial state without explaining it.

### 6. Inspect the Result

Successful completion must show actual bounded evidence, not merely a green status.

At minimum, display:

- message subject;
- sender;
- source-effective date/time;
- canonical Lore link;
- message identity;
- direct-match versus context-only inclusion;
- thread or relationship context;
- retrieved message count;
- relationship count;
- truncation or incompleteness state;
- active bounds;
- whether the stream is ready for later acquisition.

The result must link into the existing artifact or evidence inspection experience through established repository read contracts.

---

## Interaction and Feedback Requirements

### Every Action Must Be Observable

Every actionable control must produce an immediate, meaningful state change.

At minimum, the application must provide:

- idle state;
- active/busy state;
- success state;
- failure state;
- inapplicable or no-change state where relevant;
- protection against duplicate submission;
- safe retry behavior.

A button that silently reloads data or silently does nothing is a defect.

### New/Clear Behavior

If the workflow provides a “New,” “Add another,” “Reset,” or equivalent action, it must:

- state what will be cleared;
- protect unsaved changes;
- visibly establish a new draft state;
- use deterministic defaults;
- acknowledge when the interface is already in an equivalent new state.

### Refresh/Reload Behavior

Do not provide an ambiguous generic **Refresh** action.

Any manual reload control must name the state it reloads, such as:

- **Reload mailing-list catalog**
- **Reload saved configuration**
- **Retry archive validation**

The control must explain the effect on unsaved work.

Where practical, lists should refresh automatically after successful creation or update.

### Unsaved, Saved, Tested, and Ready States

The interface must visibly distinguish:

- new unsaved configuration;
- valid but unsaved configuration;
- saved stream revision;
- saved but untested configuration;
- test in progress;
- tested successfully;
- tested with incomplete or truncated evidence;
- test failed;
- ready for later acquisition;
- not runnable and why.

State must be derived from authoritative application behavior, not browser-only assumptions.

---

## Context Help Requirements

TASK-027 established the repository-owned non-modal operator help system. This workflow must integrate with it rather than substitute placeholders for explanation.

### Persistent Field Help

Each meaningful input must have persistent adjacent guidance that explains, as applicable:

- what the field controls;
- why the operator might change it;
- whether it is required;
- its default behavior;
- its bounds or accepted format;
- its consequences for acquisition;
- how validation failures are corrected.

### Placeholder Policy

Placeholders may illustrate input syntax only.

They must not be the sole carrier of:

- required instructions;
- field meaning;
- constraints;
- default semantics;
- safety implications;
- persistence effects;
- recovery guidance.

Placeholder text disappears during entry and is not context help.

Codex must not treat faint sample values inside text boxes as satisfying help requirements.

### Non-Modal Workflow Help

Provide context links into the canonical operator guide for at least:

- choosing a Lore mailing list;
- bounded acquisition;
- direct matches and discussion context;
- generated repository identities;
- validation versus save versus test;
- interpretation of incomplete or truncated results;
- rerunning or revising a saved mailing-list stream;
- troubleshooting Lore connectivity.

The help content must describe the delivered workflow exactly.

---

## Validation and Error Requirements

Errors must be:

- operator-visible;
- field- or stage-specific;
- expressed in application terms;
- actionable;
- safe for display;
- consistent across browser and API behavior.

Unacceptable errors include:

- a hidden field reported as invalid without exposing the corrective action;
- raw stack traces;
- raw persistence errors;
- raw enum or schema diagnostics without operator translation;
- generic “Bad Request” responses;
- silent non-response;
- success messages when only validation succeeded;
- success messages when durable state or live proof failed.

At minimum, verify clear handling of:

- malformed Lore URL;
- unsupported host or archive shape;
- unreachable archive;
- nonexistent mailing list;
- generated identity collision;
- invalid date or bound;
- empty or impossible selection;
- no messages found;
- bounded result truncation;
- disconnected or incomplete discussion context;
- persistence failure;
- live retrieval timeout;
- repeated submission;
- reload with unsaved changes;
- restart after saved configuration.

---

## Architectural Requirements

The implementation must preserve:

- SQLite as the sole structured application authority;
- immutable content-addressed artifact storage;
- provenance and canonical source links;
- deterministic internal identity;
- governed source transport policy;
- stream revision history;
- bounded acquisition;
- connected-discussion invariants from TASK-023;
- generic stream execution and membership contracts from TASK-025;
- canonical stream normalization and validation contracts from TASK-026;
- repository-owned non-modal help from TASK-027;
- shared services between browser, CLI, and tests;
- atomic publication semantics;
- offline inspection and rebuild behavior;
- absence of credentials in browser-visible stream definitions.

Use established public contracts.

Do not make admin route handlers or browser JavaScript directly manipulate persistence structures.

Do not bypass the source or stream service merely because the current generic screens are unsuitable.

Do not weaken an invariant to make the workflow appear successful.

---

## Required Design Record

Add or update durable design documentation explaining:

1. why Linux kernel mailing-list acquisition is a first-class operator workflow;
2. why the generic source/stream decomposition remains internal architecture;
3. how the workflow coordinates source creation, stream revision, bounded test, and evidence inspection;
4. how generated stable identity works;
5. how safe retry and partial-failure behavior work;
6. how live Lore validation differs from fixture validation;
7. how context help is divided between persistent field guidance and non-modal workflow documentation;
8. which generic administration surfaces remain available and for whom;
9. why placeholders are not treated as help;
10. what remains deliberately deferred.

Update the task index, roadmap/baseline records, operator guide, and relevant ADRs according to repository conventions.

---

## Non-Goals

TASK-028 does not require:

- a generic external-source marketplace;
- arbitrary internet source configuration;
- non-Lore mailing-list providers;
- generic IMAP or mailbox ingestion;
- email sending;
- scheduled polling;
- background daemons;
- notifications;
- complete historical Lore mirroring;
- unrestricted archive crawling;
- arbitrary query languages;
- arbitrary executable filters;
- AI-based relevance classification;
- embeddings or semantic search;
- claim, position, or report generation;
- redesign of unrelated SEC or firm workflows;
- deletion of existing generic source or stream contracts;
- migration to another persistence engine;
- a second structured store;
- a graph database;
- a browser-only source catalog authority;
- replacement of the canonical YAML/CLI capabilities;
- broad visual redesign unrelated to this workflow.

Do not absorb unrelated cleanup into this task.

Record newly discovered out-of-scope work in the repository backlog according to existing policy.

---

## Acceptance Criteria

TASK-028 is complete only when all of the following are demonstrated.

### Primary operator workflow

1. A fresh initialized repository can open the Linux kernel mailing-list workflow directly.
2. The operator does not need to visit External Sources first.
3. The operator can choose a known Lore archive or enter a supported Lore URL.
4. The archive is validated visibly before readiness is claimed.
5. The operator provides a human-readable name without manually creating internal IDs.
6. RFI-1 deterministically generates collision-safe internal source and stream identities.
7. The operator can define a safe bounded initial scope using supported mailing-list controls.
8. The operator can review the complete intended behavior before persistence.
9. One explicit operator action creates all required durable configuration through established services.
10. The workflow performs a bounded live Lore test.
11. Successful completion displays real messages and discussion context.
12. The resulting source, stream revision, artifacts, and relationships survive restart.
13. The saved stream is usable by the existing stream/acquisition architecture.

### Usability and feedback

14. Every action has visible busy, success, failure, and no-change behavior as applicable.
15. No primary action silently does nothing.
16. No ambiguous generic Refresh action remains in the primary workflow.
17. Unsaved changes are protected from reload/reset actions.
18. Unsaved, saved, tested, incomplete, failed, and ready states are visually distinct.
19. No hidden advanced field can block normal completion without an exposed corrective path.
20. Raw internal IDs and artifact schema names are not required normal-path inputs.
21. Validation, persistence, test acquisition, and later execution are explicitly distinguished.
22. Error messages identify the failed stage and safe recovery action.

### Help and terminology

23. Every meaningful field has persistent contextual guidance.
24. Placeholders are used only as optional syntax examples.
25. No required semantics or instructions exist only as placeholder text.
26. The workflow links to correct non-modal help topics.
27. Application terms, operator guide terms, API behavior, and CLI terminology are consistent.
28. Help accurately explains side effects, bounds, partial failures, and retry behavior.

### Architectural preservation

29. Existing source, stream, revision, acquisition, artifact, provenance, and repository contracts remain authoritative.
30. No browser-only or mailing-list-specific shadow persistence model is introduced.
31. No artifact bytes are duplicated merely because the workflow coordinates multiple records.
32. Bounded acquisition and connected-discussion invariants remain intact.
33. Existing canonical YAML and CLI stream operations continue to work.
34. Generic stream and source capabilities remain available where appropriate without defining the primary operator experience.
35. No unbounded Lore import path is introduced.
36. Full repository validation passes without weakening or skipping existing tests.

### Verification package

37. A complete independent review package is produced.
38. The review package includes real-browser evidence and a gated live Lore proof.
39. The review package includes complete raw validation outputs, not only summaries.
40. Repository branch, diff, status, package integrity, and checksum evidence are complete.

---

## Verification Requirements

### 1. Focused Automated Verification

Provide focused automated coverage for at least:

- known-mailing-list catalog behavior;
- supported Lore URL parsing and normalization;
- unsupported host rejection;
- archive validation state;
- generated source identity;
- generated stream identity;
- collision handling;
- bounded defaults;
- date and limit validation;
- supported relevance controls;
- review-state construction;
- validation non-persistence;
- coordinated source-and-stream creation;
- transactional or explicitly recoverable partial failure;
- repeated submission/idempotency behavior;
- saved-state restart;
- bounded test invocation;
- real result projection;
- direct-match versus context-only labeling;
- truncation and incompleteness state;
- reset/new behavior;
- reload behavior with unsaved edits;
- busy/success/failure/no-change interaction states;
- persistent help content presence;
- context-help topic registration;
- placeholder-policy compliance for required instructions;
- preservation of TASK-023, TASK-025, TASK-026, and TASK-027 behavior.

Tests must verify operator-visible behavior and durable repository effects, not merely helper return values.

### 2. Real-Browser Proof

Using a fresh controlled state, capture a reproducible browser workflow that demonstrates:

1. direct navigation to the Linux mailing-list workflow;
2. no prerequisite visit to External Sources;
3. selection or entry of a real supported Lore archive;
4. visible archive validation;
5. generated identity shown as secondary information;
6. persistent field help visible before and after typing;
7. safe bounded defaults;
8. review before persistence;
9. exact visible behavior after the create/test action;
10. progress through each material stage;
11. actual retrieved message subjects and metadata;
12. direct-match and context-only evidence;
13. thread or relationship inspection;
14. truncation/incompleteness reporting;
15. saved and ready state;
16. restart and return to the saved configuration;
17. safe reset/new behavior;
18. safe reload/retry behavior;
19. one representative failure and recovery;
20. zero unexpected browser console warnings or errors.

Screenshots alone are insufficient. Include the procedure, visible states, relevant API calls, persisted effects, and results.

### 3. Gated Live Lore Proof

Run at least one bounded live proof against an actual Linux kernel Lore archive.

The proof must record:

- exact archive;
- normalized archive identity;
- exact operator selections;
- exact hard bounds;
- direct seed count;
- expanded/context count;
- persisted message count;
- relationship count;
- direct versus context-only breakdown;
- source links;
- truncation/incompleteness state;
- run status;
- retryability;
- repeated-run/idempotency outcome;
- restart inspection outcome.

The proof must remain small and bounded.

A fixture-only demonstration does not satisfy this task.

A live HTTP 200 without stored and inspectable evidence does not satisfy this task.

### 4. Negative Proof

Explicitly prove that:

- the operator cannot initiate an unbounded Lore archive mirror;
- hidden advanced identity is not required for normal completion;
- placeholders are not the only source of required help;
- ambiguous Refresh behavior is absent from the primary workflow;
- validation does not persist;
- review does not persist;
- failed live retrieval is not reported as success;
- partial durable state is either rolled back or clearly recoverable;
- browser code does not directly create persistence records;
- no second authority or shadow mailing-list store exists;
- disconnected evidence is not labeled as complete connected discussion;
- generic YAML import does not bypass governed-source or stream invariants.

### 5. Regression and Repository Validation

Run and capture:

- focused TASK-028 tests;
- relevant TASK-023 mailing-list tests;
- relevant TASK-025 stream tests;
- relevant TASK-026 configuration/YAML tests;
- relevant TASK-027 help tests;
- complete repository validation;
- lint;
- formatting;
- type checking;
- documentation checks;
- design-baseline checks;
- schema/migration checks;
- fixture/archive integrity checks;
- sensitive-output scan;
- `git diff --check`;
- isolated copied-tree or clean-checkout-equivalent validation.

No pre-existing test may be weakened, deleted, skipped, or rewritten merely to accommodate this task without explicit evidence and justification.

---

## Required Review Package

Produce a complete TASK-028 review directory and ZIP using the repository’s established review-package convention.

The package must contain at least:

1. task ticket;
2. completion report;
3. operator-workflow summary;
4. architectural summary;
5. design decisions and alternatives considered;
6. before/after workflow analysis;
7. page and interaction-state model;
8. generated-identity policy;
9. partial-failure and retry policy;
10. field-help inventory;
11. context-help topic mapping;
12. placeholder-policy audit;
13. changed-file inventory with rationale;
14. cumulative task-scoped patch or equivalent diff evidence;
15. focused automated test commands and complete outputs;
16. full repository validation command and complete output;
17. real-browser proof procedure and results;
18. screenshots or equivalent rendered evidence;
19. browser console and network evidence;
20. gated live Lore proof;
21. persisted source, stream, revision, run, artifact, and relationship evidence;
22. restart proof;
23. idempotency proof;
24. negative architectural and usability proofs;
25. documentation and baseline validation outputs;
26. sensitive-output scan;
27. isolated-tree validation;
28. repository branch, base, HEAD, staged, unstaged, untracked, and worktree state;
29. machine-readable review manifest;
30. package-member checksums;
31. ZIP integrity output;
32. SHA-256 checksum.

The package must be self-contained enough for an independent reviewer to determine:

- whether the actual operator goal was delivered;
- whether Lore works in a bounded live workflow;
- whether the workflow is understandable without internal implementation knowledge;
- whether every operator action provides trustworthy feedback;
- whether placeholders were improperly used as help;
- whether existing architecture and invariants were preserved;
- whether regressions were introduced.

A summary claiming success without the complete evidence above is insufficient.

---

## Codex Execution Constraints

Codex must follow these constraints exactly.

- Work only in the RFI-1 repository and the prepared TASK-028 branch.
- Read the governing project documents, TASK-023, TASK-025, TASK-026, TASK-027, current source/stream services, mailing-list contracts, admin-console behavior, operator guide, and review-package conventions before proposing changes.
- Treat this ticket as an outcome and architecture requirement, not permission to minimally patch the existing form.
- Do not start implementation until the current workflow has been traced end to end and the authoritative service boundaries have been identified.
- Do not declare the generic Streams screen “good enough.”
- Do not satisfy this task by adding placeholders, tooltips, renamed labels, or additional documentation to the current two-screen workflow.
- Do not require the operator to configure External Sources separately.
- Do not expose hidden required fields.
- Do not introduce ambiguous controls.
- Do not leave primary actions without explicit observable outcomes.
- Do not invent unsupported product behavior.
- Do not bypass established repository, source, stream, revision, acquisition, or artifact contracts.
- Do not add a second persistence authority.
- Do not weaken bounded-acquisition or connected-discussion invariants.
- Do not broaden scope into unrelated UI cleanup or future intelligence features.
- Do not use fixture success as a substitute for the required gated live Lore proof.
- Do not weaken, delete, skip, or rewrite existing tests merely to obtain a passing result.
- Do not mark the task Done until every acceptance criterion and verification requirement is supported by reviewable evidence.
- If the current architecture materially prevents the required operator outcome, stop and report the conflict with evidence rather than implementing a misleading workaround.
- Do not commit, push, merge, delete branches, clean the repository, or perform unrelated Git operations unless separately authorized by the operator.

Codex must be explicit about any requirement it believes cannot be met. Silence, substitution, or unilateral scope reduction is not acceptable.

---

## Completion Report Requirements

Codex’s final report must state:

1. the exact operator workflow delivered;
2. the exact navigation and primary action labels;
3. how the operator selects or enters a Lore archive;
4. how source and stream identities are generated and collisions handled;
5. how bounds and supported relevance controls work;
6. how validation, review, save, test, and later acquisition differ;
7. how coordinated source/stream persistence works;
8. how partial failure and retry work;
9. what real Lore archive was tested;
10. exact live proof counts and result status;
11. how actual messages and discussion context are inspected;
12. how persistent field help and non-modal workflow help are provided;
13. confirmation that placeholders are not used as required help;
14. confirmation that no separate External Sources prerequisite remains;
15. confirmation that no ambiguous primary Refresh behavior remains;
16. confirmation that every primary action has observable feedback;
17. confirmation that existing source, stream, YAML, help, artifact, and repository contracts remain authoritative;
18. all focused and full validation outcomes;
19. review directory and ZIP paths;
20. ZIP size, integrity result, and SHA-256 checksum;
21. branch, base, HEAD, staged, unstaged, untracked, and worktree state;
22. known limitations and deferred capabilities;
23. any departure from this ticket and its rationale;
24. explicit confirmation that no commit, push, merge, branch deletion, or cleanup was performed unless separately authorized.

---

## Definition of Done

TASK-028 is done only when a capable operator can begin with no preconfigured Lore source, use one concrete Linux kernel mailing-list workflow to create a bounded durable stream, test it against real Lore, inspect actual messages and connected discussion evidence, understand every state transition and failure, restart RFI-1, and return to a clearly saved and usable result.

The following are explicitly insufficient:

- another generic stream form;
- another External Sources prerequisite;
- a renamed version of the current screens;
- a placeholder-heavy form;
- a fixture-only proof;
- an HTTP connectivity check without inspectable evidence;
- a successful API test without a usable browser workflow;
- a green toast without durable state;
- a passing test suite without browser and live proof;
- or a review package lacking complete raw evidence.

The task is complete only when the actual mailing-list intelligence workflow works from start to finish and the verification package proves it independently.
