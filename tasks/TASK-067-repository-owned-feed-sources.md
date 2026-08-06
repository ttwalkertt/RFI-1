# TASK-067 — Repository-Owned Feed Sources and Feed-Driven Acquisition

## Status

Completed.

## Objective

Introduce repository-owned RSS and Atom feed sources as a governed discovery mechanism for RFI.

Feed sources shall be independently managed from firm configuration and may optionally be associated with one or more existing firms. Feed polling shall discover entries, submit their linked content through the existing acquisition pipeline, preserve durable unavailable-entry records when content cannot be acquired, support deferred manual fulfillment, expose durable run history using RFI’s existing expandable JSON instrumentation pattern, provide a cron-suitable CLI action, and provide an aggregate RSS export endpoint.

Artifact unavailability is a retained acquisition outcome, not a control-flow failure.

---

## Background

RSS and Atom provide a lightweight standardized discovery channel for sources such as:

- corporate engineering blogs;
- press releases;
- standards organizations;
- open-source projects;
- government agencies;
- technical publications;
- industry communities.

A feed is not a firm property. Some feeds may be associated with one or more firms, while others are independent.

A feed is also not the authoritative artifact. It is a repository-owned discovery source whose entries are submitted to the existing governed acquisition path.

---

## Governing Model

RFI shall preserve these distinctions:

- **Feed definition:** operator-owned configuration describing a discovery source.
- **Feed observation:** metadata observed for an entry during a poll.
- **Acquired artifact:** immutable bytes successfully retained through normal repository qualification.
- **Unavailable-entry tombstone:** durable evidence that an entry was observed but its linked artifact could not be retained.
- **Feed run:** durable instrumentation describing one polling invocation and its outcomes.
- **Firm association:** optional scheduling context causing a feed to be included when an associated firm is pulled.

The UI, CLI, firm-pull integration, and future schedulers shall invoke the same application-owned feed polling service.

---

## Functional Requirements

### 1. Repository-owned feed registry

1. RFI shall introduce a repository-owned feed registry.
2. Feed definitions shall not be stored inside external firm configuration files.
3. Reloading external firm configuration shall not overwrite, remove, or recreate feed definitions.
4. Feed definitions shall participate in normal repository persistence and revision semantics.
5. Feed identity shall remain independent of firm identity.
6. Deleting or retiring a feed definition shall not delete prior:
   - feed observations;
   - acquired artifacts;
   - tombstones;
   - provenance;
   - feed-run history.

### 2. Feeds operator tab

7. RFI shall provide a dedicated **Feeds** operator tab.
8. The page shall display configured feeds as a vertically scrolling stack of compact cards.
9. Each card shall use approximately two or three lines to show, at minimum:
   - feed display name;
   - publisher or feed URL;
   - enabled status;
   - associated firms, when any.
10. Each card shall provide **Edit** and **Delete** controls aligned on the right.
11. Selecting **Delete** shall open a confirmation dialog.
12. Canceling the confirmation dialog shall leave the feed unchanged.
13. A **+** button at the top of the page shall open the editor for a new feed.
14. Selecting **Edit** shall open the same editor populated with the existing definition.
15. The page shall provide access to:
   - feed polling;
   - feed-run history;
   - unresolved unavailable entries;
   - aggregate RSS export.

### 3. Feed editor

16. The feed editor shall support:
   - display name;
   - feed URL;
   - enabled or disabled state;
   - optional notes;
   - optional association with one or more existing firms.
17. Firm association shall use a multi-select control, preferably searchable.
18. A feed may be associated with:
   - no firms;
   - one firm;
   - multiple firms.
19. The operator shall not be required to identify RSS versus Atom.
20. RFI shall fetch, detect, and validate the supported feed format from the supplied URL.
21. Validation shall report actionable failures without discarding entered values.
22. The editor shall not expose adapter names, XML namespaces, GUID policy, request internals, or other implementation details.

### 4. Firm association semantics

23. The sole operational purpose of associating a feed with a firm shall be to include the feed when RFI pulls that firm’s data.
24. Pulling a firm shall poll every enabled feed associated with that firm.
25. A feed associated with multiple firms shall be polled no more than once within a single acquisition run.
26. A feed with no firm associations shall remain available for:
   - direct feed polling;
   - poll-all operations;
   - CLI polling;
   - external scheduling.
