# Repository-First Intelligence architecture

RFI-1 is an evidence-first repository architecture with a local operating product and several
implemented downstream architectural POCs. This document describes the stable structure and
invariants. [`docs/current-state.md`](docs/current-state.md) records current maturity, product
composition, evidence, and limitations; those properties must not be inferred from an architecture
diagram alone.

## Purpose

The repository is the durable system of record for source evidence and the governed objects built
from it. Acquisition, knowledge development, retrieval, intelligence, and operator projections
have distinct authority and lifecycle. Any of their implementations may evolve without allowing a
downstream convenience layer to replace upstream evidence.

RFI-1 is designed to outlive an individual provider, vector technique, model, report format, or
user interface.

## Architectural layers

```text
External sources
      |
      v
Governed acquisition ------------------------------+
      |                                             |
      v                                             v
Immutable evidence + acquisition history     Operational projections
      |                                       (feeds, streams, browser,
      v                                        mailing-list views)
Structural source objects
      |
      v
Versioned derived knowledge
      |
      v
Governed retrieval + evidence packages
      |
      v
Grounded intelligence execution
      |
      v
Consulting workspace and projections
```

The operating product currently composes the first two rows and the operational projections. The
lower source-object-through-workspace chain is implemented and tested as bounded POCs but is not
part of the stable application workflow.

### Governed acquisition

Acquisition owns bounded source discovery and retrieval. Provider adapters propose candidates and
return exact bytes plus provenance; repository contracts own canonical persistence, duplicate
handling, observations, attempts, checkpoints, interval outcomes, and replay.

Artifact-family policy remains artifact-specific. Shared SEC transport does not make Form 10-K,
10-Q, 8-K, 20-F, and 6-K one configurable semantic artifact. Transcript and press-release
discovery do not weaken deterministic admission or repository evidence authority.

Date-delimited retrievers use the observable contract in
[`docs/date-delimited-acquisition-contract.md`](docs/date-delimited-acquisition-contract.md).
Coverage is conservative: candidate success cannot establish completeness unless an authoritative
interval-spanning surface was affirmatively and fully evaluated.

### Immutable evidence

An artifact is exact immutable content. One content-addressed artifact can have multiple immutable
acquisition observations and multiple run-bound attempts. Observation time, adapter, diagnostics,
and provenance do not redefine or copy content identity.

Repository-owned query contracts expose normalized summary/detail records and exact stored bytes.
Source-effective chronology and ingestion chronology remain distinct. External provider URLs are
provenance, not substitute read paths.

### Structural source objects

Source objects identify exact structure and byte spans in immutable artifacts. They are evidence
location metadata, not semantic conclusions. Their identities must be stable across deterministic
rebuilds and verifiable against exact artifact bytes.

The current parser is deliberately narrow: SEC submission/header structure. This narrowness is a
maturity fact, not a change to the architectural role.

### Versioned derived knowledge

Derived knowledge represents normalized or interpreted meaning. Every version carries status,
confidence, derivation identity, and provenance to source objects. Corrections and supersession do
not rewrite prior versions. The knowledge subsystem consumes a source-object reader contract and
does not open acquisition persistence directly.

### Governed retrieval and evidence packages

Retrieval uses typed queries, explicit metadata constraints, bounded candidate generation,
traceable ranking/filter decisions, and fail-closed freshness/integrity checks. Vector similarity
is a replaceable candidate-generation mechanism, not the authority or the complete retrieval
architecture.

Evidence packages retain source and derived authority classes, exact bounded contexts,
provenance, omissions, budgets, truncation, and retrieval traces. The same package must be
inspectable by an operator and consumable by downstream reasoning.

### Grounded intelligence

Intelligence converts an information need into bounded retrieval activity and a non-authoritative
result. Plans, budgets, package consumption, model-facing evidence, claims, uncertainty,
contradictions, gaps, failures, and stopping reasons remain explicit.

Every accepted claim is labeled as source evidence, derived knowledge, or model inference and maps
to consumed evidence. A model adapter cannot become an evidence authority. The current
deterministic planner/reasoner implementations prove contracts and failure behavior; they do not
prove frontier-model quality.

### Consulting workspace and projections

The workspace retains investigations, executions, comparisons, notes, exports, and append-only
operator history through a public intelligence-executor port. Its reference snapshots are audit
history, not copies of source authority. Operator annotations remain labeled separately from
source facts, derived knowledge, and model inference.

Reports, briefs, dashboards, answers, and presentations are projections. Routine projection must
not mutate repository history or silently promote an analysis into evidence.

## Authority model

