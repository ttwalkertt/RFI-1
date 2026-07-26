"""SEC-specific authoritative retrieval workflow façade."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Callable

from rfi.acquisition import (
    AcquisitionEngine, AcquisitionRepository, AdapterRegistry, SourceProfile,
)
from rfi.acquisition.sec_form_10k import SecForm10KAdapter
from rfi.firms.contracts import FirmCatalog
from rfi.sec.contracts import (
    SecApplicability, SecIdentityResolver, SecSourceKnowledge, SecWorkflowOutcome,
    SecWorkflowResult, SecWorkflowState,
)
from rfi.sec.repository import SecRepository


def utc_now() -> str:
    return datetime.now(UTC).isoformat()


class SecRetrievalWorkflow:
    """Complete bounded Form 10-K workflow with explicit durable transitions."""

    def __init__(
        self, firms: FirmCatalog, repository: SecRepository,
        acquisition: AcquisitionRepository, resolver: SecIdentityResolver,
        adapter: SecForm10KAdapter, clock: Callable[[], str] = utc_now,
        identifier_factory: Callable[[], str] = lambda: uuid.uuid4().hex,
        verification_ttl: timedelta = timedelta(days=30),
    ) -> None:
        self._firms = firms
        self._repository = repository
        self._acquisition = acquisition
        self._resolver = resolver
        self._adapter = adapter
        self._clock = clock
        self._identifier_factory = identifier_factory
        self._verification_ttl = verification_ttl

    def initiate(self, firm_id: str) -> str:
        firm = self._firms.get(firm_id)
        run_id = f"sec-{self._identifier_factory()}"
        now = self._clock()
        self._repository.create_run({
            "schema_version": 1, "run_id": run_id, "firm_id": firm.firm_id,
            "outcome": "running", "current_state": SecWorkflowState.RECEIVED.value,
            "requested_at": now, "completed_at": "", "cancellation_requested": False,
            "source_bootstrapped": False, "source_refreshed": False,
            "artifact_ids": [], "states": [SecWorkflowState.RECEIVED.value],
            "diagnostics": [],
        })
        return run_id

    def cancel(self, run_id: str) -> None:
        self._repository.cancel(run_id)

    def run(self, firm_id: str) -> SecWorkflowResult:
        return self.execute(self.initiate(firm_id))

    def execute(self, run_id: str) -> SecWorkflowResult:
        record = self._repository.run(run_id)
        if record.get("completed_at"):
            return self._typed(record)
        try:
            if self._cancelled(record):
                return self._typed(record)
            firm = self._firms.get(record["firm_id"])
            self._transition(record, SecWorkflowState.APPLICABILITY_DETERMINED)
            existing = self._repository.source(firm.firm_id)
            self._transition(record, SecWorkflowState.SOURCE_LOADED)
            source = existing
            now = self._clock()
            if existing is None:
                resolution = self._resolver.resolve(firm, now)
                self._transition(record, SecWorkflowState.IDENTITY_RESOLVED)
                if resolution.source is None:
                    outcome = (SecWorkflowOutcome.SOURCE_AMBIGUITY if resolution.candidates
                               else SecWorkflowOutcome.SOURCE_AMBIGUITY)
                    return self._finish(record, outcome, resolution.diagnostic)
                source, _ = self._repository.persist_source(resolution.source, None)
                record["source_bootstrapped"] = True
                self._transition(record, SecWorkflowState.SOURCE_PERSISTED)
            elif self._stale(existing, now):
                resolution = self._resolver.validate(firm, existing, now)
                self._transition(record, SecWorkflowState.SOURCE_VALIDATED)
                if resolution.source is None:
                    return self._finish(record, SecWorkflowOutcome.SOURCE_AMBIGUITY,
                                        resolution.diagnostic)
                if self._identity(resolution.source) != self._identity(existing):
                    return self._finish(record, SecWorkflowOutcome.SOURCE_CONFLICT,
                                        resolution.diagnostic or "SEC identity conflict")
                source, _ = self._repository.persist_source(resolution.source, existing)
                record["source_refreshed"] = True
                self._transition(record, SecWorkflowState.SOURCE_PERSISTED)
            else:
                self._transition(record, SecWorkflowState.SOURCE_VALIDATED)
            assert source is not None
            if source.applicability == SecApplicability.NON_APPLICABLE:
                return self._finish(record, SecWorkflowOutcome.NON_APPLICABLE,
                                    "firm is verified as not SEC-applicable")
            if self._cancelled(record):
                return self._typed(record)
            self._transition(record, SecWorkflowState.FILING_POLICY_DETERMINED)
            source_id = f"source-sec-{firm.firm_id}-10k"
            profile = SourceProfile(
                source_id, f"{firm.canonical_name}: SEC Form 10-K", True,
                self._adapter.mechanism,
                {"mode": "identifier", "priority": 1, "locator": f"CIK:{source.cik}"},
                {"firm_id": firm.firm_id, "artifact_id": "sec_10k",
                 "source_profile_revision_id": "sec-authoritative",
                 "retrieval_adapter_id": self._adapter.adapter_id,
                 "document_id": f"document-{firm.firm_id}-sec_10k"},
            )
            self._acquisition.register_source(profile)
            engine = AcquisitionEngine(
                self._acquisition,
                AdapterRegistry((self._adapter,)), self._clock,
            )
            result = engine.run_source(source_id, f"workflow-{run_id.removeprefix('sec-')}")
            codes = {str(item.get("failure_code", "")) for item in result.diagnostics}
            if "no_eligible_form_10k" in codes:
                return self._finish(record, SecWorkflowOutcome.NO_QUALIFYING_FILING,
                                    "SEC issuer has no qualifying unamended Form 10-K")
            if result.status.value not in {"complete"}:
                diagnostic = "; ".join(
                    str(item.get("message", item)) for item in result.diagnostics
                )
                return self._finish(record, SecWorkflowOutcome.RETRIEVAL_FAILURE, diagnostic)
            self._transition(record, SecWorkflowState.FILINGS_ENUMERATED)
            self._transition(record, SecWorkflowState.FILING_SELECTED)
            self._transition(record, SecWorkflowState.DOCUMENT_RETRIEVED)
            self._transition(record, SecWorkflowState.RETRIEVAL_VALIDATED)
            attempt_ids = {item.attempt_id for item in result.outcomes if item.attempt_id}
            record["artifact_ids"] = sorted({
                str(item["artifact_id"]) for item in self._acquisition.history()
                if item.get("attempt_id") in attempt_ids and item.get("artifact_id")
            })
            if not record["artifact_ids"]:
                record["artifact_ids"] = sorted({
                    str(artifact_id)
                    for document in self._acquisition.document_index()["documents"].values()
                    if source_id in document["source_ids"]
                    for artifact_id in document["artifacts"]
                })
            self._transition(record, SecWorkflowState.ARTIFACT_INGESTED)
            outcome = (SecWorkflowOutcome.SUCCESS_WITH_SOURCE_BOOTSTRAP
                       if record["source_bootstrapped"] else SecWorkflowOutcome.SUCCESS)
            return self._finish(record, outcome, "SEC Form 10-K retrieval completed")
        except Exception as error:
            return self._finish(record, SecWorkflowOutcome.RETRIEVAL_FAILURE, str(error))

    def _cancelled(self, record: dict[str, object]) -> bool:
        current = self._repository.run(str(record["run_id"]))
        if not current.get("cancellation_requested"):
            return False
        record.update(current)
        self._finish(record, SecWorkflowOutcome.CANCELLED, "operator cancellation requested",
                     SecWorkflowState.CANCELLED)
        return True

    def _transition(self, record: dict[str, object], state: SecWorkflowState) -> None:
        record["current_state"] = state.value
        record["states"].append(state.value)  # type: ignore[union-attr]
        self._repository.save_run(record)

    def _finish(self, record: dict[str, object], outcome: SecWorkflowOutcome,
                diagnostic: str, state: SecWorkflowState = SecWorkflowState.COMPLETED
                ) -> SecWorkflowResult:
        record["outcome"] = outcome.value
        record["current_state"] = state.value
        if record["states"][-1] != state.value:  # type: ignore[index]
            record["states"].append(state.value)  # type: ignore[union-attr]
        record["completed_at"] = self._clock()
        if diagnostic:
            record["diagnostics"].append(diagnostic)  # type: ignore[union-attr]
        self._repository.save_run(record)
        return self._typed(record)

    def _stale(self, source: SecSourceKnowledge, now: str) -> bool:
        verified = datetime.fromisoformat(source.verified_at.replace("Z", "+00:00"))
        current = datetime.fromisoformat(now.replace("Z", "+00:00"))
        return current - verified >= self._verification_ttl

    @staticmethod
    def _identity(source: SecSourceKnowledge) -> tuple[object, ...]:
        return source.applicability, source.cik, source.parent_firm_id

    @staticmethod
    def _typed(record: dict[str, object]) -> SecWorkflowResult:
        return SecWorkflowResult(
            str(record["run_id"]), str(record["firm_id"]),
            SecWorkflowOutcome(str(record["outcome"])),
            SecWorkflowState(str(record["current_state"])),
            str(record["requested_at"]), str(record["completed_at"]),
            bool(record["source_bootstrapped"]), bool(record["source_refreshed"]),
            tuple(str(x) for x in record["artifact_ids"]),  # type: ignore[union-attr]
            tuple(SecWorkflowState(str(x)) for x in record["states"]),  # type: ignore[union-attr]
            tuple(str(x) for x in record["diagnostics"]),  # type: ignore[union-attr]
        )
