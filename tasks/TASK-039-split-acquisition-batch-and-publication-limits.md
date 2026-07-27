# TASK-039 — Split Acquisition Batch Limits from Stream Publication Limits

## Status
Draft

## Objective

Correct the architectural coupling between mailing-list acquisition batching and saved-stream publication.

Linux Mailing Lists is exposing a contract collision introduced after resumable acquisition was added. The implementation correctly acquires a complete connected discussion across multiple bounded acquisition runs, but then rejects publication because the same configuration value is also interpreted as the maximum size of the completed stream projection.

The goal is to preserve bounded acquisition while allowing valid completed discussions to publish atomically.

## Problem Statement

Today a single configuration value (`expanded_limit`, derived from `bounds.total_artifacts`) serves two unrelated purposes:

- Maximum artifacts acquired during one bounded acquisition run.
- Maximum artifacts allowed in a fully materialized saved stream.

With resumable acquisition (TASK-031), these concepts diverged.

Current behavior:

```
expanded_limit
├── acquisition batch allowance
└── complete stream membership ceiling
```

A discussion may legitimately require multiple acquisition batches. Once acquisition completes, the saved-stream projection evaluates the aggregate discussion against the same ceiling and fails with:

> connected context exceeds expanded_limit; no partial component was published

The acquisition evidence is correct and complete. Only projection publication fails.

## Scope

### In Scope

- Separate acquisition batch policy from publication policy.
- Preserve bounded Lore requests and resumable acquisition.
- Preserve the invariant that connected components are never partially materialized.
- Atomically publish complete connected components regardless of how many acquisition batches produced them.
- Continue using the existing paginated repository query contract for membership delivery.
- Add regression coverage for a discussion larger than one acquisition batch that publishes successfully.

### Out of Scope

- Raising `expanded_limit` as the solution.
- UI pagination enhancements.
- Browser presentation changes.
- Changes to acquisition semantics.
- Changes to immutable artifact storage.

## Repository Compatibility

No in-place repository migration is required.

Configuration compatibility should be preserved or deterministically translated for existing `bounds.total_artifacts` definitions.

## Acceptance Criteria

- Acquisition batch limits and publication limits are independent concepts.
- Successful multi-run acquisition does not fail publication solely because multiple batches were required.
- Publication remains atomic.
- No partial connected component is ever published.
- Existing paginated membership queries continue to function.
- Full validation passes.
- Review package contains architectural rationale and regression evidence.

## Required Validation

- Focused tests for the new policy split.
- Regression reproducing the current Linux Mailing Lists failure.
- Proof that a discussion larger than one acquisition batch publishes successfully.
- Full `make validate`.
