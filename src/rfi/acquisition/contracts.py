"""Provider-neutral contracts for repository acquisition semantics."""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from enum import StrEnum
from typing import Any

JsonValue = None | bool | int | float | str | list["JsonValue"] | dict[str, "JsonValue"]

_IDENTIFIER = re.compile(r"^[a-z][a-z0-9]*(?:[._-][a-z0-9]+)*$")
_MEDIA_TYPE = re.compile(r"^[a-z0-9!#$&^_.+-]+/[a-z0-9!#$&^_.+-]+$")


class ContractError(ValueError):
    """Raised when a repository contract is malformed or ambiguous."""


class ConflictError(RuntimeError):
    """Raised when an immutable identity is reused with different semantics."""


class IntegrityError(RuntimeError):
    """Raised when authoritative repository state is missing or corrupt."""


class PartialFailure(RuntimeError):
    """Raised by an explicit failure point after prior effects may be durable."""


class RetrievalOutcome(StrEnum):
    """Material outcomes retained in acquisition history."""

    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"
    DUPLICATE = "duplicate"


class FailurePoint(StrEnum):
    """Deterministic fault locations used to prove transaction ordering."""

    BEFORE_ARTIFACT = "before_artifact"
    AFTER_ARTIFACT = "after_artifact"
    BEFORE_INDEX = "before_index"
    BEFORE_CHECKPOINT = "before_checkpoint"
    DURING_REPLAY = "during_replay"


def require_identifier(value: str, kind: str) -> None:
    """Validate a stable repository-owned identifier."""
    if not _IDENTIFIER.fullmatch(value):
        raise ContractError(
            f"{kind} must start with a lowercase letter and contain lowercase segments: {value!r}"
        )


def validate_json(value: JsonValue, location: str = "value") -> None:
    """Reject non-portable or ambiguous configuration values."""
    if value is None or isinstance(value, (bool, int, str)):
        return
    if isinstance(value, float):
        if value != value or value in {float("inf"), float("-inf")}:
            raise ContractError(f"{location} contains a non-finite number")
        return
    if isinstance(value, list):
        for index, item in enumerate(value):
            validate_json(item, f"{location}[{index}]")
        return
    if isinstance(value, dict):
        for key, item in value.items():
            if not isinstance(key, str) or not key:
                raise ContractError(f"{location} contains an invalid object key")
            validate_json(item, f"{location}.{key}")
        return
    raise ContractError(f"{location} is not deterministic JSON data")


@dataclass(frozen=True)
class SourceProfile:
    """Governed source identity and deterministic, provider-neutral policy."""

    source_id: str
    name: str
    enabled: bool
    mechanism: str
    configuration: dict[str, JsonValue] = field(default_factory=dict)
    policy: dict[str, JsonValue] = field(default_factory=dict)

    def __post_init__(self) -> None:
        require_identifier(self.source_id, "source_id")
        if not self.name.strip():
            raise ContractError("source name must not be blank")
        require_identifier(self.mechanism, "mechanism")
        validate_json(self.configuration, "configuration")
        validate_json(self.policy, "policy")

    def to_dict(self) -> dict[str, Any]:
        """Return the canonical JSON-compatible representation."""
        return asdict(self)


@dataclass(frozen=True)
class DiscoveryProvenance:
    """Provider and discovery attributes that do not define repository identity."""

    discovered_at: str
    discovery_method: str
    provider_identifiers: dict[str, str] = field(default_factory=dict)
    locations: tuple[str, ...] = ()
    metadata: dict[str, JsonValue] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.discovered_at.strip():
            raise ContractError("discovered_at must not be blank")
        require_identifier(self.discovery_method, "discovery_method")
        if any(not key or not value for key, value in self.provider_identifiers.items()):
            raise ContractError("provider identifiers require non-empty keys and values")
        if any(not location for location in self.locations):
            raise ContractError("discovery locations must not be blank")
        validate_json(self.metadata, "discovery metadata")

    def to_dict(self) -> dict[str, Any]:
        """Return the canonical JSON-compatible representation."""
        value = asdict(self)
        value["locations"] = list(self.locations)
        return value


@dataclass(frozen=True)
class CandidateDocument:
    """Deterministic candidate linked to stable repository source and document IDs."""

    candidate_id: str
    source_id: str
    document_id: str
    provenance: DiscoveryProvenance

    def __post_init__(self) -> None:
        require_identifier(self.candidate_id, "candidate_id")
        require_identifier(self.source_id, "source_id")
        require_identifier(self.document_id, "document_id")

    def to_dict(self) -> dict[str, Any]:
        """Return the canonical JSON-compatible representation."""
        return {
            "candidate_id": self.candidate_id,
            "source_id": self.source_id,
            "document_id": self.document_id,
            "provenance": self.provenance.to_dict(),
        }


@dataclass(frozen=True)
class RetrievalResult:
    """Bytes and retrieval evidence supplied by a future external adapter."""

    content: bytes
    media_type: str
    retrieved_at: str
    mechanism: str
    provider_identifiers: dict[str, str] = field(default_factory=dict)
    diagnostics: dict[str, JsonValue] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.content, bytes):
            raise ContractError("retrieval content must be exact bytes")
        if not _MEDIA_TYPE.fullmatch(self.media_type.lower()):
            raise ContractError(f"invalid media type: {self.media_type!r}")
        if not self.retrieved_at.strip():
            raise ContractError("retrieved_at must not be blank")
        require_identifier(self.mechanism, "mechanism")
        if any(not key or not value for key, value in self.provider_identifiers.items()):
            raise ContractError("provider identifiers require non-empty keys and values")
        validate_json(self.diagnostics, "retrieval diagnostics")


@dataclass(frozen=True, order=True)
class Checkpoint:
    """Explicit source-scoped progress position with caller-defined opaque cursor."""

    position: int
    cursor: str

    def __post_init__(self) -> None:
        if self.position < 0:
            raise ContractError("checkpoint position must be non-negative")
        if not self.cursor:
            raise ContractError("checkpoint cursor must not be blank")

    def to_dict(self) -> dict[str, Any]:
        """Return the canonical JSON-compatible representation."""
        return asdict(self)


@dataclass(frozen=True)
class AcquisitionReceipt:
    """Repository result after all requested durable effects succeeded."""

    attempt_id: str
    observation_id: str
    artifact_id: str
    document_id: str
    checkpoint: Checkpoint | None
    idempotent: bool
    artifact_created: bool


@dataclass(frozen=True)
class ReplayResult:
    """Counts and digests from rebuilding disposable acquisition views."""

    documents: int
    checkpoints: int
    attempts: int
    index_sha256: str
    checkpoint_sha256: str
