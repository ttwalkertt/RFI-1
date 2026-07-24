# ADR 0024: Process Local Fetch Queue progress, timestamps, and durable bounded history

## Status

Accepted for TASK-032.

## Context

The Process Local Fetch Queue (TASK-029) provided single-worker FIFO execution,
duplicate suppression, cooperative cancellation, and lifecycle events. Its
operator-facing behavior was incomplete: a running fetch emitted `started` and
then remained silent until terminal completion; displayed activity lacked
consistent timestamps; terminal jobs and events were retained only in
process-local memory and were lost on restart; and the operator could not
distinguish a stalled fetch from one progressing normally.

Persisting the entire execution queue as durable work was rejected because it
would add unnecessary durability and recovery complexity for mailing-list
fetch requests. The queue is asynchronous UI execution state, not a durable
cursor or scheduler.

## Decision

Keep the Process Local Fetch Queue as the execution authority for Linux
mailing-list fetch requests. Add three operator-observability improvements
without changing the execution model:

1. **Running-job progress**: `LinuxMailingListWorkflowService.fetch_up_to_date`
   accepts an optional `on_progress: Callable[[FetchProgress], None]` callback
   emitted at acquisition-window boundaries (the existing ~31-day window).
   The callback is best-effort: an exception while publishing progress never
   fails the fetch. The `FetchProgress` dataclass contains only
   operator-relevant fields: phase, message, window_start, window_end,
   windows_completed, and occurred_at.

2. **Timestamps**: `FetchJob` gains `updated_at` and `progress` fields.
   `QueueEvent` already carries `occurred_at`. All timestamps are UTC ISO-8601
   strings produced by the queue's clock. The browser renders them with
   `toLocaleString()` / `toLocaleTimeString()`.

3. **Durable bounded terminal history**: Two new SQLite tables
   (`mailing_list_fetch_history`, `mailing_list_fetch_events`) store terminal
   job summaries and bounded queue events for operator scrollback. History is
   bounded to 50 terminal entries and 200 events. Pruning is deterministic:
   oldest eligible entries are removed first. Active process-local jobs are
   never pruned by history retention. Progress events are coalesced with a
   minimum interval of 3 sequence gaps to prevent flooding.

## Progress callback contract

```python
@dataclass(frozen=True)
class FetchProgress:
    phase: str           # "acquiring" or "window_complete"
    message: str         # human-readable operator message
    window_start: str | None = None
    window_end: str | None = None
    windows_completed: int = 0
    occurred_at: str | None = None
```

The workflow calls `on_progress(progress)` at the top of each window iteration
(phase `acquiring`) and after each window completes (phase `window_complete`).
The queue's `_work` method wraps the callback in a closure that acquires the
condition lock, mutates `job.progress`, `job.message`, and `job.updated_at`,
and emits a coalesced `progress` QueueEvent.

## Restart semantics

After restart, crash, or host restart:
- queued jobs are not restored;
- a running job is not restored;
- interrupted work is not automatically resumed;
- the new process starts with an empty active queue;
- persisted terminal history remains visible;
- persisted bounded display events remain visible;
- durable mailing-list artifacts and acquisition evidence remain authoritative.

The UI and API do not imply that active fetch work is durable. The
`restart_behavior` field in the snapshot response explicitly states
`process_local_queue_resets_durable_evidence_remains`.

## API compatibility

All existing queue routes remain available with the same HTTP methods and
response semantics:
- `GET /api/linux-mailing-lists/fetches`
- `POST /api/linux-mailing-lists/fetches`
- `POST /api/linux-mailing-lists/fetches/{stream_id}`
- `POST /api/linux-mailing-lists/fetches/cancel-all`

The snapshot response adds fields compatibly: `history`, `history_limit`,
`durable_events`, `durable_event_limit`. Existing fields (`running`, `queued`,
`recent`, `events`, `event_limit`, `restart_behavior`) are preserved. The
`running` object adds `progress` and `updated_at` fields.

Browser polling remains at 1.5 seconds. No WebSockets, server-sent events, or
additional workers were introduced.

## Consequences and limits

The queue remains process-local. Terminal history is durable but not an
execution authority. Progress is best-effort and coalesced; it is not a
guaranteed telemetry stream. The schema migration from v5 to v6 adds two
tables with `IF NOT EXISTS` and is idempotent. No existing test was weakened,
deleted, skipped, or rewritten to obtain a passing result.