27. Adding or removing a firm association shall not alter prior artifacts, observations, tombstones, or provenance.
28. Firm association shall not imply that every entry in the feed belongs exclusively to that firm.
29. Feed entry URLs shall remain subject to existing source and acquisition restrictions.

### 5. RSS and Atom polling

30. RFI shall support RSS and Atom through one normalized feed-source abstraction.
31. Each poll shall fetch the current feed document and enumerate its visible entries.
32. RFI shall normalize available metadata including:
   - source entry identifier;
   - title;
   - canonical entry URL;
   - publication time;
   - update time;
   - author;
   - summary or description;
   - originating feed identity and URL.
33. RFI shall use the strongest available source identity:
   1. Atom entry ID;
   2. RSS GUID;
   3. canonical entry URL as fallback.
34. Publication time and feed position shall not independently determine entry identity.
35. Feed reordering shall not create duplicate acquisition work.
36. Disappearance from the current feed window shall not delete or invalidate prior observations.
37. Materially updated entries shall create a new observation and shall be handled through existing repository versioning and duplicate rules.
38. Polling shall retain sufficient evidence to explain what entry metadata RFI observed and when.

### 6. Feed-driven artifact acquisition

39. Each newly discovered or materially updated feed entry shall be submitted to the normal governed acquisition path.
40. The feed subsystem shall not bypass:
   - source restrictions;
   - URL policy;
   - qualification;
   - immutable storage;
   - duplicate detection;
   - metadata extraction;
   - repository validation.
41. A feed entry URL shall be treated as a discovered acquisition target, not automatically as trusted content.
42. When linked content can be acquired, RFI shall:
   - retain immutable artifact bytes;
   - extract supported metadata;
   - preserve the original entry URL;
   - preserve feed and entry identity;
   - preserve discovery and acquisition provenance;
   - expose the artifact through normal repository query and classification mechanisms.
43. Duplicate content shall use existing canonical identity and occurrence-provenance behavior rather than storing duplicate canonical bytes.

### 7. Non-blocking unavailable-entry tombstones

44. When a validly observed feed entry cannot be acquired, RFI shall create or update one durable unresolved tombstone.
45. An individual artifact-retrieval failure shall not interrupt:
   - the current feed;
   - remaining feeds;
   - a firm pull;
   - Pull All;
   - a CLI poll.
46. RFI shall continue processing all remaining selected entries and feeds.
47. Unresolved tombstones alone shall produce a completed or completed-with-unavailable-entries outcome, not a failed run.
48. A tombstone shall not falsely represent nonexistent bytes as a successfully acquired artifact.
49. Each tombstone shall retain, at minimum:
   - stable tombstone identity;
   - originating feed identity and URL;
   - source entry identifier;
   - entry title and URL;
   - publication and update times, when available;
   - author and summary, when available;
   - first-observed and most-recently-observed times;
   - acquisition-attempt history;
   - failure category and diagnostic reason;
   - retry eligibility or terminal status.
50. Repeated observation of the same unavailable entry shall update observation and retry history without producing uncontrolled duplicate tombstones.
51. Tombstones shall remain durable even if the entry later disappears from the publisher’s feed.
52. Tombstones shall be visibly and semantically distinct from successfully retained artifacts.

### 8. Unavailable-entry work queue

53. The Feeds area shall provide an operator-filterable unavailable-entry view.
54. The view shall support, at minimum:
   - unresolved;
   - fulfilled;
   - dismissed.
55. Each unresolved item shall provide:
   - **Open Source**;
   - **Retry**;
   - **Provide Artifact**;
   - **Dismiss**.
56. Operators may defer resolution indefinitely without preventing future polling, firm pulls, export, or repository use.
57. Dismissal shall remove an item from the active work queue without deleting its metadata, provenance, or failure history.
58. A dismissed item may later be restored or manually fulfilled.

### 9. Manual fulfillment

59. RFI shall allow an operator to manually fulfill an unresolved tombstone later at the operator’s convenience.
60. Manual fulfillment shall support:
   - upload of a local artifact file;
   - an operator-supplied alternate retrieval URL.
