# ADR 0026: External Firm-Configuration Materialization

## Status

Accepted for TASK-041.

## Decision

Externally generated versioned JSON may own current firm, verified external SEC identity, and source
profile configuration on a per-firm basis. RFI validates the complete state-relative file set and
projects it into existing SQLite aggregates in one transaction before serving or acquiring.

Stable firm identities and immutable revision history are preserved. A small ownership table prevents
silent transfer back to editor authority and retains the exact read-only file projection. Managed
write paths fail closed; unmanaged firms retain existing editor behavior.

`firm_external_identities` is configuration input to existing SEC candidate synthesis.
`sec_sources` remains mutable workflow knowledge and is explicitly outside the materializer.
Acquisition and evidence authorities are unchanged.

## Consequences

- Microsoft can move first without forcing an atomic fleet conversion.
- Startup may append equivalent revisions until no-op detection is separately authorized.
- Missing managed files refuse startup.
- The v1 schema exposes only fields and SEC artifact behavior the current application can represent.
- Non-SEC parser/adapter expansion, schedules, file generation, watching, and reconciliation are not
  introduced.
