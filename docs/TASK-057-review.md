# TASK-057 Verification Report

## Result

TASK-057 is Complete. Transcript discovery now explores a bounded deterministic directed graph,
uses the repository's conservative normalized URL identity for cycle and duplicate control, ranks
unique nodes with explicit stable signals, and reports actionable structured and Pull Sources
diagnostics. Candidate retrieval and validation remain owned by the TASK-048 retriever.
The final robustness repair also removes eager candidate validation and cached bodies from
discovery: the engine now receives bounded proposals and invokes validation during retrieval.

The partial-success corrective hardening adds a distinct `success_with_warnings` Pull outcome.
Durably retained transcript artifacts now take precedence over candidate-level failures, while the
complete warning evidence remains in engine diagnostics. A partial mixed-result run advances its
checkpoint from the highest successfully validated retained candidate and anchors that advancement
to a successful attempt. Discovery, transport, ranking, candidate ordering, validation, and
checkpoint qualification rules are unchanged.

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
6. the adapter emits at most the governed number of ranked unique proposals and the engine invokes
   the existing transcript retriever for each selected proposal;
7. structured diagnostics and Pull Sources expose the primary actual outcome.

Exact requested and resolved URLs still flow into provenance. Normalized identity is never used as
a substitute for observed provenance.

## Separation of Responsibilities

- `BudgetedTranscriptTransport` owns page, byte, host, elapsed, and observed redirect accounting.
- `BoundedTranscriptDiscovery` owns graph identity, queued/visited/ancestor state, eligibility,
  deterministic ranking, queue admission, search fallthrough, and bounded graph diagnostics.
- `EarningsCallTranscriptAcquisition` continues to own candidate HTTP retrieval, date, content
  type, transcript structure, speaker evidence, firm identity, and artifact-envelope validation.
- `EarningsTranscriptPullAdapter` converts graph proposals into engine candidates, retains only
  small run-scoped transport accounting, and invokes the retriever from `retrieve()` without
  caching candidate bodies.
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

Traversal behavior is unchanged. URL normalization, retained-anchor and hint precedence, ranking keys,
cycle/duplicate rules, all governed limits, operator messages, and retriever validation rules are
identical. Reproduction evidence remains deterministic, and TASK-056 retained-anchor compatibility
remains green.

## Corrective Robustness Hardening

The architectural review confirmed four defects and one lifecycle weakness after the original
TASK-057 repair.

First, a transcript-like non-HTML graph response attempted to append to an undefined local
candidate collection. Non-HTML responses now remain typed graph proposals; PDF regression
evidence proves one admission, consistent counters, and subsequent validation by
`EarningsCallTranscriptAcquisition`.

Second, two requested aliases could resolve to one normalized transcript URL and later collide as
ambiguous engine candidates. `RankedCandidateProposal` now retains exact observed aliases while
`GraphTraversalState` reconciles graph-observed redirect targets by normalized resolved identity.
The engine receives one canonical candidate for converged aliases, while requested aliases and the
exact resolved URL remain attributable. Query-distinct resolved identities remain distinct.

Third, expected-period evidence from a URL or label could mark coverage before retrieval and
validation. Proposal period evidence is now ranking-only. The retriever marks expected-period
precedence only after date, media, transcript structure, and firm identity validation succeeds.
Focused 404 and invalid-content cases retain a valid historical fallback; a validated expected-
period artifact still suppresses that fallback.

Fourth, broad exception handlers could turn `NameError` and invariant defects into retryable
provider failures. Discovery now catches only policy conversion at its outer boundary, and the
retriever catches explicit transport, parsing, normalization, and validation errors. Injected
unexpected exceptions propagate without a transient-provider classification.

Finally, the adapter previously retrieved and validated every candidate inside `discover()`,
cached exact bodies, and made `retrieve()` a dictionary pop. It also fetched the configured listing
a second time solely to satisfy the interval retriever's listing input. Discovery now emits
bounded proposal metadata for normal listing paths. `retrieve()` makes a proposal-only retriever
invocation and returns exact bytes immediately. There is no body cache, early termination leaves no
cached retrieval result, sequential discovery replaces its small accounting context, and the
configured listing is fetched once. A deferred-candidate marker keeps checkpoint position
advancement tied to a validated date rather than a failed proposal signal.

## Amazon Live-Run Repair

An Amazon production-style run exposed two remaining behavioral defects after the original graph
repair: the extended policy's 30-link per-page limit still acted as an ordinary cutoff, and all
recognizable reporting periods shared one Boolean rank. Historical candidates therefore fell to
lexical URL ordering, consumed the 40-candidate evaluation budget, and could prevent the current
quarter from establishing coverage.

The governed field is now `max_unique_eligible_links_per_page`, with a value of 1000 in every
policy class. It is applied only after URL extraction, normalization, duplicate/cycle rejection,
eligibility, and deterministic ranking. It counts unique eligible admissions from one page and is
reported as an emergency ceiling, distinct from `max_candidate_evaluations`. The loader accepts
the old field name as an explicit migration input, while current configuration, schema,
diagnostics, and operator messages use only the corrected name.

