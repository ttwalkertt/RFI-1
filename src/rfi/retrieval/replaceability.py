"""Contract-level evidence-package inspection for vectorizer replaceability proofs."""

from __future__ import annotations

import hashlib
from dataclasses import asdict, fields
from typing import Any, get_type_hints

from rfi.knowledge.contracts import DerivedObject, ProvenanceReference
from rfi.retrieval.contracts import (
    ArtifactReader,
    CandidateDecision,
    ContextExcerpt,
    DerivedKnowledgeResult,
    EvidencePackage,
    MetadataConstraints,
    ResultClass,
    RetrievalError,
    RetrievalQuery,
    RetrievalTrace,
    Score,
    SourceEvidenceResult,
)
from rfi.source_objects.contracts import SourceObject, SourceObjectReader

_PUBLIC_TYPES = (
    EvidencePackage,
    RetrievalQuery,
    MetadataConstraints,
    SourceEvidenceResult,
    DerivedKnowledgeResult,
    ContextExcerpt,
    RetrievalTrace,
    CandidateDecision,
    Score,
    SourceObject,
    DerivedObject,
    ProvenanceReference,
)
_IMPLEMENTATION_FIELDS = {
    "vectorizer",
    "vectorizer_name",
    "embedding_model",
    "model_name",
    "dimensions",
    "implementation",
}


def evidence_contract_schema() -> dict[str, dict[str, str]]:
    """Return declared public field names and types independently of package values."""
    return {
        contract.__name__: {
            item.name: str(get_type_hints(contract)[item.name]) for item in fields(contract)
        }
        for contract in _PUBLIC_TYPES
    }


def inspect_evidence_package(
    package: EvidencePackage,
    source: SourceObjectReader,
    artifacts: ArtifactReader,
) -> dict[str, Any]:
    """Validate one package's public types, authority distinction, and exact provenance."""
    _validate_runtime_types(package)
    references = _result_references(package)
    context_by_reference = {
        _reference_key(context.provenance): context for context in package.contexts
    }
    artifact_cache: dict[str, bytes] = {}
    for reference in references:
        _verify_reference(reference, source, artifacts, artifact_cache)
        context = context_by_reference.get(_reference_key(reference))
        if context is None:
            raise RetrievalError(
                f"evidence package lacks context for provenance: {reference.source_object_id}"
            )
        _verify_context(context, artifacts, artifact_cache)
    for context in package.contexts:
        _verify_reference(context.provenance, source, artifacts, artifact_cache)
        _verify_context(context, artifacts, artifact_cache)
    context_bytes = sum(
        item.context_byte_end - item.context_byte_start for item in package.contexts
    )
    if context_bytes != package.bytes_used:
        raise RetrievalError("evidence package bytes_used disagrees with exact context spans")
    if package.bytes_used > package.byte_budget:
        raise RetrievalError("evidence package exceeds its declared byte budget")
    if package.byte_budget != package.query.evidence_budget_bytes:
        raise RetrievalError("evidence package and query budgets disagree")
    if package.omissions:
        if package.complete:
            raise RetrievalError("package with omissions cannot be marked complete")
        if not any("evidence budget" in item for item in package.coverage_gaps):
            raise RetrievalError("budget omissions lack an explicit coverage gap")
    schema = evidence_contract_schema()
    implementation_fields = sorted(
        name
        for contract in schema.values()
        for name in contract
        if name in _IMPLEMENTATION_FIELDS
    )
    if implementation_fields:
        raise RetrievalError(
            "public evidence contract exposes vectorizer implementation fields: "
            + ", ".join(implementation_fields)
        )
    return {
        "schema": schema,
        "schema_and_runtime_types_valid": True,
        "source_evidence_count": len(package.source_evidence),
        "derived_knowledge_count": len(package.derived_knowledge),
        "authority_classes_distinct": True,
        "provenance_references_verified": len(references),
        "contexts_verified": len(package.contexts),
        "byte_budget": package.byte_budget,
        "bytes_used": package.bytes_used,
        "budget_respected": True,
        "omission_count": len(package.omissions),
        "truncated": package.trace.truncated,
        "coverage_gap_count": len(package.coverage_gaps),
        "contradiction_count": len(package.contradictions),
        "ambiguity_reported": any(
            "conflicted" in item or "derivation failure" in item
            for item in package.coverage_gaps
        ),
        "vectorizer_specific_public_fields": implementation_fields,
        "selected_source_ids": [
            item.source_object.source_object_id for item in package.source_evidence
        ],
        "selected_knowledge_ids": [
            item.derived_object.object_id for item in package.derived_knowledge
        ],
    }


