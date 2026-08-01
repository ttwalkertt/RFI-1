"""Focused acceptance evidence for TASK-057 deterministic transcript graph traversal."""

from __future__ import annotations

import json
import unittest
from dataclasses import replace

from rfi.acquisition import EarningsTranscriptHttpResponse, SourceProfile
from rfi.acquisition.earnings_transcripts import normalize_transcript_url
from rfi.discovery import (
    BoundedTranscriptDiscovery,
    BudgetedTranscriptTransport,
    DiscoveryPolicy,
    DiscoveryPolicyCatalog,
    DiscoverySearchResponse,
    EarningsTranscriptPullAdapter,
)
from rfi.pull import ArtifactOutcome
from rfi.pull.workflow import PullWorkflow


def policy(**changes: int) -> DiscoveryPolicy:
    return replace(
        DiscoveryPolicy(2, 8, 20, 3, 30, 8, 2_000_000, 60, 40, 10), **changes
    )


def html(url: str, body: str, *, status: int = 200,
         redirects: tuple[str, ...] = ()) -> EarningsTranscriptHttpResponse:
    return EarningsTranscriptHttpResponse(
        url, status, "text/html", f"<html>{body}</html>".encode(), redirects
    )


class Search:
    endpoint = "https://search.example/results"

    def __init__(self, urls: tuple[str, ...] = ()) -> None:
        self.urls = urls
        self.calls: list[str] = []

    def search(self, query: str, limit: int) -> DiscoverySearchResponse:
        self.calls.append(query)
        return DiscoverySearchResponse(self.urls, 1)


class Transport:
    def __init__(self, responses: dict[str, EarningsTranscriptHttpResponse | Exception]) -> None:
        self.responses = responses
        self.requests: list[str] = []

    def get(self, url: str) -> EarningsTranscriptHttpResponse:
        self.requests.append(url)
        value = self.responses[url]
        if isinstance(value, Exception):
            raise value
        return value


def discover(
    hint: str, responses: dict[str, EarningsTranscriptHttpResponse | Exception],
    selected: DiscoveryPolicy | None = None,
):
    transport = Transport(responses)
    bounded = BudgetedTranscriptTransport(transport, selected or policy())
    result = BoundedTranscriptDiscovery(Search(), bounded, bounded.policy).discover((), (hint,))
    return result, transport


def profile(hint: str) -> SourceProfile:
    return SourceProfile(
        "source-a", "Firm A transcripts", True, "earnings_transcript",
        {"mode": "discovery", "discovery_hints": [hint],
         "discovery_class": "standard"},
        {"firm_id": "firm-a", "artifact_id": "earnings_transcript"},
    )


class UrlIdentityTests(unittest.TestCase):
    def test_conservative_identity_normalizes_case_ports_fragments_and_dot_segments(self) -> None:
        self.assertEqual(
            normalize_transcript_url("HTTPS://IR.Example.COM:443/a/../calls/./q1#speaker"),
            "https://ir.example.com/calls/q1",
        )
        self.assertNotEqual(
            normalize_transcript_url("https://ir.example.com/calls?q=1"),
            normalize_transcript_url("https://ir.example.com/calls?q=2"),
        )

    def test_self_fragment_and_normalized_duplicates_are_rejected_without_fetch(self) -> None:
        root = "https://IR.Example.com:443/transcripts/"
        candidate = "https://ir.example.com/q1-2026-earnings-call-transcript.html"
        body = (
            "<a href='#top'>Transcript archive</a>"
            f"<a href='{candidate}#one'>Q1 earnings call transcript</a>"
            f"<a href='{candidate}#two'>Q1 earnings call transcript duplicate</a>"
        )
        result, transport = discover(root, {root: html(root, body)})
        self.assertEqual(transport.requests, [root])
        self.assertEqual(len(result.candidate_proposals), 1)
        self.assertEqual(result.diagnostics["cycle_counts"]["self_reference"], 1)
        self.assertEqual(result.diagnostics["cycle_counts"]["duplicate_edge"], 1)
        self.assertEqual(result.diagnostics["candidate_admitted_count"], 1)

    def test_query_distinct_candidates_remain_distinct(self) -> None:
        root = "https://ir.example.com/transcripts/"
        base = "https://ir.example.com/earnings-call-transcript"
        body = "".join(
            f"<a href='{base}?period={period}'>Q{period} earnings call transcript</a>"
            for period in (1, 2)
        )
        result, _ = discover(root, {root: html(root, body)})
        self.assertEqual(len(result.candidate_proposals), 2)


