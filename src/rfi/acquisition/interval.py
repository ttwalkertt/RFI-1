"""Narrow application integration for completed date-delimited acquisitions."""

from __future__ import annotations

import hashlib
import uuid
from collections.abc import Callable

from rfi.acquisition.contracts import (
    ContractError,
    IntervalAcquisitionRequest,
    IntervalAcquisitionResult,
    IntervalOutcomeReceipt,
)
from rfi.acquisition.repository import AcquisitionRepository
from rfi.firms.contracts import FirmCatalog
from rfi.source_profiles.contracts import AcquisitionTemplate
from rfi.storage.sqlite import canonical_json, utc_now


class IntervalAcquisitionService:
    """Apply canonical firm/artifact policy and persist a completed result."""

    def __init__(
        self,
        firms: FirmCatalog,
        template: AcquisitionTemplate,
        repository: AcquisitionRepository,
        clock: Callable[[], str] = utc_now,
        identifier_factory: Callable[[], str] = lambda: uuid.uuid4().hex,
    ) -> None:
        self._firms = firms
        self._artifact_ids = frozenset(item.artifact_id for item in template.artifacts)
        self._repository = repository
        self._clock = clock
        self._identifier_factory = identifier_factory

    def record(
        self,
        request: IntervalAcquisitionRequest,
        result: IntervalAcquisitionResult,
    ) -> IntervalOutcomeReceipt:
        """Ingest successes through existing repository ingress, then record coverage."""
        self._firms.get(request.firm_id)
        if request.artifact_type not in self._artifact_ids:
            raise ContractError(f"unknown canonical artifact type: {request.artifact_type}")
        for envelope in result.artifacts:
            if not request.contains(envelope.artifact_date):
                raise ContractError(
                    "successful artifact date lies outside the requested interval"
                )
            source = self._repository.source(envelope.candidate.source_id)
            policy = source.get("policy", {})
            if policy.get("firm_id") != request.firm_id:
                raise ContractError("artifact source policy does not match requested firm")
            if policy.get("artifact_id") != request.artifact_type:
                raise ContractError("artifact source policy does not match requested type")
        outcome_id = f"intervaloutcome-{self._identifier_factory()}"
        receipts = []
        for ordinal, envelope in enumerate(result.artifacts):
            identity = canonical_json(
                {
                    "outcome_id": outcome_id,
                    "ordinal": ordinal,
                    "candidate_id": envelope.candidate.candidate_id,
                }
            ).encode()
            attempt_id = f"intervalattempt-{hashlib.sha256(identity).hexdigest()}"
            receipts.append(
                self._repository.record_success(
                    attempt_id, envelope.candidate, envelope.retrieval
                )
            )
        return self._repository.record_interval_outcome(
            outcome_id, request, result, tuple(receipts), self._clock()
        )
