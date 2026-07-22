# ADR 0022 — Task-specific façade for Linux mailing-list acquisition

## Decision

Add a first-class Linux Mailing Lists workflow backed by a service façade that orchestrates the
existing governed-source, revisioned-stream, bounded-acquisition, immutable-artifact, provenance,
and query contracts. Use Lore/public-inbox Atom feeds for bounded production discovery and reply
enumeration. Keep repository identities secondary and generated deterministically.

## Rationale

The prior two-screen sequence exposed repository decomposition as the operator task. Improving its
generic forms would not let a Linux kernel engineer express “collect bounded Linux Block discussion
evidence” coherently. A façade supplies the missing task boundary while retaining one authority for
each durable concern. Provisional source validation permits a truthful non-persistent review.

Atom search is Lore's supported bounded discovery surface and preserves the adapter boundary. The
existing parser and repository remain authoritative for message identity, relationships, exact
bytes, and provenance; the browser does not infer threads.

## Consequences

The main operator path creates both source and stream through one explicit action, then performs a
real bounded test and exposes retained evidence. Generic source and stream screens remain available
as advanced administrative surfaces. The workflow has no shadow storage. Failures may reveal a
durable source created before stream failure, and must say so. A successful bounded but truncated
run reports **Configuration ready** because the saved definition is executable and separately
reports **Test evidence incomplete or truncated**. Executability never implies evidence
completeness.

Strict Lore validation canonicalizes supported host-case and trailing-slash variants at source
ingress, and the façade reuses the resulting existing source identity. The known malformed,
unused `linux-block-lore` legacy record is handled once by an exact schema-v5 persisted-state
repair. That migration atomically updates the governed-source and mailing-list projections only
when the complete known predicate matches and no durable dependency exists. The façade owns no
source-repair policy, endpoint, or mutation path; other conflicts remain central source-governance
work requiring a separately reviewed migration.

The implementation does not add scheduling, archive mirroring, durable cursors, cross-list
relationships, or patch-series semantics.
