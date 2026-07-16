# TASK-003 — Fixture-Backed Acquisition Engine and End-to-End Kernel

## Status

Ready

## Objective

Implement the deterministic acquisition engine that orchestrates governed sources, discovery, retrieval, durable repository ingestion, checkpointing, replay, and operator-visible outcomes across the TASK-002 acquisition substrate.

This task must prove the complete acquisition kernel through representative fixture-backed source adapters and realistic multi-run scenarios without contacting external services.

The result should be a useful, executable acquisition framework ready for the first real SEC adapter in the next task. It must not yet implement SEC, EDGAR, Investor Relations, web crawling, or any other live network source.

## Context

TASK-001 established the repository foundation and authoritative design baseline.

TASK-002 implemented repository-owned acquisition contracts and persistence semantics, including:

- governed source profiles;
- stable repository-owned identities;
- immutable content-addressed artifacts;
- append-only retrieval and checkpoint records;
- rebuildable indexes;
- idempotent repository operations;
- replay and integrity verification;
- explicit partial-failure behavior.

TASK-003 must now connect these capabilities into a coherent acquisition engine that can execute complete source runs.

The implementation program is intentionally condensed into a small number of framework-scale tasks. Codex is responsible for subsystem-level design choices within the architectural constraints and acceptance criteria in this ticket.

The governing project documents, TASK-002 implementation, ADRs, and repository development guidance are authoritative inputs.

## Governing Principles

The implementation must preserve these principles:

1. The repository remains the durable system of record.
2. Acquisition orchestration must not own repository identity or evidence semantics.
3. Source adapters discover and retrieve; the repository substrate validates and persists.
4. Evidence must be durable before progress advances.
5. Repeated runs must be deterministic and idempotent for equivalent source state.
6. Partial failure must remain visible and resumable.
7. Checkpoints are source-scoped and must not hide unprocessed candidates.
8. Stored evidence defines the replay boundary.
9. Fixture adapters must exercise real contracts rather than bypassing them.
10. Source-specific behavior must remain outside the core acquisition engine.
11. Abstractions must emerge from demonstrated fixture behavior rather than imagined future sources.
12. The engine must remain understandable and operable by a single technical owner.
13. A commercial provider may later implement an adapter, but the engine must not depend on one.
14. Acquisition must remain separate from extraction, interpretation, knowledge development, and projection.

## Required Outcomes

### 1. Acquisition engine

Implement a repository-independent orchestration component that coordinates a complete acquisition run.

The engine must be able to:

- load and validate an enabled governed source profile;
- select an appropriate source adapter through an explicit, inspectable mechanism;
- discover deterministic source candidates;
- apply source-scoped progress or checkpoint semantics;
- retrieve candidate content and retrieval metadata;
- convert adapter results into repository-owned acquisition inputs;
- invoke the TASK-002 repository substrate for durable processing;
- record materially meaningful successes, duplicates, skips, and failures;
- advance source progress only when the governing durability conditions are satisfied;
- return a structured run result suitable for operator inspection and automation;
- support repeated execution without duplicating evidence or corrupting history.

The engine must not directly manipulate the physical artifact store, ledger files, or derived index layout outside the public TASK-002 repository contracts.

### 2. Source-adapter boundary

Define and implement the minimum adapter contract needed to prove multiple source behaviors.

The contract must clearly separate:

- source configuration;
- discovery;
- candidate identity and provenance;
- retrieval;
- source continuation or pagination state;
- adapter diagnostics;
- repository ingestion.

Adapters must not:

- assign repository document identity as provider identity;
- write repository evidence directly;
- advance durable checkpoints directly;
- mutate prior acquisition history;
- perform knowledge extraction or document interpretation.

The adapter boundary must be sufficient for the next real SEC adapter, but it must not become a speculative universal plugin framework.

### 3. Representative fixture adapters

Implement at least two materially different deterministic fixture adapters.

Together, the fixtures must exercise differences such as:

- single-page versus paginated discovery;
- stable provider identifiers versus URL-like discovery references;
- successful retrieval;
- duplicate discovery;
- unchanged repeated retrieval;
- a document revised under a stable source reference;
- transient retrieval failure;
- permanent or policy-based skip;
- malformed provider response;
- source continuation state;
- deterministic ordering.

The fixture adapters must invoke the same acquisition engine and repository contracts intended for future live adapters.

A fixture must not directly seed repository storage as a substitute for engine execution.

### 4. Complete run lifecycle

A source run must have an explicit lifecycle and structured result.

The design must define, document, and verify:

- run identity;
- source identity;
- start and completion state;
- candidate counts;
- retrieval attempts;
- durable acquisitions;
- duplicates or unchanged results;
- skips;
- failures;
- checkpoint state before and after;
- whether the run is complete, partial, blocked, or failed;
- diagnostics sufficient for operator action.

