# TASK-061 Verification Report

## Result

TASK-061 is complete. The local REST API exposes the acquisition repository's current transcript
learning for one canonical firm through:

```http
GET /api/transcript-acquisitions/learning/{firm_id}
```

The endpoint remains observational and reads the existing discovery-anchor history through a
read-only repository connection. It does not plan acquisition, discover, learn, advance a
checkpoint, or write repository state.

This final branch also contains two operator-requested corrective repairs discovered through real
Oracle and IBM archive testing: `latest` terminates after its first validated candidate, and an
equivalent repeat acquisition no longer proposes a different checkpoint cursor merely because
checkpoint-aware discovery exposes a different candidate set.

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
`discovery_anchor_history`. Persisted fields include record/schema identity, firm/source/adapter
identity, normalized/requested/resolved URL evidence, attempt and artifact identity, success time,
source-profile revision, and qualification. The response invents no confidence, score, date,
promotion, or recovery metadata.

Unknown firms use the existing HTTP 400 `invalid_request` convention.

## Repository Order and Read-Only Proof

The repository query groups independent histories by persisted source and adapter identity and
orders each by authoritative `stack_position`. It decodes stored canonical JSON without sorting or
reconstructing anchor metadata in application code.

The populated-state test proves exact JSON equality between the existing `discovery_anchors()`
projection and the API response. The repeated-read test snapshots repository revision, sources,
attempts, artifacts, checkpoints, and learning before two GET requests and proves every value is
unchanged afterward. Empty learning returns HTTP 200 with an empty array.

## Corrective Replay Diagnosis

A controlled Oracle StockAnalysis archive reproduction established the exact pre-repair conflict:

- persisted checkpoint position: `8107`;
- persisted checkpoint cursor: `engine-9ff3effe37ef7e7c1c0bf5ee`;
- replay-proposed checkpoint position: `8107`;
- replay-proposed checkpoint cursor: `engine-19a94d325d1102d3b06ea2a1`;
- differing checkpoint fields: cursor only.

Both positions derive from validated content date `2026-08-03`, mapped to reporting period
`2026-Q3` and ordinal `8107`. The position therefore represented the same durable progress.

The old cursor input was the stable candidate projection present when the first validated success
terminated the initial trial. On replay, checkpoint-aware discovery filtered proposals at or below
the checkpoint and admitted a future-labelled proposal whose content still validated to position
`8107`. `_target_checkpoint()` then hashed that different discovered candidate membership. Although
the helper already excluded provenance and sorted map keys, its cursor still depended on candidate
identity, proposal-period position, and proposal revision. Those values describe the current
discovery path, not the already-retained durable artifact.

Repository conflict detection correctly rejected rebinding position `8107` to the different cursor.
The defect was that the engine reached checkpoint advancement instead of recognizing equivalent
retained content as unchanged.

TASK-060's prior replay fixture contained one candidate whose proposal period matched its validated
period, so both runs either hashed the same membership or used the zero-retrieval checkpoint path.
Its cursor unit test varied provenance and dictionary order while keeping candidate membership
fixed. It did not model future-labelled archive proposals resolving to retained content at the
existing durable position.

## Corrective Architecture

The repository now provides one read-only equivalence query:
`has_retained_source_artifact(source_id, result)`. It derives the immutable artifact ID from the
validated bytes and asks whether that exact artifact already has an observation for the governed
source. It does not inspect seed origin, trial ID, run ID, proposal rank, traversal path, request
identity, or diagnostics.

After successful validation, a trial-oriented streaming acquisition compares the validated
position with the current monotonic checkpoint. If the position is not newer and the exact artifact
bytes are already retained for that source, the engine emits the existing `unchanged` outcome and
terminates the successful trial without calling `record_success()` or `advance_checkpoint()`.

No checkpoint cursor is recomputed or rebound for this replay. The existing checkpoint remains the
authority. `first_in_date_range` continues through its existing deferred global reducer and retains
its prior retained-artifact replay behavior. Genuinely newer validated content uses the normal
success and checkpoint-advancement path.

