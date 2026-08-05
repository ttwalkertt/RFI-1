# TASK-061 Verification Report

## Result

TASK-061 is complete. The local REST API exposes the acquisition repository's current transcript
learning for one canonical firm through:

```http
GET /api/transcript-acquisitions/learning/{firm_id}
```

The endpoint remains observational and reads existing discovery-anchor history through a read-only
repository connection. It does not plan acquisition, discover, learn, advance a checkpoint, or
write repository state.

This final branch also contains operator-requested corrective repairs discovered through real
Oracle and IBM archive testing: `latest` terminates after its first validated candidate, and an
equivalent repeat acquisition recognizes the checkpoint's stable validated revision without
attempting to bind a traversal-dependent cursor.

## Endpoint Contract and Response Schema

The request supplies one canonical firm path identity and no body:

```http
GET /api/transcript-acquisitions/learning/seagate
```

An empty successful response is:

```json
{
  "firm_id": "seagate",
  "learning": []
}
```

Each populated `learning` element is the canonical JSON already stored in
`discovery_anchor_history`, with an explicit `provider` projection. Persisted fields include record/schema identity, firm/source/adapter
identity, normalized/requested/resolved URL evidence, attempt and artifact identity, success time,
source-profile revision, qualification, and the authoritative provider association used for
dispatch. Provider is not inferred from URL shape or current firm configuration. Historical rows
without that association expose `provider: null` and are not backfilled. The response invents no confidence, score, date,
promotion, or recovery metadata. Unknown firms use the existing HTTP 400 `invalid_request`
convention.

## Repository Order and Read-Only Proof

The repository query groups independent histories by persisted source and adapter identity and
orders each by authoritative `stack_position`. It decodes stored canonical JSON without sorting or
reconstructing anchor metadata in application code.

The populated-state test proves exact JSON equality between the existing `discovery_anchors()`
projection and the API response. The repeated-read test snapshots repository revision, sources,
attempts, artifacts, checkpoints, and learning before two GET requests and proves every value is
unchanged afterward. Empty learning returns HTTP 200 with an empty array.

## Live Corrective Replay Diagnosis

The reported Oracle request was reproduced against an isolated copy of the operator repository.
The running server was confirmed to use this checkout, virtual environment, branch, and commit.
The exact pre-repair conflict was:

- persisted checkpoint position: `8107`;
- persisted checkpoint cursor: `engine-e61b3a001cf4b33258d8b610`;
- replay-proposed checkpoint position: `8107`;
- replay-proposed checkpoint cursor: `engine-e30530ac68b9ea19cade9623`;
- differing checkpoint fields: cursor only.

Both positions derive from validated event date `2026-08-03`, mapped to reporting period `2026-Q3`
and ordinal `8107`. The position therefore represented the same durable progress.

The persisted cursor was hashed from the original discovery candidate membership. The replay
cursor input contained the checkpoint-filtered Q3/Q4 candidates, including candidate/document
identity, proposal-period position and revision, disposition, and disposition reason. Its current
provenance, seed source, proposal rank, and traversal diagnostics were excluded by the cursor
helper, but the changed candidate membership still produced a different hash. Candidate membership
is derived from checkpoint-aware discovery and is not the durable validated revision.

The first repair attempted to recognize replay by exact artifact bytes. Live StockAnalysis evidence
showed why that was insufficient: the retained Q2 page was 258,853 bytes and its current response
was 258,854 bytes. Embedded epoch timestamps, quote price, after-hours change, and quote time had
changed while the source, media type, validated position, and validated revision were unchanged.
The exact SHA-256 therefore changed and the engine incorrectly reached checkpoint advancement.

TASK-060's Oracle regression reused identical fixture bytes and began with a clean one-artifact
state. It did not model mutable provider wrapper data together with checkpoint-filtered candidate
membership and the historical multi-artifact repository state, so this path was not covered.

## Corrective Architecture

The repository retains one read-only equivalence seam. It first accepts exact artifact identity.
When bytes differ, it compares the validator-owned durable identity: media type,
`validated_position`, and `validated_revision`. Latest replay compares that identity directly with
the successful attempt that anchors the current checkpoint. Range replay additionally scopes the
same comparison to the selected source document.

No replay identity is persisted. Seed origin, trial ID, run ID, proposal rank, candidate iteration
order, traversal path, request identity, provenance, and diagnostic metadata do not participate.
The existing artifact, observation, attempt, and checkpoint models remain the only durable models.

After successful validation, a trial-oriented latest acquisition whose validated position is not
newer and whose validated revision matches the current checkpoint attempt emits the existing
`unchanged` outcome. It does not call `record_success()` or `advance_checkpoint()`. The existing
checkpoint remains authoritative and its cursor is neither recomputed nor rebound.

