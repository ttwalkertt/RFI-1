# Revisioned multi-level artifact streams

TASK-025 adds repository-owned streams as revisioned, bounded, materialized projections over
retained immutable artifacts. A stream consumes either one governed external-source projection or
one or more compatible upstream streams. Downstream membership never copies authoritative bytes:
it references an existing artifact and document identity.

## Boundaries and responsibilities

- `StreamRepository` owns generic SQLite definitions, revisions, dependency edges, typed artifact
  projections, execution runs, durable publication plans, memberships, and lineage.
- `StreamService` owns generic bounded Boolean evaluation, DAG validation, deterministic ordering,
  canonical definition normalization, YAML review/import/export, semantic comparison, execution,
  and idempotency. It dispatches schema work through a finite registry.
- Registered schema contracts declare capabilities, projection providers, and context-expansion
  handlers. The first registrations are `mail.message` and `sec.filing`.
- The admin page, CLI, REST adapter, and artifact browser consume the same service/repository
  contracts. Browser-local draft state cannot execute until explicitly saved.

SQLite remains the sole structured authority. Exact artifact bytes remain in the existing
content-addressed filesystem authority.

## Definitions, revisions, and topology

A stable stream identity points to one current immutable revision. Each revision records display
metadata, enabled state, input kind and identities, schema, typed selection policy, expansion
policy, and hard output bounds. External-source settings are not copied into a stream revision.
Previous revisions remain inspectable.

Derived input edges are persisted separately and validated as a directed acyclic graph before a
revision is saved. Direct self-reference and indirect cycles fail with explicit error codes.
Fan-out and compatible fan-in are supported. `run-chain` computes the dependency closure and
executes it in deterministic topological order, with a hard 50-stream chain bound.

## Typed selection and schema capabilities

Policies contain only bounded `all`, `any`, and `not` groups and typed predicates. Policy depth is
limited to five and total nodes to fifty. Operators are registered per field; operators cannot
contain SQL, Python, JavaScript, arbitrary JSON paths, or executable regular expressions.

Common fields are schema, source, title, text, authors/participants, and effective timestamp.
Mail adds completeness and registered `mail.list_id` / `mail.patch_version` attributes. SEC adds
registered `sec.form_type` / `sec.accession` attributes. Unsupported fields or operators fail
validation rather than silently producing no matches.

## Selection and expansion

Selection first identifies direct matches. Expansion is a separate registered schema behavior.
`none` works for every current schema. `connected_discussion` is available only for mail messages
and consumes TASK-023's authoritative discussion membership and connectivity classification.

Connected expansion rejects incomplete or quarantined seeds. If a complete connected component
would exceed the configured expansion maximum, the run fails without publishing a partial
component. Direct matches and context-only members remain distinct. Context lineage records the
seed and whether the member is ancestor or descendant context.

## External-source authority and hard bounds

The governed external-source profile is the one executable authority for provider, archive
endpoint, list identity, User-Agent, timeout, response-size bound, minimum request interval,
source-wide in-process concurrency, bounded attempts, and capped exponential backoff. The Lore
adapter coordinates request starts and concurrency across adapter instances for the same source,
honors valid `Retry-After` values, retries HTTP 429 and transient 5xx responses, and classifies
other HTTP responses as terminal. Profiles may carry different policies.

Lore/public-inbox profiles are repository-global objects, not firm-owned objects. Operators create,
validate, inspect, and clone them at `/external-sources`; `/source-profiles` remains the separate
firm-owned acquisition configuration surface. A saved Lore identity is immutable. Policy changes
use a new stable source ID so existing acquisition and stream references retain their meaning.

A stream revision stores only the governed source ID plus selection, expansion, dependencies, and
output bounds. It evaluates retained projections and never performs provider I/O. There is no
unbounded selection form or archive-mirror operation, and rebuild is network-free.

If a durable acquisition cursor is added later, its state and advancement transaction belong to
the governed source/acquisition boundary, never to a stream revision.

