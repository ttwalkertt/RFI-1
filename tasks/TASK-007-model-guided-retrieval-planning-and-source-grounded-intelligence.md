# TASK-007 — Model-Guided Retrieval Planning and Source-Grounded Intelligence

## Status

Ready

## Architectural Milestone

Establish the first governed reasoning layer over the retrieval and evidence-package contracts completed in TASK-006.

The new subsystem must:

- translate an information need into governed retrieval activity;
- consume evidence packages without depending on repository storage internals;
- produce source-grounded analysis;
- distinguish evidence, derived knowledge, and model inference;
- expose its execution, uncertainty, and stopping behavior to operators;
- remain bounded, inspectable, and replaceable.

## Purpose

RFI-1 now has:

- immutable evidence;
- structured source objects;
- independently persisted derived knowledge;
- governed retrieval;
- provenance-complete evidence packages;
- operator inspection across those layers.

TASK-007 must prove that a model can use these repository-owned contracts to perform bounded, source-grounded intelligence work.

The milestone is not to build a general autonomous agent or a polished consulting product. It is to establish the reasoning, control, and evidence-use contracts that later workflows will rely on.

## Required Capabilities

### Model-Guided Retrieval Planning

The subsystem must be able to transform a user information need into one or more structured retrieval requests using TASK-006 contracts.

It must support, at minimum:

- interpretation of the information need;
- decomposition where multiple retrieval steps are required;
- structured retrieval requests;
- result-class selection;
- metadata constraints;
- evidence-budget selection;
- bounded follow-up retrieval when evidence is insufficient;
- explicit stopping conditions;
- refusal or incomplete-answer behavior when requirements cannot be satisfied.

The exact model interface, prompt design, planner representation, orchestration approach, and execution architecture are implementation decisions.

### Evidence-Grounded Analysis

The reasoning subsystem must consume governed evidence packages and produce an analysis that clearly distinguishes:

- source evidence;
- derived repository knowledge;
- model-generated inference;
- uncertainty;
- contradiction;
- missing or insufficient evidence.

The model must not treat derived knowledge as authoritative source evidence.

The model must not make factual claims that cannot be traced to consumed evidence or explicitly labeled as inference.

### Governed Intelligence Result

The public result contract must support:

- a direct response to the information need;
- supporting evidence references;
- provenance mappings;
- identified inferences;
- uncertainty or confidence representation;
- unresolved questions or evidence gaps;
- contradiction reporting;
- retrieval and evidence-package references;
- completion, incompleteness, or refusal status.

The result contract must remain stable if the underlying model provider, planner, or prompt strategy changes.

### Inspectable Execution

Operators must be able to inspect:

- the original information need;
- planner input and structured plan;
- each retrieval request;
- each evidence package consumed;
- model-facing evidence;
- model outputs;
- evidence-to-claim mappings;
- follow-up decisions;
- iteration count;
- stopping reason;
- failures, refusals, and incomplete results.

The exact console interaction model is an implementation decision.

## Architectural Constraints

- The reasoning subsystem may depend on the public retrieval and evidence contracts from TASK-006.
- Acquisition, source-object, derived-knowledge, and retrieval subsystems must not depend on reasoning internals.
- The reasoning subsystem must not access source, knowledge, or retrieval storage directly.
- Model output is not repository evidence.
- Model inference must remain distinguishable from both source evidence and derived repository knowledge.
- Retrieval planning and answer generation must be bounded by explicit budgets and iteration limits.
- The system must fail closed when evidence provenance cannot be verified.
- The public intelligence-result contract must not expose provider-specific or model-specific implementation details.
- Model providers and orchestration strategies must remain replaceable.
- Prompts and model inputs must avoid unnecessary disclosure of repository data.
- No hidden autonomous actions are permitted.
- No production consulting workspace or long-lived research project state is required.

## Functional Proof

Demonstrate the complete bounded flow:

```text
information need
    ↓
model-guided retrieval plan
    ↓
one or more governed retrieval requests
    ↓
provenance-complete evidence packages
    ↓
source-grounded analysis
    ↓
inspectable intelligence result
```

The real-corpus proof must use the TASK-004 SEC corpus and require meaningful synthesis across more than one document or company.

The proof must include:

- at least one multi-step retrieval plan;
- both source-evidence and derived-knowledge results;
- synthesis across multiple evidence packages;
- complete claim-to-evidence mappings;
- at least one explicitly labeled inference;
- at least one reported evidence limitation;
- an explicit stopping reason.

