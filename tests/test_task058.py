"""Focused acceptance evidence for TASK-058 transcript acquisition orchestration."""

from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from rfi.acquisition import (
    AdapterAcquisitionTrial,
    AdapterCandidate,
    AcquisitionEngine,
    AcquisitionRepository,
    AdapterRegistry,
    CandidateDocument,
    Checkpoint,
    DiscoveryPage,
    DiscoveryProvenance,
    EarningsTranscriptHttpResponse,
    RetrievalResult,
    RunStatus,
    SourceProfile,
    TranscriptAcquisitionTarget,
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


class OverlappingLearnedTrialAdapter:
    """Amazon-shaped learned trials that rediscover one archive candidate."""

    mechanism = "earnings_transcript"

    def __init__(self, conflicting_revision: bool = False) -> None:
        self.target = TranscriptAcquisitionTarget("firm-a")
        self.conflicting_revision = conflicting_revision
        self.retrievals: list[str] = []

    def acquisition_trials(
        self, profile: SourceProfile
    ) -> tuple[AdapterAcquisitionTrial, ...]:
        del profile
        return (
            AdapterAcquisitionTrial(
                "transcript-trial-1",
                "https://stockanalysis.com/stocks/amzn/transcripts/63594-q3-2016/",
                "single_seed", self.target, "learned",
            ),
            AdapterAcquisitionTrial(
                "transcript-trial-2",
                "https://stockanalysis.com/stocks/amzn/transcripts/63591-q4-2016/",
                "single_seed", self.target, "learned",
            ),
            AdapterAcquisitionTrial(
                "transcript-trial-3",
                "https://stockanalysis.com/stocks/amzn/transcripts/",
                "configured_pipeline", self.target, "configured",
            ),
        )

    def discover_trial(
        self, profile: SourceProfile, trial: AdapterAcquisitionTrial
    ) -> DiscoveryPage:
        del profile
        q2 = self._candidate(
            "https://stockanalysis.com/stocks/amzn/transcripts/657334-q2-2026/",
            ReportingPeriod.parse("2026-Q2").ordinal,
            "proposal-2026-q2-conflict" if self.conflicting_revision
            and trial.trial_id == "transcript-trial-2" else "proposal-2026-q2",
            "2026-08-03T21:55:11Z" if trial.trial_id == "transcript-trial-1"
            else "2026-08-03T21:57:32Z",
            1 if trial.trial_id == "transcript-trial-1" else 0,
            trial,
        )
        if trial.seed_source == "configured":
            return DiscoveryPage((q2,), None, {"seed_stage": "configured"})
        if trial.trial_id == "transcript-trial-2":
            return DiscoveryPage((q2,), None, {"seed_stage": "learned"})
        q4_2016 = self._candidate(
            "https://stockanalysis.com/stocks/amzn/transcripts/63591-q4-2016/",
            ReportingPeriod.parse("2016-Q4").ordinal,
            "proposal-2016-q4", "2026-08-03T21:55:11Z", 0, trial,
        )
        return DiscoveryPage((q4_2016, q2), None, {"seed_stage": "learned"})

    def discover(
        self, profile: SourceProfile, continuation: str | None
    ) -> DiscoveryPage:
        del profile, continuation
        raise AssertionError("trial adapter must use discover_trial")

    def retrieve(
        self, profile: SourceProfile, candidate: AdapterCandidate
    ) -> RetrievalResult:
        del profile
        self.retrievals.append(candidate.candidate_id)
        raise AssertionError("checkpoint-filtered overlap must not be retrieved")

    def _candidate(
        self, url: str, position: int, revision: str, discovered_at: str,
        proposal_rank: int, trial: AdapterAcquisitionTrial,
    ) -> AdapterCandidate:
        digest = hashlib.sha256(url.encode()).hexdigest()
        return AdapterCandidate(
            f"candidate-{digest}", f"document-{digest}", position, revision,
            DiscoveryProvenance(
                discovered_at, self.mechanism, locations=(url,), metadata={
                    "requested_url": url,
                    "resolved_url": url,
                    "proposal_rank": proposal_rank,
                    "trial_id": trial.trial_id,
                    "seed_kind": trial.seed_kind,
                    "seed_source": trial.seed_source,
                    "starting_seed": trial.starting_seed,
                    "deferred_candidate_evaluation": True,
                },
            ),
            trial.acquisition_target,
        )


class TranscriptAcquisitionOrchestrationTests(unittest.TestCase):
    def _checkpointed_repository(
        self, directory: str, configured: SourceProfile
    ) -> AcquisitionRepository:
        firms = FirmRepository.initialize(Path(directory) / "firms")
        firms.create(FirmDraft(
            "firm-a", "Firm A", "2026-01-01", status=FirmStatus.ACTIVE
        ))
        repository = AcquisitionRepository(Path(directory) / "acquisition")
        repository.register_source(configured)
        prior_url = (
            "https://stockanalysis.com/stocks/amzn/transcripts/63594-q3-2016/"
        )
        candidate = CandidateDocument(
            "candidate-prior-amazon", configured.source_id, "document-prior-amazon",
            DiscoveryProvenance(
                "2026-08-03T03:50:26Z", "earnings_transcript",
                locations=(prior_url,), metadata={"requested_url": prior_url},
            ),
        )
        repository.record_success(
            "attempt-prior-amazon", candidate,
            RetrievalResult(
                b"retained Amazon transcript", "text/html",
                "2026-08-03T03:50:26Z", "earnings_transcript",
                diagnostics={
                    "validated_position": ReportingPeriod.parse("2026-Q3").ordinal,
                    "validated_revision": "published-2026-07-31",
                },
            ),
        )
        repository.advance_checkpoint(
            configured.source_id, "attempt-prior-amazon",
            Checkpoint(
                ReportingPeriod.parse("2026-Q3").ordinal,
                "engine-amazon-existing-checkpoint",
            ),
        )
        return repository

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

    def test_overlapping_learned_trials_use_stable_candidate_equivalence(self) -> None:
        configured = source()
        with tempfile.TemporaryDirectory() as directory:
            repository = self._checkpointed_repository(directory, configured)
            adapter = OverlappingLearnedTrialAdapter()
            result = AcquisitionEngine(
                repository, AdapterRegistry((adapter,)),
                lambda: "2026-08-03T22:00:00Z",
            ).run_source(configured.source_id, "amazon-overlap")
            duplicate_history = [
                item for item in repository.history()
                if item.get("outcome") == "duplicate"
            ]

        q2 = "candidate-" + hashlib.sha256(
            b"https://stockanalysis.com/stocks/amzn/transcripts/657334-q2-2026/"
        ).hexdigest()
        q2_outcomes = [item.outcome for item in result.outcomes if item.candidate_id == q2]
        self.assertEqual(result.status, RunStatus.COMPLETE, json.dumps(result.to_dict(), indent=2))
        self.assertEqual(result.failures, 0)
        self.assertEqual(result.retrieval_attempts, 0)
        self.assertEqual(adapter.retrievals, [])
        self.assertEqual(
            q2_outcomes, ["checkpoint_filtered", "duplicate", "duplicate"]
        )
        self.assertEqual(result.duplicates, 2)
        self.assertEqual(len(duplicate_history), 1)
        self.assertEqual(result.checkpoint_before, result.checkpoint_after)
        self.assertEqual(
            [item["trial_outcome"] for item in result.diagnostics if "trial_id" in item],
            ["no_validated_artifact", "no_validated_artifact", "no_validated_artifact"],
        )
        self.assertNotIn("ambiguous duplicate candidate", json.dumps(result.to_dict()))

    def test_overlapping_learned_trial_stable_conflict_still_fails_closed(self) -> None:
        configured = source()
        with tempfile.TemporaryDirectory() as directory:
            repository = self._checkpointed_repository(directory, configured)
            adapter = OverlappingLearnedTrialAdapter(conflicting_revision=True)
            result = AcquisitionEngine(
                repository, AdapterRegistry((adapter,)),
                lambda: "2026-08-03T22:00:00Z",
            ).run_source(configured.source_id, "amazon-conflict")

        self.assertEqual(result.status, RunStatus.FAILED)
        self.assertEqual(result.failures, 1)
        self.assertEqual(result.retrieval_attempts, 0)
        self.assertEqual(adapter.retrievals, [])
        self.assertEqual(result.diagnostics[-1]["failure_class"], "malformed_adapter")
        self.assertIn("ambiguous duplicate candidate", result.diagnostics[-1]["message"])
        self.assertEqual(result.checkpoint_before, result.checkpoint_after)

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
