# TASK-053 — Apply Link Traversal Budget After Eligibility Filtering

## Status

Done

## Objective

Correct the semantics of `max_links_per_page` so that it limits eligible outbound link traversal rather than the raw number of hyperlinks present on a fetched page.

This task changes only where the existing traversal budget is applied. It does not increase any acquisition limit or alter discovery policy.

## Problem Statement

TASK-052 restored configured transcript discovery hints and proved that the earnings transcript adapter now:

- receives source-scoped `RetrievalCandidate.discovery_hints`;
- traverses configured URL hints before issuing search requests;
- preserves existing acquisition limits;
- preserves TASK-051 indeterminate-coverage semantics.

The Amazon live proof then exposed a separate defect.

The configured Stock Analysis transcript index was fetched first and no search queries were issued. However, the page contained more than the configured `max_links_per_page=30` raw hyperlinks.

The current implementation appears to apply `max_links_per_page` to the page's raw hyperlink count. Because the hinted page contained more than 30 links, discovery stopped before filtering and traversing eligible transcript links.

This causes directory and index pages to be rejected because of unrelated navigation links, even when the number of relevant transcript links is well within the configured traversal budget.

## In Scope

- Locate the current enforcement point for `max_links_per_page`.
- Separate hyperlink extraction from eligibility filtering, prioritization, and traversal.
- Apply the existing budget only after eligible outbound links have been identified.
- Preserve hint-first ordering introduced by TASK-052.
- Preserve existing diagnostics and indeterminate-coverage behavior.
- Add focused regression coverage for pages with many irrelevant links and a small number of eligible transcript links.
- Add a bounded Amazon live proof using the configured transcript index hint.

## Out of Scope

- Increasing `max_links_per_page`.
- Increasing page, host, query, byte, or other acquisition limits.
- Adding unbounded search.
- Changing configured discovery-hint contracts.
- Changing transcript candidate validation.
- Adding Amazon-, Stock Analysis-, or provider-specific production logic.
- Changing provenance, artifact identity, or repository-ingress behavior.
- Changing TASK-051 coverage semantics.
- General crawler redesign.
- Changing unrelated adapters or source families.

## Required Semantics

The discovery pipeline must conceptually perform these steps:

1. Fetch the page.
2. Extract hyperlinks.
3. Normalize and deduplicate links.
4. Filter out ineligible links.
5. Prioritize the remaining eligible links.
6. Traverse no more than `max_links_per_page` eligible links.

A page containing more than `max_links_per_page` raw hyperlinks must not be rejected solely because of its total hyperlink count.

`max_links_per_page` must constrain outbound traversal work, not page eligibility.

Budget exhaustion may be reported only when additional eligible links remain after the configured traversal allowance has been consumed.

## Eligibility and Ordering

The implementation must use the existing link-eligibility and transcript-discovery rules.

Do not create provider-specific filters to make the Amazon example pass.

Configured URL hints must remain ahead of search requests.

If a configured hint yields an acceptable transcript candidate within existing bounds, generic search must not be issued.

If the hint yields no acceptable candidate, existing bounded fallback behavior may continue unchanged.

## Required Invariants

Preserve:

- the numeric value and policy meaning of all acquisition limits;
- TASK-052 source-scoped hint projection;
- TASK-052 hint-first discovery ordering;
- canonical `RetrievalCandidate.discovery_hints`;
- transcript validation;
- structured diagnostics;
- provenance separation;
- artifact identity;
- immutable retained bytes;
- repository ingress;
- TASK-051 indeterminate-coverage semantics;
- SEC and unrelated adapter behavior.

## Required Tests

Add focused regression coverage for at least the following cases.

### 1. Raw link count exceeds the budget

A fixture page contains more than `max_links_per_page` raw hyperlinks.

Most links are irrelevant.

The page also contains one or more eligible transcript links.

Assert that eligible links are still considered.

### 2. Eligible traversal remains bounded

A fixture page contains more eligible links than `max_links_per_page`.

Assert that no more than the configured number are traversed.

Assert that diagnostics report `max_links_per_page` exhaustion only because eligible links remained beyond the traversal allowance.

### 3. Filtering occurs before budget application

Assert that irrelevant navigation, social, asset, legal, and unrelated links do not consume the eligible traversal budget.

### 4. Hint-first behavior remains intact

A configured URL hint yields an eligible transcript candidate.

Assert that the hinted page is fetched before search and that no generic search request is issued when the candidate is accepted.

### 5. Ordinary validation remains intact

A hinted page links to an invalid or non-transcript document.

Assert that normal transcript validation rejects it.

### 6. Missing or unusable hints

Assert that no-hint and unusable-hint behavior remain compatible with TASK-052.

### 7. Coverage semantics

Assert that bounded exhaustion still produces accurate TASK-051 coverage semantics.

### 8. Unrelated adapter stability

Assert that SEC and other unrelated source-family behavior is unchanged.

## Live Proof

Use the Amazon transcript configuration introduced by TASK-052.

The configured hint is:

```text
https://stockanalysis.com/stocks/amzn/transcripts/
```

Demonstrate that:

- the configured hint page is fetched first;
- `search_queries=0` when the hint path yields an acceptable candidate;
- the raw page link count may exceed 30 without causing immediate rejection;
- eligible transcript links are filtered and prioritized;
- no more than 30 eligible links are traversed;
- no acquisition limits are increased;
- the target transcript is either acquired normally or rejected by ordinary validation with accurate diagnostics;
- configured hints remain distinct from provenance and artifact identity.

## Review Actions

Review specifically:

- where raw hyperlinks are counted;
- where links are normalized and deduplicated;
- where eligibility filtering occurs;
- where eligible links are prioritized;
- where the traversal budget is decremented;
- how `exhausted_budget=max_links_per_page` is determined;
- whether diagnostics distinguish raw extracted links from eligible and traversed links;
- whether TASK-052 ordering remains intact;
- whether any provider-specific behavior was introduced.

## Verification Package

Provide:

- root-cause analysis;
- exact budget-enforcement boundary before and after the repair;
- files changed and why;
- focused test commands and results;
- full `make validate` result;
- Amazon live-proof output;
- proof that acquisition limits were not changed;
- proof that traversal did not exceed the configured limit;
- proof that unrelated adapters remained stable;
- final Git status;
- commit hash and pushed branch.

## Acceptance Criteria

TASK-053 is complete when:

- `max_links_per_page` limits eligible outbound link traversal rather than raw hyperlink count;
- pages with many irrelevant links are not rejected before eligible transcript links are considered;
- traversal never exceeds the existing configured limit;
- exhaustion is reported only when additional eligible links remain beyond the allowance;
- TASK-052 hint-first behavior remains intact;
- TASK-051 coverage semantics remain intact;
- no acquisition limit is increased;
- focused tests and full repository validation pass;
- the completed task and verification evidence are committed and pushed on the task branch.