A run summary must be derived from observed outcomes, not optimistic control flow.

### 5. Deterministic candidate processing

Candidate handling must be deterministic.

The implementation must define and test:

- candidate ordering;
- duplicate candidate behavior within one discovery result;
- duplicate candidate behavior across pages;
- stable handling of equal timestamps or equivalent ordering keys;
- checkpoint filtering;
- source revisions;
- retry behavior;
- run resumption after partial failure.

The engine must not silently drop ambiguous candidates.

### 6. Pagination and continuation

Implement fixture-backed continuation behavior that is credible for a later provider-backed adapter.

The design must distinguish:

- provider continuation state used during a run;
- durable source checkpoint state;
- incomplete-page or partial-run state;
- completion of a bounded run.

A provider cursor must not automatically become the repository’s durable source identity or sole replay record.

Tests must show safe behavior when failure occurs:

- before a page is processed;
- midway through a page;
- after candidates are durable but before the next page;
- at the end of discovery before checkpoint finalization.

### 7. Retry, failure classification, and resumption

Define a proportionate failure model for acquisition execution.

The engine must distinguish at least:

- transient adapter failure;
- permanent retrieval failure;
- malformed adapter output;
- policy or source-profile rejection;
- repository conflict;
- repository integrity failure;
- partial run with durable progress;
- complete run with non-fatal skipped candidates.

The implementation must make retry and resumption behavior explicit.

Do not build a production scheduler or distributed retry service. Provide deterministic execution semantics and operator-visible guidance suitable for the POC.

### 8. Idempotency across complete runs

Prove idempotency at the orchestration level, not only within repository persistence.

Repeated equivalent source runs must:

- avoid duplicate artifacts;
- avoid contradictory document identity;
- preserve append-only attempt evidence where materially appropriate;
- avoid invalid checkpoint movement;
- produce stable final repository-derived state;
- explain any run-summary differences caused by recording a repeated attempt.

A later source revision must be distinguishable from an accidental duplicate or conflicting operation.

### 9. Offline replay and rebuild compatibility

The engine and adapter design must preserve TASK-002 replay guarantees.

After acquisition:

- mutable indexes must remain rebuildable from authoritative repository state;
- replay must not require fixture adapters;
- replay must not invoke discovery or retrieval;
- fixture source state must not become authoritative repository evidence;
- acquired artifact integrity must remain independently verifiable.

Tests must include deletion and rebuild of derived state after multi-source, multi-run acquisition.

### 10. Operator workflow

Provide a practical operator interface or documented command workflow for:

- listing governed sources;
- validating adapter registration;
- running one fixture source;
- running all enabled fixture sources;
- displaying a structured run summary;
- inspecting failures and diagnostics;
- resuming a partial run;
- verifying repository integrity;
- rebuilding derived indexes;
- replaying repository state without adapters;
- running the complete TASK-003 validation suite.

The operator interface may remain a development-oriented CLI or script. It must be explicit, deterministic, and suitable for later extension to a real SEC adapter.

### 11. Configuration and secrets boundary

Fixture source configuration must demonstrate the expected boundary for future credentials and provider configuration without requiring secrets.

The implementation must:

- keep secrets out of source profiles, repository evidence, logs, fixtures, and review artifacts;
- provide an explicit credential-reference or runtime-configuration boundary if one is needed by the adapter contract;
- avoid inventing a broad secret-management framework;
- document what a future live adapter may receive and what it must never persist.

### 12. Durable design record

Record the material decisions made in TASK-003.

The design record must address:

- acquisition-engine responsibilities;
- adapter responsibilities;
- adapter selection and registration;
- run lifecycle and result model;
- deterministic candidate ordering;
- pagination and continuation;
- retry and failure classification;
- checkpoint interaction;
- idempotency across runs;
- fixture representativeness;
- credential boundary;
- concurrency assumptions;
- alternatives considered;
- limits of the fixture-backed proof relative to the next live adapter task.

## Required Demonstration

Provide a deterministic end-to-end demonstration using the fixture adapters and an empty local repository state.

The demonstration must prove:

1. two governed fixture sources can be registered;
2. the engine selects the correct adapter explicitly;
3. one source completes a paginated acquisition;
4. one source exercises materially different discovery behavior;
5. exact retrieved bytes become immutable repository artifacts;
6. provenance and retrieval history remain inspectable;
7. duplicate candidates within and across pages are handled deterministically;
8. a second equivalent run is idempotent;
9. a source revision creates the correct new evidence relationship without corrupting prior evidence;
10. a transient failure produces a partial or failed run with actionable diagnostics;
11. the failed run can be resumed safely;
12. checkpoints do not advance beyond durable work;
13. a malformed adapter result is rejected observably;
14. derived indexes can be deleted and rebuilt after all runs;
15. replay works with adapter access disabled;
16. artifact integrity verification passes;
17. final repository-derived state is deterministic across repeated clean demonstrations.

