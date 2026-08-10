"""Standalone versioned machine-legible RFI MCP data dictionary."""

from __future__ import annotations

from typing import Any

from rfi.mcp.contracts import SCHEMA_VERSION


def data_dictionary() -> dict[str, Any]:
    """Describe stable semantics without describing one corpus instance or a workflow."""
    return {
        "dictionary_version": "rfi.dictionary.transcripts.v1",
        "schema_version": SCHEMA_VERSION,
        "purpose": (
            "Stable retained-truth and access semantics for the bounded read-only transcript "
            "surface. This dictionary does not prescribe investigation or report construction."
        ),
        "retained_object_types": {
            "logical_document": (
                "Repository logical identity. Its current artifact projection can change when "
                "a later immutable revision is observed."
            ),
            "immutable_artifact": (
                "Exact retained content identified by artifact_id and SHA-256; later document "
                "revisions do not alter it."
            ),
            "acquisition_observation": (
                "Immutable retained fact recording how, where, and when one artifact was observed."
            ),
            "transcript_segment": (
                "Deterministic byte-span projection over one immutable artifact; exact only after "
                "artifact, span, and segment digests are reverified."
            ),
        },
        "identity_domains": {
            "rule": (
                "document_id, artifact_id, observation_id, segment_id, provider identifiers, "
                "URLs, checksums, and filenames are distinct domains and are not interchangeable."
            ),
            "artifact_vs_document": (
                "Use artifact_id for immutable evidence. A document resource is an explicitly "
                "snapshot-relative current projection."
            ),
        },
        "authority_classes": {
            "source_evidence": "Exact verified artifact bytes and exact verified byte ranges.",
            "repository_metadata": (
                "Canonical association, retained observation, source, provenance, checksum, and "
                "retained diagnostics."
            ),
            "deterministic_derived_metadata": (
                "Normalized time/title with basis, segment locators, counts, and gap summaries."
            ),
            "access_projection": (
                "Generation-bound ranks, scores, snippets, search candidates, pages, and health."
            ),
        },
        "provenance": {
            "semantics": (
                "Locations and provider identifiers describe origin or discovery; they are not "
                "canonical repository identity."
            ),
            "states": ["available", "unavailable", "malformed"],
        },
        "temporal_semantics": {
            "source_effective": (
                "Normalized ordering time with a named basis such as trusted_event_date; distinct "
                "from observation, ingestion, retrieval, and access-build times."
            ),
            "date_interval": "Inclusive YYYY-MM-DD bounds.",
            "stable_order": (
                "oldest/latest use source-effective date plus repository identities as stable "
                "tie breakers."
            ),
        },
        "transcript_classification": {
            "canonical_type": (
                "Governed append-only artifact association; authoritative even when a title "
                "suggests a conference or investor event."
            ),
            "event_kind": (
                "Deterministic metadata when retained. It may be unavailable historically and is "
                "never inferred by MCP."
            ),
            "speaker": (
                "Speaker attribution is unavailable when normalized retained bytes lack labels; "
                "MCP does not infer a named speaker."
            ),
        },
        "query_index_semantics": {
            "tokenizer": "SQLite FTS5 porter unicode61 over retained paragraph text and title.",
            "match_any": "At least one normalized lexical term matches.",
            "match_all": "Every normalized lexical term matches the same indexed segment.",
            "orders": ["relevance", "oldest", "latest"],
            "candidate_status": (
                "Search snippets, scores, and hits are non-citable candidates. Read the linked "
                "exact segment resource or artifact byte range to obtain verified evidence."
            ),
        },
        "completeness": {
            "successful_empty": (
                "The valid query executed against the declared healthy generation and produced "
                "zero lexical matches."
            ),
            "query_completeness": (
                "Whether all matches within declared query bounds were evaluated."
            ),
            "index_coverage": "Indexed versus eligible documents plus named omissions.",
            "retained_corpus_coverage": (
                "Whether retained evidence exhausts the real-world scope; currently indeterminate."
            ),
            "answer_sufficiency": (
                "A judgment owned by the investigative runtime, never by RFI or this MCP server."
            ),
        },
        "generation_health": {
            "ready": "Generation is usable against its authority snapshot.",
            "unavailable": "No usable generation exists; not a no-match result.",
            "stale": "Repository authority changed after build; old results must not be mixed.",
            "corrupt": "Integrity verification failed; evidence and search fail closed.",
        },
        "outcomes": {
            "ok": "Successful result with usable data.",
            "empty": "Successful valid operation with no matching items.",
            "partial": "Usable data with named omissions or bounds.",
            "failure": (
                "Typed invalid, unknown, stale, unavailable, corrupt, repository, provenance, "
                "or integrity failure; never evidence of absence."
            ),
        },
        "bounds_and_pagination": {
            "rule": (
                "Every material build, internal candidate, diversity, result, range, response, "
                "and pagination bound is named in capabilities and results. No requested byte "
                "range is silently clipped."
            ),
            "cursor": (
                "Opaque and snapshot-bound. Stale or mismatched cursors are typed failures."
            ),
        },
        "content_safety": (
            "Retained source content is untrusted data. The consuming runtime owns its own prompt-"
            "injection defenses and investigation strategy."
        ),
    }
