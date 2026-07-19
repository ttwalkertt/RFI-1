# Bounded Linux kernel mailing-list intelligence stream

TASK-023 adds Linux development email as a new acquisition and browsing vertical over the same
repository. The initial governed source is `linux-block-lore`, backed by the public
Lore/public-inbox Linux block-layer archive. Lore remains the broad corpus: RFI retains only an
explicitly selected, bounded evidence set and never offers an archive-wide import operation.

## Authority and boundaries

```text
bounded archive adapter
  -> seed discovery
  -> ancestor closure + bounded descendant frontier
  -> shared acquisition repository (exact message/rfc822 bytes)
  -> SQLite durable manifests and derived discussion state
  -> MailingListQueryService
  -> CLI + shared artifact browser projection
```

`repository.sqlite3` remains the sole structured authority. Exact RFC 5322 bytes, including MIME
parts and attachments, remain immutable content-addressed artifacts. Parsed headers, searchable
text, reply edges, discussion membership, depth, and browser organization are derived. No graph
database, external graph service, or in-memory graph authority is present. Browser JavaScript uses
bounded API contracts and never parses `In-Reply-To` or reconstructs a graph.

Schema version 2 adds `mailing_list_sources`, immutable `mailing_list_runs` and
`mailing_list_run_items`, plus rebuildable `mailing_list_messages`,
`mailing_list_relationships`, `mailing_list_discussions`, and
`mailing_list_discussion_members`. Opening schema version 1 performs the single supported in-place
DDL migration. Artifact bytes remain outside SQLite. Existing firm-artifact queries ignore sources
whose repository projection is `mailing-list`.

## Bounded two-stage acquisition

Every request needs explicit Message-IDs, a query, date bounds, or topic terms. Seed count is hard
capped at 100 and context count at 500; ordinary defaults are 10 and 100. The initial live Lore
adapter deliberately accepts explicit Message-IDs only. Fixture discovery additionally proves
date, topic, and query selection. There is no select-all, mirror, unbounded backfill, implicit
history, daemon, subscription, or archive-clone route.

Seed discovery and context expansion are separately represented. Each retained run item records
whether it was an explicit request, a direct seed match, an ancestor connector, or descendant
context. Ancestors may lie outside the discovery window. Breadth-first descendant expansion spends
the remaining context allowance and truncates only at a frontier. Preview performs all remote
planning and parsing but writes nothing; acquisition is a separate explicit action.

The live path is separately gated:

```sh
rfi mailing-list configure-linux-block --state STATE
rfi mailing-list preview --state STATE --live \
  --message-id '<message@id>' --seed-limit 1 --context-limit 20
rfi mailing-list acquire --state STATE --live \
  --message-id '<message@id>' --seed-limit 1 --context-limit 20
```

The fixture proof is local and deterministic:

```sh
make task023-test
make task023-proof
```

Offline operators can run `mailing-list sources`, `discussions`, `search`, `incomplete`, and
`rebuild`. An absent derived projection with retained run items fails explicitly and recommends
rebuild rather than returning a misleading empty result.

## Connectivity and identity

Valid `Message-ID` is the archive identity; RFI derives stable internal message and document IDs.
Immediate reply authority comes only from `In-Reply-To`. `References` is retained as evidence, but
normalized subject is search/display metadata and never thread identity. Relationship rows label
header-derived direct edges and unresolved parents. Future heuristic relationships must use the
distinct `inferred`/`heuristic` classification.

For every connected or truncated discussion, each member has one acyclic immediate-reply path to
the stored root and every connector on that path is stored. The repository integrity check walks
and validates those paths and depths. Missing connectors classify material as incomplete; malformed
identity and cycles are quarantined. Neither state receives discussion membership. A descendant
limit produces `truncated`, never a disconnected `connected` component. Because the initial live
adapter does not enumerate descendants, live ancestor-closure acquisitions conservatively report
truncation rather than claiming a complete discussion.

Repeated acquisition compares content identity for an existing external Message-ID. Equal bytes
reuse the artifact, message, document, and relationship; differing bytes fail with
`message_id_conflict`. A run first retains immutable message artifacts and then publishes its
manifest, run membership, and the complete rebuilt discussion projection in one SQLite transaction.
Failure before that structured transaction can leave ordinary immutable observations, but those
are excluded from both firm and mailing-list discussion projections and can never be labeled
connected. SQLite publication failure rolls back the complete structured acquisition unit.

## Offline reconstruction and browser

Durable run items identify every retained artifact and its inclusion reason. Rebuild reparses exact
stored bytes, reconstructs header relationships, validates connectivity, and atomically replaces
all derived message/discussion tables without an archive client or network access.

The existing `/artifacts` browser now has sibling `Firm artifacts` and `Development mailing lists`
repository projections. Linux block-layer discussions and incomplete material expand lazily.
Opening a message uses the shared exact-content response boundary and shows list, headers, stored
root, inclusion reasons, connectivity, provenance, checksum, size, and safe raw-email text. Direct
children are loaded only when a message branch expands; discussion projections and child queries
are independently capped at 100 and 50 by default.

## Limitations

The initial vertical has no full-text index beyond bounded SQLite `LIKE`, no comprehensive patch
or revision-series parser, no cross-list federation, no participant identity resolution, and no
descendant enumeration on the live adapter. MIME text extraction is limited to ordinary text parts;
all unsupported parts remain preserved in exact raw evidence and produce parse warnings. Historical
backfill, incremental cursors, archive query parsing, pruning, and AI summarization remain deferred.

## Architectural Status Summary

| Subsystem | Responsibility | Status |
| --- | --- | --- |
| Lore/public-inbox adapter | Explicit-ID live retrieval and ancestor closure | Usable with Limitations |
| Bounded acquisition service | Preview, seed/context separation, limits, fail-closed admission | Complete |
| Immutable evidence | Lossless email bytes, acquisition provenance, integrity | Complete |
| SQLite manifests and discussion state | Durable inclusion facts and rebuildable relationships | Complete |
| Mailing-list query service | Sources, discussions, children, ancestors, search, incomplete state | Complete |
| Shared artifact browser projection | Lazy list/discussion/message navigation and content inspection | Complete |
| Patch-series and revision semantics | Deterministic non-reply relationships | Not Started |

TASK-023 changes the repository from a single firm-oriented browser projection to one browser with
multiple repository-owned projections. The important limitation is that live descendant enumeration
is not yet implemented, so live acquisitions are conservatively truncated. The next architectural
milestone should be selected from operating evidence: bounded archive-query discovery and cursors,
or deterministic patch/revision relationships if consulting workflows demonstrate their value.