The demonstration must use the production acquisition engine and public repository contracts. It must not use test-only shortcuts to write artifacts, ledger entries, indexes, or checkpoints directly.

## Non-Goals

TASK-003 must not implement:

- SEC-API.io or another commercial SEC provider;
- native SEC EDGAR retrieval;
- Investor Relations website retrieval;
- live HTTP access;
- web crawling or scraping;
- robots.txt policy;
- rate limiting for real services;
- production credential storage;
- production scheduling or queues;
- distributed workers;
- broad plugin discovery;
- arbitrary dynamic code loading;
- content parsing or extraction;
- OCR;
- observations, derivations, enrichments, claims, positions, or projections;
- LLM calls;
- embeddings or vector search;
- RAG;
- consulting briefs, reports, dashboards, or question answering;
- production deployment infrastructure.

Do not add placeholder implementations for these deferred capabilities.

## Architectural Boundaries

Codex has implementation discretion subject to these boundaries:

- preserve the TASK-002 public repository contracts unless evidence proves a correction is necessary;
- document any TASK-002 contract change and its compatibility impact;
- keep adapter behavior outside repository persistence;
- keep repository layout private behind repository-owned interfaces;
- do not allow provider cursors or IDs to become repository-owned identity;
- do not allow the engine to bypass append-only ledger behavior;
- do not advance checkpoints before durable repository success;
- do not use fixture-specific branches in the engine’s central control flow;
- do not introduce a generalized framework unsupported by at least two fixture behaviors;
- preserve offline replay and rebuild;
- use deterministic time or injected clocks where required for reproducible tests;
- keep dependencies proportionate and documented;
- preserve existing validation and documentation guarantees;
- prefer a cohesive engine and explicit contracts over framework magic;
- retain clear single-process and single-writer assumptions unless intentionally changed and verified.

## Acceptance Criteria

TASK-003 is complete only when all of the following are true:

1. A coherent acquisition engine orchestrates complete source runs through TASK-002 public repository contracts.
2. The source-adapter boundary separates discovery and retrieval from repository persistence.
3. At least two materially different deterministic fixture adapters use the same engine.
4. Fixture adapters do not write repository state directly.
5. Source profiles select adapters through an explicit validated mechanism.
6. Run identity, lifecycle, outcomes, counts, diagnostics, and checkpoint changes are structured and inspectable.
7. Candidate ordering and duplicate handling are deterministic.
8. Pagination and provider continuation are distinct from durable repository checkpoints.
9. Partial-page and partial-run failures preserve durable work without overstating progress.
10. Failure classes and resumption behavior are explicit and tested.
11. Repeated equivalent complete runs are idempotent.
12. Source revisions are represented without corrupting prior evidence.
13. Malformed adapter output and repository conflicts fail observably.
14. No checkpoint advances beyond required durable effects.
15. Multi-source, multi-run derived state is completely rebuildable.
16. Replay works with adapter and network access unavailable.
17. Artifact integrity remains independently verifiable.
18. Operator workflows support execution, inspection, resumption, verification, rebuild, and replay.
19. Fixture configuration demonstrates a safe future credential boundary without storing secrets.
20. Material design decisions and alternatives are durably recorded.
21. Existing TASK-001 and TASK-002 tests and quality gates continue to pass.
22. No live source, downstream knowledge, AI, or projection functionality is implemented.
23. A complete independently auditable TASK-003 verification package is generated.
24. Final Git and branch state are explicitly reported.

## Verification Requirements

Verification must include, at minimum:

- focused unit tests for engine and adapter contracts;
- end-to-end tests using each fixture adapter;
- multi-source execution tests;
- pagination tests;
- deterministic candidate-order tests;
- duplicate-within-page and duplicate-across-page tests;
- idempotent repeated-run tests;
- source-revision tests;
- transient failure and safe-resumption tests;
- malformed adapter-output tests;
- repository-conflict propagation tests;
- checkpoint-ordering tests;
- partial-page and partial-run tests;
- blocked-network tests for all fixture execution and replay;
- adapter-disabled replay tests;
- index-loss and full-rebuild tests after multi-run acquisition;
- artifact-corruption detection;
- deterministic clean-run comparison;
- complete existing-project validation;
- isolated-tree or clean-checkout-equivalent validation;
- evidence that prohibited live-source and downstream capabilities are absent.

