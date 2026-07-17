"""Public contracts for durable target-firm identity and recognition metadata."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Protocol


class FirmError(RuntimeError):
    """Raised when firm-catalog state or requested intent is invalid."""


class FirmStatus(StrEnum):
    """Operator-owned lifecycle state for a target firm."""

    DRAFT = "draft"
    ACTIVE = "active"
    PAUSED = "paused"
    RETIRED = "retired"


@dataclass(frozen=True)
class FirmIdentifier:
    """A typed recognition identifier such as a ticker, CIK, or LEI."""

    kind: str
    value: str
    market: str | None = None


@dataclass(frozen=True)
class FirmRelationship:
    """A lightweight reference to another stable firm identity."""

    kind: str
    target_firm_id: str
    label: str = ""
    notes: str = ""


@dataclass(frozen=True)
class FirmReference:
    """Stable integration reference; callers may optionally pin recognition semantics."""

    firm_id: str
    firm_revision_id: str | None = None


@dataclass(frozen=True)
class SourceDiscoveryHint:
    """Operator guidance for locating sources without becoming source evidence."""

    kind: str
    value: str
    notes: str = ""


@dataclass(frozen=True)
class FirmDraft:
    """Validated mutable intent used to create an immutable firm revision."""

    firm_id: str
    canonical_name: str
    valid_from: str
    legal_name: str = ""
    aliases: tuple[str, ...] = ()
    identifiers: tuple[FirmIdentifier, ...] = ()
    domains: tuple[str, ...] = ()
    headquarters: str = ""
    jurisdiction: str = ""
    sector: str = ""
    industry: str = ""
    technology_focus: tuple[str, ...] = ()
    relationships: tuple[FirmRelationship, ...] = ()
    source_hints: tuple[SourceDiscoveryHint, ...] = ()
    notes: str = ""
    status: FirmStatus = FirmStatus.DRAFT
    valid_through: str | None = None


@dataclass(frozen=True)
class FirmRevision:
    """One immutable historical description of a stable target-firm identity."""

    firm_id: str
    revision_id: str
    revision_number: int
    canonical_name: str
    legal_name: str
    aliases: tuple[str, ...]
    identifiers: tuple[FirmIdentifier, ...]
    domains: tuple[str, ...]
    headquarters: str
    jurisdiction: str
    sector: str
    industry: str
    technology_focus: tuple[str, ...]
    relationships: tuple[FirmRelationship, ...]
    source_hints: tuple[SourceDiscoveryHint, ...]
    notes: str
    status: FirmStatus
    valid_from: str
    valid_through: str | None
    created_at: str
    updated_at: str
    supersedes_revision_id: str | None


class FirmCatalog(Protocol):
    """Persistence-independent authority used by programs and the admin console."""

    def create(self, draft: FirmDraft) -> FirmRevision:
        """Create the first revision of a stable firm identity."""

    def validate(self, draft: FirmDraft, current_firm_id: str | None = None) -> None:
        """Validate intent and cross-catalog recognition conflicts without publishing."""

    def revise(
        self, firm_id: str, draft: FirmDraft, expected_revision_id: str
    ) -> FirmRevision:
        """Append a revision if the caller still targets the current revision."""

    def get(self, firm_id: str, revision_id: str | None = None) -> FirmRevision:
        """Return a current or named historical firm revision."""

    def history(self, firm_id: str) -> tuple[FirmRevision, ...]:
        """Return immutable history in ascending revision order."""

    def lookup(
        self,
        query: str = "",
        status: FirmStatus | None = None,
        sector: str | None = None,
        industry: str | None = None,
    ) -> tuple[FirmRevision, ...]:
        """Search current firm records through public recognition metadata."""
