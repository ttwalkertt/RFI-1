"""Focused acceptance evidence for TASK-062 candidate occurrence separation."""

from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from dataclasses import replace
from datetime import date
from pathlib import Path

from rfi.acquisition import (
    AcquisitionEngine,
    AcquisitionRepository,
    AdapterAcquisitionTrial,
    AdapterCandidate,
    AdapterRegistry,
    CandidateDocument,
    CandidateIdentity,
    Checkpoint,
    DiscoveryOccurrence,
    DiscoveryPage,
    DiscoveryProvenance,
    RetrievalResult,
    RunStatus,
    SourceProfile,
    TranscriptAcquisitionSelection,
    TranscriptAcquisitionTarget,
    TranscriptEventDisposition,
    TranscriptMetadataObservation,
)
from rfi.acquisition.earnings_transcripts import ReportingPeriod
from rfi.discovery import TranscriptTerminalSelectionPolicy
from rfi.firms import FirmRepository
from rfi.firms.contracts import FirmDraft, FirmStatus


def source() -> SourceProfile:
    return SourceProfile(
        "source-a",
        "Firm A transcripts",
        True,
        "earnings_transcript",
        {
            "mode": "discovery",
            "discovery_class": "standard",
            "discovery_hints": ["https://stockanalysis.com/stocks/amzn/transcripts/"],
        },
        {
            "firm_id": "firm-a",
            "artifact_id": "earnings_transcript",
            "retrieval_adapter_id": "earnings-call-transcript",
        },
    )


def candidate(
    url: str,
    target: TranscriptAcquisitionTarget,
    period: str,
    discovered_at: str,
    proposal_rank: int,
    depth: int,
    trial: AdapterAcquisitionTrial,
) -> AdapterCandidate:
    digest = hashlib.sha256(url.encode()).hexdigest()
    position = ReportingPeriod.parse(period).ordinal
    return AdapterCandidate(
        f"candidate-{digest}",
        f"document-{digest}",
        position,
        f"proposal-{period.casefold()}",
        DiscoveryProvenance(
            discovered_at,
            "earnings_transcript",
            locations=(url,),
            metadata={
                "firm_id": target.firm_id,
                "canonical_artifact_id": target.canonical_artifact_id,
                "link_label": f"Earnings Call: {period}",
                "requested_url": url,
                "resolved_url": url,
                "observed_aliases": [url],
                "allowed_hosts": ["stockanalysis.com"],
                "firm_identity_terms": [],
                "checkpoint_reporting_period": "2026-Q3",
                "expected_reporting_period": "2026-Q4",
                "deferred_candidate_evaluation": True,
                "proposal_rank": proposal_rank,
                "deterministic_selection_rank": [0, -position, -depth, 0],
                "trial_id": trial.trial_id,
                "seed_kind": trial.seed_kind,
                "seed_source": trial.seed_source,
                "starting_seed": trial.starting_seed,
                "traversal_depth": depth,
                "parent_path": [trial.starting_seed, url],
                "ranking_reasons": [f"depth_{depth}"],
                "acquisition_target": target.to_dict(),
            },
        ),
        target,
    )


