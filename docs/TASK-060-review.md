# TASK-060 Verification Report

## Result

TASK-060 is Complete. A local REST caller can provide one firm, the canonical
`earnings_transcript` artifact identity, an optional existing transcript selection contract, and
one operator-supplied HTTP(S) starting URL. The endpoint resolves the firm's governed source
profile, constructs exactly one `operator_supplied` trial, and returns the existing
`AcquisitionRunResult` representation.

The URL is advisory. The manual proof starts at an archive page and acquires a different related
transcript URL. After trial construction, injected and learned seeds both execute
`EarningsTranscriptPullAdapter.discover_trial()` and the same `AcquisitionEngine._run_source()`
lifecycle. Traversal, ranking, retrieval, validation, terminal selection, persistence, learning,
checkpoint finalization, and diagnostics were not forked.

## Architectural Summary

The REST adapter parses a narrow transport shape directly into the existing frozen
`TranscriptAcquisitionTarget` and `TranscriptAcquisitionSelection` contracts. Omitted selection
resolves to `latest`; `first_in_date_range` retains its inclusive date behavior.

`PullWorkflow.acquire_transcript_from_seed()` is the service boundary. It resolves the current firm
and source-profile revision through the normal planner, selects the existing transcript discovery
capability, and builds the same governed `SourceProfile` used by ordinary Pull Workflow execution.
It never publishes or revises firm configuration.

The transcript adapter normalizes the supplied URL and creates one `AdapterAcquisitionTrial` with
`seed_kind=single_seed` and provenance-only `seed_source=operator_supplied`.
`AcquisitionEngine.run_source_trial()` supplies that one trial to the existing private run
lifecycle. Normal `run_source()` still obtains its learned/configured trial plan exactly as before.

## API Contract

Endpoint: `POST /api/transcript-acquisitions/seed`

No query parameters are accepted. The JSON body accepts only:

- `firm_id`: required string;
- `canonical_artifact_id`: required string and currently exactly `earnings_transcript`;
- `starting_seed`: required single absolute HTTP(S) URL string;
- `selection`: optional existing selection object.

Omitted selection request:

```json
{
  "firm_id": "seagate",
  "canonical_artifact_id": "earnings_transcript",
  "starting_seed": "https://investors.example.com/events/archive"
}
```

Date-range request:

```json
{
  "firm_id": "seagate",
  "canonical_artifact_id": "earnings_transcript",
  "selection": {
    "mode": "first_in_date_range",
    "start_date": "2025-01-01",
    "end_date": "2025-12-31"
  },
  "starting_seed": "https://investors.example.com/events/archive"
}
```

Success returns HTTP 200 with the existing acquisition result. Representative fields are:

```json
{
  "run_id": "run-source-pull-seagate-earnings-transcript-...-injected-...",
  "source_id": "source-pull-seagate-earnings-transcript-...",
  "mechanism": "earnings_transcript",
  "status": "complete",
  "durable_acquisitions": 1,
  "checkpoint_before": null,
  "checkpoint_after": {"position": 8106, "cursor": "engine-..."},
  "outcomes": [],
  "diagnostics": []
}
```

Malformed, blank, non-HTTP(S), extra, repeated, multiple-seed, query-controlled, and mismatched
requests fail closed with the existing REST error envelope and `invalid_request` classification
where no narrower existing classification applies.

## Seed Provenance and Convergence Proof

The trial retains normalized `starting_seed`, `trial_id`, immutable acquisition target,
`seed_kind=single_seed`, and provenance-only `seed_source=operator_supplied`. Operator diagnostics
use the existing URL redaction function. Candidate and retrieval provenance continue to identify
the URLs actually discovered, requested, resolved, validated, and persisted.

Both paths converge as follows:

1. learned acquisition uses `acquisition_trials()` to select a learned starting seed;
2. injected acquisition uses `injected_trial()` to validate one operator starting seed;
3. both are represented by `seed_kind=single_seed`, and origin is retained only in `seed_source`;
4. both enter the same `configured_hint` discovery stage through `discover_trial(profile, trial)`;
5. both enter the same engine trial loop, candidate evaluator, repository transaction, terminal
   selection, checkpoint finalization, and existing result projection.

The focused regression proves identical stages, ranked candidates, request traversal, page
diagnostics after removing `seed_source`, and terminal acquisition results after removing only
that provenance field for both `latest` and `first_in_date_range`. It also proves the learned seed
no longer enters the formerly divergent `retained_anchor` stage. The manual proof records this
request sequence:

1. `https://ir.example.com/archive`;
2. `https://ir.example.com/q2-2026-earnings-call-transcript.html`.

Only the second URL is validated, persisted, and learned. The injected archive seed is not promoted
merely because it was supplied.

## Checkpoint Replay and Observable No-Change

Checkpoint cursors hash stable candidate identity, position, revision, and disposition fields.
Discovery locations, traversal metadata, seed source, selector attribution, and other incidental
provenance do not participate. Existing checkpoints with an older cursor shape remain compatible:
a complete run that confirms only candidates at or below the durable position finalizes against
the existing checkpoint as observable no-change rather than requiring a new successful retrieval.

