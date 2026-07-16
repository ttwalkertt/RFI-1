"""Provenance-complete bounded evidence assembly over governed retrieval results."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict
from typing import Any

from rfi.knowledge.contracts import KnowledgeStatus, ProvenanceReference
from rfi.retrieval.contracts import (
    ArtifactReader,
    ContextExcerpt,
    DerivedKnowledgeResult,
    EvidencePackage,
    RetrievalError,
    RetrievalResponse,
    ResultClass,
    SourceEvidenceResult,
)
from rfi.source_objects.contracts import SourceObjectReader


def _canonical(value: Any) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()


class EvidenceAssembler:
    """Assemble typed retrieval results without promoting search state to authority."""

    def __init__(self, source: SourceObjectReader, artifacts: ArtifactReader) -> None:
        self.source = source
        self.artifacts = artifacts

    def assemble(self, response: RetrievalResponse) -> EvidencePackage:
        """Verify provenance and include only results that fit with all required context."""
        query = response.trace.query
        ranked: list[SourceEvidenceResult | DerivedKnowledgeResult] = sorted(
            [*response.source_results, *response.knowledge_results],
            key=lambda item: (-item.score.final, self._identity(item)),
        )
        contexts: dict[tuple[str, int, int, str], ContextExcerpt] = {}
        source_results: list[SourceEvidenceResult] = []
        knowledge_results: list[DerivedKnowledgeResult] = []
        omissions: list[str] = []
        bytes_used = 0
        artifact_cache: dict[str, bytes] = {}
        for result in ranked:
            references = self._references(result)
            pending: list[tuple[tuple[str, int, int, str], ContextExcerpt, int]] = []
            required = 0
            for reference in references:
                key = (
                    reference.artifact_id,
                    reference.byte_start,
                    reference.byte_end,
                    reference.content_sha256,
                )
                if key in contexts or any(item[0] == key for item in pending):
                    continue
                excerpt, size = self._context(reference, query.context_radius, artifact_cache)
                pending.append((key, excerpt, size))
                required += size
            if bytes_used + required > query.evidence_budget_bytes:
                omissions.append(
                    f"{self._identity(result)} omitted: evidence budget cannot include all "
                    "provenance context"
                )
                continue
            for key, excerpt, size in pending:
                contexts[key] = excerpt
                bytes_used += size
            if isinstance(result, SourceEvidenceResult):
                source_results.append(result)
            else:
                knowledge_results.append(result)
        contradictions = self._contradictions(knowledge_results)
        gaps = list(response.trace.coverage_notes)
        if omissions:
            gaps.append("evidence budget excluded one or more otherwise selected results")
        for result in knowledge_results:
            status = result.derived_object.status
            if status in {KnowledgeStatus.UNCERTAIN, KnowledgeStatus.CONFLICTED}:
                gaps.append(
                    f"{result.derived_object.object_id} has {status.value} interpretive status"
                )
        gaps = list(dict.fromkeys(gaps))
        material = {
            "query": asdict(query),
            "source": [asdict(item) for item in source_results],
            "knowledge": [asdict(item) for item in knowledge_results],
            "contexts": [asdict(item) for item in contexts.values()],
            "trace": asdict(response.trace),
            "omissions": omissions,
            "gaps": gaps,
            "contradictions": contradictions,
        }
        package_id = f"evidence-package-{hashlib.sha256(_canonical(material)).hexdigest()}"
        complete = not omissions and not gaps and not response.trace.failures
        return EvidencePackage(
            package_id,
            query,
            tuple(source_results),
            tuple(knowledge_results),
            tuple(contexts.values()),
            response.trace,
            tuple(omissions),
            tuple(gaps),
            tuple(contradictions),
            complete,
            query.evidence_budget_bytes,
            bytes_used,
        )

    def _references(
        self, result: SourceEvidenceResult | DerivedKnowledgeResult
    ) -> tuple[ProvenanceReference, ...]:
        if isinstance(result, DerivedKnowledgeResult):
            if not result.derived_object.provenance:
                raise RetrievalError(
                    f"derived result has no provenance: {result.derived_object.object_id}"
                )
            return result.derived_object.provenance
        item = result.source_object
        return (
            ProvenanceReference(
                item.source_object_id,
                item.document_id,
                item.artifact_id,
                item.byte_start,
                item.byte_end,
                item.content_sha256,
            ),
        )

    def _context(
        self,
        reference: ProvenanceReference,
        radius: int,
        cache: dict[str, bytes],
    ) -> tuple[ContextExcerpt, int]:
        try:
            source = self.source.get(reference.source_object_id)
        except Exception as error:
            raise RetrievalError(
                f"provenance source object is absent: {reference.source_object_id}"
            ) from error
        observed = (
            source.document_id,
            source.artifact_id,
            source.byte_start,
            source.byte_end,
            source.content_sha256,
        )
        asserted = (
            reference.document_id,
            reference.artifact_id,
            reference.byte_start,
            reference.byte_end,
            reference.content_sha256,
        )
        if observed != asserted:
            raise RetrievalError(
                f"provenance inconsistency for source object: {reference.source_object_id}"
            )
        if reference.artifact_id not in cache:
            try:
                cache[reference.artifact_id] = self.artifacts.read_artifact(
                    reference.artifact_id
                )
            except Exception as error:
                raise RetrievalError(
                    f"immutable artifact is unavailable: {reference.artifact_id}"
                ) from error
        content = cache[reference.artifact_id]
        artifact_id = f"artifact-{hashlib.sha256(content).hexdigest()}"
        if artifact_id != reference.artifact_id:
            raise RetrievalError(f"immutable artifact identity mismatch: {reference.artifact_id}")
        exact = content[reference.byte_start:reference.byte_end]
        if hashlib.sha256(exact).hexdigest() != reference.content_sha256:
            raise RetrievalError(
                f"exact provenance content mismatch: {reference.source_object_id}"
            )
        start = max(0, reference.byte_start - radius)
        end = min(len(content), reference.byte_end + radius)
        context = content[start:end]
        return (
            ContextExcerpt(
                reference,
                start,
                end,
                context.decode("utf-8", errors="replace"),
                hashlib.sha256(context).hexdigest(),
            ),
            len(context),
        )

    def _identity(self, result: SourceEvidenceResult | DerivedKnowledgeResult) -> str:
        if result.result_class == ResultClass.SOURCE_EVIDENCE:
            assert isinstance(result, SourceEvidenceResult)
            return result.source_object.source_object_id
        assert isinstance(result, DerivedKnowledgeResult)
        return result.derived_object.object_id

    def _contradictions(self, results: list[DerivedKnowledgeResult]) -> list[str]:
        contradictions: list[str] = []
        grouped: dict[tuple[str, str], list[DerivedKnowledgeResult]] = {}
        for result in results:
            item = result.derived_object
            grouped.setdefault((item.object_type, item.semantic_key), []).append(result)
            if item.status == KnowledgeStatus.CONFLICTED:
                contradictions.append(
                    f"{item.object_id} is explicitly conflicted: {item.payload}"
                )
        for key, values in grouped.items():
            payloads = {_canonical(item.derived_object.payload) for item in values}
            if len(payloads) > 1:
                contradictions.append(
                    f"competing derived assertions for {key[0]} {key[1]}"
                )
        return sorted(set(contradictions))
