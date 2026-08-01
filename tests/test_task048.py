"""Focused acceptance evidence for TASK-048 earnings-call transcripts."""

from __future__ import annotations

import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import MagicMock, patch

from rfi.acquisition import (
    AcquisitionRepository,
    EarningsCallTranscriptAcquisition,
    EarningsTranscriptHttpResponse,
    EarningsTranscriptTransport,
    IntervalAcquisitionRequest,
    IntervalAcquisitionService,
    IntervalCoverage,
    SourceProfile,
    UrllibEarningsTranscriptTransport,
)
from rfi.acquisition.earnings_transcripts import TRANSCRIPT_ACCEPT
from rfi.discovery import DuckDuckGoHtmlSearch
from rfi.firms import FirmRepository
from rfi.firms.contracts import FirmDraft, FirmStatus
from rfi.source_profiles import load_canonical_template


class FixtureTransport(EarningsTranscriptTransport):
    def __init__(self, responses: dict[str, EarningsTranscriptHttpResponse | Exception]) -> None:
        self.responses = responses
        self.requested: list[str] = []

    def get(self, url: str) -> EarningsTranscriptHttpResponse:
        self.requested.append(url)
        response = self.responses[url]
        if isinstance(response, Exception):
            raise response
        return response


def html(url: str, body: str) -> EarningsTranscriptHttpResponse:
    return EarningsTranscriptHttpResponse(url, 200, "text/html", body.encode())


def pdf(url: str) -> EarningsTranscriptHttpResponse:
    return EarningsTranscriptHttpResponse(url, 200, "application/pdf", b"%PDF-1.7\nfixture")