class CapturedTopologyAdapter:
    """Learned transcript pages and one archive converge on one candidate."""

    mechanism = "earnings_transcript"

    def __init__(
        self,
        seeds: tuple[str, ...],
        candidate_url: str,
        candidate_period: str = "2026-Q2",
        conflicting_document: bool = False,
    ) -> None:
        self.target = TranscriptAcquisitionTarget("firm-a")
        self.seeds = seeds
        self.candidate_url = candidate_url
        self.candidate_period = candidate_period
        self.conflicting_document = conflicting_document
        self.retrievals: list[str] = []

    def acquisition_trials(
        self, profile: SourceProfile
    ) -> tuple[AdapterAcquisitionTrial, ...]:
        del profile
        trials = []
        for index, seed in enumerate(self.seeds, 1):
            configured = index == len(self.seeds)
            trials.append(AdapterAcquisitionTrial(
                f"transcript-trial-{index}",
                seed,
                "configured_pipeline" if configured else "single_seed",
                self.target,
                "configured" if configured else "learned",
            ))
        return tuple(trials)

    def discover_trial(
        self, profile: SourceProfile, trial: AdapterAcquisitionTrial
    ) -> DiscoveryPage:
        del profile
        index = int(trial.trial_id.rsplit("-", 1)[1])
        value = candidate(
            self.candidate_url,
            self.target,
            self.candidate_period,
            f"2026-08-03T22:00:0{index}Z",
            len(self.seeds) - index,
            1 if trial.seed_source == "configured" else 2,
            trial,
        )
        if self.conflicting_document and index == 2:
            value = replace(value, document_id="document-conflicting-stable-identity")
        return DiscoveryPage((value,), None, {"captured_topology": True})

    def retrieve(
        self, profile: SourceProfile, value: AdapterCandidate
    ) -> RetrievalResult:
        del profile
        self.retrievals.append(value.candidate_id)
        raise AssertionError("checkpoint-filtered candidates must not be retrieved")


class SelectionAdapter:
    """Two trials rediscover two candidates under either selector."""

    mechanism = "earnings_transcript"

    def __init__(self, selection: TranscriptAcquisitionSelection) -> None:
        self.target = TranscriptAcquisitionTarget("firm-a", selection=selection)
        self.retrievals: list[str] = []

    def acquisition_trials(
        self, profile: SourceProfile
    ) -> tuple[AdapterAcquisitionTrial, ...]:
        del profile
        return tuple(
            AdapterAcquisitionTrial(
                f"transcript-trial-{index}",
                f"https://ir.example.com/seed-{index}",
                "single_seed",
                self.target,
                "learned",
            )
            for index in (1, 2)
        )

    def terminal_selection_policy(
        self,
        profile: SourceProfile,
        trials: tuple[AdapterAcquisitionTrial, ...],
    ) -> TranscriptTerminalSelectionPolicy | None:
        del profile, trials
        if self.target.selection.start_date is None:
            return None
        return TranscriptTerminalSelectionPolicy(self.target.selection)

    def discover_trial(
        self, profile: SourceProfile, trial: AdapterAcquisitionTrial
    ) -> DiscoveryPage:
        del profile
        index = int(trial.trial_id.rsplit("-", 1)[1])
        values = (
            candidate(
                "https://ir.example.com/q2-2025-transcript.html",
                self.target,
                "2025-Q2",
                f"2026-08-03T22:10:0{index}Z",
                0 if index == 1 else 1,
                2 if index == 1 else 1,
                trial,
            ),
            candidate(
                "https://ir.example.com/q1-2025-transcript.html",
                self.target,
                "2025-Q1",
                f"2026-08-03T22:10:0{index}Z",
                1 if index == 1 else 0,
                2 if index == 1 else 1,
                trial,
            ),
        )
        return DiscoveryPage(values, None, {"candidate_evaluated_count": 0})

    def retrieve(
        self, profile: SourceProfile, value: AdapterCandidate
    ) -> RetrievalResult:
        del profile
        self.retrievals.append(value.candidate_id)
        event_date = "2025-04-30" if "q2-2025" in value.provenance.locations[0] else "2025-01-30"
        return RetrievalResult(
            f"validated transcript {event_date}".encode(),
            "text/html",
            "2026-08-03T22:10:10Z",
            self.mechanism,
            diagnostics={
                "validated_event_date": event_date,
                "validated_position": value.position,
                "validated_revision": value.revision,
            },
            trusted_event_date=date.fromisoformat(event_date),
            transcript_metadata_observation=TranscriptMetadataObservation(
                "Earnings Call",
                date.fromisoformat(event_date),
                TranscriptEventDisposition.EXPLICIT_EARNINGS,
            ),
        )