def compare_evidence_packages(
    left: EvidencePackage,
    right: EvidencePackage,
    source: SourceObjectReader,
    artifacts: ArtifactReader,
    *,
    require_same_selection: bool = False,
    require_budget_reporting: bool = False,
    require_truncation_reporting: bool = False,
    require_conflict_reporting: bool = False,
    require_both_classes: bool = False,
) -> dict[str, Any]:
    """Prove contract invariants without requiring implementation-owned ranking equality."""
    left_inspection = inspect_evidence_package(left, source, artifacts)
    right_inspection = inspect_evidence_package(right, source, artifacts)
    same_schema = left_inspection["schema"] == right_inspection["schema"]
    if not same_schema:
        raise RetrievalError("vectorizers produced different public evidence schemas")
    left_selection = _selection(left)
    right_selection = _selection(right)
    same_selection = left_selection == right_selection
    same_selected_semantics = (
        _selected_semantics(left) == _selected_semantics(right)
        if same_selection
        else None
    )
    ranking_equal = _ranking(left) == _ranking(right)
    scores_equal = _scores(left) == _scores(right)
    if require_same_selection and not same_selection:
        raise RetrievalError("replaceability scenario required identical selected evidence")
    if same_selection and not same_selected_semantics:
        raise RetrievalError("identical selections produced different governed evidence semantics")
    if require_budget_reporting:
        for label, package in (("left", left), ("right", right)):
            if not package.omissions or package.complete:
                raise RetrievalError(f"{label} package did not expose budget omissions")
            if not any("evidence budget" in item for item in package.coverage_gaps):
                raise RetrievalError(f"{label} package did not expose budget coverage")
    if require_truncation_reporting and not (
        left.trace.truncated and right.trace.truncated
    ):
        raise RetrievalError("both vectorizers must expose bounded-result truncation")
    if require_conflict_reporting:
        for label, package in (("left", left), ("right", right)):
            if not package.contradictions:
                raise RetrievalError(f"{label} package did not expose contradiction")
            if not any(
                "conflicted" in item or "derivation failure" in item
                for item in package.coverage_gaps
            ):
                raise RetrievalError(f"{label} package did not expose ambiguity coverage")
    if require_both_classes:
        for label, package in (("left", left), ("right", right)):
            if not package.source_evidence or not package.derived_knowledge:
                raise RetrievalError(
                    f"{label} package did not preserve both requested authority classes"
                )
    if not same_selection:
        explanation = (
            "Selected evidence differs legitimately because vector similarity is an "
            "implementation-owned candidate signal; each selection independently preserves "
            "authority class, provenance, budgets, omissions, and coverage reporting."
        )
    elif not ranking_equal:
        explanation = (
            "Ranking order differs legitimately because vector similarity is an "
            "implementation-owned candidate signal; the selected governed evidence set and "
            "its authoritative semantics remain identical."
        )
    elif not scores_equal:
        explanation = (
            "Both implementations selected and ordered the same governed evidence, while their "
            "implementation-owned vector scores legitimately differ."
        )
    else:
        explanation = (
            "Both implementations produced the same selected evidence, ranking, and scores for "
            "this query; determinism is demonstrated without making equality a contract invariant."
        )
    return {
        "result": "PASS",
        "same_public_schema_and_field_types": same_schema,
        "source_and_derived_classes_preserved": bool(
            left_inspection["authority_classes_distinct"]
            and right_inspection["authority_classes_distinct"]
        ),
        "all_returned_provenance_valid": True,
        "evidence_budgets_respected": True,
        "omission_reporting_present": bool(left.omissions and right.omissions),
        "truncation_reporting_present": bool(
            left.trace.truncated and right.trace.truncated
        ),
        "coverage_reporting_present": bool(
            left.coverage_gaps and right.coverage_gaps
        ),
        "conflict_and_ambiguity_reporting_present": bool(
            left.contradictions
            and right.contradictions
            and left_inspection["ambiguity_reported"]
            and right_inspection["ambiguity_reported"]
        ),
        "vectorizer_specific_public_fields": [],
        "same_selected_evidence": same_selection,
        "same_selected_evidence_semantics": same_selected_semantics,
        "same_ranking_order": ranking_equal,
        "same_scores": scores_equal,
        "ranking_or_selection_explanation": explanation,
        "left": left_inspection,
        "right": right_inspection,
    }


