# TASK-056 Verification and Architectural Review

## Completion

TASK-056 is Complete. RFI now retains at most three prior successful URL anchors per existing
`(firm_id, source_id, retrieval_adapter_id)` identity and attempts them in deterministic
move-to-front order before configured transcript discovery hints. The existing `source_id` is the
stable logical configured-source identity; source-profile revisions remain immutable acquisition
snapshots and do not partition the history.

## Architecture

The SQLite structured-state authority owns a bounded `discovery_anchor_history` projection. Each
row preserves exact requested and resolved URLs alongside a conservative normalized deduplication
identity, successful attempt, retained artifact, timestamp, adapter, and acquisition-time profile
revision. Successful artifact ingress updates the projection inside the same SQLite transaction as
the attempt, observation, document, artifact metadata, and any ingress checkpoint. Rollback removes
all structured progress together; failed and skipped attempts use a separate path that cannot teach
history.

Transcript discovery reads the three-entry stack through the acquisition repository and prepends
resolved-then-requested fallback URLs for each entry to configured hints. All URLs continue through
the existing host, page, byte, time, link, validation, and traversal bounds. A stale anchor is
retained and discovery proceeds deterministically to the next retained location, then configuration,
then existing search traversal.

## Evidence

`tests/test_task056.py` proves empty state; first through fourth successes; move-to-front,
deduplication, and eviction; exact requested/resolved provenance; conservative URL normalization;
failed-attempt non-learning; transaction rollback; firm/source isolation; profile-revision survival;
v14 populated migration; retained-anchor ordering; stale-anchor fallback; and preservation of the
prior acquisition-attempt count during migration. TASK-048, TASK-052, and TASK-053 regressions prove
the transcript validation, configured-hint, and bounded traversal contracts remain intact.

## Limitations

This milestone adapts only ordering for URL-addressable transcript discovery. It does not infer
relevance, host preference, probability, content policy, or configuration authority. History has no
automatic decay or failure-based removal and is intentionally capped at three entries. Exact URLs
are retained for provenance but diagnostics expose only normalized bounded identities, avoiding
sensitive query-value disclosure in ordinary operator output.

## Architectural Status Summary

- Immutable acquisition evidence — Complete; attempts, artifacts, observations, provenance, and
  checkpoint contracts remain authoritative.
- Persistent discovery-anchor projection — Complete; durable, bounded, deterministic, and
  transactionally coupled to successful artifact progress.
- Transcript discovery integration — Complete; retained anchors precede configured hints and broad
  traversal while all established bounds remain enforced.
- Operator observability — Usable with limitations; bounded diagnostics expose the history key,
  retained normalized order, counts, fallthrough, and existing failure/budget evidence, but there is
  no dedicated history browser.
- Adaptive intelligence — Not Started beyond the explicitly governed URL ordering in this task.

The next architectural milestone remains TASK-007 model-guided intelligence; any broader adaptive
behavior should first receive a separate governance contract rather than extending this history.