class ManyOccurrencesAdapter(CapturedTopologyAdapter):
    """Ten candidates repeated five times exercise both diagnostic bounds."""

    def __init__(self) -> None:
        super().__init__(
            tuple(f"https://ir.example.com/seed-{index}" for index in range(5)),
            "https://ir.example.com/unused",
        )

    def discover_trial(
        self, profile: SourceProfile, trial: AdapterAcquisitionTrial
    ) -> DiscoveryPage:
        del profile
        index = int(trial.trial_id.rsplit("-", 1)[1])
        values = tuple(
            candidate(
                f"https://ir.example.com/q{number}-2025-transcript.html",
                self.target,
                "2025-Q1",
                f"2026-08-03T22:20:0{index}Z",
                number,
                index,
                trial,
            )
            for number in range(10)
        )
        return DiscoveryPage(values, None, {"many_occurrences": True})


class CandidateOccurrenceTests(unittest.TestCase):
    def _repository(
        self, directory: str, configured: SourceProfile, checkpointed: bool
    ) -> AcquisitionRepository:
        firms = FirmRepository.initialize(Path(directory) / "firms")
        firms.create(FirmDraft(
            "firm-a", "Firm A", "2026-01-01", status=FirmStatus.ACTIVE
        ))
        repository = AcquisitionRepository(Path(directory) / "acquisition")
        repository.register_source(configured)
        if not checkpointed:
            return repository
        prior_url = "https://ir.example.com/q3-2026-transcript.html"
        prior = CandidateDocument(
            "candidate-prior", configured.source_id, "document-prior",
            DiscoveryProvenance(
                "2026-08-03T21:00:00Z", "earnings_transcript",
                locations=(prior_url,), metadata={"requested_url": prior_url},
            ),
        )
        repository.record_success(
            "attempt-prior",
            prior,
            RetrievalResult(
                b"prior validated transcript",
                "text/html",
                "2026-08-03T21:00:00Z",
                "earnings_transcript",
                diagnostics={
                    "validated_position": ReportingPeriod.parse("2026-Q3").ordinal,
                    "validated_revision": "published-2026-q3",
                },
            ),
        )
        repository.advance_checkpoint(
            configured.source_id,
            "attempt-prior",
            Checkpoint(
                ReportingPeriod.parse("2026-Q3").ordinal,
                "existing-checkpoint",
            ),
        )
        return repository

    def test_identity_is_allowlisted_and_occurrence_is_explicit(self) -> None:
        target = TranscriptAcquisitionTarget("firm-a")
        first_trial = AdapterAcquisitionTrial(
            "transcript-trial-1", "https://ir.example.com/learned",
            "single_seed", target, "learned",
        )
        second_trial = AdapterAcquisitionTrial(
            "transcript-trial-2", "https://ir.example.com/archive",
            "configured_pipeline", target, "configured",
        )
        first = candidate(
            "https://ir.example.com/q2", target, "2026-Q2",
            "2026-08-03T22:00:01Z", 1, 2, first_trial,
        )
        second = candidate(
            "https://ir.example.com/q2", target, "2026-Q2",
            "2026-08-03T22:00:02Z", 0, 1, second_trial,
        )
        second_metadata = {
            **second.provenance.metadata,
            "link_label": "Q2 2026 transcript reached from archive",
            "requested_url": "https://alias.example.com/q2",
            "resolved_url": "HTTPS://IR.EXAMPLE.COM:443/q2#fragment",
            "observed_aliases": [
                "https://alias.example.com/q2",
                "https://ir.example.com/q2",
            ],
        }
        second = replace(
            second,
            provenance=replace(
                second.provenance,
                locations=(
                    "https://alias.example.com/q2",
                    "https://ir.example.com/q2",
                ),
                metadata=second_metadata,
            ),
        )

        self.assertIsInstance(first.identity(), CandidateIdentity)
        self.assertEqual(first.identity(), second.identity())
        self.assertIsInstance(first.occurrence(first_trial), DiscoveryOccurrence)
        self.assertNotEqual(
            first.occurrence(first_trial), second.occurrence(second_trial)
        )
        changed = replace(second, revision="proposal-conflicting")
        self.assertNotEqual(first.identity(), changed.identity())
        oversized = replace(
            first,
            provenance=replace(
                first.provenance,
                metadata={
                    **first.provenance.metadata,
                    "parent_path": [f"https://ir.example.com/{index}" for index in range(20)],
                },
            ),
        ).occurrence(first_trial)
        self.assertTrue(oversized.details_omitted)
        self.assertEqual(len(oversized.metadata["parent_path"]), 8)

    def test_captured_topologies_deduplicate_and_preserve_first_occurrence(self) -> None:
        topologies = {
            "amazon": (
                (
                    "https://stockanalysis.com/stocks/amzn/transcripts/63594-q3-2016/",
                    "https://stockanalysis.com/stocks/amzn/transcripts/63591-q4-2016/",
                    "https://stockanalysis.com/stocks/amzn/transcripts/63590-q1-2017/",
                    "https://stockanalysis.com/stocks/amzn/transcripts/",
                ),
                "https://stockanalysis.com/stocks/amzn/transcripts/63591-q4-2016/",
                "2016-Q4",
            ),
            "ibm": (
                (
                    "https://stockanalysis.com/stocks/ibm/transcripts/learned-a/",
                    "https://stockanalysis.com/stocks/ibm/transcripts/learned-b/",
                    "https://stockanalysis.com/stocks/ibm/transcripts/",
                ),
                "https://stockanalysis.com/stocks/ibm/transcripts/q2-2026/",
                "2026-Q2",
            ),
            "western-digital": (
                (
                    "https://stockanalysis.com/stocks/wdc/transcripts/149492-q3-2018/",
                    "https://stockanalysis.com/stocks/wdc/transcripts/149490-q4-2018/",
                    "https://stockanalysis.com/stocks/wdc/transcripts/",
                ),
                "https://stockanalysis.com/stocks/wdc/transcripts/q2-2026/",
                "2026-Q2",
            ),
        }
        for name, (seeds, candidate_url, candidate_period) in topologies.items():
            with self.subTest(name=name), tempfile.TemporaryDirectory() as directory:
                configured = source()
                repository = self._repository(directory, configured, checkpointed=True)
                adapter = CapturedTopologyAdapter(
                    seeds, candidate_url, candidate_period
                )
                result = AcquisitionEngine(
                    repository, AdapterRegistry((adapter,)),
                    lambda: "2026-08-03T22:30:00Z",
                ).run_source(configured.source_id, name)
                occurrence = next(
                    item for item in result.diagnostics
                    if item.get("diagnostic_type") == "candidate_occurrences"
                )

                self.assertEqual(result.status, RunStatus.COMPLETE)
                self.assertEqual(result.failures, 0)
                self.assertEqual(result.candidates_unique, 1)
                self.assertEqual(result.retrieval_attempts, 0)
                self.assertEqual(adapter.retrievals, [])
                self.assertEqual(
                    [item.outcome for item in result.outcomes],
                    ["checkpoint_filtered", *("duplicate" for _ in seeds[1:])],
                )
                self.assertEqual(
                    occurrence["candidate_samples"][0]["occurrence_count"],
                    len(seeds),
                )
                self.assertEqual(
                    occurrence["candidate_samples"][0]
                    ["authoritative_occurrence"]["trial_id"],
                    "transcript-trial-1",
                )
                self.assertNotIn(
                    "ambiguous duplicate candidate", json.dumps(result.to_dict())
                )

    def test_changed_stable_identity_remains_fail_closed(self) -> None:
        configured = source()
        seeds = (
            "https://ir.example.com/learned",
            "https://ir.example.com/archive",
        )
        with tempfile.TemporaryDirectory() as directory:
            repository = self._repository(directory, configured, checkpointed=True)
            adapter = CapturedTopologyAdapter(
                seeds,
                "https://ir.example.com/q2-2026",
                conflicting_document=True,
            )
            result = AcquisitionEngine(
                repository, AdapterRegistry((adapter,)),
                lambda: "2026-08-03T22:30:00Z",
            ).run_source(configured.source_id, "stable-conflict")

        self.assertEqual(result.status, RunStatus.FAILED)
        self.assertEqual(result.failures, 1)
        self.assertEqual(result.retrieval_attempts, 0)
        self.assertEqual(result.diagnostics[-1]["failure_class"], "malformed_adapter")
        self.assertIn("ambiguous duplicate candidate", result.diagnostics[-1]["message"])
        self.assertEqual(result.checkpoint_before, result.checkpoint_after)

    def test_occurrence_diagnostics_retain_totals_with_bounded_samples(self) -> None:
        configured = source()
        with tempfile.TemporaryDirectory() as directory:
            repository = self._repository(directory, configured, checkpointed=True)
            adapter = ManyOccurrencesAdapter()
            result = AcquisitionEngine(
                repository, AdapterRegistry((adapter,)),
                lambda: "2026-08-03T22:30:00Z",
            ).run_source(configured.source_id, "bounded-occurrences")
        occurrence = next(
            item for item in result.diagnostics
            if item.get("diagnostic_type") == "candidate_occurrences"
        )

        self.assertEqual(result.status, RunStatus.COMPLETE)
        self.assertEqual(result.candidates_discovered, 50)
        self.assertEqual(result.candidates_unique, 10)
        self.assertEqual(result.duplicates, 40)
        self.assertEqual(occurrence["candidates_with_multiple_occurrences"], 10)
        self.assertEqual(occurrence["duplicate_occurrence_count"], 40)
        self.assertEqual(len(occurrence["candidate_samples"]), 8)
        self.assertTrue(occurrence["candidate_samples_omitted"])
        self.assertTrue(all(
            item["occurrence_count"] == 5
            and len(item["occurrences"]) == 3
            and item["occurrences_omitted"] is True
            for item in occurrence["candidate_samples"]
        ))

    def test_latest_and_first_in_range_selector_behavior_is_unchanged(self) -> None:
        configured = source()
        selections = (
            TranscriptAcquisitionSelection.latest(),
            TranscriptAcquisitionSelection.first_in_date_range(
                date(2025, 1, 1), date(2025, 12, 31)
            ),
        )
        for selection in selections:
            with self.subTest(mode=selection.mode), tempfile.TemporaryDirectory() as directory:
                repository = self._repository(directory, configured, checkpointed=False)
                adapter = SelectionAdapter(selection)
                result = AcquisitionEngine(
                    repository, AdapterRegistry((adapter,)),
                    lambda: "2026-08-03T22:30:00Z",
                ).run_source(configured.source_id, selection.mode.value)
                successes = [
                    item for item in repository.history()
                    if item.get("record_type") == "retrieval_attempt"
                    and item.get("outcome") == "success"
                ]

                self.assertEqual(result.status, RunStatus.COMPLETE)
                self.assertEqual(result.durable_acquisitions, 1)
                if selection.start_date is None:
                    self.assertEqual(len(adapter.retrievals), 1)
                    self.assertIn(
                        "q2-2025",
                        successes[0]["candidate"]["provenance"]["locations"][0],
                    )
                else:
                    self.assertEqual(len(adapter.retrievals), 2)
                    self.assertEqual(
                        successes[0]["diagnostics"]["validated_event_date"],
                        "2025-01-30",
                    )


if __name__ == "__main__":
    unittest.main()
