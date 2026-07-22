# Linux mailing-list workflow façade

TASK-028 makes the operator outcome—not the repository decomposition—the primary product surface.
An operator can choose a Linux kernel mailing list, define a bounded sample, review it without
persistence, create the governed configuration, test it against Lore, and inspect the retained
messages in one coherent workflow at `/linux-mailing-lists`.

## Operator contract

The normal path is:

```text
choose Lore list -> define bounded scope -> review -> create -> live test -> inspect evidence
```

The screen uses archive names, canonical Lore URLs, a human-readable stream name, dates,
relevance controls, and hard limits. It does not ask for source IDs, stream IDs, schema IDs,
revision IDs, JSON, or YAML. Deterministic identities are shown only in review so an operator can
audit what will be created. Every primary action reports what happened, what changed, whether it
succeeded, and the next safe action.

Each input has persistent adjacent guidance covering purpose, format, bounds, consequences, and
recovery. Placeholders are intentionally absent: an example that disappears during typing is not
documentation. Deeper choosing, bounds, context, identity, lifecycle, incompleteness, retry, and
connectivity topics use the TASK-027 named non-modal Help target so the draft remains intact.

## Architecture and ownership

`LinuxMailingListWorkflowService` is a task-specific orchestration façade. It does not own a new
database or bypass established authorities:

```text
workflow façade
  -> MailingListSourceService
  -> StreamService and immutable StreamRevision
  -> MailingListAcquisitionService and LoreArchive
  -> immutable artifact/provenance repository
  -> MailingListQueryService and artifact browser
```

Review uses provisional-source validation so the intended stream can be checked without first
persisting a source. Create resolves or creates the governed Lore source and then saves through the
stream service. Test uses the saved revision to construct the existing bounded acquisition
contract, publishes the stream through `StreamService.run`, and reads exact run-bound messages
through `MailingListQueryService`. The browser and REST routes contain no persistence logic.

Source identities start with the canonical archive name plus `-lore`; stream identities start with
a normalized human name. If an occupied identity does not describe the same normalized definition,
the façade appends a deterministic SHA-256 prefix and increases its length if necessary. Repeating
the same intent therefore resolves the same source and current revision without duplicating either.

The generic External Sources and Streams/YAML surfaces remain available for maintainers and
advanced repository administration. They are not prerequisites and are not the product path for a
Linux kernel engineer adding a mailing list.

## Lore discovery and connected context

The Lore adapter now uses public-inbox Atom search for date, free-text, subject, and participant
criteria. Seed discovery remains distinct from ancestor closure and bounded reply expansion.
Thread Atom feeds supply reply candidates; RFC 5322 `Message-ID` and `In-Reply-To` remain the
relationship authority. Direct matches and context-only messages remain separately labeled.

Fixture validation proves deterministic selection, graph invariants, persistence, and failure
paths without a network. Live validation separately probes the canonical archive's `new.atom` feed;
the required live test then performs real search, retrieves messages and context, persists exact
bytes, runs the saved stream, and reopens that evidence. A successful HTTP response alone is not a
readiness claim.

The initial window is at most 31 days. Direct matches are capped at 25, the complete retained
sample at 100, and reply depth at 10. Defaults are seven days, five direct matches, 50 total
messages, and depth three. Transport time, response size, pacing, concurrency, and retry policy
remain governed by the source. There is no unbounded or archive-mirroring mode.

## State, failure, and recovery

Review is non-mutating. Create can leave a durable source if subsequent stream creation fails; the
result names that partial state and declares retry safety. Acquisition records retryable, terminal,
or partial outcomes through the established run contract. Valid bounded frontier exhaustion is a
successful but explicitly `tested_incomplete` result, not silent completeness. Saved entries
separate **Configuration ready**—the source and revision can execute—from latest test evidence
status: not run, complete and connected, incomplete or truncated, empty, partial, or failed. They
reconstruct both dimensions and the authoritative draft after restart.

Live results show subject, sender, effective time, Message-ID, Lore link, direct/context reason,
parent, depth, child count, message and relationship totals, connectivity, truncation, configuration
readiness, and test-evidence status. The complete retained set links to the existing Artifacts
browser. A ready configuration never reclassifies incomplete test evidence as complete.

Legacy governed-source records are resolved by archive/list identity before any network request.
The supported canonicalization is deliberately narrow: HTTPS, the case-normalized
`lore.kernel.org` host, one archive path component, and a canonical trailing slash. HTTP, alternate
hosts, nested paths, queries, fragments, credentials, and ports are not aliases. Sources created
through the validated External Sources contract are stored canonically and their existing identity
is reused. A schema-v5 migration repairs only the exact unused TASK-028 legacy `linux-block-lore`
record that stored `https://lore-kernel-org/linux-block`. It atomically updates both persisted
projections to `https://lore.kernel.org/linux-block/` without changing the source identity. Any
different record or any source with durable dependencies is left untouched. There is no runtime or
operator-facing source-repair capability; other mismatches require a separately reviewed central
source-governance migration.

## TASK-029 operations extension

The operations-first console, deterministic catch-up coverage, and minimal process-local FIFO are
documented in `docs/linux-mailing-list-operator-console.md`. They compose this façade rather than
replacing its source, revision, acquisition, evidence, or query authorities. The queue is
asynchronous UI execution state, not a durable cursor or scheduler.

## Limitations

The archive catalog is deliberately small, though canonical custom Lore archive URLs are accepted.
There is no durable incremental cursor, durable scheduler, cross-list federation, participant
alias resolution, patch-series model, or full-text index. Live testing and queued catch-up require
Lore connectivity and are subject to the governed transport policy. A valid hard-bound result may
be incomplete by design. Process restart clears queued jobs and operational status while durable
evidence remains.

## Architectural Status Summary

| Subsystem | Responsibility | Status |
| --- | --- | --- |
| Mailing-list workflow façade | Task-level review, identity, create, test, and restart orchestration | Complete |
| Linux Mailing Lists browser/API | Discoverable operator flow, feedback, result inspection, recovery | Complete |
| Lore Atom adapter | Live bounded search, archive probe, and reply-feed enumeration | Usable with Limitations |
| Source and stream services | Governed source, immutable revision, validation, execution | Complete and unchanged |
| Acquisition/artifact/provenance contracts | Bounded retrieval and immutable evidence ownership | Complete and unchanged |
| Saved status projection | Separate configuration readiness and latest test-evidence completeness | Complete |
| Process-local fetch queue | FIFO catch-up, duplicate suppression, cancellation, status | Complete |
| Durable scheduling and incremental cursors | Cross-restart repeat acquisition | Not Started |

The architectural change is a task-specific façade over existing authorities plus production Lore
Atom discovery and thread enumeration. No second configuration or persistence authority was added.
The important limitations are no durable cursor or scheduler and bounded Atom search rather than
archive mirroring. The next milestone should be selected from operating evidence.
