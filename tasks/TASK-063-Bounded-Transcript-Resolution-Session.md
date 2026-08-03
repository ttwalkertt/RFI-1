# TASK-063 — Bounded Transcript Resolution Session

## Status

Complete

---

## Summary

Replace production transcript seed graph crawling with a bounded run-level resolution
session.

Normal transcript acquisition currently executes one independent graph traversal for each
learned seed and then executes a configured fallback pipeline. Each traversal receives a fresh
page, byte, host, redirect, and elapsed-time budget. Learned transcript pages commonly converge
on the same archive graph, producing repeated network work and brittle topology-dependent
behavior.

TASK-063 consolidates learned seeds into one resolution phase, shares one ephemeral resource
context with a conditional configured fallback, classifies fetched seed pages from content, and
admits only direct transcript documents or direct links from one listing page. It does not create
a larger run-level crawler.

---

## Objective

For one transcript acquisition run:

1. canonicalize learned seeds in repository FIFO order;
2. fetch every distinct learned seed at most once;
3. classify each fetched page as a transcript document, transcript listing, unsupported page, or
   failed fetch;
4. validate transcript documents directly through the existing retrieval contract;
5. admit only immediate transcript-document links from listing pages;
6. invoke at most one configured archive fallback when learned resolution produces no validated
   `latest` result;
7. share one run-level budget and response cache across both phases; and
8. preserve existing selector, persistence, learning, checkpoint, and replay behavior.

---

## Architectural Decision

Production transcript acquisition is a bounded resolver, not a general crawler.

The resolver may fetch supplied seed pages and candidate documents. It shall not recursively
follow listing-to-listing links, paginate archives, or traverse a discovered graph. Search-engine
results shall not become an implicit fallback in this milestone.

Normal acquisition may contain two deterministic phases:

1. one consolidated learned-seed resolution phase; and
2. one configured archive fallback phase, executed only when existing engine terminal behavior
   requires another phase.

Both phases belong to one run-level resource session. This supersedes the normal-acquisition
per-learned-seed trial rule in `docs/design/TRANSCRIPT_LLM_SEED_RECOVERY.md`. Operator-supplied and
future recovery seeds remain exact single-seed resolver invocations.

---

## Page Classification Contract

Every successfully fetched seed page receives exactly one classification:

- `transcript_document`: existing transcript structure evidence is present;
- `transcript_listing`: the HTML page contains at least one immediate eligible transcript link;
- `unsupported`: neither document nor listing evidence is sufficient;
- `failed`: retrieval, redirect, media, or parsing failed.

Classification shall use response content and media evidence. URL or link text terminology alone
shall not classify the fetched page as a transcript document.

Classification is not durable validation. Transcript documents still pass the existing firm,
date, content, selection, persistence, learning, and checkpoint contracts.

---

## Ordering Contract

Canonical learned seeds preserve repository FIFO order. Within one seed, immediate transcript
links preserve the existing deterministic candidate rank and tie-breakers.

For `latest`, the effective execution order remains:

```text
learned seed FIFO position
→ existing within-seed candidate rank
→ existing deterministic candidate tie-breakers
→ configured fallback
```

The first validated result remains terminal.

For `first_in_date_range`, existing candidate qualification and global earliest validated event
date selection remain authoritative.

---

## Run-Level Resource Contract

One ephemeral session shall account for:

- fetched pages;
- response bytes;
- elapsed time;
- redirects;
- distinct hosts;
- canonical seed pages;
- admitted direct links; and
- candidate retrievals and validations through the existing policy ceilings.

The budget shall not reset between learned resolution and configured fallback. Budget exhaustion
remains explicit and shall not be reclassified as empty successful coverage.

The session may cache exact fetched responses by canonical URL so classification and later
validation do not repeat the same request. The cache is run-local, bounded by the existing byte
and page policy, and never persisted.

---

## Identity and Provenance

- Use the existing conservative transcript URL normalizer for seed and fetch identity.
- Use TASK-062 `CandidateIdentity` for stable candidate equivalence.
- Use TASK-062 `DiscoveryOccurrence` for seed, phase, alias, and rank attribution.
- Retain the first canonical seed occurrence as authoritative while reporting bounded duplicate
  seed counts.
- Do not introduce another candidate, checkpoint, or learning identity.

---

## Invocation Contracts

### Normal acquisition

- Consolidate canonical learned seeds into one learned phase.
- Use at most the first configured HTTP(S) discovery hint as the fallback archive.
- Do not submit a web-search query.

