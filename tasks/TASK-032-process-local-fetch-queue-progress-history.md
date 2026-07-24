# TASK-032 — Process Local Fetch Queue Progress, Timestamps, and Durable Bounded History

## Status

Complete

## Purpose

Improve the Linux Mailing Lists operator experience by making the **Process Local Fetch Queue** understandable while work is running and useful after work completes.

This task must deliver three related outcomes:

1. occasional, meaningful progress updates from the running mailing-list fetch;
2. timestamps for displayed queue and history activity; and
3. bounded terminal fetch history that survives application restart.

The mailing-list fetch execution queue remains process-local. Queued and running fetch requests do not need to survive a process crash or server restart.

---

## Problem Statement

The current Process Local Fetch Queue provides reliable single-worker execution and basic lifecycle events, but its operator-facing behavior is incomplete.

Current behavior includes:

- process-local queued and running job state;
- FIFO execution;
- duplicate suppression for queued or running jobs for the same stream;
- cooperative bulk cancellation;
- lifecycle events such as `queued`, `started`, `completed`, `failed`, `cancelled`, and `abandoned`;
- browser polling of `GET /api/linux-mailing-lists/fetches` every 1.5 seconds.

Observed limitations include:

1. a running fetch emits `started` and then remains silent until terminal completion;
2. long-running fetches provide no indication of which bounded acquisition window is being processed;
3. displayed activity lacks consistent operator-visible timestamps;
4. terminal jobs and events are retained only in process-local memory;
5. useful recent fetch history is lost when the application restarts;
6. the operator cannot distinguish a stalled fetch from one that is progressing normally;
7. persisting the entire execution queue would add unnecessary durability and recovery complexity for mailing-list fetch requests.

These are operator-observability defects, not a requirement for a general durable task system.

---

## Required User Outcome

An operator using the Linux Mailing Lists area must be able to:

1. see which fetch is queued and which fetch is running;
2. receive occasional meaningful progress updates while a fetch remains active;
3. see when each queue state or progress update occurred;
4. distinguish queued, running, completed, failed, cancelled, and abandoned work;
5. review a bounded recent history of terminal fetches;
6. restart RFI-1 and still see recent terminal fetch history;
7. understand that queued or running fetch work is process-local and is not resumed after restart;
8. continue using the existing queue controls and browser polling behavior without learning a new execution model.

The display must remain concise enough to support routine operator use rather than becoming a raw event log.

---

## Product Direction

### Preserve the Process-Local Execution Model

The Process Local Fetch Queue remains the execution authority for Linux mailing-list fetch requests.

Keep process-local:

- pending FIFO work;
- current running-job identity;
- worker thread and synchronization;
- cancellation signal;
- duplicate suppression for active work;
- active job progress state.

Do not turn this task into a durable or resumable job system.

### Persist Operator History, Not Pending Work

Use the existing SQLite state database to retain bounded terminal job summaries and bounded display events needed for operator scrollback.

Do not introduce:

- a second database;
- a shadow persistence authority;
- durable pending-job claims;
- restart recovery or automatic re-enqueue;
- exactly-once or at-least-once task execution semantics.

### Use the Existing Polling Path

The browser already polls the queue snapshot every 1.5 seconds.

Progress and timestamps must flow through the existing:

- worker thread;
- queue state;
- queue snapshot;
- REST endpoint; and
- browser polling path.

Do not add WebSockets, server-sent events, an additional worker, or another polling mechanism.

---

## Required Behavior

### 1. Running-Job Progress

Extend `LinuxMailingListWorkflowService.fetch_up_to_date(...)` with an optional progress-reporting contract.

Requirements:

- The progress callback must be optional and backward-compatible.
- Progress must be reported at meaningful acquisition-window boundaries.
- The existing approximately 31-day workflow window is the expected reporting boundary.
- Do not emit per-message progress.
- Do not require an exact total-window count if determining it is not already cheap and deterministic.
- Progress reporting must be best-effort and must never determine acquisition success or failure.
- An exception while publishing progress must not fail the fetch.

The progress value should be typed and contain only operator-relevant fields. Codex shall determine the exact type, but it should be equivalent in intent to:

- phase;
- human-readable message;
- current window start;
- current window end;
- completed window count, when available;
- update timestamp.

Avoid an unrestricted free-form payload unless existing project conventions require it.

