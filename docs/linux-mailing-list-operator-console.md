# Linux mailing-list operator console

TASK-029 changes `/linux-mailing-lists` from a configuration-first wizard into an
operations-first console. The separate `/streams` surface, governed sources, immutable stream
revisions, bounded acquisition, artifact evidence, and incomplete-result contracts remain the
authorities.

## UI Design Summary

The default workflow is **select a saved stream -> understand coverage and latest outcome -> Fetch
up to date**. A selected card opens a compact summary containing the stream purpose, Lore source,
relevance criteria, hard limits, configured initial scope, effective last-fetch date, and latest
acquisition result. **Edit** explicitly enters configuration mode. This keeps the common daily
operation visible and moves infrequent configuration behind progressive disclosure.

The primary action is **Fetch up to date** in both the selected summary and each stream card.
**Fetch All up to date** and the confirmed **Cancel / Abandon all Fetches** action are grouped at
the top of the sidebar. The bounded status panel stays at the bottom of the workspace and shows
FIFO activity without becoming durable audit history. It reports queued, duplicate ignored,
started, completed, failed, cancellation requested, abandoned, and cancelled events. Queue counts
and cards update by polling the process-local status endpoint.

The editor reuses the human-readable TASK-028 fields but groups them into identity, relevance and
initial scope, and bounded acquisition limits. Existing streams save directly as a new immutable
authoritative revision and always receive a modal confirmation. New streams retain non-persisting
Review and the explicit Create and test action. The sticky editor action bar prevents long forms
from hiding the save action. Evidence remains separate from configuration, and the retained
message list is an independently scrollable keyboard-focusable region.

### TASK-029 summary and card polish

The summary now separates operational comprehension from configuration detail. Stream identity
and actions remain first; a compact operational strip answers whether the stream is healthy and
how current repository coverage is. Configuration criteria and bounds remain visible beneath it
without competing with health. The primary wording is **Repository coverage** and **Current
through …**; the exact contiguous-complete, untruncated derivation remains available as secondary
help rather than implementation language in the primary interface.

A concise **Last acquisition summary** precedes retained evidence. It shows acquisition time,
lifecycle/evidence status, direct-message count, context-message count, and notable warnings.
It is deliberately not a history browser. Retained evidence is a collapsed disclosure by default;
expanding it reveals the same independently scrollable immutable-message region and established
artifact links.

Saved stream cards remain compact while giving the selected card stronger emphasis, an explicit
Selected label, an operational health indicator, and a consistently placed **Repository coverage
through** value. No queue, editor, save, API, acquisition, or repository behavior changed.

This departs from the conceptual two equal modes only in presentation: summary is the dominant
workspace, while the editor is deliberately subordinate. The evidence and status panels remain
available alongside the summary because operators need outcome context while deciding whether to
fetch. This reduces navigation and mode switching without introducing another application mode.

## Coverage and catch-up design

### Effective last-fetch derivation

There is no mutable cursor. Effective last fetch is reconstructed from durable acquisition
manifests whose Lore source and relevance criteria exactly match the current stream revision.
Qualifying intervals must be complete: successful, connected, and untruncated, or a completed
bounded search with no seed matches. Intervals are sorted and merged from the configured initial
start date. Only adjacent or overlapping intervals advance the displayed date. Partial,
incomplete, quarantined, truncated, retryable-failure, and terminal-failure intervals never bridge
a coverage gap or advance coverage. A no-match search is coverage even though the existing run
lifecycle retains its historical `no_seed_matches` representation.

### Overlap policy and multi-window catch-up

Catch-up starts exactly two days before effective last fetch and ends at the server's current UTC
date. If no complete coverage exists, it starts at the revision's configured initial date. The
two-day overlap is deterministic and intentionally re-observes the archive boundary. Immutable
content remains idempotent.

Each Lore request spans at most the existing 31-day difference and retains the revision's direct,
total, reply-depth, source transport, response-size, pacing, retry, and concurrency bounds. Longer
catch-up ranges are partitioned into gap-free FIFO windows. An incomplete or truncated window is
retained and exposed, but catch-up stops so a later complete window cannot hide the gap.

## Queue behavior

`MailingListFetchQueue` is a process-local one-worker FIFO owned by the admin server. Enqueue calls
return immediately. A stream already queued or running is not added again and produces a
`duplicate_ignored` event. Fetch All snapshots every currently eligible Lore mailing-list stream
and submits it through the same duplicate check.

Cancel All abandons queued jobs and sets a cooperative cancellation token for the running job.
Cancellation checkpoints exist before discovery, after discovery, before every message fetch,
before each bounded window, and between acquisition and the next window. A blocking network call
is allowed to return before its next checkpoint. Durable evidence already published by a completed
window is never removed. Planning cancelled before publication does not create a misleading failed
coverage record.

The most recent 200 events and 100 jobs are retained in memory. Restart starts with an empty queue
and status panel; queued jobs are not replayed. Durable acquisition manifests and evidence remain,
so effective coverage reconstructs after restart. The browser polls status every 1.5 seconds; no
websocket, daemon, scheduler, or general job framework was introduced.

## REST API

All enqueue and cancellation responses use HTTP 202 and return before acquisition completes.

```sh
# Queue one saved mailing-list stream.
curl -i -X POST http://127.0.0.1:8765/api/linux-mailing-lists/fetches/STREAM_ID \
  -H 'Content-Type: application/json' -d '{}'

# Queue every eligible saved mailing-list stream.
curl -i -X POST http://127.0.0.1:8765/api/linux-mailing-lists/fetches \
  -H 'Content-Type: application/json' -d '{}'

# Abandon queued jobs and request safe cancellation of the running job.
curl -i -X POST http://127.0.0.1:8765/api/linux-mailing-lists/fetches/cancel-all \
  -H 'Content-Type: application/json' -d '{}'

# Inspect running, queued, recent, and bounded status events.
curl http://127.0.0.1:8765/api/linux-mailing-lists/fetches

# Save an edited existing stream as its next authoritative revision.
curl -X PUT http://127.0.0.1:8765/api/linux-mailing-lists/STREAM_ID \
  -H 'Content-Type: application/json' -d @workflow-draft.json
```

Existing TASK-028 review, validation, create, test, draft, result, and source/query endpoints remain
compatible. The generic Streams API and `/streams` page were not changed.

## Architectural Status Summary

| Subsystem | Responsibility | Status |
| --- | --- | --- |
| Summary/editor browser workflow | Daily operation, progressive configuration, result inspection | Complete |
| Catch-up orchestration | Coverage derivation, overlap, bounded multi-window execution | Complete |
| Process-local fetch queue | FIFO, duplicate suppression, cancellation, bounded status | Complete |
| Source, stream revision, and acquisition services | Governed configuration and bounded execution | Complete and preserved |
| Artifact and provenance repositories | Immutable evidence and inspectability | Complete and preserved |
| Browser status refresh | 1.5-second process-local polling | Complete |
| Durable scheduling and queue recovery | Cross-restart background work | Not Started (out of scope) |

The architectural change is a minimal operations orchestration layer. It adds neither a durable
cursor nor a scheduling authority. Important limitations are cooperative (not preemptive) network
cancellation, process-local status, and repository coverage derivation limited to the current
revision's exact relevance criteria. The next architectural milestone should be selected from
operator evidence rather than expanding this queue into a scheduler.
