# TASK-002 — Acquisition Substrate and Core Repository Contracts

## Status

Ready

## Objective

Establish the durable acquisition substrate for RFI-1.

This task must define and implement the repository-owned contracts and persistence behavior required to receive, identify, preserve, audit, index, and replay acquired source documents. It creates the stable kernel on which later fixture-backed acquisition and real source adapters will depend.

The implementation should be substantial enough to prove the substrate’s invariants through executable tests, but it must not yet implement a production source adapter, external-provider integration, exploratory acquisition, knowledge extraction, or projection capability.

## Context

RFI-1 is a Repository-First Intelligence system. Its enduring asset is the repository state—not an external provider, AI model, user interface, or transient processing pipeline.

TASK-001 established the project foundation and authoritative design baseline. TASK-002 now moves into the first substantive product capability: the acquisition substrate.

The condensed implementation program intentionally gives Codex responsibility for subsystem-level engineering decisions. This ticket therefore defines architectural outcomes, invariants, and verification obligations rather than prescribing classes, functions, files, database tables, or algorithms.

The governing project documents include:

- `RFI_MANIFESTO.md`
- `DESIGN_PRINCIPLES.md`
- `ACQUISITION_POC_GUIDANCE.md`
- `ARCHITECTURE.md`
- `ROADMAP.md`
- `TASKS.md`
- applicable repository decision records and development guidance

Codex must read the governing documents before selecting an implementation approach.

## Governing Principles

The implementation must preserve these principles:

1. The repository is the system of record.
2. Evidence precedes interpretation.
3. Source artifacts are immutable.
4. Retrieval history is append-only.
5. Provenance is mandatory and inspectable.
6. Repository identity must not depend on a provider, filename, object layout, or mutable URL.
7. Mutable indexes are derived state and must be rebuildable.
8. Stored artifacts define the replay boundary.
9. Repeated operations must be idempotent where the same evidence and identity are presented again.
10. Durable success must precede checkpoint advancement.
11. Source-specific behavior belongs outside the repository substrate.
12. Acquisition, knowledge development, and projection remain architecturally separate.
13. Commercial services may accelerate acquisition but must not own repository semantics.
14. The subsystem must remain understandable and operable by a single technical owner.

## Required Outcomes

### 1. Core acquisition contracts

Define coherent repository-facing contracts for the concepts needed by later acquisition engines and adapters.

The contracts must be sufficient to represent, at minimum:

- governed source identity and source configuration;
- deterministic discovery candidates;
- retrieval attempts and outcomes;
- immutable acquired artifacts;
- document identity independent of acquisition provider;
- complete provenance;
- append-only retrieval history;
- mutable document-discovery or access indexes;
- replay inputs and replay results;
- durable checkpoints or equivalent source progress state.

Codex may choose names, boundaries, and representations. The contracts must reflect repository semantics rather than the quirks of an anticipated SEC or Investor Relations source.

The design must distinguish clearly between:

- source identity;
- document identity;
- artifact identity;
- retrieval-attempt identity;
- provider-specific identifiers;
- mutable discovery metadata;
- immutable evidence.

### 2. Immutable artifact storage

Implement the repository-owned mechanism for preserving exact source artifacts.

The substrate must:

- preserve acquired bytes without mutation;
- calculate and retain integrity information;
- prevent silent overwrite or replacement;
- support deterministic retrieval of stored evidence;
- preserve sufficient media-type and provenance metadata;
- detect conflicting attempts to reuse an existing artifact identity;
- remain independent of any particular commercial provider;
- avoid making the physical object layout part of the public domain contract.

The implementation may use a filesystem-backed store for the POC, but the architecture must preserve the distinction between artifact semantics and storage layout.

### 3. Append-only retrieval ledger

Implement durable acquisition-history recording.

The ledger must make retrieval activity auditable and must preserve failed, skipped, duplicate, and successful outcomes where they are materially meaningful.

At minimum, ledger records must support answering:

- which governed source initiated the activity;
- what candidate or document was involved;
- when the attempt occurred;
- which retrieval mechanism or adapter was used;
- what outcome occurred;
- what artifact, if any, was durably stored;
- what checkpoint effect, if any, followed;
- what diagnostic evidence is available for failure analysis.

Previously recorded history must not be rewritten as part of normal operation.

### 4. Rebuildable document index

Implement a mutable index that provides practical document access without requiring Git-history traversal or ledger scanning for routine use.

The index must:

- contain only derived or reconstructable state;
- preserve stable repository-owned document identity;
- point to immutable artifacts and relevant provenance;
- support deterministic rebuild from authoritative repository records;
- detect or report inconsistent repository state rather than silently repairing ambiguity;
- avoid becoming the sole owner of information required for replay or audit.

A complete loss of the mutable index must not cause loss of evidence or retrieval history.

### 5. Source registry and governed source profiles

Implement the minimum source-registry behavior needed to define deterministic sources for later tasks.

The registry must:

- assign stable internal source identity;
- separate internal identity from provider-specific names or URLs;
- support deterministic source configuration;
- make source enablement and relevant acquisition policy explicit;
- validate configurations before use;
- reject ambiguous or invalid source definitions;
- remain extensible to both provider-backed SEC acquisition and direct Investor Relations retrieval without embedding either source type into the substrate.

Do not build real external-source retrievers in this task.

### 6. Durable checkpoint semantics

Establish and verify safe checkpoint or source-progress behavior.

The implementation must ensure that progress does not advance until all required durable effects have succeeded.

Checkpoint behavior must be:

- source-scoped;
- explicit;
- auditable;
- compatible with repeated execution;
- safe under partial failure;
- reconstructable or diagnosable from repository state.

Codex must document the selected checkpoint model, its guarantees, and alternatives considered.

### 7. Replay boundary

Implement the repository-side capability needed to replay stored acquisition evidence without revisiting external sources.

Replay in this task means that authoritative repository records and stored artifacts can regenerate the mutable document index and equivalent repository-derived acquisition state.

Replay must not:

- contact an external source;
- require a commercial provider;
- reinterpret document meaning;
- create observations, claims, or projections.

### 8. Transaction and failure behavior

Define and implement coherent behavior for partial failure across artifact storage, ledger recording, index updates, and checkpoint advancement.

The implementation must make the ordering and durability guarantees explicit.

Tests must demonstrate behavior under representative failures, including failures that occur:

- before artifact durability;
- after artifact durability but before ledger completion;
- before index update;
- before checkpoint advancement;
- during replay or index rebuild.

The substrate must fail observably. It must not convert uncertain or partially durable outcomes into apparent success.

### 9. Repository inspection and operator workflow

Provide documented commands or interfaces that allow an operator to:

- validate repository acquisition state;
- inspect source definitions;
- inspect stored-artifact metadata;
- inspect retrieval history;
- rebuild the mutable index;
- verify artifact integrity;
- run the complete TASK-002 validation suite.

A full user-facing application or polished CLI is not required. The operator workflow must nevertheless be explicit, repeatable, and useful for later tasks.

### 10. Durable design record

Record the material design decisions made in this task.

The design record must address:

- identity model;
- artifact immutability and integrity;
- ledger representation and append-only enforcement;
- index representation and rebuild strategy;
- source-registry boundary;
- checkpoint ordering;
- replay boundary;
- transaction and partial-failure model;
- concurrency assumptions for the POC;
- filesystem and portability assumptions;
- alternatives considered;
- known limits between the POC implementation and a future MVP.

## Required Demonstration

Provide an executable, deterministic demonstration using local synthetic or fixture data that proves the substrate can:

1. register a governed source;
2. accept a deterministic candidate and acquisition result;
3. durably preserve an exact artifact;
4. append retrieval history;
5. create or update the rebuildable document index;
6. advance source progress only after required durable success;
7. repeat the same operation idempotently;
8. detect a materially conflicting operation;
9. remove and rebuild the mutable index from authoritative repository state;
10. replay without external network access;
11. verify stored artifact integrity;
12. expose sufficient evidence to diagnose a simulated failed retrieval.

This demonstration validates the substrate only. It must not become a general acquisition engine or source adapter.

## Non-Goals

TASK-002 must not implement:

- SEC-API.io integration;
- native SEC EDGAR retrieval;
- Investor Relations retrievers;
- network crawling or scraping;
- source-specific pagination logic;
- broad adapter frameworks based on imagined future sources;
- exploratory web search;
- LLM calls;
- embeddings or vector search;
- OCR or text extraction pipelines;
- observations, derivations, enrichments, claims, positions, or projections;
- consulting briefs, reports, dashboards, or Q&A;
- production cloud storage;
- distributed processing;
- multi-user authorization;
- production deployment infrastructure.

Do not introduce speculative abstractions solely to anticipate these deferred capabilities.

## Architectural Boundaries

Codex has discretion over implementation details, subject to these boundaries:

- domain semantics must remain independent of storage-provider and acquisition-provider details;
- source-specific code must remain outside the core substrate;
- authoritative records and derived indexes must be clearly distinguished;
- immutable artifacts must never be edited in place;
- append-only history must not be emulated by mutable current-state records alone;
- index rebuild and replay must not require external network access;
- public contracts must not expose physical object-layout assumptions unnecessarily;
- internal identifiers must remain stable if acquisition providers change;
- artifact integrity and provenance must be first-class data;
- the design should suit a single-owner POC while leaving a credible path to MVP hardening;
- abstractions must be justified by current task behavior and evidence;
- dependencies must be proportionate and documented;
- existing TASK-001 validation and documentation guarantees must remain intact.

## Acceptance Criteria

TASK-002 is complete only when all of the following are true:

