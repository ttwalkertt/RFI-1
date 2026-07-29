# TASK-048 Review

## Implementation Summary

TASK-048 implements the first production TASK-047 retriever. It acquires only official textual
earnings-call transcripts from governed issuer or authorized investor-relations hosts. Configured
listing pages are fetched within explicit page/candidate/byte bounds; transcript-looking links and
optional candidate proposals then receive the same deterministic host, date, media, and
artifact-semantic validation. Accepted HTML must contain transcript and earnings-call evidence plus
speaker/section evidence. Accepted PDFs require a PDF signature and an attributable transcript link.

The retriever returns the existing interval contract values, imports no repository, and performs no
persistence. `IntervalAcquisitionService` validates canonical policy and calls
`AcquisitionRepository.record_success`; repository content hashes remain canonical artifact
identities.

## Coverage Semantics

- Empty intervals complete without network access.
- A fully fetched source explicitly governed as an authoritative interval listing may report
  `complete`, including no results, only when every discovered candidate was evaluated.
- Any known listing/candidate failure or candidate-bound truncation reports `incomplete`, preserving
  other successes.
- Useful results from non-authoritative listings or search-located proposals report `indeterminate`.
- Candidate proposals preserve a future escalation seam but cannot bypass validation or ingestion.

## Live Acquisition Evidence

The reproducible command `PYTHONPATH=src .venv/bin/python
scripts/task048_earnings_transcripts.py live-proof` evaluates `[2025-07-01, 2025-08-01)`:

| Official source | Artifact | Media | Proof bytes | Coverage and rationale |
| --- | --- | --- | ---: | --- |
| Microsoft Investor Relations | FY25 Q4, 2025-07-30 | HTML | 326,415 | Indeterminate: genuine official transcript acquired, but the search-located proposal and non-authoritative events listing do not prove full interval coverage. |
| Coca-Cola Investor Relations | Q2 2025, 2025-07-22 | PDF | 305,381 | Indeterminate: genuine issuer-hosted transcript acquired, but the search-located proposal and financial-information listing do not prove full interval coverage. |

The live repository reported two artifacts, two attempts, two observations, and integrity `PASS`.
Exact URLs, hashes, sizes, failures, and rationales are retained in `live/live-acquisition.txt`.

## Verification and Inventory

`tests/test_task048.py` covers empty/no-result intervals; one/multiple transcripts; both boundaries;
HTML/PDF; exclusion of releases, presentations, investor days, unrelated calls, and non-text media;
all coverage states; partial success; reacquisition and content identity reuse; ordinary repository
observations; proposal validation; and absence of direct persistence.

Changed areas are the production retriever and acquisition exports; focused tests and live proof;
review tooling; the completed ticket/status; and acquisition architecture documentation. The review
package retains the complete patch and changed-file inventory plus focused TASK-047/048,
acquisition/repository/schema regression, `git diff --check`, and full `make validate` output.

## Known Limitations

- Public IR HTML varies. This supports bounded anchor discovery and explicit proposals, not
  JavaScript execution, arbitrary crawling, site search APIs, or a generic framework.
- HTML validation is lexical and conservative. PDF validation uses official link evidence and the
  PDF signature; it does not extract compressed PDF text.
- Dates must be explicit in a link label, URL, or document text in a supported calendar form.
  Fiscal-quarter inference is not attempted.
- Authoritative-listing designation is governed configuration. Search success and proposals cannot
  elevate coverage to complete.
- HTTP retries remain invocation-local future work; structured failures and safe interval
  reacquisition preserve successes.

## Architectural Status Summary

| Subsystem | Responsibility | Status |
| --- | --- | --- |
| Date-delimited contract | Request/result/failure/coverage boundary | Complete, reused |
| Transcript discovery | Bounded official listing links and proposal intake | Usable with Limitations |
| Transcript validation | Host, date, type, HTML/PDF and semantic checks | Complete for supported forms |
| Application integration | Canonical policy and ingress dispatch | Complete, reused |
| Immutable repository ingestion | Identity, bytes, attempts, observations, duplicates | Complete, reused |
| Coverage reporting | Evidence-based complete/incomplete/indeterminate | Complete |
| LLM-assisted proposals | Future escalation without bypass | Not Started; seam preserved |
| Other investor artifacts | Releases, decks, events, audio/video | Out of scope / Not Started |

Architectural change: the shared interval contract now has its first production artifact-family
implementation without a second persistence path or generalized acquisition layer. The next
milestone should follow observed production limitations rather than premature shared extraction.
