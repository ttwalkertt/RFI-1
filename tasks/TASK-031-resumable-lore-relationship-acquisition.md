# TASK-031 — Resumable Lore Relationship Acquisition

## Status

Done

## Purpose

Make Linux kernel mailing-list relationship acquisition resumable across bounded Lore requests.

RFI-1 must continue to honor adapter request limits while allowing a discussion larger than one relationship batch to complete through additional durable acquisition runs.

Depth-first traversal is the preferred relationship-expansion strategy because it should reduce continuation complexity. Codex may select the exact design after tracing the existing workflow and persistence contracts.

---

## Problem Statement

The current Lore workflow decomposes a large catch-up into bounded date windows and pageable seed searches, but relationship expansion for each seed page remains a single non-resumable batch.

When the relationship allowance is exhausted or Lore exposes additional relationship pages, RFI-1 currently:

- retains the evidence already acquired;
- marks the relationship batch incomplete or truncated;
- withholds complete coverage; and
- stops the larger catch-up before later seed pages or date windows can finish.

This incorrectly turns an adapter request bound into an effective corpus bound.

A discussion containing more relationship context than one request permits is not inherently defective. Consuming one bounded request should normally mean that more bounded work remains, not that the discussion has permanently failed or that the larger acquisition must stop.

The current generic status wording also conflates:

- successful bounded progress with more work pending;
- intentional policy truncation;
- provider or execution failure; and
- structurally incomplete retained evidence.

This is an acquisition-orchestration and durable-state issue, not a GUI-only correction.

---

## Required Outcome

RFI-1 shall support relationship acquisition that can span multiple bounded runs while preserving the existing Lore adapter limits and repository invariants.

For a qualifying mailing-list catch-up, RFI-1 must be able to:

1. acquire a bounded seed page;
2. expand required ancestry and reply relationships within the current request limits;
3. preserve valid acquired evidence and durable progress when more relationship work remains;
4. resume that relationship work in a later bounded run;
5. continue until configured relationship coverage is complete or an explicit terminal policy condition is reached;
6. proceed to later seed pages and date windows after the current relationship work reaches a valid terminal state;
7. restart safely without losing progress or duplicating evidence; and
8. report the difference between pending continuation, policy truncation, and actual failure.

A discussion requiring more than 50 total records must be capable of completing across multiple runs when no explicit policy limit prevents completion.

---

## Product and Architectural Direction

### Adapter Bounds Remain Hard

This task must not remove or weaken bounded provider interaction.

Each individual Lore request or acquisition run must remain within the established adapter criteria, including applicable:

- direct-seed limits;
- total/context record limits;
- date-window limits;
- reply-depth policy;
- provider pagination limits;
- timeout and retry controls; and
- governed transport requirements.

Resumption extends acquisition across bounded runs. It does not create an unbounded request or uncontrolled mirror.

### Depth-First Is Preferred

Depth-first traversal is the preferred relationship-expansion strategy because it is expected to simplify durable continuation and deterministic restart.

Codex shall confirm that the chosen traversal:

- is deterministic;
- eventually covers all relationships required by configured policy;
- preserves ancestry requirements;
- resumes safely;
- does not duplicate stored evidence; and
- does not allow one branch to corrupt or conceal another.

This ticket intentionally does not prescribe the internal continuation frontier, schema, cursor representation, or detailed algorithm. Codex is responsible for selecting an architecture consistent with existing public contracts and repository authority.

### Pending Work Is Not Incompleteness

Exhausting a bounded relationship batch while resumable work remains must not be represented as a permanent defect.

The system must distinguish at least:

- **complete** — configured relationship acquisition is exhausted successfully;
- **continuation pending** — the current bounded run completed successfully and more relationship work remains;
- **policy truncated** — an explicit configured policy prevents further expansion;
- **failed** — provider, persistence, validation, integrity, or execution failure prevented valid progress.

Retained artifacts remain immutable evidence. Run-level acquisition status must not be projected onto messages as though the artifacts themselves were defective.

### Coverage Must Be Precise

RFI-1 must preserve distinct coverage concepts where relevant, including:

- direct seed-search progress;
- relationship-acquisition progress;
- policy-truncated relationships;
- actual failed work; and
- final date-window coverage.

A date window must not be declared fully covered while required resumable relationship work remains unfinished.

At the same time, one pending relationship continuation must not erase or mislabel valid evidence already acquired.

---

## Required Behavior

### Resumable Relationship Work

When a relationship batch reaches an adapter boundary and valid additional work remains, RFI-1 shall:

- complete the current bounded run without reporting an execution error;
- retain all valid evidence and relationship progress;
- persist sufficient authoritative state to resume deterministically;
- make the pending continuation observable through existing service and operator surfaces;
- resume through a later bounded run; and
- avoid repeating completed provider work except where safe idempotent verification is required.