### 2. Queue Integration

`MailingListFetchQueue._work()` must pass a progress callback to the workflow.

The callback must:

- update only the currently running job;
- acquire the queue’s existing synchronization primitive before mutating shared state;
- update the running job’s latest progress/status fields;
- preserve the running job’s identity and lifecycle state;
- optionally emit a bounded `progress` queue event;
- coalesce or suppress redundant updates;
- avoid blocking acquisition for unnecessary work.

The queue must not emit an unbounded event for every internal operation.

### 3. Timestamps

Expose consistent timestamps for all displayed queue activity.

At minimum, the operator display must show timestamps for:

- queued;
- started;
- latest progress update;
- completed;
- failed;
- cancellation requested;
- cancelled;
- abandoned.

Use existing timestamp fields where they already represent the event correctly. Add only the fields necessary to provide unambiguous display behavior.

Timestamp requirements:

- store authoritative timestamps in a consistent machine-readable format;
- return timestamps through the REST snapshot;
- render them consistently in the operator console;
- include date and time where entries may survive beyond the current day;
- make timezone treatment explicit and consistent with existing RFI conventions;
- do not derive durable event times solely in browser JavaScript.

### 4. Bounded Durable Terminal History

Persist recent terminal job summaries in the existing SQLite state database.

Terminal states include:

- completed;
- failed;
- cancelled;
- abandoned.

The persisted summary must contain enough information to recreate the operator display without retaining unnecessary internal or sensitive data.

At minimum, preserve as applicable:

- job identity;
- stream identity;
- human-readable stream name;
- terminal state;
- final message;
- queued timestamp;
- started timestamp;
- finished timestamp;
- terminal result summary already considered safe for display;
- relevant final progress/window context where useful.

Do not persist pending or running jobs as resumable work.

### 5. Bounded Durable Event Scrollback

Persist the bounded queue-event history required by the operator display.

Requirements:

- events must retain sequence/order information;
- events must have authoritative timestamps;
- terminal and selected progress events may appear in scrollback;
- duplicate or overly frequent progress events must be coalesced or rate-limited;
- retention limits must be explicit and repository-defined;
- pruning must be deterministic;
- pruning must remove oldest eligible history first;
- history retention must never interfere with active queue execution.

Codex may use one terminal-history representation plus one bounded event representation, or another design consistent with existing persistence conventions. It must not create competing authorities for the same displayed state.

### 6. Operator-Console Presentation

The Linux Mailing Lists queue display must present:

1. the running job, if any;
2. queued jobs in FIFO order;
3. recent terminal history in newest-first order;
4. bounded recent events or status scrollback where that is already part of the display.

The display must clearly distinguish:

- queued;
- running;
- completed;
- failed;
- cancellation requested;
- cancelled;
- abandoned.

For a running job, display:

- stream name;
- current state;
- latest progress message;
- current acquisition window when available;
- queued time;
- started time;
- latest progress-update time.

For terminal history, display:

- stream name;
- terminal state;
- final message;
- relevant start and finish timestamps.

The exact visual design is Codex’s responsibility, but the display must remain readable and bounded.

---

## Restart and Crash Semantics

The execution queue is intentionally process-local.

After orderly restart, process crash, or host restart:

- queued jobs are not restored;
- a running job is not restored;
- interrupted work is not automatically resumed;
- no pending job is automatically re-enqueued;
- the new process starts with an empty active queue;
- persisted terminal history remains visible;
- persisted bounded display events remain visible according to retention policy;
- durable mailing-list artifacts and acquisition evidence remain authoritative.

The UI and API must not imply that active fetch work is durable.

If an orderly shutdown can record a terminal `abandoned` or interrupted display entry without complicating shutdown semantics, Codex may do so. Crash recovery is not required to manufacture a terminal entry for work whose final state cannot be known.

---

## API and Compatibility Requirements

Preserve the existing public queue routes and behavior:

- `GET /api/linux-mailing-lists/fetches`
- `POST /api/linux-mailing-lists/fetches`
- `POST /api/linux-mailing-lists/fetches/{stream_id}`
- `POST /api/linux-mailing-lists/fetches/cancel-all`

Requirements:

