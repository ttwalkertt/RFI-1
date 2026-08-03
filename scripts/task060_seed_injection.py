#!/usr/bin/env python3
"""Deterministic manual evidence for TASK-060 operator seed injection."""

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
from rfi.discovery import (
    DiscoveryPolicy,
    DiscoveryPolicyCatalog,
    DiscoverySearchResponse,
    EarningsTranscriptPullAdapter,
)
from rfi.firms import FirmRepository
from rfi.firms.contracts import FirmDraft, FirmStatus


class NoSearch:
    endpoint = "https://search.example/results"

    def search(self, query: str, limit: int) -> DiscoverySearchResponse:
        del query, limit
        return DiscoverySearchResponse((), 0)


class FixtureTransport:
    def __init__(self, responses: dict[str, EarningsTranscriptHttpResponse]) -> None:
        self.responses = responses
        self.requests: list[str] = []

    def get(self, url: str) -> EarningsTranscriptHttpResponse:
        self.requests.append(url)
        return self.responses[url]


def proof() -> dict[str, object]:
    seed = "https://ir.example.com/archive"
    selected = "https://ir.example.com/q2-2026-earnings-call-transcript.html"
    responses = {
        seed: EarningsTranscriptHttpResponse(
            seed, 200, "text/html",
            f"<a href='{selected}'>April 30, 2026 earnings call transcript</a>".encode(),
        ),
        selected: EarningsTranscriptHttpResponse(
            selected, 200, "text/html",
            b"<html>Firm A quarterly earnings call transcript April 30, 2026. "
            b"Operator. Chief Executive Officer. Prepared remarks.</html>",
        ),
    }
    profile = SourceProfile(
        "source-a", "Firm A transcripts", True, "earnings_transcript",
        {
            "mode": "discovery",
            "discovery_class": "standard",
            "discovery_hints": [],
        },
        {
            "firm_id": "firm-a",
            "artifact_id": "earnings_transcript",
            "retrieval_adapter_id": "earnings-call-transcript",
        },
    )
    policy = DiscoveryPolicyCatalog(
        {"standard": DiscoveryPolicy(1, 5, 1000, 2, 20, 8, 2_000_000, 60)},
        "standard",
    )
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        firms = FirmRepository.initialize(root / "firms")
        firms.create(FirmDraft(
            "firm-a", "Firm A", "2025-01-01", status=FirmStatus.ACTIVE
        ))
        repository = AcquisitionRepository(root / "acquisition")
        repository.register_source(profile)
        transport = FixtureTransport(responses)
        adapter = EarningsTranscriptPullAdapter(
            policy, NoSearch(), transport, lambda: "2026-08-03T00:00:00Z",
            repository=repository,
        )
        engine = AcquisitionEngine(
            repository, AdapterRegistry((adapter,)),
            lambda: "2026-08-03T00:00:00Z",
        )
        target = TranscriptAcquisitionTarget("firm-a")
        ordinary_before = engine.run_source("source-a", "ordinary-before")
        trial = adapter.injected_trial(profile, target, seed)
        result = engine.run_source_trial("source-a", "manual-proof", trial)
        successful = [
            item for item in repository.history()
            if item.get("record_type") == "retrieval_attempt"
            and item.get("outcome") == "success"
        ]
        anchors = repository.discovery_anchors(
            "firm-a", "source-a", "earnings-call-transcript"
        )
        history = repository.history()
        artifacts = repository.artifact_metadata()
        checkpoint = result.checkpoint_after
        learned_replay = engine.run_source("source-a", "ordinary-learned")
        injected_replay = engine.run_source_trial(
            "source-a", "injected-replay", adapter.injected_trial(profile, target, seed)
        )
        trial_diagnostics = [
            item for item in result.diagnostics if item.get("trial_id")
        ]
        evidence = {
            "result": result.status.value,
            "ordinary_before": ordinary_before.status.value,
            "ordinary_before_durable": ordinary_before.durable_acquisitions,
            "trial_count": len(trial_diagnostics),
            "seed_kind": trial_diagnostics[0]["seed_kind"],
            "seed_source": trial_diagnostics[0]["seed_source"],
            "effective_selection": target.selection.to_dict(),
            "supplied_seed": seed,
            "selected_artifact_url": successful[0]["candidate"]["provenance"][
                "locations"
            ][-1],
            "selected_url_differs_from_seed": seed != selected,
            "request_sequence": transport.requests,
            "durable_acquisitions": result.durable_acquisitions,
            "checkpoint_advanced": result.checkpoint_after is not None,
            "learned_anchor_count": len(anchors),
            "learned_anchor_is_validated_artifact": (
                len(anchors) == 1 and anchors[0]["normalized_url"] == selected
            ),
            "learned_replay": learned_replay.status.value,
            "learned_replay_unchanged": learned_replay.unchanged,
            "injected_replay": injected_replay.status.value,
            "injected_replay_unchanged": injected_replay.unchanged,
            "replay_checkpoint_unchanged": (
                checkpoint is not None
                and learned_replay.checkpoint_before == checkpoint
                and learned_replay.checkpoint_after == checkpoint
                and injected_replay.checkpoint_before == checkpoint
                and injected_replay.checkpoint_after == checkpoint
            ),
            "replay_repository_unchanged": (
                repository.history() == history
                and repository.artifact_metadata() == artifacts
                and repository.discovery_anchors(
                    "firm-a", "source-a", "earnings-call-transcript"
                ) == anchors
            ),
        }
    if not all((
        evidence["result"] == "complete",
        evidence["ordinary_before"] == "complete",
        evidence["ordinary_before_durable"] == 0,
        evidence["trial_count"] == 1,
        evidence["seed_kind"] == "single_seed",
        evidence["seed_source"] == "operator_supplied",
        evidence["selected_url_differs_from_seed"],
        evidence["durable_acquisitions"] == 1,
        evidence["checkpoint_advanced"],
        evidence["learned_anchor_is_validated_artifact"],
        evidence["learned_replay"] == "complete",
        evidence["learned_replay_unchanged"] == 1,
        evidence["injected_replay"] == "complete",
        evidence["injected_replay_unchanged"] == 1,
        evidence["replay_checkpoint_unchanged"],
        evidence["replay_repository_unchanged"],
    )):
        raise RuntimeError("TASK-060 seed-injection proof failed")
    return evidence


if __name__ == "__main__":
    print(json.dumps(proof(), indent=2, sort_keys=True))
