"""Deterministic source-adapter orchestration over repository-owned persistence."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from enum import StrEnum
from typing import Any, Callable, Protocol

from rfi.acquisition.contracts import (
    CandidateDocument,
    Checkpoint,
    ConflictError,
    ContractError,
    DiscoveryProvenance,
    IntegrityError,
    JsonValue,
    RetrievalOutcome,
    RetrievalResult,
    SourceProfile,
    require_identifier,
    validate_json,
)
from rfi.acquisition.repository import AcquisitionRepository


class FailureClass(StrEnum):
    """Operator-actionable acquisition failure classifications."""

    TRANSIENT_ADAPTER = "transient_adapter"
    PERMANENT_RETRIEVAL = "permanent_retrieval"
    MALFORMED_ADAPTER = "malformed_adapter"
    POLICY_REJECTION = "policy_rejection"
    REPOSITORY_CONFLICT = "repository_conflict"
    REPOSITORY_INTEGRITY = "repository_integrity"


class RunStatus(StrEnum):
    """Observed terminal state of one source run."""

    COMPLETE = "complete"
    PARTIAL = "partial"
    BLOCKED = "blocked"
    FAILED = "failed"


class EngineFailurePoint(StrEnum):
    """Deterministic orchestration fault used to prove finalization ordering."""

    BEFORE_CHECKPOINT_FINALIZATION = "before_checkpoint_finalization"


class AdapterFailure(RuntimeError):
    """Expected source-boundary failure with stable classification and retry guidance."""

    def __init__(
        self, classification: FailureClass, message: str, retryable: bool
    ) -> None:
        super().__init__(message)
        self.classification = classification
        self.retryable = retryable


@dataclass(frozen=True)
class AdapterCandidate:
    """Provider-neutral discovery item before repository contract conversion."""

    candidate_id: str
    document_id: str
    position: int
    revision: str
    provenance: DiscoveryProvenance
    disposition: str = "acquire"
    disposition_reason: str | None = None

    def __post_init__(self) -> None:
        require_identifier(self.candidate_id, "candidate_id")
        require_identifier(self.document_id, "document_id")
        if self.position < 1:
            raise ContractError("adapter candidate position must be positive")
        require_identifier(self.revision, "revision")
        if self.disposition not in {"acquire", "skip"}:
            raise ContractError("adapter candidate disposition must be acquire or skip")
        if self.disposition == "skip" and not self.disposition_reason:
            raise ContractError("skipped adapter candidate requires a reason")

    def canonical(self) -> dict[str, Any]:
        """Return stable candidate semantics used for ambiguity detection."""
        return {
            "candidate_id": self.candidate_id,
            "document_id": self.document_id,
            "position": self.position,
            "revision": self.revision,
            "provenance": self.provenance.to_dict(),
            "disposition": self.disposition,
            "disposition_reason": self.disposition_reason,
        }


@dataclass(frozen=True)
class DiscoveryPage:
    """One provider page and its in-run continuation token."""

    candidates: tuple[AdapterCandidate, ...]
    next_token: str | None
    diagnostics: dict[str, JsonValue] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.next_token == "":
            raise ContractError("empty provider continuation token is ambiguous")
        validate_json(self.diagnostics, "page diagnostics")


class SourceAdapter(Protocol):
    """Minimum discovery/retrieval boundary; adapters never receive a repository."""

    mechanism: str

    def discover(
        self, profile: SourceProfile, continuation: str | None
    ) -> DiscoveryPage:
        """Return one deterministic page or raise an AdapterFailure."""

    def retrieve(
        self, profile: SourceProfile, candidate: AdapterCandidate
    ) -> RetrievalResult:
        """Return exact bytes and retrieval evidence or raise an AdapterFailure."""


class AdapterRegistry:
    """Explicit inspectable mechanism-to-adapter registration."""

    def __init__(self, adapters: tuple[SourceAdapter, ...] = ()) -> None:
        self._adapters: dict[str, SourceAdapter] = {}
        for adapter in adapters:
            self.register(adapter)

    def register(self, adapter: SourceAdapter) -> None:
        """Register exactly one adapter for a validated mechanism."""
        require_identifier(adapter.mechanism, "adapter mechanism")
        if adapter.mechanism in self._adapters:
            raise ContractError(f"adapter already registered: {adapter.mechanism}")
        self._adapters[adapter.mechanism] = adapter

    def select(self, profile: SourceProfile) -> SourceAdapter:
        """Select and validate the adapter named by the governed profile."""
        if not profile.enabled:
            raise ContractError(f"source is disabled: {profile.source_id}")
        adapter = self._adapters.get(profile.mechanism)
        if adapter is None:
            raise ContractError(f"no adapter registered for mechanism: {profile.mechanism}")
        return adapter

    def registrations(self) -> dict[str, str]:
        """Return deterministic operator-visible registration information."""
        return {
            mechanism: type(adapter).__name__
            for mechanism, adapter in sorted(self._adapters.items())
        }


@dataclass(frozen=True)
class CandidateRunOutcome:
    """Observed durable or non-durable result for one candidate occurrence."""

    candidate_id: str
    document_id: str
    position: int
    revision: str
    outcome: str
    attempt_id: str | None
    durable: bool
    diagnostic: str


@dataclass(frozen=True)
class AcquisitionRunResult:
    """Structured source-run lifecycle derived from actual outcomes."""

    run_id: str
    source_id: str
    mechanism: str
    started_at: str
    completed_at: str
    status: RunStatus
    pages: int
    candidates_discovered: int
    candidates_unique: int
    retrieval_attempts: int
    durable_acquisitions: int
    unchanged: int
    duplicates: int
    skips: int
    failures: int
    checkpoint_before: Checkpoint | None
    checkpoint_after: Checkpoint | None
    provider_continuations: tuple[str, ...]
    outcomes: tuple[CandidateRunOutcome, ...]
    diagnostics: tuple[dict[str, JsonValue], ...]

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-compatible operator representation."""
        value = asdict(self)
        value["status"] = self.status.value
        return value


