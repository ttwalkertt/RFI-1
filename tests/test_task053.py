"""Focused regression evidence for TASK-053 traversal-budget semantics."""

from __future__ import annotations

import json
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

from rfi.acquisition import EarningsTranscriptHttpResponse, SourceProfile
from rfi.acquisition.earnings_transcripts import TRANSCRIPT_ACCEPT
from rfi.discovery import (
    BoundedTranscriptDiscovery,
    BudgetedTranscriptTransport,
    DiscoveryPolicy,
    DiscoveryPolicyCatalog,
    DiscoverySearchResponse,
    EarningsTranscriptPullAdapter,
    TranscriptDiscoveryResult,
)
from rfi.firm_configuration import prepare_firm_configuration
from rfi.pull import ArtifactOutcome, PullRequest, create_pull_workflow
from rfi.storage import RepositoryDatabase


HINT = "https://directory.example/transcripts/"
STOCK_ANALYSIS_HINT = "https://stockanalysis.com/stocks/amzn/transcripts/"


class LiveHttpResponse:
    def __init__(self, url: str, content: bytes) -> None:
        self._url = url
        self._content = content
        self.status = 200
        self.headers = self

    def __enter__(self) -> LiveHttpResponse:
        return self

    def __exit__(self, *_args: object) -> None:
        return None

    def read(self, limit: int) -> bytes:
        return self._content[:limit]

    def geturl(self) -> str:
        return self._url

    def get_content_type(self) -> str:
        return "text/html"


class RecordingSearch:
    endpoint = "https://search.example/results"

    def __init__(self, urls: tuple[str, ...] = ()) -> None:
        self.urls = urls
        self.queries: list[tuple[str, int]] = []

    def search(self, query: str, limit: int) -> DiscoverySearchResponse:
        self.queries.append((query, limit))
        return DiscoverySearchResponse(self.urls, 10)


class RecordingTransport:
    def __init__(self, responses: dict[str, EarningsTranscriptHttpResponse]) -> None:
        self.responses = responses
        self.requests: list[str] = []

    def get(self, url: str) -> EarningsTranscriptHttpResponse:
        self.requests.append(url)
        return self.responses[url]


def policy(**changes: int) -> DiscoveryPolicy:
    return replace(DiscoveryPolicy(4, 10, 2, 2, 30, 8, 20_971_520, 60), **changes)


def transcript_url(index: int) -> str:
    return f"https://directory.example/amzn-q{index}-2026-earnings-call-transcript.html"


def response(url: str, content: bytes) -> EarningsTranscriptHttpResponse:
    return EarningsTranscriptHttpResponse(url, 200, "text/html", content)


def source() -> SourceProfile:
    return SourceProfile(
        "source-amazon", "Amazon transcripts", True, "earnings_transcript",
        {"mode": "discovery", "discovery_hints": [HINT, "Amazon.com, Inc."],
         "discovery_class": "standard"},
        {"firm_id": "amazon", "artifact_id": "earnings_transcript"},
    )


