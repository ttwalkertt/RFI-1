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
    RunStatus,
    SourceProfile,
)
from rfi.firms.contracts import FirmCatalog
from rfi.pull.adapters import RetrievalAdapterRegistry
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
        adapters: RetrievalAdapterRegistry,
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

    def adapter_capabilities(self) -> tuple[dict[str, object], ...]:
        """Expose deterministic adapter declarations for operator inspection."""
        return self._adapters.registrations()

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
                "progress": {
                    "percent": 5,
                    "message": "Pull request received.",
                    "completed_artifacts": 0,
                    "total_artifacts": 0,
                    "updated_at": requested_at,
                },
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
                total_artifacts = sum(len(plan.artifacts) for plan in plans)
                completed_artifacts = 0

                def artifact_started(plan: PlannedFirm, artifact: PlannedArtifact) -> None:
                    self._set_progress(
                        record,
                        self._retrieval_percent(completed_artifacts, total_artifacts),
                        (
                            f"Retrieving source {completed_artifacts + 1} of "
                            f"{total_artifacts}: {artifact.label} for "
                            f"{plan.firm.canonical_name}."
                        ),
                        completed_artifacts,
                        total_artifacts,
                    )

                def artifact_completed(
                    plan: PlannedFirm, artifact: PlannedArtifact
                ) -> None:
                    nonlocal completed_artifacts
                    del plan, artifact
                    completed_artifacts += 1
                    self._set_progress(
                        record,
                        self._retrieval_percent(completed_artifacts, total_artifacts),
                        f"Processed {completed_artifacts} of {total_artifacts} sources.",
                        completed_artifacts,
                        total_artifacts,
                    )

                if total_artifacts == 0:
                    self._set_progress(
                        record, 90, "No enabled sources require retrieval.", 0, 0
                    )
                firm_results = []
                for plan in plans:
                    result = self._execute_firm(
                        run_id, plan, artifact_started, artifact_completed
                    )
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
                current = record.get("progress", {})
                self._set_progress(
                    record,
                    int(current.get("percent", 0)),
                    "Pull failed before the current step could finish.",
                    int(current.get("completed_artifacts", 0)),
                    int(current.get("total_artifacts", 0)),
                )
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
                "progress",
            )
            if key in record
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
        return PullPlanner(self._template, self._adapters, self._firms)

    def _execute_firm(
        self,
        run_id: str,
        plan: PlannedFirm,
        artifact_started: Callable[[PlannedFirm, PlannedArtifact], None] | None = None,
        artifact_completed: Callable[[PlannedFirm, PlannedArtifact], None] | None = None,
    ) -> FirmPullResult:
        artifacts = []
        for artifact in plan.artifacts:
            if artifact_started is not None:
                artifact_started(plan, artifact)
            artifacts.append(self._execute_artifact(run_id, plan, artifact))
            if artifact_completed is not None:
                artifact_completed(plan, artifact)
        artifact_results = tuple(artifacts)
        return FirmPullResult(
            plan.firm.firm_id,
            plan.firm.canonical_name,
            plan.profile.source_profile_revision_id if plan.profile else None,
            plan.profile.revision_number if plan.profile else 0,
            self._artifact_status(artifact_results),
            artifact_results,
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
        terminal_diagnostic = "No runnable retrieval candidate established an artifact outcome."
        for candidate in artifact.runnable_candidates:
            attempt, outcome = self._execute_candidate(run_id, firm, artifact, candidate)
            attempts.append(attempt)
            if outcome in {
                ArtifactOutcome.SUCCESS,
                ArtifactOutcome.SUCCESS_WITH_WARNINGS,
                ArtifactOutcome.DUPLICATE,
                ArtifactOutcome.NO_CHANGE,
                ArtifactOutcome.INDETERMINATE,
            }:
                terminal = outcome
                terminal_diagnostic = attempt.diagnostic
                break
            terminal_diagnostic = attempt.diagnostic
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
        registration = self._adapters.select(artifact.artifact_id, candidate)
        adapter_id = registration.capability.adapter_id
        revision_id = (
            firm.profile.source_profile_revision_id if firm.profile is not None else "defaults"
        )
        source_id = self._source_id(
            firm.firm.firm_id,
            artifact.artifact_id,
            revision_id,
            candidate_value,
            adapter_id,
        )
        source = SourceProfile(
            source_id=source_id,
            name=f"{firm.firm.canonical_name}: {artifact.label}",
            enabled=True,
            mechanism=registration.source_adapter.mechanism,
            configuration=candidate_value,
            policy={
                "firm_id": firm.firm.firm_id,
                "artifact_id": artifact.artifact_id,
                "source_profile_revision_id": revision_id,
                "retrieval_adapter_id": adapter_id,
                "document_id": f"document-{firm.firm.firm_id}-{artifact.artifact_id}",
            },
        )
        try:
            self._acquisition.register_source(source)
            engine = AcquisitionEngine(
                self._acquisition,
                self._adapters.acquisition_registry(adapter_id),
                self._clock,
            )
            result = engine.run_source(
                source_id,
                "workflow-"
                f"{workflow_run_id.removeprefix('pull-')}-{candidate.priority}",
            )
            artifact_ids = self._artifact_ids(result)
            outcome = self._engine_outcome(result)
            diagnostic = self._engine_diagnostic(result, outcome)
            details = self._attempt_details(result, adapter_id)
            attempt = RetrievalAttemptResult(
                candidate.mode,
                candidate.priority,
                adapter_id,
                result.run_id,
                result.status.value,
                diagnostic,
                artifact_ids,
                details,
            )
            return attempt, outcome
        except Exception as error:
            return (
                RetrievalAttemptResult(
                    candidate.mode,
                    candidate.priority,
                    adapter_id,
                    None,
                    "failed",
                    str(error),
                    details={"adapter_id": adapter_id},
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

    def _attempt_details(self, result: Any, adapter_id: str) -> dict[str, Any]:
        attempt_ids = {item.attempt_id for item in result.outcomes if item.attempt_id}
        records = [
            record
            for record in self._acquisition.history()
            if record.get("attempt_id") in attempt_ids
            and record.get("record_type") == "retrieval_attempt"
        ]
        documents = sorted(
            {str(record["document_id"]) for record in records if record.get("document_id")}
        )
        candidates = sorted(
            {str(record["candidate_id"]) for record in records if record.get("candidate_id")}
        )
        provenance = []
        for record in records:
            candidate = record.get("candidate", {})
            discovery = candidate.get("provenance", {}) if isinstance(candidate, dict) else {}
            provenance.append(
                {
                    "document_id": record.get("document_id"),
                    "candidate_id": record.get("candidate_id"),
                    "provider_identifiers": discovery.get("provider_identifiers", {}),
                    "locations": discovery.get("locations", []),
                    "metadata": discovery.get("metadata", {}),
                    "retrieval_provider_identifiers": record.get(
                        "retrieval_provider_identifiers", {}
                    ),
                    "retrieval_diagnostics": record.get("diagnostics", {}),
                }
            )
        return {
            "adapter_id": adapter_id,
            "document_ids": documents,
            "candidate_ids": candidates,
            "provenance": provenance,
            "engine_diagnostics": list(result.diagnostics),
        }

    @staticmethod
    def _engine_outcome(result: Any) -> ArtifactOutcome:
        if result.durable_acquisitions:
            return (
                ArtifactOutcome.SUCCESS_WITH_WARNINGS
                if PullWorkflow._engine_has_warnings(result)
                else ArtifactOutcome.SUCCESS
            )
        if result.failures or result.status != RunStatus.COMPLETE:
            return ArtifactOutcome.RETRIEVAL_FAILURE
        if result.duplicates:
            return ArtifactOutcome.DUPLICATE
        if PullWorkflow._has_checkpoint_decision(result) or result.unchanged:
            return ArtifactOutcome.NO_CHANGE
        coverage = PullWorkflow._engine_coverage(result)
        if coverage == "complete":
            return ArtifactOutcome.NO_CHANGE
        return ArtifactOutcome.INDETERMINATE

    @staticmethod
    def _engine_has_warnings(result: Any) -> bool:
        if result.failures or result.status != RunStatus.COMPLETE:
            return True
        for diagnostic in result.diagnostics:
            if int(diagnostic.get("discovery_failures", 0) or 0) > 0:
                return True
            for key in (
                "discovery_failure_counts",
                "candidate_retrieval_failure_counts",
                "validation_failure_counts",
            ):
                counts = diagnostic.get(key)
                if isinstance(counts, dict) and any(int(value) > 0 for value in counts.values()):
                    return True
        return False

    @staticmethod
    def _engine_coverage(result: Any) -> str | None:
        """Aggregate page diagnostics without inventing adapter-specific semantics."""
        coverage = None
        for diagnostic in result.diagnostics:
            if (
                diagnostic.get("bounds_exhausted") is True
                or bool(diagnostic.get("exhausted_budget"))
                or diagnostic.get("coverage") == "indeterminate"
            ):
                return "indeterminate"
            if diagnostic.get("coverage") == "incomplete":
                coverage = "incomplete"
            elif diagnostic.get("coverage") == "complete" and coverage is None:
                coverage = "complete"
        return coverage

    @staticmethod
    def _has_checkpoint_decision(result: Any) -> bool:
        return result.checkpoint_before is not None and any(
            outcome.outcome == "checkpoint_filtered" for outcome in result.outcomes
        )

    @staticmethod
    def _engine_diagnostic(result: Any, outcome: ArtifactOutcome) -> str:
        if outcome == ArtifactOutcome.SUCCESS:
            return "Retrieved and ingested through repository ingress."
        if outcome == ArtifactOutcome.SUCCESS_WITH_WARNINGS:
            count = int(result.durable_acquisitions)
            return (
                f"Retrieved and ingested {count} artifact"
                f"{'s' if count != 1 else ''} with warnings; earlier discovery and "
                "candidate diagnostics remain available for review."
            )
        if outcome == ArtifactOutcome.RETRIEVAL_FAILURE:
            messages = [
                str(item.get("message"))
                for item in result.diagnostics if item.get("message")
            ]
            if messages:
                return "; ".join(dict.fromkeys(messages))
        summaries = [
            str(item.get("operator_summary"))
            for item in result.diagnostics if item.get("operator_summary")
        ]
        if summaries:
            return "; ".join(dict.fromkeys(summaries))
        if outcome == ArtifactOutcome.INDETERMINATE:
            return (
                "No new artifact was acquired, but discovery did not conclusively establish "
                "that none exists because configured bounds were exhausted or coverage "
                "remained indeterminate."
            )
        if outcome == ArtifactOutcome.NO_CHANGE:
            if PullWorkflow._has_checkpoint_decision(result):
                return "Source checkpoint indicates no new artifact."
            if result.unchanged:
                return "Artifact ingress was unchanged; no new artifact was recorded."
            return "Discovery completed conclusively and found no new artifact."
        messages = [
            str(item.get("message"))
            for item in result.diagnostics
            if item.get("message")
        ]
        if messages:
            return "; ".join(messages)
        return {
            ArtifactOutcome.DUPLICATE: "Exact artifact bytes already exist in immutable storage.",
            ArtifactOutcome.RETRIEVAL_FAILURE: "Retrieval did not complete.",
        }[outcome]

    def _complete_stage(self, record: dict[str, Any], stage: PullStage) -> None:
        record["current_stage"] = stage.value
        if stage.value not in record["completed_stages"]:
            record["completed_stages"].append(stage.value)
            record["stage_events"].append(
                {"stage": stage.value, "completed_at": self._clock()}
            )
        percent, message = {
            PullStage.RECEIVED: (5, "Pull request received."),
            PullStage.FIRMS_RESOLVED: (10, "Resolved the selected firms."),
            PullStage.REVISIONS_SNAPSHOTTED: (15, "Saved the source-profile revisions."),
            PullStage.ARTIFACTS_EXPANDED: (20, "Expanded the enabled sources."),
            PullStage.ATTEMPTABILITY_DETERMINED: (25, "Checked which sources can run."),
            PullStage.RETRIEVAL_EXECUTED: (90, "Finished retrieving enabled sources."),
            PullStage.ARTIFACTS_INGESTED: (93, "Confirmed repository ingestion."),
            PullStage.RESULTS_RECORDED: (97, "Recorded source results."),
            PullStage.SUMMARIZED: (100, "Pull workflow complete."),
        }[stage]
        current = record.get("progress", {})
        self._set_progress(
            record,
            percent,
            message,
            int(current.get("completed_artifacts", 0)),
            int(current.get("total_artifacts", 0)),
            save=False,
        )
        self._runs.save(record["run_id"], record)

    @staticmethod
    def _retrieval_percent(completed: int, total: int) -> int:
        """Allocate the long-running retrieval stage across 25–90 percent."""
        if total <= 0:
            return 90
        return 25 + round(65 * completed / total)

    def _set_progress(
        self,
        record: dict[str, Any],
        percent: int,
        message: str,
        completed_artifacts: int,
        total_artifacts: int,
        *,
        save: bool = True,
    ) -> None:
        record["progress"] = {
            "percent": max(0, min(100, percent)),
            "message": message,
            "completed_artifacts": completed_artifacts,
            "total_artifacts": total_artifacts,
            "updated_at": self._clock(),
        }
        if save:
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

    def _plan_record(self, plan: PlannedFirm) -> dict[str, Any]:
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
                    "adapter_selections": [
                        {
                            "priority": value.priority,
                            "adapter_id": plan_adapter.capability.adapter_id,
                        }
                        for value in item.runnable_candidates
                        for plan_adapter in self._adapters.compatible(
                            item.artifact_id, value
                        )
                    ],
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
        adapter_id: str,
    ) -> str:
        payload = json.dumps(
            {
                "firm_id": firm_id,
                "artifact_id": artifact_id,
                "revision_id": revision_id,
                "candidate": candidate,
                "adapter_id": adapter_id,
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
            counts[ArtifactOutcome.SUCCESS_WITH_WARNINGS],
            counts[ArtifactOutcome.DUPLICATE],
            counts[ArtifactOutcome.NO_CHANGE],
            counts[ArtifactOutcome.INDETERMINATE],
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
                        item.get("adapter_id", item["mode"]),
                        item["acquisition_run_id"],
                        item["status"],
                        item["diagnostic"],
                        tuple(item.get("artifact_ids", ())),
                        item.get("details"),
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
            PullSummary(**{
                "indeterminate": 0,
                "success_with_warnings": 0,
                **record["summary"],
            }),
            tuple(record["diagnostics"]),
        )
