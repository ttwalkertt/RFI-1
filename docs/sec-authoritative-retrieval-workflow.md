# SEC authoritative retrieval workflow

TASK-036 introduces an independently invocable SEC-specific workflow:

```text
firm → applicability → durable SEC source → validation/bootstrap
     → exact Form 10-K policy → SEC submissions metadata → deterministic selection
     → exact SEC archive bytes → AcquisitionRepository → operator outcome
```

Run it with:

```bash
RFI_SEC_USER_AGENT='RFI-1 operator@example.com' \
  rfi sec-retrieve --state .artifacts/runtime/rfi-1 --firm seagate
```

The command prints the durable run identity, terminal outcome, every reached lifecycle state,
bootstrap/refresh flags, immutable artifact identities, and sanitized diagnostics.

## Architectural design

`rfi.sec` is a narrow orchestration façade, not an acquisition framework. `FirmRepository`
continues to own the target firm. `SecRepository` owns current verified SEC source knowledge and
inspectable run journals in the shared SQLite authority. `FirmIdentifierSecResolver` consumes only
explicit governed CIK identifiers and confirms them against the authoritative SEC submissions
surface; it does not guess by name. The existing `SecForm10KAdapter` owns exact-form eligibility,
amendment exclusion, deterministic ordering, primary-document identity, and bounded provider
transport. `AcquisitionRepository` remains the only artifact-ingress authority and therefore
retains content addressing, immutable attempts and observations, idempotency, replay, and integrity.

```text
received
  → applicability_determined
  → source_loaded
  → source_validated                         (fresh verified source)
       or identity_resolved → source_persisted (missing or stale source)
  → filing_policy_determined
  → filings_enumerated → filing_selected → document_retrieved
  → retrieval_validated → artifact_ingested → completed

Any pre-ingress cancellation boundary → cancelled
Any terminal policy/provider/reconciliation condition → completed with explicit outcome
```

## Source model and reconciliation

One `sec_sources` row per firm records applicability (`direct`, `parent`, or `non_applicable`),
legal issuer, normalized CIK, filing regime, optional parent firm, verified status, timestamp, and
canonical JSON. Direct and parent identities require a CIK; non-applicable records forbid one.
Parent relationships are supported by the contracts and reconciliation boundary, but the initial
production resolver deliberately resolves only explicit direct CIKs. A future parent resolver may
be injected without changing workflow or artifact authority.

A fresh verified source is used first without resolution. Missing state is bootstrapped only from
an unambiguous authoritative result. A stale record is refreshed when issuer identity is unchanged;
legal name, filing regime, and timestamp may be refreshed. Different CIK, applicability, or parent
relationship is a conflict and fails closed without replacing durable state. Competing CIKs and
unresolved identity are ambiguity outcomes. Non-applicability is an explicit successful terminal
classification and performs no SEC retrieval.

## Failure and cancellation analysis

- No exact unamended Form 10-K is `no_qualifying_filing`, not a transport failure.
- Ambiguous or unresolved source resolution is `source_ambiguity`.
- Changed CIK or parent relationship is `source_conflict`; existing source knowledge remains.
- Bounded provider, validation, or repository errors are `retrieval_failure` with diagnostics.
- Operator cancellation is durable and checked before resolution and before artifact work. It
  leaves a bounded run journal and performs no later retrieval or ingestion.
- Repetition may add immutable observations/attempts but does not duplicate content-addressed
  artifacts or document authority.

## Explicit non-goals and limitations

No generic acquisition plan, web discovery, company-name guessing, IR/RSS/patent retrieval,
scheduling, historical filing pagination, broad forms, or full filing history is introduced.
Cancellation cannot interrupt a single already-running bounded HTTP request or the atomic ingress
transaction. The production resolver does not discover parent issuers or persist non-applicability;
those require an authoritative operator/provider resolution supplied through the public resolver
contract. Form 10-K remains limited to the SEC recent-submissions surface and excludes amendments.

## Architectural Status Summary

| Subsystem | Responsibility | Status |
|---|---|---|
| Target firm authority | Stable firm and governed recognition identifiers | Complete, unchanged |
| SEC source knowledge | Verified applicability/issuer/CIK/regime and reconciliation | Complete for this slice |
| Direct issuer resolver | Validate explicit CIK against authoritative SEC metadata | Complete |
| Parent/non-applicable resolution | Contract and durable representation | Usable with Limitations |
| Form 10-K policy/provider | Deterministic selection and exact bounded bytes | Complete, reused |
| Immutable artifact ingress | Content address, document authority, observations, replay | Complete, reused |
| SEC workflow journal | States, outcomes, cancellation, diagnostics | Complete |

The next milestone should use operational evidence to decide whether parent issuer resolution or
additional SEC artifact-specific workflows justify shared resolver mechanics. It should not begin
with a generic acquisition framework.