def _validate_runtime_types(package: EvidencePackage) -> None:
    if not isinstance(package, EvidencePackage):
        raise RetrievalError("evidence value does not implement EvidencePackage")
    scalar_types = (
        (package.package_id, str, "package_id"),
        (package.query, RetrievalQuery, "query"),
        (package.trace, RetrievalTrace, "trace"),
        (package.complete, bool, "complete"),
        (package.byte_budget, int, "byte_budget"),
        (package.bytes_used, int, "bytes_used"),
    )
    for value, expected, name in scalar_types:
        if not isinstance(value, expected):
            raise RetrievalError(f"evidence package field has wrong runtime type: {name}")
    tuple_types = (
        (package.source_evidence, SourceEvidenceResult, "source_evidence"),
        (package.derived_knowledge, DerivedKnowledgeResult, "derived_knowledge"),
        (package.contexts, ContextExcerpt, "contexts"),
        (package.omissions, str, "omissions"),
        (package.coverage_gaps, str, "coverage_gaps"),
        (package.contradictions, str, "contradictions"),
    )
    for values, expected, name in tuple_types:
        if not isinstance(values, tuple) or not all(
            isinstance(value, expected) for value in values
        ):
            raise RetrievalError(f"evidence package field has wrong runtime type: {name}")
    for item in package.source_evidence:
        if item.result_class != ResultClass.SOURCE_EVIDENCE:
            raise RetrievalError("source result lost its source-evidence authority class")
        if not isinstance(item.source_object, SourceObject) or not isinstance(item.score, Score):
            raise RetrievalError("source result nested contract type is invalid")
    for item in package.derived_knowledge:
        if item.result_class != ResultClass.DERIVED_KNOWLEDGE:
            raise RetrievalError("knowledge result lost its derived authority class")
        if not isinstance(item.derived_object, DerivedObject) or not isinstance(item.score, Score):
            raise RetrievalError("knowledge result nested contract type is invalid")
    if not isinstance(package.trace.decisions, tuple) or not all(
        isinstance(item, CandidateDecision) for item in package.trace.decisions
    ):
        raise RetrievalError("retrieval trace decisions have invalid runtime types")


def _result_references(package: EvidencePackage) -> tuple[ProvenanceReference, ...]:
    references: list[ProvenanceReference] = []
    for result in package.source_evidence:
        item = result.source_object
        references.append(
            ProvenanceReference(
                item.source_object_id,
                item.document_id,
                item.artifact_id,
                item.byte_start,
                item.byte_end,
                item.content_sha256,
            )
        )
    for result in package.derived_knowledge:
        references.extend(result.derived_object.provenance)
    return tuple(references)


