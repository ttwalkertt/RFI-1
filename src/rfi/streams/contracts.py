"""Typed contracts for revisioned repository artifact streams."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol


class StreamError(RuntimeError):
    """Actionable stream configuration, execution, or query failure."""

    def __init__(self, code: str, message: str, path: str | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.path = path


@dataclass(frozen=True)
class AttributeCapability:
    attribute_id: str
    value_type: str
    operators: tuple[str, ...]
    label: str


@dataclass(frozen=True)
class SchemaCapability:
    schema_id: str
    label: str
    fields: dict[str, tuple[str, ...]]
    attributes: tuple[AttributeCapability, ...]
    expansions: tuple[str, ...]


@dataclass(frozen=True)
class ArtifactProjection:
    artifact_id: str
    document_id: str
    schema_id: str
    source_id: str
    effective_at: str | None
    title: str
    searchable_text: str
    authors: tuple[str, ...] = ()
    attributes: dict[str, str | tuple[str, ...]] = field(default_factory=dict)
    context_id: str | None = None
    context_depth: int | None = None
    completeness: str | None = None


@dataclass(frozen=True)
class StreamDraft:
    stream_id: str
    name: str
    description: str
    enabled: bool
    input_kind: str
    input_ids: tuple[str, ...]
    schema_id: str
    selection: dict[str, Any]
    expansion: dict[str, Any]
    bounds: dict[str, int]
    metadata: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class ExpandedProjection:
    projection: ArtifactProjection
    inclusion_reason: str
    lineage: tuple[dict[str, Any], ...]


class ArtifactProjectionProvider(Protocol):
    schema_id: str

    def refresh(self, repository: Any) -> int: ...


class ContextExpansionHandler(Protocol):
    schema_id: str
    strategy: str

    def validate(self, expansion: dict[str, Any]) -> tuple[dict[str, str], ...]: ...

    def expand(
        self,
        repository: Any,
        draft: StreamDraft,
        direct: tuple[ArtifactProjection, ...],
        upstream: dict[str, list[dict[str, Any]]],
    ) -> tuple[ExpandedProjection, ...]: ...


@dataclass(frozen=True)
class RegisteredArtifactSchema:
    capability: SchemaCapability
    projection_provider: ArtifactProjectionProvider
    expansion_handlers: tuple[ContextExpansionHandler, ...]


@dataclass(frozen=True)
class StreamRevision:
    stream_id: str
    revision_id: str
    revision_number: int
    predecessor_id: str | None
    created_at: str
    draft: StreamDraft


@dataclass(frozen=True)
class StreamSummary:
    stream_id: str
    name: str
    enabled: bool
    input_kind: str
    schema_id: str
    revision_id: str
    revision_number: int
    upstream_ids: tuple[str, ...]
    consumer_ids: tuple[str, ...]
    latest_run_id: str | None
    latest_run_status: str | None
    membership_count: int


@dataclass(frozen=True)
class StreamRun:
    run_id: str
    stream_id: str
    revision_id: str
    requested_at: str
    completed_at: str | None
    status: str
    input_fingerprint: str
    direct_count: int
    context_count: int
    error_code: str | None = None
    idempotent: bool = False


@dataclass(frozen=True)
class StreamMembership:
    membership_id: str
    run_id: str
    stream_id: str
    revision_id: str
    artifact_id: str
    document_id: str
    inclusion_kind: str
    inclusion_reason: str
    expansion_strategy: str
    completeness: str | None
    ordinal: int
    projection: ArtifactProjection
    lineage: tuple[dict[str, Any], ...] = ()


@dataclass(frozen=True)
class StreamPreview:
    stream_id: str
    candidate_count: int
    direct_count: int
    context_count: int
    truncated: bool
    items: tuple[dict[str, Any], ...]


@dataclass(frozen=True)
class ValidationResult:
    valid: bool
    errors: tuple[dict[str, str], ...]
    topological_order: tuple[str, ...]


@dataclass(frozen=True)
class StreamDefinitionReview:
    """A normalized, non-persistent definition review shared by browser and CLI."""

    valid: bool
    errors: tuple[dict[str, str], ...]
    warnings: tuple[dict[str, str], ...]
    draft: StreamDraft | None
    canonical_yaml: str | None
    semantic_fingerprint: str | None
    differences: tuple[dict[str, Any], ...]
    existing_revision_id: str | None
    import_mode: str


@dataclass(frozen=True)
class StreamImportResult:
    """Revision-safe outcome of one explicit YAML import."""

    outcome: str
    revision: StreamRevision
    semantic_fingerprint: str
