# ADR-0005: Independent source-object and derived-knowledge subsystems

- Status: accepted
- Scope: TASK-005

## Context

Immutable TASK-004 SEC artifacts must become structurally addressable before the repository can
derive governed meaning. Treating parsed structure and interpretation as one store would make
parser replacement rewrite knowledge authority, couple optimization choices, and obscure whether
a value came from evidence or inference.

## Decision

Create a source-object subsystem whose authority is structural location in immutable evidence and
a derived-knowledge subsystem whose authority is explicitly versioned interpretation. Export a
small `SourceObjectReader` contract. Dependencies flow from the knowledge deriver to that contract;
the source subsystem knows nothing about knowledge persistence.

Persist source objects in a replaceable SQLite catalog published by atomic file replacement.
Persist knowledge as immutable JSON generation directories selected by an atomic pointer. This
uses different physical models in the POC to make lifecycle independence executable rather than
conceptual. Storage formats remain private.

Base source identities on artifact identity, structural kind and role, exact byte span, and content
digest. Base knowledge identities on semantic keys, and version identities on canonical payload,
status, confidence, provenance, and derivation identity. Provenance repeats the source object,
document, artifact, byte span, and digest assertions so replacement catalogs can be checked rather
than trusted by identity alone.

Use deterministic SEC header derivation for the first ontology. Preserve ambiguous names as
conflicted entities, missing required fields as failures, missing optional values as uncertain,
and corrections as superseding versions. Do not introduce model-assisted extraction in this
milestone.

## Consequences and tradeoffs

Rebuilding either subsystem is local, deterministic, independently publishable, and does not
require the other store to become authoritative. SQLite supports compact source inventory and
location indexes; JSON generations make knowledge history and review transparent. The cost is two
lifecycle implementations and deliberate duplication of provenance assertions. That duplication
is a contract check, not shared persistence.

Source identity changes when exact artifact bytes or structural spans change. This is intentional:
knowledge provenance then becomes stale instead of silently pointing to different evidence. A
future parser may add structures while preserving existing identities, or replace the catalog
entirely if it satisfies the same reader contract.

## Alternatives considered

- One relational schema with source and knowledge tables was rejected because shared migrations,
  transactions, and rebuild assumptions would couple the subsystems.
- Persisting normalized text as knowledge input was rejected because it would create a hidden
  shared representation and weaken exact artifact provenance.
- Deriving directly from acquisition metadata was rejected because acquisition provenance is not
  a structurally addressable source-object contract.
- Model-assisted extraction was deferred because deterministic SEC headers are enough to prove
  lifecycle, ambiguity, and provenance behavior without model reproducibility concerns.

## Proof limits

The real proof covers all ten bounded TASK-004 filings, 62,070,796 artifact bytes, and SEC SGML
structure. It does not establish broad document-format coverage, a complete consulting ontology,
concurrent writers, retrieval performance, or production correction workflows.
