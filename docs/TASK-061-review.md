# TASK-061 Verification Report

## Result

TASK-061 is complete. The local REST API exposes the acquisition repository's current transcript
learning for one canonical firm through:

```http
GET /api/transcript-acquisitions/learning/{firm_id}
```

The endpoint is observational. It validates the firm through the existing firm catalog and reads
the existing discovery-anchor history through a read-only repository connection. It does not plan
or register a source, run discovery or acquisition, learn, advance a checkpoint, or write any
repository projection.

Post-implementation operational testing found a pre-existing TASK-058/059 orchestration defect:
`latest` persisted every validated candidate in a successful archive-page trial before stopping the
trial sequence. At the operator's explicit request, the final branch also restores the documented
TASK-058/059 contract: a trial-oriented `latest` acquisition publishes the first validated
candidate in deterministic rank and terminates immediately. This correction is separate from, and
does not add mutation to, the inspection endpoint.

## Architectural Summary

`AcquisitionRepository.transcript_learning()` is the endpoint's only repository operation. It
reads `discovery_anchor_history`, joins the governed source record to select transcript learning,
and decodes the existing canonical anchor JSON. No new table, file, cache, DTO, or parallel
learning representation exists.

`PullWorkflow.transcript_learning()` resolves the canonical `firm_id` through the existing firm
catalog and delegates directly to the repository read. The admin HTTP adapter parses the fixed firm
path, rejects query controls, invokes the service, and projects the returned tuple as JSON. Callers
never need a source, adapter, stack-position, or other internal identifier.

The corrective acquisition change is confined to the existing engine candidate loop. Once a
trial-oriented latest candidate has been validated and `record_success()` has completed, the loop
exits. The existing trial-finalization path then reports `first_validated_success`, applies the
single success's existing learning and checkpoint behavior, and terminates later seed trials.
`first_in_date_range` continues through its existing deferred terminal-selection policy and remains
globally reduced to exactly one candidate.

## Endpoint Contract and Response Schema

The request contains one path identity and no request body:

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

Each populated `learning` element is the existing persisted discovery-anchor model. Persisted
fields include schema and record identity, firm/source/adapter identity, normalized/requested and
optional resolved URL, attempt and optional artifact identity, success time, optional source
profile revision, and qualification. The API adds no score, confidence, date, promotion state, or
recovery metadata.

Unknown firms use the existing admin API convention: HTTP 400 with the standard JSON error
envelope, `error_code: invalid_request`, and `error: unknown firm: {firm_id}`.

## Repository Order Proof

The authoritative order is `discovery_anchor_history.stack_position`, which is also consumed by
transcript trial planning. The query groups independent histories by persisted `source_id` and
`adapter_id`, then orders each history by `stack_position`. It returns canonical persisted JSON
without reconstructing or sorting anchor metadata in application code.

The populated-state acceptance test records three successes, obtains the existing
`discovery_anchors()` projection, and proves exact JSON equality with the API response. It also
proves the URLs retain the expected move-to-front order.

## Read-Only, Empty-State, and Unknown-Firm Proof

The repository query uses `RepositoryDatabase.connect(read_only=True)` and executes one `SELECT`.
The service performs only firm lookup and that query. The handler performs only serialization.

The repeated-read test snapshots repository revision, sources, history, artifacts, checkpoints,
and learning before two HTTP reads, proves the responses identical, and proves every snapshot
unchanged. A known firm without learning receives HTTP 200 and an empty array. An unknown firm
receives the existing HTTP 400 error contract.

## Injected-Acquisition Integration Proof

The integration test starts from an operator-supplied archive URL through the TASK-060 POST
endpoint, discovers and validates a transcript URL, persists one artifact, and then reads the
learning endpoint. The GET returns the validated transcript URL as the existing learned anchor;
the supplied seed is not learned.

The archive-page correction regression models the observed StockAnalysis shape with three ranked
Oracle transcript links whose retrieved content all validates to the current date. It proves
`latest` fetches and persists only the first ranked success and that learning contains exactly that
one validated URL. This protects the inspection API from merely making a known multi-persistence
defect look authoritative.

## Complexity and Robustness Review

The deliberate review established:

- the GET call graph terminates at a read-only connection and cannot mutate repository state;
- the response is the existing anchor model, not a duplicate learning representation;
- persisted stack order is preserved exactly within each independent history;
- empty and unknown-firm behavior use existing repository and API conventions;
- callers supply only canonical `firm_id`;
- the acquisition correction adds no representation, policy, ranking, checkpoint, or learning
  mechanism; it restores the existing orchestration terminal condition;
- `first_in_date_range` still uses the deferred global-selection path;
- later candidates are neither fetched, persisted, learned, checkpointed, nor reported as failures
  after the first validated `latest` success.

No corrective finding remains.

## Verification Results

- Focused TASK-061 tests: PASS (5 tests).
- TASK-060 regression suite, including TASK-059/058 and transcript regressions: PASS (129 tests).
- Real archive-page latest regression: PASS.
- Transcript acquisition regression suite: PASS.
- Relevant admin/API suite: PASS.
- Injected acquisition followed by learning inspection: PASS.
- Full `make validate`: PASS.

The generated review package retains the complete output and exit status of every required command.

## Assumptions and Limitations

- Learning remains capped and qualified by the existing TASK-056 policy.
- Independent source/adapter histories have no persisted cross-history recency order and are grouped
  deterministically without changing their internal persisted order.
- The endpoint reports repository state; it does not assess anchor quality, freshness, or expected
  future success.
- The endpoint has no pagination because existing learning histories are bounded.
- The correction does not repair already-persisted Oracle or IBM artifacts, anchors, or checkpoints.
- Content-date extraction that allowed historical archive URLs to validate as 2026-08-03 is a
  distinct observed issue and is not changed here.

## Architectural Status Summary

| Subsystem | Responsibility | Status | Important limitations / next milestone |
|---|---|---|---|
| Transcript learning authority | Persist bounded qualified anchor histories and execution order | Complete | Existing bound and qualification policy unchanged |
| Learning inspection repository query | Read transcript anchors by canonical firm scope | Complete | Independent histories have no global recency order |
| Learning inspection REST API | Return persisted learning or empty state using existing errors | Complete | Local synchronous JSON API; no UI or pagination |
| Latest acquisition orchestration | Publish first validated deterministic candidate and stop | Corrected | Existing bad state is not backfilled or repaired |
| Range acquisition selection | Select one globally earliest validated in-range artifact | Complete and unchanged | Uses deferred terminal reducer |
| LLM-assisted seed recovery | Propose bounded temporary seeds after deterministic exhaustion | Not started | Separate future milestone |
| Recovery workspace | Persist bounded recovery context and operator review | Not started | Separate future milestone |
