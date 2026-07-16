# TASK-001 — Repository Bootstrap and Design Baseline

## Status

Ready

## Objective

Establish the initial RFI-1 repository as a clean, usable, reviewable engineering project and import the project’s governing design documents from the operator’s `~/Downloads` directory.

This task creates the foundation for the condensed RFI-1 implementation program. It should establish enough project structure, conventions, tooling, and documentation discipline for later framework-scale tasks without prematurely implementing the acquisition substrate or other product capabilities.

## Context

RFI-1 is an accelerated proof-of-concept and prospective MVP for a consulting-oriented Repository-First Intelligence system.

The project will follow the normal governed Codex workflow, but the implementation is intentionally condensed into approximately six to eight substantial tasks rather than dozens of narrowly prescriptive tasks. Each task therefore gives Codex responsibility for appropriate engineering decisions within explicit architectural boundaries and requires a complete verification package suitable for independent review.

The governing design baseline currently exists as Markdown files in the operator’s `~/Downloads` directory. These files define the project philosophy, architecture, design principles, acquisition POC guidance, roadmap, and initial task framing. They must be brought into the repository as authoritative project inputs before implementation proceeds.

## Governing Principles

The work must preserve the intent of the supplied RFI design baseline, including:

- the repository is the primary product and durable system of record;
- evidence precedes interpretation;
- provenance is mandatory;
- immutable source evidence and replay are first-class concerns;
- acquisition, knowledge development, and projection remain architecturally separate;
- abstractions should emerge from observed source behavior;
- commercial services and AI models may accelerate development but must not own repository identity or semantics;
- this task establishes a framework and development foundation, not speculative product implementation.

## Required Source Documents

Codex must locate the following files in `~/Downloads`:

- `RFI_MANIFESTO.md`
- `README.md`
- `DESIGN_PRINCIPLES.md`
- `ACQUISITION_POC_GUIDANCE.md`
- `TASKS.md`
- `ROADMAP.md`
- `ARCHITECTURE.md`

The task must fail closed if any required source file is absent, unreadable, ambiguous, or duplicated in a way that prevents a deterministic selection.

Codex must not silently recreate, approximate, omit, or substitute a missing design document.

## Scope

### 1. Import the authoritative design baseline

Copy the required source documents from `~/Downloads` into appropriate repository locations.

Normalize downloaded duplicate-name suffixes as follows:


Codex may choose a coherent documentation layout, but the governing documents must remain easy to locate from the repository root and their authority must be clear.

The imported `README.md` should remain the repository’s primary entry point unless a compelling repository-level reason requires a narrowly scoped adjustment.

### 2. Preserve document content and provenance

Preserve the substantive content of every source document.

Permitted changes are limited to those needed to make the imported baseline coherent inside the repository, such as:

- filename normalization;
- repairing internal links affected by relocation or renaming;
- correcting references to obsolete task numbering where required to make the repository internally consistent;
- adding narrowly scoped repository navigation or document-status notes.

Any intentional content change must be individually documented in the verification package with the source text, destination text, and rationale.

Do not broadly rewrite, consolidate, stylistically normalize, or reinterpret the governing documents during this task.

### 3. Establish repository conventions

Create the minimum coherent repository structure and engineering conventions needed for subsequent RFI-1 work.

Codex is responsible for choosing an appropriate framework, layout, package structure, dependency-management approach, test structure, and developer commands, subject to these constraints:

- the repository must support incremental implementation and clean review boundaries;
- generated, local, credential-bearing, downloaded, and runtime data must not be accidentally committed;
- project code, tests, documentation, fixtures, scripts, and review artifacts must have clear homes;
- routine developer workflows must be discoverable from repository documentation;
- the baseline must be suitable for a small but production-minded Python project unless the imported design documents provide a stronger contrary constraint;
- the design must avoid premature implementation of the acquisition substrate defined for later tasks.

### 4. Establish baseline quality gates

Provide executable baseline checks appropriate to the chosen project structure.

At minimum, the repository must have documented commands for:

- environment or dependency setup;
- automated tests;
- linting and formatting validation;
- static analysis or type checking where appropriate;
- package or application import validation;
- verification-package generation or assembly.

A task is not complete merely because the repository is empty enough for checks to pass. Baseline checks must exercise meaningful repository setup and document-import behavior.

### 5. Reconcile the condensed task model

The imported `TASKS.md` currently reflects an earlier task-numbering concept. Reconcile it with the decision to execute RFI-1 in approximately six to eight framework-scale tasks.

This task should establish only the high-level roadmap needed to avoid contradictory numbering or scope. It must not over-specify later implementation details.

The detailed ticket for each later task remains authoritative when created.

### 6. Document engineering decisions

Record material bootstrap decisions in a durable repository document or decision log.

The record must explain:

- the chosen repository and package layout;
- dependency and tooling choices;
- documentation placement;
- local/runtime data boundaries;
- verification-package conventions;
- significant alternatives considered;
- why the selected approach is appropriate for an accelerated POC that may evolve into an MVP.

## Non-Goals

This task must not implement substantive RFI acquisition capabilities, including:

- source registry behavior;
- retrievers or provider adapters;
- object-store semantics;
- retrieval ledger behavior;
- document indexing;
- replay processing;
- observations, derivations, enrichments, claims, or projections;
- LLM, embedding, vector-database, or RAG integration;
- production deployment infrastructure;
- consulting reports or user-facing intelligence outputs.

Small test fixtures or placeholders are acceptable only when needed to validate the repository foundation. They must not become speculative domain implementations.

## Architectural Boundaries

Codex has discretion over implementation details, but the resulting foundation must:

- treat the imported design documents as governing inputs;
- preserve separation between project code, repository metadata, immutable evidence, mutable indexes, and generated outputs;
- avoid coupling repository identity to a commercial provider, AI model, or storage vendor;
- support future deterministic acquisition and replay;
- remain understandable and operable by a single technical owner;
- favor explicit, inspectable behavior over framework magic;
- avoid unnecessary abstraction before real source behavior has been observed.

## Acceptance Criteria

TASK-001 is complete only when all of the following are true:

1. A clean RFI-1 repository foundation exists and is usable from a fresh checkout.
2. All seven required design files were deterministically located in `~/Downloads` and imported.
3. `DESIGN_PRINCIPLES.md` and `TASKS.md` were imported using their stable source filenames.
4. The substantive content of the imported design baseline is preserved.
5. Every intentional content change is explicitly accounted for.
6. The repository has a coherent structure for code, tests, documentation, fixtures, scripts, local/runtime data, and review artifacts.
7. Local data, credentials, generated files, caches, and review outputs are appropriately excluded from version control unless intentionally retained.
8. Setup and routine development commands are documented and executable.
9. Baseline tests and quality gates run successfully from the documented environment.
10. The condensed six-to-eight-task execution model is reflected without prematurely defining implementation details.
11. Material bootstrap decisions and alternatives are durably documented.
12. No substantive acquisition or downstream intelligence capability has been implemented.
13. A complete TASK-001 verification package has been generated and validated.
14. The working tree and branch state are explicitly reported at handoff.

## Required Verification Package

Produce a self-contained review package under a predictable generated-artifact location and also provide a ZIP archive of that package.

The package must allow a reviewer to understand and assess the task without first exploring the repository manually.

At minimum, include:

- `executive-summary.md` — concise statement of outcome, scope, and review conclusion;
- `implementation-summary.md` — what was created or changed and why;
- `architecture-decisions.md` — material decisions, alternatives considered, tradeoffs, and selected rationale;
- `source-document-manifest.md` — required source paths, destination paths, filename normalization, sizes, and checksums;
- `document-change-audit.md` — all intentional content differences between each source and destination, or an explicit statement that none exist;
- `repository-tree.txt` — relevant repository structure after implementation;
- `changed-files.txt` — complete task-scoped changed-file inventory;
- `git-status.txt` — exact repository status at package creation;
- `git-diff.patch` — complete unstaged and staged task diff in reviewable form;
- `validation-commands.md` — exact commands executed, working directory, and environment assumptions;
- captured output for every required test, lint, format, type, import, and packaging check;
- `fresh-checkout-validation.md` — evidence that documented setup and validation work from a clean checkout or equivalent isolated environment;
- `known-limitations.md` — limitations, deferred work, risks, and technical debt;
- `review-manifest.json` or equivalent machine-readable manifest containing task ID, branch, HEAD, timestamps, commands, outcomes, and artifact checksums;
- ZIP integrity evidence and a listing of ZIP contents.

### Verification requirements

The verification package must:

- be generated from the final task state;
- contain exact command output rather than paraphrased claims;
- identify skipped or inapplicable checks and justify each one;
- record failures as failures rather than filtering or rewriting them;
- distinguish source-document copies from intentionally edited destination documents;
- include cryptographic hashes sufficient to verify source-to-destination identity where no content change was intended;
- prove that required source documents were not silently omitted;
- be reproducible through a documented repository command or script;
- exclude credentials, secrets, private tokens, and unrelated local information;
- avoid depending on uncommitted external files after package creation.

A green summary without the underlying evidence is insufficient.

## Codex Execution Constraints

- Work only within the prepared task branch and the RFI-1 repository, except for read access to the required files in `~/Downloads`.
- Do not create or switch branches unless the environment and operator instructions explicitly permit it.
- Do not commit, push, merge, delete branches, or perform cleanup unless separately instructed.
- Do not modify unrelated repositories or user files.
- Do not overwrite or delete the source documents in `~/Downloads`.
- Do not infer approval from an apparently clean result; produce the complete verification package.
- Stop and report a blocker if a required source document cannot be deterministically imported.
- Prefer framework-level engineering judgment over ticket-driven file-by-file implementation.
- Keep all changes within TASK-001 scope.

## Expected Handoff

At completion, report:

- branch name and HEAD;
- concise implementation summary;
- imported source-to-destination mapping;
- intentional document changes, if any;
- validation commands and outcomes;
- verification-package directory and ZIP path;
- ZIP size and integrity result;
- changed-file count;
- staged and unstaged state;
- known limitations or blockers;
- explicit confirmation that no commit, push, merge, branch deletion, or cleanup was performed.
