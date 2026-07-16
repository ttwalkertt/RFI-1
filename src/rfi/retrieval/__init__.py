"""Governed retrieval, provenance-complete evidence assembly, and inspection contracts."""

from rfi.retrieval.contracts import (
    ArtifactReader,
    CandidateDecision,
    ContextExcerpt,
    DerivedKnowledgeResult,
    EvidencePackage,
    MetadataConstraints,
    ResultClass,
    RetrievalError,
    RetrievalHealth,
    RetrievalQuery,
    RetrievalResponse,
    RetrievalState,
    RetrievalTrace,
    Score,
    SourceEvidenceResult,
    Vectorizer,
)
from rfi.retrieval.evidence import EvidenceAssembler
from rfi.retrieval.replaceability import (
    compare_evidence_packages,
    evidence_contract_schema,
    inspect_evidence_package,
)
from rfi.retrieval.repository import RetrievalRepository
from rfi.retrieval.vector import CharacterNgramVectorizer, HashingVectorizer

__all__ = [
    "ArtifactReader",
    "CandidateDecision",
    "CharacterNgramVectorizer",
    "ContextExcerpt",
    "DerivedKnowledgeResult",
    "EvidenceAssembler",
    "EvidencePackage",
    "HashingVectorizer",
    "MetadataConstraints",
    "ResultClass",
    "RetrievalError",
    "RetrievalHealth",
    "RetrievalQuery",
    "RetrievalRepository",
    "RetrievalResponse",
    "RetrievalState",
    "RetrievalTrace",
    "Score",
    "SourceEvidenceResult",
    "Vectorizer",
    "compare_evidence_packages",
    "evidence_contract_schema",
    "inspect_evidence_package",
]
