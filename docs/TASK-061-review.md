# TASK-061 Verification Report

## Result

TASK-061 is Complete. The local REST API now exposes the acquisition repository's current
transcript learning for one canonical firm through:

```http
GET /api/transcript-acquisitions/learning/{firm_id}
```

The endpoint is observational. It validates the firm through the existing firm catalog, opens the
acquisition database read-only, and returns the existing persisted discovery-anchor records. It
does not plan or register a source, run discovery or acquisition, learn, advance a checkpoint, or
write any repository projection.

## Architectural Summary

`AcquisitionRepository.transcript_learning()` is the only new repository operation. It reads
`discovery_anchor_history`, joins the already governed source record to select transcript learning,
and decodes the existing canonical anchor JSON. No new table, file, cache, DTO, or alternate
learning representation exists.

`PullWorkflow.transcript_learning()` is a narrow service facade. It resolves the caller's canonical
`firm_id` through the same firm catalog used by existing Pull Workflow operations, then delegates
directly to the repository read. It does not acquire the execution lock because no acquisition or
mutable workflow state is involved.

The admin HTTP adapter parses the fixed firm path, rejects populated query controls, invokes the
service, and projects the returned tuple as JSON. The caller never supplies `source_id`, adapter
identity, stack position, or any other internal repository identifier.

## Endpoint Contract and Response Schema

The request contains exactly one path identity and no request body:

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

Each populated `learning` element is the existing persisted discovery-anchor model, including only
repository-owned fields:

- `schema_version` and `record_type`;
- `firm_id`, `source_id`, and `adapter_id`;
- `normalized_url`, `requested_url`, and optional `resolved_url`;
- `attempt_id` and optional `artifact_id`;
- `succeeded_at` and optional `source_profile_revision_id`;
- `qualification` (`retained_artifact` or `no_change`).

The API does not add labels, confidence, scores, promotion status, inferred dates, or recovery
metadata. Internal identities can be inspected in the returned persisted record, but they are not
request inputs and callers do not need to resolve them.

Unknown firms retain the existing admin API convention: HTTP 400 with the normal JSON error
envelope, `error_code: invalid_request`, and `error: unknown firm: {firm_id}`.

## Repository Order Proof

The authoritative learning order is `discovery_anchor_history.stack_position`, the same persisted
order returned by `discovery_anchors()` and consumed by transcript trial planning. The new query
orders by persisted `source_id`, persisted `adapter_id`, then `stack_position`; this keeps every
independent learning history contiguous and preserves its exact execution order. It returns each
row's canonical JSON without reconstructing or sorting anchor metadata in application code.

`test_populated_learning_preserves_persisted_repository_order` records three successes, obtains the
existing `discovery_anchors()` repository projection, and proves byte-for-JSON equality with the API
array. It separately proves the observed URLs remain in the expected move-to-front order.

There is no invented cross-history recency order: distinct governed source/adapter histories have
independent stack positions and are grouped by their persisted identity.

## Read-Only and Empty-State Proof

The repository query uses `RepositoryDatabase.connect(read_only=True)` and executes one `SELECT`.
The service performs only firm lookup and that query. The handler performs only JSON serialization.
No mutation method is reachable from this call chain.

`test_repeated_reads_do_not_mutate_repository_state` snapshots repository revision, governed
sources, acquisition history, artifact metadata, checkpoints, and transcript learning before two
HTTP reads, proves both responses are identical, then proves every snapshot is unchanged.

`test_empty_learning_state_returns_success` uses a known firm with no anchor history and proves HTTP
200 with the exact empty response. It does not require a saved or runnable transcript profile.

## Injected-Acquisition Integration Proof

`test_injected_acquisition_is_visible_through_learning_endpoint` configures the existing transcript
adapter with a bounded fixture transport, starts at an injected archive URL through the TASK-060
POST endpoint, discovers and validates a different transcript URL, and persists one artifact. A
subsequent TASK-061 GET returns one existing learned anchor whose `normalized_url` and
`requested_url` are the validated transcript URL rather than the supplied archive seed.

This proves the new endpoint observes existing evidence-based learning. It does not teach the
operator-supplied seed or introduce a second learning path.

## Complexity and Robustness Review

The required deliberate review found:

