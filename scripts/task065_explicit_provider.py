#!/usr/bin/env python3
"""Deterministic operator proof for TASK-065 explicit provider selection."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from rfi.acquisition import (
    AcquisitionEngine,
    AcquisitionRepository,
    AdapterRegistry,
    EarningsTranscriptHttpResponse,
    SourceProfile,
    TranscriptAcquisitionTarget,
)
from rfi.acquisition.contracts import ContractError
from rfi.discovery import (
    DiscoveryPolicy,
    DiscoveryPolicyCatalog,
    EarningsTranscriptPullAdapter,
)
from rfi.firms import FirmRepository
from rfi.firms.contracts import FirmDraft, FirmStatus


DOCUMENT_URL = "https://stockanalysis.com/stocks/orcl/transcripts/592465-q4-2026/"
DOCUMENT = (
    Path(__file__).resolve().parents[1]
    / "fixtures/transcripts/stockanalysis-orcl-q4-2026.html"
).read_bytes()


class Transport:
    def get(self, url: str) -> EarningsTranscriptHttpResponse:
        if url != DOCUMENT_URL:
            raise RuntimeError(f"unexpected proof URL: {url}")
        return EarningsTranscriptHttpResponse(url, 200, "text/html", DOCUMENT)


def proof() -> dict[str, object]:
    profile = SourceProfile(
        "source-oracle-transcript", "Oracle transcripts", True,
        "earnings_transcript",
        {
            "mode": "discovery",
            "provider": "stockanalysis",
            "discovery_hint_kind": "provider_identifier",
            "discovery_hint_value": "ORCL",
            "discovery_class": "standard",
            "discovery_hints": [],
        },
        {
            "firm_id": "oracle",
            "artifact_id": "earnings_transcript",
            "retrieval_adapter_id": "earnings-call-transcript",
        },
    )
    policies = DiscoveryPolicyCatalog(
        {"standard": DiscoveryPolicy(1, 5, 1000, 2, 20, 8, 2_000_000, 60)},
        "standard",
    )
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        firms = FirmRepository.initialize(root / "firms")
        firms.create(FirmDraft(
            "oracle", "Oracle Corporation", "2026-01-01",
            status=FirmStatus.ACTIVE,
        ))
        repository = AcquisitionRepository(root / "acquisition")
        repository.register_source(profile)
        adapter = EarningsTranscriptPullAdapter(
            policies,
            transport=Transport(),
            repository=repository,
            clock=lambda: "2026-08-04T00:00:00+00:00",
        )
        target = TranscriptAcquisitionTarget("oracle")
        trial = adapter.injected_trial(
            profile, target, "stockanalysis", DOCUMENT_URL
        )
        result = AcquisitionEngine(
            repository, AdapterRegistry((adapter,)),
            lambda: "2026-08-04T00:00:00+00:00",
        ).run_source_trial(profile.source_id, "task065-proof", trial)
        learning = repository.transcript_learning("oracle")
        if not learning:
            raise RuntimeError(
                f"proof acquisition did not persist learning: {result.to_dict()}"
            )
        revision = repository.repository_revision()
        repository.transcript_learning("oracle")
        read_only = repository.repository_revision() == revision
        unknown_rejected = False
        try:
            adapter.injected_trial(profile, target, "unknown", DOCUMENT_URL)
        except ContractError:
            unknown_rejected = True
    evidence = {
        "adapter_id": adapter.adapter_id,
        "registry": adapter._provider_registry.registrations(),
        "selected_provider": trial.provider,
        "trial_seed_source": trial.seed_source,
        "starting_seed": trial.starting_seed,
        "durable_acquisitions": result.durable_acquisitions,
        "persisted_learning_provider": learning[0]["provider"],
        "learning_inspection_read_only": read_only,
        "unknown_provider_rejected_before_transport": unknown_rejected,
    }
    if not all((
        evidence["adapter_id"] == "earnings-call-transcript",
        evidence["selected_provider"] == "stockanalysis",
        evidence["trial_seed_source"] == "operator_supplied",
        evidence["durable_acquisitions"] == 1,
        evidence["persisted_learning_provider"] == "stockanalysis",
        evidence["learning_inspection_read_only"],
        evidence["unknown_provider_rejected_before_transport"],
    )):
        raise RuntimeError("TASK-065 explicit-provider proof failed")
    return evidence


if __name__ == "__main__":
    print(json.dumps(proof(), indent=2, sort_keys=True))
