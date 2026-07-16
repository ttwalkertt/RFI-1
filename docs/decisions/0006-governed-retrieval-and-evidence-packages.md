# ADR-0006: Governed retrieval and evidence-package boundary

- Status: accepted
- Scope: TASK-006

## Context

TASK-005 established immutable structural evidence and independently versioned interpretation.
Downstream consumers need relevant subsets without learning SQLite, generation-directory, or
artifact layouts. A raw vector API would obscure deterministic constraints, authority class,
provenance failures, exclusions, and coverage.

## Decision

Create a third `rfi.retrieval` package that depends only on public source, knowledge, and artifact
reader contracts. Persist search data as replaceable immutable generations selected atomically.
Fingerprint current public authority objects and fail closed when the selected generation is
missing, stale, corrupt, or built by a different vector implementation.

Use explicit query, result, score, decision, trace, health, context, and evidence-package
contracts. Keep source evidence and derived knowledge in distinct result and package collections.
Apply deterministic metadata filters with vector-plus-lexical candidate scoring and record a
decision for every considered object. Treat vector similarity as ranking input, never authority.

Assemble evidence separately from retrieval. Recheck provenance against the source reader and
immutable bytes, expand exact bounded byte context, deduplicate it, and omit a whole result when
its complete provenance context exceeds budget. Surface exclusions, truncation, uncertainty,
contradiction, derivation gaps, and empty results in stable package fields.

Use a deterministic signed feature-hashing vector for the first bounded proof. Expose a vectorizer
contract and test it against an independent character-trigram implementation. Prove replaceability
at the public contract level: schema and types, authority classes, exact provenance, budgets,
omissions, truncation, coverage, conflicts, ambiguity, and deterministic constrained selections.
Allow rankings and selected evidence to differ with an explicit explanation because candidate
scoring is implementation-owned. Use one console browser over the same contracts intended for
later model callers.

## Consequences and tradeoffs

Retrieval can be deleted and rebuilt without changing source or knowledge authority. Strict stale
checks make queries more expensive because current public contracts are fingerprinted, but prevent
authoritative-looking answers from partial or outdated search state. Full candidate decisions make
traces larger, but let an operator explain inclusion and exclusion.

The local vectorizer is reproducible and reviewable but provides weaker semantic recall than a
learned embedding model. Index generations duplicate searchable text and metadata intentionally;
that content is disposable candidate state. Exact evidence remains in artifacts and knowledge
meaning remains in versioned derived objects.

Whole-result budget omission favors provenance completeness over maximum hit count. Byte-window
context is format-neutral but less meaningful than future section-aware expansion.

## Alternatives considered

- Direct queries against source SQLite and knowledge JSON were rejected because consumers would
  couple to private storage and lifecycle assumptions.
- A unified vector-result type was rejected because it would collapse evidence and interpretation.
- Vector-only relevance was rejected because entity, period, document type, provenance, and
  deterministic exclusions are governing constraints.
- Persisting evidence packages as authority was rejected because packages are query projections
  and must remain reproducible from repository data.
- Silent lexical fallback after index or embedding failure was rejected because it could produce
  complete-looking but semantically different results.

## Proof limits

The bounded proof establishes contracts, exact provenance, filtering, traceability, context,
deduplication, budget behavior, rebuild, corruption detection, and contract-level implementation
replaceability. Governed retrieval contracts and failure semantics are complete. Retrieval quality
is provisional: the proof does not establish learned semantic recall, ranking quality, scale,
concurrency, autonomous query planning, answer generation, or consulting workflow fitness.
