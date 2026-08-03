"""Focused acceptance evidence for TASK-060 operator seed injection."""

from __future__ import annotations

import json
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
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
    TranscriptAcquisitionTarget,
    TranscriptSelectionMode,
)
from rfi.acquisition.contracts import ContractError
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

    def test_injected_and_learned_seed_use_one_identical_trial_method(self) -> None:
        seed = "https://ir.example.com/archive"
        artifact = "https://ir.example.com/q2-2025-transcript.html"
        responses = {
            seed: response(
                seed, f"<a href='{artifact}'>April 30, 2025 earnings call transcript</a>"
            ),
            artifact: response(artifact, transcript_body("April 30, 2025")),
        }
        configured = source()

        with tempfile.TemporaryDirectory() as first, tempfile.TemporaryDirectory() as second:
            learned_repository = self._repository(first, configured)
            learned_adapter = EarningsTranscriptPullAdapter(
                policies(), Search(), Transport(responses),
                lambda: "2026-08-03T00:00:00Z", repository=learned_repository,
            )
            with patch.object(
                learned_repository, "discovery_anchors",
                return_value=({
                    "normalized_url": seed,
                    "requested_url": seed,
                    "resolved_url": None,
                },),
            ), patch.object(
                learned_adapter, "discover_trial", wraps=learned_adapter.discover_trial
            ) as learned_trial:
                learned = AcquisitionEngine(
                    learned_repository, AdapterRegistry((learned_adapter,)),
                    lambda: "2026-08-03T00:00:00Z",
                ).run_source("source-a", "learned")

            injected_repository = self._repository(second, configured)
            injected_adapter = EarningsTranscriptPullAdapter(
                policies(), Search(), Transport(responses),
                lambda: "2026-08-03T00:00:00Z", repository=injected_repository,
            )
            target = TranscriptAcquisitionTarget("firm-a")
            trial = injected_adapter.injected_trial(configured, target, seed)
            with patch.object(
                injected_adapter, "discover_trial", wraps=injected_adapter.discover_trial
            ) as injected_trial:
                injected = AcquisitionEngine(
                    injected_repository, AdapterRegistry((injected_adapter,)),
                    lambda: "2026-08-03T00:00:00Z",
                ).run_source_trial("source-a", "injected", trial)
            successful = [item for item in injected_repository.history()
                          if item.get("record_type") == "retrieval_attempt"
                          and item.get("outcome") == "success"]

        self.assertEqual(learned.durable_acquisitions, 1)
        self.assertEqual(injected.durable_acquisitions, 1)
        learned_trial.assert_called_once()
        injected_trial.assert_called_once()
        self.assertIsInstance(
            learned_trial.call_args.args[1], type(injected_trial.call_args.args[1])
        )
        diagnostic = injected.diagnostics[0]
        self.assertEqual(diagnostic["seed_kind"], "operator_supplied")
        self.assertEqual(diagnostic["starting_seed"], seed)
        self.assertEqual(diagnostic["trial_outcome"], "validated_success")
        self.assertEqual(len([item for item in injected.diagnostics if "trial_id" in item]), 1)
        self.assertEqual(successful[0]["candidate"]["provenance"]["locations"][-1], artifact)

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
                self.assertEqual(post({**valid, "seeds": [valid["starting_seed"]]})[0], 400)
                self.assertEqual(post({**valid, "starting_seed": ["a", "b"]})[0], 400)
                self.assertEqual(post_raw(
                    '{"firm_id":"seagate","canonical_artifact_id":'
                    '"earnings_transcript","starting_seed":"https://one.example",'
                    '"starting_seed":"https://two.example"}'
                ), 400)
                self.assertEqual(post(valid, "?retry=true")[0], 400)
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
