# TASK-063 Architectural Review — Bounded Transcript Resolution Session

## Result

TASK-063 is complete. Production transcript acquisition no longer launches an independent graph
crawl for every learned seed. It now canonicalizes the learned repository history into one ordered
resolution phase, classifies only the supplied pages, admits direct transcript documents or one-hop
transcript links, and uses at most one configured fallback under the same ephemeral run budget.

No recursive listing traversal or search-engine fallback occurs in the production engine path.
Existing selector, validation, persistence, learning, checkpoint, and replay contracts remain the
authoritative downstream behavior.

## Root Cause and Architectural Boundary

The former production topology treated every learned URL as an independent discovery trial. Each
trial constructed a new graph traversal and fresh page, byte, host, redirect, elapsed-time, and
candidate ceilings. Learned transcript pages for Amazon, IBM, and Western Digital linked into the
same archive graph, so the engine repeatedly fetched and expanded shared pages before TASK-062
could deduplicate the resulting candidates.

TASK-063 replaces that production path with a resolver, not another crawler:

```text
repository learning order
  -> canonical learned-seed phase
       -> classify each supplied page once
       -> direct document, or immediate transcript links only
  -> existing validation and selector
  -> one configured fallback only when the learned phase has no terminal result
```

The pre-existing graph-discovery class remains only as an explicit compatibility seam for legacy
callers that invoke aggregate `discover()` directly. Normal engine trials and injected trials use
`BoundedTranscriptResolver`; removing the old compatibility seam is a separate cleanup.

## Resolution and Classification Contract

`BoundedTranscriptResolver` owns the single production classification definition:

- `transcript_document`: the existing transcript structure validator accepts the response body;
- `transcript_listing`: the HTML contains at least one immediate eligible transcript link;
- `unsupported`: neither document evidence nor an eligible direct link is present; and
- `failed`: transport, HTTP, redirect-cycle, or parsing behavior fails.

Classification uses fetched content and media evidence. A document classification is still only a
candidate proposal: existing firm, event-date, content, selection, persistence, learning, and
checkpoint validation remains mandatory.

Listing pages are parsed once. Eligible immediate links are ranked by the existing reporting-period,
same-host, transcript terminology, document-path, normalized-URL, and label fields. A discovered
listing link is never placed on another traversal queue. Production diagnostics state
`resolution_mode=bounded_one_hop`, `recursive_traversal=false`, `traversed_hyperlinks=0`, and
`search_queries=0`.

## Ordering and Terminal Behavior

The orchestrator reads learned anchors in repository order, considers resolved then requested URL
forms, and applies the existing conservative transcript URL normalizer. The first canonical
occurrence remains authoritative and exact duplicate counts are retained.

Candidate proposal order is:

```text
learned seed FIFO position
  -> existing within-page rank
  -> existing deterministic tie-breakers
  -> configured fallback phase
```

For `latest`, the first validated result remains terminal and prevents fallback execution. Candidate
retrieval failures within the consolidated learned phase continue to the next ordered candidate,
preserving the useful behavior formerly supplied by separate learned trials. Contract, integrity,
and repository conflicts still fail closed.

For `first_in_date_range`, all qualifying distinct candidates continue through the existing terminal
selection policy, which selects the earliest validated content date with the existing deterministic
tie-breakers. No selector policy was moved into the resolver.

## Run-Level Resource Session

`BudgetedTranscriptTransport` is the one run-local owner of:

- page, byte, distinct-host, redirect, and elapsed-time accounting;
- exact response reuse by conservative canonical URL;
- unique admitted candidate identities; and
- the candidate-evaluation ceiling state.

The adapter resets that state at normal-run or injected-run planning, then reuses it across the
learned and configured-fallback phases. A configured fallback cannot receive a fresh allowance.
Canonical requested and redirect-resolved aliases share cached responses, so direct seed
classification followed by existing retrieval does not redownload the document.

Budget exhaustion is explicit. An exhausted phase with no proposal raises the existing typed
adapter-failure path; candidate-cap exhaustion prevents fallback from starting. Neither condition is
reported as successful empty coverage or unchanged replay.

## Invocation Boundaries

- Normal acquisition has one canonical learned phase and at most the first configured HTTP(S)
  discovery hint as fallback.
- A fallback canonically equal to a learned seed is removed during planning.
- Operator injection resolves exactly the supplied normalized seed and adds neither learned seeds
  nor configured fallback.
- Search queries are not submitted by production resolution.
- Future recovery remains an exact temporary seed invocation; TASK-063 adds no LLM behavior.

