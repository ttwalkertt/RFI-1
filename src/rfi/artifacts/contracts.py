"""Stable repository-owned read contracts for durable acquired artifacts."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class ArtifactQueryError(RuntimeError):
    """Structured, sanitized artifact read failure."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


class ArtifactOrder(StrEnum):
    """Supported source-effective query orders."""

    NEWEST = "newest"
    OLDEST = "oldest"


class ObservationSelection(StrEnum):
    """Named observation selectors accepted by artifact detail."""

    FIRST = "first"
    LAST = "last"


class ArtifactAssociation(StrEnum):
    """Whether repository evidence carries firm/canonical semantics."""

    FIRM_CANONICAL = "firm-canonical"
    UNASSOCIATED = "unassociated"


@dataclass(frozen=True)
class ArtifactQuery:
    """Bounded typed artifact query; no persistence-shaped predicates are accepted."""

    firm_ids: tuple[str, ...] = ()
    family_ids: tuple[str, ...] = ()
    canonical_artifact_ids: tuple[str, ...] = ()
    provider_ids: tuple[str, ...] = ()
    association_kinds: tuple[ArtifactAssociation, ...] = ()
    durable_statuses: tuple[str, ...] = ("durable",)
    source_effective_from: str | None = None
    source_effective_through: str | None = None
    order: ArtifactOrder = ArtifactOrder.NEWEST
    limit: int = 50
    cursor: str | None = None


@dataclass(frozen=True)
class SourceEffectiveOrder:
    """Provider-neutral ordering facts used by every consumer."""

    value: str
    basis: str
    secondary: str
    repository_tie_breaker: str


@dataclass(frozen=True)
class ArtifactSummary:
    """Compact normalized artifact projection for lists, trees, and planning."""

    document_id: str
    artifact_id: str
    association_kind: ArtifactAssociation
    association_basis: str
    firm_id: str | None
    firm_name: str | None
    family_id: str | None
    family_label: str | None
    canonical_artifact_id: str | None
    canonical_artifact_label: str | None
    display_title: str
    source_effective: SourceEffectiveOrder
    filing_or_publication_date: str | None
    period_date: str | None
    provider: str | None
    provider_artifact_type: str | None
    provider_identifiers: dict[str, str]
    durable_status: str
    ingestion_time: str
    checksum_sha256: str
    media_type: str
    content_size: int
    stored_content_available: bool


@dataclass(frozen=True)
class ArtifactReadDiagnostic:
    """Bounded integrity finding isolated from otherwise readable artifacts."""

    code: str
    message: str
    source_id: str
    document_id: str
    artifact_id: str


@dataclass(frozen=True)
class ProvenanceLocation:
    """One external provenance location; never repository identity."""

    location: str
    role: str


@dataclass(frozen=True)
class ArtifactObservation:
    """One immutable acquisition observation for one immutable artifact."""

    observation_id: str
    acquisition_attempt_id: str
    artifact_id: str
    document_id: str
    observed_at: str
    retrieval_adapter_id: str | None
    retrieval_mechanism: str
    source_profile_revision_id: str | None
    candidate_id: str
    source_id: str
    provenance_locations: tuple[ProvenanceLocation, ...]
    provider_identifiers: dict[str, str]
    diagnostics: dict[str, Any]
    metadata: dict[str, Any]
    status: str


@dataclass(frozen=True)
class ArtifactDetail:
    """Normalized operator inspection contract for one repository document."""

    summary: ArtifactSummary
    observation: ArtifactObservation
    observation_cursor: str
    has_previous_observation: bool
    has_next_observation: bool
    provenance_locations: tuple[ProvenanceLocation, ...]
    retrieval_adapter_id: str | None
    retrieval_mechanism: str
    source_profile_revision_id: str | None
    candidate_id: str
    source_id: str
    content_integrity: str
    original_source_available: bool
    original_source_url: str | None
    artifact_metadata: dict[str, Any] = field(default_factory=dict)
    malformed_fields: tuple[str, ...] = ()


@dataclass(frozen=True)
class ArtifactPage:
    """One snapshot-bound deterministic query page."""

    items: tuple[ArtifactSummary, ...]
    next_cursor: str | None
    repository_snapshot: str
    total_items: int
    diagnostics: tuple[ArtifactReadDiagnostic, ...] = ()


@dataclass(frozen=True)
class ArtifactContent:
    """Exact immutable bytes served separately from query and detail models."""

    document_id: str
    artifact_id: str
    content: bytes
    media_type: str
    checksum_sha256: str
