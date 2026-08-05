# TASK-064 — Dedicated StockAnalysis Transcript Provider Adapter

## Status

Complete

---

## Summary

Create a dedicated, provider-specific transcript adapter for StockAnalysis.

The firm configuration shall explicitly select the provider and provide a typed discovery hint:

```xml
<earnings_transcript>
  <provider>stockanalysis</provider>
  <discovery_hint>
    <kind>provider_identifier</kind>
    <value>ORCL</value>
  </discovery_hint>
</earnings_transcript>
```

For StockAnalysis, the configured `provider_identifier` is the firm identifier used by that provider, presently the stock ticker. The StockAnalysis adapter owns construction of the canonical archive URL:

```text
https://stockanalysis.com/stocks/{ticker}/transcripts/
```

The transcript orchestrator shall dispatch configured and learned seeds to providers without understanding provider-specific URL layouts, markup, retries, extraction rules, or recovery behavior.

The StockAnalysis adapter shall provide a substantial vertical slice:

1. resolve a configured provider identifier or accepted learned seed;
2. discover transcript documents from the firm-specific StockAnalysis archive;
3. retrieve direct transcript documents;
4. deterministically extract the complete transcript and trusted provider-explicit metadata;
5. optionally emit ordered speaker-turn observations and typed related-artifact observations;
6. return bounded diagnostics and optional learning feedback; and
7. preserve all existing repository ownership for validation, seed selection, escalation, learning updates, persistence, replay, checkpointing, and terminal behavior.

The retained transcript artifact remains authoritative. Speaker turns and related-artifact relationships are provider observations used by repository-owned persistence or projection paths.

Reference material:

- representative archive: `https://stockanalysis.com/stocks/orcl/transcripts/`
- representative transcript: `https://stockanalysis.com/stocks/orcl/transcripts/592465-q4-2026/`

### Bounded post-completion corrective repair

The StockAnalysis archive also contains conference, investor-day, and other event transcripts.
The provider therefore emits one provider-neutral `TranscriptMetadataObservation` containing an
opaque event label, optional trusted artifact-local date, event disposition, related-artifact
observations, and parsed speaker-turn observations. `event_disposition` is exactly one of
`explicit_earnings`, `explicit_non_earnings`, or `unknown`.

Disposition is populated only from fixture-covered provider-explicit candidate or artifact
metadata. A directly associated earnings release, quarterly report, or annual report establishes
`explicit_earnings`; only a dedicated StockAnalysis event classification establishes
`explicit_non_earnings`; all incomplete or questionable evidence remains `unknown`. The mere
presence or absence of a relationship container is not evidence. Titles, headings, URLs, slugs,
fiscal-period text, archive position, and global link labels are never classification inputs.

Earnings acquisition ranks `explicit_earnings` before `unknown`, preserves archive order inside
each class, and excludes only `explicit_non_earnings`. The transcript-substance gate is separate
from event disposition and uses only already-parsed transcript structure: minimum turn count,
content-bearing turn count, normalized-text word count, and distinct opaque speaker-label count.
Questionable events remain eligible when they expose substantial transcript structure.

Candidate-evaluation accounting begins only immediately before a unique document is retrieved
and evaluated. Entries excluded during metadata admission consume no evaluation capacity.
Duplicate discovery occurrences retain trial-local provenance and do not become ambiguous
candidate identities.

---

## Objective

Establish StockAnalysis transcript acquisition behind one explicit provider boundary while preserving the provider-neutral transcript orchestration model.

The adapter shall:

- accept the existing immutable transcript target, selection, source-profile, seed, policy, and run-budget inputs;
- support the configured `provider_identifier` seed kind and provider-associated URL seeds;
- perform provider-local retries and bounded recovery for one dispatched seed;
- discover and retrieve only the bounded StockAnalysis transcript surface;
- extract provider-explicit metadata, complete transcript content, optional speaker-turn observations, related-artifact observations, and learning feedback;
- return existing repository-owned discovery and retrieval outputs, bounded diagnostics, provenance, and failure classifications; and
- leave provider dispatch, seed ordering, escalation, learning updates, validation, persistence, replay, checkpointing, and terminal selection with the existing owners.