### Operator-injected acquisition

- Resolve only the supplied canonical seed.
- Do not add learned seeds or the configured fallback.
- Preserve the existing HTTP request and response contract.

### Future LLM recovery

- A proposed URL remains one temporary exact-seed resolver invocation.
- No LLM classification, ranking, traversal, or persistence behavior is added by this task.

---

## Required Invariants

1. Production transcript resolution performs no recursive listing traversal.
2. Canonically equivalent seeds are fetched once per run.
3. A fetched response is not downloaded again for validation within the same run.
4. Learned seed FIFO authority is preserved.
5. A configured fallback is attempted at most once.
6. Successful `latest` learned resolution prevents fallback execution.
7. Each stable candidate is evaluated at most once by the engine.
8. One run-level budget covers learned and fallback work.
9. Partial, failed, and budget-exhausted work is never reported as unchanged or complete-empty.
10. Existing candidate conflicts remain fail closed.
11. Existing persistence, learning, checkpoint, replay, and repository conflict semantics remain
    unchanged.
12. No seed-origin-specific persistence or checkpoint branch is introduced.

---

## Explicitly Out of Scope

Do not implement:

- recursive BFS or DFS transcript crawling;
- pagination traversal;
- unrestricted search-engine fallback;
- browser automation;
- LLM page classification, crawling, ranking, or validation;
- new selector or ranking policy;
- learning or checkpoint policy changes;
- repository schema changes or state repair;
- historical backfill;
- operator UI changes.

The pre-existing graph-discovery implementation may remain temporarily as a compatibility seam
for direct legacy discovery callers, but normal and injected engine acquisition shall not invoke
it. Removal of that compatibility implementation is a separate cleanup after all callers migrate.

---

## Required Tests

Add focused tests proving:

1. a learned transcript page is classified from content, fetched once, validated directly, and
   causes no outward listing traversal;
2. canonically duplicate learned seeds are fetched once while retaining bounded attribution;
3. multiple learned transcript pages do not crawl their shared archive links;
4. a listing seed admits only immediate transcript-document links;
5. a listing-to-listing link is not followed;
6. one configured archive fallback runs only after learned `latest` resolution has no validated
   result;
7. successful learned `latest` acquisition prevents fallback execution;
8. learned FIFO and within-seed order remain deterministic;
9. `first_in_date_range` terminal selection remains unchanged;
10. response reuse prevents classification/validation refetch;
11. one budget is shared across learned and fallback phases and cannot reset;
12. budget exhaustion remains explicit;
13. operator injection resolves only its supplied seed;
14. a genuinely conflicting `CandidateIdentity` still fails closed;
15. replay and checkpoint behavior remain unchanged.

Use captured Amazon, IBM, and Western Digital seed shapes where multiple learned transcript pages
previously converged on the same archive graph.

---

## Validation

Run:

- focused TASK-063 tests;
- TASK-057 regressions;
- TASK-058 regressions;
- TASK-059 regressions;
- TASK-060 regressions;
- TASK-061 regressions;
- TASK-062 regressions;
- relevant transcript discovery, engine, repository, API, replay, and checkpoint tests;
- full `make validate`.

Perform a deliberate complexity and robustness review confirming:

- production code uses a resolver rather than a new crawler;
- page classification has one definition;
- run-level budget/cache ownership has one definition;
- selector ordering is unchanged;
- no second candidate identity, checkpoint model, or persistence path exists;
- no operator/learned seed-origin persistence special case exists;
- diagnostics are bounded.

---

## Repository Requirements

Work on:

```text
codex/task-063-bounded-transcript-resolution-session
```

Commit and push completed work. Do not merge and do not open a pull request.

If corrective work occurs after package generation, delete the existing TASK-063 package and
architectural review report before beginning the correction. Generate a new package only from the
final validated branch head.

---

## Review Package

Generate a complete verified TASK-063 review package containing:

- architectural summary and superseded trial rule;
- page-classification contract;
- resolution sequence and ordering proof;
- proof that production performs no recursive crawl;
- canonical seed and response-reuse evidence;
- shared run-level budget evidence;
- fallback and injected-seed boundaries;
- selector, persistence, learning, checkpoint, and replay compatibility evidence;
- Amazon, IBM, and Western Digital topology regressions;
- focused and full validation results;
- complexity and robustness review;
- assumptions and limitations;
- package manifest and SHA-256 verification.