## Selector, Persistence, and Replay Compatibility

TASK-063 introduces no repository schema, durable session, candidate identity, learning record,
checkpoint record, or persistence branch. TASK-062 `CandidateIdentity` remains the sole stable
candidate equivalence definition, and `DiscoveryOccurrence` remains the occurrence attribution.

Existing TASK-059 tests prove `latest` still persists exactly the first validated candidate and
`first_in_date_range` still selects the global earliest validated date. TASK-060 tests prove
injected/learned equivalence, mutation-free retained replay, monotonic advancement for newer
content, and fail-closed same-position cursor conflict. TASK-061 read-only learning inspection and
TASK-062 duplicate-conflict protections remain green.

## Captured Topology Evidence

The focused suite represents Amazon, IBM, and Western Digital with two learned transcript-document
seeds that both link to their shared archive. Each case:

- fetches both supplied learned documents exactly once;
- validates and persists one `latest` artifact;
- does not fetch the shared archive;
- does not invoke configured fallback; and
- does not issue a search query.

Additional focused cases prove one-hop listing behavior, configured fallback after an unsupported
learned page, response reuse, shared page and candidate ceilings, range selection, and exact
operator-seed isolation.

## Complexity and Robustness Review

- Production has one bounded page-classification implementation.
- One transport object owns all run-level network accounting and response reuse.
- The resolver has no recursive queue, pagination loop, discovered-listing traversal, or search
  submission.
- Learned/configured/operator origin affects planning and occurrence attribution only; it does not
  select a persistence or checkpoint path.
- Candidate conflict protection is unchanged and remains fail closed.
- No second candidate identity, checkpoint model, learning representation, durable resolution
  session, or replay-only persistence branch was introduced.
- Exact counts are retained while URL and classification samples are bounded and redacted.
- Consolidated candidate failure continuation is explicitly trial-controlled; malformed adapter,
  contract, repository conflict, and integrity failures are never continued.

## Validation Results

- `make task063-test`: PASS, 8 focused tests.
- Resolver-specific focused regression: PASS.
- `make task057-test`: PASS, 104 tests.
- `make task058-test`: PASS, 109 tests.
- `make task059-test`: PASS, 121 tests.
- `make task060-test`: PASS, 133 tests.
- `make task061-test`: PASS, 5 tests.
- `make task062-test`: PASS, 5 tests.
- Relevant acquisition, engine, discovery, repository, API, replay, and checkpoint suites: PASS.
- Formatting, lint, type checking, import, documentation, design-baseline, build, and diff checks:
  PASS.
- Full `make validate`: PASS.

The review-package generator reruns and retains the complete output of every listed validation from
the final committed branch head.

## Assumptions and Limitations

- The resolver intentionally does not discover transcript links hidden behind pagination or nested
  listing pages. A configured archive must expose immediate transcript links.
- Production resolves every distinct learned seed page in FIFO order before the engine begins
  candidate validation; it avoids outward crawling, but it does not stop fetching later supplied
  learned seeds merely because an earlier seed is itself a valid document.
- The response cache is ephemeral and source-run scoped. It is never persisted or shared across
  processes.
- The old graph crawler remains temporarily reachable only through the documented aggregate
  discovery compatibility entry point.
- Company evidence is deterministic captured topology, not a live network mutation test.
- No existing Amazon repository state is deleted, rewritten, or reinterpreted.

## Architectural Status Summary

| Subsystem | Responsibility | Status | Limitations / next milestone |
|---|---|---|---|
| Transcript resolution | Classify supplied pages and admit direct documents/links | Complete | No pagination or nested-listing discovery |
| Learned seed orchestration | Canonical FIFO consolidation into one phase | Complete | Every distinct learned seed is probed |
| Configured fallback | One conditional configured archive phase | Complete | Only the first configured HTTP(S) hint participates |
| Run resource control | Shared budget, response cache, and unique-candidate ceiling | Complete | State is intentionally process-local and ephemeral |
| Candidate identity | TASK-062 stable equivalence and global engine deduplication | Complete and unchanged | Future stable metadata requires allowlist review |
| Selector and persistence | Existing latest/range, validation, learning, checkpoint, replay | Complete and unchanged | Historical repair and backfill remain out of scope |
| Legacy graph discovery | Compatibility for direct aggregate callers | Usable with limitations | Remove after the remaining callers migrate |

The next architectural milestone should either remove the legacy aggregate crawler after caller
migration or introduce an explicit provider adapter for sites whose archives require pagination;
it should not expand this resolver into a general crawler.