The architectural milestone is the provider boundary and the complete StockAnalysis vertical slice, not introduction of a generic crawler framework.

---

## Configuration Contract

### Required provider selection

An earnings-transcript source configuration that uses this adapter shall explicitly declare:

```xml
<provider>stockanalysis</provider>
```

Provider selection shall not be inferred from:

- URL shape;
- firm name;
- ticker text outside the typed hint;
- page title;
- learned URL host;
- source ordering; or
- provider-specific string inspection in the orchestrator.

### Required typed discovery hint

The configured StockAnalysis hint shall be:

```xml
<discovery_hint>
  <kind>provider_identifier</kind>
  <value>{ticker}</value>
</discovery_hint>
```

The value shall be one non-empty provider identifier accepted by the StockAnalysis adapter. The adapter shall conservatively normalize the identifier for StockAnalysis URL construction while preserving the exact configured value for provenance.

The StockAnalysis adapter may also accept a provider-associated URL seed for:

```text
https://stockanalysis.com/stocks/{ticker}/transcripts/
https://stockanalysis.com/stocks/{ticker}/transcripts/{transcript-document}/
```

A direct transcript URL seed shall be resolved directly and shall not require an archive fetch first.

### Retained generic transcript discovery

An earnings-transcript source without `provider` remains a provider-neutral generic discovery
configuration. It shall supply one or more string URL `discovery_hints`; those hints remain generic
seeds and shall not be coerced into typed provider hints or dispatched to the StockAnalysis
adapter. This branch supports StockAnalysis quote namespaces, including `/quote/tyo/...`, that are
outside the strict adapter's `/stocks/{ticker}/transcripts/` boundary.

The generic and provider-backed forms are mutually exclusive. A provider-backed configuration
shall not fall through to generic discovery, and generic configuration shall not infer a provider
from URL shape.

### Schema and validation

The task may extend firm configuration to represent:

- `provider`;
- `discovery_hint.kind`; and
- `discovery_hint.value`.

Configuration loading shall fail closed when:

- any provider-backed field is supplied but provider is missing;
- hint kind is missing;
- hint value is empty;
- the provider name is unknown;
- the provider does not support the declared kind; or
- provider-specific validation rejects the value.

No hint kind shall be inferred.

`discovery_class` continues to select repository-owned resource policy. It does not select the provider.

---

## Seed and Dispatch Contract

Use one provider-neutral seed contract containing at least:

```text
provider
kind
value
origin
```

Supported origins include configured, learned, and operator-injected seeds.

For this milestone:

- configured StockAnalysis seeds use `kind = provider_identifier`;
- learned or operator-injected StockAnalysis locators may use `kind = url`;
- the provider association is explicit on learned seeds;
- the orchestrator shall not reclassify learned seeds by inspecting the URL;
- the StockAnalysis adapter shall still validate every URL defensively before use.

Mixed-provider learned FIFOs shall preserve their existing order. The orchestrator dispatches each seed to its recorded provider and retains all current terminal-selection behavior.

A successful learned StockAnalysis trial shall prevent later seeds or configured fallbacks exactly when the existing orchestration contract would already stop.

---

## Ownership Boundary

### Orchestrator owns

- reading configured and learned seeds;
- FIFO ordering;
- provider dispatch;
- seed selection;
- escalation between seeds;
- configured fallback selection;
- run-level budgets and terminal behavior;
- durable validation and selection;
- learning eligibility and updates;
- persistence transactions;
- replay and checkpoint semantics;
- duplicate and conflict handling; and
- operator-visible final outcomes.

### Provider adapter owns

Within one dispatched seed attempt:

- supported seed-kind validation;
- provider identifier resolution;
- StockAnalysis archive URL construction;
- archive and direct-document retrieval;
- provider-local redirects, retries, backoff, and bounded recovery;
- provider-specific content-type and status handling;
- provider-specific parsing and markup assumptions;
- archive candidate extraction;
- transcript content extraction;
- provider-explicit metadata extraction;
- optional speaker-turn extraction;
- related-artifact discovery;
- provider-local canonicalization and deduplication;
- bounded provider diagnostics;
- failure classification; and
- optional learning feedback.