- accidental mutation: none; the call graph terminates in a read-only connection and repeated-read
  state snapshots are identical;
- duplicate representations: none; the response contains decoded canonical anchor records from the
  existing table;
- order preservation: exact within every persisted learning history, with deterministic grouping
  for independent histories;
- unnecessary complexity: avoided; one repository query, one service facade, and one handler route
  were sufficient;
- hidden caller assumptions: none; only canonical `firm_id` is supplied, and empty state does not
  depend on source-profile or adapter resolution;
- empty-state correctness: HTTP 200 and an empty array for every known firm without transcript
  learning.

No corrective finding remained after this review.

## Verification Results

- `make task061-test`: PASS, 5 focused repository/service/HTTP acceptance tests.
- `make task060-test`: PASS, 128 seed injection, transcript, Pull Workflow, and REST regressions.
- Transcript acquisition regression suite: PASS, 77 tests covering TASK-048/048A, TASK-052/053,
  TASK-056, and TASK-057.
- Relevant admin/API suite: PASS, 29 tests covering TASK-009, TASK-012, and TASK-015.
- Injected acquisition followed by learning inspection: PASS as a separately runnable focused
  integration case.
- Format, lint, type, documentation, baseline, diff, and source archive checks: PASS.
- `make validate`: PASS, 582 tests plus all repository demos, offline proofs, quality checks,
  documentation checks, architecture checks, and source archive integrity verification.

The final review package reruns and retains the complete output of every required command.

## Files Changed

- `src/rfi/acquisition/repository.py`: read-only transcript learning query over existing anchors.
- `src/rfi/pull/workflow.py`: canonical-firm validation and repository delegation.
- `src/rfi/admin/server.py`: fixed GET endpoint and existing error-envelope integration.
- `tests/test_task061.py`: focused empty, ordered, unknown, mutation-free, and injected integration
  evidence.
- `scripts/generate_task061_review.py`: commit-aware validation, package assembly, and verification.
- `Makefile`: TASK-061 focused and review targets.
- `docs/pull-workflow.md`: public REST contract.
- `TASKS.md`, the TASK-061 ticket, and the design baseline: completed milestone governance.

## Assumptions and Limitations

- The endpoint is synchronous and local, matching the existing admin REST boundary.
- Learning remains capped and qualified by the existing TASK-056 repository policy.
- Exact persisted URLs and internal provenance identifiers are returned because they are existing
  repository state; the endpoint adds no redaction or fabricated display metadata.
- Independent source/adapter learning histories have no persisted cross-history recency order. They
  are grouped deterministically while preserving each history's authoritative stack order.
- This endpoint does not assess anchor quality, availability, freshness, or likelihood of success.
- No pagination or continuation cursor is present because the existing repository learning set is
  bounded.

## Explicit Scope Confirmation

No edit/delete/reorder operation, deterministic search change, learning-policy change, checkpoint
change, seed-injection change, acquisition change, backfill, continuation cursor, LLM recovery,
recovery workspace, operator UI, or historical representation was added.

## Architectural Status Summary

| Subsystem | Responsibility | Status | Important limitations / next milestone |
|---|---|---|---|
| Transcript learning authority | Persist bounded, evidence-qualified anchor histories and execution order | Complete | Existing three-entry bound and qualification policy remain unchanged |
| Learning inspection repository query | Read existing transcript anchor records by canonical firm scope | Complete | Independent histories have no global recency order |
| Learning inspection service | Validate canonical firm identity without requiring internal identifiers | Complete | Read-only; does not assess configuration readiness |
| Learning inspection REST API | Return exact persisted learning or an empty array using existing errors | Complete | Local synchronous JSON API; no UI or pagination |
| Transcript acquisition/search/learning/checkpoints | Existing deterministic behavior and transactional mutation ownership | Complete and unchanged | Future policy work remains separately governed |
| LLM-assisted seed recovery | Propose bounded temporary seeds after deterministic exhaustion | Not Started | Separate future milestone; may consume this inspection surface |
| Recovery workspace | Persist bounded recovery context and operator review | Not Started | Separate future milestone |

The next architectural milestone may use this observational surface to evaluate deterministic
learning quality before authorizing any search, learning-policy, or recovery behavior change.
