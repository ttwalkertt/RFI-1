"""Stable governed-retrieval and evidence-package contracts."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Protocol

from rfi.knowledge.contracts import DerivedObject, KnowledgeStatus, ProvenanceReference
from rfi.source_objects.contracts import SourceObject


class RetrievalError(RuntimeError):
    """Raised when rebuildable retrieval state cannot be trusted or used."""


class ResultClass(StrEnum):
    """Authority class retained through retrieval and evidence assembly."""

    SOURCE_EVIDENCE = "source-evidence"
    DERIVED_KNOWLEDGE = "derived-knowledge"


class RetrievalState(StrEnum):
    """Operator-visible health of non-authoritative search state."""

    READY = "ready"
    MISSING = "missing"
    STALE = "stale"
    CORRUPT = "corrupt"


@dataclass(frozen=True)
class MetadataConstraints:
    """Deterministic filters applied before final bounded selection."""

    document_ids: tuple[str, ...] = ()
    artifact_ids: tuple[str, ...] = ()
    entity_ids: tuple[str, ...] = ()
    document_types: tuple[str, ...] = ()
    source_kinds: tuple[str, ...] = ()
    source_roles: tuple[str, ...] = ()
    knowledge_types: tuple[str, ...] = ()
    knowledge_statuses: tuple[KnowledgeStatus, ...] = ()
    period_from: str | None = None
    period_to: str | None = None
    unsupported: tuple[str, ...] = ()


@dataclass(frozen=True)
class RetrievalQuery:
    """Repository-owned bounded query contract, independent of search implementation."""

    text: str
    result_classes: tuple[ResultClass, ...] = (
        ResultClass.SOURCE_EVIDENCE,
        ResultClass.DERIVED_KNOWLEDGE,
    )
    constraints: MetadataConstraints = field(default_factory=MetadataConstraints)
    max_results: int = 10
    candidate_limit: int = 50
    context_radius: int = 160
    evidence_budget_bytes: int = 16_000
    minimum_score: float = 0.01


@dataclass(frozen=True)
class Score:
    """Inspectable components used to rank one accepted candidate."""

    vector: float
    lexical: float
    final: float


@dataclass(frozen=True)
class SourceEvidenceResult:
    """A source result that remains exact structural evidence."""

    result_class: ResultClass
    source_object: SourceObject
    score: Score
    rationale: tuple[str, ...]
    metadata: dict[str, tuple[str, ...]]


@dataclass(frozen=True)
class DerivedKnowledgeResult:
    """A knowledge result explicitly labeled as derived interpretation."""

    result_class: ResultClass
    derived_object: DerivedObject
    score: Score
    rationale: tuple[str, ...]
    metadata: dict[str, tuple[str, ...]]


@dataclass(frozen=True)
class CandidateDecision:
    """Why a candidate was included, bounded, or deterministically excluded."""

    identity: str
    result_class: ResultClass
    included: bool
    reason: str
    score: Score | None = None


@dataclass(frozen=True)
class RetrievalTrace:
    """Complete inspectable execution record for one deterministic retrieval."""

    trace_id: str
    index_generation_id: str
    authority_fingerprint: str
    query: RetrievalQuery
    decisions: tuple[CandidateDecision, ...]
    failures: tuple[str, ...]
    coverage_notes: tuple[str, ...]
    truncated: bool


@dataclass(frozen=True)
class RetrievalResponse:
    """Typed retrieval results plus the exact trace that produced them."""

    source_results: tuple[SourceEvidenceResult, ...]
    knowledge_results: tuple[DerivedKnowledgeResult, ...]
    trace: RetrievalTrace


@dataclass(frozen=True)
class ContextExcerpt:
    """Verified exact artifact context surrounding one provenance reference."""

    provenance: ProvenanceReference
    context_byte_start: int
    context_byte_end: int
    text: str
    context_sha256: str


@dataclass(frozen=True)
class EvidencePackage:
    """Stable, bounded handoff contract for operators and future model consumers."""

    package_id: str
    query: RetrievalQuery
    source_evidence: tuple[SourceEvidenceResult, ...]
    derived_knowledge: tuple[DerivedKnowledgeResult, ...]
    contexts: tuple[ContextExcerpt, ...]
    trace: RetrievalTrace
    omissions: tuple[str, ...]
    coverage_gaps: tuple[str, ...]
    contradictions: tuple[str, ...]
    complete: bool
    byte_budget: int
    bytes_used: int


@dataclass(frozen=True)
class RetrievalHealth:
    """Index state relative to current authoritative repository contracts."""

    state: RetrievalState
    message: str
    generation_id: str | None = None
    indexed_items: int = 0


class ArtifactReader(Protocol):
    """Public exact-evidence access required only during evidence assembly."""

    def read_artifact(self, artifact_id: str) -> bytes:
        """Return verified immutable artifact bytes for one identity."""


class Vectorizer(Protocol):
    """Replaceable candidate-vector implementation behind stable retrieval contracts."""

    @property
    def name(self) -> str:
        """Return an implementation and version identifier."""

    def vector(self, text: str) -> tuple[float, ...]:
        """Create a deterministic vector or raise an explicit failure."""
