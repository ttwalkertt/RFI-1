"""Stable contracts for durable consulting investigations and execution history."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Protocol

from rfi.intelligence import ExecutionRecord, InformationNeed, IntelligenceBudget


class WorkspaceError(RuntimeError):
    """Raised when durable workspace state cannot be trusted or changed safely."""


class InvestigationStatus(StrEnum):
    """Operator-owned lifecycle state for one consulting problem."""

    OPEN = "open"
    PAUSED = "paused"
    CLOSED = "closed"


class AnnotationKind(StrEnum):
    """Kinds of operator-authored material, separate from repository authorities."""

    OBSERVATION = "observation"
    CORRECTION = "correction"
    FOLLOW_UP = "follow-up"
    INTERPRETATION = "interpretation"
    CONCLUSION = "conclusion"


class ExecutionOutcome(StrEnum):
    """Workspace-level outcome, including failures before intelligence returns."""

    STARTED = "started"
    COMPLETED = "completed"
    FAILED = "failed"
    INTERRUPTED = "interrupted"


@dataclass(frozen=True)
class OperationalMetrics:
    """Provider-neutral timings, volume, usage, and cost captured when available."""

    execution_ms: int
    planning_ms: int | None = None
    retrieval_ms: int | None = None
    model_ms: int | None = None
    evidence_bytes: int = 0
    retrieval_count: int = 0
    iteration_count: int = 0
    model_calls: int | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    estimated_cost: float | None = None
    cost_currency: str | None = None


@dataclass(frozen=True)
class JournalEvent:
    """One immutable, hash-chained workspace fact."""

    sequence: int
    event_id: str
    timestamp: str
    event_type: str
    investigation_id: str | None
    payload: dict[str, Any]
    previous_hash: str | None
    event_hash: str


@dataclass(frozen=True)
class InvestigationSummary:
    """Current projection derived exclusively from append-only events."""

    investigation_id: str
    title: str
    purpose: str
    customer: str | None
    engagement: str | None
    status: InvestigationStatus
    created_at: str
    updated_at: str
    execution_ids: tuple[str, ...] = field(default_factory=tuple)
    annotation_ids: tuple[str, ...] = field(default_factory=tuple)
    export_ids: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class ExecutionComparison:
    """Semantic comparison of two immutable execution snapshots."""

    first_execution_id: str
    second_execution_id: str
    identical: bool
    question_changed: bool
    configuration_changed: bool
    plan_changed: bool
    retrieval_changed: bool
    evidence_changed: bool
    reasoning_changed: bool
    conclusions_changed: bool
    status_changed: bool
    metric_deltas: dict[str, float | int | None]
    details: dict[str, Any]


@dataclass(frozen=True)
class IntegrityReport:
    """Fail-closed verification result for workspace or backup state."""

    valid: bool
    events_checked: int
    files_checked: int
    open_executions: tuple[str, ...]
    failures: tuple[str, ...]


class IntelligenceExecutor(Protocol):
    """Public downstream port; workspace never learns subsystem persistence."""

    def execute(
        self,
        need: InformationNeed,
        budget: IntelligenceBudget | None = None,
    ) -> ExecutionRecord:
        """Return one public TASK-007 execution record."""
