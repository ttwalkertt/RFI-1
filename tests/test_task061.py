"""Focused acceptance evidence for TASK-061 transcript learning inspection."""

from __future__ import annotations

import json
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from pathlib import Path

from rfi.acquisition import (
    AcquisitionRepository,
    CandidateDocument,
    DiscoveryProvenance,
    EarningsTranscriptHttpResponse,
    RetrievalResult,
    SourceProfile,
)
from rfi.admin import create_admin_server
from rfi.concepts import ConceptRepository
from rfi.discovery import (
    DiscoveryPolicy,
    DiscoveryPolicyCatalog,
    DiscoverySearchResponse,
    EarningsTranscriptPullAdapter,
)
from rfi.firms import FirmRepository
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

    def get(self, url: str) -> EarningsTranscriptHttpResponse:
        return self.responses[url]


def response(url: str, body: str) -> EarningsTranscriptHttpResponse:
    return EarningsTranscriptHttpResponse(
        url, 200, "text/html", f"<html>{body}</html>".encode()
    )


class TranscriptLearningInspectionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.state = Path(self.temporary.name)
        ConceptRepository.initialize(self.state)
        self.firms = FirmRepository.initialize(self.state / "firm-catalog")
        self.firms.create(
            FirmDraft("firm-a", "Firm A", "2025-01-01", status=FirmStatus.ACTIVE)
        )
        self.template = load_canonical_template()
        self.profiles = SourceProfileRepository.initialize(
            self.state / "source-profiles", self.template
        )
        self.repository = AcquisitionRepository(self.state / "acquisition")
        self.source = SourceProfile(
            "source-a",
            "Firm A transcripts",
            True,
            "earnings_transcript",
            {},
            {
                "firm_id": "firm-a",
                "artifact_id": "earnings_transcript",
                "retrieval_adapter_id": "earnings-call-transcript",
                "source_profile_revision_id": "profile-r1",
            },
        )
        self.repository.register_source(self.source)

    def _learn(self, name: str, url: str) -> None:
        candidate = CandidateDocument(
            f"candidate-{name}",
            self.source.source_id,
            f"document-{name}",
            DiscoveryProvenance(
                "2026-08-03T00:00:00Z",
                "earnings_transcript",
                locations=(url,),
                metadata={"requested_url": url},
            ),
        )
        self.repository.record_success(
            f"attempt-{name}",
            candidate,
            RetrievalResult(
                f"artifact-{name}".encode(),
                "text/html",
                "2026-08-03T00:00:00Z",
                "earnings_transcript",
                diagnostics={"final_url": url},
            ),
        )

    def _serve(self, workflow: PullWorkflow | None = None):
        server = create_admin_server(self.state, port=0)
        if workflow is not None:
            server.pull_workflow = workflow
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        host, port = server.server_address
        return server, thread, f"http://{host}:{port}"

    @staticmethod
    def _request(
        base: str, path: str, method: str = "GET", payload: dict | None = None
    ) -> tuple[int, dict]:
        body = json.dumps(payload).encode() if payload is not None else None
        request = urllib.request.Request(
            base + path,
            data=body,
            method=method,
            headers={"Content-Type": "application/json"} if body else {},
        )
        try:
            with urllib.request.urlopen(request, timeout=3) as result:
                return result.status, json.load(result)
        except urllib.error.HTTPError as error:
            try:
                return error.code, json.load(error)
            finally:
                error.close()

    def test_empty_learning_state_returns_success(self) -> None:
        server, thread, base = self._serve()
        try:
            status, body = self._request(
                base, "/api/transcript-acquisitions/learning/firm-a"
            )
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=3)
        self.assertEqual(status, 200)
        self.assertEqual(body, {"firm_id": "firm-a", "learning": []})

    def test_populated_learning_preserves_persisted_repository_order(self) -> None:
        urls = [f"https://ir.example.com/call-{number}" for number in range(3)]
        for number, url in enumerate(urls):
            self._learn(str(number), url)
        expected = self.repository.discovery_anchors(
            "firm-a", "source-a", "earnings-call-transcript"
        )
        server, thread, base = self._serve()
        try:
            status, body = self._request(
                base, "/api/transcript-acquisitions/learning/firm-a"
            )
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=3)
        self.assertEqual(status, 200)
        self.assertEqual(body["learning"], list(expected))
        self.assertEqual(
            [item["normalized_url"] for item in body["learning"]],
            list(reversed(urls)),
        )

    def test_unknown_firm_uses_existing_api_error_convention(self) -> None:
        server, thread, base = self._serve()
        try:
            status, body = self._request(
                base, "/api/transcript-acquisitions/learning/unknown-firm"
            )
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=3)
        self.assertEqual(status, 400)
        self.assertEqual(body["error"], "unknown firm: unknown-firm")
        self.assertEqual(body["error_code"], "invalid_request")

    def test_repeated_reads_do_not_mutate_repository_state(self) -> None:
        self._learn("one", "https://ir.example.com/call-one")
        before = {
            "revision": self.repository.repository_revision(),
            "sources": self.repository.sources(),
            "history": self.repository.history(),
            "artifacts": self.repository.artifact_metadata(),
            "checkpoints": self.repository.checkpoints(),
            "learning": self.repository.transcript_learning("firm-a"),
        }
        server, thread, base = self._serve()
        try:
            first = self._request(base, "/api/transcript-acquisitions/learning/firm-a")
            second = self._request(base, "/api/transcript-acquisitions/learning/firm-a")
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=3)
        after = {
            "revision": self.repository.repository_revision(),
            "sources": self.repository.sources(),
            "history": self.repository.history(),
            "artifacts": self.repository.artifact_metadata(),
            "checkpoints": self.repository.checkpoints(),
            "learning": self.repository.transcript_learning("firm-a"),
        }
        self.assertEqual(first, second)
        self.assertEqual(before, after)

    def test_injected_acquisition_is_visible_through_learning_endpoint(self) -> None:
        seed = "https://stockanalysis.com/stocks/orcl/transcripts/"
        q4 = "https://stockanalysis.com/stocks/orcl/transcripts/32001-q4-2026/"
        q3 = "https://stockanalysis.com/stocks/orcl/transcripts/31001-q3-2026/"
        artifact = "https://stockanalysis.com/stocks/orcl/transcripts/30001-q2-2026/"
        q1 = "https://stockanalysis.com/stocks/orcl/transcripts/29001-q1-2026/"
        archive = "".join((
            f"<a href='{q4}'>Earnings Call: Q4 2026</a>",
            f"<a href='{q3}'>Earnings Call: Q3 2026</a>",
            f"<a href='{artifact}'>Earnings Call: Q2 2026</a>",
            f"<a href='{q1}'>Earnings Call: Q1 2026</a>",
        ))
        validated = (
            "Firm A quarterly earnings call transcript August 3, 2026. "
            "Operator. Chief Executive Officer. Prepared remarks."
        )
        self.profiles.publish(
            SourceProfileDraft(
                "firm-a",
                tuple(
                    SourceProfileItem(
                        item.artifact_id,
                        item.artifact_id == "earnings_transcript",
                        (
                            RetrievalCandidate(
                                "discovery",
                                1,
                                discovery_class="standard",
                                discovery_hints=("identity:Firm A",),
                            ),
                        )
                        if item.artifact_id == "earnings_transcript"
                        else (),
                    )
                    for item in self.template.artifacts
                ),
            ),
            None,
        )
        adapter = EarningsTranscriptPullAdapter(
            DiscoveryPolicyCatalog(
                {"standard": DiscoveryPolicy(1, 5, 1000, 2, 20, 8, 2_000_000, 60)},
                "standard",
            ),
            Search(),
            Transport(
                {
                    seed: response(seed, archive),
                    q4: response(q4, validated),
                    q3: response(q3, validated),
                    artifact: response(artifact, validated),
                    q1: response(q1, validated),
                }
            ),
            lambda: "2026-08-03T00:00:00Z",
            repository=self.repository,
        )
        workflow = PullWorkflow(
            self.firms,
            self.profiles,
            self.template,
            self.repository,
            RetrievalAdapterRegistry(
                (
                    RetrievalAdapterRegistration(
                        RetrievalAdapterCapability(
                            adapter.adapter_id,
                            adapter.artifact_ids,
                            adapter.retrieval_modes,
                        ),
                        adapter,
                    ),
                )
            ),
            PullRunRepository(self.state / "pull-workflows"),
            lambda: "2026-08-03T00:00:00Z",
            lambda: "task061",
        )
        server, thread, base = self._serve(workflow)
        try:
            acquisition_status, acquisition = self._request(
                base,
                "/api/transcript-acquisitions/seed",
                "POST",
                {
                    "firm_id": "firm-a",
                    "canonical_artifact_id": "earnings_transcript",
                    "starting_seed": seed,
                },
            )
            checkpoint = self.repository.checkpoints()
            snapshot = {
                "revision": self.repository.repository_revision(),
                "history": self.repository.history(),
                "artifacts": self.repository.artifact_metadata(),
                "observations": self.repository.observations(),
                "learning": self.repository.transcript_learning("firm-a"),
            }
            replay_status, replay = self._request(
                base,
                "/api/transcript-acquisitions/seed",
                "POST",
                {
                    "firm_id": "firm-a",
                    "canonical_artifact_id": "earnings_transcript",
                    "starting_seed": seed,
                },
            )
            learning_status, learning = self._request(
                base, "/api/transcript-acquisitions/learning/firm-a"
            )
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=3)
        self.assertEqual(acquisition_status, 200, acquisition)
        self.assertEqual(acquisition["durable_acquisitions"], 1)
        self.assertEqual(replay_status, 200, replay)
        self.assertEqual(replay["durable_acquisitions"], 0)
        self.assertEqual(replay["unchanged"], 1)
        self.assertEqual(self.repository.checkpoints(), checkpoint)
        self.assertEqual(self.repository.repository_revision(), snapshot["revision"])
        self.assertEqual(self.repository.history(), snapshot["history"])
        self.assertEqual(self.repository.artifact_metadata(), snapshot["artifacts"])
        self.assertEqual(self.repository.observations(), snapshot["observations"])
        self.assertEqual(
            self.repository.transcript_learning("firm-a"), snapshot["learning"]
        )
        self.assertEqual(learning_status, 200)
        self.assertEqual(len(learning["learning"]), 1)
        self.assertEqual(learning["learning"][0]["normalized_url"], artifact)
        self.assertEqual(learning["learning"][0]["requested_url"], artifact)


if __name__ == "__main__":
    unittest.main()
