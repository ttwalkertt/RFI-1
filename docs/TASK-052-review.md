# TASK-052 Verification Report

## Result

TASK-052 is Done. External firm configuration can now carry a bounded, source-scoped earnings
transcript discovery hint through the existing retrieval-candidate contract into the production
transcript adapter. No acquisition policy limit changed.

## Root Cause and Repaired Boundary

`RetrievalCandidate.discovery_hints` survived in the source-profile contract, persistence, Pull
Sources candidate serialization, and adapter. `BoundedTranscriptDiscovery` also accepted URL hints.
The contract was lost at the external configuration boundary: `firm-config-v1` allowed only
`discovery_class`, so `_profile()` could not project a source-scoped hint. Discovery also searched
before traversing supplied URLs.

The repair is deliberately narrow:

1. `sources.earnings_transcript.discovery_hints` validates up to eight unique credential-free
   HTTP(S) URLs.
2. `_profile()` projects them unchanged and first into canonical
   `RetrievalCandidate.discovery_hints`.
3. Existing Pull Sources dataclass serialization constructs the adapter request without another
   hint model.
4. The transcript adapter separates URL hints from identity terms and bounded discovery traverses
   URL hints before general search.

The optional field is transcript-specific in the schema. Press-release and SEC configuration are
unchanged. Firm-level `source_hints` were not selected as the new authoritative field.

## Before and After

Before:

```json
"earnings_transcript": {
  "discovery_class": "extended"
}
```

After:

```json
"earnings_transcript": {
  "discovery_class": "extended",
  "discovery_hints": ["https://stockanalysis.com/stocks/amzn/transcripts/"]
}
```

## Configuration-to-Adapter Evidence

The focused test validates and loads the JSON, then inspects the materialized transcript candidate
and proves that its first `discovery_hints` value exactly equals the configured URL. The live proof
serializes that same candidate with the Pull Sources representation and reports identical
`configured_hint` and `adapter_request_hint` values. Adapter diagnostics report:

```json
{
  "configured_hint_count": 1,
  "configured_hint_pages": 1,
  "configured_hint_status": "used",
  "search_queries": 0
}
```

Configured hints remain retrieval intent. Candidate and document identity continue to derive from
the validated retrieved candidate URL. Provenance is created only by ordinary discovery/retrieval;
configuration loading itself creates none.

## Validation and Coverage

`tests/test_task052.py` covers valid loading and projection, malformed and unsupported schemes,
missing-hint fallback, hint-first ordering, explicit participation diagnostics, ordinary candidate
validation, identity/provenance separation, and unrelated source-family isolation.

`make task052-test` passed all 26 TASK-052, TASK-048A, Pull Sources, and TASK-051 coverage regression
tests. In particular, bound exhaustion remains a completed discovery run with indeterminate
coverage, not a system failure. `make validate` passed the full repository gate, including all unit
tests, demonstrations, lint, formatting, type checking, imports, docs, baseline checks, and build.

## Amazon Live Proof

Run:

```sh
make task052-proof
```

On 2026-07-31 the adapter fetched the configured Stock Analysis listing before search. The live page
had more than the unchanged 30 admitted links, so discovery stopped honestly with:

- `result=rejected` and `candidate_count=0`;
- `configured_hint_status=used` and `search_queries=0`;
- `bounds_exhausted=true` and `exhausted_budget=max_links_per_page`;
- `coverage=indeterminate`;
- 2 pages, 1 distinct host, and 769,524 bytes within the existing extended policy.

The proof therefore demonstrates configuration acceptance, projection, adapter delivery and use,
bounded rejection, and preserved TASK-051 semantics. It does not claim that a hint guarantees a
transcript.

## Bounds

Neither `config/discovery-policies.json` nor `docs/discovery-policies-v1.schema.json` changed. The
extended policy remains 8 search queries, 15 results per query, 30 links per page, depth 3, 75 pages,
15 hosts, 52,428,800 bytes, and 180 seconds. The configuration schema adds a maximum of eight hint
URLs; it does not expand transport or discovery budgets.

## Files Changed

- Runtime: `src/rfi/firm_configuration.py`, `src/rfi/discovery.py`.
- Schema: `src/rfi/resources/firm-config-v1.schema.json`,
  `docs/firm-config-v1.schema.json`.
- Tests/proof: `tests/test_task052.py`, `scripts/task052_transcript_hints.py`, `Makefile`.
- Operator evidence: `docs/amazon.firm-config.example.json`,
  `docs/external-firm-configuration.md`, `docs/operator-guide.md`, this report, task state, and
  roadmap state.

## Architectural Status Summary

- **External configuration — Complete.** Transcript-scoped HTTP(S) hint authoring is explicit,
  bounded, and validated.
- **Runtime source-profile projection — Complete.** The source-scoped value reaches the existing
  canonical retrieval candidate unchanged.
- **Pull Sources and transcript adapter — Complete.** Existing adapter selection/request
  construction preserves the field; hint-first discovery and diagnostics are operational.
- **Validation, provenance, and identity — Complete.** Hints do not bypass validation or become
  canonical artifact identity; ordinary retrieved evidence contracts remain authoritative.
- **Coverage semantics — Complete.** TASK-051 indeterminate behavior is preserved.
- **Live provider behavior — Usable with limitations.** The Amazon listing participated, but its
  current link volume exhausted the unchanged per-page limit before a candidate was admitted.
- **Next architectural milestone.** Continue with the roadmap's governed knowledge/retrieval work;
  broader transcript discovery is intentionally not introduced here.
