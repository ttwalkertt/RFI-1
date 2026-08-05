"""Provider-neutral contracts for repository acquisition semantics."""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from datetime import date
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


class IntervalCoverage(StrEnum):
    """Observable coverage of one requested closed-open date interval."""

    COMPLETE = "complete"
    INCOMPLETE = "incomplete"
    INDETERMINATE = "indeterminate"


class TranscriptSelectionMode(StrEnum):
    """Bounded selector vocabulary for one transcript acquisition attempt."""

    LATEST = "latest"
    FIRST_IN_DATE_RANGE = "first_in_date_range"


@dataclass(frozen=True)
class TranscriptAcquisitionSelection:
    """Immutable rules deciding which validated transcript qualifies."""

    mode: TranscriptSelectionMode = TranscriptSelectionMode.LATEST
    start_date: date | None = None
    end_date: date | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.mode, TranscriptSelectionMode):
            raise ContractError("transcript selection mode is invalid")
        if self.mode == TranscriptSelectionMode.LATEST:
            if self.start_date is not None or self.end_date is not None:
                raise ContractError("latest transcript selection cannot include a date range")
            return
        if not isinstance(self.start_date, date) or not isinstance(self.end_date, date):
            raise ContractError("first_in_date_range requires date boundaries")
        if self.start_date > self.end_date:
            raise ContractError("transcript selection start_date must not follow end_date")

    @classmethod
    def latest(cls) -> TranscriptAcquisitionSelection:
        return cls()

    @classmethod
    def first_in_date_range(
        cls, start_date: date, end_date: date
    ) -> TranscriptAcquisitionSelection:
        return cls(TranscriptSelectionMode.FIRST_IN_DATE_RANGE, start_date, end_date)

    def contains(self, event_date: date) -> bool:
        """Qualify only normalized validated dates, with inclusive boundaries."""
        if self.mode == TranscriptSelectionMode.LATEST:
            return True
        assert self.start_date is not None and self.end_date is not None
        return self.start_date <= event_date <= self.end_date

    def to_dict(self) -> dict[str, JsonValue]:
        return {
            "mode": self.mode.value,
            "start_date": self.start_date.isoformat() if self.start_date else None,
            "end_date": self.end_date.isoformat() if self.end_date else None,
        }


@dataclass(frozen=True)
class TranscriptAcquisitionTarget:
    """Immutable transcript identity and selection contract shared by all trials."""

    firm_id: str
    canonical_artifact_id: str = "earnings_transcript"
    selection: TranscriptAcquisitionSelection = field(
        default_factory=TranscriptAcquisitionSelection.latest
    )

    def __post_init__(self) -> None:
        require_identifier(self.firm_id, "transcript acquisition target firm_id")
        require_identifier(
            self.canonical_artifact_id,
            "transcript acquisition target canonical_artifact_id",
        )
        if self.canonical_artifact_id != "earnings_transcript":
            raise ContractError("transcript acquisition target has the wrong artifact type")
        if not isinstance(self.selection, TranscriptAcquisitionSelection):
            raise ContractError("transcript acquisition target selection is invalid")

    def to_dict(self) -> dict[str, JsonValue]:
        return {
            "firm_id": self.firm_id,
            "canonical_artifact_id": self.canonical_artifact_id,
            "selection": self.selection.to_dict(),
        }


@dataclass(frozen=True)
class TranscriptSeed:
    """Provider-neutral seed selected and ordered only by the orchestrator."""

    provider: str
    kind: str
    value: str
    origin: str

    def __post_init__(self) -> None:
        require_identifier(self.provider, "transcript seed provider")
        require_identifier(self.kind, "transcript seed kind")
        require_identifier(self.origin, "transcript seed origin")
        if self.origin not in {"configured", "learned", "operator_supplied"}:
            raise ContractError("transcript seed origin is unknown")
        if not self.value.strip():
            raise ContractError("transcript seed value must not be blank")


@dataclass(frozen=True)
class TranscriptTurnObservation:
    """Optional provider observation; labels are not canonical identities."""

    ordinal: int
    speaker_label: str
    role_label: str | None
    section_label: str | None
    paragraphs: tuple[str, ...]

    def __post_init__(self) -> None:
        if self.ordinal < 1 or not self.speaker_label.strip() or not self.paragraphs:
            raise ContractError("transcript turn observation is malformed")
        if any(not paragraph.strip() for paragraph in self.paragraphs):
            raise ContractError("transcript turn paragraphs must not be blank")

    def to_dict(self) -> dict[str, JsonValue]:
        return {
            "ordinal": self.ordinal,
            "speaker_label": self.speaker_label,
            "role_label": self.role_label,
            "section_label": self.section_label,
            "paragraphs": list(self.paragraphs),
        }