Codex may select the exact consulting-style question, provided the proof is reviewable and genuinely exercises the architecture.

## Insufficient-Evidence Proof

Demonstrate behavior for a question the current corpus cannot fully answer.

The result must:

- avoid unsupported completion;
- identify what evidence is missing;
- distinguish known facts from inference;
- report whether additional retrieval was attempted;
- terminate within configured bounds;
- return an incomplete or refused status as appropriate.

## Contradiction and Ambiguity Proof

Demonstrate reasoning behavior when consumed evidence contains:

- contradictory derived assertions;
- ambiguous entity, period, or terminology;
- incomplete coverage.

The final result must preserve the ambiguity or contradiction rather than silently resolving it.

## Replaceability Proof

Provide evidence that:

- the public planning and intelligence-result contracts do not expose model-provider details;
- at least two reasoning implementations, model substitutes, or deterministic test doubles can operate through the same public contracts;
- valid evidence and provenance semantics remain unchanged across implementations;
- implementation-specific wording may differ without changing authority, provenance, completion status, or evidence-to-claim obligations.

This proof does not require different models to produce identical prose.

## Failure Semantics

The design must explicitly address:

- planner output that is malformed or invalid;
- unsupported retrieval constraints;
- retrieval failure;
- missing, stale, or corrupt evidence packages;
- provenance verification failure;
- model invocation failure;
- context or token budget exhaustion;
- iteration limit exhaustion;
- unsupported or unsafe requests;
- unsupported factual claims in model output;
- missing claim-to-evidence mappings;
- partial execution;
- operator-visible refusal.

Failures must remain visible and auditable.

## Runtime and Data-Governance Expectations

The design must define:

- how model access is configured;
- how credentials are kept out of repository artifacts;
- what model inputs and outputs are retained;
- what execution metadata is persisted;
- how sensitive source content is bounded;
- how offline or deterministic validation operates;
- how provider-specific behavior is isolated.

Live-model execution may be included if practical, but deterministic and offline verification is required.

## Validation Expectations

Validation must include:

- planning contract tests;
- retrieval-orchestration tests;
- claim-to-evidence mapping tests;
- provenance verification tests;
- inference-labeling tests;
- insufficient-evidence tests;
- contradiction and ambiguity tests;
- iteration and budget-bound tests;
- provider or implementation replaceability tests;
- failure-path tests;
- deterministic offline proof;
- bounded real-corpus proof;
- operator inspection proof;
- repository-wide validation;
- documentation and baseline validation;
- secret scan;
- review-package integrity.

## Required Review Package

Produce a complete TASK-007 review package containing:

- task ticket;
- implementation summary;
- architectural decisions and tradeoffs;
- cumulative task-scoped patch and changed-file inventory;
- validation commands and complete results;
- model-guided plan examples;
- retrieval requests and consumed evidence packages;
- intelligence-result examples;
- claim-to-evidence mappings;
- inference and uncertainty examples;
- insufficient-evidence proof;
- contradiction and ambiguity proof;
- replaceability proof;
- execution traces;
- failure evidence;
- runtime and retention documentation;
- known limitations and deferred work;
- Git branch, base, HEAD, and commit state;
- package manifest and integrity verification.

## Architectural Status Summary

Conclude with the required high-level Architectural Status Summary.

At minimum, report status for:

- repository foundation;
- acquisition substrate;
- acquisition engine;
- live SEC providers;
- immutable evidence;
- source-object subsystem;
- derived-knowledge subsystem;
- retrieval and evidence assembly;
- source/knowledge inspection;
- model-guided retrieval planning;
- source-grounded intelligence;
- consulting workspace.

Distinguish architectural-contract completeness from model quality or answer-quality maturity.

## Non-Goals

This task does not require:

- a polished consulting workspace;
- saved research projects;
- long-form report authoring;
- autonomous open-ended agents;
- unrestricted tool use;
- broad internet research;
- production model routing;
- cost optimization;
- broad ontology expansion;
- end-user application UX;
- continuous acquisition scheduling.

## Completion Standard

TASK-007 is complete only when RFI-1 can perform bounded, inspectable, model-guided retrieval and produce source-grounded intelligence results with complete evidence mappings, explicit inference and uncertainty, and robust insufficient-evidence behavior.

Do not claim completion if the implementation produces fluent answers without verifiable evidence mappings, hides retrieval or model execution, permits unsupported factual claims, or couples reasoning directly to repository storage internals.
