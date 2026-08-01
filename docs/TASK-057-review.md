# TASK-057 Verification Report

## Result

TASK-057 is Complete. Transcript discovery now explores a bounded deterministic directed graph,
uses the repository's conservative normalized URL identity for cycle and duplicate control, ranks
unique nodes with explicit stable signals, and reports actionable structured and Pull Sources
diagnostics. Candidate retrieval and validation remain owned by the TASK-048 retriever.

## Before and After

Before, `BoundedTranscriptDiscovery` used a FIFO of exact URL strings. A per-page eligible-link
slice doubled as the practical visited-link control, normalization was local and incomplete,
candidate proposals were ordered while each page happened to be processed, and fetch, eligibility,
candidate, and coverage failures often collapsed into generic indeterminate wording.

After:

1. exact hyperlinks and redirect results are observed as graph edges;
2. shared conservative URL normalization supplies node identity;
3. self, duplicate-edge, queued, visited, ancestor, and redirect cycles are rejected before useful
   work is charged;
4. eligible nodes enter a deterministic priority queue;
5. candidate proposals are globally ordered across parent pages with retained-anchor, configured-
   hint, and bounded-traversal stage precedence;
6. the existing transcript retriever independently evaluates at most the governed number of
   ranked unique proposals;
7. structured diagnostics and Pull Sources expose the primary actual outcome.

Exact requested and resolved URLs still flow into provenance. Normalized identity is never used as
a substitute for observed provenance.

## Separation of Responsibilities

- `BudgetedTranscriptTransport` owns page, byte, host, elapsed, and observed redirect accounting.
- `BoundedTranscriptDiscovery` owns graph identity, queued/visited/ancestor state, eligibility,
  deterministic ranking, queue admission, search fallthrough, and bounded graph diagnostics.
- `EarningsCallTranscriptAcquisition` continues to own candidate HTTP retrieval, date, content
  type, transcript structure, speaker evidence, firm identity, and artifact-envelope validation.
- `EarningsTranscriptPullAdapter` composes graph proposals with retriever evaluation and maps the
  two layers into one bounded diagnostic result.
- `PullWorkflow` selects the adapter's primary operator summary without interpreting graph JSON.

This preserves the acquisition/evidence boundary and avoids a second validation path in traversal.

## Corrective Maintainability Hardening

The original implementation had two brittle internal seams even though its observable discovery
behavior was correct. First, the Pull Sources adapter reconstructed candidate failure subtypes by
searching human-readable exception text. Second, the traversal function represented proposals,
failures, samples, counters, and graph identity sets as unrelated locals and tuple/dictionary
shapes whose consistency depended on coordinated mutation.

The repair keeps the compatible `candidate_unavailable` and `candidate_invalid` acquisition
categories, while the retriever now assigns one explicit `CandidateFailureCode` where retrieval or
validation fails. The stable code and typed HTTP status travel in structured failure details;
messages are presentation only. Counters, bounded samples, primary classifications, and Pull
Sources summaries all consume that code. Focused tests exercise HTTP not found, access denied,
timeout, unsupported content, empty content, JavaScript-required content, validation mismatch, and
other retrieval failure, and prove that changing message wording cannot change classification.

`GraphTraversalState`, `RankedCandidateProposal`, `DiscoveryFailureRecord`, and bounded typed sample
records now make graph transitions and ordering contracts explicit. Queue admission, proposal
admission, rejection, cycle, visit, and failure metrics are projected from this state instead of
duplicated counters and ad hoc tuples. This is a minimum internal extraction: transport still owns
fetch and resource accounting, graph exploration still owns normalized-node ordering, and the
retriever still exclusively decides whether a proposal is a valid transcript.

Behavior is unchanged. URL normalization, retained-anchor and hint precedence, ranking keys,
cycle/duplicate rules, all governed limits, operator messages, and retriever validation rules are
identical. The regenerated eight-case reproduction JSON is byte-for-byte equal to the prior
evidence, and TASK-056 retained-anchor compatibility remains green.

## URL Identity, Cycle Control, and Determinism

The retained-anchor normalizer was extracted into one shared acquisition URL-identity module and
extended to the graph and retriever. It lowercases scheme/host, removes default ports and fragments,
normalizes dot segments, preserves query parameters, and retains trailing-slash meaning.

Focused tests prove direct self-reference, fragment collapse, host/default-port collapse, query-
distinct identity, two- and three-node ancestor cycles, redirect cycles, and multi-parent fetch-
once behavior. Duplicate/cyclic edges are rejected before page fetch or candidate evaluation. The
same reordered HTML yields byte-equivalent proposal ordering and ranking diagnostics. A separate
fixture proves globally stronger candidates discovered under a later parent precede weaker
candidates from an earlier parent.

Ranking uses inspectable Boolean/ordinal signals only: stage relationship, configured-hint
relationship, same authoritative host, transcript/earnings terms, period evidence, document-like
path, depth, normalized URL, and label. There are no learned, adaptive, probabilistic, or hidden
weights. TASK-056 retained-anchor history is the only adaptive input.

## Budgets and Accounting

Existing page, byte, host, depth, link-admission, query, search-result, and elapsed limits remain.
The existing retriever maximum of 40 candidate evaluations and urllib redirect maximum of 10 are
now explicit named policy fields for every discovery class. Their numeric behavior did not expand.

Diagnostics name `max_candidate_evaluations`, `max_redirects`, or another actual policy field only
when that limit is reached. A fixture with two ranked proposals and an evaluation limit of one
fetches/evaluates one candidate and reports exactly that count. Indeterminate-without-exhaustion
reports no exhausted budget.

## Diagnostics and Operator Messages

