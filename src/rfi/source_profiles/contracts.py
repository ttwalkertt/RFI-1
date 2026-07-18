"""Public contracts for canonical acquisition configuration and firm source profiles."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol


class SourceProfileError(RuntimeError):
    """Raised when canonical or firm-specific acquisition configuration is invalid."""


class AddressabilityClass(StrEnum):
    """How predictably an artifact family can be located."""

    DETERMINISTIC = "deterministic"
    SEMI_DETERMINISTIC = "semi-deterministic"
    DISCOVERY_BASED = "discovery-based"


@dataclass(frozen=True)
class RetrievalFieldDefinition:
    """One canonical retrieval-candidate field rendered by the administration UI."""

    name: str
    label: str
    description: str
    value_type: str
    multiple: bool


@dataclass(frozen=True)
class RetrievalModeDefinition:
    """One supported candidate shape and its required field alternatives."""

    mode: str
    label: str
    description: str
    supported_fields: tuple[str, ...]
    required_fields: tuple[str, ...]
    required_any: tuple[str, ...]


@dataclass(frozen=True)
class CanonicalArtifact:
    """One repository-owned acquisition-planning item."""

    artifact_id: str
    short_name: str
    label: str
    description: str
    category_id: str
    default_enabled: bool
    addressability: AddressabilityClass
    supported_retrieval_modes: tuple[str, ...]
    order: int


@dataclass(frozen=True)
class CanonicalCategory:
    """An ordered UI and planning group from the canonical template."""

    category_id: str
    label: str
    description: str
    order: int
    items: tuple[CanonicalArtifact, ...]


@dataclass(frozen=True)
class AcquisitionTemplate:
    """Validated canonical acquisition catalog and candidate-field authority."""

    schema_version: int
    retrieval_fields: tuple[RetrievalFieldDefinition, ...]
    retrieval_modes: tuple[RetrievalModeDefinition, ...]
    categories: tuple[CanonicalCategory, ...]

    @property
    def artifacts(self) -> tuple[CanonicalArtifact, ...]:
        """Return artifacts in canonical category and item order."""
        return tuple(item for category in self.categories for item in category.items)


@dataclass(frozen=True)
class RetrievalCandidate:
    """Firm-owned retrieval intent; it is not a retrieved source or provenance record."""

    mode: str
    priority: int
    url: str = ""
    locator: str = ""
    preferred_domains: tuple[str, ...] = ()
    discovery_hints: tuple[str, ...] = ()
    expected_media_type: str = ""
    parser_hint: str = ""
    operator_notes: str = ""


@dataclass(frozen=True)
class SourceProfileItem:
    """Firm-owned configuration for one canonical artifact family."""

    artifact_id: str
    enabled: bool
    retrieval_candidates: tuple[RetrievalCandidate, ...] = ()
    operator_notes: str = ""


@dataclass(frozen=True)
class SourceProfileDraft:
    """Validated mutable intent used to publish an immutable profile revision."""

    firm_id: str
    items: tuple[SourceProfileItem, ...]
    operator_notes: str = ""


@dataclass(frozen=True)
class SourceProfileRevision:
    """One immutable historical source-profile revision, independent of firm identity."""

    firm_id: str
    source_profile_revision_id: str
    revision_number: int
    items: tuple[SourceProfileItem, ...]
    operator_notes: str
    created_at: str
    updated_at: str
    supersedes_revision_id: str | None


@dataclass(frozen=True)
class SourceProfileView:
    """A saved revision or documented canonical defaults before first publication."""

    firm_id: str
    source_profile_revision_id: str | None
    revision_number: int
    items: tuple[SourceProfileItem, ...]
    operator_notes: str
    created_at: str | None
    updated_at: str | None
    supersedes_revision_id: str | None
    is_default: bool


class SourceProfileCatalog(Protocol):
    """Persistence-independent immutable source-profile authority."""

    def publish(
        self,
        draft: SourceProfileDraft,
        expected_revision_id: str | None,
    ) -> SourceProfileRevision:
        """Create or revise a profile using optimistic publication."""

    def validate(self, draft: SourceProfileDraft) -> None:
        """Validate and normalize-compatible profile intent without publication."""

    def get(
        self, firm_id: str, revision_id: str | None = None
    ) -> SourceProfileRevision | None:
        """Return current or historical configuration, or None before first save."""

    def history(self, firm_id: str) -> tuple[SourceProfileRevision, ...]:
        """Return immutable source-profile history in ascending revision order."""