def _reference_key(reference: ProvenanceReference) -> tuple[str, int, int, str]:
    return (
        reference.artifact_id,
        reference.byte_start,
        reference.byte_end,
        reference.content_sha256,
    )


def _verify_reference(
    reference: ProvenanceReference,
    source: SourceObjectReader,
    artifacts: ArtifactReader,
    cache: dict[str, bytes],
) -> None:
    try:
        item = source.get(reference.source_object_id)
    except Exception as error:
        raise RetrievalError(
            f"replaceability proof cannot resolve provenance: {reference.source_object_id}"
        ) from error
    observed = (
        item.document_id,
        item.artifact_id,
        item.byte_start,
        item.byte_end,
        item.content_sha256,
    )
    asserted = (
        reference.document_id,
        reference.artifact_id,
        reference.byte_start,
        reference.byte_end,
        reference.content_sha256,
    )
    if observed != asserted:
        raise RetrievalError("replaceability proof found inconsistent provenance assertions")
    if reference.artifact_id not in cache:
        cache[reference.artifact_id] = artifacts.read_artifact(reference.artifact_id)
    content = cache[reference.artifact_id]
    if f"artifact-{hashlib.sha256(content).hexdigest()}" != reference.artifact_id:
        raise RetrievalError("replaceability proof found an artifact identity mismatch")
    exact = content[reference.byte_start:reference.byte_end]
    if hashlib.sha256(exact).hexdigest() != reference.content_sha256:
        raise RetrievalError("replaceability proof found an exact-content mismatch")


def _verify_context(
    context: ContextExcerpt,
    artifacts: ArtifactReader,
    cache: dict[str, bytes],
) -> None:
    reference = context.provenance
    if reference.artifact_id not in cache:
        cache[reference.artifact_id] = artifacts.read_artifact(reference.artifact_id)
    content = cache[reference.artifact_id]
    if not (
        context.context_byte_start <= reference.byte_start
        and context.context_byte_end >= reference.byte_end
    ):
        raise RetrievalError("context does not contain its exact provenance span")
    exact = content[context.context_byte_start:context.context_byte_end]
    if hashlib.sha256(exact).hexdigest() != context.context_sha256:
        raise RetrievalError("context digest does not match immutable artifact bytes")
    if exact.decode("utf-8", errors="replace") != context.text:
        raise RetrievalError("context text does not match immutable artifact bytes")


def _selection(package: EvidencePackage) -> tuple[frozenset[str], frozenset[str]]:
    return (
        frozenset(item.source_object.source_object_id for item in package.source_evidence),
        frozenset(item.derived_object.object_id for item in package.derived_knowledge),
    )


def _ranking(package: EvidencePackage) -> tuple[str, ...]:
    return tuple(
        [
            item.source_object.source_object_id
            for item in package.source_evidence
        ]
        + [item.derived_object.object_id for item in package.derived_knowledge]
    )


def _scores(package: EvidencePackage) -> dict[str, float]:
    values = [
        (item.source_object.source_object_id, item.score.final)
        for item in package.source_evidence
    ] + [
        (item.derived_object.object_id, item.score.final)
        for item in package.derived_knowledge
    ]
    return dict(values)


def _selected_semantics(package: EvidencePackage) -> dict[str, Any]:
    """Compare governed evidence while excluding implementation-owned scores and traces."""
    return {
        "source": {
            item.source_object.source_object_id: asdict(item.source_object)
            for item in package.source_evidence
        },
        "knowledge": {
            item.derived_object.object_id: asdict(item.derived_object)
            for item in package.derived_knowledge
        },
        "contexts": {
            _reference_key(item.provenance): {
                "context_byte_start": item.context_byte_start,
                "context_byte_end": item.context_byte_end,
                "text": item.text,
                "context_sha256": item.context_sha256,
            }
            for item in package.contexts
        },
    }