The adapter shall not:

- choose another seed;
- reorder the FIFO;
- dispatch another provider;
- reset the run-level budget;
- write durable learning state;
- persist artifacts directly;
- update checkpoints;
- change terminal-selection behavior; or
- silently broaden into generic search.

---

## Provider Module Boundary

Create a dedicated StockAnalysis module beneath the transcript acquisition/discovery provider layer.

All StockAnalysis-specific concerns shall remain private to the module, including:

- provider identifier normalization;
- archive and transcript URL construction and validation;
- HTTP client behavior;
- selectors and DOM assumptions;
- structured-page-data handling;
- archive parsing;
- transcript parsing;
- provider-specific retries and recovery;
- provider-specific metadata extraction;
- speaker-turn extraction;
- related-artifact link extraction;
- provider-local request ordering and deduplication; and
- provider-specific diagnostics and failure mapping.

No StockAnalysis selector, DOM node, provider-specific DTO, HTTP-client context, or internal parser object may escape the module.

The public provider contract shall use repository-owned, provider-neutral inputs and outputs.

Use the simplest deterministic HTTP implementation that reliably handles captured and live StockAnalysis evidence. Do not add Crawlee, Playwright, browser state, or a generic crawling framework unless implementation evidence demonstrates that static deterministic retrieval is insufficient. If such evidence appears, stop and document the gap before adding the dependency.

---

## Archive Discovery Contract

For a configured `provider_identifier`, the adapter shall construct:

```text
https://stockanalysis.com/stocks/{normalized-provider-identifier}/transcripts/
```

The archive is a listing surface, not a general crawl graph.

The adapter shall:

- fetch the firm-specific archive;
- extract only transcript-document entries for that firm;
- retain exact observed URLs and normalized candidate identities;
- preserve visible archive labels and deterministic archive position;
- preserve exact parent archive provenance;
- exclude unrelated tickers and all site-wide navigation; and
- return candidates in deterministic order for identical captured input.

The adapter shall not enqueue or traverse:

- stock overview pages;
- prices or forecasts;
- financial statements;
- filings indexes;
- annual or quarterly reports as transcript candidates;
- earnings releases as transcript candidates;
- slides as transcript candidates;
- audio as transcript candidates;
- advertisements;
- account pages;
- unrelated firms;
- site navigation;
- search engines;
- sitemaps; or
- another host.

Related artifacts explicitly associated with a transcript page may be returned as typed observations for orchestrator-controlled retrieval, but they are not transcript candidates.

---

## Direct-Document Contract

A provider-associated StockAnalysis transcript URL may be supplied as a learned or operator-injected seed.

The adapter shall:

- validate that the URL belongs to the recognized StockAnalysis transcript namespace;
- preserve the exact requested URL;
- fetch the document directly;
- preserve the exact resolved URL;
- avoid an archive fetch unless required by an explicit existing contract;
- apply the same extraction, validation-output, provenance, budget, and diagnostic rules used for archive-discovered documents; and
- converge on the same candidate identity and retrieval contracts as archive discovery.

---

## Trusted Metadata Contract

Extract metadata only when it is explicitly present in the transcript artifact in an established, fixture-covered form.

At minimum, StockAnalysis may explicitly provide:

- document title;
- company label;
- ticker label;
- event type label;
- fiscal-period label;
- event date;
- complete transcript content;
- speaker labels;
- role or affiliation labels;
- section labels when structurally explicit;
- related annual-report link;
- related slides link;
- related earnings-release link;
- audio availability;
- transcript-download availability; and
- provider-summary availability.

### Date authority

The event date shall be accepted only from the transcript artifact itself in a known, tested format.

If the artifact date is:

- missing;
- malformed;
- ambiguous;
- conflicting; or
- presented in an unrecognized format,

the adapter shall ignore it and leave the date unset for existing validation to handle.

The adapter shall not infer event date from:

