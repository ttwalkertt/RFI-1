"""Public contracts owned by the derived-knowledge subsystem."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class KnowledgeError(RuntimeError):
    """Raised when knowledge history, derivation, or provenance is invalid."""


class KnowledgeStatus(StrEnum):
    """Interpretive state that must never be silently promoted to fact."""

    CONFIRMED = "confirmed"
    UNCERTAIN = "uncertain"
    CONFLICTED = "conflicted"
    SUPERSEDED = "superseded"
    STALE = "stale"


@dataclass(frozen=True)
class ProvenanceReference:
    """Stable assertion about a supporting source object and exact artifact span."""

    source_object_id: str
    document_id: str
    artifact_id: str
    byte_start: int
    byte_end: int
    content_sha256: str


@dataclass(frozen=True)
class DerivedObject:
    """One immutable version of repository-owned interpreted knowledge."""

    object_id: str
    version_id: str
    object_type: str
    semantic_key: str
    payload: dict[str, Any]
    status: KnowledgeStatus
    confidence: float
    provenance: tuple[ProvenanceReference, ...]
    derivation_id: str
    supersedes_version_id: str | None = None
    annotations: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class DerivationFailure:
    """Auditable failure or ambiguity encountered while constructing knowledge."""

    failure_id: str
    document_id: str
    category: str
    message: str
    source_object_ids: tuple[str, ...] = ()
