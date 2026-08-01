# TASK-056 --- Persistent Discovery Anchor History

## Status

Complete

## Objective

Improve deterministic document rediscovery by retaining a bounded
history of previously successful discovery URL anchors for each logical
acquisition source.

## Problem Statement

Current discovery depends primarily on configured hints and bounded
traversal. Previously successful document locations may no longer be
revisited first, causing bounded discovery to exhaust its search budget
before reaching a known-good source.

The repository should retain a small, durable history of successful URL
anchors and consult them before broader discovery, without changing
acquisition semantics or weakening bounded search.

## In Scope

-   Persist a bounded move-to-front history of the three most recently
    successful unique URL anchors for each logical acquisition source.
-   Key the history by the stable repository identity of:
    -   firm;
    -   logical configured source; and
    -   adapter.
-   Attempt retained anchors in deterministic LIFO order before
    configured hints.
-   Update the history only after durable successful acquisition
    progress.
-   Preserve bounded discovery after retained anchors are exhausted.
-   Add focused regression coverage.

## Out of Scope

-   Unlimited URL history.
-   Automatic learning from failed attempts.
-   Background crawling.
-   Changes to configuration ownership.
-   Changes to acquisition checkpoint semantics.
-   Changes to bounded discovery limits other than using retained
    anchors first.

## Required Invariants

-   History survives source-profile revisions.
-   History advances only after successful acquisition or deterministic
    no-change confirmation.
-   Failed, blocked, partial, or policy-rejected attempts never update
    history.
-   Duplicate URL identities are move-to-front, not duplicated.
-   History is bounded to three unique entries.
-   History updates atomically with acquisition progress.
-   URL normalization is used only for identity and deduplication;
    original observed URLs remain preserved as provenance.
-   Discovery remains deterministic for identical repository state and
    identical external content.

## Discovery Order

1.  Most recent retained anchor.
2.  Second retained anchor.
3.  Third retained anchor.
4.  Configured discovery hints.
5.  Existing bounded discovery.

## Required Tests

-   History is empty for a newly configured source.
-   Successful acquisition creates the first anchor.
-   Repeated success moves an existing anchor to the front.
-   Fourth unique success evicts the oldest anchor.
-   Failed retrieval does not modify history.
-   No-change confirmation refreshes the successful anchor.
-   History survives source-profile reloads.
-   Discovery attempts retained anchors before configured hints.
-   Existing acquisition checkpoints, immutable artifacts, and evidence
    remain unchanged.
-   Full repository validation passes.

## Verification Package

Provide:

-   before/after discovery ordering evidence;
-   proof of atomic history updates;
-   proof that retained anchors survive profile reload;
-   proof that failed attempts do not modify history;
-   focused test commands and results;
-   full `make validate` result;
-   changed-file inventory and patch;
-   final Git status, commit hash, and pushed branch.

## Acceptance Criteria

TASK-056 is complete when:

-   every logical acquisition source retains a durable LIFO history of
    its three most recent successful unique discovery anchors;
-   retained anchors are consulted before configured hints;
-   history remains bounded, deterministic, and atomic;
-   existing acquisition semantics, checkpoints, immutable evidence, and
    bounded discovery remain unchanged;
-   focused tests and full validation pass.