- transcript URL;
- URL slug;
- archive order;
- archive date;
- fiscal quarter/year;
- publication timestamp;
- adjacent filing dates; or
- related-artifact dates.

### Fiscal-period authority

A visible fiscal-period label may be retained as provider metadata when extracted from the artifact in a known format. URL slugs may support route recognition and identity only; they shall not override artifact content.

### Provider summary

Provider summary text shall not be included in transcript content. The adapter may record that a provider summary exists, but retaining or using the summary text is outside this task.

### Conflicts

Conflicting company, ticker, document type, fiscal period, or other trusted metadata shall fail closed through existing validation semantics and appear in bounded diagnostics.

---

## Transcript Content Contract

The adapter shall extract the complete available transcript content and exclude surrounding page content.

Exclude at minimum:

- site navigation;
- stock data;
- page summary;
- audio controls;
- download controls;
- related filings;
- related transcripts;
- advertisements;
- subscription prompts; and
- footer content.

Do not summarize, rewrite, model-classify, or semantically repair transcript text.

Normalize only representation details required by the existing artifact contract.

The retained artifact remains authoritative.

---

## Speaker-Turn Observation Contract

Define a provider-neutral optional observation shape equivalent to:

```python
@dataclass(frozen=True)
class TranscriptTurnObservation:
    ordinal: int
    speaker_label: str
    role_label: str | None
    section_label: str | None
    paragraphs: tuple[str, ...]
```

The exact repository type may differ, but the semantics are authoritative:

- turns are ordered exactly as observed;
- speaker labels are provider labels, not canonical person identities;
- role labels are preserved as provider text;
- section labels are populated only when structurally explicit;
- paragraph order is preserved;
- consecutive turns by the same speaker are not merged;
- missing speaker structure is represented as unavailable, not guessed;
- extraction failure does not invalidate an otherwise valid transcript artifact unless an existing validation contract independently requires the structure; and
- no generic speaker-segmentation fallback is introduced.

StockAnalysis shall populate speaker-turn observations when the provider page deterministically exposes them.

Other providers may omit them or derive them by different provider-specific methods.

---

## Related-Artifact Observation Contract

The StockAnalysis adapter may return typed related-artifact observations explicitly linked by the transcript page, such as:

- annual report;
- presentation slides;
- earnings release; and
- audio.

A provider-neutral observation shall contain at least:

```text
artifact kind
exact observed URL
relationship kind
source artifact or page provenance
```

The adapter shall not assign a shared `event_group_id`.

Each retained artifact keeps its own existing primary key.

The orchestrator decides:

- whether a related artifact is eligible for retrieval;
- which provider handles it;
- when it is fetched;
- how it is persisted; and
- whether an artifact-to-artifact relationship is created.

The adapter only reports the explicit provider relationship.

---

## Learning Feedback Contract

Provider adapters may return bounded, optional learning feedback.

The adapter shall never write durable learning state.

The StockAnalysis adapter may report, for example:

- the resolved canonical firm archive URL;
- a confirmed provider identifier;
- a reusable direct document URL;
- a redirect alias; or
- a locator that should not be reused.

StockAnalysis does not depend on learned URLs because the configured provider identifier deterministically reconstructs the archive.

The orchestrator remains the sole owner of:

- learning eligibility;
- validation prerequisites;
- deduplication;
- FIFO ordering;
- persistence;
- replay;
- checkpoint interaction; and
- whether feedback becomes durable learned state.

Learned StockAnalysis seeds are secondary to the configured StockAnalysis discovery hint and are considered only after the configured attempt fails or remains incomplete, subject to existing orchestration and budget rules.
---

## Retry, Recovery, and Failure Contract

The adapter owns local retries and provider-local recovery for one seed attempt.

Local recovery may include:

- retrying transient network failures;
- bounded backoff;
- provider-specific retryable status handling;
- redirect resolution;
- alternate deterministic selectors;
- known structured-data fallback;
- known transcript-representation fallback; and
- bounded recovery from fixture-covered markup variation.

The adapter shall not:

- choose another seed;
- submit a search query;
- switch providers;
- broaden to unrelated pages;
- synthesize missing metadata;
- infer dates;
- model-repair content; or
- report incomplete coverage as complete-empty.

