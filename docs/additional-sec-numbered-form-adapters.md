# Additional SEC numbered-form retrieval adapters

TASK-022 extends the deterministic SEC vertical slice to canonical Form 10-Q, Form 8-K, Form
20-F, and Form 6-K artifacts. Ordinary validation is fixture-backed and offline. Live proof is
explicitly gated and bounded.

## Responsibility and reuse analysis

| Classification | Responsibilities | Resolution |
| --- | --- | --- |
| Generic retrieval-adapter infrastructure | Capability declaration, ambiguity rejection, planning, execution, outcome aggregation | Reused unchanged from TASK-016. |
| Shared SEC provider mechanics | CIK normalization, submissions decoding, bounded HTTPS, retries, pacing, archive retrieval, content validation | Reused; issuer/accession association was corrected from live evidence. |
| Reusable numbered-form mechanics | Exact-form filtering, duplicate-accession conflict detection, deterministic ordering, primary candidate/retrieval projection, provenance | Extracted to `SecNumberedFormAdapter` because every numbered form uses the identical algorithm and typed SEC records. |
| Form 10-K policy | `sec_10k`, exact `10-K`, amendment exclusion, annual multiplicity and failures | Remains explicit in `SecForm10KAdapter`; all TASK-016 regression tests pass. |
| Acquisition/repository behavior | Attempts, checkpoints, documents, observations, immutable bytes, SQLite transactions, queries, browser, integrity | Remains outside adapters and is reached only through existing public contracts. |

The extraction does not accept form strings or canonical artifact configuration at runtime. Each
production class declares one adapter identity, one canonical artifact, one eligible SEC form,
one amendment policy, one multiplicity description, and one form-specific no-match result. A
universal SEC filing adapter and arbitrary form-code configuration engine remain rejected.

## Filing policies

| Artifact | Exact eligible form | Amendments | Current multiplicity | Source-effective fields |
| --- | --- | --- | --- | --- |
| `sec_10q` | `10-Q` | `10-Q/A` excluded | Latest visible quarterly report | filing date, acceptance time, accession; period retained for display |
| `sec_8k` | `8-K` | `8-K/A` excluded | Latest visible item in a high-frequency current-report stream | filing date, acceptance time, accession; event/report date retained when supplied |
| `sec_20f` | `20-F` | `20-F/A` excluded | Latest visible foreign-private-issuer annual report | filing date, acceptance time, accession; annual period retained |
| `sec_6k` | `6-K` | `6-K/A` excluded | Latest visible item in an irregular foreign current-report stream | filing date, acceptance time, accession; provider report/event date retained when supplied |

Eligible records are deduplicated by accession. Conflicting metadata for one accession fails as
ambiguous. Ordering is descending filing date, acceptance timestamp, then accession number.
Provider response order, ingestion time, URL order, and dictionary order never select a filing.
An amendment is never included merely because it is newer. The period field is provenance and
display chronology; adapters do not interpret fiscal quarters, events, or accounting meaning.

## Primary-document, identity, and provenance model

The provider supplies the issuer CIK, accession, form, filing date, acceptance time, optional
report date, and `primaryDocument`. The exact archive location uses the issuer CIK directory,
accession digits, and primary filename. Exhibits and complete submissions are not candidates.

Firm identity, SEC issuer CIK, canonical artifact, provider form, accession, primary filename,
retrieval candidate, adapter, provider, repository document, observation, and content checksum
remain separate. Repository document identity is CIK plus accession; exact bytes remain
content-addressed. A valid accession prefix need not equal the issuer CIK: SEC issuer submissions
authoritatively associate rows with the issuer, while filing agents can produce a different
accession prefix. Live TASK-022 evidence exposed and corrected the prior overly strict check.

## Acquisition, query, browser, and SQLite boundary

Adapters receive only a provider client and clock and return existing acquisition contracts. They
do not import SQLite, issue SQL, receive database handles, inspect schemas, or call repository
persistence. Pull orchestration projects the selected adapter into the acquisition engine; the
repository owns publication. The existing query service normalizes filing date and acceptance
metadata for deterministic ordering, and the existing browser displays all four canonical types
without form-specific UI branches.

An equivalent latest-only rerun queries submissions, selects the same candidate, and returns
`no_change` at the source checkpoint before artifact retrieval. It reuses the artifact/document
and creates no additional `ArtifactObservation`. A separately successful acquisition attempt of
the same bytes can still create another observation under the TASK-019 repository contract.

## Live proof and limitations

The passing bounded proof used Seagate CIK 1137789 for Form 10-Q and Form 8-K, and ASML CIK 937966
for Form 20-F and Form 6-K. Four first pulls succeeded, four equivalent reruns returned
`no_change`, four artifacts and observations passed integrity, and restart/query/browser contracts
worked with network access blocked. Twelve requests, zero retries, and no request identity output
were recorded.

The first sandbox attempt retained four transport failures. The first network-enabled attempt
then exposed the accession-prefix defect: Form 10-Q succeeded while valid 8-K, 20-F, and 6-K
filings were rejected. After the provider correction and complete offline regression, a fresh live
state passed all four forms.

Only recent submissions and latest-visible selection are supported. Historical traversal, exact
accession workflows, scheduling, exhibits, attachment graphs, XBRL, item/event interpretation,
furnished-document classification, extraction, semantic analysis, and intelligence remain
deferred.
