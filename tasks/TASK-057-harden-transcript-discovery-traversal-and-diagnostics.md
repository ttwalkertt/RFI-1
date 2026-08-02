# TASK-057 — Harden Transcript Discovery Traversal and Diagnostics

## Status

Complete; acquisition correctness baseline hardened

## Objective

Harden earnings-call transcript discovery so that RFI explores a deterministic, relevance-prioritized link graph; prevents cycles by normalized URL identity; and produces actionable diagnostics for discovery, transport, eligibility, validation, and bounded-search failures.

Replace the existing visited-link-count traversal limit with explicit cycle and duplicate detection. Preserve independent bounds for pages, bytes, hosts, depth, candidate evaluation, redirects, queries, and elapsed work.

## Problem Statement

A full Pull Sources run produced sixteen indeterminate transcript results and two retrieval failures across twenty configured firms. The indeterminate results separated into three recurring classes:

1. **Link eligibility collapse** — configured hint pages were fetched and contained many raw hyperlinks, but no links became eligible or traversable.
2. **Configured hint transport failure** — the configured starting page could not be fetched.
3. **Candidate unavailable or rejected** — discovery produced a candidate, but retrieval or validation could not establish a usable transcript.

Current diagnostics often collapse these outcomes into the general statement that bounds were exhausted or coverage remained indeterminate. In many cases, no bound was actually exhausted.

The existing link-count control also constrains traversal by the number or position of encountered links rather than by useful discovery work. It can stop before relevant links are evaluated and does not distinguish a genuinely large graph from cyclic navigation, duplicate edges, or repeated normalized URLs.

## In Scope

- Replace the visited-link-count traversal limit with normalized URL cycle and duplicate detection.
- Preserve independent bounded-search controls for:
  - fetched pages;
  - total bytes;
  - traversal depth;
  - distinct hosts;
  - candidate evaluations;
  - search queries;
  - redirects;
  - elapsed work.
- Introduce deterministic relevance ordering for newly discovered hyperlinks.
- Preserve discovery order:
  1. retained successful anchors;
  2. configured hints;
  3. bounded graph traversal and search.
- Add explicit diagnostics for:
  - raw links;
  - normalized unique links;
  - duplicate and cycle rejection;
  - eligibility rejection;
  - ranking and queue admission;
  - transport failure;
  - candidate retrieval failure;
  - candidate validation failure;
  - actual budget exhaustion;
  - actual fallthrough between discovery stages.
- Improve operator-facing result classifications and messages.
- Add focused transcript-discovery regression and reproducible failure evidence.

## Out of Scope

- Unbounded crawling.
- Automatic modification of external firm configuration.
- Operator-seeded URL acquisition.
- Generalization to press releases or other document classes.
- Model-based semantic ranking.
- Probabilistic or opaque learning.
- Removal of page, byte, host, depth, candidate, redirect, query, or time bounds.
- Changes to TASK-056 discovery-anchor persistence semantics.
- Broad redesign of acquisition checkpoints, artifacts, provenance, or pull orchestration.
- Per-firm configuration repair except where needed for deterministic fixtures.

## Required Architectural Model

Transcript discovery shall operate as a bounded directed graph traversal.

Each fetched page is a node. Each discovered hyperlink or redirect is an edge. Exact observed URLs remain available for provenance and diagnostics, while conservative normalized URL identities govern cycle and duplicate detection.

The traversal pipeline shall be:

```text
retained anchors
    ↓
configured hints
    ↓
fetch page
    ↓
extract exact links
    ↓
normalize identity
    ↓
reject self-reference, duplicate, queued, visited, and redirect cycles
    ↓
apply explicit eligibility rules
    ↓
rank deterministically
    ↓
admit new nodes to bounded priority queue
    ↓
fetch/evaluate candidates within independent resource bounds
```

## URL Identity and Cycle Detection

Use the repository's existing conservative URL-normalization contract where suitable. At minimum:

- lowercase scheme and host;
- normalize default ports;
- remove fragments;
- normalize path dot segments;
- preserve query parameters unless an existing adapter-specific rule explicitly permits otherwise.

Exact requested and resolved URLs must remain preserved.

Maintain distinct normalized sets for:

- queued nodes;
- visited nodes;
- active redirect chain;
- optionally rejected nodes where useful for diagnostics.

