"""Focused integration evidence for TASK-048A Pull Sources wiring."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from rfi.acquisition import (
    AcquisitionEngine,
    AcquisitionRepository,
    AdapterRegistry,
    EarningsTranscriptHttpResponse,
    EarningsTranscriptPullAdapter,
    EarningsTranscriptTransport,
    SourceProfile,
    RunStatus,
)
from rfi.firm_configuration import prepare_firm_configuration
from rfi.pull import create_pull_workflow
from rfi.source_profiles import SourceProfileRepository, load_canonical_template
from rfi.storage import RepositoryDatabase


class TranscriptTransport(EarningsTranscriptTransport):
    def __init__(self, responses: dict[str, EarningsTranscriptHttpResponse]) -> None:
        self.responses = responses

    def get(self, url: str) -> EarningsTranscriptHttpResponse:
        return self.responses[url]


class TranscriptPullIntegrationTests(unittest.TestCase):
    def test_production_registry_declares_transcript_listing_capability(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            state = Path(directory)
            RepositoryDatabase.initialize(state)
            capabilities = create_pull_workflow(state).adapter_capabilities()
        transcript = next(
            item for item in capabilities if item["adapter_id"] == "earnings-call-transcript"
        )
        self.assertEqual(transcript["artifact_ids"], ["earnings_transcript"])
        self.assertEqual(transcript["retrieval_modes"], ["listing_page"])

    def test_file_authority_enables_governed_transcript_candidate_read_only(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            state = Path(directory)
            RepositoryDatabase.initialize(state)
            target = state / "firm-config"
            target.mkdir()
            target.joinpath("microsoft.firm-config.json").write_text(
                Path("docs/microsoft.firm-config.example.json").read_text(encoding="utf-8"),
                encoding="utf-8",
            )
            prepare_firm_configuration(state)
            profile = SourceProfileRepository.open(
                state / "source-profiles", load_canonical_template()
            ).get("microsoft")
            self.assertIsNotNone(profile)
            transcript = next(
                item for item in profile.items if item.artifact_id == "earnings_transcript"
            )
            self.assertTrue(transcript.enabled)
            self.assertEqual(transcript.retrieval_candidates[0].parser_hint, "")
            self.assertEqual(
                transcript.retrieval_candidates[0].preferred_domains,
                ("www.microsoft.com",),
            )

    def test_adapter_executes_listing_and_returns_repository_contracts(self) -> None:
        listing = "https://ir.example.com/events"
        transcript = "https://ir.example.com/2026-01-28-earnings-call-transcript.html"
        transport = TranscriptTransport({
            listing: EarningsTranscriptHttpResponse(
                listing, 200, "text/html",
                (
                    f"<html><a href='{transcript}'>"
                    "Earnings Call Transcript January 28, 2026</a></html>"
                ).encode(),
            ),
            transcript: EarningsTranscriptHttpResponse(
                transcript, 200, "text/html",
                b"<!doctype html><html>Quarterly earnings call transcript. "
                b"Operator: Welcome. Chief Executive Officer: Remarks.</html>",
            ),
        })
        source = SourceProfile(
            "source-pull-example", "Example transcripts", True, "earnings_transcript",
            {"mode": "listing_page", "url": listing,
             "preferred_domains": ["ir.example.com"]},
            {"firm_id": "example", "artifact_id": "earnings_transcript"},
        )
        adapter = EarningsTranscriptPullAdapter(
            transport, lambda: "2026-07-30T12:00:00+00:00"
        )
        page = adapter.discover(source, None)
        self.assertEqual(len(page.candidates), 1)
        result = adapter.retrieve(source, page.candidates[0])
        self.assertEqual(result.content, transport.responses[transcript].content)
        self.assertEqual(result.mechanism, "earnings_transcript")

    def test_enabled_empty_official_listing_is_no_change_not_system_failure(self) -> None:
        listing = "https://ir.example.com/events"
        transport = TranscriptTransport({
            listing: EarningsTranscriptHttpResponse(
                listing, 200, "text/html", b"<html><a href='call.mp3'>Webcast</a></html>"
            )
        })
        source = SourceProfile(
            "source-empty-transcripts", "Empty official listing", True,
            "earnings_transcript",
            {"mode": "listing_page", "url": listing,
             "preferred_domains": ["ir.example.com"]},
            {"firm_id": "example", "artifact_id": "earnings_transcript"},
        )
        with tempfile.TemporaryDirectory() as directory:
            repository = AcquisitionRepository(Path(directory) / "acquisition")
            repository.register_source(source)
            adapter = EarningsTranscriptPullAdapter(
                transport, lambda: "2026-07-30T12:00:00+00:00"
            )
            result = AcquisitionEngine(
                repository, AdapterRegistry((adapter,)),
                lambda: "2026-07-30T12:00:00+00:00",
            ).run_source(source.source_id, "empty-listing")
        self.assertEqual(result.status, RunStatus.COMPLETE)
        self.assertEqual(result.candidates_discovered, 0)
        self.assertEqual(result.failures, 0)
        self.assertEqual(result.durable_acquisitions, 0)


if __name__ == "__main__":
    unittest.main()