61. The operator shall not edit or replace the tombstone directly; the operator supplies candidate content intended to satisfy it.
62. Supplied content shall enter the same qualification, hashing, immutable-storage, metadata-extraction, duplicate-detection, and repository-validation path as automatically acquired content.
63. Before confirmation, RFI shall display the tombstone metadata and available candidate metadata for comparison.
64. Successful fulfillment shall:
   - retain or identify the canonical artifact;
   - link the artifact to the tombstone;
   - mark the tombstone fulfilled;
   - preserve all original failure evidence.
65. If supplied content duplicates an existing retained artifact, RFI shall link the tombstone to that artifact rather than duplicate canonical bytes.
66. Identity conflict shall fail closed with an actionable diagnostic.
67. A failed manual-fulfillment attempt shall leave the tombstone unresolved and preserve the attempt outcome.
68. Later automatic acquisition of the same content shall not create a second canonical artifact.

### 10. Polling entry points

69. RFI shall support feed polling through:
   - pulling an associated firm;
   - polling one selected feed;
   - polling all enabled feeds;
   - the cron-suitable CLI action.
70. All entry points shall invoke the same application-owned feed polling service.
71. UI, CLI, and firm-pull orchestration shall not implement independent feed-processing logic.
72. Overlapping feed-poll operations shall be rejected or safely serialized.

### 11. CLI action

73. RFI shall provide:

```text
rfi feeds poll [--state PATH] [--feed FEED_ID] [--json]
```

74. With no `--feed`, the command shall poll all enabled feeds.
75. With `--feed`, the command shall poll only the specified feed.
76. The command shall perform one polling pass and exit.
77. The command shall contain no internal recurrence or scheduler.
78. The command shall be suitable for cron, launchd, systemd timers, and direct operator use.
79. Human-readable and JSON output shall summarize:
   - run identity;
   - feeds selected;
   - feeds succeeded and failed;
   - entries observed;
   - new and materially updated entries;
   - artifacts retained;
   - tombstones created or updated;
   - acquisition requests created;
   - final run outcome.
80. One feed failure shall not prevent processing of other selected feeds.
81. Exit behavior shall distinguish invalid invocation or fatal run failure from a completed run containing ordinary per-feed or per-entry failures.

### 12. Durable feed-run history

82. Every feed-poll invocation shall create one durable feed-run record.
83. Feed-run history shall include runs initiated by:
   - the Feeds UI;
   - firm pull;
   - Pull All;
   - CLI;
   - external schedulers invoking the CLI.
84. Each run record shall retain, at minimum:
   - run ID;
   - trigger or invocation source;
   - selected feed IDs;
   - associated firm context, when applicable;
   - start and completion times;
   - final outcome;
   - feed counts;
   - entry counts;
   - artifact outcomes;
   - tombstone outcomes;
   - bounded diagnostics.
85. Run outcome shall distinguish, at minimum:
   - completed;
   - completed with unavailable entries;
   - partial;
   - failed;
   - canceled, when cancellation is supported by the invoked path.
86. Feed-run history shall use deterministic newest-first ordering.
87. The operator surface shall retain a bounded recent history consistent with the existing acquisition-history presentation.
88. Each history entry shall provide a concise one-line or compact summary.
89. Expanding a history entry shall expose the complete structured run result as formatted JSON.
90. The expandable JSON presentation shall reuse the instrumentation and visual convention already used by normal firm pulls rather than introducing an unrelated feed-specific diagnostics UI.
91. The structured JSON shall include enough detail to review:
   - each selected feed;
   - fetch and parse outcome;
   - discovered entry counts;
   - duplicate or unchanged counts;
   - acquisition submissions;
   - retained artifacts;
   - unavailable-entry tombstones;
   - bounded failure diagnostics;
   - run termination reason.
92. Structured run results shall be generated from the same authoritative application result used by the CLI and API surfaces, not reconstructed independently by the browser.
93. Diagnostics shall be bounded and shall not expose internal filesystem paths, secrets, cookies, credentials, or unbounded source payloads.
94. Feed-run history shall survive restart and shall not depend on in-memory process state.

### 13. Aggregate RSS export endpoint

95. RFI shall provide a read-only aggregate RSS 2.0 endpoint:

```text
GET /api/feed-items.rss
```

