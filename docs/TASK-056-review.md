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

The independent review found two deficiencies: engine checkpoint finalization remained in a second
transaction, and artifact reuse had been presented as no-change evidence. The repair gives one
engine run a repository-owned transaction boundary and adds an explicit checkpoint-backed
`record_no_change` operation. Only the current checkpoint's successful attempt and retained valid
artifact qualify. Duplicate reuse remains `retained_artifact`; non-success and idempotent paths do
not qualify.

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

Bounded diagnostics now record the history key, normalized retained order, at most six anchor
attempts with stack position, resolved/requested form, query-redacted URL, and actual status, plus
actual configured-hint and broad-traversal fallthrough.

## Acceptance Mapping

- LIFO creation, deduplication, eviction, normalization, and exact provenance:
  `test_empty_lifo_move_to_front_dedup_eviction_and_exact_provenance`.
- Genuine no-change and failed, validation-failed, blocked, partial, cancelled, policy-rejected,
  bound-exhausted, unsupported, skipped, and duplicate separation:
  `test_checkpoint_backed_no_change_is_explicit_and_non_successes_never_teach`.
- Complete direct rollback proof: `test_atomic_rollback_restores_every_structured_success_projection`.
- Normal engine checkpoint rollback proof:
  `test_engine_checkpoint_failure_rolls_back_success_and_anchor_together`.
- Actual two-revision publication and identity isolation:
  `test_revision_changes_and_key_isolation_preserve_history`.
- Three anchors, URL-form fallback, configured hints, bounded traversal, and actual diagnostics:
  `test_three_anchor_forms_hints_and_bounded_traversal_have_exact_diagnostics`.
- Failed-anchor retention: `test_retained_anchor_precedes_hint_and_failure_falls_through_without_search`.
- Empty/populated migration: `test_v14_populated_migration_adds_empty_history_without_changing_evidence`.
- Existing validation, hint, traversal, evidence, and startup behavior: captured TASK-048/052/053
  regressions and full `make validate`.

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