Tests must assert repository effects and durable records, not merely method return values.

## Required Verification Package

Produce the complete TASK-003 review directory and ZIP under the established `.artifacts/review` convention.

The package must be generated from the final task state and support independent review.

At minimum, include:

- `executive-summary.md`
- `implementation-summary.md`
- `architecture-decisions.md`
- `alternatives-considered.md`
- `engine-contract-summary.md`
- `adapter-boundary-summary.md`
- `run-lifecycle-and-result-model.md`
- `candidate-ordering-and-pagination.md`
- `failure-retry-and-resumption.md`
- `checkpoint-and-idempotency-analysis.md`
- `fixture-representativeness.md`
- `credential-boundary.md`
- `end-to-end-demonstration.md`
- `known-limitations.md`
- `deferred-work.md`
- `repository-tree.txt`
- `changed-files.txt`
- `git-status.txt`
- complete task-scoped `git-diff.patch`
- exact `validation-commands.md`
- raw focused-test output
- raw full-suite output
- raw end-to-end demonstration output
- raw repeated-run/idempotency output
- raw revision demonstration output
- raw failure-and-resumption output
- raw replay-with-adapters-disabled output
- raw rebuild and integrity-verification output
- deterministic clean-run comparison evidence
- isolated-tree validation evidence
- a machine-readable review manifest containing task ID, branch, HEAD, validations, results, timestamps, and checksums
- ZIP member listing, SHA-256 checksum, self-check results, and ZIP integrity evidence

### Verification-package quality rules

The package must:

- contain raw outputs rather than summary claims alone;
- include all tracked and untracked TASK-003 changes in the patch;
- identify skipped or inapplicable checks with justification;
- preserve final failed evidence if any required validation fails;
- distinguish fixture/provider state, authoritative repository state, derived state, and generated review artifacts;
- prove fixture execution did not use the network;
- prove replay did not invoke adapters;
- prove artifact bytes remained unchanged;
- exclude credentials, tokens, caches, unrelated absolute paths, and local runtime data;
- avoid recursive package inclusion;
- be reproducible through a documented repository command;
- validate its manifest, member checksums, and ZIP integrity.

A passing summary without underlying evidence is insufficient.

## Codex Execution and Git Constraints

Codex is explicitly authorized to prepare the task branch for this task.

Starting from the repository supplied by the operator, Codex must:

1. verify it is in the RFI-1 repository;
2. verify the only authorized pre-existing untracked task input is `tasks/TASK-003.md`;
3. verify tracked files and the staged index are otherwise clean;
4. update local knowledge of `origin/main` without rewriting local work;
5. ensure local `main` can be fast-forwarded to `origin/main`;
6. create and switch to:
   `agent/TASK-003-fixture-backed-acquisition-engine`
7. preserve `tasks/TASK-003.md` across the branch transition;
8. confirm the branch starts from the current `origin/main`;
9. implement TASK-003 only on that branch.

If the branch already exists, Codex must stop unless it can prove that it is the intended clean TASK-003 branch based on current `origin/main`. It must not reset, delete, overwrite, or reuse an ambiguous branch.

If branch creation or switching is blocked by the environment, stop and report the exact blocker. Do not implement on `main`.

Codex may perform only the branch preparation described above. It must not:

- commit;
- push;
- merge;
- rebase;
- reset;
- delete branches;
- clean the repository;
- stash unrelated changes;
- modify Git configuration;
- create a pull request.

## Additional Execution Constraints

- Read the governing documents, TASK-002 code, and applicable ADRs before implementation.
- Treat `tasks/TASK-003.md` as an authorized task input, not an unexpected dirty file.
- Stop on any other unexpected pre-existing change.
- Work only inside the RFI-1 repository.
- Do not use live network access for implementation demonstrations or tests.
- Do not introduce real credentials.
- Do not silently weaken TASK-002 invariants.
- Do not broaden scope into the next live-source task.
- Prefer framework-level engineering judgment over file-by-file instructions.
- Produce the complete verification package even when all checks pass.

## Expected Handoff

At completion, report:

- branch and HEAD;
- confirmation that the task branch was created from current `origin/main`;
- concise implementation summary;
- engine and adapter contracts introduced;
- fixture behaviors represented;
- run lifecycle and failure model;
- checkpoint, idempotency, replay, and rebuild results;
- focused and full validation results;
- review directory and ZIP path;
- ZIP size, SHA-256, and integrity result;
- changed-file count;
- staged and unstaged state;
- known limitations and deferred work;
- explicit confirmation that no live provider, downstream knowledge, AI, or projection capability was implemented;
- explicit confirmation that no commit, push, merge, rebase, reset, branch deletion, cleanup, or Git-configuration change was performed.