Return one terminal attempt result to the orchestrator with explicit:

- success or failure;
- retryability;
- coverage;
- budget state;
- provider diagnostics;
- provenance;
- optional learning feedback; and
- optional related-artifact and speaker-turn observations.

A reachable recognized page whose expected transcript structure cannot be extracted shall produce an actionable provider-layout or parse failure, not a false success.

---

## Budget and Determinism Contract

All provider activity consumes the existing TASK-063 run-level budget.

The adapter shall not reset budgets between:

- archive and document phases;
- redirects;
- retries;
- parsing fallbacks;
- related-artifact observation extraction; or
- direct and archive handling.

Enforce and report existing applicable bounds, including:

- pages or requests;
- bytes;
- elapsed time;
- redirects;
- retries;
- candidate evaluations; and
- diagnostic size.

For identical captured inputs:

- candidate ordering shall be stable;
- direct and archive paths shall converge on the same candidate identity;
- speaker-turn ordering shall be stable;
- related-artifact observations shall be stable; and
- repeated replay shall emit identical normalized results.

Request completion order shall not change emitted candidate order.

---

## Existing Contract Compatibility

Reuse the existing transcript acquisition contracts wherever they faithfully represent the required observations.

Preserve unchanged:

- `SourceProfile` semantics except for the explicit provider and typed hint projection required by this task;
- `TranscriptAcquisitionTarget`;
- `TranscriptAcquisitionSelection`;
- `AdapterAcquisitionTrial` invocation semantics;
- `DiscoveryPage`;
- `AdapterCandidate`;
- `DiscoveryProvenance`;
- `RetrievalResult`;
- `CandidateIdentity`;
- `DiscoveryOccurrence`;
- `latest`;
- `first_in_date_range`;
- TASK-063 run-level budget behavior;
- exact requested and resolved URL provenance;
- failure class, retryability, coverage, and operator-visible outcome semantics;
- immutable artifact bytes;
- repository conflict behavior;
- persistence ownership;
- checkpointing;
- replay; and
- learning ownership.

The provider-neutral speaker-turn, related-artifact, and learning-feedback contracts may be added only if current contracts cannot faithfully carry those observations.

Do not add a StockAnalysis-only side channel.

If the current repository model cannot represent a required observation without a provider-specific leak or an unbounded schema change, stop and document the gap.

---

## Required Invariants

1. Configured provider selection is explicit.
2. Discovery-hint kind is explicit and never inferred.
3. StockAnalysis configured discovery uses `provider_identifier`.
4. Learned seeds retain explicit provider association.
5. The orchestrator dispatches; it does not understand StockAnalysis URL structure or markup.
6. The provider adapter owns local retries and bounded provider recovery.
7. The orchestrator owns seed selection, escalation, fallback, and terminal behavior.
8. The adapter may emit learning feedback but cannot write learning.
9. The orchestrator owns durable learning updates.
10. The complete retained artifact remains authoritative.
11. Speaker turns are optional provider observations, not canonical speaker identities.
12. Related artifacts retain independent artifact identities.
13. No `event_group_id` is introduced by this task.
14. The adapter reports related-artifact relationships; the orchestrator decides retrieval.
15. Event date is accepted only from a known artifact-local representation.
16. Event date is never inferred from URL, slug, archive position, fiscal period, or adjacent documents.
17. Provider summary text is excluded from transcript content.
18. A candidate is evaluated at most once per run.
19. The run-level budget cannot reset inside the provider.
20. Candidate and speaker-turn order are reproducible.
21. No search-engine request occurs on the StockAnalysis path.
22. Failures and incomplete coverage remain explicit and bounded.
23. Mixed-provider learned FIFOs retain their existing order.
24. Existing validation, persistence, learning, replay, checkpoint, duplicate, and conflict semantics remain authoritative.
25. Non-StockAnalysis transcript behavior remains unchanged unless required by the provider-neutral contract extension.

---

## Explicitly Out of Scope

Do not implement:

