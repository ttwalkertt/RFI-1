# TASK-053 Verification Report

## Result

TASK-053 is Done. `max_links_per_page` now limits normalized, deduplicated,
transcript-eligible outbound links. A page is no longer rejected because its raw anchor count
exceeds the traversal allowance. No acquisition limit changed.

## Root Cause and Repaired Boundary

`BoundedTranscriptDiscovery.traverse()` previously extracted and sorted every anchor, compared the
raw `parser.links` length with `max_links_per_page`, and sliced that raw list. Normalization and the
existing transcript-candidate check happened only inside the sliced loop. Directory navigation,
social links, legal links, assets, duplicates, fragments, and non-HTTP targets could therefore
consume the allowance or cause exhaustion before eligible transcript links were considered.

The repaired boundary is:

1. fetch the page;
2. extract raw anchors;
3. resolve absolute HTTP(S) URLs, remove fragments, and deduplicate by normalized URL;
4. retain transcript candidates and transcript-oriented intermediate pages;
5. prioritize candidate links before intermediate pages;
6. admit at most `max_links_per_page` eligible links.

Plural `transcripts` path evidence is normalized to the existing singular transcript discovery
token for candidate classification. This is provider-neutral and does not alter ordinary HTML/PDF,
date, firm-identity, host, provenance, or artifact validation.

Exhaustion is now reported only when the eligible list has members beyond the per-page allowance.
The concise diagnostics `raw_hyperlinks`, `eligible_hyperlinks`, and `traversed_hyperlinks` expose
the three relevant counts.

## Files Changed

- `src/rfi/discovery.py`: moves enforcement after normalization, deduplication, eligibility, and
  prioritization; adds bounded traversal diagnostics.
- `tests/test_task053.py`: covers raw-link noise, post-filter bounds, prioritization, hint-first
  behavior, ordinary validation, and indeterminate coverage.
- `tests/test_task048a.py`: updates legacy bound fixtures so they exercise eligible links under the
  corrected semantics.
- `scripts/task053_traversal_budget.py`: records the bounded Amazon live proof.
- `Makefile`: adds reproducible `task053-test` and `task053-proof` targets.
- `docs/operator-guide.md`: documents the corrected per-page limit semantics.
- `TASKS.md`, `tasks/TASK-053-apply-link-traversal-budget-after-eligibility-filtering.md`, and
  `docs/design-baseline.json`: record task completion and refresh governed roadmap metadata.
- `docs/TASK-053-review.md`: provides this verification and architectural review package.

## Focused Verification

Command:

```sh
make task053-test
```

Result: PASS, 49 tests. The target includes TASK-053, TASK-052, TASK-048A, Pull Workflow/TASK-051
coverage paths, and TASK-016 SEC adapter regressions.

Focused observable evidence includes:

- 42 raw links, one eligible link, one traversed link, and no exhaustion;
- three eligible links capped at two traversed links with
  `exhausted_budget=max_links_per_page`;
- candidate links admitted before transcript-oriented intermediate pages;
- hint-first acceptance with zero search queries;
- ordinary transcript validation retained;
- eligible-bound exhaustion retained as indeterminate coverage.

## Full Validation

Command:

```sh
make validate
```

Result: PASS. All 477 unit tests passed, followed by every repository demonstration, offline
provider proof, lint, format, type, import, documentation, design-baseline, and source-archive gate.

## Amazon Live Proof

Command:

```sh
make task053-proof
```

On 2026-07-31, the production adapter reported:

```json
{
  "configured_hint_fetched_first": true,
  "result": "rejected",
  "diagnostics": {
    "search_queries": 0,
    "configured_hint_status": "used",
    "raw_hyperlinks": 423,
    "eligible_hyperlinks": 77,
    "traversed_hyperlinks": 30,
    "candidate_urls": 30,
    "validation_failures": 30,
    "bounds_exhausted": true,
    "exhausted_budget": "max_links_per_page"
  }
}
```

The directory was not rejected from its 423 raw anchors. Eligible links were filtered and
candidate-prioritized; exactly 30 were admitted, and all 30 reached ordinary validation. The live
documents were rejected by that unchanged validation. Search remained unused because the hint
produced candidates. Coverage remained indeterminate because 47 additional eligible links were
outside the unchanged allowance.

## Bounds and Compatibility

`config/discovery-policies.json` and `docs/discovery-policies-v1.schema.json` are unchanged. The
Amazon extended policy remains 8 search queries, 15 results per query, 30 links per page, depth 3,
75 pages, 15 hosts, 52,428,800 bytes, and 180 seconds.

TASK-052 source-scoped hint projection, hint-first ordering, and no-search-on-candidate behavior pass
their existing tests. TASK-051 indeterminate coverage behavior passes both the focused eligible
exhaustion test and Pull Workflow regressions. SEC tests and the complete validation suite establish
that unrelated adapters are unchanged. Configuration hints remain retrieval intent and do not enter
provenance or artifact identity.

## Architectural Status Summary

- **Transcript discovery — Complete.** Retrieval, extraction, normalization/deduplication,
  eligibility, prioritization, and bounded traversal now have the required semantic ordering.
- **Discovery policy enforcement — Complete.** Existing numeric page, host, byte, query, depth,
  elapsed-time, result, and per-page link bounds remain enforced without expansion.
- **Configured hint projection and ordering — Complete.** TASK-052 contracts and hint-first behavior
  remain intact.
- **Transcript validation and evidence ingress — Complete.** Candidate validation, provenance,
  artifact identity, immutable bytes, and repository ingress are unchanged.
- **Coverage reporting — Complete.** Bounded eligible-link exhaustion remains explicit and
  indeterminate under TASK-051 semantics.
- **Live transcript acquisition — Usable with limitations.** The Amazon directory yields 30 bounded
  candidates, but its current documents are rejected by ordinary validation.
- **Next architectural milestone.** Resume the roadmap's governed knowledge and retrieval work;
  broader transcript discovery and provider-specific behavior remain out of scope.
