"""Strongly typed contracts for the concrete Pull Workflow business capability."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from rfi.acquisition.contracts import JsonValue


class PullError(RuntimeError):
    """Raised when a pull request or durable run identity is invalid."""


class PullStage(StrEnum):
    """Ordered conceptual stages of every Pull Workflow execution."""

    RECEIVED = "receive_request"
    FIRMS_RESOLVED = "resolve_firms"
    REVISIONS_SNAPSHOTTED = "snapshot_source_profile_revisions"
    ARTIFACTS_EXPANDED = "expand_enabled_artifacts"
    ATTEMPTABILITY_DETERMINED = "determine_attemptability"
    RETRIEVAL_EXECUTED = "execute_retrieval"
    ARTIFACTS_INGESTED = "ingest_successful_artifacts"
    RESULTS_RECORDED = "record_results"
    SUMMARIZED = "summarize_execution"


class PullStatus(StrEnum):
    """Lifecycle and terminal states for a run or firm."""

    RUNNING = "running"
    COMPLETED = "completed"
    PARTIAL = "partial"
    FAILED = "failed"


class ArtifactOutcome(StrEnum):
    """Terminal operator-facing result for one enabled configured artifact."""

    SUCCESS = "success"
    DUPLICATE = "duplicate"
    NO_CHANGE = "no_change"
    SKIPPED = "skipped"
    CONFIGURATION_PROBLEM = "configuration_problem"
    RETRIEVAL_FAILURE = "retrieval_failure"


@dataclass(frozen=True)
class PullRequest:
    """Select explicit firms or all firms with a saved source profile."""

    firm_ids: tuple[str, ...] = ()
    all_configured: bool = False

    def __post_init__(self) -> None:
        if self.all_configured == bool(self.firm_ids):
            raise PullError("select one or more firms or --all-configured, but not both")
        if any(not value for value in self.firm_ids):
            raise PullError("firm identifiers must not be blank")
        if len(set(self.firm_ids)) != len(self.firm_ids):
            raise PullError("firm identifiers must not be repeated")


@dataclass(frozen=True)
class ConfiguredFirm:
    """Current pull readiness projected for the operator console."""

    firm_id: str
    canonical_name: str
    source_profile_revision_id: str
    source_profile_revision_number: int
    enabled_artifacts: int
    runnable_artifacts: int
    incomplete_artifacts: int


@dataclass(frozen=True)
class RetrievalAttemptResult:
    """One prioritized retrieval candidate execution within an artifact result."""

    mode: str
    priority: int
    adapter_id: str
    acquisition_run_id: str | None
    status: str
    diagnostic: str
    artifact_ids: tuple[str, ...] = ()
    details: dict[str, JsonValue] | None = None


@dataclass(frozen=True)
class ArtifactPullResult:
    """Durable result for one enabled artifact in a snapshotted profile revision."""

    firm_id: str
    artifact_id: str
    label: str
    outcome: ArtifactOutcome
    diagnostic: str
    attempts: tuple[RetrievalAttemptResult, ...] = ()


@dataclass(frozen=True)
class FirmPullResult:
    """Aggregated result for one independently executed firm."""

    firm_id: str
    canonical_name: str
    source_profile_revision_id: str | None
    source_profile_revision_number: int
    status: PullStatus
    artifacts: tuple[ArtifactPullResult, ...]


@dataclass(frozen=True)
class PullSummary:
    """Terminal counts derived from the actual artifact results."""

    firms: int
    artifacts: int
    success: int
    duplicate: int
    no_change: int
    skipped: int
    configuration_problem: int
    retrieval_failure: int


@dataclass(frozen=True)
class PullRunResult:
    """Complete typed result returned by CLI, API, and GUI workflow initiation."""

    run_id: str
    status: PullStatus
    requested_at: str
    completed_at: str
    completed_stages: tuple[PullStage, ...]
    firms: tuple[FirmPullResult, ...]
    summary: PullSummary
    diagnostics: tuple[str, ...] = ()