96. The endpoint shall operate entirely from durable repository state.
97. Rendering the endpoint shall perform no live source polling.
98. The export shall include feed-entry observations across configured feeds according to a deterministic bounded policy.
99. Both successfully acquired and unavailable entries shall be representable.
100. Unavailable entries shall be marked clearly and shall not imply successful artifact acquisition.
101. Exported items shall use standard RSS fields where available and stable RFI identity or provenance extensions where necessary.
102. The endpoint shall return:

```text
application/rss+xml; charset=utf-8
```

103. The Feeds page shall provide an **Export All as RSS** action linked to the endpoint.

---

## Required UI Outcomes

The completed operator surface shall provide:

- a dedicated Feeds tab;
- a scrolling card stack;
- a top-level **+** action;
- compact create/edit controls;
- delete confirmation;
- optional multi-firm association;
- feed polling controls;
- recent feed-run history;
- expandable structured JSON results consistent with firm-pull instrumentation;
- unavailable-entry filtering;
- manual artifact fulfillment;
- aggregate RSS export.

---

## Explicit Non-Goals

This task shall not introduce:

- automatic feed discovery from arbitrary home pages;
- OPML import or export;
- authenticated feeds;
- arbitrary custom request headers;
- cookie management;
- JavaScript-rendered feed discovery;
- per-feed internal scheduling;
- editing external firm configuration files;
- automatic firm inference from domains;
- changes that weaken existing acquisition restrictions;
- a new diagnostics model unrelated to normal firm-pull instrumentation.

---

## Required Invariants

- Feed configuration is repository-owned and independent of firm configuration.
- Firm association affects pull inclusion only.
- Feed discovery never grants acquisition authority.
- All linked content remains subject to normal acquisition policy.
- Successfully acquired content has immutable retained bytes.
- Unavailable content is represented by a durable tombstone, not fabricated artifact bytes.
- Individual entry failures do not interrupt the pull.
- Manual fulfillment preserves history and uses normal qualification.
- UI, CLI, and firm pulls share one application service.
- Feed-run JSON is the durable authoritative result, not a browser-generated approximation.
- Prior artifacts, observations, tombstones, and run history survive feed edits, retirement, or deletion.

---

## Required Verification

The implementation review package shall demonstrate:

1. Creation of a feed through the **+** editor.
2. Editing a feed and changing its optional firm associations.
3. Delete confirmation and preservation of prior repository facts.
4. Successful validation and polling of representative RSS and Atom feeds.
5. Pulling a firm and polling its associated feeds exactly once.
6. Polling a feed with no firm association through the UI and CLI.
7. Successful linked-artifact acquisition with extracted metadata and feed provenance.
8. Retrieval failure creating a durable unresolved tombstone while the run continues.
9. A completed-with-unavailable-entries result rather than a failed pull.
10. Unavailable-entry filtering and dismissal behavior.
11. Manual fulfillment through local upload.
12. Manual fulfillment through an alternate URL.
13. Duplicate fulfillment linking to existing canonical bytes.
14. Failed or conflicting fulfillment preserving the unresolved tombstone.
15. `rfi feeds poll` human-readable output.
16. `rfi feeds poll --json` structured output.
17. A practical cron invocation using absolute paths.
18. Durable feed-run history across restart.
19. Compact feed-run summary presentation.
20. Expandable formatted JSON results matching the normal firm-pull instrumentation model.
21. JSON evidence covering feed, entry, artifact, tombstone, and termination outcomes.
22. Aggregate RSS export returning valid RSS 2.0.
23. Export behavior for both fulfilled and unavailable entries.
24. Overlap rejection or serialization.
25. Focused tests for feed registry, polling, identity, firm association, tombstones, fulfillment, CLI, history, and export.
26. Full repository validation passing.
27. A complete review package containing:
    - UI screenshots;
    - representative expandable JSON;
    - CLI transcripts;
    - API response examples;
    - persistence and restart evidence;
    - focused and full validation results.

---

## Review Questions

Before implementation, reviewers should specifically assess:

1. Whether feed definitions should be retired rather than physically deleted.
2. The bounded retention depth for feed-run history.
3. The bounded item count for aggregate RSS export.
4. Whether manually supplied alternate URLs must satisfy the original source authority or may be accepted with explicit operator provenance.
5. Whether a materially updated feed entry should trigger immediate reacquisition when a canonical artifact already exists.
6. Whether unresolved tombstones should be included in ordinary repository search results or only in the unavailable-entry work queue.
7. Whether feed XML bytes themselves should be retained as immutable acquisition evidence or whether normalized observations plus run diagnostics are sufficient.

