# ADR-0004: Native EDGAR acceptance with optional commercial acceleration

- Status: accepted implementation; native live acceptance blocked pending runtime identity
- Scope: TASK-004 and the authorized 2026-07-15 native EDGAR amendment

## Context

TASK-004 originally selected SEC-API.io as its commercial live provider. The complete commercial
adapter, profiles, fixtures, tests, and blocked review package were implemented, but no credential
was available. The operator then authorized native SEC EDGAR as the required live acceptance path
while retaining SEC-API.io as an optional, offline-verified acceleration path.

Both adapters must preserve one repository-owned SEC filing identity and use the unchanged
TASK-003 adapter, engine, and repository contracts. The native path must comply with SEC fair-access
guidance, including a declared operator-supplied User-Agent and conservative request pacing.

## Decision

Use the official EDGAR submissions endpoint
`GET https://data.sec.gov/submissions/CIK##########.json` for native discovery. Decode the official
columnar `filings.recent` structure and any overlapping referenced submissions-history files.
Select exactly the newest one 10-K, two 10-Qs, and two 8-Ks per issuer within the fixed inclusive
2024-01-01 through 2025-12-31 interval. Page the resulting five-candidate set one item at a time
behind provider-specific in-run continuations.

Retrieve exact complete-submission bytes from
`https://www.sec.gov/Archives/edgar/data/<CIK>/<accession digits>/<accession>.txt`. Preserve those
bytes unchanged. The adapter validates the complete-submission marker but never parses filing
content.

Require the operator to set `RFI_SEC_USER_AGENT` at runtime to a descriptive application identity
and contact email. Checked-in profiles contain only `env:RFI_SEC_USER_AGENT`. The value exists only
in process memory and the outgoing User-Agent header; it must not enter repository evidence,
diagnostics, fixtures, patches, or review artifacts. Missing or malformed identity stops before
network access.

Pace native requests at no more than two per second through a minimum 0.5-second interval, below
the SEC-published maximum of ten requests per second. Use a 20-second timeout, two bounded attempts,
a 50 MB artifact limit, a 5 MB submissions limit, and an 80-request process ceiling for the bounded
two-run acceptance. Retry 429, timeout, and selected 5xx responses once. Discard error bodies and
emit only sanitized classifications.

Retain SEC-API.io Query and Filing Download adapters as an optional commercial path. Its credential
remains `SEC_API_IO_API_KEY`, referenced indirectly. Commercial live behavior is untested and does
not determine TASK-004 completion after the amendment.

## Identity and provenance

Issuer identity is normalized SEC CIK. Logical filing identity is CIK plus SEC accession number.
Each amendment has its own accession and filing identity. Candidate identity adds the exact
complete-submission artifact role. Artifact identity remains repository SHA-256 of exact bytes.

EDGAR hosts, archive paths, submissions JSON fields, primary-document names, historical-file names,
and continuations are provenance. SEC-API.io object IDs, endpoints, response fields, and quota
headers are also provenance. Neither provider defines repository document or artifact identity.

## Contract compatibility

Both adapters implement the unchanged `discover` and `retrieve` contract and never receive a
repository. No TASK-002 or TASK-003 production contract correction was required by offline native
evidence. Scope/baseline tests were narrowly extended to allow network imports only inside the two
provider adapters; engine and repository networking remains prohibited.

Cross-provider acquisition of the same accession has not yet occurred live. If later evidence
shows attempt-identity conflict between source mechanisms, TASK-005 should make the narrowest
compatible history-identity correction rather than changing filing or artifact identity.

## Alternatives considered

- Making SEC-API.io live acceptance mandatory remained blocked on a missing commercial credential.
- Inventing or committing an operator contact was rejected as noncompliant and privacy-unsafe.
- Ten requests per second was allowed by current SEC guidance but rejected as unnecessarily
  aggressive for a ten-filing POC; two per second is proportionate.
- Bulk submissions ZIPs, daily indexes, full-text search, and XBRL endpoints were rejected because
  the per-issuer submissions API supplies the bounded discovery data directly.
- Filing-details HTML is smaller, but complete-submission text is the authoritative filing-level
  artifact and matches the established repository evidence choice.
- Relative dates and mixed-form total caps were rejected because they can silently widen or omit
  required form variety.

## Current status and TASK-005 recommendations

The native adapter, operator boundary, deterministic fixtures, and offline lifecycle are verified.
Native live acceptance remains blocked because `RFI_SEC_USER_AGENT` was absent from the execution
environment. No native request or live-success claim was made.

After live evidence exists, TASK-005 should assess submissions schema drift, historical-file
behavior, response caching headers, retry-after handling, cross-provider attempt identity,
run-scoped request accounting, writer locking, and runtime corpus backup/retention. Extraction,
knowledge development, AI, search, and reporting remain separate future capabilities.