RFI-1 uses a hybrid local repository:

- **SQLite:** authoritative structured runtime records and relationships.
- **Content-addressed filesystem:** authoritative exact acquired bytes.
- **Version-controlled files:** governance, canonical schemas/templates, and selected
  configuration.
- **Rebuildable indexes/projections:** disposable or reproducible state; never an alternate
  evidence authority.

The POC source-object catalog, knowledge generations, retrieval generations, and workspace journal
retain deliberately independent publication/lifecycle mechanics behind public contracts. They are
not yet integrated into the operating product's SQLite lifecycle. Product composition must decide
that lifecycle explicitly; incidental file locations in proof scripts are not a migration plan.

A server database becomes justified only by evidence such as multi-host writers, sustained write
concurrency, high availability, or point-in-time recovery requirements.

## Product composition

The stable application composition roots are:

- `rfi.cli` for initialization, operation, and maintenance;
- `rfi.admin.server.create_admin_server()` for the local browser and REST API; and
- `rfi.pull.create_pull_workflow()` for shared firm-oriented acquisition.

They compose concepts, firms, source profiles, external firm configuration, acquisition, Pull
Workflow, feeds, SEC workflow, mailing lists, streams, artifacts, backup/restore, and help. They do
not compose source objects, derived knowledge, retrieval, intelligence, or workspace services.

Package-level public contracts for those lower layers are nevertheless established and supported
by executable tests. Product absence must not be described as implementation absence, and POC
completion must not be described as product completion.

## Integrated operational projections

### Artifact browser

The artifact browser consumes repository-owned query and exact-content contracts. Firm/canonical
artifacts, unassociated feed evidence, and mailing-list projections remain distinguishable. Stored
external content is untrusted and executes only behind a capability-denying preview sandbox.

### Feeds

Revisioned RSS/Atom definitions are repository-owned discovery configuration, independent of
externally managed firm files. Normalized entry observations, unavailable-entry tombstones,
fulfillment, and bounded run history remain SQLite authority. Successfully retrieved content uses
the normal acquisition engine and artifact store. Firm association selects feeds for a pull but
does not assign evidence ownership or canonical artifact identity.

### Mailing lists

Selected development email is ordinary immutable evidence. Source-scoped observations preserve
where a message was seen; canonical message identity and relationship evidence support cross-list
lineage without graph persistence. Connected paths fail closed on unresolved connectors or cycles.

Relationship acquisition retains a durable ancestry-first continuation frontier. Budget exhaustion
can be `continuation_pending` without declaring retained messages incomplete; interval coverage is
withheld until the applicable relationship boundary is terminal.

### Revisioned artifact streams

Streams are bounded materialized projections over artifacts or other streams. Stable identities
have immutable revisions, dependencies form a validated DAG, and successful runs publish
membership and lineage atomically. Stream membership never owns artifact lifetime or creates an
alternate copy of content.

Typed schema capabilities and context-expansion handlers are finite repository registrations. The
Linux mailing-list workflow is a task-specific façade over mailing-list, stream, source, artifact,
and SQLite authorities—not a second workflow authority.

## Established invariants

1. Exact source evidence remains distinct from structural descriptions, derived knowledge,
   intelligence, and operator annotations.
2. Acquired bytes are immutable and content-addressed; repeated retrieval adds history rather than
   mutating content.
3. Provider adapters use public ingress contracts and do not write repository storage directly.
4. SQLite is the sole structured authority for the operating product; UIs and projections do not
   own hidden state.
5. Dependencies point downstream: acquisition does not import knowledge, and upstream layers do
   not import intelligence or workspaces.
6. Provenance, uncertainty, omissions, failures, and conservative coverage remain explicit.
7. Bounded execution and fail-closed validation apply at external, retrieval, and model
   boundaries.
8. Whatever a downstream model can consume must also be inspectable through repository-owned
   contracts.
9. Product integration, architectural existence, task completion, and production readiness are
   separate claims.

## Known limitations and evolution

The present operating model is local, foreground, single-operator, and predominantly
single-writer. Authentication, durable internal scheduling, remote multi-user operation,
monitoring, signed audit guarantees, and scale testing are deferred.

The downstream POCs have narrow SEC structure/ontology, deterministic local retrieval and
reasoning substitutes, and no product UI. The WDC Business Wire adapter is operationally blocked
despite its fixture-backed implementation and Pull registration.

The next architectural frontier is described in [`ROADMAP.md`](ROADMAP.md). Current maturity and
evidence are maintained in [`docs/current-state.md`](docs/current-state.md), so this document can
remain focused on boundaries that should change slowly.