class GraphCycleAndRankingTests(unittest.TestCase):
    def test_two_and_three_node_cycles_fetch_each_normalized_page_once(self) -> None:
        a = "https://ir.example.com/transcripts/a"
        b = "https://ir.example.com/transcripts/b"
        c = "https://ir.example.com/transcripts/c"
        responses = {
            a: html(a, f"<a href='{b}'>Transcript archive B</a>"),
            b: html(b, f"<a href='{c}'>Transcript archive C</a><a href='{a}'>Transcript A</a>"),
            c: html(c, f"<a href='{a}'>Transcript archive A</a>"),
        }
        result, transport = discover(a, responses)
        self.assertEqual(transport.requests, [a, b, c])
        self.assertEqual(result.diagnostics["visited_count"], 3)
        self.assertEqual(result.diagnostics["cycle_counts"]["ancestor_cycle"], 2)
        self.assertEqual(result.diagnostics["candidate_evaluated_count"] if
                         "candidate_evaluated_count" in result.diagnostics else 0, 0)

    def test_same_node_from_multiple_parents_is_fetched_once(self) -> None:
        root = "https://ir.example.com/transcripts/root"
        left = "https://ir.example.com/transcripts/left"
        right = "https://ir.example.com/transcripts/right"
        shared = "https://ir.example.com/transcripts/shared"
        responses = {
            root: html(root, f"<a href='{right}'>Transcript archive</a>"
                             f"<a href='{left}'>Transcript archive</a>"),
            left: html(left, f"<a href='{shared}'>Transcript archive</a>"),
            right: html(right, f"<a href='{shared}'>Transcript archive</a>"),
            shared: html(shared, ""),
        }
        result, transport = discover(root, responses)
        self.assertEqual(transport.requests.count(shared), 1)
        self.assertGreaterEqual(result.diagnostics["cycle_counts"]["duplicate_identity"], 1)

    def test_ranking_is_input_order_independent_and_relevant_link_beats_noise(self) -> None:
        root = "https://ir.example.com/transcripts/"
        generic = [f"https://ir.example.com/transcripts/archive-{index}" for index in range(12)]
        winner = "https://ir.example.com/q2-2026-earnings-call-transcript.html"
        anchors = [*(f"<a href='{url}'>Transcript archive</a>" for url in generic),
                   f"<a href='{winner}'>Q2 2026 earnings call transcript</a>"]
        first, _ = discover(root, {root: html(root, "".join(anchors))},
                            policy(max_links_per_page=1))
        second, _ = discover(root, {root: html(root, "".join(reversed(anchors)))},
                             policy(max_links_per_page=1))
        self.assertEqual(first.candidate_proposals, second.candidate_proposals)
        self.assertEqual(first.candidate_proposals[0]["url"], winner)
        self.assertEqual(first.diagnostics["top_ranked_candidates"],
                         second.diagnostics["top_ranked_candidates"])

    def test_candidate_ranking_is_global_across_parent_pages(self) -> None:
        root = "https://ir.example.com/transcripts/root"
        left = "https://ir.example.com/transcripts/a-left"
        right = "https://ir.example.com/transcripts/z-right"
        weak = "https://ir.example.com/earnings-call-transcript"
        strong = "https://ir.example.com/2026-04-30-earnings-call-transcript.html"
        result, _ = discover(root, {
            root: html(root, f"<a href='{left}'>Transcript archive</a>"
                             f"<a href='{right}'>Transcript archive</a>"),
            left: html(left, f"<a href='{weak}'>Earnings call transcript</a>"),
            right: html(right, f"<a href='{strong}'>Q1 2026 earnings call transcript</a>"),
        })
        self.assertEqual(
            [item["url"] for item in result.candidate_proposals], [strong, weak]
        )

    def test_redirect_cycle_and_redirect_budget_are_explicit(self) -> None:
        root = "https://ir.example.com/transcripts/"
        cycle, _ = discover(root, {
            root: html(root, "", redirects=("https://ir.example.com/other", root))
        })
        self.assertEqual(cycle.diagnostics["cycle_counts"]["redirect_cycle"], 1)
        limited, _ = discover(root, {
            root: html(root, "", redirects=("https://ir.example.com/one",
                                             "https://ir.example.com/two"))
        }, policy(max_redirects=1))
        self.assertTrue(limited.exhausted)
        self.assertEqual(limited.diagnostics["exhausted_budget"], "max_redirects")


