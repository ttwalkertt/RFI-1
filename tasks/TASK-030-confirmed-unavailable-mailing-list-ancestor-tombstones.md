# TASK-030 — Confirmed-Unavailable Mailing-List Ancestor Tombstones

## Status

Complete

## Objective

Allow bounded Lore acquisition to complete when a required ancestor is conclusively absent
from both the configured list archive and Lore's cross-list `/all/` archive. Persist an
immutable tombstone that records the negative retrieval evidence, closes the header-derived
relationship path, and prevents deterministic catch-up from remaining permanently blocked.

## Boundaries and invariants

- Only an HTTP 404 from both the configured Lore archive and `/all/` establishes a tombstone.
- Rate limits, timeouts, transport errors, 5xx responses, authorization failures, malformed
  responses, and every other failure remain incomplete or failed acquisition outcomes.
- A tombstone is evidence of confirmed unavailability, not a synthetic email. It must use a
  distinct media type, carry the attempted locations and response statuses, and never claim
  lossless RFC 5322 content.
- The original child's `In-Reply-To` header remains the authority for the relationship edge.
- Tombstones may close structural ancestor paths and count toward repository coverage, but
  operator and query surfaces must distinguish them from retrieved messages.
- Repeated acquisition of the same unavailable ancestor is idempotent.
- Immutable evidence, bounded acquisition, cancellation, and offline rebuild guarantees remain
  intact.

This milestone explicitly refines TASK-023's fail-closed rule: a missing connector may count as
structurally resolved only when the repository retains explicit, inspectable evidence that both
authoritative Lore lookup paths returned 404. It is not promoted as retrieved message content.

## Acceptance criteria

1. The Lore adapter distinguishes confirmed absence from generic request rejection and exposes
   both attempted locations and their 404 statuses.
2. A required ancestor confirmed absent on both paths produces one immutable tombstone artifact.
3. The tombstone resolves the immediate-parent relationship and permits coverage completion when
   all other discovery and context policies complete.
4. The manifest and operator-facing result disclose the tombstone.
5. A single-path 404, 403, transient failure, or non-404 fallback result does not create a
   tombstone.
6. Repeated runs and offline projection rebuild preserve one stable tombstone identity and the
   same connected path.
7. Existing connected, truncated, incomplete, quarantined, queue, and stream behaviors regress
   cleanly.

## Required evidence

- focused provider and acquisition tests;
- coverage-advance proof;
- idempotency and offline-rebuild proof;
- operator disclosure proof;
- full test-suite result;
- Architectural Status Summary.

Do not commit, merge, push, or clean the branch.

## Completion evidence

Implementation, validation, review evidence, limitations, and the required Architectural Status
Summary are recorded in `docs/task-030-review.md`.