Every result includes adapter/history identity, retained-anchor and configured-hint attempt order,
stage fallthrough, raw/normalized/eligible counts, queue and visited counts, proposal/evaluation
counts, rejection and cycle counters, bounded redacted representative URLs, bounded ranking
reasons, transport class/status, redirect count/final host, candidate retrieval and validation
classes, exact exhausted budget, and final coverage classification.

Representative URL collections are capped at eight and ranking collections at ten. Query values
are replaced with `REDACTED`; credentials, cookies, tokens, bodies, and unbounded URL logs are never
included. No diagnostic-only network request was added.

Pull Sources now presents messages such as:

- `No eligible transcript links were identified on the configured page.`
- `The configured transcript hint timed out.`
- `The configured transcript hint returned HTTP 403.`
- `A transcript candidate was found but its content type is unsupported.`
- `Discovery exhausted the candidate-evaluation budget after evaluating 1 ranked unique links.`
- `Discovery completed without a candidate, but coverage remains indeterminate.`

## Reproduction Evidence

`make task057-proof` deterministically writes
`.artifacts/task057-validation/reproduction.json`. Its eight cases are:

1. 50 raw links, 50 normalized unique links, zero eligible links, and `no_eligible_links`;
2. configured hint timeout and `hint_fetch_timeout`;
3. configured hint HTTP 403 and `hint_http_failure`;
4. discovered candidate HTTP 404 and `candidate_http_not_found`;
5. a three-node cyclic graph, three visited nodes, and one ancestor-cycle rejection;
6. a relevant transcript after 25 generic transcript-navigation links, ranked first;
7. genuine `max_candidate_evaluations` exhaustion after one evaluation;
8. indeterminate coverage with no exhausted budget.

Each record contains its operator summary and bounded structured diagnostics.

## Compatibility and Durable-State Evidence

The 80-test focused target includes TASK-048, TASK-048A, TASK-052, TASK-053, TASK-056, Pull
Workflow, and SEC adapter regressions. TASK-056 tests prove anchor LIFO ordering, exact requested/
resolved provenance, atomic history updates, failed-attempt non-learning, profile-revision survival,
checkpoint behavior, and rollback. TASK-048 tests prove validation, immutable bytes, provenance,
and repository ingress remain unchanged. TASK-015/016 tests prove Pull Sources and SEC behavior.

No storage schema, acquisition checkpoint, transaction, artifact, observation, immutable-content,
or discovery-history persistence contract changed. The browser proof wait condition now waits for
both API responses and rendered checkboxes, removing a validation race without changing production
behavior or durable state.

## Verification Results

- `make task057-test`: PASS, 84 focused and compatibility tests.
- `make task057-proof`: PASS, eight deterministic reproduction cases.
- `git diff --check`: PASS.
- `make validate`: PASS. All 533 unit tests passed, followed by every repository demonstration,
  offline provider proof, lint, format, type, import, documentation, design-baseline, and build gate.

## Changed-File Inventory

- Graph/runtime: `src/rfi/discovery.py`, `src/rfi/acquisition/url_identity.py`,
  `src/rfi/acquisition/earnings_transcripts.py`, `src/rfi/acquisition/repository.py`, and
  `src/rfi/pull/workflow.py`.
- Governed policy: `config/discovery-policies.json` and
  `docs/discovery-policies-v1.schema.json`.
- Tests/evidence: `tests/test_task057.py`, `scripts/task057_reproduction.py`,
  `tests/test_acquisition.py`, `tests/test_foundation.py`, `tests/task017_browser_harness.js`, and
  `Makefile`.
- Documentation/governance: `ARCHITECTURE.md`, `TASKS.md`, the TASK-057 ticket,
  `docs/operator-guide.md`, `docs/design-baseline.json`, this report, and
  `scripts/check_baseline.py`.
- Review packaging: `scripts/generate_task057_review.py`.

The corrective repair itself changes `src/rfi/acquisition/earnings_transcripts.py`,
`src/rfi/discovery.py`, `tests/test_task057.py`, `scripts/task057_reproduction.py`, and this report.

## Limitations

- Link eligibility remains transcript-specific and deterministic; it does not infer semantics from
  arbitrary navigation text.
- Redirect diagnostics report redirect URLs exposed by the transport boundary; urllib still owns
  its fixed maximum redirect behavior.
- Coverage remains indeterminate unless existing authoritative-listing semantics establish
  completeness.
- Press-release discovery is not implemented by this task.

## Architectural Status Summary

- **Transcript graph exploration — Complete.** Explicit normalized graph state, deterministic
  priority ordering, cycle control, and bounded stage fallthrough are operational.
- **Transcript transport bounds — Complete.** Page, byte, host, elapsed, and redirect controls are
  independently named and observable.
- **Candidate retrieval and validation — Complete.** The TASK-048 retriever remains the single
  candidate evidence gate with an explicit independent evaluation bound.
- **Discovery diagnostics and Pull Sources presentation — Complete.** Major transport,
  eligibility, candidate, exhaustion, and coverage outcomes are actionable and testable.
- **Retained-anchor history — Complete.** TASK-056 ordering, persistence, and atomic learning
  semantics are unchanged.
- **Acquisition evidence and SEC verticals — Complete and unaffected.** Checkpoints, transactions,
  immutable bytes, provenance, observations, and SEC adapters pass compatibility validation.
- **Live provider variability — Usable with limitations.** External pages may still require
  JavaScript, deny access, or expose no transcript-eligible links; these now fail diagnostically.
- **Next architectural milestone — Press-release vertical.** The explicit transport/graph/candidate
  boundaries and inspectable bounded-search outcomes provide reusable architectural seams, while
  press-release eligibility and validation remain a separate future vertical.
