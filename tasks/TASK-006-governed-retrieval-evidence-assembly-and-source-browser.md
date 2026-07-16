# TASK-006 — Governed Retrieval, Evidence Assembly, and Source Browser

## Status

Complete

## Architectural Milestone

Establish a governed access layer over the independent source-object and derived-knowledge subsystems created in TASK-005.

The new subsystem must:

- retrieve from both source objects and derived knowledge;
- preserve their distinct authority and semantics;
- assemble provenance-complete evidence;
- expose inspectable retrieval behavior to operators;
- provide stable machine-facing contracts for later LLM orchestration.

## Purpose

RFI-1 now contains immutable evidence, structured source objects, and independently persisted derived knowledge.

TASK-006 must make those layers usable without coupling future consumers to their storage internals.

The milestone is not merely “add vector search.” It is to establish the repository-owned retrieval, evidence, and inspection contracts that future reasoning systems and operators will rely on.

## Required Capabilities

### Governed Retrieval

The retrieval subsystem must support:

- search across source objects and derived knowledge;
- vector retrieval combined with metadata constraints;
- explicit result classes for source evidence and derived knowledge;
- stable repository-owned query and result contracts;
- deterministic filters where applicable;
- bounded retrieval;
- result deduplication;
- context expansion;
- provenance preservation;
- explicit truncation, exclusion, and coverage reporting;
- inspectable retrieval traces.

The exact retrieval architecture, embedding strategy, vector implementation, metadata model, reranking approach, and persistence choices are implementation decisions.

### Evidence Assembly

The subsystem must assemble retrieval results into bounded evidence packages suitable for later reasoning.

Evidence packages must preserve:

- source-versus-derived distinction;
- exact provenance;
- source context;
- object identity;
- retrieval rationale;
- filters and constraints applied;
- omissions, truncation, ambiguity, and coverage gaps;
- contradictions or competing derived assertions when present.

The evidence assembly contract should remain stable even if underlying search implementations change.

### Source and Knowledge Inspection

Provide a console-oriented operator experience for inspecting and navigating repository data.

The operator must be able to:

- inspect sources, documents, artifacts, and source objects;
- inspect derived entities, observations, relationships, and status;
- follow provenance from derived knowledge to source evidence;
- navigate from source objects to associated derived knowledge;
- inspect retrieval requests, results, filters, traces, and evidence packages.

Codex has latitude to choose the interaction model and presentation. The task does not prescribe a specific command hierarchy, TUI, or browser design.

The resulting experience must be practical enough for an operator to understand what the repository contains and why a retrieval result was returned.

## Architectural Constraints

- Retrieval may depend on public contracts from both TASK-005 subsystems.
- Source-object and derived-knowledge subsystems must not depend on retrieval internals.
- Retrieval must not collapse source evidence and derived interpretation into one undifferentiated result type.
- Vector similarity is a candidate-generation mechanism, not the sole definition of relevance.
- Metadata constraints and provenance must remain first-class.
- Retrieval and evidence assembly must remain replaceable and independently optimizable.
- Storage internals of source and knowledge subsystems must remain hidden behind stable contracts.
- The operator and future model-facing interfaces should rely on the same underlying access semantics.
- Retrieval failures and uncertainty must remain visible.
- No production LLM reasoning, consulting-answer generation, or autonomous query planning is required.

## Functional Proof

Demonstrate governed retrieval over the bounded real SEC corpus.

The proof must include:

- source-object retrieval;
- derived-knowledge retrieval;
- combined vector-plus-metadata retrieval;
- provenance-complete evidence assembly;
- source-context expansion;
- deduplication;
- a constrained query that returns no valid result;
- visible truncation or bounded-result behavior;
- a case involving ambiguity, conflict, or incomplete coverage.

## Inspection Proof

Demonstrate an operator workflow that can:

- browse or inspect the source-object subsystem;
- browse or inspect the derived-knowledge subsystem;
- follow provenance in both directions;
- inspect at least one retrieval trace;
- inspect a complete evidence package;
- identify why included results matched and why excluded candidates did not.

## Replaceability and Rebuild Proof

Provide evidence that:

- retrieval indexes or derived search state can be rebuilt without changing authoritative source or knowledge data;
- search implementation details can change without changing public evidence-package semantics;
- retrieval state is non-authoritative and reproducible from repository data;
- index corruption or partial rebuild failure does not silently produce authoritative-looking results.

## Failure Semantics

The design must explicitly address:

- missing or stale indexes;
- embedding or vector-generation failure;
- unsupported metadata constraints;
- incomplete source coverage;
- ambiguous entities or periods;
- contradictory derived knowledge;
- provenance inconsistency;
- evidence-budget exhaustion;
- partial retrieval failure;
- empty-result behavior.

## Validation Expectations

Validation must include:

- query contract tests;
- vector-plus-metadata retrieval tests;
- provenance integrity tests;
- evidence assembly tests;
- deterministic filtering tests;
- rebuild tests;
- failure-path tests;
- bounded real-corpus proof;
- operator inspection proof;
- repository-wide validation;
- documentation and baseline validation;
- secret scan;
- review-package integrity.

## Required Review Package

Produce a complete TASK-006 review package containing:

- task ticket;
- implementation summary;
- architectural decisions and tradeoffs;
- cumulative task-scoped patch and changed-file inventory;
- validation commands and complete results;
- retrieval contract examples;
- evidence-package examples;
- retrieval traces;
- source-browser or inspection demonstration;
- rebuild and failure evidence;
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
- source/knowledge inspection experience;
- model-guided intelligence;
- consulting workspace.

## Non-Goals

This task does not require:

- final free-form LLM query planning;
- production answer generation;
- autonomous retrieval agents;
- consulting report generation;
- broad ontology expansion;
- continuous acquisition scheduling;
- final user-facing application UX;
- premature optimization for model cost or scale.

## Completion Standard

TASK-006 is complete only when RFI-1 has a governed, inspectable, provenance-preserving retrieval and evidence subsystem over both source objects and derived knowledge, with stable machine-facing contracts and a practical console-oriented inspection experience.

Do not claim completion if the implementation only exposes raw vector results, hides provenance, collapses source and derived data, or couples retrieval to subsystem storage internals.
