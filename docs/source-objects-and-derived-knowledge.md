# Source objects and derived knowledge

TASK-005 introduces two repository subsystems with deliberately different authority and lifecycle.
The source-object catalog describes exact structure found in immutable artifacts. The
derived-knowledge store describes meaning inferred or normalized from those structures. A source
object is evidence location metadata; a knowledge object is interpretation and is always labeled
with status, confidence, derivation, version, and provenance.

## Boundaries and dependency direction

```text
AcquisitionRepository public artifact/document API
        |
        v
SourceObjectRepository (independent SQLite catalog)
        |
        | SourceObjectReader contract only
        v
KnowledgeRepository (independent versioned JSON generations)
```

The source package never imports knowledge code. Knowledge construction does not read SQLite,
artifact paths, acquisition ledgers, or document-index JSON. It consumes `SourceObjectReader` and
persists only stable source-object provenance assertions. Separate roots, schemas, publication
mechanisms, rebuild commands, integrity checks, and failure behavior make either implementation
replaceable without making the other authoritative.

## Source-object model

The initial SEC parser emits an artifact root, SEC header, header fields, embedded document
regions, and embedded document metadata fields. Every object records:

- repository document and immutable artifact identity;
- kind, structural role, ordinal, and optional parent identity;
- exact half-open byte span and SHA-256 of those bytes;
- a stable identity derived from the artifact identity, structural locator, and exact digest;
- a normalized value only for field objects.

Identity is independent of SQLite row order and rebuild time. The catalog can navigate from a
document to source objects and return bounded exact context when callers supply artifact bytes.
Integrity checks validate hierarchy, spans, and optional bytes. Unsupported signatures,
unclosed/missing SEC document structure, and parser failure are recorded as explicit per-artifact
outcomes. An atomic temporary-database replacement prevents partial rebuild publication.

## Derived-knowledge model

The bounded deterministic deriver produces:

- SEC issuer entities keyed by normalized CIK;
- filing observations keyed by repository document identity;
- issuer-filed relationships between those stable objects.

Each immutable version records a stable semantic object identity, payload, status, confidence,
derivation identity, supporting source objects, and optional superseded-version identity. Current
versions are selected by a small atomic generation pointer. Operator corrections create a new
version with a reason and explicit predecessor; old versions remain inspectable. Rebuilding from
unchanged source contracts reproduces the same object, version, and generation identities.

Conflicting names for one CIK create a `conflicted` entity and an ambiguity failure. Missing
required fields create an incomplete-extraction failure. Optional filing dates produce an
`uncertain` observation rather than an invented value. Missing or changed source-object provenance
fails integrity verification. A failed rebuild does not advance the current-generation pointer.

## Console inspection and proof

Run the offline checked-fixture proof:

```sh
make task005-proof
```

Run the bounded ten-filing real-corpus proof from the TASK-004 state:

```sh
.venv/bin/python scripts/task005_operator.py real-proof \
  --acquisition-state .artifacts/runtime/TASK-004-edgar \
  --state .artifacts/runtime/TASK-005
```

Inspect already-built state:

```sh
.venv/bin/python scripts/task005_operator.py source-inventory --state STATE
.venv/bin/python scripts/task005_operator.py knowledge-inventory --state STATE
.venv/bin/python scripts/task005_operator.py verify --state STATE
```

The proof reports both provenance directions, source and knowledge inventories, exact artifact
locators, integrity, separate storage paths, and stable identities across independent rebuilds.
It is intentionally console inspection, not the TASK-006 retrieval system or source browser.

## Limitations

The parser supports SEC complete-submission SGML only and does not parse HTML sections, inline XBRL,
tables, PDFs, or semantic document sections. The ontology is deliberately bounded to issuer,
filing observation, and filed-by relationship concepts. Knowledge generations are single-writer
and do not yet garbage-collect old generations. Correction provenance retains the original source
support and does not yet accept additional human evidence. Retrieval indexes, vector search,
free-form questions, model reasoning, and consulting workflows remain outside TASK-005.
