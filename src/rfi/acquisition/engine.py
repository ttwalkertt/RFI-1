"""Deterministic source-adapter orchestration over repository-owned persistence."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from enum import StrEnum
from typing import Any, Callable, Protocol, runtime_checkable

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
from rfi.acquisition.url_identity import normalize_discovery_url


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
        self,
        classification: FailureClass,
        message: str,
        retryable: bool,
        code: str | None = None,
    ) -> None:
        super().__init__(message)
        self.classification = classification
        self.retryable = retryable
        self.code = code or classification.value


_CANDIDATE_IDENTITY_METADATA_FIELDS = frozenset({
    "accepted_at",
    "acceptance_datetime",
    "accession_no",
    "accession_number",
    "adapter_id",
    "allowed_hosts",
    "amendment",
    "amendment_policy",
    "archive_path",
    "artifact_role",
    "canonical_artifact_id",
    "checkpoint_reporting_period",
    "company_name",
    "complete_submission_archive_path",
    "configured_source",
    "deferred_candidate_evaluation",
    "expected_reporting_period",
    "filed_at",
    "filing_date",
    "firm_id",
    "firm_identity_terms",
    "fixture_source",
    "form_type",
    "issuer_cik",
    "issuer_ticker",
    "link_to_txt",
    "ordering_key",
    "period_of_report",
    "primary_document",
    "provider",
    "provider_surface",
    "resolved_url",
    "revision",
    "sequence",
    "submissions_path",
})

_DISCOVERY_OCCURRENCE_METADATA_FIELDS = frozenset({
    "deterministic_selection_rank",
    "link_label",
    "observed_aliases",
    "parent_path",
    "parent_url",
    "proposal_rank",
    "ranking_reasons",
    "requested_url",
    "seed_kind",
    "seed_source",
    "starting_seed",
    "traversal_depth",
    "trial_id",
})

_MAX_OCCURRENCE_CANDIDATE_SAMPLES = 8
_MAX_OCCURRENCES_PER_CANDIDATE = 3
_MAX_OCCURRENCE_COLLECTION_ITEMS = 8
_MAX_OCCURRENCE_STRING_LENGTH = 512


def _string_or_none(value: object) -> str | None:
    return value if isinstance(value, str) else None


def _bounded_occurrence_value(value: JsonValue) -> tuple[JsonValue, bool]:
    if isinstance(value, str):
        return value[:_MAX_OCCURRENCE_STRING_LENGTH], (
            len(value) > _MAX_OCCURRENCE_STRING_LENGTH
        )
    if isinstance(value, list):
        bounded: list[JsonValue] = []
        truncated = len(value) > _MAX_OCCURRENCE_COLLECTION_ITEMS
        for item in value[:_MAX_OCCURRENCE_COLLECTION_ITEMS]:
            projected, item_truncated = _bounded_occurrence_value(item)
            bounded.append(projected)
            truncated = truncated or item_truncated
        return bounded, truncated
    if isinstance(value, dict):
        bounded_dict: dict[str, JsonValue] = {}
        items = list(value.items())
        truncated = len(items) > _MAX_OCCURRENCE_COLLECTION_ITEMS
        for key, item in items[:_MAX_OCCURRENCE_COLLECTION_ITEMS]:
            projected, item_truncated = _bounded_occurrence_value(item)
            bounded_dict[key] = projected
            truncated = truncated or item_truncated
        return bounded_dict, truncated
    return value, False


@runtime_checkable
class AdapterAcquisitionTarget(Protocol):
    """Provider-neutral immutable target carried through deterministic trials."""

    firm_id: str

    def to_dict(self) -> dict[str, Any]:
        """Return stable target semantics for boundary validation."""


@dataclass(frozen=True)
class CandidateIdentity:
    """Allowlisted stable semantics used for duplicate conflict detection."""

    candidate_id: str
    document_id: str
    position: int
    revision: str
    disposition: str
    disposition_reason: str | None
    discovery_method: str
    provider_identifiers: dict[str, str]
    canonical_locations: tuple[str, ...]
    metadata: dict[str, JsonValue]
    acquisition_target: dict[str, Any] | None

    def to_dict(self) -> dict[str, Any]:
        value: dict[str, Any] = {
            "candidate_id": self.candidate_id,
            "document_id": self.document_id,
            "position": self.position,
            "revision": self.revision,
            "disposition": self.disposition,
            "disposition_reason": self.disposition_reason,
            "discovery_method": self.discovery_method,
            "provider_identifiers": dict(self.provider_identifiers),
            "canonical_locations": list(self.canonical_locations),
            "metadata": dict(self.metadata),
        }
        if self.acquisition_target is not None:
            value["acquisition_target"] = dict(self.acquisition_target)
        return value


@dataclass(frozen=True)
class DiscoveryOccurrence:
    """Trial-local attribution for one observation of a stable candidate."""

    discovered_at: str
    trial_id: str | None
    starting_seed: str | None
    seed_kind: str | None
    seed_source: str | None
    locations: tuple[str, ...]
    metadata: dict[str, JsonValue]
    details_omitted: bool

    def to_dict(self) -> dict[str, JsonValue]:
        return {
            "discovered_at": self.discovered_at,
            "trial_id": self.trial_id,
            "starting_seed": self.starting_seed,
            "seed_kind": self.seed_kind,
            "seed_source": self.seed_source,
            "locations": list(self.locations),
            "metadata": dict(self.metadata),
            "details_omitted": self.details_omitted,
        }


@dataclass(frozen=True)
class AdapterCandidate:
    """Provider-neutral discovery item before repository contract conversion."""

    candidate_id: str
    document_id: str
    position: int
    revision: str
    provenance: DiscoveryProvenance
    acquisition_target: AdapterAcquisitionTarget | None = None
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
        """Return the complete candidate representation used for persistence."""
        value = {
            "candidate_id": self.candidate_id,
            "document_id": self.document_id,
            "position": self.position,
            "revision": self.revision,
            "provenance": self.provenance.to_dict(),
            "disposition": self.disposition,
            "disposition_reason": self.disposition_reason,
        }
        if self.acquisition_target is not None:
            value["acquisition_target"] = self.acquisition_target.to_dict()
        return value

    def identity(self) -> CandidateIdentity:
        """Return the one allowlisted candidate identity representation."""
        metadata = {
            key: value for key, value in self.provenance.metadata.items()
            if key in _CANDIDATE_IDENTITY_METADATA_FIELDS
        }
        resolved = metadata.get("resolved_url")
        if isinstance(resolved, str):
            resolved = normalize_discovery_url(resolved)
            metadata["resolved_url"] = resolved
        canonical_locations = (
            (resolved,) if isinstance(resolved, str)
            else self.provenance.locations
        )
        return CandidateIdentity(
            self.candidate_id,
            self.document_id,
            self.position,
            self.revision,
            self.disposition,
            self.disposition_reason,
            self.provenance.discovery_method,
            dict(self.provenance.provider_identifiers),
            canonical_locations,
            metadata,
            (
                self.acquisition_target.to_dict()
                if self.acquisition_target is not None else None
            ),
        )

    def occurrence(
        self, trial: AdapterAcquisitionTrial | None = None
    ) -> DiscoveryOccurrence:
        """Return trial-local discovery attribution excluded from identity."""
        metadata = {
            key: value for key, value in self.provenance.metadata.items()
            if key in _DISCOVERY_OCCURRENCE_METADATA_FIELDS
        }
        bounded_metadata: dict[str, JsonValue] = {}
        details_omitted = False
        for key, value in metadata.items():
            bounded, omitted = _bounded_occurrence_value(value)
            bounded_metadata[key] = bounded
            details_omitted = details_omitted or omitted
        starting_seed = _string_or_none(metadata.get("starting_seed"))
        if starting_seed is None and trial is not None:
            starting_seed = trial.starting_seed
        if starting_seed is not None:
            bounded_seed, omitted = _bounded_occurrence_value(starting_seed)
            assert isinstance(bounded_seed, str)
            starting_seed = bounded_seed
            details_omitted = details_omitted or omitted
        locations = self.provenance.locations[:_MAX_OCCURRENCE_COLLECTION_ITEMS]
        details_omitted = details_omitted or (
            len(self.provenance.locations) > len(locations)
        )
        return DiscoveryOccurrence(
            self.provenance.discovered_at,
            trial.trial_id if trial is not None else _string_or_none(metadata.get("trial_id")),
            starting_seed,
            _string_or_none(metadata.get("seed_kind"))
            or (trial.seed_kind if trial is not None else None),
            (
                _string_or_none(metadata.get("seed_source"))
                or (trial.seed_source if trial is not None else None)
            ),
            locations,
            bounded_metadata,
            details_omitted,
        )


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


@dataclass(frozen=True)
class AdapterAcquisitionTrial:
    """One independently attributable deterministic adapter trial."""

    trial_id: str
    starting_seed: str
    seed_kind: str
    acquisition_target: AdapterAcquisitionTarget
    seed_source: str = "configured"
    starting_seeds: tuple[str, ...] = ()
    duplicate_seed_count: int = 0
    continue_candidate_failures: bool = False
    provider: str = ""

    def __post_init__(self) -> None:
        require_identifier(self.trial_id, "trial_id")
        if not self.starting_seed.strip():
            raise ContractError("acquisition trial starting_seed must not be blank")
        require_identifier(self.seed_kind, "trial seed_kind")
        require_identifier(self.seed_source, "trial seed_source")
        if self.seed_source not in {"learned", "configured", "operator_supplied"}:
            raise ContractError("acquisition trial seed_source is unknown")
        if not isinstance(self.acquisition_target, AdapterAcquisitionTarget):
            raise ContractError("acquisition trial target is malformed")
        if self.starting_seeds:
            if self.starting_seeds[0] != self.starting_seed:
                raise ContractError("acquisition trial primary seed changed")
            if any(not isinstance(seed, str) or not seed.strip() for seed in self.starting_seeds):
                raise ContractError("acquisition trial contains a malformed seed")
            if len(set(self.starting_seeds)) != len(self.starting_seeds):
                raise ContractError("acquisition trial contains duplicate canonical seeds")
        if (
            isinstance(self.duplicate_seed_count, bool)
            or not isinstance(self.duplicate_seed_count, int)
            or self.duplicate_seed_count < 0
        ):
            raise ContractError("acquisition trial duplicate seed count is invalid")
        if not isinstance(self.continue_candidate_failures, bool):
            raise ContractError("acquisition trial failure-continuation policy is invalid")
        if self.provider:
            require_identifier(self.provider, "trial provider")

    @property
    def seeds(self) -> tuple[str, ...]:
        """Return the ordered run-phase seeds without changing single-seed callers."""
        return self.starting_seeds or (self.starting_seed,)


@dataclass(frozen=True)
class AdapterSelectionDecision:
    """Provider-neutral qualification result returned by an adapter policy."""

    qualifies: bool
    disposition: str
    validation_outcome: str
    diagnostics: dict[str, JsonValue] = field(default_factory=dict)

    def __post_init__(self) -> None:
        require_identifier(self.disposition, "selection disposition")
        require_identifier(self.validation_outcome, "selection validation outcome")
        validate_json(self.diagnostics, "selection decision diagnostics")


@dataclass(frozen=True)
class AdapterSelectionCandidate:
    """Validated retrieval awaiting adapter-policy terminal reduction."""

    candidate: AdapterCandidate
    repository_candidate: CandidateDocument
    retrieval: RetrievalResult
    decision: AdapterSelectionDecision


class AdapterTerminalSelectionPolicy(Protocol):
    """Adapter-owned qualification and terminal reduction policy seam."""

    def qualify(
        self, candidate: AdapterCandidate, retrieval: RetrievalResult
    ) -> AdapterSelectionDecision:
        """Classify one successfully validated retrieval."""

    def select(
        self, candidates: tuple[AdapterSelectionCandidate, ...]
    ) -> AdapterSelectionCandidate:
        """Select exactly one globally preferred qualified retrieval."""

    def attribution(self) -> dict[str, JsonValue]:
        """Return stable terminal diagnostic attribution."""


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
        with self._repository.acquisition_transaction():
            return self._run_source(source_id, run_key, fail_at)

    def run_source_trial(
        self,
        source_id: str,
        run_key: str,
        trial: AdapterAcquisitionTrial,
        fail_at: EngineFailurePoint | None = None,
    ) -> AcquisitionRunResult:
        """Execute one caller-selected trial through the normal acquisition lifecycle."""
        if not isinstance(trial, AdapterAcquisitionTrial):
            raise ContractError("injected acquisition trial is malformed")
        with self._repository.acquisition_transaction():
            return self._run_source(source_id, run_key, fail_at, (trial,))

    def _run_source(
        self, source_id: str, run_key: str,
        fail_at: EngineFailurePoint | None = None,
        acquisition_trial_override: tuple[AdapterAcquisitionTrial, ...] | None = None,
    ) -> AcquisitionRunResult:
        require_identifier(run_key, "run_key")
        started = self._clock()
        run_id = f"run-{source_id}-{run_key}"
        try:
            profile = self._load_profile(source_id)
            adapter = self._adapters.select(profile)
            checkpoint_before = self._checkpoint(source_id)
        except (IntegrityError, ConflictError) as error:
            return AcquisitionRunResult(
                run_id,
                source_id,
                "unknown",
                started,
                self._clock(),
                RunStatus.FAILED,
                0,
                0,
                0,
                0,
                0,
                0,
                0,
                0,
                1,
                None,
                None,
                (),
                (),
                (
                    self._diagnostic(
                        FailureClass.REPOSITORY_INTEGRITY, str(error), False
                    ),
                ),
            )
        continuation: str | None = None
        continuations: list[str] = []
        seen_tokens: set[str] = set()
        seen_candidates: dict[str, dict[str, Any]] = {}
        seen_candidate_identities: dict[str, CandidateIdentity] = {}
        authoritative_candidates: dict[str, AdapterCandidate] = {}
        occurrence_counts: dict[str, int] = {}
        occurrence_samples: dict[str, list[DiscoveryOccurrence]] = {}
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
        checkpoint_success: str | None = None
        maximum_position = checkpoint_before.position if checkpoint_before else 0
        maximum_success_position = maximum_position
        successful_candidates: dict[str, dict[str, Any]] = {}
        previous_page_position = 0
        status = RunStatus.COMPLETE
        checkpoint_confirmed = False
        retained_replays = 0

        acquisition_trials: tuple[AdapterAcquisitionTrial, ...] | None = None
        selection_policy: AdapterTerminalSelectionPolicy | None = None
        selection_checkpoint_eligible = True
        selection_incomplete_status: RunStatus | None = None
        qualified_selection_candidates: list[AdapterSelectionCandidate] = []
        selected_selection_candidate: AdapterSelectionCandidate | None = None
        trial_planning_failed = False
        try:
            if hasattr(adapter, "acquisition_trials") or hasattr(adapter, "discover_trial"):
                if not (
                    callable(getattr(adapter, "acquisition_trials", None))
                    and callable(getattr(adapter, "discover_trial", None))
                ):
                    raise ContractError(
                        "trial-oriented adapters require acquisition_trials and discover_trial"
                    )
                acquisition_trials = (
                    acquisition_trial_override
                    if acquisition_trial_override is not None
                    else adapter.acquisition_trials(profile)
                )
                if not isinstance(acquisition_trials, tuple) or not acquisition_trials:
                    raise ContractError("trial-oriented adapter returned no acquisition trials")
                if any(
                    not isinstance(item, AdapterAcquisitionTrial)
                    for item in acquisition_trials
                ):
                    raise ContractError("trial-oriented adapter returned a malformed trial")
                target = acquisition_trials[0].acquisition_target
                if any(item.acquisition_target is not target for item in acquisition_trials):
                    raise ContractError(
                        "deterministic acquisition trials changed the immutable target"
                    )
                if target.firm_id != profile.policy.get("firm_id"):
                    raise ContractError("acquisition target firm differs from source profile")
                factory = getattr(adapter, "terminal_selection_policy", None)
                if factory is not None:
                    if not callable(factory):
                        raise ContractError("adapter terminal selection policy is malformed")
                    selection_policy = factory(profile, acquisition_trials)
                    if selection_policy is not None and not all(callable(getattr(
                        selection_policy, name, None
                    )) for name in ("qualify", "select", "attribution")):
                        raise ContractError("adapter terminal selection policy is malformed")
                    selection_checkpoint_eligible = selection_policy is None
        except (ContractError, TypeError, AttributeError) as error:
            failures += 1
            status = RunStatus.FAILED
            diagnostics.append(
                self._diagnostic(FailureClass.MALFORMED_ADAPTER, str(error), False)
            )
            trial_planning_failed = True
        except Exception as error:
            failures += 1
            status = RunStatus.FAILED
            diagnostics.append(self._diagnostic(
                FailureClass.MALFORMED_ADAPTER,
                str(error) or error.__class__.__name__,
                False,
            ))
            trial_planning_failed = True
        trial_index = 0

        while not trial_planning_failed:
            active_trial = (
                acquisition_trials[trial_index]
                if acquisition_trials is not None else None
            )
            success_before_trial = last_success
            failures_before_trial = failures
            qualified_before_trial = len(qualified_selection_candidates)
            retained_replays_before_trial = retained_replays
            continued_candidate_status: RunStatus | None = None
            try:
                page = (
                    adapter.discover_trial(profile, active_trial)
                    if active_trial is not None
                    else adapter.discover(profile, continuation)
                )
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
            except Exception as error:
                failures += 1
                status = RunStatus.FAILED
                diagnostics.append(
                    self._diagnostic(
                        FailureClass.MALFORMED_ADAPTER,
                        str(error) or error.__class__.__name__,
                        False,
                    )
                )
                break
            pages += 1
            diagnostics.append({
                "page": pages,
                **({
                    "trial_id": active_trial.trial_id,
                    "starting_seed": active_trial.starting_seed,
                    "seed_kind": active_trial.seed_kind,
                    "seed_source": active_trial.seed_source,
                } if active_trial is not None else {}),
                **page.diagnostics,
            })
            trial_diagnostic_index = len(diagnostics) - 1
            ordered = sorted(
                page.candidates,
                key=lambda item: (
                    (
                        item.provenance.metadata.get("proposal_rank", item.position)
                        if item.provenance.metadata.get("deferred_candidate_evaluation") is True
                        else item.position
                    ),
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
                identity = candidate.identity()
                occurrence = candidate.occurrence(active_trial)
                occurrence_counts[candidate.candidate_id] = (
                    occurrence_counts.get(candidate.candidate_id, 0) + 1
                )
                samples = occurrence_samples.setdefault(candidate.candidate_id, [])
                if len(samples) < _MAX_OCCURRENCES_PER_CANDIDATE:
                    samples.append(occurrence)
                deferred_evaluation = (
                    candidate.provenance.metadata.get("deferred_candidate_evaluation") is True
                )
                if not deferred_evaluation:
                    maximum_position = max(maximum_position, candidate.position)
                prior = seen_candidates.get(candidate.candidate_id)
                if prior is not None:
                    if (
                        seen_candidate_identities[candidate.candidate_id]
                        != identity
                    ):
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
                    authoritative = authoritative_candidates[candidate.candidate_id]
                    duplicates += 1
                    attempt_id = self._attempt_id(run_id, authoritative, "duplicate")
                    repository_candidate = self._repository_candidate(
                        profile, authoritative
                    )
                    created = self._repository.record_outcome(
                        attempt_id,
                        repository_candidate,
                        RetrievalOutcome.DUPLICATE,
                        authoritative.provenance.discovered_at,
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
                seen_candidate_identities[candidate.candidate_id] = identity
                authoritative_candidates[candidate.candidate_id] = candidate
                if (
                    selection_policy is None
                    and checkpoint_before
                    and candidate.position <= checkpoint_before.position
                ):
                    checkpoint_confirmed = True
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
                    attempt_id = self._attempt_id(run_id, candidate, "skip")
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
                    if selection_policy is not None:
                        decision = selection_policy.qualify(candidate, result)
                        if not isinstance(decision, AdapterSelectionDecision):
                            raise ContractError(
                                "adapter selection policy returned a malformed decision"
                            )
                        self._record_selection_diagnostic(
                            diagnostics[trial_diagnostic_index], candidate, decision
                        )
                        if decision.qualifies:
                            qualified_selection_candidates.append(AdapterSelectionCandidate(
                                candidate, repository_candidate, result, decision
                            ))
                        else:
                            skips += 1
                            outcomes.append(CandidateRunOutcome(
                                candidate.candidate_id,
                                candidate.document_id,
                                candidate.position,
                                candidate.revision,
                                "selection_rejected",
                                None,
                                False,
                                decision.validation_outcome,
                            ))
                        continue
                    if deferred_evaluation:
                        validated_position = result.diagnostics.get("validated_position")
                        if not isinstance(validated_position, int) or validated_position < 1:
                            raise ContractError(
                                "deferred candidate retrieval lacks validated position"
                            )
                        maximum_position = max(maximum_position, validated_position)
                        checkpoint_position = validated_position
                    else:
                        checkpoint_position = candidate.position
                    retained_replay = (
                        active_trial is not None
                        and checkpoint_before is not None
                        and checkpoint_position <= checkpoint_before.position
                        and self._repository.has_retained_source_artifact(source_id, result)
                    )
                    if retained_replay:
                        checkpoint_confirmed = True
                        selection_checkpoint_eligible = False
                        retained_replays += 1
                        if fail_at == EngineFailurePoint.BEFORE_CHECKPOINT_FINALIZATION:
                            failures += 1
                            status = RunStatus.PARTIAL
                            diagnostics.append({
                                "failure_class": FailureClass.TRANSIENT_ADAPTER.value,
                                "message": "injected failure before checkpoint finalization",
                                "retryable": True,
                            })
                        else:
                            unchanged += 1
                            outcomes.append(CandidateRunOutcome(
                                candidate.candidate_id,
                                candidate.document_id,
                                candidate.position,
                                candidate.revision,
                                "unchanged",
                                None,
                                False,
                                "validated artifact is already retained at durable progress",
                            ))
                        break
                    attempt_id = self._attempt_id(run_id, candidate, "success")
                    receipt = self._repository.record_success(
                        attempt_id, repository_candidate, result
                    )
                    successful_candidates[candidate.candidate_id] = candidate.canonical()
                    if checkpoint_position > maximum_success_position:
                        maximum_success_position = checkpoint_position
                        checkpoint_success = attempt_id
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
                    # A successful deterministic trial is terminal. Range selection
                    # follows the deferred policy path above and is reduced globally.
                    if active_trial is not None:
                        break
                except AdapterFailure as error:
                    if selection_policy is not None:
                        failures += 1
                        failed_id = self._attempt_id(
                            run_id, candidate, error.classification.value
                        )
                        self._repository.record_outcome(
                            failed_id,
                            repository_candidate,
                            RetrievalOutcome.FAILED,
                            candidate.provenance.discovered_at,
                            profile.mechanism,
                            {
                                "failure_class": error.classification.value,
                                "failure_code": error.code,
                                "message": str(error),
                                "retryable": error.retryable,
                                **selection_policy.attribution(),
                            },
                        )
                        outcomes.append(CandidateRunOutcome(
                            candidate.candidate_id,
                            candidate.document_id,
                            candidate.position,
                            candidate.revision,
                            "failed",
                            failed_id,
                            True,
                            str(error),
                        ))
                        diagnostics.append(
                            self._failure_diagnostic(error, candidate.candidate_id)
                        )
                        self._record_selection_diagnostic(
                            diagnostics[trial_diagnostic_index], candidate,
                            AdapterSelectionDecision(
                                False, "validation_rejected", error.code,
                                {"retryable": error.retryable},
                            ),
                            retrieval_failure=error.retryable,
                        )
                        if error.classification != FailureClass.POLICY_REJECTION:
                            candidate_status = (
                                RunStatus.PARTIAL if error.retryable else RunStatus.BLOCKED
                            )
                            if (
                                selection_incomplete_status is None
                                or candidate_status == RunStatus.BLOCKED
                            ):
                                selection_incomplete_status = candidate_status
                        continue
                    if error.code == "historical_candidate_superseded":
                        skips += 1
                        skipped_id = self._attempt_id(run_id, candidate, "skip")
                        created = self._repository.record_outcome(
                            skipped_id,
                            repository_candidate,
                            RetrievalOutcome.SKIPPED,
                            candidate.provenance.discovered_at,
                            profile.mechanism,
                            {"reason": str(error)},
                        )
                        outcomes.append(CandidateRunOutcome(
                            candidate.candidate_id,
                            candidate.document_id,
                            candidate.position,
                            candidate.revision,
                            "skipped",
                            skipped_id,
                            created,
                            str(error),
                        ))
                        continue
                    failures += 1
                    failed_id = self._attempt_id(
                        run_id, candidate, error.classification.value
                    )
                    self._repository.record_outcome(
                        failed_id,
                        repository_candidate,
                        RetrievalOutcome.FAILED,
                        candidate.provenance.discovered_at,
                        profile.mechanism,
                        {
                            "failure_class": error.classification.value,
                            "failure_code": error.code,
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
                    candidate_failure_status = (
                        RunStatus.PARTIAL
                        if durable or unchanged
                        else self._failure_status(error)
                    )
                    if (
                        active_trial is not None
                        and active_trial.continue_candidate_failures
                    ):
                        if (
                            continued_candidate_status is None
                            or candidate_failure_status == RunStatus.BLOCKED
                        ):
                            continued_candidate_status = candidate_failure_status
                        continue
                    status = candidate_failure_status
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
                except Exception as error:
                    failures += 1
                    status = RunStatus.FAILED
                    diagnostics.append(
                        self._diagnostic(
                            FailureClass.MALFORMED_ADAPTER,
                            str(error) or error.__class__.__name__,
                            False,
                        )
                    )
                    break
            trial_qualified = (
                active_trial is not None
                and len(qualified_selection_candidates) > qualified_before_trial
            )
            trial_validated = (
                active_trial is not None
                and selection_policy is None
                and (
                    last_success != success_before_trial
                    or retained_replays > retained_replays_before_trial
                )
            )
            if (
                continued_candidate_status is not None
                and not trial_validated
                and not trial_qualified
            ):
                status = continued_candidate_status
            if active_trial is not None:
                diagnostics[trial_diagnostic_index].update({
                    "trial_outcome": (
                        "validated_success" if trial_validated else
                        "qualified_candidate" if trial_qualified else
                        "failed" if failures > failures_before_trial else
                        "no_validated_artifact"
                    ),
                    "acquisition_termination_reason": (
                        "first_validated_success" if trial_validated else
                        "next_seed" if trial_index + 1 < len(acquisition_trials or ()) else
                        "selection_trials_exhausted" if selection_policy is not None else
                        "seed_trials_exhausted"
                    ),
                    "validation_outcome": (
                        "validated" if trial_validated or trial_qualified
                        else "no_qualifying_validated_artifact"
                    ),
                    "terminal_selection_outcome": (
                        "selected" if trial_validated else
                        "pending_global_selection" if selection_policy is not None and (
                            trial_qualified or qualified_selection_candidates
                        ) else
                        "continue" if trial_index + 1 < len(acquisition_trials or ()) else
                        "no_match"
                    ),
                })
            if trial_validated:
                break
            if status != RunStatus.COMPLETE:
                retry_next_trial = (
                    acquisition_trials is not None
                    and status in {RunStatus.PARTIAL, RunStatus.BLOCKED}
                    and trial_index + 1 < len(acquisition_trials)
                )
                if retry_next_trial:
                    status = RunStatus.COMPLETE
                    trial_index += 1
                    previous_page_position = 0
                    continue
                break
            if acquisition_trials is not None:
                if page.next_token is not None:
                    failures += 1
                    status = RunStatus.FAILED
                    diagnostics.append(self._diagnostic(
                        FailureClass.MALFORMED_ADAPTER,
                        "deterministic acquisition trial returned a continuation token",
                        False,
                    ))
                    break
                trial_index += 1
                previous_page_position = 0
                if trial_index < len(acquisition_trials):
                    continue
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

        if (
            selection_policy is not None
            and status == RunStatus.COMPLETE
            and selection_incomplete_status is not None
        ):
            status = selection_incomplete_status

        if (
            selection_policy is not None
            and status == RunStatus.COMPLETE
            and qualified_selection_candidates
        ):
            try:
                selected_selection_candidate = selection_policy.select(
                    tuple(qualified_selection_candidates)
                )
                if selected_selection_candidate not in qualified_selection_candidates:
                    raise ContractError(
                        "adapter selection policy chose an unknown candidate"
                    )
                candidate = selected_selection_candidate.candidate
                repository_candidate = selected_selection_candidate.repository_candidate
                result = selected_selection_candidate.retrieval
                validated_position = result.diagnostics.get("validated_position")
                if not isinstance(validated_position, int) or validated_position < 1:
                    raise ContractError("selected retrieval lacks validated position")
                maximum_position = max(maximum_position, validated_position)
                selection_checkpoint_eligible = (
                    checkpoint_before is None
                    or validated_position > checkpoint_before.position
                )
                retained_replay = (
                    checkpoint_before is not None
                    and validated_position <= checkpoint_before.position
                    and self._repository.has_retained_artifact(repository_candidate, result)
                )
                if retained_replay:
                    checkpoint_confirmed = True
                    unchanged += 1
                    outcomes.append(CandidateRunOutcome(
                        candidate.candidate_id,
                        candidate.document_id,
                        candidate.position,
                        candidate.revision,
                        "unchanged",
                        None,
                        False,
                        "validated artifact is already retained at durable progress",
                    ))
                else:
                    attempt_id = self._attempt_id(run_id, candidate, "success")
                    receipt = self._repository.record_success(
                        attempt_id, repository_candidate, result
                    )
                    maximum_success_position = max(
                        maximum_success_position, validated_position
                    )
                    checkpoint_success = attempt_id
                    last_success = attempt_id
                    successful_candidates[candidate.candidate_id] = candidate.canonical()
                    if receipt.idempotent:
                        unchanged += 1
                        observed = "unchanged"
                    elif not receipt.artifact_created:
                        duplicates += 1
                        observed = "duplicate"
                    else:
                        durable += 1
                        observed = "acquired"
                    outcomes.append(CandidateRunOutcome(
                        candidate.candidate_id,
                        candidate.document_id,
                        candidate.position,
                        candidate.revision,
                        observed,
                        attempt_id,
                        True,
                        f"artifact {receipt.artifact_id}",
                    ))
            except (ContractError, ConflictError, IntegrityError) as error:
                failures += 1
                status = RunStatus.FAILED
                diagnostics.append(self._diagnostic(
                    FailureClass.MALFORMED_ADAPTER, str(error), False
                ))

        if status == RunStatus.COMPLETE and not (
            selection_policy is not None and selected_selection_candidate is None
        ) and selection_checkpoint_eligible:
            target = self._target_checkpoint(maximum_position, seen_candidates)
            checkpoint_replay = (
                checkpoint_before is not None
                and checkpoint_confirmed
                and retrievals == 0
                and target.position == checkpoint_before.position
            )
            if (
                fail_at == EngineFailurePoint.BEFORE_CHECKPOINT_FINALIZATION
                and seen_candidates
            ):
                failures += 1
                status = RunStatus.PARTIAL
                diagnostics.append(
                    {
                        "failure_class": FailureClass.TRANSIENT_ADAPTER.value,
                        "message": "injected failure before checkpoint finalization",
                        "retryable": True,
                    }
                )
            elif checkpoint_replay:
                if self._repository.record_no_change(source_id, checkpoint_before):
                    unchanged += 1
            elif checkpoint_before != target:
                if not seen_candidates:
                    # A successfully evaluated empty listing is a truthful no-change result.
                    # With no successful attempt there is deliberately no checkpoint to advance.
                    pass
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
            elif checkpoint_confirmed and checkpoint_before is not None and retrievals == 0:
                if self._repository.record_no_change(source_id, checkpoint_before):
                    unchanged += 1
        elif (
            status == RunStatus.PARTIAL
            and durable > 0
            and checkpoint_success is not None
            and maximum_success_position > (
                checkpoint_before.position if checkpoint_before else 0
            )
        ):
            target = self._target_checkpoint(
                maximum_success_position, successful_candidates
            )
            self._repository.advance_checkpoint(source_id, checkpoint_success, target)

        if selection_policy is not None:
            attribution = selection_policy.attribution()
            validate_json(attribution, "terminal selection attribution")
            if selected_selection_candidate is not None:
                terminal_outcome = "selected"
                validation_outcome = "validated"
            elif status == RunStatus.COMPLETE:
                terminal_outcome = "no_match"
                validation_outcome = "no_qualifying_validated_artifact"
            elif status in {RunStatus.PARTIAL, RunStatus.BLOCKED}:
                terminal_outcome = "incomplete"
                validation_outcome = "selection_incomplete"
            else:
                terminal_outcome = "failed"
                validation_outcome = "selection_failed"
            selected_diagnostics: dict[str, JsonValue] = {}
            if selected_selection_candidate is not None:
                selected_diagnostics = {
                    "selected_candidate_id": (
                        selected_selection_candidate.candidate.candidate_id
                    ),
                    **{
                        f"selected_{key}": value
                        for key, value in (
                            selected_selection_candidate.decision.diagnostics.items()
                        )
                    },
                }
            diagnostics.append({
                **attribution,
                "terminal_selection_outcome": terminal_outcome,
                "terminal_run_status": status.value,
                "validation_outcome": validation_outcome,
                "qualified_candidate_count": len(qualified_selection_candidates),
                **selected_diagnostics,
            })

        occurrence_diagnostic = self._occurrence_diagnostic(
            occurrence_counts, occurrence_samples
        )
        if occurrence_diagnostic is not None:
            insertion = len(diagnostics)
            if diagnostics and (
                "failure_class" in diagnostics[-1]
                or "terminal_run_status" in diagnostics[-1]
            ):
                insertion -= 1
            diagnostics.insert(insertion, occurrence_diagnostic)

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
    def _occurrence_diagnostic(
        occurrence_counts: dict[str, int],
        occurrence_samples: dict[str, list[DiscoveryOccurrence]],
    ) -> dict[str, JsonValue] | None:
        """Return exact totals with bounded first-occurrence-ordered samples."""
        repeated = [
            candidate_id for candidate_id, count in occurrence_counts.items()
            if count > 1
        ]
        if not repeated:
            return None
        selected = repeated[:_MAX_OCCURRENCE_CANDIDATE_SAMPLES]
        samples: list[dict[str, JsonValue]] = []
        for candidate_id in selected:
            occurrences = occurrence_samples[candidate_id]
            total = occurrence_counts[candidate_id]
            samples.append({
                "candidate_id": candidate_id,
                "occurrence_count": total,
                "authoritative_occurrence": occurrences[0].to_dict(),
                "occurrences": [item.to_dict() for item in occurrences],
                "occurrences_omitted": total > len(occurrences),
            })
        value: dict[str, JsonValue] = {
            "diagnostic_type": "candidate_occurrences",
            "candidates_with_multiple_occurrences": len(repeated),
            "duplicate_occurrence_count": sum(
                occurrence_counts[candidate_id] - 1 for candidate_id in repeated
            ),
            "candidate_samples": samples,
            "candidate_samples_omitted": len(repeated) > len(selected),
        }
        validate_json(value, "candidate occurrence diagnostics")
        return value

    @staticmethod
    def _record_selection_diagnostic(
        page: dict[str, JsonValue],
        candidate: AdapterCandidate,
        decision: AdapterSelectionDecision,
        retrieval_failure: bool = False,
    ) -> None:
        """Fold policy qualification into the existing bounded diagnostic model."""
        evaluated = page.get("candidate_evaluated_count", 0)
        page["candidate_evaluated_count"] = (
            evaluated + 1 if isinstance(evaluated, int) else 1
        )
        dispositions = page.get("candidate_disposition_counts")
        if not isinstance(dispositions, dict):
            dispositions = {}
            page["candidate_disposition_counts"] = dispositions
        current = dispositions.get(decision.disposition, 0)
        dispositions[decision.disposition] = current + 1 if isinstance(current, int) else 1
        if decision.validation_outcome != "validated":
            validation_failures = page.get("validation_failure_counts")
            if not isinstance(validation_failures, dict):
                validation_failures = {}
                page["validation_failure_counts"] = validation_failures
            current = validation_failures.get(decision.validation_outcome, 0)
            validation_failures[decision.validation_outcome] = (
                current + 1 if isinstance(current, int) else 1
            )
        if retrieval_failure:
            retrieval_failures = page.get("candidate_retrieval_failure_counts")
            if not isinstance(retrieval_failures, dict):
                retrieval_failures = {}
                page["candidate_retrieval_failure_counts"] = retrieval_failures
            current = retrieval_failures.get(decision.validation_outcome, 0)
            retrieval_failures[decision.validation_outcome] = (
                current + 1 if isinstance(current, int) else 1
            )
        samples = page.get("candidate_disposition_samples")
        if not isinstance(samples, list):
            samples = []
            page["candidate_disposition_samples"] = samples
        if len(samples) < 20:
            sample = {
                "candidate_id": candidate.candidate_id,
                "disposition": decision.disposition,
                "validation_outcome": decision.validation_outcome,
                **decision.diagnostics,
            }
            samples.append(sample)
            if decision.validation_outcome != "validated":
                failure_samples = page.get("candidate_failure_samples")
                if not isinstance(failure_samples, list):
                    failure_samples = []
                    page["candidate_failure_samples"] = failure_samples
                if len(failure_samples) < 20:
                    failure_samples.append(dict(sample))

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
    def _attempt_id(run_id: str, candidate: AdapterCandidate, outcome: str) -> str:
        """Derive run-bound attempt identity without using provider identity."""
        payload = json.dumps(
            {
                "run_id": run_id,
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
        """Derive durable progress from candidate semantics, excluding provenance."""
        stable_candidates = {
            candidate_id: {
                key: candidate.get(key)
                for key in (
                    "candidate_id",
                    "document_id",
                    "position",
                    "revision",
                    "disposition",
                    "disposition_reason",
                )
            }
            for candidate_id, candidate in candidates.items()
        }
        payload = json.dumps(
            stable_candidates, sort_keys=True, separators=(",", ":")
        ).encode()
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
            "failure_code": error.code,
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
