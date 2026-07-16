# Governed retrieval, evidence assembly, and source browser

TASK-006 adds a non-authoritative access subsystem over the independent source-object and
derived-knowledge authorities. It supplies one retrieval model to the console operator and future
model-facing callers. Search narrows and ranks repository objects; it never changes whether an
object is source evidence or derived interpretation.

## Boundaries and data flow

```text
Immutable acquisition artifacts       SourceObjectReader       KnowledgeReader
              |                               |                       |
              | exact bytes                   +-----------+-----------+
              |                                           |
              v                                           v
      EvidenceAssembler <--- typed results --- RetrievalRepository
              |                              disposable generations
              v
       EvidencePackage
       - source evidence
       - derived knowledge
       - verified contexts
       - retrieval trace
       - omissions and gaps
```

`rfi.retrieval` imports public contracts, not either subsystem's persistence schema. Source and
knowledge packages do not import retrieval. The index is a separate immutable JSON generation
selected by an atomic pointer. Its authority fingerprint is reproducible from current public
source objects, current knowledge versions, and visible derivation failures. A query fails closed
when the pointer is missing, the generation is corrupt, the fingerprint is stale, or its vector
implementation differs from the current implementation.

## Retrieval contract

`RetrievalQuery` declares result classes, query text, bounded candidate/result counts, context and
evidence budgets, a minimum score, and typed metadata constraints. Supported constraints cover
document and artifact identity, normalized SEC entity identity, document type, source kind/role,
knowledge type/status, and temporal bounds. Unknown constraints fail explicitly.

The initial candidate generator is a deterministic 256-dimensional signed hashing vector. It is
dependency-free and reproducible, not claimed to be a semantic embedding model. Metadata filters
are applied deterministically, vector and lexical scores are recorded separately, and identity is
the final tie-breaker. The vectorizer is a replaceable contract; evidence-package fields do not
depend on its dimensions or implementation. An independent character-trigram vectorizer exercises
the same boundary with different features, dimensions, scores, rankings, and potentially selected
evidence.

Results use separate `SourceEvidenceResult` and `DerivedKnowledgeResult` contracts. Every
candidate receives an inspectable decision such as `metadata:document_type`,
`below-minimum-score`, `candidate-limit`, `result-limit`, or
`vector-plus-metadata-match`. The trace records the exact query, index generation, authority
fingerprint, decisions, coverage notes, failures, and truncation state.

## Evidence assembly

`EvidenceAssembler` admits a result only after checking every provenance assertion against the
current source reader and exact immutable artifact bytes. Context is expanded by the query's byte
radius, hashed, decoded for inspection, and deduplicated by artifact/span/digest. If all required
context for a result cannot fit, that result is omitted instead of becoming provenance-incomplete.
The package reports byte use, omissions, requested classes with no selected result, derivation
coverage notes, uncertain or conflicted knowledge, and competing derived assertions.

The stable package keeps `source_evidence`, `derived_knowledge`, and `contexts` separate. It also
includes the complete retrieval trace, so later reasoning can cite both what was used and why
other candidates were excluded. Search scores are rationale, not evidence authority.

## Console browser

Build and prove the checked fixture corpus:

```sh
make task006-proof
```

Run the bounded ten-filing TASK-004 real-corpus proof:

```sh
.venv/bin/python scripts/task006_browser.py real-proof \
  --acquisition-state .artifacts/runtime/TASK-004-edgar \
  --state .artifacts/runtime/TASK-006
```

Inspect the repository and navigate provenance:

```sh
.venv/bin/python scripts/task006_browser.py acquisition-sources --state STATE \
  --acquisition-state ACQUISITION_STATE
.venv/bin/python scripts/task006_browser.py documents --state STATE \
  --acquisition-state ACQUISITION_STATE
.venv/bin/python scripts/task006_browser.py artifacts --state STATE \
  --acquisition-state ACQUISITION_STATE
.venv/bin/python scripts/task006_browser.py sources --state STATE
.venv/bin/python scripts/task006_browser.py source --state STATE --id SOURCE_OBJECT_ID
.venv/bin/python scripts/task006_browser.py knowledge --state STATE
.venv/bin/python scripts/task006_browser.py derived --state STATE --id KNOWLEDGE_OBJECT_ID
.venv/bin/python scripts/task006_browser.py from-source --state STATE --id SOURCE_OBJECT_ID
```

Inspect retrieval or assemble the corresponding evidence package:

```sh
.venv/bin/python scripts/task006_browser.py retrieve --state STATE \
  --query "Seagate annual report" --entity-id 1137789 --document-type 10-K
.venv/bin/python scripts/task006_browser.py package --state STATE \
  --acquisition-state ACQUISITION_STATE --query "Seagate annual report" \
  --entity-id 1137789 --document-type 10-K
```