---

## Completion Record

Completed on 2026-08-06 on `codex/task-067-repository-feed-sources`.

### Material implementation decisions

1. Delete is implemented as an appended disabled, retired revision. It never physically removes
   a feed or its observations, artifact links, tombstones, provenance, or run history.
2. Feed-run history retains the newest 100 authoritative application results in deterministic
   order.
3. Aggregate RSS exports at most 200 current feed-entry observations and never polls a source
   while rendering.
4. A manually supplied alternate URL may use a different public host when the operator explicitly
   supplies it. The URL must remain credential-free HTTP(S), the candidate retains operator and
   alternate-URL provenance, and normal repository qualification still applies.
5. A materially changed normalized entry is reacquired immediately. Repository content identity
   decides whether the resulting bytes are new or an existing canonical duplicate.
6. Unresolved tombstones are exposed only through the unavailable-entry queue and RSS status
   projection, not as fabricated artifacts in ordinary repository search.
7. Raw feed XML is not retained as an artifact. Durable normalized observations and bounded
   fetch/parse diagnostics are the feed-discovery evidence; linked content is the governed
   artifact.

### Clarified semantics and bounded deviations

- `completed_with_unavailable` is a successful feed-run outcome and does not degrade a containing
  firm pull. A feed-document fetch or parse failure makes the feed run partial while other feeds,
  entries, and firms continue.
- Feed-run JSON is persisted by the application and returned unchanged to UI, API, and CLI
  projections. A feed run inside a firm pull has one `parent_pull_run_id` and is embedded once in
  the containing pull result rather than copied into parallel instrumentation.
- An entry acquisition is submitted through a governed source identity derived from the feed
  revision, stable entry identity, and material observation hash. This prevents an acquisition
  checkpoint from suppressing sibling entries or material updates without creating a second
  artifact path.
- No functional requirement was removed and no explicit non-goal was implemented. Fixed retention
  and export limits are bounded repository policy rather than new operator configuration.

### Implemented behavior

- **Operator:** dedicated Feeds navigation and compact card stack; shared add/edit editor with RSS
  and Atom validation; searchable optional multi-firm association; retirement confirmation;
  per-feed and Poll All actions; expandable durable run JSON; unavailable queue filters and
  retry/dismiss/restore actions; upload and alternate-URL fulfillment; aggregate RSS export.
- **API:** feed registry validation and revision endpoints, polling, run history, unavailable work
  queue actions, manual fulfillment, and `GET /api/feed-items.rss` with the required RSS media type.
- **CLI:** single-pass `rfi feeds poll`, optional `--feed`, stable human output, authoritative
  `--json`, and exit semantics suitable for an external scheduler such as cron.
- **Persistence:** schema version 16 adds revisioned definitions and firm associations, immutable
  observations, current entry selectors, canonical artifact links, durable tombstones and attempt
  history, and bounded feed runs. Migration is additive and restart-safe.
- **Repository:** automatic feed acquisitions reuse `AcquisitionEngine` and
  `AcquisitionRepository`; manual candidates reuse public repository ingress and qualification.
  Immutable storage, identity, deduplication, metadata, observations, and provenance remain owned
  by the existing repository.

### Verification results

- Focused: `make task067-test` — 13 tests passed, including deterministic RSS, Atom, unavailable,
  malformed, materially updated, duplicate, firm-pull, UI/API, CLI, restart, RSS export, and manual
  fulfillment scenarios.
- Full: `make validate` — 677 tests passed; lint, format, type, import, docs, design-baseline,
  source-archive build, and integrity validation passed.
- Live smoke: bounded parsing succeeded for NASA public RSS (10 visible entries) and CPython GitHub
  Atom (20 visible entries) on 2026-08-06. Live evidence is diagnostic and does not replace the
  deterministic fixture suite.
- Restart and persistence, CLI transcripts, API examples, authoritative feed-run JSON, valid RSS
  2.0, schema evidence, manual fulfillment, and the required operator screenshots are included in
  the generated review package.

### Review package

- Directory: `.artifacts/review/TASK-067/`
- Archive: `.artifacts/review/TASK-067-review.zip`
- Architectural completion report: `docs/TASK-067-review.md`
