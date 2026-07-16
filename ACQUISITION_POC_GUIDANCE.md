# Acquisition POC Guidance

## Status

Working guidance (living document)

## Repository-First Philosophy

The repository is the primary product and the enduring asset.

Public-source acquisition **sinks** immutable evidence into the repository. Future processes **source** reports, call briefs, comparisons, LinkedIn posts, and interactive answers from repository state.

Acquisition and projection are intentionally independent and asynchronous.

## Working Architecture

```text
Public Sources
        |
        v
Deterministic Acquisition
        |
        v
Repository (System of Record)
  - Source Registry
  - Immutable Artifacts
  - Retrieval Ledger
  - Document Index
        |
        +-----------------------------+
        |                             |
        v                             v
Future Knowledge Processing      Future Projections
(observations, claims, etc.)     (reports, Q&A, briefs)
```

---

# POC Objective

Build a small number of robust deterministic document retrievers that:

- discover documents from configured sources
- preserve exact source artifacts
- maintain immutable storage
- maintain an append-only retrieval ledger
- maintain a rebuildable document index
- support replay from stored artifacts

The POC deliberately postpones downstream knowledge modeling until real documents are flowing.

---

# Hard Invariants

1. Source artifacts are immutable.
2. Retrieval history is append-only.
3. Every artifact has complete provenance.
4. Every deterministic source is represented by a governed Source Registry entry.
5. Discovery and interpretation are separate concerns.
6. Routine acquisition is deterministic software, not LLM reasoning.
7. Retrievers fail observably.
8. Mutable indexes are always rebuildable.
9. Immutable source artifacts are durable records. Repository version control tracks the evolution of metadata, schemas, and processing logic.
10. Internal identifiers remain stable regardless of provider.
11. Object layout is an implementation detail.
12. Repeated runs are idempotent.
13. Checkpoints advance only after durable success.
14. Stored artifacts define the replay boundary.
15. Preserve enough acquisition evidence to debug retrievers.
16. Source-specific code remains narrow.

---

# POC Scope

## Included

- object storage
- source registry
- deterministic source profiles
- retrieval engine
- append-only retrieval ledger
- rebuildable document index
- replay

## Deferred

- observations
- enrichments
- claims
- positions
- embeddings
- semantic search
- projections
- reports
- exploratory web search

---

# Commercial API Guidance

## Principle

**Development acceleration is acceptable. Architectural dependency is not.**

Commercial APIs may be used when they:

- materially accelerate development
- improve acquisition quality
- reduce engineering effort
- preserve provenance
- expose original source artifacts or identifiers
- can be replaced without changing repository semantics

They must never become the repository or define repository identity.

The repository continues to own:

- Source Registry
- document identity
- artifact identity
- retrieval ledger
- document index
- provenance
- replay

Only the acquisition adapter changes.

```text
Commercial Provider
        |
        v
Provider Adapter
        |
CandidateDocument / FetchResult
        |
        v
Repository
```

## Recommended Initial Provider

The current recommendation is to begin with **SEC-API.io** as the first commercial acquisition provider.

Reasons:

- inexpensive relative to engineering effort
- accelerates SEC acquisition and historical backfill
- simplifies exhibit discovery
- allows the repository architecture to mature before implementing a native EDGAR adapter

This is viewed as a bootstrap strategy rather than a permanent dependency.

The repository should archive original artifacts whenever available.

The provider should always be replaceable by a direct SEC implementation behind the same adapter contract.

---

# Initial Retriever Set

1. SEC filings (initially via SEC-API.io adapter)
2. One HDD vendor Investor Relations news page
3. One HDD vendor Investor Relations events page

The goal is to understand real acquisition behavior, not maximize source count.

---

# Questions the POC Must Answer

- Which publisher identifiers are sufficiently stable?
- What metadata is genuinely useful?
- How should checkpoints behave?
- How often do publishers replace documents in place?
- What discovery responses are worth preserving?
- How should duplicate discovery paths be reconciled?
- What evidence is required to debug a missed acquisition?
- Can the repository be completely replayed without revisiting external sources?

---

# Exit Criteria

The POC succeeds when it demonstrates:

- deterministic acquisition from multiple source types
- immutable artifact storage
- append-only retrieval history
- rebuildable indexes
- direct document access without Git history
- replay from archived artifacts
- documented lessons learned before downstream knowledge modeling begins