Both commands use the same `RetrievalQuery`, trace, and result semantics. JSON output is stable,
scriptable, and deliberately more transparent than a conversational presentation.

## Vectorizer replaceability proof

The fixture and real-corpus proofs run both the signed token-hashing and character-trigram
implementations through `RetrievalRepository` and `EvidenceAssembler`. The proof does not require
ranking equality. Instead, `compare_evidence_packages` independently validates each output against
the declared public dataclass schema and current source/artifact authorities, then reports:

- the exact public schema and field types;
- preservation of separate source-evidence and derived-knowledge result classes;
- resolution and exact-byte validation of every returned provenance reference and context;
- byte-budget accounting, whole-result omissions, truncation, and coverage gaps;
- contradiction and ambiguity reporting over a checked conflicted-entity corpus;
- absence of vectorizer name, model, dimensions, or implementation fields from public contracts;
- identical authoritative evidence semantics for exact metadata-constrained selections; and
- the identities, order, and explicit rationale when scores, rankings, or selections differ.

Vector scores and candidate ordering are implementation-owned. Source objects, derived objects,
provenance, evidence budgets, and reporting semantics are repository-owned. The review proof makes
that boundary independently inspectable rather than claiming that replacement search engines must
rank alike.

## Failure semantics

- Missing indexes report `missing`; queries do not fall back to ungoverned scans.
- Authority changes report `stale`; a rebuild is required before another query.
- Digest, schema, inventory, or pointer inconsistency reports `corrupt` and fails closed.
- Vector generation failure aborts rebuild or query without publishing partial state.
- Unsupported metadata constraints are contract errors rather than ignored hints.
- Empty retrieval is a valid response with explicit class and coverage notes.
- Source/knowledge coverage gaps and derivation failures are carried into trace notes.
- Ambiguous or contradictory knowledge retains its status and is surfaced in package gaps.
- Provenance or immutable-byte inconsistency aborts assembly.
- Evidence-budget exhaustion omits whole results and records each omission.
- A failed rebuild leaves the prior atomic pointer unchanged.

Partial authoritative reads, artifact outages, and provenance inconsistency fail package assembly;
the implementation does not return a package that could look complete. Partial relevance coverage
is allowed only when explicitly represented by trace notes, omissions, and `complete=false`.

## Limits

The POC vectorizers provide deterministic token and character feature hashing, not learned
semantic recall or validated ranking quality.
There is no reranker, synonym model, query planner, distributed index, incremental indexing,
concurrency control, or performance claim. Source text search is limited to structural metadata
and normalized field values because TASK-005 does not yet expose semantic body sections. Context
uses byte windows rather than HTML-aware section expansion. Contradiction detection is bounded to
explicit conflicted status and competing retrieved semantic keys. Saved investigations, LLM
reasoning, and consulting outputs remain downstream milestones.

## Architectural Status Summary

- **Repository foundation — Complete.** Governing design, task model, validation, and review
  packaging remain in force.
- **Acquisition substrate — Complete.** Immutable artifacts and append-only acquisition history
  remain authoritative and outside retrieval state.
- **Acquisition engine — Complete.** Deterministic provider orchestration remains independently
  replayable.
- **Live SEC providers — Usable with Limitations.** Native EDGAR and SEC-API paths exist; the
  bounded accepted corpus is native EDGAR and continuous scheduling is absent.
- **Immutable evidence — Complete.** Artifact identity and exact bytes anchor every assembled
  context.
- **Source-object subsystem — Usable with Limitations.** Exact SEC SGML structures are stable and
  rebuildable; body sections, HTML, XBRL, tables, PDFs, and other formats remain unparsed.
- **Derived-knowledge subsystem — Usable with Limitations.** Versioned entities, observations,
  relationships, status, and provenance remain independent; the ontology is deliberately narrow.
- **Governed retrieval contracts and evidence assembly — Complete.** Typed results, deterministic
  metadata constraints, provenance verification, evidence budgets, inspection traces, replaceable
  vector candidates, and fail-closed lifecycle semantics are established over both authorities.
- **Retrieval quality — Provisional.** The deterministic token and character vectorizers prove the
  boundary and failure behavior, not learned semantic recall, ranking quality, or production-scale
  relevance. Quality evaluation and implementation selection remain future work.
- **Source/knowledge inspection experience — Complete.** The console browser spans governed
  sources, documents, artifacts, source objects, derived objects, bidirectional provenance,
  retrieval decisions, and evidence packages.
- **Model-guided intelligence — Not Started.** TASK-007 can now consume stable evidence packages
  and traces without access to storage internals.
- **Consulting workspace — Not Started.** Saved work and consulting projections remain TASK-008.

TASK-006 introduces a fourth architectural layer: disposable governed access state. It does not
create a fourth authority. The next milestone is TASK-007 model-guided intelligence with explicit
citations, uncertainty, and reproducible retrieval traces.
