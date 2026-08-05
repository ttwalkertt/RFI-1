#!/usr/bin/env python3
"""Deterministic operator proof for TASK-065 explicit provider selection."""

from __future__ import annotations

import json

from rfi.acquisition import SourceProfile, TranscriptAcquisitionTarget
from rfi.acquisition.contracts import ContractError
from rfi.discovery import (
    DiscoveryPolicy,
    DiscoveryPolicyCatalog,
    EarningsTranscriptPullAdapter,
)


DOCUMENT_URL = "https://stockanalysis.com/stocks/orcl/transcripts/592465-q4-2026/"


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
        {"firm_id": "oracle", "artifact_id": "earnings_transcript"},
    )
    policies = DiscoveryPolicyCatalog(
        {"standard": DiscoveryPolicy(1, 5, 1000, 2, 20, 8, 2_000_000, 60)},
        "standard",
    )
    adapter = EarningsTranscriptPullAdapter(policies)
    target = TranscriptAcquisitionTarget("oracle")
    trial = adapter.injected_trial(
        profile, target, "stockanalysis", DOCUMENT_URL
    )
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
        "unknown_provider_rejected_before_transport": unknown_rejected,
    }
    if not all((
        evidence["adapter_id"] == "earnings-call-transcript",
        evidence["selected_provider"] == "stockanalysis",
        evidence["trial_seed_source"] == "operator_supplied",
        evidence["unknown_provider_rejected_before_transport"],
    )):
        raise RuntimeError("TASK-065 explicit-provider proof failed")
    return evidence


if __name__ == "__main__":
    print(json.dumps(proof(), indent=2, sort_keys=True))