class EarningsTranscriptTests(unittest.TestCase):
    listing = "https://ir.example.com/quarterly-results"

    def profile(self, **configuration: object) -> SourceProfile:
        values: dict[str, object] = {
            "listing_urls": [self.listing],
            "allowed_hosts": ["cdn.example.com"],
            "authoritative_listing": True,
            "maximum_candidates": 40,
        }
        values.update(configuration)
        return SourceProfile(
            "source-example-earnings-transcripts", "Example official IR transcripts", True,
            "earnings_transcript", configuration=values,
            policy={"firm_id": "example-firm", "artifact_id": "earnings_transcript"},
        )

    def request(self, start: str = "2026-01-01", end: str = "2026-04-01"):
        return IntervalAcquisitionRequest(
            "example-firm", "earnings_transcript", date.fromisoformat(start),
            date.fromisoformat(end),
        )

    def acquire(self, listing_body: str, responses=None, **configuration):
        transport = FixtureTransport({
            self.listing: html(self.listing, listing_body), **(responses or {})
        })
        result = EarningsCallTranscriptAcquisition(
            self.profile(**configuration), transport, lambda: "2026-07-29T12:00:00Z"
        ).acquire(self.request())
        return result, transport

    @staticmethod
    def transcript(day: str) -> str:
        return (
            f"<!doctype html><html><title>Earnings Call Transcript {day}</title>"
            "<body>Quarterly earnings conference call transcript. Operator: Welcome. "
            "Chief Executive Officer: Thank you. Questions and Answers</body></html>"
        )

    def test_empty_interval_is_complete_without_network_and_no_result_can_be_complete(self) -> None:
        transport = FixtureTransport({})
        retriever = EarningsCallTranscriptAcquisition(self.profile(), transport)
        empty = retriever.acquire(self.request("2026-01-01", "2026-01-01"))
        self.assertEqual(empty.coverage, IntervalCoverage.COMPLETE)
        self.assertEqual(transport.requested, [])
        no_result, _ = self.acquire("<html><a href='release.pdf'>Earnings release</a></html>")
        self.assertEqual(no_result.artifacts, ())
        self.assertEqual(no_result.coverage, IntervalCoverage.COMPLETE)

    def test_live_transport_negotiates_only_supported_transcript_representations(self) -> None:
        response = MagicMock()
        response.__enter__.return_value = response
        response.read.return_value = b"<!doctype html><html></html>"
        response.geturl.return_value = self.listing
        response.status = 200
        response.headers.get_content_type.return_value = "text/html"
        with patch(
            "rfi.acquisition.earnings_transcripts.urllib.request.urlopen",
            return_value=response,
        ) as urlopen:
            result = UrllibEarningsTranscriptTransport().get(self.listing)

        request = urlopen.call_args.args[0]
        self.assertEqual(
            request.get_header("Accept"),
            TRANSCRIPT_ACCEPT,
        )
        self.assertEqual(request.get_header("User-agent"), "RFI-1 transcript acquisition")
        self.assertEqual(result.media_type, "text/html")

    def test_transcript_search_negotiates_the_same_supported_representations(self) -> None:
        response = MagicMock()
        response.__enter__.return_value = response
        response.read.return_value = (
            b"<html><a class='result__a' href='https://example.com/transcript'>"
            b"Transcript</a></html>"
        )
        with patch(
            "rfi.discovery.urllib.request.urlopen", return_value=response
        ) as urlopen:
            result = DuckDuckGoHtmlSearch().search("Example transcript", 1)

        request = urlopen.call_args.args[0]
        self.assertEqual(request.get_header("Accept"), TRANSCRIPT_ACCEPT)
        self.assertEqual(
            request.get_header("User-agent"), "RFI-1 bounded source discovery"
        )
        self.assertEqual(result.urls, ("https://example.com/transcript",))

    def test_one_multiple_html_pdf_and_closed_open_boundaries(self) -> None:
        urls = {
            day: f"https://ir.example.com/transcripts/earnings-call-transcript-{day}.html"
            for day in ("2025-12-31", "2026-01-01", "2026-03-31", "2026-04-01")
        }
        pdf_url = "https://cdn.example.com/2026-02-10-quarterly-earnings-call-transcript.pdf"
        links = "".join(
            f"<a href='{url}'>Quarterly earnings call transcript {day}</a>"
            for day, url in urls.items()
        ) + f"<a href='{pdf_url}'>Quarterly earnings call transcript February 10, 2026</a>"
        responses = {url: html(url, self.transcript(day)) for day, url in urls.items()}
        responses[pdf_url] = pdf(pdf_url)
        result, _ = self.acquire(f"<html>{links}</html>", responses)
        self.assertEqual(result.coverage, IntervalCoverage.COMPLETE)
        self.assertEqual(
            {item.artifact_date for item in result.artifacts},
            {date(2026, 1, 1), date(2026, 2, 10), date(2026, 3, 31)},
        )
        self.assertEqual(
            {item.retrieval.media_type for item in result.artifacts},
            {"text/html", "application/pdf"},
        )

    def test_excludes_releases_presentations_unrelated_calls_and_non_text_media(self) -> None:
        body = """<html>
          <a href='/2026-02-01-earnings-release.pdf'>Earnings release</a>
          <a href='/2026-02-01-earnings-presentation.pdf'>Earnings presentation</a>
          <a href='/2026-02-01-investor-day-transcript.pdf'>Investor day transcript</a>
          <a href='/2026-02-01-product-call-transcript.mp3'>Product call transcript</a>
        </html>"""
        result, transport = self.acquire(body)
        self.assertEqual(result.artifacts, ())
        self.assertEqual(transport.requested, [self.listing])

    def test_complete_incomplete_and_indeterminate_coverage(self) -> None:
        complete, _ = self.acquire("<html></html>")
        self.assertEqual(complete.coverage, IntervalCoverage.COMPLETE)
        indeterminate, _ = self.acquire("<html></html>", authoritative_listing=False)
        self.assertEqual(indeterminate.coverage, IntervalCoverage.INDETERMINATE)
        broken = self.profile(listing_urls=[self.listing, "https://ir.example.com/archive"])
        transport = FixtureTransport({self.listing: html(self.listing, "<html></html>"),
                                      "https://ir.example.com/archive": TimeoutError("timed out")})
        incomplete = EarningsCallTranscriptAcquisition(broken, transport).acquire(self.request())
        self.assertEqual(incomplete.coverage, IntervalCoverage.INCOMPLETE)
        self.assertEqual(incomplete.failures[0].code, "listing_unavailable")

    def test_partial_success_retains_artifact_and_structured_candidate_failure(self) -> None:
        good = "https://ir.example.com/2026-02-01-earnings-call-transcript.html"
        bad = "https://ir.example.com/2026-03-01-earnings-call-transcript.pdf"
        links = (
            f"<a href='{good}'>Quarterly earnings call transcript 2026-02-01</a>"
            f"<a href='{bad}'>Quarterly earnings call transcript 2026-03-01</a>"
        )
        result, _ = self.acquire(
            f"<html>{links}</html>",
            {good: html(good, self.transcript("2026-02-01")), bad: TimeoutError("timed out")},
        )
        self.assertEqual(len(result.artifacts), 1)
        self.assertEqual(result.coverage, IntervalCoverage.INCOMPLETE)
        self.assertEqual(result.failures[0].code, "candidate_unavailable")
        self.assertTrue(result.failures[0].source_artifact_id)

    def test_reacquisition_uses_repository_ingress_identity_and_observations(self) -> None:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        firms = FirmRepository.initialize(root / "firms")
        firms.create(FirmDraft(
            "example-firm", "Example Firm", "2026-01-01", status=FirmStatus.ACTIVE
        ))
        repository = AcquisitionRepository(root / "acquisition")
        repository.register_source(self.profile())
        service = IntervalAcquisitionService(firms, load_canonical_template(), repository)
        url = "https://ir.example.com/2026-02-01-quarterly-earnings-call-transcript.html"
        result, _ = self.acquire(
            f"<html><a href='{url}'>Quarterly earnings call transcript 2026-02-01</a></html>",
            {url: html(url, self.transcript("2026-02-01"))},
        )
        first = service.record(self.request(), result)
        second = service.record(self.request(), result)
        self.assertTrue(first.artifacts[0].artifact_created)
        self.assertFalse(second.artifacts[0].artifact_created)
        self.assertEqual(first.artifacts[0].artifact_id, second.artifacts[0].artifact_id)
        self.assertEqual(len(repository.artifact_metadata()), 1)
        self.assertEqual(len(repository.observations()), 2)
        self.assertEqual(repository.verify_integrity()["result"], "PASS")

    def test_candidate_proposals_cannot_bypass_validation_or_official_host_policy(self) -> None:
        invalid = "https://outside.example/2026-02-01-earnings-call-transcript.html"
        result, _ = self.acquire(
            "<html></html>", candidate_proposals=[{
                "url": invalid, "label": "Quarterly earnings call transcript 2026-02-01"
            }],
        )
        self.assertEqual(result.artifacts, ())
        self.assertEqual(result.coverage, IntervalCoverage.INCOMPLETE)
        self.assertIn("official-source policy", result.failures[0].message)

        malformed, _ = self.acquire(
            "<html></html>", candidate_proposals=[{"url": "not-a-url", "label": "transcript"}],
        )
        self.assertEqual(malformed.failures[0].code, "candidate_invalid")
        self.assertFalse(malformed.failures[0].retryable)

    def test_retriever_has_no_persistence_dependency(self) -> None:
        source = Path("src/rfi/acquisition/earnings_transcripts.py").read_text()
        self.assertNotIn("AcquisitionRepository", source)
        self.assertNotIn("record_success", source)
        self.assertNotIn("rfi.storage.sqlite import RepositoryDatabase", source)


if __name__ == "__main__":
    unittest.main()
