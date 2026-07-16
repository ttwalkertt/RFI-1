# ADR-0009: Revision-aware concept catalog and local admin console

- Status: accepted
- Scope: TASK-009

## Context

RFI-1 has separate evidence, source-object, knowledge, retrieval, intelligence, and workspace
lifecycles, but no durable authority for the meaning of reusable business concepts. Folding concept
definitions into derived knowledge would conflate interpretation instances with reusable semantic
contracts. A finance-shaped schema would also prematurely constrain state, event, relationship,
narrative, forecast, and other concepts expected to emerge through operational learning.

Operators need practical management through a local web interface. Letting that interface edit
persistence files would make the GUI a second lifecycle implementation and prevent programmatic
callers from sharing validation and revision semantics.

## Decision

Create `rfi.concepts` as an independent definition authority. Store complete immutable concept
revisions as canonical JSON with content-derived identities, explicit predecessors, monotonic
revision numbers, lifecycle status, definition validity, and creation/update timestamps. Select
current revisions through one atomically replaced catalog pointer. Reject stale edits and verify the
complete history and file inventory on open.

Represent observation methods as common typed metadata plus method-specific JSON configuration.
Recognize an initial generic set of method families and permit explicitly registered extension
kinds and shapes. Keep concepts, methods, observations, and deterministic results as distinct public
contracts. Pin every observation to an exact concept revision and method.

Use a deliberately small, data-only deterministic operation set instead of executable expressions.
Require explicit input roles, concept identities, units, and applicable period/scope/dimension
checks. Emit calculated observations with exact input lineage. Preserve extracted and calculated
observations independently and represent reconciliation only as a comparison.

Create `rfi.admin` as a standard-library local HTTP composition root. Bind to `127.0.0.1` by default,
construct `ConceptService` over the public catalog contract, and route both the browser editor and
JSON API through that service. Establish a persistent multi-tab shell with Concept Catalog as its
first tab. Keep authentication and remote deployment outside this milestone.

## Consequences and tradeoffs

Historical meaning is inspectable and cannot be silently rewritten. Domain validity does not become
confused with edit time. Definition persistence remains independent of evidence and observation
lifecycle. Generic values and opaque registered configuration allow substantial future realignment.
The cost is full revision snapshots, a single-writer pointer, and limited executable validation for
future method families.

The operation contract is auditable and safe but intentionally less expressive than a formula
language. Exact unit checks prove preconditions but do not provide conversion or dimensional
analysis. Observation persistence is deferred, so TASK-009 proves coexistence and lineage through
public contracts rather than selecting a durable observation authority prematurely.

The dependency-free server is easy to run and review. Its embedded UI and JSON method editor are
appropriate for a technical local operator, not a final multi-user administration product. The
service boundary permits replacing the server or adding console tabs without changing catalog
persistence.

## Alternatives considered

- Adding definitions to the derived-knowledge store was rejected because reusable definition
  authority and source-grounded interpretation have different provenance and lifecycle.
- A normalized finance database was rejected because sample financial concepts are proofs and the
  required model includes stateful, event, narrative, relationship, and multi-shaped concepts.
- Mutable concept rows were rejected because edits could silently reinterpret historical
  observations.
- Arbitrary expression or Python evaluation was rejected because it expands the security boundary
  before formula semantics, unit policy, and operational requirements are understood.
- One canonical observation per concept was rejected because extracted and calculated assertions
  can legitimately conflict and must coexist.
- Direct GUI access to revision JSON was rejected because it would bypass public validation and
  create a second persistence contract.
- A framework and client build stack were deferred because the standard library provides the local
  API and console proof with a smaller dependency and security footprint.

## Proof limits

The proof establishes durable definitions, immutable revision history, validity lookup, extension
registration, multiple value shapes, two deterministic margin paths, exact lineage, independent
reported/calculated observations, reconciliation visibility, state and event modeling, programmatic
and browser interfaces, restart persistence, local binding, security request boundaries, real
browser editing, and broad failure semantics. It does not establish a final ontology, production
extraction, an observation store, a full formula language, unit conversion, automatic conflict
resolution, concurrent writers, authentication, multi-user authorization, remote hosting, or
production-scale operations.
