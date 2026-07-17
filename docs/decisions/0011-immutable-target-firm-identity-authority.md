# ADR-0011: Immutable target-firm identity authority

## Status

Accepted for TASK-011.

## Decision

Create `rfi.firms` as an authority independent from evidence, concepts, knowledge, workspaces, and
intelligence. Give each research target a stable operator-selected `firm_id`. Represent changing
recognition metadata as complete immutable revisions selected through an atomic current pointer,
using the same optimistic append semantics proven by the concept catalog.

Model market and registry identities as typed `(kind, optional market, value)` records. Prevent
identifier and domain conflicts among current firms. Exclude competitor, customer, supplier,
partner, technology, strategic, parent, subsidiary, brand, predecessor, successor, and other
business or corporate-network relationships from firm revisions. Those edges require a separate
evidence-backed relationship graph with provenance, validity, confidence, and source support.
Provide `FirmReference` as the persistence-independent join contract for future acquisition,
source, knowledge, relationship-graph, workspace, and question-answering layers.

Expose the authority through `FirmService` and the existing local admin composition root. Project
typed contracts into a Target Firms page that reuses TASK-010's list/detail/edit/validate/preview/
save workflow, shared help registry, dirty-state behavior, accessibility conventions, and browser-
native dependency footprint.

## Consequences

- Future systems can attach material to a stable firm without importing firm persistence.
- Historical recognition semantics remain inspectable and stale admin edits fail visibly.
- Exact current identifier/domain uniqueness provides useful conflict safety without pretending to
  be a security master.
- Removing relationship edges keeps operator-maintained identity metadata from becoming an
  unsupported assertion store. Firm-centered views can later join relationship records by
  `FirmReference` without changing firm persistence.
- Corporate events, ticker reuse, ownership percentages, product catalogs, relationship-graph
  semantics, automatic discovery, authentication, and multi-user locking remain future policy
  choices.

## Alternatives considered

- Storing firm identity in source objects was rejected because who is targeted and what was
  published have different authorities and lifecycles.
- Reusing business concepts for companies was rejected because semantic definitions and corporate
  identities have different revision, recognition, and integration roles.
- A normalized universal entity/security master was deferred because TASK-011 lacks operational
  evidence for corporate actions, subsidiaries, brands, exchange history, and ownership semantics.
- Lightweight relationship fields on the firm record were rejected because even apparently simple
  competitor, parent, subsidiary, or brand edges are evidence-dependent, time-varying assertions.
  Without provenance, validity, confidence, and source support they would blur identity authority
  with derived business knowledge.
- Mutable firm rows were rejected because changes could silently reinterpret historical source or
  knowledge associations.
- Direct GUI persistence edits were rejected because they would create a second firm authority.