1. Core acquisition contracts are implemented and documented.
2. Source, document, artifact, retrieval-attempt, and provider identity are unambiguously separated.
3. A governed source registry supports deterministic validated source definitions.
4. Exact artifact bytes are stored immutably with verifiable integrity metadata.
5. Conflicting artifact writes are rejected or surfaced without corrupting existing evidence.
6. Retrieval history is durable, append-only, and records materially meaningful outcomes.
7. The document index is useful for routine access and completely rebuildable from authoritative state.
8. Loss of the mutable index does not lose evidence, provenance, retrieval history, or replayability.
9. Checkpoints advance only after required durable success and behave safely under partial failure.
10. Repeated equivalent operations are idempotent.
11. Materially conflicting operations are detected and reported.
12. Replay and index rebuild operate without external network access.
13. Representative partial-failure cases are tested and fail observably.
14. Stored-artifact integrity can be independently verified.
15. An executable fixture-backed demonstration proves the required substrate lifecycle.
16. Operator workflows for validation, inspection, integrity checking, and index rebuild are documented.
17. Material design choices and alternatives are recorded durably.
18. Existing repository quality gates continue to pass.
19. No real external retriever, downstream knowledge model, AI integration, or projection capability is implemented.
20. A complete TASK-002 verification package is generated and independently auditable.
21. The final branch and working-tree state are explicitly reported.

## Verification Requirements

Verification must go beyond unit-level happy paths.

At minimum, validation must include:

- focused tests for each core invariant;
- integration tests covering the complete fixture-backed substrate lifecycle;
- idempotency tests;
- duplicate and conflict tests;
- immutable-artifact enforcement tests;
- append-only ledger tests;
- index-loss and full-rebuild tests;
- replay-without-network tests;
- checkpoint ordering and partial-failure tests;
- corruption or integrity-mismatch detection;
- malformed source-registry input tests;
- deterministic results across repeated clean runs;
- complete existing-project validation;
- isolated-tree or clean-checkout validation;
- evidence that prohibited downstream capabilities are absent.

Where a requirement is verified structurally rather than dynamically, the package must explain the method and its limits.

## Required Verification Package

Produce a self-contained review package under the repository’s established review-artifact location and a ZIP archive of that package.

The package must be generated from the final TASK-002 state and must allow independent review without relying on the Codex handoff narrative.

At minimum, include:

- `executive-summary.md`
- `implementation-summary.md`
- `architecture-decisions.md`
- `alternatives-considered.md`
- `contract-and-identity-model.md`
- `durability-and-failure-model.md`
- `source-registry-summary.md`
- `artifact-store-summary.md`
- `retrieval-ledger-summary.md`
- `document-index-summary.md`
- `checkpoint-and-replay-summary.md`
- `fixture-demonstration.md`
- `known-limitations.md`
- `deferred-work.md`
- `repository-tree.txt`
- `changed-files.txt`
- `git-status.txt`
- complete task-scoped `git-diff.patch`
- exact `validation-commands.md`
- captured output for every focused and project-wide validation command
- captured output for the fixture-backed demonstration
- captured output for index deletion and rebuild
- captured output for artifact-integrity verification
- captured output for representative failure-injection tests
- isolated-tree or clean-checkout validation evidence
- a machine-readable review manifest with task ID, branch, HEAD, commands, outcomes, timestamps, and artifact checksums
- ZIP member listing, ZIP checksum, and ZIP integrity evidence

### Verification-package quality rules

The package must:

- contain raw command output, not only summaries;
- identify every skipped or inapplicable check and explain why;
- retain failed validation evidence if failures occurred during final verification;
- distinguish authoritative state from generated indexes and review artifacts;
- prove that replay and index rebuild did not use the network;
- prove that artifact bytes remained unchanged;
- document how the patch includes untracked files, if applicable;
- exclude credentials, secrets, private tokens, unrelated local paths, and runtime caches;
- avoid recursive inclusion of review packages;
- be reproducible through a documented repository command;
- validate its own manifest, member checksums, and ZIP integrity.

A green executive summary without the supporting evidence is insufficient.

## Codex Execution Constraints

- Work only within the prepared TASK-002 branch and the RFI-1 repository.
- Read the governing design documents before implementation.
- Do not create or switch branches unless explicitly authorized.
- Do not commit, push, merge, delete branches, or perform cleanup.
- Do not modify unrelated repositories or user files.
- Do not use network access as part of the fixture demonstration, replay, or validation.
- Do not introduce real provider credentials or configuration.
- Do not implement later-task capabilities merely because they appear convenient.
- Do not silently weaken an invariant to simplify implementation.
- Stop and report a blocker if the repository state or governing documents are materially inconsistent.
- Prefer framework-level engineering judgment over ticket-driven file-by-file implementation.
- Produce the complete verification package even when all checks pass.

## Expected Handoff

At completion, report:

- branch name and HEAD;
- concise implementation summary;
- major contracts and repository records introduced;
- identity, durability, checkpoint, and replay decisions;
- fixture demonstration result;
- focused and full validation outcomes;
- review directory and ZIP path;
- ZIP size, checksum, and integrity result;
- changed-file count;
- staged and unstaged state;
- known limitations and deferred work;
- explicit confirmation that no external source integration or downstream knowledge capability was implemented;
- explicit confirmation that no commit, push, merge, branch deletion, or cleanup was performed.