TASK-025 deliberately has no durable Lore cursor. `initial_date` and `incremental` are absent from
the active operator contract and UI. Explicit live acquisition is bounded by Message-ID, seed and
context limits, but a later invocation may repeat requests. This is not a production-ready polling
implementation.

## Acquisition outcomes and restartability

Mailing acquisition records `succeeded`, `partial`, `retryable_failure`, or `terminal_failure`
separately from connectivity. A transport failure before any usable message writes only a failed
run record and no run item, artifact, membership, or derived discussion. A failure after useful
retrieval publishes the retained immutable evidence and a `partial` manifest; valid limit/frontier
incompleteness alone uses `truncated`. Content-addressed artifact identity, observation identity,
and stream-run fingerprints make retries idempotent.

## Runs, publication, lineage, and rebuild

Each explicit execution has a durable running, succeeded, or failed run. The input fingerprint
includes the stream revision, normalized candidate projections, and upstream membership lineage.
An unchanged successful fingerprint returns the existing run and does not duplicate memberships.

Publication is one SQLite transaction: the durable publication plan, all memberships, all lineage,
and succeeded status become visible together. Failure leaves a durable failed run and no final
memberships for that run; the previous successful run remains the current view. Membership identity
records stream revision, run, existing artifact/document,
direct/context classification, inclusion reason, expansion, completeness, upstream membership,
and seed identity.

Publication plans are durable execution metadata. Offline rebuild removes and recreates only
materialized memberships and lineage from those plans. It never contacts providers or changes
artifact hashes.

## Operator workflow

The `/streams` page follows Identity → Input → Selection → Context and limits → Review and save.
Common keywords, authors, title, source, and effective-date filters are capability-aware. Nested
Boolean groups, negation, and registered attributes remain available under Advanced policy.
External-source choices and upstream choices lead with display names and operational summaries;
stable IDs remain visible secondary context.

Draft validation, bounded preview, YAML review, and YAML export are separate from saving. A new,
imported, or modified draft cannot run. An explicit save creates a new stream or immutable
revision; only the latest valid saved revision can run. `rfi stream schema`, `validate`, `import`,
and `export` invoke the same service as the browser. Legacy JSON preview/save commands remain for
TASK-025 compatibility, but canonical authoring and interchange use YAML version 1.

The complete format, commands, revision behavior, examples, and troubleshooting guide are in
[`stream-configuration-and-yaml.md`](stream-configuration-and-yaml.md).

The existing artifact browser adds an Artifact streams projection. It exposes upstream and
consumer topology, durable runs, current memberships, direct/context reason, registered
attributes, upstream/seed lineage, and the underlying immutable content. Existing firm and
mailing-list projections remain siblings and retain their prior behavior.

## Explicit non-goals and limitations

This slice does not add scheduling, continuous propagation, a durable Lore cursor, production
polling, transformed artifacts, summaries, arbitrary joins, a broker, graph database, vector
search, retention deletion, or a second store. Remote Lore acquisition remains an explicit bounded
operation before stream execution. The first SEC proof is deterministic and adapter-backed;
automatic projection of every historical provider record is deferred until a production use case
establishes the exact native mapping contract.

## Lifetime and recomputation invariant

Acquisition/evidence storage owns artifact lifetime. Stream memberships and lineage are historical
references and never act as retention counts. No stored reference or membership count is
authoritative; displayed counts are derived queries or diagnostics.

A successful recomputation publishes a new immutable run. If it matches nothing, current-stream
resolution selects that empty successful run while all memberships and lineage belonging to prior
runs remain historical. Artifact rows, exact bytes, documents, observations, and acquisition runs
are unchanged. Foreign keys require every projection and membership to reference an existing
artifact/document; there is no cascade from membership deletion to evidence.

Normal stream publication does not delete or supersede prior memberships before replacement.
Plan, memberships, lineage, and succeeded status commit atomically. The maintenance rebuild path
deletes and recreates only membership and lineage rows inside one transaction; the explicit test
helper that clears materialized memberships is not a run/publication operation. Mailing projection
rebuild replaces only mailing-derived message, relationship, discussion, and discussion-member
rows. Neither path deletes acquisition records, artifact rows, documents, or content bytes.
