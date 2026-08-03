"""Focused acceptance evidence for TASK-058 transcript acquisition orchestration."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from rfi.acquisition import (
    AcquisitionEngine,
    AcquisitionRepository,
    AdapterRegistry,
    EarningsTranscriptHttpResponse,
    RunStatus,
    SourceProfile,
)
from rfi.acquisition.earnings_transcripts import ReportingPeriod
from rfi.discovery import (
    DiscoveryPolicy,
    DiscoveryPolicyCatalog,
    DiscoverySearchResponse,
    EarningsTranscriptPullAdapter,
)
from rfi.firms import FirmRepository
from rfi.firms.contracts import FirmDraft, FirmStatus


class Search:
    endpoint = "https://search.example/results"

    def __init__(self) -> None:
        self.calls: list[str] = []

    def search(self, query: str, limit: int) -> DiscoverySearchResponse:
        self.calls.append(query)
        return DiscoverySearchResponse((), 0)


class Transport:
    def __init__(self, responses: dict[str, EarningsTranscriptHttpResponse | Exception]):
        self.responses = responses
        self.requests: list[str] = []

    def get(self, url: str) -> EarningsTranscriptHttpResponse:
        self.requests.append(url)
        value = self.responses[url]
        if isinstance(value, Exception):
            raise value
        return value


def response(url: str, body: str, status: int = 200) -> EarningsTranscriptHttpResponse:
    return EarningsTranscriptHttpResponse(
        url, status, "text/html", f"<html>{body}</html>".encode()
    )


def source(*hints: str) -> SourceProfile:
    return SourceProfile(
        "source-a", "Firm A transcripts", True, "earnings_transcript",
        {
            "mode": "discovery",
            "discovery_class": "standard",
            "discovery_hints": list(hints),
        },
        {
            "firm_id": "firm-a",
            "artifact_id": "earnings_transcript",
            "retrieval_adapter_id": "earnings-call-transcript",
        },
    )


def policies() -> DiscoveryPolicyCatalog:
    return DiscoveryPolicyCatalog(
        {"standard": DiscoveryPolicy(2, 5, 1000, 2, 20, 8, 2_000_000, 60)},
        "standard",
    )


class TranscriptAcquisitionOrchestrationTests(unittest.TestCase):
    def test_orchestrator_preserves_learned_order_then_existing_fallback_pipeline(self) -> None:
        learned = (
            {
                "normalized_url": "https://ir.example.com/new",
                "resolved_url": "https://cdn.example.com/new",
                "requested_url": "https://ir.example.com/new",
            },
            {
                "normalized_url": "https://ir.example.com/old",
                "resolved_url": None,
                "requested_url": "https://ir.example.com/old",
            },
        )
        configured = source(
            "https://ir.example.com/transcripts", "identity:Firm A"
        )
        with tempfile.TemporaryDirectory() as directory:
            firms = FirmRepository.initialize(Path(directory) / "firms")
            firms.create(FirmDraft(
                "firm-a", "Firm A", "2026-01-01", status=FirmStatus.ACTIVE
            ))
            repository = AcquisitionRepository(Path(directory) / "acquisition")
            adapter = EarningsTranscriptPullAdapter(
                policies(), Search(), Transport({}),
                lambda: "2026-08-01T00:00:00Z", repository=repository,
            )
            with patch.object(repository, "discovery_anchors", return_value=learned):
                trials = adapter.acquisition_trials(configured)

        self.assertEqual(
            [(item.seed_kind, item.seed_source, item.starting_seed) for item in trials],
            [
                ("single_seed", "learned", "https://cdn.example.com/new"),
                ("single_seed", "learned", "https://ir.example.com/new"),
                ("single_seed", "learned", "https://ir.example.com/old"),
                (
                    "configured_pipeline",
                    "configured",
                    "https://ir.example.com/transcripts",
                ),
            ],
        )
        self.assertEqual(len({item.trial_id for item in trials}), len(trials))

    def test_failed_learned_trial_advances_only_orchestration_and_success_stops_fifo(self) -> None:
        failed = "https://ir.example.com/archive-one"
        successful = "https://ir.example.com/archive-two"
        unexecuted = "https://ir.example.com/archive-three"
        failed_candidate = (
            "https://ir.example.com/q1-2026-earnings-call-transcript.html"
        )
        successful_candidate = (
            "https://ir.example.com/q2-2026-earnings-call-transcript.html"
        )
        learned = tuple(
            {
                "normalized_url": url,
                "resolved_url": None,
                "requested_url": url,
            }
            for url in (failed, successful, unexecuted)
        )
        transport = Transport({
            failed: response(
                failed,
                f"<a href='{failed_candidate}'>Q1 2026 earnings call transcript</a>",
            ),
            failed_candidate: response(failed_candidate, "not found", 404),
            successful: response(
                successful,
                f"<a href='{successful_candidate}'>Q2 2026 earnings call transcript</a>",
            ),
            successful_candidate: response(
                successful_candidate,
                "Firm A quarterly earnings call transcript April 30, 2026. "
                "Operator. Chief Executive Officer. Prepared remarks.",
            ),
            unexecuted: AssertionError("orchestration did not stop after validation"),
        })
        configured = source("https://configured.example/transcripts")

        with tempfile.TemporaryDirectory() as directory:
            firms = FirmRepository.initialize(Path(directory) / "firms")
            firms.create(FirmDraft(
                "firm-a", "Firm A", "2026-01-01", status=FirmStatus.ACTIVE
            ))
            repository = AcquisitionRepository(Path(directory) / "acquisition")
            repository.register_source(configured)
            adapter = EarningsTranscriptPullAdapter(
                policies(), Search(), transport,
                lambda: "2026-08-01T00:00:00Z", repository=repository,
            )
            with patch.object(repository, "discovery_anchors", return_value=learned):
                result = AcquisitionEngine(
                    repository, AdapterRegistry((adapter,)),
                    lambda: "2026-08-01T00:00:00Z",
                ).run_source(configured.source_id, "task058-fifo")
            retained = repository.discovery_anchors(
                "firm-a", configured.source_id, adapter.adapter_id
            )

        self.assertEqual(
            result.status, RunStatus.COMPLETE, json.dumps(result.to_dict(), indent=2)
        )
        self.assertEqual(result.durable_acquisitions, 1)
        self.assertEqual(result.failures, 1)
        self.assertEqual(
            transport.requests,
            [failed, failed_candidate, successful, successful_candidate],
        )
        self.assertNotIn(unexecuted, transport.requests)
        trial_diagnostics = [
            item for item in result.diagnostics if "trial_id" in item
        ]
        self.assertEqual(len(trial_diagnostics), 2)
        self.assertEqual(
            [item["trial_outcome"] for item in trial_diagnostics],
            ["failed", "validated_success"],
        )
        self.assertEqual(
            trial_diagnostics[-1]["acquisition_termination_reason"],
            "first_validated_success",
        )
        self.assertEqual(len(retained), 1)
        self.assertEqual(retained[0]["requested_url"], successful_candidate)
        self.assertEqual(
            result.checkpoint_after.position,
            ReportingPeriod.parse("2026-Q2").ordinal,
        )

    def test_exhausted_failed_trials_never_learn_or_advance_checkpoint(self) -> None:
        first = "https://ir.example.com/q1-2026-earnings-call-transcript.html"
        second = "https://ir.example.com/q2-2026-earnings-call-transcript.html"
        learned = tuple(
            {"normalized_url": url, "resolved_url": None, "requested_url": url}
            for url in (first, second)
        )
        transport = Transport({
            first: TimeoutError("first failed"),
            second: TimeoutError("second failed"),
        })
        configured = source()
        with tempfile.TemporaryDirectory() as directory:
            repository = AcquisitionRepository(Path(directory) / "acquisition")
            repository.register_source(configured)
            adapter = EarningsTranscriptPullAdapter(
                policies(), Search(), transport,
                lambda: "2026-08-01T00:00:00Z", repository=repository,
            )
            with patch.object(repository, "discovery_anchors", return_value=learned):
                result = AcquisitionEngine(
                    repository, AdapterRegistry((adapter,)),
                    lambda: "2026-08-01T00:00:00Z",
                ).run_source(configured.source_id, "task058-exhausted")
            retained = repository.discovery_anchors(
                "firm-a", configured.source_id, adapter.adapter_id
            )

        self.assertEqual(result.durable_acquisitions, 0)
        self.assertIsNone(result.checkpoint_after)
        self.assertEqual(retained, ())
        trial_diagnostics = [item for item in result.diagnostics if "trial_id" in item]
        self.assertEqual(
            sum(item["seed_source"] == "learned" for item in trial_diagnostics), 2
        )
        self.assertEqual(len(trial_diagnostics), 3)
        self.assertEqual(
            trial_diagnostics[-1]["acquisition_termination_reason"],
            "seed_trials_exhausted",
            json.dumps(result.to_dict(), indent=2),
        )


if __name__ == "__main__":
    unittest.main()