class ClassificationAndBoundaryTests(unittest.TestCase):
    def adapter(self, hint: str, responses, selected: DiscoveryPolicy | None = None):
        return EarningsTranscriptPullAdapter(
            DiscoveryPolicyCatalog({"standard": selected or policy()}, "standard"),
            Search(), Transport(responses), lambda: "2026-08-01T00:00:00Z",
        ).discover(profile(hint), None)

    def test_no_eligible_timeout_and_http_failure_are_distinct(self) -> None:
        hint = "https://ir.example.com/transcripts/"
        no_links = self.adapter(hint, {hint: html(hint, "<a href='/legal'>Legal</a>")})
        self.assertEqual(no_links.diagnostics["primary_classification"], "no_eligible_links")
        self.assertIn("No eligible", no_links.diagnostics["operator_summary"])
        timed_out = self.adapter(hint, {hint: TimeoutError("timed out")})
        self.assertEqual(timed_out.diagnostics["primary_classification"], "hint_fetch_timeout")
        forbidden = self.adapter(hint, {hint: html(hint, "", status=403)})
        self.assertEqual(forbidden.diagnostics["primary_classification"], "hint_http_failure")
        self.assertIn("403", forbidden.diagnostics["operator_summary"])

    def test_candidate_evaluation_budget_remains_retriever_owned(self) -> None:
        hint = "https://ir.example.com/transcripts/"
        missing = "https://ir.example.com/2026-04-30-earnings-call-transcript.html"
        listing = html(hint, f"<a href='{missing}'>Q1 earnings call transcript</a>")
        unavailable = self.adapter(
            hint, {hint: listing, missing: html(missing, "", status=404)}
        )
        self.assertEqual(unavailable.diagnostics["primary_classification"],
                         "candidate_http_not_found")

        unsupported = EarningsTranscriptHttpResponse(missing, 200, "application/json", b"{}")
        invalid = self.adapter(hint, {hint: listing, missing: unsupported})
        self.assertEqual(invalid.diagnostics["primary_classification"],
                         "candidate_unsupported_content_type")

        second = "https://ir.example.com/2026-07-30-earnings-call-transcript.html"
        two = html(hint, f"<a href='{missing}'>Q1 earnings call transcript</a>"
                         f"<a href='{second}'>Q2 earnings call transcript</a>")
        valid = html(missing, "Firm A quarterly earnings call transcript April 30, 2026. "
                              "Operator. Chief Executive Officer. Prepared remarks.")
        bounded = self.adapter(
            hint, {hint: two, missing: valid}, policy(max_candidate_evaluations=1)
        )
        self.assertEqual(bounded.diagnostics["candidate_evaluated_count"], 1)
        self.assertEqual(bounded.diagnostics["exhausted_budget"],
                         "max_candidate_evaluations")
        self.assertIn("evaluating 1 ranked unique links", bounded.diagnostics["operator_summary"])

    def test_diagnostics_are_bounded_redacted_and_pull_summary_uses_primary_message(self) -> None:
        hint = "https://ir.example.com/transcripts/?token=secret"
        links = "".join(
            f"<a href='/legal/{index}?api_key=value-{index}'>Legal</a>" for index in range(30)
        )
        page = self.adapter(hint, {hint: html(hint, links)})
        samples = page.diagnostics["representative_rejections"]
        self.assertLessEqual(len(samples), 8)
        encoded = json.dumps(page.diagnostics)
        self.assertNotIn("secret", encoded)
        self.assertNotIn("value-", encoded)

        class Result:
            diagnostics = ({"operator_summary": page.diagnostics["operator_summary"]},)

        self.assertEqual(
            PullWorkflow._engine_diagnostic(Result(), ArtifactOutcome.INDETERMINATE),
            page.diagnostics["operator_summary"],
        )


if __name__ == "__main__":
    unittest.main()
