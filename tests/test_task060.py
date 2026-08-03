"""Focused acceptance evidence for TASK-060 operator seed injection."""

from __future__ import annotations

import json
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from datetime import date
from http.client import HTTPConnection
from pathlib import Path
from typing import Any
from unittest.mock import Mock, patch

from rfi.acquisition import (
    AcquisitionEngine,
    AcquisitionRepository,
    AdapterRegistry,
    Checkpoint,
    EngineFailurePoint,
    EarningsTranscriptHttpResponse,
    RunStatus,
    SourceProfile,
    TranscriptAcquisitionSelection,
    TranscriptAcquisitionTarget,
    TranscriptSelectionMode,
)
from rfi.acquisition.contracts import ConflictError, ContractError
from rfi.admin import create_admin_server
from rfi.concepts import ConceptRepository
from rfi.discovery import (
    DiscoveryPolicy,
    DiscoveryPolicyCatalog,
    DiscoverySearchResponse,
    EarningsTranscriptPullAdapter,
)
from rfi.firms import FirmRepository, sample_firms
from rfi.firms.contracts import FirmDraft, FirmStatus
from rfi.pull import (
    PullRunRepository,
    PullWorkflow,
    RetrievalAdapterCapability,
    RetrievalAdapterRegistration,
    RetrievalAdapterRegistry,
)
from rfi.source_profiles import (
    RetrievalCandidate,
    SourceProfileDraft,
    SourceProfileItem,
    SourceProfileRepository,
    load_canonical_template,
)


class Search:
    endpoint = "https://search.example/results"

    def search(self, query: str, limit: int) -> DiscoverySearchResponse:
        del query, limit
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