Transcript-specific `ReportingPeriod` ordering now recognizes explicit quarter/year and calendar
date evidence. Within each discovery stage, exact expected period ranks first, then periods newer
than the acquisition checkpoint newest-first, the checkpoint period, older periods newest-first,
and unknown periods. Normalized lexical URL remains the final tie-breaker. The expected period is
the quarter after a recognizable durable acquisition checkpoint or retained successful anchor;
without one, ranking uses the latest completed calendar quarter. Candidate positions use stable
period ordinals so a new quarter advances beyond legacy list-position checkpoints.

The graph still proposes URLs only. The retriever remains the sole owner of date, firm, media,
document, and transcript validation. Once the expected period validates, later historical
proposals are explicitly superseded. If the expected-period proposal fails retrieval or
validation, valid historical fallbacks remain eligible and the expected failure remains
independently observable.

## Graph Queue Priority Repair

A subsequent Amazon run with multiple retained anchors exposed an internal heap invariant that
single-seed fixtures could not reach. Seed entries used `(position, normalized URL)` priorities,
while discovered nodes used the transcript relevance tuple. With the second seed at position one,
Python treated `1` and the discovered-node Boolean as equal and then compared a URL string with a
reporting-period tuple, producing a nonretryable `malformed_adapter` failure.

All heap entries now use one ordered `GraphQueueEntry` and `GraphQueuePriority`. Named integer
enums make retained-anchor, configured-hint, bounded-traversal, seed, and discovered-node
precedence explicit. `LinkRank` flattens period and relevance fields into a homogeneous total order;
normalized URL and insertion sequence provide deterministic final tie-breaking. The existing
semantic ranking reasons and candidate ordering remain unchanged.

The focused regression keeps two retained anchors queued while the first admits a traversable
archive child. Repeated runs fetch both seeds before the child in identical order, preserve graph
metrics and proposal order, and complete through the acquisition engine without a
`malformed_adapter` diagnostic.

Every retriever evaluation now produces exactly one typed disposition. Counts and bounded samples
cover valid current artifacts, checkpoint and historical periods, duplicates, reporting-period
exclusions, firm mismatch, stable retrieval failures, and stable validation failures. A runtime
invariant and focused tests prove the disposition sum equals `candidate_evaluated_count`.

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

Ranking uses inspectable ordinal signals only: stage relationship, ordered reporting period,
configured-hint relationship, same authoritative host, transcript/earnings terms, document-like
path, depth, normalized URL, and label. There are no learned, adaptive, probabilistic, or hidden
weights. TASK-056 retained-anchor history and the durable acquisition checkpoint are the only
repository-state inputs.

## Budgets and Accounting

Existing page, byte, host, depth, query, search-result, and elapsed limits remain.
The existing retriever maximum of 40 candidate evaluations and urllib redirect maximum of 10 are
explicit named policy fields for every discovery class. The per-page unique-eligible-link control
is now a 1000-link pathological-page safety ceiling rather than normal useful-work throttling.

Diagnostics name `max_candidate_evaluations`, `max_redirects`, or another actual policy field only
when that limit is reached. A fixture with two ranked proposals and an evaluation limit of one
selects exactly one candidate; the engine performs its evaluation during retrieval.
Indeterminate-without-exhaustion reports no exhausted budget. The shared transport continues
accounting across graph discovery and retrieval, while removal of the redundant listing request
releases one page and its bytes from every normal configured-hint run.

## Diagnostics and Operator Messages

Discovery diagnostics include adapter/history identity, retained-anchor and configured-hint
attempt order, stage fallthrough, raw/normalized/eligible counts, queue and visited counts,
proposal/selection counts, rejection and cycle counters, bounded redacted representative URLs,
ranking reasons, transport class/status, redirect count/final host, exact exhausted budget, and
final coverage classification. Candidate retrieval and validation classes are emitted from the
engine retrieval phase, where those failures now occur.

Representative URL collections are capped at eight and ranking collections at ten. Query values
are replaced with `REDACTED`; credentials, cookies, tokens, bodies, and unbounded URL logs are never
included. No diagnostic-only network request was added.

Pull Sources now presents messages such as:

- `No eligible transcript links were identified on the configured page.`
- `The configured transcript hint timed out.`
- `The configured transcript hint returned HTTP 403.`
- `Discovery selected 1 ranked transcript candidate for retrieval.`
- `A transcript candidate was found but its content type is unsupported.`
- `Discovery exhausted the candidate-evaluation budget after selecting 1 ranked unique links.`
- `Discovery completed without a candidate, but coverage remains indeterminate.`

## Reproduction Evidence

`make task057-proof` deterministically writes
`.artifacts/task057-validation/reproduction.json`. Its nine cases are:

