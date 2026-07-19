"""Repository-owned contracts for bounded development-mailing-list evidence."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Protocol


class MailingListError(RuntimeError):
    """Sanitized mailing-list acquisition or query failure."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


class InclusionReason(StrEnum):
    SEED_MATCH = "seed_match"
    EXPLICIT_REQUEST = "explicit_request"
    ANCESTOR = "ancestor_context"
    DESCENDANT = "descendant_context"
    RELATIONSHIP = "relationship_context"


class ConnectivityState(StrEnum):
    CONNECTED = "connected"
    TRUNCATED = "truncated"
    INCOMPLETE = "incomplete"
    QUARANTINED = "quarantined"


@dataclass(frozen=True)
class MailingListSource:
    source_id: str
    list_id: str
    display_name: str
    archive_base_url: str


@dataclass(frozen=True)
class SelectionCriteria:
    """Explicit bounded seed selection. There is deliberately no select-all form."""

    message_ids: tuple[str, ...] = ()
    query: str | None = None
    date_from: str | None = None
    date_through: str | None = None
    topic_terms: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not any((self.message_ids, self.query, self.date_from, self.date_through,
                    self.topic_terms)):
            raise MailingListError(
                "unbounded_selection", "mailing-list acquisition requires explicit bounds"
            )
        if any(not value.strip() for value in self.message_ids + self.topic_terms):
            raise MailingListError("invalid_selection", "selection values must not be blank")


@dataclass(frozen=True)
class AcquisitionLimits:
    seed_limit: int = 10
    context_limit: int = 100
    descendant_depth: int = 3

    def __post_init__(self) -> None:
        if not 1 <= self.seed_limit <= 100:
            raise MailingListError("invalid_limit", "seed limit must be between 1 and 100")
        if not 1 <= self.context_limit <= 500:
            raise MailingListError("invalid_limit", "context limit must be between 1 and 500")
        if not 0 <= self.descendant_depth <= 20:
            raise MailingListError("invalid_limit", "descendant depth must be between 0 and 20")


@dataclass(frozen=True)
class ArchiveMessage:
    raw: bytes
    location: str


class MailingListArchive(Protocol):
    """Bounded archive adapter; persistence is intentionally absent."""

    def discover(
        self, criteria: SelectionCriteria, limit: int
    ) -> tuple[tuple[str, ...], bool]: ...

    def fetch(self, external_message_id: str) -> ArchiveMessage: ...

    def direct_children(
        self, external_message_id: str, limit: int
    ) -> tuple[tuple[str, ...], bool]: ...

    @property
    def descendant_enumeration_complete(self) -> bool: ...


@dataclass(frozen=True)
class AcquisitionPreview:
    source_id: str
    criteria: SelectionCriteria
    limits: AcquisitionLimits
    seed_ids: tuple[str, ...]
    proposed_messages: int
    inclusion_reasons: dict[str, int]
    state: ConnectivityState
    truncated: bool
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True)
class AcquisitionManifest:
    run_id: str
    source_id: str
    requested_at: str
    criteria: SelectionCriteria
    limits: AcquisitionLimits
    seed_ids: tuple[str, ...]
    message_count: int
    relationship_count: int
    discussion_count: int
    inclusion_reasons: dict[str, int]
    state: ConnectivityState
    truncated: bool
    warnings: tuple[str, ...] = ()
    artifact_count_created: int = 0
    idempotent_messages: int = 0


@dataclass(frozen=True)
class ParsedMessage:
    external_message_id: str | None
    subject: str
    normalized_subject: str
    sender: str
    message_date: str | None
    immediate_parent_id: str | None
    references: tuple[str, ...]
    text_content: str
    parse_warnings: tuple[str, ...] = ()


@dataclass(frozen=True)
class DiscussionSummary:
    discussion_id: str
    source_id: str
    list_id: str
    root_message_key: str
    root_subject: str
    message_count: int
    first_message_at: str | None
    last_message_at: str | None
    connectivity_state: ConnectivityState
    descendant_truncated: bool


@dataclass(frozen=True)
class MessageSummary:
    message_key: str
    external_message_id: str | None
    document_id: str
    artifact_id: str
    subject: str
    sender: str
    message_date: str | None
    immediate_parent_id: str | None
    connectivity_state: ConnectivityState
    child_count: int
    depth: int | None = None


@dataclass(frozen=True)
class MessageDetail:
    summary: MessageSummary
    source: MailingListSource
    discussion_id: str | None
    stored_root_message_key: str | None
    inclusion_reasons: tuple[str, ...]
    acquisition_run_ids: tuple[str, ...]
    relationship_authority: str | None
    relationship_certainty: str | None
    missing_parent_reference: str | None
    checksum_sha256: str
    media_type: str
    content_size: int
    content_integrity: str
    provenance_locations: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class DiscussionProjection:
    summary: DiscussionSummary
    messages: tuple[MessageSummary, ...]
    result_truncated: bool