def policies() -> DiscoveryPolicyCatalog:
    return DiscoveryPolicyCatalog(
        {"standard": DiscoveryPolicy(1, 5, 1000, 2, 20, 8, 2_000_000, 60)},
        "standard",
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


class TranscriptSeedAcquisitionTests(unittest.TestCase):
    def _repository(self, directory: str, configured: SourceProfile) -> AcquisitionRepository:
        firms = FirmRepository.initialize(Path(directory) / "firms")
        firms.create(FirmDraft(
            "firm-a", "Firm A", "2025-01-01", status=FirmStatus.ACTIVE
        ))
        repository = AcquisitionRepository(Path(directory) / "acquisition")
        repository.register_source(configured)
        return repository

    def test_injected_and_learned_seeds_converge_before_discovery(self) -> None:
        seed = "https://ir.example.com/archive"
        later = "https://ir.example.com/q2-2025-transcript.html"
        earlier = "https://ir.example.com/q1-2025-transcript.html"
        configured = source()
        responses = {
            seed: response(
                seed,
                f"<a href='{later}'>April 30, 2025 earnings call transcript</a>"
                f"<a href='{earlier}'>January 30, 2025 earnings call transcript</a>",
            ),
            later: response(later, transcript_body("April 30, 2025")),
            earlier: response(earlier, transcript_body("January 30, 2025")),
        }

        def terminal_projection(result: Any) -> dict[str, Any]:
            value = result.to_dict()
            for diagnostic in value["diagnostics"]:
                diagnostic.pop("seed_source", None)
            return value

        for selection in (
            TranscriptAcquisitionSelection.latest(),
            TranscriptAcquisitionSelection.first_in_date_range(
                date(2025, 1, 1), date(2025, 12, 31)
            ),
        ):
            with self.subTest(selection=selection.mode.value), tempfile.TemporaryDirectory(
            ) as first, tempfile.TemporaryDirectory() as second:
                learned_repository = self._repository(first, configured)
                learned_transport = Transport(responses)
                learned_adapter = EarningsTranscriptPullAdapter(
                    policies(), Search(), learned_transport,
                    lambda: "2026-08-03T00:00:00Z", repository=learned_repository,
                    selection=selection,
                )
                learned_anchor = ({
                    "normalized_url": seed,
                    "requested_url": seed,
                    "resolved_url": None,
                },)
                with patch.object(
                    learned_repository, "discovery_anchors", return_value=learned_anchor
                ):
                    learned_trial = learned_adapter.acquisition_trials(configured)[0]
                    learned_page = learned_adapter.discover_trial(configured, learned_trial)
                    learned_traversal = tuple(learned_transport.requests)
                    learned_transport.requests.clear()
                    learned = AcquisitionEngine(
                        learned_repository, AdapterRegistry((learned_adapter,)),
                        lambda: "2026-08-03T00:00:00Z",
                    ).run_source_trial("source-a", "equivalent", learned_trial)

                injected_repository = self._repository(second, configured)
                injected_transport = Transport(responses)
                injected_adapter = EarningsTranscriptPullAdapter(
                    policies(), Search(), injected_transport,
                    lambda: "2026-08-03T00:00:00Z", repository=injected_repository,
                    selection=selection,
                )
                target = TranscriptAcquisitionTarget("firm-a", selection=selection)
                injected_trial = injected_adapter.injected_trial(configured, target, seed)
                injected_page = injected_adapter.discover_trial(configured, injected_trial)
                injected_traversal = tuple(injected_transport.requests)
                injected_transport.requests.clear()
                injected = AcquisitionEngine(
                    injected_repository, AdapterRegistry((injected_adapter,)),
                    lambda: "2026-08-03T00:00:00Z",
                ).run_source_trial("source-a", "equivalent", injected_trial)

                self.assertEqual(learned_trial.seed_kind, "single_seed")
                self.assertEqual(injected_trial.seed_kind, "single_seed")
                self.assertEqual(learned_trial.seed_source, "learned")
                self.assertEqual(injected_trial.seed_source, "operator_supplied")
                self.assertEqual(
                    learned_page.diagnostics["stage_sequence"], ["configured_hint"]
                )
                self.assertEqual(
                    learned_page.diagnostics["stage_sequence"],
                    injected_page.diagnostics["stage_sequence"],
                )
                self.assertNotIn(
                    "retained_anchor", learned_page.diagnostics["stage_sequence"]
                )
                self.assertEqual(
                    [candidate.canonical() for candidate in learned_page.candidates],
                    [candidate.canonical() for candidate in injected_page.candidates],
                )
                self.assertEqual(learned_traversal, injected_traversal)
                self.assertEqual(
                    learned_page.diagnostics["top_ranked_candidates"],
                    injected_page.diagnostics["top_ranked_candidates"],
                )
                learned_page_diagnostics = dict(learned_page.diagnostics)
                injected_page_diagnostics = dict(injected_page.diagnostics)
                learned_page_diagnostics.pop("seed_source")
                injected_page_diagnostics.pop("seed_source")
                self.assertEqual(learned_page_diagnostics, injected_page_diagnostics)
                self.assertEqual(
                    terminal_projection(learned), terminal_projection(injected)
                )
                learned_diagnostic = next(
                    item for item in learned.diagnostics if "trial_id" in item
                )
                injected_diagnostic = next(
                    item for item in injected.diagnostics if "trial_id" in item
                )
                self.assertEqual(learned_diagnostic["seed_source"], "learned")
                self.assertEqual(
                    injected_diagnostic["seed_source"], "operator_supplied"
                )

    def test_default_latest_and_first_in_range_flow_unchanged(self) -> None:
        seed = "https://ir.example.com/archive"
        later = "https://ir.example.com/q2-2025-transcript.html"
        earlier = "https://ir.example.com/q1-2025-transcript.html"
        transport = Transport({
            seed: response(
                seed,
                f"<a href='{later}'>April 30, 2025 earnings call transcript</a>"
                f"<a href='{earlier}'>January 30, 2025 earnings call transcript</a>",
            ),
            later: response(later, transcript_body("April 30, 2025")),
            earlier: response(earlier, transcript_body("January 30, 2025")),
        })
        configured = source()
        selection = TranscriptAcquisitionSelection.first_in_date_range(
            date(2025, 1, 1), date(2025, 12, 31)
        )
        with tempfile.TemporaryDirectory() as directory:
            repository = self._repository(directory, configured)
            adapter = EarningsTranscriptPullAdapter(
                policies(), Search(), transport,
                lambda: "2026-08-03T00:00:00Z", repository=repository,
                selection=selection,
            )
            target = TranscriptAcquisitionTarget("firm-a", selection=selection)
            result = AcquisitionEngine(
                repository, AdapterRegistry((adapter,)),
                lambda: "2026-08-03T00:00:00Z",
            ).run_source_trial(
                "source-a", "range", adapter.injected_trial(configured, target, seed)
            )
            attempts = [item for item in repository.history()
                        if item.get("record_type") == "retrieval_attempt"
                        and item.get("outcome") == "success"]

        self.assertEqual(TranscriptAcquisitionTarget("firm-a").selection.mode,
                         TranscriptSelectionMode.LATEST)
        self.assertEqual(result.durable_acquisitions, 1)
        self.assertEqual(attempts[0]["diagnostics"]["validated_event_date"], "2025-01-30")

    def test_invalid_seeds_fail_closed_and_failure_does_not_learn_or_checkpoint(self) -> None:
        configured = source()
        with tempfile.TemporaryDirectory() as directory:
            repository = self._repository(directory, configured)
            adapter = EarningsTranscriptPullAdapter(
                policies(), Search(), Transport({}),
                lambda: "2026-08-03T00:00:00Z", repository=repository,
            )
            target = TranscriptAcquisitionTarget("firm-a")
            for invalid in ("", "not-a-url", "ftp://ir.example.com/archive"):
                with self.subTest(invalid=invalid), self.assertRaises(
                    (ContractError, ValueError)
                ):
                    adapter.injected_trial(configured, target, invalid)

            seed = "https://ir.example.com/empty"
            adapter._transport = Transport({seed: response(seed, "No transcript here")})
            result = AcquisitionEngine(
                repository, AdapterRegistry((adapter,)),
                lambda: "2026-08-03T00:00:00Z",
            ).run_source_trial(
                "source-a", "failed", adapter.injected_trial(configured, target, seed)
            )
            anchors = repository.discovery_anchors(
                "firm-a", "source-a", "earnings-call-transcript"
            )

        self.assertEqual(result.durable_acquisitions, 0)
        self.assertEqual(anchors, ())
        self.assertEqual(result.checkpoint_before, result.checkpoint_after)

    def test_success_applies_existing_learning_and_checkpoint_once(self) -> None:
        seed = "https://ir.example.com/archive"
        artifact = "https://ir.example.com/q2-2025-transcript.html"
        configured = source()
        with tempfile.TemporaryDirectory() as directory:
            repository = self._repository(directory, configured)
            adapter = EarningsTranscriptPullAdapter(
                policies(), Search(), Transport({
                    seed: response(
                        seed,
                        f"<a href='{artifact}'>April 30, 2025 earnings call transcript</a>",
                    ),
                    artifact: response(artifact, transcript_body("April 30, 2025")),
                }), lambda: "2026-08-03T00:00:00Z", repository=repository,
            )
            target = TranscriptAcquisitionTarget("firm-a")
            with patch.object(
                repository, "record_success", wraps=repository.record_success
            ) as save:
                result = AcquisitionEngine(
                    repository, AdapterRegistry((adapter,)),
                    lambda: "2026-08-03T00:00:00Z",
                ).run_source_trial(
                    "source-a", "success", adapter.injected_trial(configured, target, seed)
                )
            anchors = repository.discovery_anchors(
                "firm-a", "source-a", "earnings-call-transcript"
            )

        save.assert_called_once()
        self.assertIsNotNone(result.checkpoint_after)
        self.assertEqual(len(anchors), 1)
        self.assertEqual(anchors[0]["normalized_url"], artifact)

    def test_checkpoint_replay_is_observable_no_change_for_both_selectors(self) -> None:
        seed = "https://ir.example.com/archive"
        artifact = "https://ir.example.com/q1-2025-earnings-call-transcript.html"
        configured = source()
        responses = {
            seed: response(
                seed, f"<a href='{artifact}'>January 30, 2025 earnings transcript</a>"
            ),
            artifact: response(artifact, transcript_body("January 30, 2025")),
        }
        selections = (
            TranscriptAcquisitionSelection.latest(),
            TranscriptAcquisitionSelection.first_in_date_range(
                date(2025, 1, 1), date(2025, 12, 31)
            ),
        )

        for selection in selections:
            with self.subTest(selection=selection.mode.value), tempfile.TemporaryDirectory(
            ) as directory:
                repository = self._repository(directory, configured)
                adapter = EarningsTranscriptPullAdapter(
                    policies(), Search(), Transport(responses),
                    lambda: "2026-08-03T00:00:00Z", repository=repository,
                    selection=selection,
                )
                engine = AcquisitionEngine(
                    repository, AdapterRegistry((adapter,)),
                    lambda: "2026-08-03T00:00:00Z",
                )
                target = TranscriptAcquisitionTarget("firm-a", selection=selection)

                ordinary = engine.run_source("source-a", "ordinary-empty")
                injected = engine.run_source_trial(
                    "source-a", "injected-success",
                    adapter.injected_trial(configured, target, seed),
                )
                checkpoint = injected.checkpoint_after
                anchors = repository.discovery_anchors(
                    "firm-a", "source-a", adapter.adapter_id
                )
                history = repository.history()
                artifacts = repository.artifact_metadata()
                revision = repository.repository_revision()

                learned_replay = engine.run_source("source-a", "ordinary-learned")
                injected_replay = engine.run_source_trial(
                    "source-a", "injected-repeat",
                    adapter.injected_trial(configured, target, seed),
                )

                self.assertEqual(ordinary.status, RunStatus.COMPLETE)
                self.assertEqual(ordinary.durable_acquisitions, 0)
                self.assertIsNone(ordinary.checkpoint_after)
                self.assertEqual(injected.status, RunStatus.COMPLETE)
                self.assertEqual(injected.durable_acquisitions, 1)
                self.assertIsNotNone(checkpoint)
                for replay in (learned_replay, injected_replay):
                    self.assertEqual(replay.status, RunStatus.COMPLETE)
                    self.assertEqual(replay.durable_acquisitions, 0)
                    self.assertEqual(
                        replay.unchanged, 1, json.dumps(replay.to_dict(), indent=2)
                    )
                    self.assertEqual(replay.checkpoint_before, checkpoint)
                    self.assertEqual(replay.checkpoint_after, checkpoint)
                    self.assertNotIn(
                        "blocked", {item.outcome for item in replay.outcomes}
                    )
                    self.assertTrue(
                        any(
                            item.outcome in {"checkpoint_filtered", "unchanged"}
                            for item in replay.outcomes
                        ),
                        json.dumps(replay.to_dict(), indent=2),
                    )
                self.assertEqual(repository.history(), history)
                self.assertEqual(repository.artifact_metadata(), artifacts)
                self.assertEqual(
                    repository.discovery_anchors(
                        "firm-a", "source-a", adapter.adapter_id
                    ),
                    anchors,
                )
                self.assertEqual(repository.repository_revision(), revision)

    def test_oracle_archive_injected_and_learned_replay_are_mutation_free(self) -> None:
        seed = "https://stockanalysis.com/stocks/orcl/transcripts/"
        q4 = "https://stockanalysis.com/stocks/orcl/transcripts/32001-q4-2026/"
        q3 = "https://stockanalysis.com/stocks/orcl/transcripts/31001-q3-2026/"
        q2 = "https://stockanalysis.com/stocks/orcl/transcripts/30001-q2-2026/"
        q1 = "https://stockanalysis.com/stocks/orcl/transcripts/29001-q1-2026/"
        archive = "".join((
            f"<a href='{q4}'>Earnings Call: Q4 2026</a>",
            f"<a href='{q3}'>Earnings Call: Q3 2026</a>",
            f"<a href='{q2}'>Earnings Call: Q2 2026</a>",
            f"<a href='{q1}'>Earnings Call: Q1 2026</a>",
        ))
        validated = transcript_body("August 3, 2026")
        configured = source(seed)
        transport = Transport({
            seed: response(seed, archive),
            q4: response(q4, validated),
            q3: response(q3, validated),
            q2: response(q2, validated),
            q1: response(q1, validated),
        })

        with tempfile.TemporaryDirectory() as directory:
            repository = self._repository(directory, configured)
            adapter = EarningsTranscriptPullAdapter(
                policies(), Search(), transport,
                lambda: "2026-08-03T00:00:00Z", repository=repository,
            )
            engine = AcquisitionEngine(
                repository, AdapterRegistry((adapter,)),
                lambda: "2026-08-03T00:00:00Z",
            )
            target = TranscriptAcquisitionTarget("firm-a")
            first = engine.run_source_trial(
                "source-a", "oracle-first",
                adapter.injected_trial(configured, target, seed),
            )
            checkpoint = first.checkpoint_after
            snapshot = {
                "revision": repository.repository_revision(),
                "history": repository.history(),
                "artifacts": repository.artifact_metadata(),
                "observations": repository.observations(),
                "anchors": repository.discovery_anchors(
                    "firm-a", "source-a", adapter.adapter_id
                ),
            }

            injected_replay = engine.run_source_trial(
                "source-a", "oracle-repeat",
                adapter.injected_trial(configured, target, seed),
            )
            learned_replay = engine.run_source("source-a", "oracle-learned")
            partial_replay = engine.run_source_trial(
                "source-a", "oracle-partial",
                adapter.injected_trial(configured, target, seed),
                EngineFailurePoint.BEFORE_CHECKPOINT_FINALIZATION,
            )

            self.assertEqual(first.status, RunStatus.COMPLETE)
            self.assertEqual(first.durable_acquisitions, 1)
            self.assertEqual(len(snapshot["artifacts"]), 1)
            self.assertEqual(len(snapshot["observations"]), 1)
            self.assertEqual(len(snapshot["anchors"]), 1)
            self.assertIsNotNone(checkpoint)
            for replay in (injected_replay, learned_replay):
                self.assertEqual(replay.status, RunStatus.COMPLETE)
                self.assertEqual(replay.durable_acquisitions, 0)
                self.assertEqual(replay.unchanged, 1)
                self.assertEqual(replay.checkpoint_before, checkpoint)
                self.assertEqual(replay.checkpoint_after, checkpoint)
            self.assertEqual(partial_replay.status, RunStatus.PARTIAL)
            self.assertEqual(partial_replay.durable_acquisitions, 0)
            self.assertEqual(partial_replay.unchanged, 0)
            self.assertEqual(partial_replay.checkpoint_before, checkpoint)
            self.assertEqual(partial_replay.checkpoint_after, checkpoint)
            self.assertEqual(repository.repository_revision(), snapshot["revision"])
            self.assertEqual(repository.history(), snapshot["history"])
            self.assertEqual(repository.artifact_metadata(), snapshot["artifacts"])
            self.assertEqual(repository.observations(), snapshot["observations"])
            self.assertEqual(
                repository.discovery_anchors(
                    "firm-a", "source-a", adapter.adapter_id
                ),
                snapshot["anchors"],
            )

    def test_same_position_different_checkpoint_cursor_remains_a_conflict(self) -> None:
        seed = "https://ir.example.com/archive"
        artifact = "https://ir.example.com/q2-2025-transcript.html"
        configured = source(seed)
        with tempfile.TemporaryDirectory() as directory:
            repository = self._repository(directory, configured)
            adapter = EarningsTranscriptPullAdapter(
                policies(), Search(), Transport({
                    seed: response(
                        seed,
                        f"<a href='{artifact}'>April 30, 2025 earnings transcript</a>",
                    ),
                    artifact: response(artifact, transcript_body("April 30, 2025")),
                }), lambda: "2026-08-03T00:00:00Z", repository=repository,
            )
            first = AcquisitionEngine(
                repository, AdapterRegistry((adapter,)),
                lambda: "2026-08-03T00:00:00Z",
            ).run_source_trial(
                "source-a", "conflict-first",
                adapter.injected_trial(
                    configured, TranscriptAcquisitionTarget("firm-a"), seed
                ),
            )
            checkpoint = first.checkpoint_after
            checkpoint_state = repository.checkpoints()["sources"]["source-a"]

            with self.assertRaisesRegex(
                ConflictError,
                "checkpoint position is already bound to a different cursor",
            ):
                repository.advance_checkpoint(
                    "source-a",
                    checkpoint_state["attempt_id"],
                    Checkpoint(checkpoint.position, "intentionally-conflicting-cursor"),
                )

            self.assertEqual(first.checkpoint_after, checkpoint)
            self.assertEqual(
                repository.checkpoints()["sources"]["source-a"], checkpoint_state
            )

    def test_checkpoint_cursor_ignores_provenance_and_candidate_order(self) -> None:
        first = {
            "candidate-b": {
                "candidate_id": "candidate-b",
                "document_id": "document-b",
                "position": 2,
                "revision": "v1",
                "provenance": {"locations": ["https://one.example/b"]},
                "disposition": "acquire",
                "disposition_reason": None,
            },
            "candidate-a": {
                "candidate_id": "candidate-a",
                "document_id": "document-a",
                "position": 1,
                "revision": "v1",
                "provenance": {"locations": ["https://one.example/a"]},
                "disposition": "acquire",
                "disposition_reason": None,
            },
        }
        equivalent = {
            "candidate-a": {
                **first["candidate-a"],
                "provenance": {"locations": ["https://two.example/archive", "a"]},
            },
            "candidate-b": {
                **first["candidate-b"],
                "provenance": {"locations": ["https://two.example/b"]},
            },
        }
        revised = {
            **equivalent,
            "candidate-b": {**equivalent["candidate-b"], "revision": "v2"},
        }

        checkpoint = AcquisitionEngine._target_checkpoint(2, first)
        self.assertEqual(
            checkpoint, AcquisitionEngine._target_checkpoint(2, equivalent)
        )
        self.assertNotEqual(
            checkpoint.cursor,
            AcquisitionEngine._target_checkpoint(2, revised).cursor,
        )

    def test_newer_validated_artifact_advances_after_checkpoint_replay_repair(self) -> None:
        first_seed = "https://ir.example.com/archive-q1"
        first_artifact = "https://ir.example.com/q1-2025-earnings-call-transcript.html"
        newer_seed = "https://ir.example.com/archive-q2"
        newer_artifact = "https://ir.example.com/q2-2025-earnings-call-transcript.html"
        configured = source()
        responses = {
            first_seed: response(
                first_seed,
                f"<a href='{first_artifact}'>January 30, 2025 earnings transcript</a>",
            ),
            first_artifact: response(
                first_artifact, transcript_body("January 30, 2025")
            ),
            newer_seed: response(
                newer_seed,
                f"<a href='{newer_artifact}'>April 30, 2025 earnings transcript</a>",
            ),
            newer_artifact: response(
                newer_artifact, transcript_body("April 30, 2025")
            ),
        }

        for selection in (
            TranscriptAcquisitionSelection.latest(),
            TranscriptAcquisitionSelection.first_in_date_range(
                date(2025, 1, 1), date(2025, 12, 31)
            ),
        ):
            with self.subTest(selection=selection.mode.value), tempfile.TemporaryDirectory(
            ) as directory:
                repository = self._repository(directory, configured)
                adapter = EarningsTranscriptPullAdapter(
                    policies(), Search(), Transport(responses),
                    lambda: "2026-08-03T00:00:00Z", repository=repository,
                    selection=selection,
                )
                engine = AcquisitionEngine(
                    repository, AdapterRegistry((adapter,)),
                    lambda: "2026-08-03T00:00:00Z",
                )
                target = TranscriptAcquisitionTarget("firm-a", selection=selection)
                first = engine.run_source_trial(
                    "source-a", "first",
                    adapter.injected_trial(configured, target, first_seed),
                )
                newer = engine.run_source_trial(
                    "source-a", "newer",
                    adapter.injected_trial(configured, target, newer_seed),
                )

                self.assertEqual(first.durable_acquisitions, 1)
                self.assertEqual(newer.status, RunStatus.COMPLETE)
                self.assertEqual(newer.durable_acquisitions, 1)
                self.assertGreater(
                    newer.checkpoint_after.position, first.checkpoint_after.position
                )
                self.assertEqual(len(repository.artifact_metadata()), 2)
                self.assertEqual(
                    repository.discovery_anchors(
                        "firm-a", "source-a", adapter.adapter_id
                    )[0]["normalized_url"],
                    newer_artifact,
                )

    def test_partial_checkpoint_replay_cannot_claim_no_change(self) -> None:
        seed = "https://ir.example.com/archive"
        artifact = "https://ir.example.com/q1-2025-earnings-call-transcript.html"
        configured = source()
        with tempfile.TemporaryDirectory() as directory:
            repository = self._repository(directory, configured)
            adapter = EarningsTranscriptPullAdapter(
                policies(), Search(), Transport({
                    seed: response(
                        seed,
                        f"<a href='{artifact}'>January 30, 2025 earnings transcript</a>",
                    ),
                    artifact: response(artifact, transcript_body("January 30, 2025")),
                }), lambda: "2026-08-03T00:00:00Z", repository=repository,
            )
            target = TranscriptAcquisitionTarget("firm-a")
            first = AcquisitionEngine(
                repository, AdapterRegistry((adapter,)),
                lambda: "2026-08-03T00:00:00Z",
            ).run_source_trial(
                "source-a", "first", adapter.injected_trial(configured, target, seed)
            )
            replay = AcquisitionEngine(
                repository, AdapterRegistry((adapter,)),
                lambda: "2026-08-03T00:00:00Z",
            ).run_source_trial(
                "source-a", "partial", adapter.injected_trial(configured, target, seed),
                EngineFailurePoint.BEFORE_CHECKPOINT_FINALIZATION,
            )

        self.assertEqual(replay.status, RunStatus.PARTIAL)
        self.assertEqual(replay.unchanged, 0)
        self.assertEqual(replay.checkpoint_before, first.checkpoint_after)
        self.assertEqual(replay.checkpoint_after, first.checkpoint_after)

    def test_service_resolves_governed_firm_profile_without_configuration_write(self) -> None:
        seed = "https://ir.example.com/archive"
        artifact = "https://ir.example.com/q2-2025-transcript.html"
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            firms = FirmRepository.initialize(root / "firm-catalog")
            firms.create(FirmDraft(
                "firm-a", "Firm A", "2025-01-01", status=FirmStatus.ACTIVE
            ))
            template = load_canonical_template()
            profiles = SourceProfileRepository.initialize(root / "source-profiles", template)
            profiles.publish(SourceProfileDraft(
                "firm-a",
                tuple(
                    SourceProfileItem(
                        item.artifact_id,
                        item.artifact_id == "earnings_transcript",
                        (RetrievalCandidate(
                            "discovery", 1, discovery_class="standard",
                            discovery_hints=("identity:Firm A",),
                        ),) if item.artifact_id == "earnings_transcript" else (),
                    )
                    for item in template.artifacts
                ),
            ), None)
            repository = AcquisitionRepository(root / "acquisition")
            adapter = EarningsTranscriptPullAdapter(
                policies(), Search(), Transport({
                    seed: response(
                        seed,
                        f"<a href='{artifact}'>April 30, 2025 earnings call transcript</a>",
                    ),
                    artifact: response(artifact, transcript_body("April 30, 2025")),
                }), lambda: "2026-08-03T00:00:00Z", repository=repository,
            )
            registry = RetrievalAdapterRegistry((RetrievalAdapterRegistration(
                RetrievalAdapterCapability(
                    adapter.adapter_id, adapter.artifact_ids, adapter.retrieval_modes
                ),
                adapter,
            ),))
            workflow = PullWorkflow(
                firms, profiles, template, repository, registry,
                PullRunRepository(root / "pull-workflows"),
                lambda: "2026-08-03T00:00:00Z", lambda: "service",
            )
            before = profiles.get("firm-a")
            result = workflow.acquire_transcript_from_seed(
                TranscriptAcquisitionTarget("firm-a"), seed
            )
            after = profiles.get("firm-a")

        self.assertEqual(result.durable_acquisitions, 1)
        self.assertEqual(before, after)


class TranscriptSeedApiTests(unittest.TestCase):
    def test_rest_contract_defaults_latest_and_rejects_extra_or_multiple_seeds(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            state = Path(temporary)
            ConceptRepository.initialize(state)
            firms = FirmRepository.initialize(state / "firm-catalog")
            firms.create(sample_firms()[0])
            SourceProfileRepository.initialize(
                state / "source-profiles", load_canonical_template()
            )
            server = create_admin_server(state, port=0)
            result = Mock()
            result.to_dict.return_value = {"status": "complete"}
            server.pull_workflow.acquire_transcript_from_seed = Mock(return_value=result)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            host, port = server.server_address
            endpoint = f"http://{host}:{port}/api/transcript-acquisitions/seed"

            def post(payload: dict[str, object], suffix: str = "") -> tuple[int, dict]:
                request = urllib.request.Request(
                    endpoint + suffix,
                    data=json.dumps(payload).encode(),
                    method="POST",
                    headers={"Content-Type": "application/json"},
                )
                try:
                    with urllib.request.urlopen(request, timeout=3) as response:
                        return response.status, json.load(response)
                except urllib.error.HTTPError as error:
                    try:
                        return error.code, json.load(error)
                    finally:
                        error.close()

            def post_raw(payload: str) -> int:
                request = urllib.request.Request(
                    endpoint,
                    data=payload.encode(),
                    method="POST",
                    headers={"Content-Type": "application/json"},
                )
                try:
                    with urllib.request.urlopen(request, timeout=3) as response:
                        return response.status
                except urllib.error.HTTPError as error:
                    try:
                        return error.code
                    finally:
                        error.close()

            def post_target(
                target: str, payload: dict[str, object] | bytes
            ) -> tuple[int, dict]:
                connection = HTTPConnection(host, port, timeout=3)
                try:
                    connection.request(
                        "POST",
                        target,
                        body=(
                            payload
                            if isinstance(payload, bytes)
                            else json.dumps(payload).encode()
                        ),
                        headers={"Content-Type": "application/json"},
                    )
                    response = connection.getresponse()
                    return response.status, json.loads(response.read())
                finally:
                    connection.close()

            valid = {
                "firm_id": "seagate",
                "canonical_artifact_id": "earnings_transcript",
                "starting_seed": "https://ir.example.com/archive",
            }
            try:
                self.assertEqual(post(valid)[0], 200)
                target, seed = server.pull_workflow.acquire_transcript_from_seed.call_args.args
                self.assertEqual(target.selection.mode, TranscriptSelectionMode.LATEST)
                self.assertEqual(seed, valid["starting_seed"])
                server.pull_workflow.acquire_transcript_from_seed.reset_mock()
                for query in (
                    "?retry=1",
                    "?retry=",
                    "?retry",
                    "?retry=1&retry=2",
                    "?unknown=",
                    "?",
                ):
                    with self.subTest(query=query):
                        status, response_body = post_target(
                            "/api/transcript-acquisitions/seed" + query, valid
                        )
                        self.assertEqual(status, 400)
                        self.assertEqual(
                            response_body["error"],
                            "transcript seed acquisition does not accept query parameters",
                        )
                        self.assertEqual(response_body["error_code"], "invalid_request")
                server.pull_workflow.acquire_transcript_from_seed.assert_not_called()
                malformed_query_status, malformed_query_body = post_target(
                    "/api/transcript-acquisitions/seed?retry=", b"{"
                )
                self.assertEqual(malformed_query_status, 400)
                self.assertEqual(
                    malformed_query_body["error"],
                    "transcript seed acquisition does not accept query parameters",
                )
                self.assertEqual(malformed_query_body["error_code"], "invalid_request")
                self.assertEqual(post({**valid, "seeds": [valid["starting_seed"]]})[0], 400)
                self.assertEqual(post({**valid, "starting_seed": ["a", "b"]})[0], 400)
                self.assertEqual(post_raw("{"), 400)
                self.assertEqual(post_raw(
                    '{"firm_id":"seagate","canonical_artifact_id":'
                    '"earnings_transcript","starting_seed":"https://one.example",'
                    '"starting_seed":"https://two.example"}'
                ), 400)
                server.pull_workflow.acquire_transcript_from_seed.assert_not_called()
                range_request = {
                    **valid,
                    "selection": {
                        "mode": "first_in_date_range",
                        "start_date": "2025-01-01",
                        "end_date": "2025-12-31",
                    },
                }
                self.assertEqual(post(range_request)[0], 200)
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=3)


if __name__ == "__main__":
    unittest.main()
