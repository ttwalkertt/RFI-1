# Repository-First Intelligence (RFI)

> **An architectural pattern for building persistent, evidence-backed AI knowledge systems.**

---

## Vision

Repository-First Intelligence (RFI) is an engineering approach for building AI systems whose primary long-term product is a curated knowledge repository rather than a collection of one-time reports or chat sessions.

RFI separates **information acquisition** from **knowledge development** and from **information presentation**. Public sources are collected into a durable repository with explicit provenance. Over time, additional processing may extract observations, derive relationships, enrich metadata, develop claims, and formulate positions. Reports, consulting briefs, dashboards, and interactive question answering are treated as projections generated from the current repository state.

The repository is intended to become the durable foundation for information ingress, knowledge development, and downstream outputs.

---

# Core Philosophy

RFI is built around a small number of architectural principles.

## Repository First

The repository is the system of record.

It preserves source evidence, provenance, and the evolving knowledge model independently of any individual report or AI conversation.

## Evidence Before Interpretation

Evidence is collected before conclusions are formed.

The architecture distinguishes between:

- source artifacts
- observations
- derivations
- enrichments
- claims
- positions

Each layer should be traceable to supporting evidence.

## Provenance Is Mandatory

Every meaningful repository object should be traceable to its origin.

The objective is not merely to answer questions, but to explain why an answer was produced.

## Acquisition and Projection Are Independent

Information acquisition operates continuously as public sources evolve.

Reports and question answering operate on demand against repository state.

Neither process depends on the timing of the other.

## Evolution Through Evidence

The repository architecture is expected to evolve.

New abstractions should emerge from observed source behavior rather than speculative design.

---

# What RFI Is Not

RFI is **not**:

- a replacement for Large Language Models
- another Retrieval-Augmented Generation (RAG) framework
- a web crawler
- an autonomous research agent
- a vector database
- a reporting engine
- a competitive intelligence product

Instead, RFI provides an architectural foundation upon which those capabilities may be built.

Commercial APIs, AI models, search systems, and storage technologies are considered replaceable implementation components rather than architectural dependencies.

---

# High-Level Architecture

```text
Public Sources
        |
        v
Acquisition
        |
        v
Repository (System of Record)
    - Source Registry
    - Immutable Artifacts
    - Retrieval Ledger
    - Document Index
        |
        +-------------------------------+
        |                               |
        v                               v
Knowledge Development            Projections
(observations, claims, etc.)     (reports, briefs, Q&A)
```

The current implementation effort is focused exclusively on the acquisition layer.

Knowledge development and projection are intentionally deferred until a representative corpus has been collected.

---

# Current Status

RFI is currently in its initial acquisition proof of concept.

The immediate objectives are:

- establish immutable source storage
- implement deterministic acquisition
- maintain append-only retrieval history
- support replay of archived artifacts
- validate the architecture against real public sources

The first reference implementation is expected to use a small number of high-value deterministic source profiles, including SEC filings and selected investor-relations sources.

The acquisition subsystem is intentionally being developed before downstream knowledge modeling.

---

# Documentation

The following documents define the project.

| Document | Purpose |
|----------|---------|
| `RFI_MANIFESTO.md` | Statement of philosophy and intent |
| `ARCHITECTURE.md` *(planned)* | Stable architectural concepts |
| `ACQUISITION_POC_GUIDANCE.md` | Design guidance and hard invariants for the acquisition proof of concept |
| `docs/deterministic-sec-form-10k-retrieval.md` | Current artifact-semantic SEC Form 10-K retrieval boundary and operator proof |
| `docs/storage_architecture_design_draft.md` | TASK-020 structured storage comparison and hybrid SQLite/file recommendation |
| `DESIGN_PRINCIPLES.md` *(planned)* | Enduring engineering principles |
| `docs/admin-preferences.md` | Browser-local admin preference contract and authority boundary |
| `docs/artifact-query-service-and-browser.md` | Repository-owned artifact query, browser, content, and preview-security contracts |
| `docs/multiple-artifact-observations.md` | Artifact, acquisition-observation, attempt identity, replay, and navigation contracts |
| `BACKLOG.md` | Unscheduled candidates, review observations, deferred improvements, and future ideas |
| `ROADMAP.md` *(planned)* | Capability roadmap |
| `TASKS.md` | Authorized implementation work and task status |
| `TASK-XXX` | Incremental implementation work items |

---

# Design Goals

The project seeks to produce an architecture that is:

- evidence-backed
- reproducible
- replayable
- extensible
- implementation-independent
- suitable for long-lived knowledge repositories

Success will be measured by the repository's ability to preserve, explain, and reuse knowledge over time rather than by the quality of any individual generated report.

---

# Project Status

Repository-First Intelligence is an active engineering exploration.

The architecture should be considered a working design that is expected to improve as implementation experience and operational evidence accumulate.