- preserve enqueue behavior;
- preserve duplicate suppression;
- preserve single-worker FIFO behavior;
- preserve cooperative cancellation;
- preserve existing terminal-state semantics;
- preserve existing browser polling cadence;
- preserve existing snapshot fields where practical;
- add fields compatibly rather than repurposing existing fields;
- do not make browser JavaScript directly manipulate SQLite.

If a response-shape change is necessary, document it and update all consumers and tests.

---

## Architectural Requirements

The implementation must preserve:

- SQLite as the sole structured application authority;
- existing repository and migration conventions;
- process-local queue execution;
- single-worker FIFO behavior;
- existing queue synchronization;
- existing mailing-list workflow and acquisition boundaries;
- cancellation polling through the current safe checkpoints;
- bounded acquisition;
- existing REST route ownership;
- shared application services rather than browser-owned state;
- deterministic history pruning;
- safe restart with no restored active work;
- durable acquired artifacts as the authoritative evidence record.

Use established public contracts.

Do not:

- add a general task-runner abstraction;
- add a new daemon;
- add distributed locking;
- add durable leases or claims;
- make SQLite polling drive the worker;
- bypass existing workflow services;
- weaken cancellation or duplicate-suppression behavior.

---

## Required Design Record

Add or update durable design documentation explaining:

1. why mailing-list fetch execution remains process-local;
2. why terminal display history is durable while pending work is not;
3. the progress callback contract and reporting boundary;
4. how progress publication is isolated from acquisition correctness;
5. how queue synchronization protects running-job updates;
6. which timestamps are authoritative and how they are rendered;
7. how terminal history and event scrollback are bounded and pruned;
8. restart semantics;
9. API compatibility;
10. what remains deliberately deferred.

Update the task index, roadmap or baseline records, operator documentation, schema/migration records, and relevant ADRs according to repository conventions.

---

## Non-Goals

TASK-032 does not require:

- durable queued fetch requests;
- resumable or checkpointed fetches;
- automatic retry after crash or restart;
- exact-once or at-least-once task execution guarantees;
- multiple fetch workers;
- individual-job cancellation;
- WebSockets;
- server-sent events;
- a general telemetry subsystem;
- a general job scheduler;
- analytics retention;
- audit-log redesign;
- unbounded event history;
- per-message progress;
- redesign of mailing-list acquisition;
- redesign of unrelated operator-console areas;
- migration to another persistence engine;
- a second structured store.

Do not absorb unrelated cleanup into this task.

Record newly discovered out-of-scope work according to repository backlog policy.

---

## Acceptance Criteria

TASK-032 is complete only when all of the following are demonstrated.

### Progress

1. `fetch_up_to_date(...)` supports an optional backward-compatible progress callback.
2. Progress is emitted at meaningful acquisition-window boundaries.
3. The queue worker updates the running job while the workflow remains active.
4. The browser can observe changing progress through the existing polling endpoint.
5. Progress publication failure cannot fail acquisition.
6. Duplicate or overly frequent progress updates do not flood the queue history.
7. Cancellation and terminal-state behavior remain unchanged.

### Timestamps

8. Queued entries display a queued timestamp.
9. Running entries display started and latest-update timestamps.
10. Progress events display timestamps.
11. Terminal entries display completion/failure/cancellation/abandonment timestamps as applicable.
12. REST timestamps are machine-readable and consistent.
13. Browser timestamp rendering is consistent and timezone behavior is documented.

### Durable bounded history

14. Completed history survives database close and reopen.
15. Failed history survives database close and reopen.
16. Cancelled history survives database close and reopen.
17. Abandoned history survives database close and reopen.
18. Recent terminal history is displayed newest-first.
19. Retention limits are explicit.
20. Oldest eligible history is pruned deterministically.
21. Active process-local jobs are never pruned by history retention.
22. Progress-event retention is bounded and does not grow without limit.

### Restart semantics

23. Pending jobs are not restored after restart.
24. A running job is not restored after restart.
25. The active queue starts empty after restart.
26. Persisted terminal history remains visible after restart.
27. The UI and API do not imply that active fetch jobs are durable.

### Compatibility and quality

28. Existing queue routes remain available.
29. Existing FIFO ordering remains correct.
30. Existing duplicate suppression remains correct.
31. Existing cancel-all behavior remains correct.
32. Existing 1.5-second browser polling remains correct.
33. No second persistence authority is introduced.
34. Full repository validation passes without weakening or skipping existing tests.

