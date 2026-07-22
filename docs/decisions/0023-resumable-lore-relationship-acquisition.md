# ADR 0023: Resumable Lore relationship acquisition

## Status

Accepted for TASK-031.

## Context

Lore seed pagination and date-window coverage were durable, but ancestry closure and reply
enumeration were planned breadth-first in one process-local batch. Exhausting the context allowance
set permanent truncation, withheld coverage, and stopped later seed pages and windows. The adapter's
50-record request control therefore became an unintended discussion-size ceiling.

## Decision

Each bounded run appends its deterministic relationship frontier to the existing SQLite acquisition
manifest. The frontier contains identifiers and traversal/provider offsets, never artifact bytes.
It is keyed by source, coverage batch, and seed-page offset. The next run reads the latest manifest
and resumes it; no mutable cursor table, browser state, process queue, or second authority exists.

Traversal is ancestry-first and then depth-first replies. Ancestry frames retain the current child
and visited path. Reply frames retain parent, depth, provider offset, unconsumed child identifiers,
and page-completion state. Completed reply nodes are recorded so overlapping branches do not repeat
provider enumeration. Depth-first traversal bounds the frontier to the active path plus siblings,
makes exact-budget suspension deterministic, and lets complete branches remain complete.

Provider relationship pages use the same maximum 50 identifiers per request and persist their
offset. Message acquisition remains within the configured per-run seed and context limits. A seed
page reaches a terminal relationship state before the next seed page; every seed page reaches a
terminal state before its date window advances.

The durable relationship taxonomy is:

- `complete`: configured relationship work is exhausted;
- `continuation_pending`: the bounded run succeeded and saved work remains;
- `policy_truncated`: configured reply depth intentionally ended expansion; and
- `failed`: provider, integrity, or execution failure prevented terminal progress.

Coverage advances only for `complete` or `policy_truncated` relationship work after seed discovery
and ancestry requirements also complete. A failed run may retain a retry frontier. Cancellation
before publication leaves the preceding frontier unchanged.

Artifact identity and projection truth remain independent. A run may be continuation-pending while
every retained message whose parent path closes is projected as connected. Run status is never
copied onto immutable bytes as an artifact defect. Content addressing, canonical Message-ID
identity, unique structured rows, and append-only run memberships suppress duplicates across seeds,
branches, runs, and restart.

## Alternatives considered

Increasing the record limit, unbounded Lore calls, skipping oversized discussions, a process queue,
and a mutable shadow cursor were rejected because they weaken bounds, lose restart safety, or create
a second authority. Breadth-first continuation was rejected because it produces a wider durable
frontier and makes branch completion less local.

## Consequences and limits

Catch-up and repeated workflow tests resume automatically. Direct CLI acquisition resumes when the
operator reuses `--continuation-id` and the same discovery offset. Provider requests interrupted
before a manifest commit may be repeated safely; completed manifest work is not. Future replies are
outside the completed source snapshot and are discovered by later overlapping catch-up, not labeled
as a defect. Scheduling, background polling, cross-list traversal, and tombstone supersession remain
out of scope.
