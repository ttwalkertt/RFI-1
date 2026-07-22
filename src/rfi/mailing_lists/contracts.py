"""Repository-owned contracts for bounded development-mailing-list evidence."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Protocol
from urllib.parse import urlsplit, urlunsplit

_ARCHIVE_ID = re.compile(r"[a-z0-9][a-z0-9._+-]{0,79}")


class MailingListError(RuntimeError):
    """Sanitized mailing-list acquisition or query failure."""

    def __init__(self, code: str, message: str, *, retryable: bool = False) -> None:
        super().__init__(message)
        self.code = code
        self.retryable = retryable


def normalize_lore_archive(value: str) -> tuple[str, str]:
    """Return the supported archive identity and canonical Lore URL."""
    try:
        parsed = urlsplit(value.strip())
    except ValueError as error:
        raise MailingListError("malformed_lore_url", "Lore archive URL is malformed") from error
    if parsed.scheme != "https" or parsed.hostname != "lore.kernel.org":
        raise MailingListError(
            "unsupported_lore_host", "Use an HTTPS mailing-list archive on lore.kernel.org"
        )
    if parsed.username or parsed.password or parsed.port or parsed.query or parsed.fragment:
        raise MailingListError(
            "malformed_lore_url",
            "Lore archive URL must not contain credentials, port, query, or fragment",
        )
    parts = tuple(item for item in parsed.path.split("/") if item)
    if len(parts) != 1 or not _ARCHIVE_ID.fullmatch(parts[0]):
        raise MailingListError(
            "unsupported_archive_shape",
            "Use a Lore mailing-list archive URL such as https://lore.kernel.org/linux-block/",
        )
    archive_id = parts[0]
    return archive_id, urlunsplit(("https", "lore.kernel.org", f"/{archive_id}/", "", ""))


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


class AcquisitionRunStatus(StrEnum):
    SUCCEEDED = "succeeded"
    PARTIAL = "partial"
    RETRYABLE_FAILURE = "retryable_failure"
    TERMINAL_FAILURE = "terminal_failure"


@dataclass(frozen=True)
class LoreTransportPolicy:
    """Durable per-source network policy for the bounded Lore adapter."""

    user_agent: str = "RFI-1 bounded-mailing-list/2"
    minimum_request_interval_seconds: float = 1.0
    maximum_concurrency: int = 1
    timeout_seconds: float = 20.0
    maximum_response_bytes: int = 5_000_000
    maximum_attempts_per_request: int = 3
    backoff_initial_seconds: float = 1.0
    backoff_maximum_seconds: float = 30.0

    def __post_init__(self) -> None:
        if not self.user_agent.strip() or len(self.user_agent) > 200:
            raise MailingListError("invalid_source", "Lore User-Agent must be 1-200 characters")
        if not 0.1 <= self.minimum_request_interval_seconds <= 60:
            raise MailingListError(
                "invalid_source", "Lore request interval must be between 0.1 and 60 seconds"
            )
        if not 1 <= self.maximum_concurrency <= 4:
            raise MailingListError("invalid_source", "Lore concurrency must be between 1 and 4")
        if not 1 <= self.timeout_seconds <= 120:
            raise MailingListError(
                "invalid_source", "Lore timeout must be between 1 and 120 seconds"
            )
        if not 1_024 <= self.maximum_response_bytes <= 50_000_000:
            raise MailingListError(
                "invalid_source", "Lore response bound must be between 1 KiB and 50 MB"
            )
        if not 1 <= self.maximum_attempts_per_request <= 5:
            raise MailingListError("invalid_source", "Lore attempts must be between 1 and 5")
        if not 0 <= self.backoff_initial_seconds <= 60:
            raise MailingListError("invalid_source", "Lore initial backoff is outside bounds")
        if not self.backoff_initial_seconds <= self.backoff_maximum_seconds <= 300:
            raise MailingListError("invalid_source", "Lore maximum backoff is outside bounds")


@dataclass(frozen=True)
class MailingListSource:
    source_id: str
    list_id: str
    display_name: str
    archive_base_url: str
    provider: str = "lore-public-inbox"
    transport: LoreTransportPolicy = field(default_factory=LoreTransportPolicy)


@dataclass(frozen=True)
class SelectionCriteria:
    """Explicit bounded seed selection. There is deliberately no select-all form."""

    message_ids: tuple[str, ...] = ()
    query: str | None = None
    date_from: str | None = None
    date_through: str | None = None
    topic_terms: tuple[str, ...] = ()
    subject_terms: tuple[str, ...] = ()
    participant_terms: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not any((self.message_ids, self.query, self.date_from, self.date_through,
                    self.topic_terms, self.subject_terms, self.participant_terms)):
            raise MailingListError(
                "unbounded_selection", "mailing-list acquisition requires explicit bounds"
            )
        values = (
            self.message_ids + self.topic_terms + self.subject_terms + self.participant_terms
        )
        if any(not value.strip() for value in values):
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
    run_status: AcquisitionRunStatus = AcquisitionRunStatus.SUCCEEDED
    error_code: str | None = None
    retryable: bool = False


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
class AcquisitionMessage:
    """Operator-facing projection of one message retained by one acquisition run."""

    summary: MessageSummary
    inclusion_reason: str
    direct_match: bool
    context_only: bool
    source_link: str
    discussion_id: str | None


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