- a generic crawler framework;
- Crawlee or Playwright without documented necessity;
- migration of all transcript providers;
- a generic speaker-segmentation heuristic;
- canonical speaker/person identity;
- cross-transcript person resolution;
- inferred section boundaries;
- an `event_group_id`;
- event-entity normalization;
- unrestricted site crawling;
- search-engine fallback;
- LLM extraction, classification, ranking, or recovery;
- provider-summary ingestion;
- transcript summarization;
- canonical knowledge construction;
- intelligence generation;
- new selection modes;
- backfill orchestration;
- continuation cursors;
- checkpoint redesign;
- retained-anchor redesign;
- artifact-repository redesign beyond the bounded neutral observation contracts;
- operator UI changes; or
- unrelated code removal.

The existing generic deterministic transcript implementation may remain for other providers.

---

## Required Tests

Add focused tests proving:

### Configuration and dispatch

1. Explicit `provider=stockanalysis` with `kind=provider_identifier` selects the StockAnalysis adapter.
2. Missing provider, kind, or value fails closed.
3. Unknown providers and unsupported hint kinds fail closed.
4. The orchestrator does not infer providers from URLs.
5. A learned StockAnalysis seed retains its explicit provider association.
6. Mixed-provider learned FIFO order is preserved.
7. A successful learned trial preserves existing terminal behavior.
8. Non-StockAnalysis providers retain existing behavior.

### Provider identifiers and URLs

9. `ORCL` deterministically resolves the canonical StockAnalysis archive.
10. Provider identifier normalization is conservative and tested.
11. Direct StockAnalysis transcript URLs resolve without an archive fetch.
12. Archive and direct-document paths converge on the same candidate identity.
13. Malformed, deceptive-host, unrelated-ticker, unrelated-path, and cross-host URLs fail closed.
14. Requested and resolved URLs remain exact provenance.
15. Redirect aliases do not evaluate a candidate twice.

### Archive discovery

16. The Oracle archive fixture admits the representative Q4 2026 transcript.
17. Archive extraction excludes releases, slides, reports, audio, navigation, and unrelated firms as transcript candidates.
18. Candidate order is deterministic.
19. Request completion order cannot alter emitted candidate order.
20. Archive parse failure and incomplete coverage are explicit.

### Transcript extraction

21. The Oracle transcript fixture yields the complete transcript and excludes summary, controls, related links, and footer content.
22. Document title, company, ticker, event type, fiscal period, and artifact-local event date are extracted from known provider representations.
23. URL slug and archive metadata cannot establish event date.
24. Missing or unrecognized artifact date remains unset.
25. Conflicting trusted metadata fails closed.
26. Provider summary text is excluded.

### Speaker turns

27. Ordered speaker-turn observations preserve ordinals, labels, optional roles, optional explicit sections, and paragraphs.
28. Consecutive turns by the same speaker are not merged.
29. Speaker labels do not create canonical person identities.
30. Missing or changed speaker structure yields absent observations or an explicit provider parse diagnostic without corrupting artifact content.
31. Repeated fixture replay emits identical turns.

### Related artifacts

32. Explicit related annual-report, slides, earnings-release, and audio links are returned as typed observations when present.
33. Related links are not automatically fetched by the adapter.
34. Each fetched related artifact retains its own artifact primary key.
35. No `event_group_id` is introduced.
36. Relationship observations retain exact source provenance.

### Retry, learning, and ownership

37. Provider-local transient retries stay within one seed attempt and consume the shared run budget.
38. The adapter never selects another seed or provider.
39. The orchestrator controls escalation after the adapter returns.
40. The adapter may return bounded learning feedback.
41. The adapter cannot write durable learning state.
42. The orchestrator remains the only learning writer.
43. The configured provider identifier remains sufficient when no learned URL exists.

### Regression and failure containment

44. Page, byte, elapsed, redirect, retry, candidate, and diagnostic bounds are enforced and named.
45. No search implementation is called.
46. Diagnostics exclude transcript bodies and sensitive request data.
47. Learning, checkpoints, persistence, replay, duplicate, and conflict behavior remain unchanged.
48. TASK-059 through TASK-063 transcript regressions remain green.
49. Static HTTP dependency/runtime failure produces an actionable adapter failure.
50. No Crawlee, Playwright, browser storage, or repository-local crawler state is introduced without approved evidence.

