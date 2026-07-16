"""Public contracts owned by the derived-knowledge subsystem."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Protocol

from rfi.source_objects.contracts import SourceObjectReader


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


class KnowledgeReader(Protocol):
    """Storage-independent read contract available to downstream access layers."""

    def inventory(self, include_superseded: bool = False) -> list[DerivedObject]:
        """Return current knowledge, or current-generation history when requested."""

    def get(self, object_id: str) -> DerivedObject:
        """Return the current version for one repository-owned identity."""

    def failures(self) -> list[DerivationFailure]:
        """Return visible failures and ambiguities for the current generation."""

    def by_source_object(self, source_object_id: str) -> list[DerivedObject]:
        """Navigate from exact source evidence to associated current interpretations."""

    def verify(self, source: SourceObjectReader) -> dict[str, int | str]:
        """Validate every current knowledge provenance assertion against source contracts."""
