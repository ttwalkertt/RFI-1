# ADR-0012 — Artifact-semantic deterministic SEC retrieval

## Status

Accepted by TASK-016.

## Context

TASK-014 made the canonical Form 10-K artifact configurable through an identifier candidate, and
TASK-015 made every enabled artifact participate in one shared Pull Workflow. The workflow's
initial adapter registry selected only by retrieval mode. That was sufficient for direct URLs but
was not a safe policy boundary for SEC filings: Form 10-K eligibility, amendment handling,
selection, multiplicity, and primary-document meaning are artifact semantics, not generic
`identifier` transport behavior.

The repository already contained a bounded native EDGAR adapter for TASK-004. That adapter proves
official SEC submissions and archive surfaces, fair-access identification, pacing, timeouts,
retries, response limits, and sanitized diagnostics. Its fixed multi-form historical corpus and
complete-submission retrieval policy do not satisfy the current canonical Form 10-K artifact.

## Decision

Add an explicit retrieval-adapter capability registry. Each registration declares a unique adapter
identity, the canonical artifact identities it supports (or an intentionally artifact-agnostic
declaration), its supported retrieval modes, and its acquisition-engine mechanism. The effective
selection key is the existing `(canonical artifact_id, retrieval candidate mode)` pair. Claims
that overlap on that pair fail during registry construction. Acquisition mechanism is downstream
routing metadata, not retrieval-adapter identity, and may be shared by adapters with distinct
effective capabilities. After capability selection, the workflow projects only the selected source
adapter into the mechanism-keyed acquisition-engine registry for that run. The generic Pull
Workflow plans and selects only through the retrieval registry; it does not test for Form 10-K or
SEC identifiers.

Add one `SecForm10KAdapter` with the exact capability `(sec_10k, identifier)`. It owns:

- exact `10-K` eligibility and explicit `10-K/A` exclusion;
- latest-visible selection ordered by filing date, acceptance timestamp, and accession number,
  all descending;
- duplicate-accession conflict detection and exactly-one multiplicity;
- selection of the SEC `primaryDocument`, not the complete submission or an exhibit;
- filing/candidate/document identity construction, artifact-role provenance, and Form 10-K failure
  interpretation.

Add one bounded `SecProviderClient`. It owns only reusable SEC mechanics: strict CIK normalization,
official submissions retrieval, columnar response decoding, authoritative issuer verification,
primary-document archive retrieval, request identity, HTTPS endpoint bounds, three-redirect limit,
20-second timeout, two attempts, 0.5-second pacing, 5 MB metadata and 50 MB artifact bounds,
content/status validation, and sanitized diagnostics. It does not filter forms or select filings.

The adapter returns ordinary acquisition `DiscoveryPage`, `AdapterCandidate`, and
`RetrievalResult` values. The existing engine and repository remain the only evidence ingress and
continue to own source, document, artifact, attempt, checkpoint, replay, and integrity semantics.

## Identity model

- Firm identity remains the repository `firm_id`.
- SEC issuer identity is normalized CIK.
- Filing identity is SEC CIK plus accession number.
- Filing artifact identity includes the selected primary-document role and filename as provenance.
- Retrieval candidate identity is CIK, accession, and primary role.
- Adapter and provider identities remain explicit attributes.
- Repository document identity is `document-sec-<CIK>-<accession digits>`.
- Immutable artifact identity remains the SHA-256 of exact retrieved bytes.

External URLs and filenames never define repository identity. A new filing can legitimately become
latest as the SEC source evolves; within one provider response, ordering and tie-breaking remain
deterministic.

## Alternatives considered

### Universal configurable SEC filing adapter

Rejected. Form eligibility, amendment rules, multiplicity, primary artifact meaning, and failure
semantics differ across 10-K, 10-Q, 8-K, proxies, ownership forms, foreign-issuer filings, and
exhibits. A form-parameter engine would centralize policy before those artifacts are observed.

### Add a Form 10-K branch to Pull Workflow

Rejected. It would make core orchestration understand source-specific semantics and require future
workflow changes for every canonical artifact.

### Treat every identifier candidate as SEC retrieval

Rejected. `identifier` is a configuration shape used by many future registries and platforms; it
does not identify a provider or artifact contract.

### Reuse the TASK-004 `EdgarAdapter` unchanged

Rejected. Its fixed STX/WDC, multi-form, date-bounded corpus deliberately retrieves complete
submissions. Changing it would weaken completed TASK-004 evidence and still conflate distinct
artifact contracts.

### Retrieve the complete submission or a glossy annual report

Rejected. TASK-016 requires the selected Form 10-K primary filing. A complete submission contains
additional filing artifacts; a glossy annual report is a distinct canonical artifact.

### LLM, browser, or open-web selection

Rejected. SEC CIK, structured submissions metadata, accession numbers, and primary-document fields
provide a deterministic authoritative path. Probabilistic runtime selection would reduce
reproducibility and is unnecessary.

## Consequences and limits

Adding another artifact adapter requires a unique adapter identity and a non-overlapping
artifact/mode capability declaration. It may share an acquisition mechanism and can reuse the
bounded SEC provider client only for provider mechanics. Capability priorities, fallback ordering,
and multiple-match resolution are deliberately absent; ambiguous claims fail at registration. No
dynamic plugin loading exists. Only recent submissions metadata is queried; exact historical
selection is deferred. Amendments are excluded, not separately configurable. The runtime remains
local, single-process, and single-writer. Semi-deterministic listing and discovery-based adapters
remain unimplemented.

The first live attempt revealed that SEC `reportDate` and `primaryDocument` can be empty on
unrelated filing rows. Provider-wide identity validation therefore requires CIK, accession, form,
filing date, and acceptance time; primary-document identity becomes mandatory after Form 10-K
selection; report date remains optional provenance. The failed attempt is retained as review
evidence.
