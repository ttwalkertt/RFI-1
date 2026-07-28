# ADR 0026 — Source Observations and Canonical Mailing-List Lineage

## Status

Accepted for TASK-045.

## Context

The same authored email can be delivered through several mailing lists. Those deliveries preserve
one normalized `Message-ID` but acquire different transport and list headers, and therefore different
immutable RFC822 bytes. TASK-035 correctly established corpus identity but incorrectly allowed its
representative artifact to gate acquisition. Linux NVMe cross-posts were rejected after their Linux
Block variants had established canonical identity, and rejected IDs leaked into resumable traversal
state.

RFI also needs to follow a shared authored message into descendant branches observed through
different lists without collapsing the source-specific discussion views or their evidence.

## Decision

### Identity and observations

- `canonical_mailing_list_messages` remains the corpus logical-node authority keyed by normalized
  `Message-ID`.
- A successful RFC822 observation is authoritative under `(source_id, normalized Message-ID)` and
  has its own source document, message record, artifact reference, run provenance, and canonical ID.
- Different bytes across sources are allowed. Different bytes within one source fail closed.
- The canonical artifact/document remains a compatibility representative only; it does not govern
  acquisition, traversal, continuation, or coverage.
- Canonical nodes are created only by successful RFC822 observations, never by unresolved references
  or unavailable tombstones.

### Relationship evidence and lineage

`mailing_list_relationship_claims` is the durable assertion authority. A claim binds:

- child canonical node;
- exact asserted reference and normalized reference;
- bounded role (`immediate_parent` or `ancestor_reference`);
- bounded evidence type (`header_in_reply_to` or `header_references` in the current implementation);
- exact source/run/artifact observation provenance; and
- configured-archive or cross-archive-fallback acquisition path.

`References` values remain ordered ancestry evidence and never become direct edges. Malformed or
multi-ID `In-Reply-To` remains artifact/parser evidence and creates no canonical claim.

Resolved canonical parents, unresolved boundaries, ambiguity, and lineage edges are derived at query
time by joining claims to the canonical registry. No mutable edge or resolution authority exists.
Differing valid immediate-parent claims produce an inspectable ambiguous parent set; no winner or
substantive conflict is inferred.

### Source projections and provenance

Existing source relationships and discussions remain rebuildable projections of the graph retained
while satisfying one configured source's acquisition policy. A fallback-acquired required ancestor
may be a member because it closes that graph. Membership and `source_id` record acquisition context;
they do not independently prove delivery through that list. Existing candidate locations,
`cross_archive_fallback`, provider, artifact, document, and run metadata remain the bounded provenance
contract. No generalized provenance system is introduced.

### Continuation and coverage

Only successfully retained source observations may occupy acquired/completed continuation positions.
Saved frontiers are validated against source messages before reuse. A same-source conflict or
quarantine is terminal for that bounded relationship work, with no resumable frontier and no coverage
advancement. Canonical graph enrichment does not itself alter source coverage.

### Historical repair

The repair command requires an explicit copied state, source ID, and historical run ID. It applies
the six TASK-045 evidence predicates, reuses preserved candidate artifacts, writes new repair runs and
source observations, resolves only eligible conflict diagnostics, and leaves historical runs and
conflict observations unchanged. The invalid frontier is superseded by a fresh retry of the same
discovery offset.

## Consequences

- Cross-posted deliveries retain exact evidence without false global byte conflicts.
- Corpus traversal can return all known branches once per canonical node with claim provenance.
- Source-filtered discussions remain available and evidence-specific.
- Schema version 12 adds one canonical link to the source projection and one durable claim table.
- TASK-035's global different-byte conflict rule is narrowed to same-source identity; its canonical
  node and independent run-observation contracts remain intact.
- Provider and heuristic relationship evidence types are reserved by the approved bounded schema but
  are not emitted because no qualifying current adapter assertion or heuristic exists.

## Rejected Alternatives

- Content fingerprints or header normalization: unnecessary and outside scope.
- Source-scoped canonical identity: prevents cross-list lineage.
- One mutable canonical parent: overwrites differing observations.
- Placeholder canonical parents: confuses a reference with retained message evidence.
- Repairing every repository conflict: exceeds the diagnosed run's authorized scope.