@dataclass(frozen=True)
class RelatedArtifactObservation:
    """Typed relationship explicitly observed on a provider transcript page."""

    artifact_kind: str
    observed_url: str
    relationship_kind: str
    source_provenance: str

    def __post_init__(self) -> None:
        require_identifier(self.artifact_kind, "related artifact kind")
        require_identifier(self.relationship_kind, "related artifact relationship")
        if not self.observed_url.strip() or not self.source_provenance.strip():
            raise ContractError("related artifact observation is malformed")

    def to_dict(self) -> dict[str, JsonValue]:
        return asdict(self)


@dataclass(frozen=True)
class TranscriptLearningFeedback:
    """Bounded provider advice; only the orchestrator may make it durable."""

    kind: str
    provider: str
    seed_kind: str
    value: str
    reusable: bool = True

    def __post_init__(self) -> None:
        require_identifier(self.kind, "learning feedback kind")
        require_identifier(self.provider, "learning feedback provider")
        require_identifier(self.seed_kind, "learning feedback seed kind")
        if not self.value.strip():
            raise ContractError("learning feedback value must not be blank")

    def to_dict(self) -> dict[str, JsonValue]:
        return asdict(self)


@dataclass(frozen=True)
class IntervalAcquisitionRequest:
    """Request artifacts for one firm and type in ``[start_date, end_date)``."""

    firm_id: str
    artifact_type: str
    start_date: date
    end_date: date

    def __post_init__(self) -> None:
        require_identifier(self.firm_id, "firm_id")
        require_identifier(self.artifact_type, "artifact_type")
        if not isinstance(self.start_date, date) or not isinstance(self.end_date, date):
            raise ContractError("interval boundaries must be dates")
        if self.start_date > self.end_date:
            raise ContractError("start_date must not be after end_date")

    def contains(self, value: date) -> bool:
        """Return whether a date lies inside the closed-open interval."""
        return self.start_date <= value < self.end_date

    def to_dict(self) -> dict[str, str]:
        return {
            "firm_id": self.firm_id,
            "artifact_type": self.artifact_type,
            "start_date": self.start_date.isoformat(),
            "end_date": self.end_date.isoformat(),
        }


@dataclass(frozen=True)
class IntervalArtifactEnvelope:
    """One success expressed through the repository's existing ingress contract."""

    candidate: CandidateDocument
    artifact_date: date
    retrieval: RetrievalResult

    def __post_init__(self) -> None:
        if not isinstance(self.artifact_date, date):
            raise ContractError("artifact_date must be a date")

    @property
    def source_artifact_id(self) -> str:
        """Return the existing acquisition candidate identity for result correlation."""
        return self.candidate.candidate_id


@dataclass(frozen=True)
class IntervalAcquisitionFailure:
    """One explicit acquisition failure observed during an invocation."""

    code: str
    message: str
    retryable: bool
    source_artifact_id: str | None = None
    details: dict[str, JsonValue] = field(default_factory=dict)

    def __post_init__(self) -> None:
        require_identifier(self.code, "failure code")
        if not self.message.strip():
            raise ContractError("failure message must not be blank")
        if self.source_artifact_id is not None and not self.source_artifact_id.strip():
            raise ContractError("failure source_artifact_id must not be blank")
        validate_json(self.details, "failure details")

    def to_dict(self) -> dict[str, JsonValue]:
        return {
            "code": self.code,
            "message": self.message,
            "retryable": self.retryable,
            "source_artifact_id": self.source_artifact_id,
            "details": self.details,
        }


@dataclass(frozen=True)
class IntervalAcquisitionResult:
    """Order-independent successes, failures, and truthful interval coverage."""

    artifacts: tuple[IntervalArtifactEnvelope, ...] = ()
    failures: tuple[IntervalAcquisitionFailure, ...] = ()
    coverage: IntervalCoverage = IntervalCoverage.INDETERMINATE

    def __post_init__(self) -> None:
        if self.coverage == IntervalCoverage.COMPLETE and self.failures:
            raise ContractError("complete coverage cannot include acquisition failures")
        source_ids = [item.source_artifact_id for item in self.artifacts]
        if len(set(source_ids)) != len(source_ids):
            raise ContractError("successful source artifact identities must not repeat")


@dataclass(frozen=True)
class IntervalArtifactReceipt:
    """Repository-assigned identities for one successfully persisted envelope."""

    source_artifact_id: str
    document_id: str
    artifact_id: str
    artifact_created: bool


@dataclass(frozen=True)
class IntervalOutcomeReceipt:
    """Durable receipt for one application-requested interval outcome."""

    outcome_id: str
    coverage: IntervalCoverage
    artifacts: tuple[IntervalArtifactReceipt, ...]
    failure_count: int
    idempotent: bool


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
