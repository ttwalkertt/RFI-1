# ARCHITECTURE.md

# Repository-First Intelligence (RFI) Architecture

> **This document describes the architectural model of Repository-First Intelligence.**
>
> It intentionally avoids implementation details. Those belong in design guidance, task tickets, and code.

---

# Purpose

Repository-First Intelligence (RFI) is an architectural pattern for building persistent, evidence-backed knowledge systems.

Its defining characteristic is the separation of three concerns:

1. Information acquisition
2. Knowledge development
3. Information projection

Each concern evolves independently while sharing a common repository.

---

# Repository-First Philosophy

The repository is the system of record.

It preserves:

- immutable source evidence
- provenance
- evolving knowledge
- historical context

The repository is not merely a cache for AI prompts. It is intended to become the durable foundation for information ingress, knowledge development, and downstream outputs.

The repository is expected to outlive any individual AI model, retrieval technique, reporting format, or user interface.

## Structured storage direction

Structured runtime state and immutable source bytes have distinct storage authority. TASK-021
implements the explicit hybrid model for fresh application repositories: SQLite owns authoritative
structured records and relationships, while content-addressed filesystem objects own exact
acquired bytes. Version-controlled governance and configuration remain files; rebuildable indexes
remain non-authoritative.

Public repository and query contracts isolate consumers from physical storage. Legacy POC state is
not imported or operated as a fallback authority. A future server database is justified only by
demonstrated multi-host writers, sustained write concurrency, high availability, or point-in-time
recovery requirements.

Artifact-specific deterministic SEC retrieval now covers Form 10-K, Form 10-Q, Form 8-K, Form
20-F, and Form 6-K. Concrete adapters own canonical form and amendment policy; a shared bounded
provider owns SEC transport mechanics. All retrieved bytes enter through public acquisition and
repository contracts, and no adapter depends on SQLite or persistence layout.

---

# Architectural Separation

## Acquisition

Acquisition is responsible for discovering and preserving information from trusted sources.

Its responsibilities include:

- source discovery
- document retrieval
- immutable artifact storage
- provenance capture
- acquisition history

Acquisition records **what became available**.

It does not determine what the information means.

---

## Knowledge Development

Knowledge development transforms evidence into increasingly useful forms.

Each layer is expected to remain traceable to supporting evidence.

Knowledge development may involve deterministic processing, AI-assisted processing, or human review.

---

## Projection

Projection consumes repository state to produce outputs.

Examples include:

- consulting briefs
- competitive analyses
- dashboards
- interactive Q&A
- research reports
- social media posts

Projection should not modify repository history as part of routine operation.

---

# Reference Knowledge Pipeline

The conceptual flow of information is:

```text
Sources
    ↓
Artifacts
    ↓
Observations
    ↓
Derivations
    ↓
Enrichments
    ↓
Claims
    ↓
Positions
    ↓
Projections
```

Each layer has a distinct purpose.

---

## Sources

External publishers and information providers.

Examples:

- SEC filings
- investor relations sites
- standards organizations
- conference presentations
- technical papers
- regulatory publications

---

## Artifacts

Exact immutable representations of acquired source material.

Artifacts are preserved as evidence.

Examples:

- PDF
- HTML
- transcript
- slide deck
- JSON
- audio

Artifacts retain provenance and are never modified.

One artifact may have many immutable `ArtifactObservation` records describing separate successful
acquisition events for the same bytes. These acquisition observations own retrieval time,
adapter, diagnostics, and provenance; they never redefine or copy artifact content. They are
distinct from the extracted knowledge observations in the next section.

---

## Observations

Explicit statements extracted from artifacts.

Observations describe facts present in the evidence without introducing interpretation.

Examples:

- announced capacity
- release date
- product name
- quoted shipment volume

---

## Derivations

Information computed from observations.

Examples:

- year-over-year growth
- rankings
- timelines
- trend calculations
- consistency checks

Derivations should be reproducible from repository state.

---

## Enrichments

Additional semantic structure attached to repository objects.

Examples:

- technology classification
- market segment
- workload type
- customer category
- relationship mapping

Enrichments may be deterministic, AI-assisted, or human-curated.

---

## Claims

Evidence-backed assertions supported by observations and derivations.

Claims express conclusions that remain traceable to supporting evidence.

Claims are expected to evolve as repository knowledge grows.

---

## Positions

Higher-level viewpoints developed from multiple claims.