class AcquisitionEngine:
    """Single-process deterministic acquisition orchestration."""

    def __init__(
        self,
        repository: AcquisitionRepository,
        adapters: AdapterRegistry,
        clock: Callable[[], str],
    ) -> None:
        self._repository = repository
        self._adapters = adapters
        self._clock = clock

    def run_source(
        self,
        source_id: str,
        run_key: str,
        fail_at: EngineFailurePoint | None = None,
    ) -> AcquisitionRunResult:
        """Execute one bounded source run and return only observed outcomes."""
        require_identifier(run_key, "run_key")
        profile = self._load_profile(source_id)
        adapter = self._adapters.select(profile)
        started = self._clock()
        run_id = f"run-{source_id}-{run_key}"
        checkpoint_before = self._checkpoint(source_id)
        continuation: str | None = None
        continuations: list[str] = []
        seen_tokens: set[str] = set()
        seen_candidates: dict[str, dict[str, Any]] = {}
        outcomes: list[CandidateRunOutcome] = []
        diagnostics: list[dict[str, JsonValue]] = []
        pages = 0
        discovered = 0
        retrievals = 0
        durable = 0
        unchanged = 0
        duplicates = 0
        skips = 0
        failures = 0
        last_success: str | None = None
        maximum_position = checkpoint_before.position if checkpoint_before else 0
        previous_page_position = 0
        status = RunStatus.COMPLETE

        while True:
            try:
                page = adapter.discover(profile, continuation)
                self._validate_page(page)
            except AdapterFailure as error:
                failures += 1
                status = RunStatus.PARTIAL if outcomes else self._failure_status(error)
                diagnostics.append(self._failure_diagnostic(error, continuation))
                break
            except (ContractError, TypeError, AttributeError) as error:
                failures += 1
                status = RunStatus.FAILED
                diagnostics.append(
                    self._diagnostic(FailureClass.MALFORMED_ADAPTER, str(error), False)
                )
                break
            pages += 1
            diagnostics.append({"page": pages, **page.diagnostics})
            ordered = sorted(
                page.candidates,
                key=lambda item: (
                    item.position,
                    item.document_id,
                    item.revision,
                    item.candidate_id,
                ),
            )
            page_minimum = ordered[0].position if ordered else maximum_position
            if page_minimum < previous_page_position:
                failures += 1
                status = RunStatus.FAILED
                diagnostics.append(
                    self._diagnostic(
                        FailureClass.MALFORMED_ADAPTER,
                        "provider pages are not monotonic by candidate position",
                        False,
                    )
                )
                break
            for candidate in ordered:
                discovered += 1
                maximum_position = max(maximum_position, candidate.position)
                prior = seen_candidates.get(candidate.candidate_id)
                if prior is not None:
                    if prior != candidate.canonical():
                        failures += 1
                        status = RunStatus.FAILED
                        diagnostics.append(
                            self._diagnostic(
                                FailureClass.MALFORMED_ADAPTER,
                                f"ambiguous duplicate candidate: {candidate.candidate_id}",
                                False,
                            )
                        )
                        break
                    duplicates += 1
                    attempt_id = self._attempt_id(candidate, "duplicate")
                    repository_candidate = self._repository_candidate(profile, candidate)
                    created = self._repository.record_outcome(
                        attempt_id,
                        repository_candidate,
                        RetrievalOutcome.DUPLICATE,
                        candidate.provenance.discovered_at,
                        profile.mechanism,
                        {"reason": "duplicate discovery occurrence"},
                    )
                    outcomes.append(
                        CandidateRunOutcome(
                            candidate.candidate_id,
                            candidate.document_id,
                            candidate.position,
                            candidate.revision,
                            "duplicate",
                            attempt_id,
                            created,
                            "exact duplicate candidate handled once",
                        )
                    )
                    continue
                seen_candidates[candidate.candidate_id] = candidate.canonical()
                if checkpoint_before and candidate.position <= checkpoint_before.position:
                    outcomes.append(
                        CandidateRunOutcome(
                            candidate.candidate_id,
                            candidate.document_id,
                            candidate.position,
                            candidate.revision,
                            "checkpoint_filtered",
                            None,
                            False,
                            "candidate position is at or before durable source progress",
                        )
                    )
                    continue
                repository_candidate = self._repository_candidate(profile, candidate)
                if candidate.disposition == "skip":
                    skips += 1
                    attempt_id = self._attempt_id(candidate, "skip")
                    created = self._repository.record_outcome(
                        attempt_id,
                        repository_candidate,
                        RetrievalOutcome.SKIPPED,
                        candidate.provenance.discovered_at,
                        profile.mechanism,
                        {"reason": candidate.disposition_reason or "policy rejection"},
                    )
                    outcomes.append(
                        CandidateRunOutcome(
                            candidate.candidate_id,
                            candidate.document_id,
                            candidate.position,
                            candidate.revision,
                            "skipped",
                            attempt_id,
                            created,
                            candidate.disposition_reason or "policy rejection",
                        )
                    )
                    continue
                retrievals += 1
                try:
                    result = adapter.retrieve(profile, candidate)
                    if not isinstance(result, RetrievalResult):
                        raise ContractError("adapter retrieval did not return RetrievalResult")
                    attempt_id = self._attempt_id(candidate, "success")
                    receipt = self._repository.record_success(
                        attempt_id, repository_candidate, result
                    )
                    last_success = attempt_id
                    if receipt.idempotent:
                        unchanged += 1
                        observed = "unchanged"
                    elif not receipt.artifact_created:
                        duplicates += 1
                        observed = "duplicate"
                    else:
                        durable += 1
                        observed = "acquired"
                    outcomes.append(
                        CandidateRunOutcome(
                            candidate.candidate_id,
                            candidate.document_id,
                            candidate.position,
                            candidate.revision,
                            observed,
                            attempt_id,
                            True,
                            f"artifact {receipt.artifact_id}",
                        )
                    )
                except AdapterFailure as error:
                    failures += 1
                    failed_id = self._attempt_id(candidate, error.classification.value)
                    self._repository.record_outcome(
                        failed_id,
                        repository_candidate,
                        RetrievalOutcome.FAILED,
                        candidate.provenance.discovered_at,
                        profile.mechanism,
                        {
                            "failure_class": error.classification.value,
                            "message": str(error),
                            "retryable": error.retryable,
                        },
                    )
                    outcomes.append(
                        CandidateRunOutcome(
                            candidate.candidate_id,
                            candidate.document_id,
                            candidate.position,
                            candidate.revision,
                            "failed",
                            failed_id,
                            True,
                            str(error),
                        )
                    )
                    diagnostics.append(self._failure_diagnostic(error, candidate.candidate_id))
                    status = (
                        RunStatus.PARTIAL
                        if durable or unchanged
                        else self._failure_status(error)
                    )
                    break
                except ConflictError as error:
                    failures += 1
                    status = RunStatus.FAILED
                    diagnostics.append(
                        self._diagnostic(FailureClass.REPOSITORY_CONFLICT, str(error), False)
                    )
                    break
                except IntegrityError as error:
                    failures += 1
                    status = RunStatus.FAILED
                    diagnostics.append(
                        self._diagnostic(FailureClass.REPOSITORY_INTEGRITY, str(error), False)
                    )
                    break
                except ContractError as error:
                    failures += 1
                    status = RunStatus.FAILED
                    diagnostics.append(
                        self._diagnostic(FailureClass.MALFORMED_ADAPTER, str(error), False)
                    )
                    break
            if status != RunStatus.COMPLETE:
                break
            if ordered:
                previous_page_position = max(item.position for item in ordered)
            if page.next_token is None:
                break
            if page.next_token in seen_tokens:
                failures += 1
                status = RunStatus.FAILED
                diagnostics.append(
                    self._diagnostic(
                        FailureClass.MALFORMED_ADAPTER,
                        f"provider continuation cycle: {page.next_token}",
                        False,
                    )
                )
                break
            seen_tokens.add(page.next_token)
            continuations.append(page.next_token)
            continuation = page.next_token

        if status == RunStatus.COMPLETE:
            target = self._target_checkpoint(maximum_position, seen_candidates)
            if checkpoint_before != target:
                if fail_at == EngineFailurePoint.BEFORE_CHECKPOINT_FINALIZATION:
                    failures += 1
                    status = RunStatus.PARTIAL
                    diagnostics.append(
                        {
                            "failure_class": FailureClass.TRANSIENT_ADAPTER.value,
                            "message": "injected failure before checkpoint finalization",
                            "retryable": True,
                        }
                    )
                elif last_success is None:
                    status = RunStatus.BLOCKED
                    diagnostics.append(
                        self._diagnostic(
                            FailureClass.POLICY_REJECTION,
                            "bounded run has no successful attempt to anchor progress",
                            False,
                        )
                    )
                else:
                    self._repository.advance_checkpoint(source_id, last_success, target)

        return AcquisitionRunResult(
            run_id=run_id,
            source_id=source_id,
            mechanism=profile.mechanism,
            started_at=started,
            completed_at=self._clock(),
            status=status,
            pages=pages,
            candidates_discovered=discovered,
            candidates_unique=len(seen_candidates),
            retrieval_attempts=retrievals,
            durable_acquisitions=durable,
            unchanged=unchanged,
            duplicates=duplicates,
            skips=skips,
            failures=failures,
            checkpoint_before=checkpoint_before,
            checkpoint_after=self._checkpoint(source_id),
            provider_continuations=tuple(continuations),
            outcomes=tuple(outcomes),
            diagnostics=tuple(diagnostics),
        )

    def adapter_registrations(self) -> dict[str, str]:
        """Return the explicit adapter selection table for operator inspection."""
        return self._adapters.registrations()

    def _load_profile(self, source_id: str) -> SourceProfile:
        """Revalidate the authoritative source record at execution time."""
        record = self._repository.source(source_id)
        values = {
            key: record[key]
            for key in ("source_id", "name", "enabled", "mechanism", "configuration", "policy")
        }
        return SourceProfile(**values)

    def _checkpoint(self, source_id: str) -> Checkpoint | None:
        """Load the repository-derived source checkpoint view."""
        value = self._repository.checkpoints()["sources"].get(source_id)
        return None if value is None else Checkpoint(value["position"], value["cursor"])

    @staticmethod
    def _validate_page(page: object) -> None:
        """Reject malformed provider output before any candidate on the page is processed."""
        if not isinstance(page, DiscoveryPage):
            raise ContractError("adapter discovery did not return DiscoveryPage")
        if any(not isinstance(candidate, AdapterCandidate) for candidate in page.candidates):
            raise ContractError("discovery page contains a malformed candidate")

    @staticmethod
    def _repository_candidate(
        profile: SourceProfile, candidate: AdapterCandidate
    ) -> CandidateDocument:
        """Convert adapter identity/provenance into the repository-owned input contract."""
        return CandidateDocument(
            candidate.candidate_id,
            profile.source_id,
            candidate.document_id,
            candidate.provenance,
        )

    @staticmethod
    def _attempt_id(candidate: AdapterCandidate, outcome: str) -> str:
        """Derive operation identity without treating provider identity as repository identity."""
        payload = json.dumps(
            {
                "candidate_id": candidate.candidate_id,
                "document_id": candidate.document_id,
                "revision": candidate.revision,
                "outcome": outcome,
            },
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
        return f"attempt-engine-{hashlib.sha256(payload).hexdigest()}"

    @staticmethod
    def _target_checkpoint(
        position: int, candidates: dict[str, dict[str, Any]]
    ) -> Checkpoint:
        """Derive durable progress independently of provider continuation tokens."""
        payload = json.dumps(candidates, sort_keys=True, separators=(",", ":")).encode()
        cursor = f"engine-{hashlib.sha256(payload).hexdigest()[:24]}"
        return Checkpoint(position, cursor)

    @staticmethod
    def _failure_status(error: AdapterFailure) -> RunStatus:
        """Map failure classification to operator lifecycle state."""
        return RunStatus.PARTIAL if error.retryable else RunStatus.BLOCKED

    @staticmethod
    def _failure_diagnostic(error: AdapterFailure, context: str | None) -> dict[str, JsonValue]:
        """Render adapter failure without leaking runtime configuration."""
        return {
            "failure_class": error.classification.value,
            "message": str(error),
            "retryable": error.retryable,
            "context": context,
        }

    @staticmethod
    def _diagnostic(
        classification: FailureClass, message: str, retryable: bool
    ) -> dict[str, JsonValue]:
        """Render one stable engine/repository diagnostic."""
        return {
            "failure_class": classification.value,
            "message": message,
            "retryable": retryable,
        }


class AcquisitionKernel:
    """Operator-facing composition root for one repository, registry, and engine."""

    def __init__(self, engine: AcquisitionEngine, repository: AcquisitionRepository) -> None:
        self.engine = engine
        self.repository = repository

    def run_enabled(self, run_key: str) -> tuple[AcquisitionRunResult, ...]:
        """Run all enabled governed sources in stable source identity order."""
        results = []
        for record in self.repository.sources():
            if record["enabled"]:
                results.append(self.engine.run_source(record["source_id"], run_key))
        return tuple(results)
