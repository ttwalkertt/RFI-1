# ADR-0014 — Repository-owned artifact query and isolated stored-content preview

## Status

Accepted by TASK-018.

## Context

The acquisition repository preserves immutable bytes, append-only attempts, governed sources, and
rebuildable document/checkpoint views. Those persistence contracts are sufficient for ingress and
replay but are not a stable consumer read model. A browser-specific traversal of the document
index would expose storage shape, make generic consumers reconstruct SEC metadata, and create a
second definition of “latest” before the Bring Repository Up to Date planner is implemented.

Stored external HTML is hostile. Serving it as ordinary same-origin application content would
allow a retained document to execute with operator-console authority when previewed or opened.

## Decision

Introduce `rfi.artifacts.ArtifactQueryService` between authoritative acquisition state and all
artifact consumers. It exposes separate typed query, summary, detail, page/cursor, and content
contracts. The service derives normalized views through public acquisition-repository reads and
canonical firm/artifact authorities; handlers and browser JavaScript never inspect persistence.

One logical repository document is one query result. When the same document has multiple retained
byte revisions, detail resolves its most recently ingested immutable revision while preserving
every prior attempt in authoritative history. TASK-019 extends that detail with first, last, and
explicit immutable observation selection for the resolved artifact. Cross-document “latest” never
uses ingestion time.
It orders by normalized source-effective value, provider-neutral secondary identity, repository
document ID, and immutable artifact ID. SEC acceptance time is preferred, followed by filing date;
publication or observation time supports other artifact families. Retrieval time is an explicit
last-resort fallback and its basis remains visible.

Opaque cursors bind an offset to the normalized query fingerprint and a SHA-256 digest of the
authoritative source, ledger, and artifact-metadata records. Equivalent queries over unchanged
state are stable. Any authoritative change rejects continuation as stale; callers restart rather
than combine snapshots. Limits are required and bounded to 100.

The tree is a lazy UI projection of firm → canonical family → canonical artifact type → document.
Provider form codes and identifiers appear only in normalized metadata. Latest and oldest helpers
delegate to the ordinary query contract with limit one, making the future pull planner a consumer
of the same semantics as the browser.

Stored bytes are resolved only by repository document ID and read through repository integrity
verification. HTML preview uses an iframe with an empty `sandbox` attribute. The content response
also applies CSP `sandbox`, denies all default sources, permits no scripts/forms/popups/navigation,
blocks remote subresources, and establishes an opaque origin even when opened in a new tab.
Stored content is primary; external locations remain separately labeled provenance.

Browser split position and metadata collapse state use the existing disposable preference module.
They never enter repository state or affect server correctness. The browser exposes no mutation.

## Alternatives considered

- Reading the derived document index in handlers was rejected because it is private, rebuildable,
  and too thin to own normalized semantics.
- A browser-shaped repository API was rejected because planners, reports, and analysis need the
  same non-tree query contract.
- Latest-by-ingestion was rejected because acquisition timing is not source chronology.
- Provider-specific latest queries were rejected because generic consumers must not parse SEC
  metadata.
- Offset pagination without snapshot binding was rejected because it silently mixes changed state.
- Rewriting/sanitizing arbitrary HTML was deferred because it changes retained evidence and is
  harder to prove than capability denial around exact bytes.
- Same-origin unsandboxed preview and live-provider preview were rejected as authority and
  reproducibility violations.

## Consequences and limits

The service scans the current POC authoritative records for each query; no derived query index is
introduced. This is deterministic and replay-independent but not yet optimized for large corpora.
Only one current immutable revision per logical document appears in lists. Full-text and semantic
search, arbitrary metadata predicates, annotations, repair, mutation, planning, and extraction
remain absent. Remote resources are intentionally blocked, so exact stored HTML may look less
polished than its live source while remaining safe and offline.
