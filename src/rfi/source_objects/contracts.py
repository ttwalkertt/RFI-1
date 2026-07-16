"""Stable contracts exported by the source-object subsystem."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Protocol


class SourceObjectError(RuntimeError):
    """Raised when source-object construction or integrity is invalid."""


class ParseStatus(StrEnum):
    """Visible parser outcome for one immutable artifact."""

    COMPLETE = "complete"
    INCOMPLETE = "incomplete"
    UNSUPPORTED = "unsupported"
    FAILED = "failed"


@dataclass(frozen=True)
class SourceInput:
    """Evidence supplied to construction without exposing acquisition storage layout."""

    document_id: str
    artifact_id: str
    content: bytes


@dataclass(frozen=True)
class SourceObject:
    """One exact, structural location within an immutable artifact."""

    source_object_id: str
    document_id: str
    artifact_id: str
    kind: str
    role: str
    ordinal: int
    byte_start: int
    byte_end: int
    content_sha256: str
    parent_id: str | None = None
    attributes: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class SourceRebuildResult:
    """Deterministic inventory and digest from an atomic source rebuild."""

    artifacts: int
    objects: int
    incomplete: int
    unsupported: int
    catalog_sha256: str


class SourceObjectReader(Protocol):
    """Only contract the derived-knowledge subsystem may consume."""

    def inventory(self) -> list[SourceObject]:
        """Return all current source objects in stable identity order."""

    def get(self, source_object_id: str) -> SourceObject:
        """Return one current source object or fail closed."""

    def by_document(self, document_id: str) -> list[SourceObject]:
        """Return current source objects for one repository document."""

    def field_value(self, source_object_id: str) -> str:
        """Return the normalized value retained for a structural field object."""