The repository's monotonic and same-position/different-cursor checks are unchanged. A genuinely
newer validated position uses the normal success and checkpoint-advancement path. Results without
a valid durable position/revision identity fall back to exact artifact identity and fail closed
rather than claiming semantic equivalence.

## Replay and Integration Proof

The realistic Oracle regression uses one StockAnalysis archive page containing Q4, Q3, Q2, and Q1
2026-labelled links with distinct artifact bytes. It changes provider-wrapper bytes between the
first run and replay while preserving the validator-owned durable revision, and proves:

1. the first injected `latest` run persists exactly one validated artifact and observation;
2. the checkpoint advances once;
3. an identical injected replay completes with `unchanged == 1`;
4. a learned-seed replay also completes unchanged;
5. artifact, observation, attempt, anchor, repository revision, checkpoint position, and checkpoint
   cursor are unchanged across replay;
6. a failure injected before checkpoint finalization remains partial with `unchanged == 0`;
7. a genuinely newer validated artifact advances normally;
8. `first_in_date_range` replay remains mutation-free with changed wrapper bytes; and
9. an intentionally different cursor at the same position is still rejected by the repository.

The repair was also exercised against an isolated copy of the actual operator repository using the
reported HTTP POST. It returned HTTP 200 with `durable_acquisitions=0`, `unchanged=1`, and the exact
existing checkpoint. Before and after remained revision `5224`, artifacts `2288`, observations
`2676`, anchors `18`, position `8107`, and cursor `engine-e61b3a001cf4b33258d8b610`. The operator
repository itself was not modified during diagnosis or verification.

The TASK-061 HTTP integration test sends the Oracle-shaped POST twice through the real admin API.
Both responses are HTTP 200; the first reports one durable acquisition, the second reports zero
durable acquisitions and one unchanged result. A subsequent learning GET returns the single
validated learned anchor.

## Complexity and Robustness Review

The deliberate review confirmed:

- no seed-origin special case exists; learned and operator-supplied trials use the same engine path;
- no second checkpoint table, cursor type, replay record, or parallel learning representation was
  introduced;
- replay exits before existing mutation methods rather than adding replay-only persistence;
- the source-wide comparison is anchored to the current checkpoint attempt, not arbitrary prior or
  partial attempts;
- repository same-position/different-cursor validation remains unchanged and fail-closed;
- checkpoint monotonicity rules are unchanged;
- latest and range selector contracts, learning policy, search ranking, seed injection shape, and
  request idempotency remain unchanged;
- missing or malformed validated revision identity cannot be treated as semantically equivalent;
- partial failure precedence is explicitly tested and preserved; and
- no duplicate artifact, observation, learned anchor, attempt, or repository revision is produced.

No remaining in-scope corrective finding was identified.

## Verification Results

- Focused checkpoint/replay tests: PASS (6 tests).
- TASK-059 regression target: PASS (119 tests).
- TASK-060 regression target: PASS (131 tests).
- TASK-061 focused/API target: PASS (5 tests).
- Acquisition repository and engine regression suite: PASS (42 tests).
- Transcript acquisition and admin/API regressions: PASS.
- Full `make validate`: PASS.

The generated package contains command output and exit status for every required validation, plus
the commit-aware patch, file inventory, manifest, and SHA-256 checksums.

## Assumptions and Limitations

- Existing bad Oracle/IBM artifacts, anchors, observations, and checkpoints are not deleted or
  backfilled by this repair.
- Content-date extraction that allowed historical-labelled archive URLs to validate as
  `2026-08-03` is a separate issue and is unchanged.
- Validator-owned `validated_position` and `validated_revision` define durable acquisition
  equivalence. Provider wrapper-byte changes without a validator revision change are observationally
  unchanged; a future content-sensitive validator revision can distinguish genuine same-period
  publication revisions without changing checkpoint architecture.
- Independent learning histories have no persisted global recency order; their internal stack
  order remains authoritative.

## Architectural Status Summary

| Subsystem | Responsibility | Status | Important limitations / next milestone |
|---|---|---|---|
| Transcript learning authority | Persist bounded qualified anchor histories | Complete and unchanged | Existing policy and bounds retained |
| Learning inspection API | Return persisted learning by canonical firm | Complete | Read-only; no UI or pagination |
| Latest acquisition | Publish first validated deterministic candidate | Complete | Existing bad state is not backfilled |
| Durable replay equivalence | Match checkpoint-owned validated position/revision | Corrected | Depends on current validator revision semantics |
| Checkpoint repository | Enforce monotonic position and immutable cursor binding | Complete and unchanged | Genuine inconsistencies remain conflicts |
| Range selection | Select one globally earliest validated in-range artifact | Complete and unchanged | Existing deferred reducer retained |
| LLM recovery workspace | Future bounded recovery and operator review | Not started | Separate milestone |