Use sanitized captured fixtures for the representative StockAnalysis archive and transcript. Network-only tests do not satisfy acceptance criteria.

---

## Live Acceptance Evidence

After fixture-based validation, perform bounded live acquisition using:

```xml
<earnings_transcript>
  <provider>stockanalysis</provider>
  <discovery_hint>
    <kind>provider_identifier</kind>
    <value>ORCL</value>
  </discovery_hint>
</earnings_transcript>
```

Demonstrate that the provider constructs the Oracle archive URL and discovers or directly resolves the representative Q4 2026 transcript.

Record:

- configured provider;
- configured hint kind and exact value;
- effective provider adapter;
- effective discovery policy and bounds;
- constructed archive URL;
- requested and resolved document URLs;
- candidate ordering and selection attribution;
- artifact-local metadata;
- speaker-turn count and content digest without transcript text in diagnostics;
- related-artifact observation kinds and URLs;
- learning feedback, if any;
- validated acquisition outcome;
- search-engine call count of zero; and
- limitations caused by live-site changes, access controls, or robots policy.

A live layout or access change is not permission to weaken validation, infer dates, fabricate complete coverage, or introduce generic search.

---

## Validation

Run:

- focused TASK-064 configuration, dispatch, provider, extraction, speaker-turn, related-artifact, learning-feedback, budget, and failure tests;
- relevant transcript contract, engine, API, repository, replay, checkpoint, and learning tests;
- TASK-059, TASK-060, TASK-061, TASK-062, and TASK-063 regressions;
- static HTTP dependency/runtime verification;
- fixture-based deterministic replay at least twice with identical ordered outputs;
- the bounded live acceptance described above; and
- full `make validate`.

Perform a deliberate architecture review confirming:

- provider dispatch has one definition;
- provider selection is explicit;
- hint kinds are never inferred;
- the orchestrator contains no StockAnalysis URL or markup knowledge;
- StockAnalysis-specific parsing exists only inside the provider module and its tests;
- provider-local retries cannot select seeds or reset budgets;
- learning updates remain orchestrator-owned;
- durable validation, selection, persistence, replay, and checkpoint ownership did not move;
- no `event_group_id` was introduced;
- related artifacts retain independent artifact identities;
- no generic speaker segmentation was introduced;
- no search request can occur on the StockAnalysis path;
- no Crawlee or browser dependency was added without approved evidence; and
- non-StockAnalysis transcript behavior remains unchanged.

---

## Repository Requirements

Work on:

```text
codex/task-064-stockanalysis-transcript-provider-adapter
```

Commit and push completed work. Do not merge and do not open a pull request.

If corrective work occurs after package generation, delete the existing TASK-064 package and architectural review report before beginning the correction. Generate a new package only from the final validated branch head.

---

## Review Package

Generate a complete verified TASK-064 review package containing:

- the required Architectural Status Summary;
- firm-configuration schema and validation proof;
- explicit provider-dispatch contract;
- supported seed-kind matrix;
- learned FIFO provider-association and ordering proof;
- provider/orchestrator responsibility map;
- existing input/output contract compatibility proof;
- deterministic HTTP client and dependency rationale;
- provider-identifier resolution proof;
- archive and direct-document acquisition contract;
- trusted metadata and date-authority contract;
- speaker-turn observation contract;
- related-artifact observation contract;
- learning-feedback contract and orchestrator-only write proof;
- sanitized Oracle fixtures and capture manifest;
- deterministic ordering and repeated-replay evidence;
- resource-budget evidence;
- no-search proof;
- `latest` and `first_in_date_range` compatibility evidence;
- persistence, learning, checkpoint, replay, identity, provenance, duplicate, and conflict compatibility evidence;
- non-StockAnalysis regression evidence;
- bounded live acceptance evidence;
- focused and full validation results;
- complexity and robustness review;
- assumptions, limitations, and technical debt; and
- package manifest with SHA-256 verification.