## Replay and Integration Proof

The realistic Oracle regression uses one StockAnalysis archive page containing Q4, Q3, Q2, and Q1
2026-labelled links whose fixture content validates to the same durable date. It proves:

1. the first injected `latest` run persists exactly one validated artifact and observation;
2. the checkpoint advances once;
3. an identical injected replay completes with `unchanged == 1`;
4. a learned-seed replay also completes unchanged;
5. artifact, observation, attempt, anchor, revision, checkpoint position, and checkpoint cursor are
   byte-for-model unchanged across replay;
6. a failure injected before checkpoint finalization remains partial with `unchanged == 0`;
7. a genuinely newer validated artifact advances normally;
8. `first_in_date_range` replay remains mutation-free and correct; and
9. an intentionally different cursor at the same position is still rejected by the repository.

The TASK-061 HTTP integration test sends the Oracle-shaped POST twice through the real admin API.
Both responses are HTTP 200; the first reports one durable acquisition, the second reports zero
durable acquisitions and one unchanged result. A subsequent learning GET returns the single
validated learned anchor.

## Complexity and Robustness Review

The deliberate review confirmed:

- no seed-origin special case exists; learned and operator-supplied trials use the same engine path;
- no second checkpoint table, cursor type, or checkpoint projection was introduced;
- replay adds no persistence branch—the equivalent case exits before existing mutation methods;
- repository same-position/different-cursor validation is unchanged and remains fail-closed;
- checkpoint monotonicity rules are unchanged;
- equivalence uses governed source identity plus immutable artifact bytes and validated durable
  position, not run-local or discovery-local values;
- latest and range selector contracts are unchanged;
- learning, seed injection, HTTP shape, search ranking, and request idempotency are unchanged;
- partial failure precedence is explicitly tested and preserved;
- no duplicate artifact, observation, learned anchor, attempt, or repository revision is produced.

No remaining corrective finding was identified.

## Verification Results

- Focused checkpoint/replay tests: PASS (6 tests).
- TASK-059 regression suite: PASS.
- TASK-060 regression suite: PASS (131 tests).
- TASK-061 focused/API tests: PASS (5 tests).
- Acquisition repository and engine regression suite: PASS (42 tests).
- Transcript acquisition and admin/API regressions: PASS.
- Full `make validate`: PASS.

The generated package contains the command output and exit status for every required validation,
plus the commit-aware patch, file inventory, manifest, and SHA-256 checksums.

## Assumptions and Limitations

- Existing bad Oracle/IBM artifacts, anchors, observations, and checkpoints are not deleted or
  backfilled by this repair.
- Content-date extraction that allowed historical-labelled archive URLs to validate as
  `2026-08-03` is a separate issue and is unchanged.
- Equivalent replay requires exact validated artifact bytes already retained for the governed
  source. Changed bytes continue through normal persistence and checkpoint rules.
- Independent learning histories have no persisted global recency order; their internal stack
  order remains authoritative.

## Architectural Status Summary

| Subsystem | Responsibility | Status | Important limitations / next milestone |
|---|---|---|---|
| Transcript learning authority | Persist bounded qualified anchor histories | Complete and unchanged | Existing policy and bounds retained |
| Learning inspection API | Return persisted learning by canonical firm | Complete | Read-only; no UI or pagination |
| Latest acquisition | Publish first validated deterministic candidate | Complete | Existing bad state is not backfilled |
| Durable replay equivalence | Recognize exact retained source artifact at durable progress | Corrected | Exact validated bytes required |
| Checkpoint repository | Enforce monotonic position and immutable cursor binding | Complete and unchanged | Genuine inconsistencies remain conflicts |
| Range selection | Select one globally earliest validated in-range artifact | Complete and unchanged | Existing deferred reducer retained |
| LLM recovery workspace | Future bounded recovery and operator review | Not started | Separate milestone |