1. 50 raw links, 50 normalized unique links, zero eligible links, and `no_eligible_links`;
2. configured hint timeout and `hint_fetch_timeout`;
3. configured hint HTTP 403 and `hint_http_failure`;
4. a discovered proposal followed by retrieval-phase `candidate_http_not_found`;
5. a three-node cyclic graph, three visited nodes, and one ancestor-cycle rejection;
6. a relevant transcript after 25 generic transcript-navigation links, ranked first and validated
   during retrieval;
7. genuine `max_candidate_evaluations` exhaustion after one selected proposal;
8. indeterminate coverage with no exhausted budget.
9. an Amazon-style page with 75 historical numeric-path transcripts and a lexically later Q2 2026
   candidate; Q2 2026 is selected first and the per-page emergency ceiling is not reached.

Each record contains its operator summary and bounded structured diagnostics.

## Compatibility and Durable-State Evidence

### Partial-success corrective evidence

The corrective regression reproduces a configured-hint timeout followed by successful downstream
discovery, one validated Q2 2026 transcript retention, and a later candidate timeout. The engine
retains one artifact, preserves both timeout classifications, advances the checkpoint to the
validated Q2 2026 position, and teaches one TASK-056 retained anchor. Pull Workflow reports
`success_with_warnings` with an acquisition-first summary. A companion all-candidates-failed case
retains no artifact, advances no checkpoint, and remains `retrieval_failure`; checkpoint-backed
no-change retains its established summary.

The 102-test focused target includes TASK-048, TASK-048A, TASK-052, TASK-053, TASK-056, Pull
Workflow, and SEC adapter regressions. TASK-056 tests prove anchor LIFO ordering, exact requested/
resolved provenance, atomic history updates, failed-attempt non-learning, profile-revision survival,
checkpoint behavior, and rollback. TASK-048 tests prove validation, immutable bytes, provenance,
and repository ingress remain unchanged. TASK-015/016 tests prove Pull Sources and SEC behavior.

No storage schema, checkpoint qualification, transaction, artifact, observation, immutable-content,
or discovery-history persistence contract changed. Checkpoint finalization now publishes already
qualified retained progress after mixed candidate results instead of withholding that progress.
The browser proof wait condition now waits for
both API responses and rendered checkboxes, removing a validation race without changing production
behavior or durable state.

## Verification Results

- `make task057-test`: PASS, 102 focused and compatibility tests.
- `make task057-proof`: PASS, nine deterministic reproduction cases.
- `git diff --check`: PASS.
- `make validate`: PASS. All 551 unit tests passed, followed by every repository demonstration,
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

The final robustness repair changes `src/rfi/acquisition/earnings_transcripts.py`,
`src/rfi/acquisition/engine.py`, `src/rfi/discovery.py`, TASK-048A/052/053/057 tests,
`scripts/task057_reproduction.py`, and this report.
The Amazon live-run repair additionally changes the governed discovery policy/schema,
`src/rfi/pull/workflow.py`, TASK-015/048A/053 compatibility tests, and the TASK-053 proof script.
The graph-queue priority repair changes only `src/rfi/discovery.py`, `tests/test_task057.py`, and
this report.
The partial-success corrective repair changes `src/rfi/acquisition/engine.py`, the Pull Workflow
contracts, orchestration, and browser presentation, TASK-015/057 and engine regressions, the Pull
Workflow documentation, TASK-057 governance and review records, and the governed design-baseline
checksum for `TASKS.md`.

## Limitations

- Link eligibility remains transcript-specific and deterministic; it does not infer semantics from
  arbitrary navigation text.
- Redirect diagnostics report redirect URLs exposed by the transport boundary; urllib still owns
  its fixed maximum redirect behavior.
- Coverage remains indeterminate unless existing authoritative-listing semantics establish
  completeness.
- Press-release discovery is not implemented by this task.
- Calendar-quarter fallback is an ordering expectation when no recognizable durable checkpoint or
  retained anchor exists; the retriever still validates the artifact's actual date and identity.
- Non-calendar fiscal-period support remains deferred.
- Reporting-period context still reads the existing repository history/checkpoint projections; a
  typed repository query remains deferred.
- Further decomposition of the large graph traversal method remains deferred.
- Redirect-policy exceptions retain their existing partial typing beyond the narrowed outer
  exception boundary.

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
- **Mixed-result finalization — Complete.** Durable acquisitions produce success with warnings,
  warning evidence remains inspectable, and successfully validated progress advances checkpoints
  without allowing failed candidates to qualify progress.
- **Acquisition evidence and SEC verticals — Complete and unaffected.** Checkpoints, transactions,
  immutable bytes, provenance, observations, and SEC adapters pass compatibility validation.
- **Live provider variability — Usable with limitations.** External pages may still require
  JavaScript, deny access, or expose no transcript-eligible links; these now fail diagnostically.
- **Next architectural milestone — Press-release vertical.** The explicit transport/graph/candidate
  boundaries and inspectable bounded-search outcomes provide reusable architectural seams, while
  press-release eligibility and validation remain a separate future vertical.