Positions represent the repository's current understanding of a topic.

Examples:

- competitive assessment
- technology outlook
- market interpretation

---

## Projections

Consumable outputs generated from repository state.

Projections include:

- reports
- presentations
- consulting briefs
- interactive answers
- dashboards

Projections are intentionally ephemeral.

The repository remains the durable foundation.

---

# Architectural Characteristics

## Repository read and inspection

Durable evidence is consumed through repository-owned read contracts rather than physical storage
or provider-specific metadata. Typed query, normalized summary/detail, and exact stored-content
contracts separate repository semantics from browser, planning, reporting, and intelligence
projections. Source-effective chronology defines latest and oldest; ingestion time remains an
operational fact. Operator inspection uses the same contracts future automated consumers use.

Stored external content remains untrusted even after retention. Exact repository bytes are the
authoritative inspection copy and execute behind a capability-denying sandbox. Original provider
locations are provenance, not a substitute read path.

## Development mailing-list evidence

Selected development email is retained as ordinary immutable repository evidence. Bounded seed
discovery is distinct from connected ancestor closure and bounded descendant expansion. Durable
SQLite acquisition manifests retain why each message was selected; reply edges and discussions are
rebuildable header-derived state. Every connected member has one complete acyclic path to its stored
root. Missing connectors and cycles fail closed, and descendant limits remain visible frontiers.

Relationship acquisition is resumable rather than limited to one context batch. Append-only run
manifests own an ancestry-first, depth-first continuation frontier and Lore provider-page offsets.
One seed page reaches complete, policy-truncated, or failed relationship state before seed
pagination or date-window coverage proceeds. Successful budget exhaustion is
`continuation_pending`, not artifact incompleteness. Coverage remains withheld, while already closed
message paths remain connected and inspectable. SQLite remains the only continuation authority.

The artifact browser is one repository browser with sibling firm-artifact and development-mailing-
list projections. Both consume repository-owned query and exact-content contracts. SQLite remains
the sole structured authority; no graph persistence or browser-owned threading exists.

## Revisioned artifact streams

Streams are governed materialized repository projections over external-source artifacts or other
streams. Stable identities retain immutable configuration revisions; dependency edges form a
validated DAG; explicit bounded runs publish membership and lineage transactionally. An artifact
may belong to many streams, but all memberships reference the same immutable content identity.

Generic selection evaluates bounded typed Boolean policies over schema-registered projections.
The finite schema registry owns capability declarations, projection providers, and context
expansion handlers. Schema adapters retain native typing. The mailing-list adapter reuses
authoritative connected discussions, while SEC filings use no expansion. Successful execution
plans make memberships and lineage reproducible offline. Admin, CLI, REST, and browser consumers
share repository/service contracts; none owns policy or topology state.

Governed external-source profiles are the authority for provider identity, protocol endpoint, and
transport policy. Stream revisions reference a source and own selection, expansion, dependencies,
and output bounds only. Any future acquisition cursor also belongs to the governed source and
acquisition boundary. Acquisition/evidence storage exclusively owns artifact lifetime; stream
memberships, lineage, and derived counts never trigger artifact deletion. Stream publication is
atomic and preserves the last successful view until a replacement run fully commits.

The bounded Lore adapter applies per-source pacing, source-wide in-process concurrency, time and
response bounds, capped retry/backoff, `Retry-After`, and explicit 429/503 handling. Durable Lore
cursors and production polling are deferred; the active stream contract exposes no inert
incremental or initial-date controls.

The first-class Linux Mailing Lists surface is a task-specific orchestration façade rather than a
new authority. It converts operator intent into provisional source validation, deterministic
governed-source and stream identities, immutable revision creation, bounded Lore Atom acquisition,
stream publication, and run-bound evidence inspection through existing public services. The normal
path does not expose repository identifiers or schema mechanics. Generic source and stream editors
remain advanced administration surfaces. No browser-only configuration or persistence exists.

---

An RFI implementation should strive for:

- evidence-backed reasoning
- explicit provenance
- replayability
- reproducibility
- incremental evolution
- implementation independence
- separation of concerns

---

# Expected Evolution

The architecture is intended to evolve through implementation experience.

Early development focuses on acquisition.

Later work will refine:

- observation models
- derivation pipelines
- enrichment models
- claim lifecycle
- projection architecture

The architectural boundaries described in this document are expected to remain substantially more stable than any individual implementation.
