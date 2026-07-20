# ADR 0020 — Revisioned artifact streams as relational materialized projections

## Decision

Represent an artifact stream as a stable repository identity with immutable revisions, relational
dependency edges, explicit bounded runs, and materialized memberships over existing immutable
artifact identities. Map native schemas through a finite repository-owned registry of projection
providers, schema capability declarations, and context-expansion handlers, then invoke
schema-owned context expansion after generic typed selection.

Persist a canonical publication plan with each successful run so memberships and lineage can be
rebuilt offline without provider access. Publish the plan, memberships, lineage, and terminal run
status in one SQLite transaction.

## Rationale

Multi-level filtering and fan-out require durable, explainable state rather than transient queues.
Relational edges plus application-level topological validation provide the required bounded DAG
semantics without a graph database or scheduler. Typed capabilities preserve native schema meaning
and reject unsupported predicates while avoiding an unlimited document model or rules language.

Referencing artifact IDs permits one immutable evidence object to participate in many streams.
Separating generic selection from registered projection and expansion preserves TASK-023's
connected-discussion invariant without embedding mailing tables or reply-tree behavior in the
stream engine. Governed external-source profiles, rather than stream revisions, own provider and
transport settings.

## Consequences

Schema version 3 adds stream definitions/revisions, dependencies, projections, runs, publication
plans, memberships, and lineage. Schema version 4 adds explicit mailing acquisition lifecycle
outcomes without changing artifact ownership. Execution is explicit and bounded. Automatic
scheduling, durable archive cursors, production polling, remote acquisition inside the generic
engine, transformed artifacts, arbitrary predicates, and cross-schema joins remain out of scope.

Artifacts remain owned by acquisition/evidence storage. Membership and lineage counts do not
participate in retention. A no-match run changes the current materialized view without deleting
prior run history or underlying evidence.