class TraversalBudgetSemanticsTests(unittest.TestCase):
    def discover(
        self, body: bytes, *, selected: DiscoveryPolicy | None = None
    ) -> tuple[TranscriptDiscoveryResult, RecordingTransport]:
        transport = RecordingTransport({HINT: response(HINT, body)})
        bounded = BudgetedTranscriptTransport(transport, selected or policy())
        result = BoundedTranscriptDiscovery(
            RecordingSearch(), bounded, bounded.policy
        ).discover((), (HINT,))
        return result, transport

    def test_irrelevant_raw_links_do_not_reject_page_or_consume_budget(self) -> None:
        irrelevant = "".join(
            f"<a href='/navigation/{index}'>Navigation {index}</a>" for index in range(40)
        )
        candidate = transcript_url(1)
        result, _ = self.discover(
            f"<html>{irrelevant}<a href='{candidate}'>Amazon earnings call transcript</a>"
            "<a href='mailto:ir@example.com'>Contact</a></html>".encode()
        )

        self.assertEqual([item["url"] for item in result.candidate_proposals], [candidate])
        self.assertFalse(result.exhausted)
        self.assertEqual(result.diagnostics["raw_hyperlinks"], 42)
        self.assertEqual(result.diagnostics["eligible_hyperlinks"], 1)
        self.assertEqual(result.diagnostics["traversed_hyperlinks"], 1)
        self.assertEqual(result.diagnostics["exhausted_budget"], "")

    def test_budget_is_applied_after_filtering_and_never_exceeded(self) -> None:
        irrelevant = (
            "<a href='/'>Home</a><a href='/legal'>Legal</a>"
            "<a href='https://social.example/share'>Share</a>"
            "<a href='/assets/report'>Annual report</a>"
        )
        links = "".join(
            f"<a href='{transcript_url(index)}'>Q{index} earnings call transcript</a>"
            for index in range(1, 4)
        )
        result, _ = self.discover(f"<html>{irrelevant}{links}</html>".encode())

        self.assertTrue(result.exhausted)
        self.assertEqual(
            result.diagnostics["exhausted_budget"],
            "max_unique_eligible_links_per_page",
        )
        self.assertEqual(result.diagnostics["raw_hyperlinks"], 7)
        self.assertEqual(result.diagnostics["eligible_hyperlinks"], 3)
        self.assertEqual(result.diagnostics["traversed_hyperlinks"], 2)
        self.assertEqual(len(result.candidate_proposals), 2)

    def test_candidates_are_prioritized_ahead_of_intermediate_transcript_pages(self) -> None:
        candidate = transcript_url(1)
        body = (
            "<html><a href='/aaa-transcripts/'>Transcript archive</a>"
            f"<a href='{candidate}'>Amazon earnings call transcript</a></html>"
        ).encode()
        result, transport = self.discover(
            body, selected=policy(max_unique_eligible_links_per_page=1)
        )

        self.assertEqual([item["url"] for item in result.candidate_proposals], [candidate])
        self.assertEqual(transport.requests, [HINT])
        self.assertEqual(result.diagnostics["traversed_hyperlinks"], 1)
        self.assertEqual(
            result.diagnostics["exhausted_budget"],
            "max_unique_eligible_links_per_page",
        )

    def test_plural_transcript_path_uses_existing_candidate_evidence(self) -> None:
        candidate = "https://directory.example/transcripts/123-q1-2026/"
        result, _ = self.discover(
            f"<html><a href='{candidate}'>Earnings Call: Q1 2026</a></html>".encode()
        )

        self.assertEqual([item["url"] for item in result.candidate_proposals], [candidate])
        self.assertEqual(result.diagnostics["eligible_hyperlinks"], 1)

    def test_production_pull_workflow_negotiates_directory_and_fetches_candidate(self) -> None:
        candidate = STOCK_ANALYSIS_HINT + "999999-q2-2026/"
        irrelevant = "".join(
            f"<a href='/navigation/{index}'>Navigation {index}</a>"
            for index in range(35)
        )
        listing = (
            f"<!doctype html><html>{irrelevant}"
            f"<a href='{candidate}'>Earnings Call: Q2 2026</a></html>"
        ).encode()
        transcript = (
            b"<!doctype html><html><title>Amazon Q2 2026 Earnings Call Transcript</title>"
            b"<body>Amazon.com, Inc. quarterly earnings call transcript July 30, 2026. "
            b"Operator: Welcome. Chief Executive Officer: Prepared remarks.</body></html>"
        )
        requests = []

        def urlopen(request, timeout):
            self.assertEqual(timeout, 30.0)
            self.assertEqual(request.get_header("Accept"), TRANSCRIPT_ACCEPT)
            requests.append(request.full_url)
            if request.full_url == STOCK_ANALYSIS_HINT:
                return LiveHttpResponse(STOCK_ANALYSIS_HINT, listing)
            if request.full_url == candidate:
                return LiveHttpResponse(candidate, transcript)
            self.fail(f"unexpected production Pull Sources request: {request.full_url}")

        with tempfile.TemporaryDirectory() as temporary:
            state = Path(temporary)
            RepositoryDatabase.initialize(state)
            configured = state / "firm-config"
            configured.mkdir()
            value = json.loads(
                Path("docs/amazon.firm-config.example.json").read_text(encoding="utf-8")
            )
            value["sources"]["sec"] = None
            configured.joinpath("amazon.firm-config.json").write_text(
                json.dumps(value), encoding="utf-8"
            )
            prepare_firm_configuration(state)

            with patch(
                "rfi.acquisition.earnings_transcripts.urllib.request.urlopen", urlopen
            ):
                result = create_pull_workflow(state).run(PullRequest(("amazon",)))

        artifact = next(
            item for item in result.firms[0].artifacts
            if item.artifact_id == "earnings_transcript"
        )
        diagnostics = artifact.attempts[0].details["engine_diagnostics"][0]
        self.assertEqual(artifact.outcome, ArtifactOutcome.SUCCESS)
        self.assertEqual(diagnostics["configured_hint_status"], "used")
        self.assertEqual(diagnostics["raw_hyperlinks"], 36)
        self.assertEqual(diagnostics["eligible_hyperlinks"], 1)
        self.assertEqual(diagnostics["traversed_hyperlinks"], 1)
        self.assertEqual(diagnostics["candidate_urls"], 1)
        self.assertEqual(diagnostics["search_queries"], 0)
        self.assertEqual(requests, [STOCK_ANALYSIS_HINT, STOCK_ANALYSIS_HINT, candidate])

    def test_hint_first_acceptance_avoids_search_and_preserves_coverage_semantics(self) -> None:
        candidate = transcript_url(1)
        irrelevant = "".join(
            f"<a href='/navigation/{index}'>Navigation {index}</a>" for index in range(35)
        )
        listing = response(
            HINT,
            f"<html>{irrelevant}<a href='{candidate}'>Amazon Q1 2026 earnings call transcript"
            "</a></html>".encode(),
        )
        transcript = response(
            candidate,
            b"<!doctype html><html>Amazon.com, Inc. quarterly earnings call transcript "
            b"April 30, 2026. Operator: Welcome. Chief Executive Officer: Remarks.</html>",
        )
        search = RecordingSearch()
        transport = RecordingTransport({HINT: listing, candidate: transcript})
        adapter = EarningsTranscriptPullAdapter(
            DiscoveryPolicyCatalog({"standard": policy()}, "standard"),
            search, transport, lambda: "2026-07-30T12:00:00+00:00",
        )

        page = adapter.discover(source(), None)

        self.assertEqual(transport.requests[0], HINT)
        self.assertEqual(search.queries, [])
        self.assertEqual(page.diagnostics["search_queries"], 0)
        self.assertEqual(page.diagnostics["raw_hyperlinks"], 36)
        self.assertEqual(page.diagnostics["eligible_hyperlinks"], 1)
        self.assertEqual(page.diagnostics["traversed_hyperlinks"], 1)
        self.assertEqual(page.diagnostics["coverage"], "indeterminate")
        self.assertEqual(len(page.candidates), 1)

    def test_eligible_exhaustion_remains_indeterminate_after_ordinary_validation(self) -> None:
        first, second = transcript_url(1), transcript_url(2)
        listing = response(
            HINT,
            (f"<html><a href='{first}'>Q1 earnings call transcript</a>"
             f"<a href='{second}'>Q2 earnings call transcript</a></html>").encode(),
        )
        transcript = response(
            second,
            b"<!doctype html><html>Amazon.com, Inc. quarterly earnings call transcript "
            b"June 30, 2026. Operator: Welcome. Chief Executive Officer: Remarks.</html>",
        )
        adapter = EarningsTranscriptPullAdapter(
            DiscoveryPolicyCatalog(
                {"standard": policy(max_unique_eligible_links_per_page=1)}, "standard"
            ),
            RecordingSearch(), RecordingTransport({HINT: listing, second: transcript}),
            lambda: "2026-07-30T12:00:00+00:00",
        )

        page = adapter.discover(source(), None)

        self.assertEqual(page.diagnostics["coverage"], "indeterminate")
        self.assertTrue(page.diagnostics["bounds_exhausted"])
        self.assertEqual(
            page.diagnostics["exhausted_budget"],
            "max_unique_eligible_links_per_page",
        )
        self.assertEqual(page.diagnostics["traversed_hyperlinks"], 1)
        self.assertEqual(len(page.candidates), 1)


if __name__ == "__main__":
    unittest.main()
