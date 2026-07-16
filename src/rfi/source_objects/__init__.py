"""Structurally addressable source evidence with repository-owned identities."""

from rfi.source_objects.contracts import (
    ParseStatus,
    SourceInput,
    SourceObject,
    SourceObjectError,
    SourceObjectReader,
    SourceRebuildResult,
)
from rfi.source_objects.repository import SourceObjectRepository

__all__ = [
    "ParseStatus",
    "SourceInput",
    "SourceObject",
    "SourceObjectError",
    "SourceObjectReader",
    "SourceObjectRepository",
    "SourceRebuildResult",
]
