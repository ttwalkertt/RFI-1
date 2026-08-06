# TASK-067 Architectural Review — Repository-Owned Feed Sources

## Result

TASK-067 is complete. RFI now owns revisioned RSS and Atom definitions independently from external
firm configuration, normalizes durable entry observations, submits new and materially updated
entry links through the existing governed acquisition engine, retains unavailable-entry
tombstones without interrupting the selected run, supports deferred operator fulfillment, and
projects authoritative run history through the operator UI, API, CLI, and aggregate RSS export.

## Architecture and persistence

SQLite schema version 16 adds feed definitions and immutable revisions, current-revision firm
associations, immutable normalized entry observations, current entry selectors, artifact links,
mutable work-queue tombstones with bounded attempt history, and durable feed runs. Exact content
remains in the existing SHA-256 content store. Successful automatic entries run through
`AcquisitionEngine` and `AcquisitionRepository`; manual candidates use the same public repository
ingress contract. No feed-specific artifact store, duplicate algorithm, firm configuration file,
or browser-owned result reconstruction exists.

One `FeedService` owns validation, registry revision publication, selection, polling, tombstone
updates, manual fulfillment, and RSS projection. The Feeds UI, REST handlers, `rfi feeds poll`, and
firm pulls compose that service. A firm pull selects the union of enabled associated feeds once,
creates one feed-run result linked by `parent_pull_run_id`, and embeds that authoritative result in
the pull record. Ordinary unavailable entries do not degrade the pull; a feed-document failure is
a partial feed run while remaining firms and feeds continue.

During normal service startup, the feed repository transactionally converts every durable
`running` feed run left by the prior process to the existing `canceled` terminal state before any
new run can reach overlap detection. Recovery preserves the row ID, start and trigger context,
feed and firm selection, parent pull link, summary, per-feed results, and prior diagnostics; it
adds one bounded `startup_recovery` diagnostic plus completion/recovery timestamps. Terminal rows
are not touched, so recovery is idempotent and a new poll may proceed immediately after restart.

Feed entry acquisition uses a governed source identity derived from the feed revision, strongest
entry identity, and material observation hash. This prevents acquisition checkpoints from
filtering a sibling entry or a materially updated version while preserving the feed and entry
provenance on every acquisition attempt. Canonical bytes continue to deduplicate globally.

## Bounded review decisions

1. **Deletion means retirement.** Delete appends a disabled retired revision. Prior definitions,
   observations, artifacts, tombstones, provenance, and runs remain.
2. **Run retention is 100.** Every completed invocation is durable; the operator history retains
   the newest 100 authoritative results in deterministic order.
3. **Aggregate RSS is capped at 200 current observations.** The newest current observation for
   each stable feed entry is selected deterministically; no live polling occurs during export.
4. **Alternate URLs may cross source hosts with explicit operator provenance.** They must still be
   public credential-free HTTP(S) URLs and their bytes pass normal repository qualification.
5. **Material updates reacquire immediately.** Existing canonical bytes are linked as duplicates;
   changed bytes create the repository's normal immutable revision/observation facts.
6. **Tombstones stay out of ordinary artifact search.** They are distinct non-byte facts exposed
   through the unavailable work queue and aggregate RSS until fulfilled.
7. **Feed XML is not retained as artifact bytes.** Normalized entry observations plus bounded run
   fetch/parse diagnostics are sufficient for this discovery source; linked content remains the
   authoritative artifact.

## Operator, API, and CLI behavior

The Feeds tab provides compact scrolling cards, add/edit through one editor, format validation,
optional searchable multi-firm association, retirement confirmation, per-feed and Poll All
actions, 100-run history with expandable application JSON, filtered unavailable queues, retry,
dismiss/restore, upload and alternate-URL fulfillment, and aggregate RSS export. Before manual
confirmation, the shared fulfillment dialog requires an advisory preview of the current candidate.
Uploads show filename, detected media type, byte size, and bounded extracted title and publication
metadata when available; alternate URLs use one bounded transport preflight for the same evidence.
Unavailable fields are identified as unavailable. Preview does not write acquisition facts or add
a qualification gate; confirmation still uses the existing repository ingress and qualification
path.

