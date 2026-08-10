"""Typed access contracts for the bounded RFI MCP experiment."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

SCHEMA_VERSION = "rfi.mcp.v1alpha1"
CAPABILITY_VERSION = "1.0.0"


class AccessHealth(StrEnum):
    """Externally visible state of one disposable access generation."""

    READY = "ready"
    UNAVAILABLE = "unavailable"
    STALE = "stale"
    CORRUPT = "corrupt"


class Outcome(StrEnum):
    """Successful result states; failures use a typed error record."""

    OK = "ok"
    EMPTY = "empty"
    PARTIAL = "partial"


class McpAccessError(RuntimeError):
    """Typed sanitized access failure that never masquerades as no matches."""

    def __init__(
        self,
        code: str,
        message: str,
        *,
        category: str = "access_failure",
        retryable: bool = False,
        evidence_implication: str = "No evidence-absence inference is permitted.",
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.category = category
        self.retryable = retryable
        self.evidence_implication = evidence_implication
        self.details = details or {}

    def record(self) -> dict[str, Any]:
        """Return the stable machine-readable failure representation."""
        return {
            "category": self.category,
            "code": self.code,
            "message": str(self),
            "retryable": self.retryable,
            "evidence_implication": self.evidence_implication,
            "details": self.details,
        }


@dataclass(frozen=True)
class AccessBound:
    """One named cap that materially constrained an access operation."""

    name: str
    value: int
    applied: bool
    effect: str


@dataclass(frozen=True)
class AccessDiagnostic:
    """One visible build or read omission without hidden investigative meaning."""

    code: str
    message: str
    document_id: str | None = None
    artifact_id: str | None = None


@dataclass(frozen=True)
class GenerationIdentity:
    """Identity, authority input, health, and build inventory for an access index."""

    capability_id: str
    capability_version: str
    generation_id: str
    authority_snapshot: str
    health: AccessHealth
    eligible_document_count: int
    indexed_document_count: int
    indexed_segment_count: int
    build_outcome: Outcome
    build_bounds: tuple[AccessBound, ...]
    diagnostics: tuple[AccessDiagnostic, ...] = ()


@dataclass(frozen=True)
class TranscriptProjection:
    """One deterministic exact-span locator in a disposable transcript generation."""

    segment_id: str
    document_id: str
    artifact_id: str
    ordinal: int
    byte_start: int
    byte_end: int
    segment_sha256: str
    text: str
    event_date: str
    event_date_basis: str
    title: str
    title_basis: str
    canonical_artifact_id: str
    event_kind: str | None
    speaker_label: str | None
    observation_id: str


@dataclass(frozen=True)
class SearchCandidate:
    """Non-citable lexical projection returned for runtime-directed discovery."""

    segment_id: str
    segment_uri: str
    document_id: str
    document_uri: str
    artifact_id: str
    artifact_uri: str
    ordinal: int
    event_date: str
    event_date_basis: str
    canonical_artifact_id: str
    score: float
    rank_basis: str
    snippet: str
    evidence_state: str = "candidate_only"
    authority_class: str = "access_projection"


@dataclass
class TraceContext:
    """Facts accumulated while servicing one MCP request."""

    referenced_document_ids: set[str] = field(default_factory=set)
    referenced_artifact_ids: set[str] = field(default_factory=set)
    referenced_observation_ids: set[str] = field(default_factory=set)
    referenced_segment_ids: set[str] = field(default_factory=set)
    artifact_digests: dict[str, str] = field(default_factory=dict)
    range_digests: dict[str, str] = field(default_factory=dict)
    bounds: list[dict[str, Any]] = field(default_factory=list)
    returned_count: int | None = None
    total_count: int | None = None
    cursor: str | None = None
    next_cursor: str | None = None
    truncated: bool = False
