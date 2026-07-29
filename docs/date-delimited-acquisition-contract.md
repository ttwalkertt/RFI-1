# Date-Delimited Acquisition Contract

TASK-047 defines the observable boundary for future artifact-family acquisition over a closed-open
date interval. It does not define a retriever framework or execution protocol.

## Canonical request and result

`IntervalAcquisitionRequest` identifies an existing canonical firm by `FirmRevision.firm_id`, an
existing canonical artifact family by `CanonicalArtifact.artifact_id`, and
`[start_date, end_date)`. Equal boundaries form a valid empty interval. A start after the end is
invalid.

`IntervalAcquisitionResult` contains zero or more order-independent successful
`IntervalArtifactEnvelope` values, zero or more structured failures, and exactly one coverage value:

- `complete`: the acquisition implementation determined the whole interval was evaluated. This
  includes a successful empty interval and an interval with no qualifying artifacts. Complete
  coverage cannot contain a reported failure.
- `incomplete`: a known portion or artifact could not be acquired. Successfully acquired artifacts
  remain valid and are persisted.
- `indeterminate`: the implementation cannot establish whether the interval is complete. This stays
  distinct from a known hole in durable history.

An envelope supplies the existing `CandidateDocument` and `RetrievalResult` ingress values plus the
artifact date used to enforce the requested boundary. It does not assign a new interval-specific
canonical identity. Artifact ordering has no semantic meaning.

## Responsibility boundary

The artifact-specific acquisition implementation owns discovery, retrieval, validation, bounded
within-invocation retries, and truthful result construction. It may be sequential or parallel. The
contract exposes no callbacks, workers, queues, generators, sessions, resume state, concurrency, or
synchronous/asynchronous requirement.

The narrow application service validates that the firm exists, the artifact type belongs to the
canonical acquisition template, each successful artifact lies inside the interval, and its governed
source policy matches the request. It passes each successful envelope through the existing
`AcquisitionRepository.record_success` ingress and then records the overall interval outcome. The
application owns later retry policy, scheduling, and operator workflow.

The repository retains its existing responsibilities and mechanisms:

- content-hash artifact identity and immutable exact bytes;
- document and candidate identity handling under the existing acquisition ingress;
- duplicate handling and idempotent persistence;
- acquisition attempts and artifact observations; and
- acquisition history.

Schema 13 adds interval outcome history and links each successful outcome member to the already
persisted acquisition attempt and artifact observation. It does not add a parallel artifact,
document, or observation path. Structured failures and complete/incomplete/indeterminate coverage
are retained in the outcome's canonical record.

## Recovery and retry ownership

An implementation may retry transient failures a bounded number of times before returning. It does
not schedule future work or retain execution state. The application may later request the same
interval again. Every later invocation creates another immutable acquisition outcome and ordinary
artifact observations; existing immutable content is reused by repository idempotency. A partial
first result therefore retains its successes, while a later complete result can add the missing
artifact without a resume protocol.

## Intentional limitations

TASK-047 includes only a non-production test double. It implements no earnings-call or press-release
retriever, HTTP discovery, parsing, provider adapter, generic retrieval framework, or concurrency
policy. TASK-048 now provides the first production implementation for official textual
earnings-call transcripts. It remains artifact-specific: bounded issuer/authorized-IR listing
discovery and optional candidate proposals feed deterministic host, date, media, and transcript
validation. Only validated envelopes cross this contract and enter the repository through the
existing application service. Search-located proposals never establish complete coverage.