---

## Verification Requirements

### 1. Focused Automated Verification

Provide focused automated coverage for at least:

- optional progress callback compatibility;
- callback invocation across multiple acquisition windows;
- progress content and timestamp population;
- running-job snapshot updates before terminal completion;
- synchronization of progress updates under the existing queue lock;
- callback exception isolation;
- progress-event coalescing or rate limiting;
- FIFO execution;
- duplicate suppression;
- completion behavior;
- failure behavior;
- cancellation-requested behavior;
- cancelled behavior;
- abandonment behavior;
- terminal-history persistence across close and reopen;
- event-history persistence across close and reopen;
- newest-first terminal ordering;
- bounded deterministic pruning;
- active-job preservation while pruning;
- restart with an empty active queue;
- non-restoration of queued work;
- non-restoration of running work;
- REST snapshot compatibility;
- browser timestamp formatting;
- browser progress refresh through the existing polling path;
- schema/migration behavior.

Tests must verify observable queue and persistence behavior, not merely helper return values.

### 2. Real-Browser Proof

Using a controlled state, capture a reproducible browser workflow demonstrating:

1. enqueue of a mailing-list fetch;
2. queued timestamp;
3. transition to running;
4. started timestamp;
5. at least two meaningful progress updates while the same job remains running;
6. latest progress message and current window display;
7. latest-update timestamp changing;
8. successful terminal completion or a controlled terminal failure;
9. final terminal timestamp;
10. terminal history visible after the active job completes;
11. multiple terminal entries ordered newest-first;
12. bounded scrollback behavior;
13. application restart;
14. empty active queue after restart;
15. retained terminal history after restart;
16. no unexpected browser console errors;
17. expected polling and API behavior.

Screenshots alone are insufficient. Include procedure, visible states, relevant API responses, persisted effects, and results.

### 3. Gated Live Lore Proof

Run one small bounded live mailing-list fetch that lasts long enough to demonstrate intermediate progress.

Record:

- exact stream and Lore archive;
- exact bounds;
- queued timestamp;
- started timestamp;
- progress messages and timestamps;
- window boundaries reported;
- terminal timestamp;
- final run status;
- fetched and persisted counts;
- terminal-history persistence after restart;
- confirmation that no active job was restored.

The live proof must remain bounded.

### 4. Negative Proof

Explicitly prove that:

- no pending job is stored as resumable work;
- no running job is resumed after restart;
- progress callback failure does not fail acquisition;
- progress events cannot grow without limit;
- terminal-history pruning does not remove active jobs;
- browser code does not directly manipulate persistence;
- no WebSocket or second polling mechanism was introduced;
- no second structured store exists;
- timestamps are not fabricated solely by the browser;
- the queue still rejects or ignores duplicate active work according to existing behavior.

### 5. Regression and Repository Validation

Run and capture:

- focused TASK-032 tests;
- relevant Linux mailing-list workflow tests;
- relevant queue and admin API tests;
- relevant persistence and migration tests;
- complete repository validation;
- lint;
- formatting;
- type checking;
- documentation checks;
- design-baseline checks;
- schema/migration checks;
- sensitive-output scan;
- `git diff --check`;
- isolated copied-tree or clean-checkout-equivalent validation.

No pre-existing test may be weakened, deleted, skipped, or rewritten merely to obtain a passing result without explicit evidence and justification.

---

## Required Review Package

Produce a complete TASK-032 review directory and ZIP using the repository’s established review-package convention.

The package must contain at least:

1. task ticket;
2. completion report;
3. queue-architecture summary;
4. progress-callback contract;
5. timestamp contract;
6. terminal-history persistence design;
7. retention and pruning policy;
8. restart-semantics statement;
9. API compatibility summary;
10. changed-file inventory with rationale;
11. cumulative task-scoped patch or equivalent diff evidence;
12. focused automated test commands and complete outputs;
13. full repository validation command and complete output;
14. real-browser proof procedure and results;
15. screenshots or equivalent rendered evidence;
16. browser console and network evidence;
17. gated live Lore proof;
18. persisted terminal-history evidence;
19. restart and non-restoration proof;
20. negative proofs;
21. documentation and baseline validation outputs;
22. schema/migration validation;
23. sensitive-output scan;
24. isolated-tree validation;
25. repository branch, base, HEAD, staged, unstaged, untracked, and worktree state;
26. machine-readable review manifest;
27. package-member checksums;
28. ZIP integrity output;
29. SHA-256 checksum.

