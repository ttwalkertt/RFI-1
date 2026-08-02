"""Focused acceptance evidence for TASK-059 transcript selection contracts."""

from __future__ import annotations

import json
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import Mock, patch

from rfi.acquisition import (
    AcquisitionEngine,
    AcquisitionRepository,
    AdapterRegistry,
    EarningsTranscriptHttpResponse,
    SourceProfile,
    TranscriptAcquisitionSelection,
    TranscriptSelectionMode,
)
from rfi.acquisition.contracts import ContractError
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

    def search(self, query: str, limit: int) -> DiscoverySearchResponse:
        return DiscoverySearchResponse((), 0)


class Transport:
    def __init__(self, responses: dict[str, EarningsTranscriptHttpResponse]):
        self.responses = responses
        self.requests: list[str] = []

    def get(self, url: str) -> EarningsTranscriptHttpResponse:
        self.requests.append(url)
        return self.responses[url]


def response(url: str, body: str) -> EarningsTranscriptHttpResponse:
    return EarningsTranscriptHttpResponse(
        url, 200, "text/html", f"<html>{body}</html>".encode()
    )


def transcript_body(event_date: str) -> str:
    return (
        f"Firm A quarterly earnings call transcript {event_date}. "
        "Operator. Chief Executive Officer. Prepared remarks."
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


class TranscriptSelectionContractTests(unittest.TestCase):
    def test_selection_contract_is_typed_and_bounded(self) -> None:
        with self.assertRaises(ContractError):
            TranscriptAcquisitionSelection("other")  # type: ignore[arg-type]
        with self.assertRaises(ContractError):
            TranscriptAcquisitionSelection.first_in_date_range(
                date(2025, 2, 1), date(2025, 1, 1)
            )
        with self.assertRaises(ContractError):
            TranscriptAcquisitionSelection(
                TranscriptSelectionMode.LATEST, date(2025, 1, 1), None
            )

    def test_omitted_selection_is_immutable_latest_for_every_trial(self) -> None:
        adapter = EarningsTranscriptPullAdapter(policies(), Search(), Transport({}))
        trials = adapter.acquisition_trials(source(
            "https://ir.example.com/transcripts", "identity:Firm A"
        ))

        self.assertTrue(trials)
        target = trials[0].acquisition_target
        self.assertTrue(all(item.acquisition_target is target for item in trials))
        self.assertEqual(target.selection.mode, TranscriptSelectionMode.LATEST)
        self.assertIsNone(target.selection.start_date)
        self.assertIsNone(target.selection.end_date)

    def test_starting_seed_changes_only_trial_seed_not_requested_selection(self) -> None:
        selection = TranscriptAcquisitionSelection.first_in_date_range(
            date(2025, 1, 1), date(2025, 12, 31)
        )
        adapter = EarningsTranscriptPullAdapter(
            policies(), Search(), Transport({}), selection=selection
        )
        adapter._repository = Mock()  # repository read seam only
        adapter._orchestrator._repository = adapter._repository
        adapter._repository.discovery_anchors.return_value = (
            {
                "normalized_url": "https://first.example/transcripts",
                "requested_url": "https://first.example/transcripts",
                "resolved_url": None,
            },
            {
                "normalized_url": "https://second.example/transcripts",
                "requested_url": "https://second.example/transcripts",
                "resolved_url": None,
            },
        )
        trials = adapter.acquisition_trials(source("https://configured.example/transcripts"))

        self.assertEqual({item.acquisition_target.selection for item in trials}, {selection})
        self.assertTrue(all(item.acquisition_target is trials[0].acquisition_target
                            for item in trials))
        self.assertNotEqual(trials[0].starting_seed, trials[-1].starting_seed)

    def test_first_in_range_selects_global_earliest_not_first_seed_result(self) -> None:
        first_seed = "https://ir.example.com/archive-later"
        second_seed = "https://ir.example.com/archive-earlier"
        later = "https://ir.example.com/q2-2025-earnings-call-transcript.html"
        earlier = "https://ir.example.com/q1-2025-earnings-call-transcript.html"
        transport = Transport({
            first_seed: response(
                first_seed, f"<a href='{later}'>April 30, 2025 earnings call transcript</a>"
            ),
            later: response(later, transcript_body("April 30, 2025")),
            second_seed: response(
                second_seed, f"<a href='{earlier}'>January 30, 2025 earnings call transcript</a>"
            ),
            earlier: response(earlier, transcript_body("January 30, 2025")),
        })
        configured = source()
        learned = tuple(
            {"normalized_url": value, "requested_url": value, "resolved_url": None}
            for value in (first_seed, second_seed)
        )
        selection = TranscriptAcquisitionSelection.first_in_date_range(
            date(2025, 1, 1), date(2025, 12, 31)
        )

        with tempfile.TemporaryDirectory() as directory:
            firms = FirmRepository.initialize(Path(directory) / "firms")
            firms.create(FirmDraft(
                "firm-a", "Firm A", "2025-01-01", status=FirmStatus.ACTIVE
            ))
            repository = AcquisitionRepository(Path(directory) / "acquisition")
            repository.register_source(configured)
            adapter = EarningsTranscriptPullAdapter(
                policies(), Search(), transport,
                lambda: "2026-08-01T00:00:00Z",
                repository=repository,
                selection=selection,
            )
            with patch.object(repository, "discovery_anchors", return_value=learned):
                result = AcquisitionEngine(
                    repository, AdapterRegistry((adapter,)),
                    lambda: "2026-08-01T00:00:00Z",
                ).run_source(configured.source_id, "task059-earliest")
            history = repository.history()

        self.assertEqual(result.durable_acquisitions, 1, json.dumps(result.to_dict(), indent=2))
        successes = [item for item in history if item.get("outcome") == "success"]
        self.assertEqual(len(successes), 1)
        metadata = successes[0]["candidate"]["provenance"]["metadata"]
        self.assertEqual(metadata["requested_url"], earlier)
        self.assertEqual(
            successes[0]["diagnostics"]["validated_event_date"], "2025-01-30"
        )
        terminal = next(
            item for item in result.diagnostics
            if item.get("terminal_selection_outcome") == "selected"
        )
        self.assertEqual(terminal["qualified_candidate_count"], 2)
        self.assertEqual(terminal["selected_validated_event_date"], "2025-01-30")
        self.assertEqual(
            [item["trial_outcome"] for item in result.diagnostics if "trial_id" in item],
            ["qualified_candidate", "qualified_candidate", "no_validated_artifact"],
        )

    def test_wrong_date_no_match_never_checkpoints_or_learns(self) -> None:
        seed = "https://ir.example.com/transcripts"
        wrong = "https://ir.example.com/q4-2024-earnings-call-transcript.html"
        transport = Transport({
            seed: response(
                seed, f"<a href='{wrong}'>December 15, 2024 earnings call transcript</a>"
            ),
            wrong: response(wrong, transcript_body("December 15, 2024")),
        })
        configured = source(seed)
        selection = TranscriptAcquisitionSelection.first_in_date_range(
            date(2025, 1, 1), date(2025, 3, 31)
        )

        with tempfile.TemporaryDirectory() as directory:
            repository = AcquisitionRepository(Path(directory) / "acquisition")
            repository.register_source(configured)
            adapter = EarningsTranscriptPullAdapter(
                policies(), Search(), transport,
                lambda: "2026-08-01T00:00:00Z",
                repository=repository,
                selection=selection,
            )
            result = AcquisitionEngine(
                repository, AdapterRegistry((adapter,)),
                lambda: "2026-08-01T00:00:00Z",
            ).run_source(configured.source_id, "task059-no-match")
            retained = repository.discovery_anchors(
                "firm-a", configured.source_id, adapter.adapter_id
            )

        self.assertEqual(result.durable_acquisitions, 0)
        self.assertIsNone(result.checkpoint_after)
        self.assertEqual(retained, ())
        self.assertTrue(any(outcome.outcome == "selection_rejected"
                            for outcome in result.outcomes))
        terminal = next(
            item for item in result.diagnostics
            if item.get("terminal_selection_outcome") == "no_match"
        )
        self.assertEqual(terminal["effective_selection_mode"], "first_in_date_range")
        trial = next(item for item in result.diagnostics if "trial_id" in item)
        self.assertEqual(trial["effective_selection_mode"], "first_in_date_range")
        self.assertEqual(
            trial["candidate_qualification_dispositions"][0]["disposition"],
            "outside_requested_date_range",
        )

    def test_same_date_tie_breaking_is_stable_when_discovery_order_reverses(self) -> None:
        seed = "https://ir.example.com/transcripts"
        alpha = "https://ir.example.com/a-2025-earnings-call-transcript.html"
        beta = "https://ir.example.com/b-2025-earnings-call-transcript.html"
        selection = TranscriptAcquisitionSelection.first_in_date_range(
            date(2025, 1, 1), date(2025, 12, 31)
        )

        def selected_url(order: tuple[str, str]) -> str:
            links = "".join(
                f"<a href='{url}'>January 30, 2025 earnings call transcript</a>"
                for url in order
            )
            transport = Transport({
                seed: response(seed, links),
                alpha: response(alpha, transcript_body("January 30, 2025")),
                beta: response(beta, transcript_body("January 30, 2025")),
            })
            configured = source(seed)
            with tempfile.TemporaryDirectory() as directory:
                firms = FirmRepository.initialize(Path(directory) / "firms")
                firms.create(FirmDraft(
                    "firm-a", "Firm A", "2025-01-01", status=FirmStatus.ACTIVE
                ))
                repository = AcquisitionRepository(Path(directory) / "acquisition")
                repository.register_source(configured)
                adapter = EarningsTranscriptPullAdapter(
                    policies(), Search(), transport,
                    lambda: "2026-08-01T00:00:00Z",
                    repository=repository,
                    selection=selection,
                )
                result = AcquisitionEngine(
                    repository, AdapterRegistry((adapter,)),
                    lambda: "2026-08-01T00:00:00Z",
                ).run_source(configured.source_id, "task059-same-date")
                self.assertEqual(result.durable_acquisitions, 1)
                success = next(
                    item for item in repository.history() if item.get("outcome") == "success"
                )
                return str(success["candidate"]["provenance"]["metadata"]["requested_url"])

        self.assertEqual(selected_url((beta, alpha)), selected_url((alpha, beta)))


if __name__ == "__main__":
    unittest.main()