### Ancestry

Required ancestry must remain structurally correct.

RFI-1 must not:

- omit an intermediate ancestor merely to fit a batch;
- claim complete ancestry while a required ancestor remains unresolved;
- discard resolved edges because a later continuation is pending; or
- confuse unknown future replies with missing historical ancestry.

### Replies and Discussion Expansion

Configured reply expansion must be able to continue across multiple runs.

Depth-first traversal is preferred, but the externally visible requirement is complete deterministic acquisition through the configured relationship policy, regardless of the number of bounded requests required.

A thread still receiving future replies is not defective. Completion applies to the observable source state and configured acquisition scope at the time of retrieval; future messages may be acquired by later catch-up.

### Seed Pagination and Date Windows

Relationship continuation must integrate cleanly with existing seed-page and date-window decomposition.

The workflow must not silently abandon later seed pages because one relationship batch exceeded one run’s allowance.

Codex shall define and document the sequencing policy among:

- pending relationship continuations;
- later seed pages in the same date window; and
- later date windows.

The policy must remain deterministic, bounded, restartable, and coverage-correct.

### Idempotency and Overlap

Overlapping seeds, shared ancestors, shared replies, repeated runs, and process restart must not create duplicate artifacts or contradictory relationship state.

Existing immutable artifact identity, provenance, observations, memberships, and repository query behavior must remain authoritative.

### Operator Reporting

Operator-visible status must clearly state:

- what bounded work completed;
- whether continuation remains;
- whether retained evidence is valid;
- whether coverage is complete;
- whether an explicit policy caused truncation; and
- whether an actual failure occurred.

Replace or refine generic wording such as `incomplete relationship batch` where it obscures these distinctions.

This task does not require a broad visual redesign, but all existing browser, API, CLI, run-history, and artifact projections affected by the new state model must remain truthful and consistent.

---

## Architectural Requirements

Preserve:

- SQLite as the sole structured application authority;
- immutable content-addressed artifact storage;
- canonical message identity and provenance;
- stream revision history;
- governed provider access;
- bounded acquisition;
- connected-discussion invariants;
- repository-owned query and browser contracts;
- restart and replay behavior;
- source-effective message metadata;
- separation between acquisition-run state and artifact truth;
- shared services across browser, CLI, workflows, and tests; and
- existing atomicity and integrity guarantees.

Do not:

- introduce a second relationship store;
- keep authoritative continuation state only in browser memory or process memory;
- make admin handlers or browser code manipulate persistence directly;
- treat the 50-record adapter limit as a permanent discussion-size limit;
- weaken depth, date, transport, timeout, or service-use controls;
- label all retained messages incomplete because one run is partial;
- discard complete paths or memberships merely because another branch is pending;
- bypass existing source, stream, acquisition, artifact, or projection contracts; or
- implement an unrestricted Lore mirror.

---

## Non-Goals

TASK-031 does not require:

- changing the configured reply-depth policy unless correctness requires clarification;
- unlimited historical mailing-list mirroring;
- scheduled polling or background daemons;
- notifications;
- non-Lore providers;
- generic email ingestion;
- semantic search or AI relevance classification;
- claim, position, or report generation;
- a graph database;
- broad artifact-browser redesign;
- unrelated SEC, firm, or source-workflow changes;
- general job-queue infrastructure unrelated to this bounded acquisition need;
- operator-editable internal continuation state; or
- implementation of the separate Target Firms CIK enhancement.

Record genuine newly discovered work in the repository backlog rather than expanding this ticket without authorization.

---

## Acceptance Criteria

TASK-031 is complete only when all of the following are demonstrated.

### Resumption and Completion

1. A relationship set larger than one configured batch completes across multiple bounded runs.
2. Consuming the relationship allowance produces continuation-pending status rather than permanent incompleteness or execution failure.
3. A paginated Lore relationship feed resumes and completes correctly.
4. Required ancestry remains structurally complete and prioritized appropriately.
5. Configured reply expansion eventually covers all reachable relationships within policy.
6. Depth-first traversal is used unless Codex documents compelling evidence for a different deterministic approach and obtains operator approval before implementation.
7. The exact internal continuation design is documented after implementation without being dictated by this ticket.

### Workflow Progress

8. Later seed pages are not permanently skipped because an earlier page requires relationship continuation.
9. Date-window coverage is not advanced while required continuation work remains.
10. Once continuation work reaches a valid terminal state, normal seed and date-window progress resumes.
11. Process interruption and restart preserve progress safely.
12. Repeated execution is idempotent.

### Evidence and Projection Correctness