Reject and classify:

- direct self-reference;
- already queued URL;
- already visited URL;
- same normalized URL reached from a different parent;
- redirect cycle;
- longer graph cycle such as `A → B → C → A`.

Cycle and duplicate rejection shall not consume candidate-evaluation or page-fetch budgets.

## Deterministic Relevance Ordering

After cycle and duplicate rejection, eligible links shall be ordered using explicit deterministic signals. The implementation may follow established repository conventions, but the ordering must be inspectable and stable.

Signals should include, where applicable:

1. retained successful-anchor relationship;
2. configured-hint path or host relationship;
3. same authoritative host;
4. transcript and earnings terminology in anchor text or URL;
5. reporting-period relevance;
6. document-like path, extension, or content-type expectation;
7. shallower discovery depth;
8. normalized URL lexical order as the final tie-breaker.

Do not introduce model-generated relevance scores or mutable hidden weights.

The traversal budget shall constrain the number of highest-priority unique candidate nodes evaluated across the discovery run, not the first arbitrary links encountered on each page.

## Required Outcome Classification

Replace broad or misleading messages with explicit classifications.

At minimum distinguish:

- `no_eligible_links`
- `hint_fetch_timeout`
- `hint_http_failure`
- `hint_redirect_rejected`
- `candidate_not_found_within_bounds`
- `candidate_http_not_found`
- `candidate_access_denied`
- `candidate_unsupported_content_type`
- `candidate_requires_javascript`
- `candidate_empty`
- `candidate_validation_mismatch`
- `redirect_cycle`
- `discovery_budget_exhausted`
- `coverage_indeterminate`

Exact repository naming may vary, but the distinctions must remain explicit and testable.

An outcome must not claim that a bound was exhausted unless a named bound was actually exhausted.

## Required Diagnostics

Emit bounded structured diagnostics sufficient to reconstruct why traversal progressed or stopped.

At minimum include:

- adapter and history key;
- retained-anchor count and actual attempt sequence;
- configured-hint count and actual attempt sequence;
- raw hyperlink count;
- normalized unique hyperlink count;
- queue-admitted count;
- visited count;
- candidate-evaluated count;
- rejection counts by reason;
- cycle counts by type;
- bounded representative rejected links with query-sensitive values redacted;
- ranking reasons for bounded top candidates;
- actual transport failure class and HTTP status where available;
- redirect count and redacted final host;
- validation-failure counts by reason;
- actual named exhausted budget, if any;
- actual fallthrough from anchors to hints and from hints to traversal;
- final coverage classification.

Diagnostics must remain bounded and must not expose credentials, cookies, tokens, unredacted sensitive query parameters, artifact bodies, or an unbounded URL log.

## Required Operator Messages

The Pull Sources UI shall summarize the primary failure class without requiring the operator to inspect raw JSON.

Examples:

- **No eligible transcript links were identified on the configured page.**
- **The configured transcript hint timed out.**
- **The configured transcript hint returned HTTP 403.**
- **A transcript candidate was found but its content type is unsupported.**
- **Discovery exhausted the candidate-evaluation budget after evaluating 40 ranked unique links.**
- **Discovery completed without a candidate, but coverage remains indeterminate.**

Detailed structured diagnostics shall remain available beneath the summary.

## Required Invariants

- Discovery remains deterministic for identical repository state and identical fetched content.
- Retained anchors remain first in discovery order.
- Configured hints remain second.
- Broad traversal begins only after actual fallthrough.
- Exact URL provenance is never replaced by normalized identity.
- Query-distinct URLs remain distinct unless an existing adapter-specific rule says otherwise.
- Duplicate or cyclic edges do not consume useful-work budgets.
- No cycle can cause repeated page retrieval.
- No named budget may be reported exhausted unless it was actually reached.
- Transport failure, eligibility collapse, candidate failure, and budget exhaustion remain distinct.
- Existing acquisition transaction, checkpoint, artifact, provenance, and discovery-history contracts remain unchanged.
- Existing SEC acquisition behavior remains unchanged.
- No network request is made solely for diagnostic enrichment beyond governed traversal.

## Required Tests

### Cycle and duplicate control

