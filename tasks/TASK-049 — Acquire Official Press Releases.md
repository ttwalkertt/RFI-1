TASK-049 — Acquire Official Press Releases

Status

Ready

Objective

Implement the second production retriever using the TASK-047 date-delimited acquisition contract.

The retriever shall acquire official textual press releases for a canonical firm within a requested closed-open date interval and record the results through the existing acquisition and repository path.

Scope

Implement:

* bounded discovery of public press releases;
* retrieval of qualifying HTML or PDF press-release artifacts;
* date-interval enforcement;
* structured failures;
* truthful complete, incomplete, or indeterminate coverage;
* application integration through the TASK-047 contract;
* representative live proof and complete review evidence.

Press Release Definition

A qualifying press release is an official, publisher-authored public announcement issued by or on behalf of a firm to communicate a discrete corporate event or development.

Qualifying examples include:

* earnings releases and quarterly or annual financial-results announcements;
* dividend declarations and share-repurchase announcements;
* acquisitions, divestitures, debt offerings, and equity offerings;
* executive appointments, departures, and board changes;
* product, customer, partnership, facility, and manufacturing announcements;
* regulatory approvals, litigation announcements, and sustainability or ESG announcements.

The retained artifact shall be the complete released document in HTML or PDF form, not an archive page, search result, summary, or navigational page.

A qualifying artifact shall be published by the issuer or by an explicitly governed authorized distribution channel with attributable issuer provenance.

Required Boundaries

The implementation shall:

* use the existing CandidateDocument, RetrievalResult, interval contract, and AcquisitionRepository.record_success;
* leave canonical identity, immutable bytes, duplicate handling, attempts, observations, and persistence to the repository;
* preserve successful artifacts when other candidates fail;
* support safe reacquisition of the same interval;
* retain auditable discovery and selection evidence;
* report coverage conservatively;
* deterministically validate issuer attribution, host authorization, publication date, media type, and press-release semantics before ingestion.

The retriever shall not write directly to repository storage or create a second ingestion path.

Coverage

complete requires affirmative evidence that an authoritative source was evaluated across the requested interval. An interval with no qualifying press releases may still be complete.

incomplete applies when a known artifact or source segment could not be retrieved or evaluated.

indeterminate applies when useful artifacts were found but the retriever cannot establish that discovery covered the full interval.

Finding plausible documents through search, RSS, or candidate proposals alone shall not establish complete coverage.

Out of Scope

Do not implement:

* earnings-call transcripts;
* investor presentations or slide decks;
* investor days, conference appearances, or fireside chats;
* webcast pages, audio, video, or transcription;
* SEC filings, annual reports, or proxy statements;
* fact sheets, media kits, blog posts, marketing landing pages, or careers announcements;
* RSS feeds, archive pages, index pages, or search-result pages as retained artifacts;
* generalized news crawling;
* recurring scheduling or background workers;
* operator UI;
* downstream summarization or analysis;
* a generic acquisition framework;
* an LLM dependency.

The design shall not preclude a later LLM-assisted escalation path that proposes candidates without bypassing deterministic validation or repository ingestion.

Verification

Add focused tests covering:

* empty and no-result intervals;
* one and multiple press releases;
* closed-open date boundaries;
* HTML and supported PDF retrieval;
* earnings releases as qualifying press releases;
* exclusion of transcripts, presentations, filings, reports, blog posts, archive pages, and unrelated news;
* issuer and authorized-distributor provenance validation;
* complete, incomplete, and indeterminate outcomes;
* partial success with retained valid artifacts;
* repeated acquisition without duplicate canonical content;
* reuse of existing repository identity and persistence behavior;
* absence of direct persistence by the retriever;
* search-located or proposed candidates remaining unable to establish complete coverage.

Provide bounded live proof against at least two materially different issuer or authorized-distribution sites. The proof shall include at least one earnings release and at least one non-earnings corporate announcement.

Run focused tests, TASK-047 and TASK-048 regressions, acquisition and repository regressions, schema tests, and full make validate.

Review Package

Provide a self-contained TASK-049 review package containing:

* completed ticket;
* implementation summary;
* changed-file inventory and patch;
* focused, regression, and full validation output;
* live acquisition evidence;
* coverage rationale for each live proof;
* repository status, branch, and commit;
* manifest and integrity hash;
* known limitations.

Review Criteria

Reject implementations that:

* create another ingestion path;
* assign canonical identities in the retriever;
* treat search, RSS, or candidate success as proof of complete coverage;
* discard successful artifacts because another candidate failed;
* classify transcripts, presentations, filings, reports, blog posts, archive pages, or navigational pages as press releases;
* retain only a summary when the complete release is available;
* accept unattributed third-party news as issuer press releases;
* fabricate unavailable content;
* introduce speculative shared acquisition infrastructure.

Accept implementations that satisfy the TASK-047 contract, retrieve genuine complete official press releases, report coverage truthfully, preserve repository governance, and remain narrowly scoped.