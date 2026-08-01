"""Focused regression evidence for TASK-053 traversal-budget semantics."""

from __future__ import annotations

import unittest
from dataclasses import replace

from rfi.acquisition import EarningsTranscriptHttpResponse, SourceProfile
from rfi.discovery import (
    BoundedTranscriptDiscovery,
    BudgetedTranscriptTransport,
    DiscoveryPolicy,
    DiscoveryPolicyCatalog,
    DiscoverySearchResponse,
    EarningsTranscriptPullAdapter,
    TranscriptDiscoveryResult,
)


HINT = "https://directory.example/transcripts/"


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
        self.assertEqual(result.diagnostics["exhausted_budget"], "max_links_per_page")
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
        result, transport = self.discover(body, selected=policy(max_links_per_page=1))

        self.assertEqual([item["url"] for item in result.candidate_proposals], [candidate])
        self.assertEqual(transport.requests, [HINT])
        self.assertEqual(result.diagnostics["traversed_hyperlinks"], 1)
        self.assertEqual(result.diagnostics["exhausted_budget"], "max_links_per_page")

    def test_plural_transcript_path_uses_existing_candidate_evidence(self) -> None:
        candidate = "https://directory.example/transcripts/123-q1-2026/"
        result, _ = self.discover(
            f"<html><a href='{candidate}'>Earnings Call: Q1 2026</a></html>".encode()
        )

        self.assertEqual([item["url"] for item in result.candidate_proposals], [candidate])
        self.assertEqual(result.diagnostics["eligible_hyperlinks"], 1)

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
            first,
            b"<!doctype html><html>Amazon.com, Inc. quarterly earnings call transcript "
            b"April 30, 2026. Operator: Welcome. Chief Executive Officer: Remarks.</html>",
        )
        adapter = EarningsTranscriptPullAdapter(
            DiscoveryPolicyCatalog(
                {"standard": policy(max_links_per_page=1)}, "standard"
            ),
            RecordingSearch(), RecordingTransport({HINT: listing, first: transcript}),
            lambda: "2026-07-30T12:00:00+00:00",
        )

        page = adapter.discover(source(), None)

        self.assertEqual(page.diagnostics["coverage"], "indeterminate")
        self.assertTrue(page.diagnostics["bounds_exhausted"])
        self.assertEqual(page.diagnostics["exhausted_budget"], "max_links_per_page")
        self.assertEqual(page.diagnostics["traversed_hyperlinks"], 1)
        self.assertEqual(len(page.candidates), 1)


if __name__ == "__main__":
    unittest.main()
