"""The concrete Pull Workflow: planning, execution, ingress, and aggregation."""

from __future__ import annotations

import hashlib
import json
import threading
import uuid
from dataclasses import asdict
from datetime import UTC, datetime
from typing import Any, Callable

from rfi.acquisition import (
    AcquisitionEngine,
    AcquisitionRepository,
    AdapterRegistry,
    RunStatus,
    SourceProfile,
)
from rfi.firms.contracts import FirmCatalog
from rfi.pull.contracts import (
    ArtifactOutcome,
    ArtifactPullResult,
    ConfiguredFirm,
    FirmPullResult,
    PullError,
    PullRequest,
    PullRunResult,
    PullStage,
    PullStatus,
    PullSummary,
    RetrievalAttemptResult,
)
from rfi.pull.planning import PlannedArtifact, PlannedFirm, PullPlanner
from rfi.pull.repository import PullRunRepository
from rfi.source_profiles.contracts import (
    AcquisitionTemplate,
    RetrievalCandidate,
    SourceProfileCatalog,
)


def utc_now() -> str:
    """Return an ISO timestamp for production workflow composition."""
    return datetime.now(UTC).isoformat()


class PullWorkflow:
    """RFI's single acquisition orchestration path for all initiating interfaces."""

    def __init__(
        self,
        firms: FirmCatalog,
        profiles: SourceProfileCatalog,
        template: AcquisitionTemplate,
        acquisition: AcquisitionRepository,
        adapters: AdapterRegistry,
        runs: PullRunRepository,
        clock: Callable[[], str] = utc_now,
        identifier_factory: Callable[[], str] = lambda: uuid.uuid4().hex,
    ) -> None:
        self._firms = firms
        self._profiles = profiles
        self._template = template
        self._acquisition = acquisition
        self._adapters = adapters
        self._runs = runs
        self._clock = clock
        self._identifier_factory = identifier_factory
        self._execution_lock = threading.Lock()

    def configured_firms(self) -> tuple[ConfiguredFirm, ...]:
        """Project current saved profiles and honest adapter readiness for the GUI."""
        planner = self._planner()
        result = []
        for firm in self._firms.lookup():
            profile = self._profiles.get(firm.firm_id)
            if profile is None:
                continue
            plan = planner.plan(firm, profile)
            runnable = sum(bool(item.runnable_candidates) for item in plan.artifacts)
            result.append(
                ConfiguredFirm(
                    firm.firm_id,
                    firm.canonical_name,
                    profile.source_profile_revision_id,
                    profile.revision_number,
                    len(plan.artifacts),
                    runnable,
                    len(plan.artifacts) - runnable,
                )
            )
        return tuple(sorted(result, key=lambda item: item.firm_id))

    def initiate(self, request: PullRequest) -> str:
        """Durably receive a request before any resolution or retrieval begins."""
        run_id = f"pull-{self._identifier_factory()}"
        requested_at = self._clock()
        self._runs.create(
            run_id,
            {
                "schema_version": 1,
                "run_id": run_id,
                "status": PullStatus.RUNNING.value,
                "current_stage": PullStage.RECEIVED.value,
                "requested_at": requested_at,
                "completed_at": "",
                "request": {
                    "firm_ids": list(request.firm_ids),
                    "all_configured": request.all_configured,
                },
                "completed_stages": [PullStage.RECEIVED.value],
                "stage_events": [
                    {"stage": PullStage.RECEIVED.value, "completed_at": requested_at}
                ],
                "resolved_firm_ids": [],
                "profile_snapshots": [],
                "plan": [],
                "firms": [],
                "summary": asdict(self._summary(())),
                "diagnostics": [],
            },
        )
        return run_id

    def execute(self, run_id: str) -> PullRunResult:
        """Execute every documented stage for one previously received request."""
        with self._execution_lock:
            record = self._runs.get(run_id)
            if record["status"] != PullStatus.RUNNING.value:
                return self._typed_result(record)
            request = PullRequest(
                tuple(record["request"]["firm_ids"]),
                bool(record["request"]["all_configured"]),
            )
            try:
                firms = self._resolve_firms(request)
                record["resolved_firm_ids"] = [firm.firm_id for firm in firms]
                self._complete_stage(record, PullStage.FIRMS_RESOLVED)

                snapshots = tuple((firm, self._profiles.get(firm.firm_id)) for firm in firms)
                record["profile_snapshots"] = [
                    self._snapshot(firm.firm_id, profile) for firm, profile in snapshots
                ]
                self._complete_stage(record, PullStage.REVISIONS_SNAPSHOTTED)

                planner = self._planner()
                plans = tuple(planner.plan(firm, profile) for firm, profile in snapshots)
                record["plan"] = [self._plan_record(plan) for plan in plans]
                self._complete_stage(record, PullStage.ARTIFACTS_EXPANDED)
                self._complete_stage(record, PullStage.ATTEMPTABILITY_DETERMINED)

                record["current_stage"] = PullStage.RETRIEVAL_EXECUTED.value
                self._runs.save(run_id, record)
                firm_results = []
                for plan in plans:
                    result = self._execute_firm(run_id, plan)
                    firm_results.append(result)
                    record["firms"] = [asdict(item) for item in firm_results]
                    self._runs.save(run_id, record)
                self._complete_stage(record, PullStage.RETRIEVAL_EXECUTED)
                self._complete_stage(record, PullStage.ARTIFACTS_INGESTED)
                self._complete_stage(record, PullStage.RESULTS_RECORDED)

                record["firms"] = [asdict(item) for item in firm_results]
                record["summary"] = asdict(self._summary(tuple(firm_results)))
                record["status"] = self._aggregate_status(
                    tuple(item.status for item in firm_results)
                ).value
                record["completed_at"] = self._clock()
                self._complete_stage(record, PullStage.SUMMARIZED)
            except Exception as error:
                record["status"] = PullStatus.FAILED.value
                record["completed_at"] = self._clock()
                record["diagnostics"].append(f"workflow execution failed: {error}")
                record["summary"] = asdict(self._summary(()))
                self._runs.save(run_id, record)
            return self._typed_result(self._runs.get(run_id))

    def run(self, request: PullRequest) -> PullRunResult:
        """Receive and synchronously execute a pull for CLI and direct callers."""
        return self.execute(self.initiate(request))

    def status(self, run_id: str) -> dict[str, Any]:
        """Return durable progress without requiring in-process workflow state."""
        record = self._runs.get(run_id)
        return {
            key: record[key]
            for key in (
                "run_id",
                "status",
                "current_stage",
                "requested_at",
                "completed_at",
                "completed_stages",
                "stage_events",
                "resolved_firm_ids",
                "summary",
                "diagnostics",
            )
        }

    def results(self, run_id: str) -> dict[str, Any]:
        """Return complete durable workflow results and the exact planning snapshot."""
        return self._runs.get(run_id)

    def _resolve_firms(self, request: PullRequest) -> tuple[Any, ...]:
        if request.all_configured:
            return tuple(
                firm
                for firm in self._firms.lookup()
                if self._profiles.get(firm.firm_id) is not None
            )
        return tuple(self._firms.get(firm_id) for firm_id in request.firm_ids)

    def _planner(self) -> PullPlanner:
        registrations = tuple(self._adapters.registrations())
        return PullPlanner(self._template, registrations)

    def _execute_firm(self, run_id: str, plan: PlannedFirm) -> FirmPullResult:
        artifacts = tuple(
            self._execute_artifact(run_id, plan, artifact) for artifact in plan.artifacts
        )
        return FirmPullResult(
            plan.firm.firm_id,
            plan.firm.canonical_name,
            plan.profile.source_profile_revision_id if plan.profile else None,
            plan.profile.revision_number if plan.profile else 0,
            self._artifact_status(artifacts),
            artifacts,
        )

    def _execute_artifact(
        self, run_id: str, firm: PlannedFirm, artifact: PlannedArtifact
    ) -> ArtifactPullResult:
        if not artifact.candidates:
            return ArtifactPullResult(
                firm.firm.firm_id,
                artifact.artifact_id,
                artifact.label,
                ArtifactOutcome.CONFIGURATION_PROBLEM,
                artifact.attemptability_diagnostic,
            )
        if not artifact.runnable_candidates:
            modes = ", ".join(sorted({item.mode for item in artifact.candidates}))
            return ArtifactPullResult(
                firm.firm.firm_id,
                artifact.artifact_id,
                artifact.label,
                ArtifactOutcome.SKIPPED,
                f"{artifact.attemptability_diagnostic} Configured mode(s): {modes}.",
            )
        attempts = []
        terminal = ArtifactOutcome.RETRIEVAL_FAILURE
        terminal_diagnostic = "Every runnable retrieval candidate failed."
        for candidate in artifact.runnable_candidates:
            attempt, outcome = self._execute_candidate(run_id, firm, artifact, candidate)
            attempts.append(attempt)
            if outcome in {
                ArtifactOutcome.SUCCESS,
                ArtifactOutcome.DUPLICATE,
                ArtifactOutcome.NO_CHANGE,
            }:
                terminal = outcome
                terminal_diagnostic = attempt.diagnostic
                break
        return ArtifactPullResult(
            firm.firm.firm_id,
            artifact.artifact_id,
            artifact.label,
            terminal,
            terminal_diagnostic,
            tuple(attempts),
        )

    def _execute_candidate(
        self,
        workflow_run_id: str,
        firm: PlannedFirm,
        artifact: PlannedArtifact,
        candidate: RetrievalCandidate,
    ) -> tuple[RetrievalAttemptResult, ArtifactOutcome]:
        candidate_value = self._candidate_value(candidate)
        revision_id = (
            firm.profile.source_profile_revision_id if firm.profile is not None else "defaults"
        )
        source_id = self._source_id(
            firm.firm.firm_id,
            artifact.artifact_id,
            revision_id,
            candidate_value,
        )
        document_id = f"document-{firm.firm.firm_id}-{artifact.artifact_id}"
        source = SourceProfile(
            source_id=source_id,
            name=f"{firm.firm.canonical_name}: {artifact.label}",
            enabled=True,
            mechanism=candidate.mode,
            configuration=candidate_value,
            policy={
                "firm_id": firm.firm.firm_id,
                "artifact_id": artifact.artifact_id,
                "source_profile_revision_id": revision_id,
                "document_id": document_id,
            },
        )
        try:
            self._acquisition.register_source(source)
            engine = AcquisitionEngine(self._acquisition, self._adapters, self._clock)
            result = engine.run_source(
                source_id,
                "workflow-"
                f"{workflow_run_id.removeprefix('pull-')}-{candidate.priority}",
            )
            artifact_ids = self._artifact_ids(result)
            outcome = self._engine_outcome(result)
            diagnostic = self._engine_diagnostic(result, outcome)
            attempt = RetrievalAttemptResult(
                candidate.mode,
                candidate.priority,
                result.run_id,
                result.status.value,
                diagnostic,
                artifact_ids,
            )
            return attempt, outcome
        except Exception as error:
            return (
                RetrievalAttemptResult(
                    candidate.mode,
                    candidate.priority,
                    None,
                    "failed",
                    str(error),
                ),
                ArtifactOutcome.RETRIEVAL_FAILURE,
            )

    def _artifact_ids(self, result: Any) -> tuple[str, ...]:
        attempt_ids = {item.attempt_id for item in result.outcomes if item.attempt_id}
        return tuple(
            sorted(
                {
                    record["artifact_id"]
                    for record in self._acquisition.history()
                    if record.get("attempt_id") in attempt_ids and record.get("artifact_id")
                }
            )
        )

    @staticmethod
    def _engine_outcome(result: Any) -> ArtifactOutcome:
        if result.durable_acquisitions:
            return ArtifactOutcome.SUCCESS
        if result.duplicates:
            return ArtifactOutcome.DUPLICATE
        if result.unchanged or (
            result.status == RunStatus.COMPLETE and not result.failures
        ):
            return ArtifactOutcome.NO_CHANGE
        return ArtifactOutcome.RETRIEVAL_FAILURE

    @staticmethod
    def _engine_diagnostic(result: Any, outcome: ArtifactOutcome) -> str:
        messages = [
            str(item.get("message"))
            for item in result.diagnostics
            if item.get("message")
        ]
        if messages:
            return "; ".join(messages)
        return {
            ArtifactOutcome.SUCCESS: "Retrieved and ingested through repository ingress.",
            ArtifactOutcome.DUPLICATE: "Exact artifact bytes already exist in immutable storage.",
            ArtifactOutcome.NO_CHANGE: "Source checkpoint indicates no new artifact.",
            ArtifactOutcome.RETRIEVAL_FAILURE: "Retrieval did not complete.",
        }[outcome]

    def _complete_stage(self, record: dict[str, Any], stage: PullStage) -> None:
        record["current_stage"] = stage.value
        if stage.value not in record["completed_stages"]:
            record["completed_stages"].append(stage.value)
            record["stage_events"].append(
                {"stage": stage.value, "completed_at": self._clock()}
            )
        self._runs.save(record["run_id"], record)

    def _snapshot(self, firm_id: str, profile: Any) -> dict[str, Any]:
        if profile is not None:
            return {"firm_id": firm_id, "is_default": False, **asdict(profile)}
        return {
            "firm_id": firm_id,
            "is_default": True,
            "source_profile_revision_id": None,
            "revision_number": 0,
            "items": [
                asdict(item)
                for item in self._planner().plan(self._firms.get(firm_id), None).items
            ],
        }

    @staticmethod
    def _plan_record(plan: PlannedFirm) -> dict[str, Any]:
        return {
            "firm_id": plan.firm.firm_id,
            "source_profile_revision_id": (
                plan.profile.source_profile_revision_id if plan.profile else None
            ),
            "enabled_artifacts": len(plan.artifacts),
            "artifacts": [
                {
                    "artifact_id": item.artifact_id,
                    "candidate_modes": [value.mode for value in item.candidates],
                    "runnable_priorities": [
                        value.priority for value in item.runnable_candidates
                    ],
                    "attemptability": item.attemptability_diagnostic,
                }
                for item in plan.artifacts
            ],
        }

    @staticmethod
    def _candidate_value(candidate: RetrievalCandidate) -> dict[str, Any]:
        return json.loads(json.dumps(asdict(candidate)))

    @staticmethod
    def _source_id(
        firm_id: str,
        artifact_id: str,
        revision_id: str,
        candidate: dict[str, Any],
    ) -> str:
        payload = json.dumps(
            {
                "firm_id": firm_id,
                "artifact_id": artifact_id,
                "revision_id": revision_id,
                "candidate": candidate,
            },
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
        digest = hashlib.sha256(payload).hexdigest()[:20]
        return f"source-pull-{firm_id}-{artifact_id}-{digest}"

    @staticmethod
    def _artifact_status(artifacts: tuple[ArtifactPullResult, ...]) -> PullStatus:
        failure = {
            ArtifactOutcome.CONFIGURATION_PROBLEM,
            ArtifactOutcome.RETRIEVAL_FAILURE,
        }
        failed = sum(item.outcome in failure for item in artifacts)
        if failed == 0:
            return PullStatus.COMPLETED
        if failed == len(artifacts):
            return PullStatus.FAILED
        return PullStatus.PARTIAL

    @staticmethod
    def _aggregate_status(statuses: tuple[PullStatus, ...]) -> PullStatus:
        if not statuses or all(item == PullStatus.COMPLETED for item in statuses):
            return PullStatus.COMPLETED
        if all(item == PullStatus.FAILED for item in statuses):
            return PullStatus.FAILED
        return PullStatus.PARTIAL

    @staticmethod
    def _summary(firms: tuple[FirmPullResult, ...]) -> PullSummary:
        artifacts = tuple(item for firm in firms for item in firm.artifacts)
        counts = {outcome: 0 for outcome in ArtifactOutcome}
        for artifact in artifacts:
            counts[artifact.outcome] += 1
        return PullSummary(
            len(firms),
            len(artifacts),
            counts[ArtifactOutcome.SUCCESS],
            counts[ArtifactOutcome.DUPLICATE],
            counts[ArtifactOutcome.NO_CHANGE],
            counts[ArtifactOutcome.SKIPPED],
            counts[ArtifactOutcome.CONFIGURATION_PROBLEM],
            counts[ArtifactOutcome.RETRIEVAL_FAILURE],
        )

    @staticmethod
    def _typed_result(record: dict[str, Any]) -> PullRunResult:
        firms = []
        for value in record["firms"]:
            artifacts = []
            for artifact in value["artifacts"]:
                attempts = tuple(
                    RetrievalAttemptResult(
                        item["mode"],
                        item["priority"],
                        item["acquisition_run_id"],
                        item["status"],
                        item["diagnostic"],
                        tuple(item.get("artifact_ids", ())),
                    )
                    for item in artifact["attempts"]
                )
                artifacts.append(
                    ArtifactPullResult(
                        artifact["firm_id"],
                        artifact["artifact_id"],
                        artifact["label"],
                        ArtifactOutcome(artifact["outcome"]),
                        artifact["diagnostic"],
                        attempts,
                    )
                )
            firms.append(
                FirmPullResult(
                    value["firm_id"],
                    value["canonical_name"],
                    value["source_profile_revision_id"],
                    value["source_profile_revision_number"],
                    PullStatus(value["status"]),
                    tuple(artifacts),
                )
            )
        return PullRunResult(
            record["run_id"],
            PullStatus(record["status"]),
            record["requested_at"],
            record["completed_at"],
            tuple(PullStage(item) for item in record["completed_stages"]),
            tuple(firms),
            PullSummary(**record["summary"]),
            tuple(record["diagnostics"]),
        )
