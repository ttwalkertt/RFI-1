"""Focused acceptance evidence for TASK-059 transcript selection contracts."""

from __future__ import annotations

import hashlib
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
from rfi.acquisition.engine import AdapterFailure, DiscoveryPage, FailureClass, RunStatus
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
    def test_latest_archive_page_persists_only_first_validated_transcript(self) -> None:
        seed = "https://stockanalysis.com/stocks/orcl/transcripts/"
        latest = "https://stockanalysis.com/stocks/orcl/transcripts/30001-q2-2026/"
        prior = "https://stockanalysis.com/stocks/orcl/transcripts/29001-q1-2026/"
        historical = "https://stockanalysis.com/stocks/orcl/transcripts/28001-q4-2025/"
        archive = "".join((
            f"<a href='{latest}'>Earnings Call: Q2 2026</a>",
            f"<a href='{prior}'>Earnings Call: Q1 2026</a>",
            f"<a href='{historical}'>Earnings Call: Q4 2025</a>",
        ))
        transport = Transport({
            seed: response(seed, archive),
            latest: response(latest, transcript_body("August 3, 2026")),
            # The live archive failure returned independently retrievable pages whose
            # content all validated as the current reporting period. Latest-mode
            # orchestration must still terminate after the first ranked success.
            prior: response(prior, transcript_body("August 3, 2026")),
            historical: response(historical, transcript_body("August 3, 2026")),
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
                lambda: "2026-08-03T00:00:00Z",
                repository=repository,
                selection=TranscriptAcquisitionSelection.latest(),
            )
            result = AcquisitionEngine(
                repository, AdapterRegistry((adapter,)),
                lambda: "2026-08-03T00:00:00Z",
            ).run_source(configured.source_id, "task059-latest-archive")
            successes = [
                item for item in repository.history()
                if item.get("outcome") == "success"
            ]
            learned = repository.discovery_anchors(
                "firm-a", configured.source_id, adapter.adapter_id
            )

        self.assertEqual(result.durable_acquisitions, 1, json.dumps(
            result.to_dict(), indent=2
        ))
        self.assertEqual(len(successes), 1)
        self.assertEqual(
            successes[0]["candidate"]["provenance"]["metadata"]["requested_url"],
            latest,
        )
        self.assertEqual(
            [item["normalized_url"] for item in learned],
            [latest],
        )
        self.assertEqual(transport.requests, [seed, latest])

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
            trial["candidate_disposition_counts"]["wrong_reporting_period"], 1,
        )
        self.assertEqual(
            trial["candidate_disposition_samples"][0]["validation_outcome"],
            "selection_date_mismatch",
        )
        self.assertNotIn("candidate_qualification_dispositions", trial)

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

    def test_validated_content_date_overrides_conflicting_url_and_title_dates(self) -> None:
        selection = TranscriptAcquisitionSelection.first_in_date_range(
            date(2025, 1, 1), date(2025, 3, 31)
        )

        def run(advisory_date: str, validated_date: str) -> tuple[object, list[dict]]:
            seed = "https://ir.example.com/transcripts"
            candidate = (
                "https://ir.example.com/2025-01-30-earnings-call-transcript.html"
                if advisory_date.startswith("January")
                else "https://ir.example.com/2024-12-15-earnings-call-transcript.html"
            )
            transport = Transport({
                seed: response(
                    seed,
                    f"<a href='{candidate}'>{advisory_date} earnings call transcript</a>",
                ),
                candidate: response(candidate, transcript_body(validated_date)),
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
                ).run_source(configured.source_id, "task059-conflicting-dates")
                return result, repository.history()

        rejected, rejected_history = run("January 30, 2025", "December 15, 2024")
        accepted, accepted_history = run("December 15, 2024", "January 30, 2025")

        self.assertEqual(rejected.durable_acquisitions, 0)
        self.assertFalse(any(item.get("outcome") == "success" for item in rejected_history))
        rejected_page = next(item for item in rejected.diagnostics if "trial_id" in item)
        self.assertEqual(
            rejected_page["validation_failure_counts"]["selection_date_mismatch"], 1
        )
        self.assertEqual(accepted.durable_acquisitions, 1)
        success = next(item for item in accepted_history if item.get("outcome") == "success")
        self.assertEqual(success["diagnostics"]["validated_event_date"], "2025-01-30")

    def test_same_date_global_selection_is_seed_order_independent(self) -> None:
        first_seed = "https://first.example/transcripts"
        second_seed = "https://second.example/transcripts"
        first_candidate = "https://first.example/q1-earnings-call-transcript.html"
        second_candidate = "https://second.example/q1-earnings-call-transcript.html"
        first_body = transcript_body("January 30, 2025") + " Alpha appendix."
        second_body = transcript_body("January 30, 2025") + " Beta appendix."
        expected = min(
            hashlib.sha256(f"<html>{body}</html>".encode()).hexdigest()
            for body in (first_body, second_body)
        )
        selection = TranscriptAcquisitionSelection.first_in_date_range(
            date(2025, 1, 1), date(2025, 12, 31)
        )

        def selected_digest(seed_order: tuple[str, str]) -> str:
            transport = Transport({
                first_seed: response(first_seed, (
                    f"<a href='{first_candidate}'>January 30, 2025 earnings call transcript</a>"
                )),
                first_candidate: response(first_candidate, first_body),
                second_seed: response(second_seed, (
                    f"<a href='{second_candidate}'>January 30, 2025 earnings call transcript</a>"
                )),
                second_candidate: response(second_candidate, second_body),
            })
            configured = source()
            anchors = tuple(
                {"normalized_url": seed, "requested_url": seed, "resolved_url": None}
                for seed in seed_order
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
                with patch.object(repository, "discovery_anchors", return_value=anchors):
                    result = AcquisitionEngine(
                        repository, AdapterRegistry((adapter,)),
                        lambda: "2026-08-01T00:00:00Z",
                    ).run_source(configured.source_id, "task059-seed-order")
            terminal = next(
                item for item in result.diagnostics
                if item.get("terminal_selection_outcome") == "selected"
            )
            return str(terminal["selected_validated_content_sha256"])

        self.assertEqual(selected_digest((first_seed, second_seed)), expected)
        self.assertEqual(selected_digest((second_seed, first_seed)), expected)

    def test_terminal_selection_diagnostic_covers_every_run_status(self) -> None:
        selection = TranscriptAcquisitionSelection.first_in_date_range(
            date(2025, 1, 1), date(2025, 12, 31)
        )
        cases = (
            (DiscoveryPage((), None, {}), RunStatus.COMPLETE, "no_match"),
            (AdapterFailure(FailureClass.TRANSIENT_ADAPTER, "later", True),
             RunStatus.PARTIAL, "incomplete"),
            (AdapterFailure(FailureClass.POLICY_REJECTION, "blocked", False),
             RunStatus.BLOCKED, "incomplete"),
            (ContractError("malformed"), RunStatus.FAILED, "failed"),
        )
        for index, (effect, expected_status, expected_outcome) in enumerate(cases):
            with self.subTest(status=expected_status), tempfile.TemporaryDirectory() as directory:
                configured = source()
                repository = AcquisitionRepository(Path(directory) / "acquisition")
                repository.register_source(configured)
                adapter = EarningsTranscriptPullAdapter(
                    policies(), Search(), Transport({}),
                    lambda: "2026-08-01T00:00:00Z",
                    repository=repository,
                    selection=selection,
                )
                patcher = (
                    patch.object(adapter, "discover_trial", side_effect=effect)
                    if isinstance(effect, Exception)
                    else patch.object(adapter, "discover_trial", return_value=effect)
                )
                with patcher:
                    result = AcquisitionEngine(
                        repository, AdapterRegistry((adapter,)),
                        lambda: "2026-08-01T00:00:00Z",
                    ).run_source(configured.source_id, f"task059-terminal-{index}")
            terminal = [
                item for item in result.diagnostics
                if item.get("terminal_run_status") == result.status.value
                and "effective_selection_mode" in item
            ]
            self.assertEqual(result.status, expected_status)
            self.assertEqual(len(terminal), 1, json.dumps(result.to_dict(), indent=2))
            self.assertEqual(terminal[0]["terminal_selection_outcome"], expected_outcome)

    def test_qualification_counts_are_complete_beyond_sample_limit(self) -> None:
        seed = "https://ir.example.com/transcripts"
        candidates = tuple(
            f"https://ir.example.com/q4-2024-{index}-earnings-call-transcript.html"
            for index in range(25)
        )
        links = "".join(
            f"<a href='{url}'>December 15, 2024 earnings call transcript</a>"
            for url in candidates
        )
        transport = Transport({
            seed: response(seed, links),
            **{
                url: response(url, transcript_body("December 15, 2024"))
                for url in candidates
            },
        })
        configured = source(seed)
        selection = TranscriptAcquisitionSelection.first_in_date_range(
            date(2025, 1, 1), date(2025, 3, 31)
        )
        expanded = DiscoveryPolicyCatalog({
            "standard": DiscoveryPolicy(2, 5, 1000, 2, 60, 8, 4_000_000, 60)
        }, "standard")
        with tempfile.TemporaryDirectory() as directory:
            repository = AcquisitionRepository(Path(directory) / "acquisition")
            repository.register_source(configured)
            adapter = EarningsTranscriptPullAdapter(
                expanded, Search(), transport,
                lambda: "2026-08-01T00:00:00Z",
                repository=repository,
                selection=selection,
            )
            result = AcquisitionEngine(
                repository, AdapterRegistry((adapter,)),
                lambda: "2026-08-01T00:00:00Z",
            ).run_source(configured.source_id, "task059-accounting")
        page = next(item for item in result.diagnostics if "trial_id" in item)
        self.assertEqual(page["candidate_evaluated_count"], 25)
        self.assertEqual(page["candidate_disposition_counts"]["wrong_reporting_period"], 25)
        self.assertEqual(page["validation_failure_counts"]["selection_date_mismatch"], 25)
        self.assertEqual(len(page["candidate_disposition_samples"]), 20)

    def test_date_max_is_included_without_boundary_overflow(self) -> None:
        seed = "https://ir.example.com/transcripts"
        candidate = "https://ir.example.com/max-earnings-call-transcript.html"
        transport = Transport({
            seed: response(
                seed,
                f"<a href='{candidate}'>December 31, 9999 earnings call transcript</a>",
            ),
            candidate: response(candidate, transcript_body("December 31, 9999")),
        })
        configured = source(seed)
        selection = TranscriptAcquisitionSelection.first_in_date_range(date.max, date.max)
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
            ).run_source(configured.source_id, "task059-date-max")
        self.assertEqual(result.durable_acquisitions, 1, json.dumps(result.to_dict(), indent=2))
        terminal = next(
            item for item in result.diagnostics
            if item.get("terminal_selection_outcome") == "selected"
        )
        self.assertEqual(terminal["selected_validated_event_date"], date.max.isoformat())


if __name__ == "__main__":
    unittest.main()
