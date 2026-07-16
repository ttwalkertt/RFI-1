# TASK-005 — Independent Source-Object and Derived-Knowledge Subsystems

## Status

Complete

## Architectural Milestone

Establish two independently evolvable repository subsystems:

1. a **source-object subsystem** that makes acquired evidence structurally addressable and inspectable; and
2. a **derived-knowledge subsystem** that represents entities, observations, relationships, and other meaning derived from that evidence.

The two subsystems must remain distinct in authority, lifecycle, storage assumptions, rebuild semantics, and optimization path. They are connected through stable provenance and derivation contracts rather than shared internal representations.

## Purpose

RFI-1 currently preserves immutable acquired evidence and repository-owned acquisition state.

This task advances the repository from evidence preservation to governed interpretation while preserving the boundary between:

- what the source artifact contains; and
- what the system derives from that source.

The task must create a durable architectural foundation for later retrieval, browsing, LLM reasoning, and consulting workflows.

## Required Capabilities

### Source-Object Subsystem

The source-object subsystem must make acquired evidence structurally addressable.

It must support, at minimum:

- stable identity for source-derived structures;
- navigation from repository document and artifact to source objects;
- bounded source context;
- provenance back to exact immutable artifact content;
- deterministic reconstruction where practical;
- integrity validation;
- operator inspection;
- independent lifecycle and rebuild behavior.

The exact source-object vocabulary is an implementation decision, but the resulting model must adequately represent the structure needed for later retrieval and provenance.

### Derived-Knowledge Subsystem

The derived-knowledge subsystem must represent meaning inferred, normalized, or resolved from source evidence.

It must support, at minimum:

- independently persisted derived objects;
- stable repository-owned identity;
- entities, observations, assertions, relationships, or equivalent domain concepts;
- derivation records;
- provenance to supporting source objects;
- versioning or equivalent history;
- correction and supersession;
- explicit uncertainty or status where interpretation is not definitive;
- independent lifecycle and rebuild behavior;
- operator inspection.

The exact ontology, schema, and extraction strategy are implementation decisions.

## Architectural Constraints

- Source objects and derived knowledge are separate classes of repository data.
- Neither subsystem may depend on the internal storage schema of the other.
- Dependencies flow from derived knowledge toward stable source-object contracts, not the reverse.
- Immutable artifacts remain the authoritative evidence layer.
- Derived objects must never be presented as if they were source facts.
- Provenance must remain intact across rebuild, replacement, or optimization of either subsystem.
- Each subsystem must be independently replaceable, rebuildable, testable, and optimizable.
- Separate storage engines, indexing strategies, caching approaches, or persistence models must remain possible.
- The task must not prematurely implement the final retrieval-orchestration, LLM-answering, or consulting-workspace layer.
- Any model-assisted derivation must be explicit, reproducible where possible, and distinguishable from deterministic processing.

## Functional Proof

Demonstrate a bounded end-to-end path using the real TASK-004 SEC corpus:

```text
immutable artifact
    ↓
source objects
    ↓
derived entities / observations / relationships
    ↓
provenance back to supporting source objects and artifact
```

The demonstration must show both directions:

- derived object → supporting source object(s) → immutable artifact;
- source object → associated derived object(s).

The bounded corpus should be large enough to expose real structural and provenance behavior while remaining reviewable.

## Independent Evolution Proof

The implementation must provide evidence that:

- source objects can be rebuilt without requiring derived knowledge to be authoritative;
- derived knowledge can be rebuilt or replaced from stable source-object contracts;
- identity and provenance remain valid across those operations;
- the two subsystems do not share hidden persistence assumptions;
- a future implementation could optimize either subsystem independently.

## Failure and Ambiguity Semantics

The design must explicitly address:

- malformed or unsupported source structure;
- incomplete extraction;
- ambiguous entity resolution;
- conflicting derived assertions;
- derivation failure;
- stale or superseded derived knowledge;
- provenance loss or inconsistency;
- partial rebuild failure.

Failures must remain visible and auditable. The system must not silently convert uncertainty into fact.

## Operator Inspection

Provide a console-level inspection path sufficient to verify:

- source-object inventory and identity;
- source-object linkage to documents and artifacts;
- derived-object inventory and status;
- provenance paths;
- correction or supersession state;
- rebuild results and integrity.

This is an inspection capability, not the final TASK-006 source browser.

## Validation Expectations

Validation must include:

- deterministic identity tests;
- provenance integrity tests;
- rebuild tests for both subsystems;
- correction or supersession tests;
- ambiguity or conflict tests;
- failure-path tests;
- bounded real-corpus demonstration;
- repository-wide validation;
- documentation and manifest validation;
- secret scan;
- review-package integrity.

## Required Review Package

Produce a complete TASK-005 review package containing:

- task ticket;
- implementation summary;
- architectural decisions and tradeoffs;
- cumulative task-scoped patch and changed-file inventory;
- validation commands and complete results;
- bounded corpus description;
- source-object inventory;
- derived-object inventory;
- provenance examples;
- independent rebuild evidence;
- failure and ambiguity evidence;
- known limitations and deferred work;
- Git branch, base, HEAD, and commit state;
- package manifest and integrity verification.

## Architectural Status Summary

Conclude with a high-level functional architecture status that allows the human architect to regain an accurate mental model without reading every implementation artifact.

For each major subsystem, report:

- purpose;
- current status: Complete, Usable with Limitations, Provisional, Blocked, or Not Started;
- important boundaries;
- known limitations;
- effect of TASK-005;
- next unresolved architectural milestone.

At minimum, address:

- repository foundation;
- acquisition substrate;
- acquisition engine;
- live SEC providers;
- immutable evidence;
- source-object subsystem;
- derived-knowledge subsystem;
- retrieval and source browser;
- model-guided intelligence;
- consulting workspace.

## Non-Goals

This task does not require:

- final vector retrieval;
- free-form query planning;
- evidence-packet orchestration;
- production LLM reasoning;
- final consulting workflows;
- broad domain completeness;
- continuous acquisition scheduling;
- performance optimization beyond what is needed to prove architectural viability.

## Completion Standard

TASK-005 is complete only when the repository contains two demonstrably independent, inspectable, and rebuildable subsystems for source objects and derived knowledge, connected through stable provenance and derivation contracts, with complete verification evidence.

Do not claim completion if the implementation only distinguishes the two concepts logically while coupling them through shared storage, lifecycle, or rebuild assumptions.