- Direct self-link is rejected.
- `A → B → A` is detected.
- `A → B → C → A` is detected.
- Same normalized URL reached from multiple parents is fetched once.
- Fragment-only variants collapse to one identity.
- Host-case and default-port variants collapse correctly.
- Query-distinct URLs remain distinct.
- Redirect loops are detected.
- Duplicate and cycle rejection do not consume candidate or page budgets.
- Cyclic edges do not alter deterministic ordering of unique nodes.

### Ranking and bounded traversal

- Relevant links are evaluated before generic navigation links.
- Ranking is deterministic under reordered input HTML.
- Lexical tie-breaking is stable.
- Candidate budget applies to ranked unique nodes across the run.
- Page, byte, host, depth, query, redirect, and elapsed-work bounds remain enforced.
- Retained anchors precede hints.
- Hints precede graph traversal.
- Actual fallthrough is recorded.

### Classification and diagnostics

- Link eligibility collapse reports `no_eligible_links` or equivalent.
- Timeout and HTTP failures remain distinct.
- Candidate-unavailable subclasses are actionable.
- Budget exhaustion names the exact budget.
- Indeterminate coverage without exhaustion does not claim exhaustion.
- Rejection and cycle counts are correct.
- Representative diagnostics are bounded and redacted.
- Operator-facing messages match the primary structured classification.

### Compatibility

- TASK-056 anchor ordering and learning behavior remain intact.
- Existing transcript success, no-change, failure, checkpoint, and rollback behavior remain intact.
- Existing SEC adapters are unaffected.
- Full repository validation passes.

## Required Reproduction Evidence

Include deterministic fixtures or captured cases representing:

1. A page with many raw links but zero eligible links.
2. A configured hint timeout.
3. A configured hint HTTP failure.
4. A discovered but unavailable candidate.
5. A cyclic navigation graph.
6. A relevant transcript link positioned after many generic links.
7. A run where a named budget is genuinely exhausted.
8. A run where coverage is indeterminate without budget exhaustion.

For each case, provide the operator summary and structured diagnostics.

## Verification Package

Provide:

- before/after discovery behavior;
- cycle-detection evidence;
- deterministic ranking evidence;
- exact budget-accounting evidence;
- classification and operator-message evidence;
- redaction and bounded-diagnostics evidence;
- proof that TASK-056 anchor behavior remains intact;
- proof that acquisition evidence and unrelated durable state remain unchanged;
- focused test commands and results;
- full `make validate` result;
- changed-file inventory and committed patch;
- final Git status, commit hash, and pushed branch;
- commit-aware review package manifest and SHA-256.

## Acceptance Criteria

TASK-057 is complete when:

- transcript discovery uses normalized cycle and duplicate detection instead of a visited-link-count limit;
- cyclic or duplicate edges cannot consume useful-work budgets or cause repeated page fetches;
- newly discovered links are evaluated in deterministic relevance order;
- independent governed resource bounds remain in force;
- all major failure classes produce distinct, actionable structured diagnostics and operator messages;
- no result claims bounds exhaustion without naming an actually exhausted bound;
- TASK-056 retained anchors, existing acquisition semantics, and unrelated subsystems remain intact;
- focused tests and full repository validation pass;
- implementation and review evidence are committed and pushed on a task branch without merging.

## Corrective Hardening — Partial Success and Checkpoint Advancement

A live Western Digital pull retained 30 validated transcript artifacts, recorded one candidate
retrieval failure and one recoverable configured-hint timeout, but reported the transcript source
as `retrieval_failure`. Because engine checkpoint finalization was gated on a completely clean run,
the durable checkpoint also remained at its prior reporting period.

This corrective repair is limited to post-evaluation result semantics. Discovery, graph traversal,
transport, ranking, candidate ordering, validation, and checkpoint qualification policy remain
unchanged.

Required corrective behavior:

- one or more durable acquisitions take precedence over candidate-level failures;
- mixed durable acquisition and warning evidence produces the explicit operator outcome
  `success_with_warnings`;
- the primary operator summary describes retained acquisition rather than an earlier recoverable
  discovery failure;
- all discovery, transport, candidate retrieval, and validation warnings remain in structured
  diagnostics;
- a partial run advances to the highest successfully validated retained position under the
  existing checkpoint policy;
- checkpoint evidence is anchored to a successful attempt only;
- all-candidates-failed remains `retrieval_failure`;
- no-change and fail-closed validation behavior remain unchanged; and
- TASK-056 anchors continue to learn only from successful retained evidence.

