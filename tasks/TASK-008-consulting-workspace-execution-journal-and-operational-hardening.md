# TASK-008 — Consulting Workspace, Execution Journal, and Operational Hardening

## Status

Ready

## Architectural Milestone

Establish the durable consulting workspace for RFI-1.

The workspace becomes the primary operator-facing environment for conducting, reviewing, reproducing, and extending investigations performed by the repository.

The workspace must integrate the existing acquisition, knowledge, retrieval, and intelligence subsystems without coupling to their internal implementations.

## Purpose

RFI-1 can now:

- acquire evidence;
- derive structured knowledge;
- retrieve governed evidence;
- perform bounded source-grounded intelligence.

These capabilities currently operate primarily as architectural demonstrations and inspection tools.

TASK-008 must transform them into a reusable consulting workflow.

The workspace should allow an operator to return days or months later and understand:

- what question was investigated;
- how it was answered;
- what evidence was used;
- what remained uncertain;
- what changed over time.

## Required Capabilities

### Investigation Workspace

The workspace must support durable investigations.

An investigation represents one consulting problem.

At minimum an investigation contains:

- identity;
- title;
- purpose;
- optional customer or engagement metadata;
- creation and update history;
- execution history;
- operator notes;
- exported deliverables;
- status.

The storage model is an implementation decision.

### Execution Journal

Every execution becomes a durable journal entry.

The journal should capture:

- question;
- planner output;
- retrieval activity;
- evidence packages;
- intelligence results;
- execution trace;
- timing;
- stopping reason;
- failures;
- completion status.

Journal entries are append-only.

Corrections create new history rather than rewriting prior executions.

### Workspace Navigation

The operator must be able to:

- create investigations;
- reopen investigations;
- browse execution history;
- compare executions;
- inspect evidence;
- inspect provenance;
- inspect claim mappings;
- inspect uncertainty;
- inspect execution traces.

Codex may choose the interaction model.

This task does not prescribe CLI, TUI, or browser architecture.

### Operator Corrections

Operators must be able to record:

- observations;
- corrections;
- follow-up questions;
- interpretation notes;
- investigation conclusions.

Operator annotations remain distinct from repository evidence and model inference.

### Repeatability

An operator must be able to rerun an investigation and determine:

- what changed;
- what remained identical;
- whether evidence changed;
- whether retrieval changed;
- whether reasoning changed;
- whether conclusions changed.

### Operational Metrics

Capture operational metadata including:

- execution duration;
- retrieval duration;
- planning duration;
- model duration;
- evidence volume;
- retrieval counts;
- iteration counts;
- model usage;
- token usage where available;
- estimated cost where available.

The workspace should support later reporting without changing historical executions.

### Export

Allow exporting an investigation as a bounded consulting artifact.

The export format is an implementation decision.

It should preserve:

- conclusions;
- uncertainty;
- provenance;
- evidence references;
- operator notes.

### Backup and Restore

Workspace state must support:

- backup;
- restore;
- integrity verification.

## Architectural Constraints

- Workspace depends on public subsystem contracts only.
- Workspace does not own evidence.
- Workspace does not own derived knowledge.
- Workspace does not own retrieval indexes.
- Workspace does not own intelligence results.
- Workspace references them.
- Operator annotations remain separate from source evidence, derived knowledge, and model inference.
- Workspace history must remain append-only.
- Historical executions must remain intelligible after implementation changes.
- Operational logs must not expose credentials or unnecessary source content.
- Durable workspace state must remain independently backupable and restorable.

## Functional Proof

Demonstrate:

1. Create investigation.
2. Ask consulting question.
3. Execute complete pipeline.
4. Persist execution.
5. Close workspace.
6. Reopen workspace.
7. Inspect evidence.
8. Add operator note.
9. Re-execute investigation.
10. Compare executions.
11. Export investigation.
12. Backup workspace.
13. Restore workspace.
14. Verify restored integrity.

## Logging and Journal Proof

Demonstrate that the workspace can answer:

- what executions occurred;
- when they occurred;
- what configuration was used;
- how long each stage took;
- what evidence and results were referenced;
- what failed and why;
- what model usage, token usage, and estimated cost were recorded when available;
- what changed between two executions.

The proof must distinguish:

- durable execution journal;
- operator annotations;
- subsystem evidence and results;
- transient diagnostic output.

## Failure Semantics

Demonstrate behavior for:

- interrupted execution;
- retrieval failure;
- planner failure;
- model failure;
- corrupted workspace;
- missing evidence;
- stale retrieval indexes;
- backup failure;
- restore failure;
- partial journal write;
- invalid operator annotation.

Workspace history must remain recoverable and failures must remain visible.

## Validation Expectations

Validation must include:

- workspace lifecycle;
- journal integrity;
- comparison workflow;
- backup and restore;
- export;
- operator annotation;
- rerun behavior;
- operational metrics;
- logging and failure visibility;
- repository-wide validation;
- documentation validation;
- baseline validation;
- secret scan;
- review-package integrity.

## Required Review Package

Produce:

- implementation summary;
- architectural decisions;
- workspace walkthrough;
- execution journal examples;
- comparison examples;
- export examples;
- backup and restore proof;
- operational metrics examples;
- logging and retention evidence;
- validation results;
- known limitations;
- cumulative patch;
- Architectural Status Summary.

## Architectural Status Summary

Report status for:

- repository foundation;
- acquisition;
- immutable evidence;
- source objects;
- derived knowledge;
- governed retrieval;
- model-guided intelligence;
- consulting workspace;
- execution journal and logging;
- operational hardening.

Clearly distinguish architectural completeness from operational maturity.

## Non-Goals

This task does not require:

- multi-user collaboration;
- authentication;
- cloud deployment;
- scheduling;
- distributed execution;
- sophisticated GUI;
- production observability platform;
- billing;
- external integrations.

## Completion Standard

TASK-008 is complete when RFI-1 supports a durable consulting workflow in which investigations can be created, executed, revisited, compared, annotated, exported, backed up, and restored while preserving provenance, execution history, operational metrics, and architectural independence.