For `first_in_date_range`, validation and terminal selection still run normally. After selection,
the repository suppresses a new observation only when the selected bytes already exist for that
source and document at the durable position. A genuinely newer or changed validated artifact still
uses ordinary success ingress. Replay does not rewrite the learned-anchor stack when its current
top already represents the checkpoint artifact.

The focused regression executes one repository through empty ordinary acquisition, injected
success, learned-seed replay, and repeated injection for both selectors. Each replay is complete
with `unchanged=1`, zero new durable artifacts, identical before/after checkpoints, and unchanged
history, artifact metadata, learned anchors, and repository revision. A separate regression proves
that newer validated periods advance and an explicit pre-finalization fault remains partial.

## Verification Results

- `make task060-test`: PASS, 128 focused and transcript/Pull/API regression tests.
- `make task060-proof`: PASS; empty ordinary acquisition, injected success, learned-seed replay,
  and repeated injection completed with one durable artifact and observable unchanged replays.
- `make task059-test`: PASS.
- `make task058-test`: PASS.
- Transcript acquisition regression suite: PASS.
- API/REST regression tests: PASS.
- `make task059-proof`: PASS.
- `make task058-proof`: PASS with unchanged normal acquisition behavior.
- Lint, formatting, type checking, documentation, baseline, and diff checks: PASS.
- `make validate`: PASS, 577 tests plus all repository demos, offline proofs, quality checks,
  documentation checks, architecture checks, and source archive integrity verification.

The final review package reruns and retains the full output of each required command.

## Files Changed

- `src/rfi/acquisition/engine.py`: one-trial public entry point converging on the normal lifecycle.
- `src/rfi/discovery.py`: invocation-scoped selection adapter, injected-trial construction, and
  operator seed provenance.
- `src/rfi/pull/workflow.py`: governed firm/profile resolution and shared source construction.
- `src/rfi/admin/server.py`: strict narrow REST endpoint and selection DTO parsing.
- `tests/test_task060.py`: focused service, engine, provenance, learning, checkpoint, and REST tests.
- `scripts/task060_seed_injection.py`: deterministic manual related-URL proof.
- `scripts/generate_task060_review.py`: commit-aware validation and verified package generation.
- `Makefile`: TASK-060 test, proof, and review targets.
- `TASKS.md` and the TASK-060 ticket: completed milestone status.
- `docs/TASK-060-review.md`: this architectural review.

## Assumptions and Limitations

- The endpoint is synchronous and local, matching the repository's current admin REST conventions.
- The firm must already have a runnable governed transcript discovery configuration. Injection does
  not supply or repair traversal policy, firm identity, or source configuration.
- Exactly the first runnable transcript discovery candidate in normal planner priority order
  supplies the governed deterministic policy. The injected URL replaces only its starting seed.
- Bounded traversal can still return indeterminate or failed outcomes. A seed is not proof that a
  requested transcript exists or is reachable within current budgets.
- The response is the acquisition-engine result rather than a new overlapping workflow result.
- Duplicate JSON field rejection is scoped to this endpoint; existing API decoding is unchanged.
- No operator UI was required or added.

## Explicit Scope Confirmation

No LLM invocation, OpenAI or other web search integration, retry/escalation loop, recovery
workspace, hint stack, provider context handle, new learning policy, historical backfill,
continuation cursor, traversal change, ranking change, or operator UI was introduced. The existing
production search component remains part of the unchanged deterministic configured pipeline, but
the injected trial clears identity search terms and begins only from the supplied URL.

## Architectural Status Summary

| Subsystem | Responsibility | Status | Important limitations / next milestone |
|---|---|---|---|
| Seed-injection REST boundary | Strict request parsing into existing immutable target and selector | Complete | Local synchronous API; no UI |
| Seed-injection service | Resolve governed firm/profile and construct one attributable trial | Complete | Requires runnable transcript discovery configuration |
| Deterministic transcript trial | Traversal, ranking, retrieval, validation, and diagnostics from one seed | Complete | Existing bounded discovery limits remain authoritative |
| Transcript terminal selection | Latest compatibility or global earliest validated range result | Complete | No backfill or continuation orchestration |
| Persistence, learning, checkpointing | Existing outcome-driven atomic success lifecycle | Complete | Injected seed itself never teaches |
| Normal learned-seed acquisition | Existing FIFO/configured sequencing and observable behavior | Complete | Unchanged by TASK-060 |
| LLM-assisted seed recovery | Bounded proposal after deterministic exhaustion | Not Started | Separate future milestone |
| Recovery workspace | Persist bounded recovery context and operator review | Not Started | Separate future milestone |
| Historical backfill | Repeated governed date-range acquisition | Not Started | Separate future milestone |

The next architectural milestone is bounded LLM-assisted seed proposal after deterministic
exhaustion, using this API/trial boundary without changing deterministic traversal or validation.