Corrective acceptance additionally requires focused mixed-success, hint-timeout, checkpoint,
all-failed, no-change, and retained-anchor regressions; full repository validation; updated review
documentation; and a regenerated commit-aware TASK-057 review package from a clean committed
branch.

## Final Acquisition Correctness Baseline

The final corrective pass is limited to four architectural-review findings and introduces no new
discovery or acquisition capability:

- transcript-like PDF links enter the same typed proposal state as HTML links and continue through
  the existing TASK-048 retrieval, date, firm, media, and transcript validation boundary;
- requested redirect aliases converge on the normalized resolved transcript before adapter
  candidate emission, while every exact alias remains immutable discovery provenance;
- only expected transport and parsing exceptions become provider diagnostics inside discovery;
  unexpected implementation exceptions terminate through the acquisition engine as nonretryable
  `malformed_adapter` failures; and
- ordinary listing pages are fetched once during discovery and are not fetched again by the
  candidate retriever. Candidate bodies remain uncached and validation ownership remains wholly in
  `EarningsCallTranscriptAcquisition`.

Acceptance evidence must prove successful and failed PDF paths, redirect alias provenance and
single logical emission, transient timeout compatibility, nonretryable internal-defect
classification, provider-failure compatibility, listing fetch-once behavior, unchanged candidate
ordering, and unchanged validation outcomes. TASK-056 learning, TASK-057 partial-success and
checkpoint semantics, search, ranking, traversal order, and checkpoint qualification remain
unchanged.

## Required Architectural Status Summary

The completed review shall report the status and responsibility of:

- URL identity and exact provenance;
- graph cycle and duplicate control;
- deterministic relevance ordering;
- bounded traversal budgets;
- discovery outcome classification;
- operator diagnostics;
- retained-anchor integration;
- retained limitations and the next transcript-discovery milestone.


---

# Architectural Clarifications (Revision 2)

The following requirements tighten deterministic behavior and remove implementation ambiguity.

## Additional Determinism Requirements

- The complete candidate ordering algorithm shall be deterministic. For identical repository state and identical fetched content, the ranked candidate order shall be identical across executions. Repository iteration order or container ordering shall not influence traversal.
- Queue admission shall be deterministic. Candidates with identical ranking signals shall be ordered using the documented lexical normalized-URL tie breaker.

## Useful-Work Accounting

- Cycle detection and duplicate elimination occur before useful-work accounting.
- Rejecting a duplicate node, cyclic edge, previously visited node, or redirect cycle shall not consume page-fetch, candidate-evaluation, or traversal budgets.

## Queue Bound

- Queue growth shall itself be bounded and shall not exceed the governed candidate-evaluation budget by more than a documented deterministic implementation constant.

## Ranking Explainability

For each admitted candidate, bounded diagnostics shall record the ranking factors responsible for admission (for example: retained-anchor, configured-hint host, transcript keyword, discovery depth). Numeric heuristic scores are neither required nor desired.

## Redirect Graph Invariant

Redirect traversal participates in the same normalized graph identity as ordinary hyperlink traversal. Redirects shall not maintain an independent visited graph.

## Additional Graph Metrics

Diagnostics shall include, at minimum:

- nodes_discovered
- nodes_enqueued
- nodes_visited
- edges_examined

## Representative Rejections

Representative rejected links shall include bounded examples for each rejection class rather than examples from only one class.

## Explicit Learning Boundary

Traversal ordering shall be derived only from:

- deterministic repository state;
- retained discovery anchors;
- configured hints;
- explicit ranking rules;
- fetched content.

Previous discovery outcomes shall not influence ranking except through the governed TASK-056 retained-anchor history.

## Additional Reproduction Fixture

Include a deterministic fixture containing hundreds of cyclic navigation links with a single valid transcript link to prove that cycle rejection preserves useful-work budget and still reaches the transcript.

## Stronger Acceptance Criterion

Every structured discovery outcome shall identify the earliest stage at which forward progress became impossible, including one of:

- transport
- eligibility
- candidate retrieval
- candidate validation
- budget exhaustion
- indeterminate coverage

This stage shall be reflected consistently in structured diagnostics and operator-facing summaries.