The REST surface provides registry, validation, polling, history, unavailable actions, and
`GET /api/feed-items.rss`. `rfi feeds poll [--state PATH] [--feed FEED_ID] [--json]` performs one
pass and exits. Completed, completed-with-unavailable, and partial selected-source runs exit zero;
invalid invocation, overlap, or fatal service failure exits nonzero. Recurrence remains wholly
owned by cron, launchd, systemd timers, or another external scheduler. Aggregate RSS `pubDate`
values are serialized deterministically in UTC using the RSS-compatible RFC-822/RFC-1123 form
(`Wed, 06 Aug 2025 12:00:00 +0000`).

## Verification evidence

Deterministic fixtures cover RSS, Atom, malformed XML, successful HTML, HTTP unavailability,
material updates, canonical duplicates, upload bytes, and alternate-URL bytes. The focused suite
covers registry revisions and retirement, associations, format normalization, non-blocking
continuation, authoritative JSON, restart persistence, reordering, update reacquisition, queue
status, retry, upload and URL fulfillment, duplicate linking, failed fulfillment, overlap, firm
pull inclusion, CLI, APIs, and valid RSS 2.0. Repair regressions assert the emitted RSS date value,
stale-run recovery with preserved facts and repeated-startup idempotence, subsequent polling, and
advisory upload/URL preview metadata through both service and HTTP boundaries.
`make task067-test` passes 15 tests. `make validate` passes all 679 repository tests plus lint,
formatting, typing, import, documentation, design-baseline, source-archive, and integrity checks.

The review evidence directory contains human and JSON CLI transcripts, an absolute-path cron
example, API examples, feed-run JSON, RSS output, schema and restart evidence, manual fulfillment,
live-smoke results, and operator screenshots. Bounded live validation on 2026-08-06 parsed NASA's
public RSS feed (10 visible entries) and CPython's public GitHub Atom feed (20 visible entries).
Live failures are diagnostic only; deterministic fixtures remain the acceptance authority.

## Limitations and risks

- Public URL screening rejects credentials, literal private/loopback/link-local addresses, and
  localhost, but does not perform DNS pinning across redirects; production hardening should add a
  redirect-aware resolver policy before exposing this local application as a remote multi-tenant
  service.
- Feed run retention and RSS export bounds are fixed repository policy rather than operator
  preferences.
- Authentication, OPML, custom request headers, cookies, JavaScript discovery, and internal
  recurrence remain explicit non-goals.

## Architectural Status Summary

| Subsystem | Responsibility | Status | Architectural effect / limitation |
|---|---|---|---|
| Feed registry | Independent revisioned discovery configuration | Complete | Retirement preserves all historical facts |
| RSS/Atom normalization | Strong entry identity and bounded metadata | Complete | RSS and Atom share one normalized abstraction |
| Feed polling service | Shared selection, fetch, parse, acquisition, and results | Complete | UI, CLI, firm pull, and Poll All share one owner |
| Acquisition integration | Qualification, immutable bytes, identity, dedupe, provenance | Complete | Existing engine and repository contracts reused |
| Unavailable work queue | Durable non-byte outcomes and deferred resolution | Complete | Failures remain non-blocking and inspectable |
| Manual fulfillment | Advisory candidate comparison, qualification, and linking | Complete | Preview is non-authoritative; original failure history and governed acceptance are preserved |
| Feed-run instrumentation | Durable authoritative structured results and startup recovery | Complete | Newest 100 retained; stale running rows become canceled in place; expandable UI uses exact JSON |
| Aggregate RSS | Offline bounded projection of durable observations | Complete | 200 items; retained/unavailable status explicit; dates use deterministic UTC RSS syntax |
| Live public-source smoke | Representative RSS and Atom compatibility | Complete | Diagnostic evidence only; fixtures remain authoritative |
| Internal scheduler/authenticated feeds | Recurrence and credentialed transport | Not Started | Explicitly outside TASK-067 |

The next feed-adjacent operational milestone, if real use demonstrates the need, is scheduling
policy; it is not a second feed-processing path.