The package must be self-contained enough for an independent reviewer to determine:

- whether running fetches provide meaningful progress;
- whether timestamps are correct and consistent;
- whether terminal scrollback is durable and bounded;
- whether active queue work remains intentionally process-local;
- whether restart semantics are truthful;
- whether existing queue and acquisition behavior was preserved;
- whether regressions were introduced.

A summary claiming success without the complete evidence above is insufficient.

---

## Codex Execution Constraints

Codex must follow these constraints exactly.

- Work only in the RFI-1 repository.
- Begin from a clean worktree.
- Determine the correct base branch from repository conventions.
- Create and switch to a new task branch named consistently with repository conventions for TASK-032.
- Read the governing project documents, TASK-028, current queue implementation, workflow service, acquisition service, persistence conventions, migration conventions, admin routes, Linux Mailing Lists browser code, operator documentation, and review-package conventions before implementing.
- Trace the current queue worker-to-workflow-to-browser path before changing code.
- Preserve the name **Process Local Fetch Queue** in code-facing and operator-facing documentation where that is the established term.
- Treat this ticket as an outcome and architecture requirement, not permission to build a general durable task system.
- Keep active queue execution process-local.
- Do not persist queued or running work as resumable jobs.
- Do not introduce WebSockets, another worker, or another polling mechanism.
- Do not bypass established workflow or persistence contracts.
- Do not weaken bounded acquisition, cancellation, FIFO, duplicate suppression, or terminal-state invariants.
- Do not broaden scope into unrelated operator-console redesign or mailing-list acquisition changes.
- Do not weaken, delete, skip, or rewrite existing tests merely to obtain a passing result.
- Do not mark the task Done until every acceptance criterion and verification requirement is supported by reviewable evidence.
- If the existing architecture materially prevents the required outcome, stop and report the conflict with evidence rather than implementing a misleading workaround.
- Commit the completed TASK-032 work on the task branch after all required validation and review-package generation pass.
- The commit message must identify TASK-032 and summarize the delivered outcome.
- Do not push, merge, delete branches, clean unrelated files, or perform unrelated Git operations unless separately authorized by the operator.

---

## Completion Report Requirements

Codex’s final report must state:

1. the branch created and base branch used;
2. the exact progress callback contract;
3. where progress is emitted;
4. how the queue safely updates running-job state;
5. how progress-event coalescing or rate limiting works;
6. all timestamp fields added or reused;
7. timestamp format and timezone behavior;
8. how terminal job history is persisted;
9. how event scrollback is persisted;
10. retention limits and deterministic pruning policy;
11. restart behavior for queued and running work;
12. confirmation that no active work is restored;
13. confirmation that terminal history survives restart;
14. API and browser compatibility;
15. exact bounded live Lore proof;
16. focused and full validation outcomes;
17. review directory and ZIP paths;
18. ZIP size, integrity result, and SHA-256 checksum;
19. changed-file inventory;
20. repository branch, base, HEAD, staged, unstaged, untracked, and worktree state;
21. commit hash and commit message;
22. confirmation that the completed work was committed;
23. confirmation that no push, merge, branch deletion, or unrelated cleanup was performed;
24. known limitations and deliberately deferred capabilities;
25. any departure from this ticket and its rationale.

---

## Definition of Done

TASK-032 is done only when a capable operator can enqueue a Linux mailing-list fetch, observe meaningful timestamped progress while it runs, inspect a bounded timestamped terminal history after it completes, restart RFI-1, and still inspect that terminal history—while queued and running work remain truthfully process-local and are not resumed.

The following are explicitly insufficient:

- changing only the displayed message from `Running`;
- emitting progress without timestamps;
- storing all queue state durably;
- resuming pending or running work after restart;
- adding an unbounded event log;
- persisting terminal history without displaying it;
- changing browser polling without need;
- fixture-only proof;
- a passing test suite without browser and live proof;
- or a review package lacking complete raw evidence.

The task is complete only when progress, timestamps, bounded durable history, restart semantics, and independent verification all work together and the completed work is committed on the TASK-032 branch.
