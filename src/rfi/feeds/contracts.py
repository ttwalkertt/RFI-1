"""Typed repository-owned feed registry and polling contracts."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import StrEnum
from typing import Any


class FeedError(RuntimeError):
    """Actionable feed registry, polling, or fulfillment failure."""


class FeedRunOutcome(StrEnum):
    RUNNING = "running"
    COMPLETED = "completed"
    COMPLETED_WITH_UNAVAILABLE = "completed_with_unavailable_entries"
    PARTIAL = "partial"
    FAILED = "failed"
    CANCELED = "canceled"


class TombstoneStatus(StrEnum):
    UNRESOLVED = "unresolved"
    FULFILLED = "fulfilled"
    DISMISSED = "dismissed"


@dataclass(frozen=True)
class FeedDefinition:
    feed_id: str
    revision_id: str
    revision_number: int
    display_name: str
    feed_url: str
    enabled: bool
    notes: str
    firm_ids: tuple[str, ...]
    format: str
    lifecycle_status: str
    created_at: str

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["firm_ids"] = list(self.firm_ids)
        return value


@dataclass(frozen=True)
class FeedEntry:
    entry_key: str
    title: str
    url: str
    published_at: str | None = None
    updated_at: str | None = None
    author: str | None = None
    summary: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ParsedFeed:
    format: str
    title: str
    entries: tuple[FeedEntry, ...]


@dataclass(frozen=True)
class FeedValidationResult:
    valid: bool
    format: str | None
    title: str | None
    entry_count: int
    diagnostic: str


@dataclass(frozen=True)
class FeedPollRequest:
    feed_ids: tuple[str, ...] = ()
    firm_ids: tuple[str, ...] = ()
    trigger: str = "api"
    parent_pull_run_id: str | None = None


@dataclass(frozen=True)
class FeedRunResult:
    run_id: str
    trigger: str
    requested_at: str
    completed_at: str
    outcome: FeedRunOutcome
    selected_feed_ids: tuple[str, ...]
    firm_ids: tuple[str, ...]
    summary: dict[str, int]
    feeds: tuple[dict[str, Any], ...]
    diagnostics: tuple[dict[str, Any], ...] = field(default_factory=tuple)
    parent_pull_run_id: str | None = None
    termination_reason: str = "selected feeds exhausted"

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["outcome"] = self.outcome.value
        value["selected_feed_ids"] = list(self.selected_feed_ids)
        value["firm_ids"] = list(self.firm_ids)
        value["feeds"] = list(self.feeds)
        value["diagnostics"] = list(self.diagnostics)
        return value