13. Valid retained artifacts remain verified and usable while continuation is pending.
14. Complete paths and relationships already resolved remain visible in derived projections.
15. Run-level partial or pending state is not incorrectly stamped onto artifacts as an intrinsic defect.
16. Overlapping seeds and branches do not duplicate stored evidence or relationship membership.
17. Future replies posted after the acquisition snapshot are not represented as a defect in the completed snapshot.

### Status Semantics

18. Complete, continuation pending, policy truncated, and failed outcomes are distinguishable in durable state.
19. API, CLI, browser, run history, and artifact projections use consistent terminology and semantics.
20. Operator messages identify what completed, what remains, whether evidence is valid, and whether retry/resumption is automatic or operator-initiated.
21. Generic `incomplete relationship batch` wording is removed or narrowed so it cannot misrepresent successful bounded progress.

### Preservation

22. Existing adapter request limits remain enforced per run.
23. Existing provider-error, tombstone, missing-parent, integrity, and genuine policy-truncation controls remain intact.
24. No second persistence authority is introduced.
25. Full repository validation passes without weakening or skipping existing tests.

---

## Verification Requirements

### Focused Automated Verification

Provide focused TASK-031 tests for at least:

- relationship acquisition exceeding 50 records across multiple runs;
- multiple continuations for one discussion;
- deterministic depth-first traversal;
- ancestry completion across a run boundary;
- reply expansion across a run boundary;
- provider pagination continuation;
- continuation after exact budget exhaustion;
- overlap among direct seeds and context messages;
- overlap across continuation runs;
- duplicate suppression and stable artifact identity;
- process restart between continuations;
- safe retry after interruption;
- later seed-page progress;
- later date-window progress;
- coverage withholding while required work remains;
- coverage completion after continuations finish;
- policy depth truncation remaining distinct from batch continuation;
- provider failure remaining distinct from continuation pending;
- missing-parent and tombstone behavior;
- valid projection membership for structurally complete retained paths;
- no artifact-level contamination from run-level status;
- truthful API, CLI, browser, and run-history projection; and
- existing negative controls from the mailing-list acquisition suite.

Tests must assert durable repository effects and restart behavior, not merely in-memory traversal results.

### Fixture and Failure Proof

Use deterministic fixtures that prove:

- a discussion requiring at least three bounded relationship runs;
- a branch with provider pagination;
- shared messages among multiple seeds;
- interruption after durable progress;
- recovery without duplication;
- explicit policy truncation;
- actual provider failure; and
- unknown future replies not affecting snapshot correctness.

### Gated Live Lore Proof

Run a bounded live Lore proof that demonstrates at least one real relationship continuation or, if an appropriate live thread cannot be safely and reproducibly selected, a bounded live acquisition plus deterministic fixture proof of the multi-run continuation path.

The live evidence must record:

- archive and query scope;
- adapter limits;
- seed pages processed;
- relationship runs performed;
- messages and relationships retained per run;
- continuation state transitions;
- final coverage state;
- restart or rerun result;
- source links; and
- any policy truncation or provider limitation encountered.

Codex must not manufacture a live success claim where service behavior cannot prove the required condition.

### Regression and Repository Validation

Run and retain:

- focused TASK-031 tests;
- relevant TASK-023 relationship tests;
- relevant TASK-025 stream tests;
- relevant TASK-028 workflow and browser tests;
- complete repository validation;
- lint;
- formatting;
- type checking;
- documentation checks;
- design-baseline checks;
- schema and migration checks;
- fixture/archive integrity checks;
- sensitive-output scan;
- `git diff --check`; and
- isolated copied-tree or clean-checkout-equivalent validation.

No pre-existing test may be weakened, deleted, skipped, or rewritten merely to accommodate this task without explicit evidence and justification.

---

## Required Design Record

Update durable project documentation and ADRs as warranted to explain:

1. why relationship acquisition must be resumable;
2. why adapter bounds remain per-request controls rather than corpus-size limits;
3. why depth-first traversal was selected or, with prior approval, why another traversal was necessary;
4. how continuation state fits existing repository authority;
5. how ancestry, replies, seed pages, and date windows interact;
6. how completion, continuation pending, policy truncation, and failure differ;
7. how coverage is represented while work remains;
8. how restart, idempotency, and overlap are handled;
9. how run state remains distinct from artifact truth; and
10. what remains deliberately deferred.

Update the task index, roadmap/baseline records, operator guide, and relevant status/help text according to repository conventions.

---

## Required Review Package

Produce a complete TASK-031 review directory and ZIP using the repository’s established review-package convention.

The package must contain at least:

1. task ticket;
2. completion report;
3. architectural summary;
4. current-behavior diagnosis;
5. design decisions and alternatives considered;
6. actual continuation model and responsibility split;
7. traversal-order rationale;
8. status and coverage taxonomy;
9. ancestry and reply correctness analysis;
10. seed-page and date-window orchestration analysis;
11. restart and idempotency analysis;
12. persistence/schema changes, if any;
13. changed-file inventory with rationale;
14. cumulative task-scoped patch or equivalent diff evidence;
15. focused test commands and complete outputs;
16. deterministic fixture inventory;
17. multi-run relationship evidence;
18. provider-pagination evidence;
19. overlap and deduplication evidence;
20. interruption and restart evidence;
21. policy-truncation negative control;
22. provider-failure negative control;
23. projection and artifact-truth evidence;
24. API, CLI, browser, and run-history evidence;
25. gated live Lore evidence;
26. full repository validation command and complete output;
27. documentation and baseline validation output;
28. sensitive-output scan;
29. isolated-tree validation;
30. repository branch, base, HEAD, staged, unstaged, untracked, and worktree state;
31. machine-readable review manifest;
32. package-member checksums;
33. ZIP integrity output; and
34. SHA-256 checksum.

The package must be self-contained enough for an independent reviewer to determine whether relationship acquisition truly resumes across bounded runs and whether existing evidence, coverage, and failure semantics remain correct.

A passing summary without complete raw evidence is insufficient.

---

## Codex Execution Constraints

- Work only in the RFI-1 repository and the prepared TASK-031 branch.
- Read the governing project documents, TASK-023, TASK-025, TASK-028, current mailing-list workflow, acquisition service, persistence contracts, projection logic, operator guide, and review-package conventions before proposing changes.
- Trace the current date-window, seed-pagination, ancestry, reply-expansion, run-finalization, coverage, and projection behavior end to end before implementation.
- Treat this ticket as an architectural outcome requirement, not an implementation recipe.
- Prefer depth-first relationship traversal.
- Do not require this ticket to specify the internal continuation frontier; select and justify the design from repository evidence.
- Preserve all per-request adapter bounds.
- Do not solve the problem by merely continuing to later seed pages while leaving oversized relationships permanently incomplete.
- Do not solve the problem with a GUI-only status change.
- Do not create a second queue, store, or authority outside established repository contracts.
- Do not keep authoritative resumption state only in memory.
- Do not weaken ancestry, relationship, provenance, artifact, integrity, or coverage invariants.
- Do not mark valid artifacts defective because work remains at the acquisition-run level.
- Do not broaden scope into unrelated UI cleanup, scheduling, generic job infrastructure, or intelligence features.
- Do not weaken, delete, skip, or rewrite existing tests merely to obtain a passing result.
- Do not mark the task Done until every acceptance criterion and verification requirement is supported by reviewable evidence.
- If existing architecture materially conflicts with resumable acquisition, stop and report the conflict with evidence rather than implementing a shadow mechanism.
- Do not commit, push, merge, delete branches, clean the repository, or perform unrelated Git operations unless separately authorized by the operator.

---

## Completion Report Requirements

Codex’s final report must state:

1. the exact prior stopping behavior and root cause;
2. the architecture used for durable resumable relationship acquisition;
3. the traversal order actually implemented and why;
4. how ancestry and replies resume;
5. how provider pagination resumes;
6. how seed pages and date windows progress;
7. how complete, continuation pending, policy truncated, and failed states are represented;
8. how coverage is withheld and later completed;
9. how restart and idempotency are guaranteed;
10. how overlapping seeds and branches are deduplicated;
11. how artifact truth remains separate from run status;
12. exact focused and full validation outcomes;
13. exact live Lore proof outcome;
14. review directory and ZIP paths;
15. ZIP size, integrity result, and SHA-256 checksum;
16. branch, base, HEAD, staged, unstaged, untracked, and worktree state;
17. known limitations and deferred capabilities;
18. any departure from this ticket and its rationale; and
19. explicit confirmation that no commit, push, merge, branch deletion, or cleanup was performed unless separately authorized.

---

## Definition of Done

TASK-031 is done only when a Lore discussion larger than one relationship batch can be acquired to configured completion through multiple bounded, durable, restartable runs without duplicating evidence, corrupting projections, mislabeling artifacts, or blocking the larger catch-up permanently.

The following are explicitly insufficient:

- changing only the UI message;
- increasing the 50-record limit;
- making one provider request unbounded;
- skipping the oversized discussion and continuing seed pagination;
- retaining a permanently incomplete discussion without resumable work;
- keeping continuation only in process memory;
- proving only an in-memory traversal helper;
- fixture success without durable restart proof;
- a live HTTP success without stored relationship evidence;
- or a review package lacking complete raw verification.

The task is complete only when bounded relationship acquisition is genuinely resumable and the verification package proves it independently.
