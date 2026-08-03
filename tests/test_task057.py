"""Focused acceptance evidence for TASK-057 deterministic transcript graph traversal."""

from __future__ import annotations

import json
import tempfile
import unittest
from dataclasses import replace
from datetime import date
from pathlib import Path
from unittest.mock import patch

from rfi.acquisition import (
    AcquisitionEngine, AcquisitionRepository, AdapterFailure, AdapterRegistry,
    EarningsTranscriptHttpResponse, IntervalAcquisitionFailure,
    IntervalAcquisitionRequest, RunStatus, SourceProfile,
)
from rfi.acquisition.earnings_transcripts import (
    CandidateFailureCode, EarningsCallTranscriptAcquisition, ReportingPeriod,
    normalize_transcript_url,
)
from rfi.discovery import (
    BoundedTranscriptDiscovery,
    BudgetedTranscriptTransport,
    DiscoveryPolicy,
    DiscoveryPolicyCatalog,
    DiscoverySearchResponse,
    EarningsTranscriptPullAdapter,
)
from rfi.firms import FirmRepository
from rfi.firms.contracts import FirmDraft, FirmStatus
from rfi.pull import ArtifactOutcome
from rfi.pull.workflow import PullWorkflow
from scripts.task057_reproduction import reproduction_cases


def policy(**changes: int) -> DiscoveryPolicy:
    return replace(
        DiscoveryPolicy(2, 8, 1000, 3, 30, 8, 2_000_000, 60, 40, 10), **changes
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
        if url not in self.responses:
            raise OSError(f"fixture transport has no response for {url}")
        value = self.responses[url]
        if isinstance(value, Exception):
            raise value
        return value


def discover(
    hint: str, responses: dict[str, EarningsTranscriptHttpResponse | Exception],
    selected: DiscoveryPolicy | None = None,
    checkpoint: ReportingPeriod | None = None,
    expected: ReportingPeriod | None = None,
):
    transport = Transport(responses)
    bounded = BudgetedTranscriptTransport(transport, selected or policy())
    result = BoundedTranscriptDiscovery(Search(), bounded, bounded.policy).discover(
        (), (hint,), (), checkpoint, expected
    )
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
    def test_multiple_retained_anchors_share_one_total_order_queue_key(self) -> None:
        first = "https://ir.example.com/current-earnings-call-transcript.html"
        second = "https://ir.example.com/prior-earnings-call-transcript.html"
        archive = "https://ir.example.com/transcripts/archive"
        candidate = "https://ir.example.com/q4-2025-earnings-call-transcript.html"
        anchors = (
            {"requested_url": first, "resolved_url": first,
             "normalized_url": first},
            {"requested_url": second, "resolved_url": second,
             "normalized_url": second},
        )
        transcript_text = (
            "Firm A quarterly earnings call transcript. Operator. "
            "Chief Executive Officer. Prepared remarks."
        )
        responses = {
            first: html(
                first, f"{transcript_text} 2026-04-30. "
                f"<a href='{archive}'>Transcript archive</a>",
            ),
            second: html(second, f"{transcript_text} 2026-01-30."),
            archive: html(
                archive,
                f"<a href='{candidate}'>Q4 2025 earnings call transcript</a>",
            ),
            candidate: html(candidate, f"{transcript_text} 2025-10-30."),
        }

        def run():
            transport = Transport(responses)
            bounded = BudgetedTranscriptTransport(transport, policy())
            result = BoundedTranscriptDiscovery(
                Search(), bounded, bounded.policy
            ).discover((), (), anchors)
            return result, transport.requests

        first_result, first_requests = run()
        second_result, second_requests = run()
        self.assertEqual(first_requests, [first, second, archive])
        self.assertEqual(first_requests, second_requests)
        self.assertEqual(
            first_result.candidate_proposals, second_result.candidate_proposals
        )
        self.assertEqual(first_result.diagnostics["stage_sequence"], ["retained_anchor"])
        self.assertEqual(first_result.diagnostics["visited_count"], 3)
        self.assertEqual(first_result.diagnostics["queue_admitted_count"], 4)
        self.assertEqual(len(first_result.candidate_proposals), 3)

        configured = profile("Firm A")
        with tempfile.TemporaryDirectory() as directory:
            repository = AcquisitionRepository(Path(directory) / "acquisition")
            repository.register_source(configured)
            transport = Transport(responses)
            adapter = EarningsTranscriptPullAdapter(
                DiscoveryPolicyCatalog({"standard": policy()}, "standard"), Search(),
                transport, lambda: "2026-08-01T00:00:00Z", repository=repository,
            )
            with patch.object(repository, "discovery_anchors", return_value=anchors):
                engine_result = AcquisitionEngine(
                    repository, AdapterRegistry((adapter,)),
                    lambda: "2026-08-01T00:00:00Z",
                ).run_source(configured.source_id, "multi-anchor-queue")
        self.assertEqual(
            engine_result.status, RunStatus.COMPLETE,
            json.dumps(engine_result.to_dict(), indent=2),
        )
        self.assertNotIn("malformed_adapter", json.dumps(engine_result.to_dict()))

    def test_emergency_ceiling_counts_only_unique_eligible_links(self) -> None:
        root = "https://ir.example.com/transcripts/"
        candidates = [
            f"https://ir.example.com/{2000 + index // 4}-q{index % 4 + 1}-"
            "earnings-call-transcript.html"
            for index in range(76)
        ]
        body = "".join(
            f"<a href='{url}'>Q{index % 4 + 1} {2000 + index // 4} earnings call transcript</a>"
            for index, url in enumerate(candidates)
        )
        result, _ = discover(root, {root: html(root, body)})
        self.assertFalse(result.exhausted)
        self.assertEqual(len(result.candidate_proposals), 76)

        duplicate_body = (
            "<a href='#self'>Transcript archive</a>"
            f"<a href='{candidates[0]}'>Q1 2000 earnings call transcript</a>"
            f"<a href='{candidates[0]}#again'>Q1 2000 earnings call transcript</a>"
            f"<a href='{candidates[1]}'>Q2 2000 earnings call transcript</a>"
        )
        duplicates, _ = discover(
            root, {root: html(root, duplicate_body)},
            policy(max_unique_eligible_links_per_page=2),
        )
        self.assertFalse(duplicates.exhausted)
        self.assertEqual(len(duplicates.candidate_proposals), 2)
        self.assertEqual(duplicates.diagnostics["cycle_counts"], {
            "duplicate_edge": 1, "self_reference": 1,
        })

    def test_pathological_page_triggers_renamed_emergency_ceiling(self) -> None:
        root = "https://ir.example.com/transcripts/"
        body = "".join(
            f"<a href='/calls/{index}-q1-2025-earnings-call-transcript.html'>"
            f"Q1 2025 earnings call transcript {index}</a>"
            for index in range(1001)
        )
        result, _ = discover(root, {root: html(root, body)})
        self.assertTrue(result.exhausted)
        self.assertEqual(len(result.candidate_proposals), 1000)
        self.assertEqual(
            result.diagnostics["exhausted_budget"],
            "max_unique_eligible_links_per_page",
        )

    def test_checkpoint_aware_period_ranking_is_total_and_input_stable(self) -> None:
        root = "https://ir.example.com/transcripts/"
        def link(path: str, label: str) -> tuple[str, str]:
            return f"https://ir.example.com/{path}-earnings-call-transcript", label

        links = (
            link("90-unknown", "Earnings call transcript"),
            link("80-q1-2025", "Q1 2025 earnings call transcript"),
            link("70-q2-2025", "Q2 2025 earnings call transcript"),
            link("60-q3-2025", "Q3 2025 earnings call transcript"),
            link("50-q4-2025", "Q4 2025 earnings call transcript"),
            link("40-q4-2024", "Q4 2024 earnings call transcript"),
            link("30-q3-2024", "Q3 2024 earnings call transcript"),
            link("a-q1-2024", "Q1 2024 earnings call transcript"),
            link("b-q1-2024", "Q1 2024 earnings call transcript"),
        )
        render = lambda values: "".join(
            f"<a href='{url}'>{label}</a>" for url, label in values
        )
        context = (ReportingPeriod(2025, 2), ReportingPeriod(2025, 3))
        first, _ = discover(
            root, {root: html(root, render(links))},
            checkpoint=context[0], expected=context[1],
        )
        second, _ = discover(
            root, {root: html(root, render(reversed(links)))},
            checkpoint=context[0], expected=context[1],
        )
        ordered = [item["url"] for item in first.candidate_proposals]
        self.assertEqual(first.candidate_proposals, second.candidate_proposals)
        self.assertEqual(ordered[:7], [
            links[3][0], links[4][0], links[2][0], links[1][0],
            links[5][0], links[6][0], links[7][0],
        ])
        self.assertEqual(ordered[7:], [links[8][0], links[0][0]])

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
                            policy(max_unique_eligible_links_per_page=1))
        second, _ = discover(root, {root: html(root, "".join(reversed(anchors)))},
                             policy(max_unique_eligible_links_per_page=1))
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
        transport = Transport({hint: listing, missing: html(missing, "", status=404)})
        adapter = EarningsTranscriptPullAdapter(
            DiscoveryPolicyCatalog({"standard": policy()}, "standard"), Search(),
            transport, lambda: "2026-08-01T00:00:00Z",
        )
        unavailable = adapter.discover(profile(hint), None)
        self.assertEqual(transport.requests, [hint])
        with self.assertRaises(AdapterFailure) as raised:
            adapter.retrieve(profile(hint), unavailable.candidates[0])
        self.assertEqual(raised.exception.code, "candidate_http_not_found")

        unsupported = EarningsTranscriptHttpResponse(missing, 200, "application/json", b"{}")
        transport = Transport({hint: listing, missing: unsupported})
        adapter = EarningsTranscriptPullAdapter(
            DiscoveryPolicyCatalog({"standard": policy()}, "standard"), Search(),
            transport, lambda: "2026-08-01T00:00:00Z",
        )
        invalid = adapter.discover(profile(hint), None)
        with self.assertRaises(AdapterFailure) as raised:
            adapter.retrieve(profile(hint), invalid.candidates[0])
        self.assertEqual(raised.exception.code, "candidate_unsupported_content_type")

        second = "https://ir.example.com/2026-07-30-earnings-call-transcript.html"
        two = html(hint, f"<a href='{missing}'>Q1 earnings call transcript</a>"
                         f"<a href='{second}'>Q2 earnings call transcript</a>")
        valid = html(missing, "Firm A quarterly earnings call transcript April 30, 2026. "
                              "Operator. Chief Executive Officer. Prepared remarks.")
        bounded = self.adapter(
            hint, {hint: two, missing: valid}, policy(max_candidate_evaluations=1)
        )
        self.assertEqual(bounded.diagnostics["candidate_selected_count"], 1)
        self.assertEqual(bounded.diagnostics["candidate_evaluated_count"], 0)
        self.assertEqual(bounded.diagnostics["exhausted_budget"],
                         "max_candidate_evaluations")
        self.assertIn("selecting 1 ranked unique links", bounded.diagnostics["operator_summary"])

    def test_candidate_failure_classification_is_independent_of_message_text(self) -> None:
        details = {
            "candidate_failure_code": CandidateFailureCode.HTTP_NOT_FOUND.value,
            "url": "https://ir.example.com/transcript",
            "http_status": 404,
        }
        failures = tuple(
            IntervalAcquisitionFailure(
                "candidate_unavailable", message, True, details=details
            )
            for message in (
                "HTTP Error 404: HTTP 404",
                "the presentation wording can change without changing the code",
            )
        )
        outcomes = [
            EarningsTranscriptPullAdapter._classify_outcome({}, (failure,))
            for failure in failures
        ]
        codes = [
            EarningsTranscriptPullAdapter._candidate_failure_code(failure)
            for failure in failures
        ]
        self.assertEqual(outcomes[0], outcomes[1])
        self.assertEqual(codes[0], codes[1])
        self.assertEqual(outcomes[0][0], CandidateFailureCode.HTTP_NOT_FOUND.value)

    def test_retriever_emits_all_stable_candidate_failure_codes(self) -> None:
        hint = "https://ir.example.com/transcripts/"
        candidate = "https://ir.example.com/2026-04-30-earnings-call-transcript.html"
        listing = html(hint, f"<a href='{candidate}'>Q1 earnings call transcript</a>")
        cases = (
            (html(candidate, "", status=403), CandidateFailureCode.ACCESS_DENIED),
            (TimeoutError("new timeout wording"), CandidateFailureCode.FETCH_TIMEOUT),
            (OSError("new retrieval wording"), CandidateFailureCode.RETRIEVAL_FAILURE),
            (
                EarningsTranscriptHttpResponse(candidate, 200, "text/html", b""),
                CandidateFailureCode.EMPTY_CONTENT,
            ),
            (
                html(candidate, "This page requires JavaScript."),
                CandidateFailureCode.JAVASCRIPT_REQUIRED,
            ),
            (
                html(candidate, "Quarterly earnings update without speaker evidence."),
                CandidateFailureCode.VALIDATION_MISMATCH,
            ),
        )
        for response, expected in cases:
            with self.subTest(expected=expected.value):
                transport = Transport({hint: listing, candidate: response})
                adapter = EarningsTranscriptPullAdapter(
                    DiscoveryPolicyCatalog({"standard": policy()}, "standard"),
                    Search(), transport, lambda: "2026-08-01T00:00:00Z",
                )
                page = adapter.discover(profile(hint), None)
                with self.assertRaises(AdapterFailure) as raised:
                    adapter.retrieve(profile(hint), page.candidates[0])
                self.assertEqual(raised.exception.code, expected.value)

    def test_typed_graph_state_metrics_match_actual_transitions(self) -> None:
        root = "https://ir.example.com/transcripts/root"
        archive = "https://ir.example.com/transcripts/archive"
        candidate = "https://ir.example.com/q1-2026-earnings-call-transcript.html"
        result, transport = discover(root, {
            root: html(
                root,
                f"<a href='{archive}'>Transcript archive</a>"
                f"<a href='{candidate}'>Q1 earnings call transcript</a>"
                f"<a href='{candidate}#repeat'>Duplicate transcript</a>"
                "<a href='/legal'>Legal</a>",
            ),
            archive: html(archive, f"<a href='{root}'>Transcript archive root</a>"),
        })
        diagnostics = result.diagnostics
        self.assertEqual(diagnostics["raw_hyperlinks"], 5)
        self.assertEqual(diagnostics["normalized_unique_hyperlinks"], 4)
        self.assertEqual(diagnostics["queue_admitted_count"], 3)
        self.assertEqual(diagnostics["visited_count"], len(transport.requests))
        self.assertEqual(diagnostics["candidate_admitted_count"],
                         len(result.candidate_proposals))
        self.assertEqual(sum(diagnostics["rejection_counts"].values()), 3)
        self.assertEqual(sum(diagnostics["cycle_counts"].values()), 2)

    def test_amazon_style_current_period_is_evaluated_before_numeric_history(self) -> None:
        hint = "https://ir.example.com/transcripts/"
        historical = []
        responses: dict[str, EarningsTranscriptHttpResponse | Exception] = {}
        for index in range(75):
            year = 2007 + index // 4
            quarter = index % 4 + 1
            month = quarter * 3
            url = (
                f"https://ir.example.com/{index:06d}/"
                "earnings-call-transcript.html"
            )
            label = f"Q{quarter} {year} earnings call transcript {year}-{month:02d}-01"
            historical.append((url, label))
            responses[url] = html(
                url,
                f"Firm A quarterly earnings call transcript {year}-{month:02d}-01. "
                "Operator. Chief Executive Officer. Prepared remarks.",
            )
        current = (
            "https://ir.example.com/999999/earnings-call-transcript.html",
            "Q2 2026 earnings call transcript 2026-04-30",
        )
        responses[current[0]] = html(
            current[0],
            "Firm A quarterly earnings call transcript 2026-04-30. Operator. "
            "Chief Executive Officer. Prepared remarks.",
        )
        links = "".join(
            f"<a href='{url}'>{label}</a>" for url, label in (*historical, current)
        )
        responses[hint] = html(hint, links)
        transport = Transport(responses)
        adapter = EarningsTranscriptPullAdapter(
            DiscoveryPolicyCatalog({"standard": policy(max_pages=75)}, "standard"),
            Search(), transport, lambda: "2026-08-01T00:00:00Z",
        )
        page = adapter.discover(profile(hint), None)
        self.assertEqual(transport.requests, [hint])
        self.assertEqual(page.diagnostics["expected_reporting_period"], "2026-Q2")
        self.assertEqual(page.diagnostics["candidate_selected_count"], 40)
        self.assertEqual(page.diagnostics["candidate_evaluated_count"], 0)
        self.assertEqual(len(page.candidates), 40)
        self.assertEqual(page.candidates[0].position, ReportingPeriod(2026, 2).ordinal)
        adapter.retrieve(profile(hint), page.candidates[0])
        self.assertEqual(transport.requests[1], current[0])

    def test_acquisition_checkpoint_orders_and_filters_reporting_periods(self) -> None:
        hint = "https://ir.example.com/transcripts/"
        checkpoint = "https://ir.example.com/q1-2026-earnings-call-transcript.html"
        expected = "https://ir.example.com/q2-2026-earnings-call-transcript.html"
        listing = html(
            hint,
            f"<a href='{checkpoint}'>Q1 2026 earnings call transcript 2026-03-31</a>"
            f"<a href='{expected}'>Q2 2026 earnings call transcript 2026-06-30</a>",
        )
        responses = {
            hint: listing,
            checkpoint: html(
                checkpoint,
                "Firm A quarterly earnings call transcript 2026-03-31. Operator. "
                "Chief Executive Officer. Prepared remarks.",
            ),
            expected: html(
                expected,
                "Firm A quarterly earnings call transcript 2026-06-30. Operator. "
                "Chief Executive Officer. Prepared remarks.",
            ),
        }

        class Repository:
            def discovery_anchors(self, *_args):
                return ()

            def checkpoints(self):
                return {"sources": {"source-a": {"attempt_id": "attempt-prior"}}}

            def history(self):
                return [{
                    "attempt_id": "attempt-prior",
                    "candidate": {"provenance": {"metadata": {
                        "link_label": "Q1 2026 earnings call transcript",
                        "resolved_url": checkpoint,
                    }}},
                }]

        transport = Transport(responses)
        adapter = EarningsTranscriptPullAdapter(
            DiscoveryPolicyCatalog({"standard": policy()}, "standard"),
            Search(), transport, lambda: "2026-08-01T00:00:00Z",
            repository=Repository(),
        )
        page = adapter.discover(profile(hint), None)
        self.assertEqual(transport.requests, [hint])
        self.assertEqual(page.diagnostics["reporting_period_basis"],
                         "acquisition_checkpoint")
        self.assertEqual(page.diagnostics["candidate_selected_count"], 2)
        self.assertEqual(len(page.candidates), 2)
        self.assertEqual(page.candidates[0].position, ReportingPeriod(2026, 2).ordinal)
        adapter.retrieve(profile(hint), page.candidates[0])
        self.assertEqual(transport.requests, [hint, expected])

    def test_historical_only_and_emergency_ceiling_outcomes_are_truthful(self) -> None:
        historical = {
            "candidate_evaluated_count": 3,
            "candidate_disposition_counts": {"older_than_checkpoint": 3},
        }
        classification, summary = EarningsTranscriptPullAdapter._classify_outcome(
            historical, ()
        )
        self.assertEqual(classification, "historical_candidates_only")
        self.assertIn("historical", summary)
        self.assertNotIn("Every runnable retrieval candidate failed", summary)

        ceiling, ceiling_summary = EarningsTranscriptPullAdapter._classify_outcome({
            "bounds_exhausted": True,
            "exhausted_budget": "max_unique_eligible_links_per_page",
            "candidate_evaluated_count": 40,
        }, ())
        candidate, candidate_summary = EarningsTranscriptPullAdapter._classify_outcome({
            "bounds_exhausted": True,
            "exhausted_budget": "max_candidate_evaluations",
            "candidate_evaluated_count": 40,
        }, ())
        self.assertEqual(ceiling, "discovery_emergency_ceiling_exhausted")
        self.assertEqual(candidate, "discovery_budget_exhausted")
        self.assertIn("emergency ceiling", ceiling_summary)
        self.assertIn("candidate-evaluation", candidate_summary)

        hint = "https://ir.example.com/transcripts/"
        old = "https://ir.example.com/q4-2025-earnings-call-transcript.html"
        page = self.adapter(hint, {
            hint: html(
                hint,
                f"<a href='{old}'>Q4 2025 earnings call transcript 2025-12-31</a>",
            ),
            old: html(
                old,
                "Firm A quarterly earnings call transcript 2025-12-31. Operator. "
                "Chief Executive Officer. Prepared remarks.",
            ),
        })
        self.assertEqual(len(page.candidates), 1)
        self.assertEqual(page.diagnostics["primary_classification"],
                         "candidate_proposals_ready")

        current = "https://ir.example.com/q2-2026-earnings-call-transcript.html"
        fallback_responses = {
            hint: html(
                hint,
                f"<a href='{old}'>Q4 2025 earnings call transcript 2025-12-31</a>"
                f"<a href='{current}'>Q2 2026 earnings call transcript 2026-06-30</a>",
            ),
            old: html(
                old,
                "Firm A quarterly earnings call transcript 2025-12-31. Operator. "
                "Chief Executive Officer. Prepared remarks.",
            ),
            current: html(current, "", status=404),
        }
        transport = Transport(fallback_responses)
        adapter = EarningsTranscriptPullAdapter(
            DiscoveryPolicyCatalog({"standard": policy()}, "standard"), Search(),
            transport, lambda: "2026-08-01T00:00:00Z",
        )
        failed_current = adapter.discover(profile(hint), None)
        self.assertEqual(len(failed_current.candidates), 2)
        with self.assertRaises(AdapterFailure) as raised:
            adapter.retrieve(profile(hint), failed_current.candidates[0])
        self.assertEqual(raised.exception.code, "candidate_http_not_found")
        fallback = adapter.retrieve(profile(hint), failed_current.candidates[1])
        self.assertIn(b"2025-12-31", fallback.content)

    def test_all_reproduction_cases_retain_semantic_outcomes(self) -> None:
        cases = reproduction_cases()
        expected = {
            "many_raw_zero_eligible": "no_eligible_links",
            "configured_hint_timeout": "hint_fetch_timeout",
            "configured_hint_http_failure": "hint_http_failure",
            "discovered_candidate_unavailable": "candidate_proposals_ready",
            "cyclic_navigation_graph": "coverage_indeterminate",
            "relevant_after_generic_links": "candidate_proposals_ready",
            "named_budget_exhausted": "discovery_budget_exhausted",
            "indeterminate_without_exhaustion": "coverage_indeterminate",
            "amazon_historical_links_current_period_late_numeric_id": (
                "discovery_budget_exhausted"
            ),
        }
        self.assertEqual(
            {name: item["primary_classification"] for name, item in cases.items()},
            expected,
        )
        self.assertEqual(
            json.dumps(cases, sort_keys=True),
            json.dumps(reproduction_cases(), sort_keys=True),
        )
        self.assertEqual(
            cases["discovered_candidate_unavailable"]["retrieval_outcomes"],
            ["candidate_http_not_found"],
        )
        self.assertEqual(
            cases["relevant_after_generic_links"]["retrieval_outcomes"],
            ["validated"],
        )

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


class CorrectiveRobustnessTests(unittest.TestCase):
    def test_hint_timeout_with_downstream_success_is_success_with_warnings(self) -> None:
        timed_out_hint = "https://ir-timeout.example.com/transcripts/"
        retained = "https://ir.example.com/2026-04-30-earnings-call-transcript.html"
        configured = SourceProfile(
            "source-a", "Firm A transcripts", True, "earnings_transcript",
            {"mode": "discovery", "discovery_hints": [timed_out_hint, retained],
             "discovery_class": "standard"},
            {"firm_id": "firm-a", "artifact_id": "earnings_transcript"},
        )
        transport = Transport({
            timed_out_hint: TimeoutError("configured hint timed out"),
            retained: html(
                retained,
                "Firm A quarterly earnings call transcript April 30, 2026. "
                "Operator. Chief Executive Officer. Prepared remarks.",
            ),
        })
        with tempfile.TemporaryDirectory() as directory:
            repository = AcquisitionRepository(Path(directory) / "acquisition")
            repository.register_source(configured)
            adapter = EarningsTranscriptPullAdapter(
                DiscoveryPolicyCatalog({"standard": policy()}, "standard"), Search(),
                transport, lambda: "2026-08-01T00:00:00Z", repository=repository,
            )
            result = AcquisitionEngine(
                repository, AdapterRegistry((adapter,)),
                lambda: "2026-08-01T00:00:00Z",
            ).run_source(configured.source_id, "hint-warning")

        self.assertEqual(result.status, RunStatus.COMPLETE)
        self.assertEqual(result.durable_acquisitions, 1)
        self.assertEqual(result.failures, 0)
        self.assertEqual(PullWorkflow._engine_outcome(result),
                         ArtifactOutcome.SUCCESS_WITH_WARNINGS)
        self.assertIn("hint_fetch_timeout", json.dumps(result.to_dict()))
        self.assertNotIn(
            "hint timed out",
            PullWorkflow._engine_diagnostic(
                result, ArtifactOutcome.SUCCESS_WITH_WARNINGS
            ),
        )

    def test_first_success_advances_checkpoint_without_later_candidate_failure(self) -> None:
        timed_out_hint = "https://ir-timeout.example.com/transcripts/"
        listing = "https://ir.example.com/transcripts/"
        retained = "https://ir.example.com/2026-04-30-earnings-call-transcript.html"
        failed = "https://ir.example.com/2026-07-30-earnings-call-transcript.html"
        configured = SourceProfile(
            "source-a", "Firm A transcripts", True, "earnings_transcript",
            {"mode": "discovery", "discovery_hints": [timed_out_hint, listing],
             "discovery_class": "standard"},
            {"firm_id": "firm-a", "artifact_id": "earnings_transcript",
             "retrieval_adapter_id": "earnings-call-transcript",
             "source_profile_revision_id": "profile-r1"},
        )
        transport = Transport({
            timed_out_hint: TimeoutError("configured hint timed out"),
            listing: html(
                listing,
                f"<a href='{retained}'>Q2 2026 earnings call transcript</a>"
                f"<a href='{failed}'>Q3 2026 earnings call transcript</a>",
            ),
            retained: html(
                retained,
                "Firm A quarterly earnings call transcript April 30, 2026. "
                "Operator. Chief Executive Officer. Prepared remarks.",
            ),
            failed: TimeoutError("candidate timed out"),
        })
        with tempfile.TemporaryDirectory() as directory:
            firms = FirmRepository.initialize(Path(directory) / "firms")
            firms.create(FirmDraft(
                "firm-a", "Firm A", "2026-01-01", status=FirmStatus.ACTIVE
            ))
            repository = AcquisitionRepository(Path(directory) / "acquisition")
            repository.register_source(configured)
            adapter = EarningsTranscriptPullAdapter(
                DiscoveryPolicyCatalog({"standard": policy()}, "standard"), Search(),
                transport, lambda: "2026-08-01T00:00:00Z", repository=repository,
            )
            result = AcquisitionEngine(
                repository, AdapterRegistry((adapter,)),
                lambda: "2026-08-01T00:00:00Z",
            ).run_source(configured.source_id, "mixed-success")
            anchors = repository.discovery_anchors(
                "firm-a", configured.source_id, "earnings-call-transcript"
            )

        self.assertEqual(result.status, RunStatus.COMPLETE)
        self.assertEqual(result.durable_acquisitions, 1)
        self.assertEqual(result.failures, 0)
        self.assertEqual(
            result.checkpoint_after.position, ReportingPeriod.parse("2026-Q2").ordinal
        )
        self.assertEqual(PullWorkflow._engine_outcome(result),
                         ArtifactOutcome.SUCCESS_WITH_WARNINGS)
        summary = PullWorkflow._engine_diagnostic(
            result, ArtifactOutcome.SUCCESS_WITH_WARNINGS
        )
        self.assertIn("Retrieved and ingested 1 artifact with warnings", summary)
        self.assertNotIn("hint timed out", summary)
        evidence = json.dumps(result.to_dict())
        self.assertIn("hint_fetch_timeout", evidence)
        self.assertNotIn("candidate_fetch_timeout", evidence)
        self.assertNotIn(failed, transport.requests)
        self.assertEqual(len(anchors), 1)
        self.assertEqual(anchors[0]["requested_url"], retained)

    def test_all_candidates_failed_remains_retrieval_failure(self) -> None:
        listing = "https://ir.example.com/transcripts/"
        failed = "https://ir.example.com/2026-04-30-earnings-call-transcript.html"
        configured = profile(listing)
        transport = Transport({
            listing: html(
                listing,
                f"<a href='{failed}'>Q2 2026 earnings call transcript</a>",
            ),
            failed: TimeoutError("candidate timed out"),
        })
        with tempfile.TemporaryDirectory() as directory:
            repository = AcquisitionRepository(Path(directory) / "acquisition")
            repository.register_source(configured)
            adapter = EarningsTranscriptPullAdapter(
                DiscoveryPolicyCatalog({"standard": policy()}, "standard"), Search(),
                transport, lambda: "2026-08-01T00:00:00Z", repository=repository,
            )
            result = AcquisitionEngine(
                repository, AdapterRegistry((adapter,)),
                lambda: "2026-08-01T00:00:00Z",
            ).run_source(configured.source_id, "all-failed")

        self.assertEqual(result.durable_acquisitions, 0)
        self.assertEqual(result.failures, 1)
        self.assertIsNone(result.checkpoint_after)
        self.assertEqual(PullWorkflow._engine_outcome(result),
                         ArtifactOutcome.RETRIEVAL_FAILURE)
        self.assertIn(
            "retrieval timed out",
            PullWorkflow._engine_diagnostic(
                result, ArtifactOutcome.RETRIEVAL_FAILURE
            ),
        )

    def test_checkpoint_no_change_summary_is_unchanged(self) -> None:
        class Result:
            failures = 0
            status = RunStatus.COMPLETE
            durable_acquisitions = 0
            duplicates = 0
            unchanged = 0
            diagnostics = ()
            checkpoint_before = object()
            outcomes = (type("Outcome", (), {"outcome": "checkpoint_filtered"})(),)

        result = Result()
        self.assertEqual(PullWorkflow._engine_outcome(result), ArtifactOutcome.NO_CHANGE)
        self.assertEqual(
            PullWorkflow._engine_diagnostic(result, ArtifactOutcome.NO_CHANGE),
            "Source checkpoint indicates no new artifact.",
        )

    def test_pdf_proposal_admission_and_successful_engine_acquisition(self) -> None:
        listing = "https://ir.example.com/transcripts/"
        url = "https://ir.example.com/2026-04-30-earnings-call-transcript.pdf"
        response = EarningsTranscriptHttpResponse(
            url, 200, "application/pdf", b"%PDF-1.7\nvalidated transcript bytes"
        )
        transport = Transport({
            listing: html(
                listing, f"<a href='{url}'>Q2 2026 earnings call transcript</a>"
            ),
            url: response,
        })
        adapter = EarningsTranscriptPullAdapter(
            DiscoveryPolicyCatalog({"standard": policy()}, "standard"), Search(),
            transport, lambda: "2026-08-01T00:00:00Z",
        )
        page = adapter.discover(profile(listing), None)
        self.assertEqual(len(page.candidates), 1)
        self.assertEqual(page.diagnostics["candidate_admitted_count"], 1)
        self.assertEqual(page.diagnostics["candidate_evaluated_count"], 0)
        self.assertEqual(transport.requests, [listing])
        result = adapter.retrieve(profile(listing), page.candidates[0])
        self.assertEqual(result.media_type, "application/pdf")
        self.assertEqual(transport.requests, [listing, url])

        engine_transport = Transport({
            listing: html(
                listing, f"<a href='{url}'>Q2 2026 earnings call transcript</a>"
            ),
            url: response,
        })
        engine_adapter = EarningsTranscriptPullAdapter(
            DiscoveryPolicyCatalog({"standard": policy()}, "standard"), Search(),
            engine_transport, lambda: "2026-08-01T00:00:00Z",
        )
        configured = profile(listing)
        with tempfile.TemporaryDirectory() as directory:
            repository = AcquisitionRepository(Path(directory) / "acquisition")
            repository.register_source(configured)
            engine_result = AcquisitionEngine(
                repository, AdapterRegistry((engine_adapter,)),
                lambda: "2026-08-01T00:00:00Z",
            ).run_source(configured.source_id, "pdf-success")
        self.assertEqual(engine_result.status, RunStatus.COMPLETE)
        self.assertEqual(engine_result.durable_acquisitions, 1)
        self.assertEqual(len(engine_result.outcomes), 1)
        self.assertEqual(engine_transport.requests, [listing, url])

    def test_failed_pdf_retrieval_is_structured_and_no_exception_escapes(self) -> None:
        listing = "https://ir.example.com/transcripts/"
        url = "https://ir.example.com/2026-04-30-earnings-call-transcript.pdf"
        configured = profile(listing)
        transport = Transport({
            listing: html(
                listing, f"<a href='{url}'>Q2 2026 earnings call transcript</a>"
            ),
            url: TimeoutError("pdf retrieval timed out"),
        })
        adapter = EarningsTranscriptPullAdapter(
            DiscoveryPolicyCatalog({"standard": policy()}, "standard"), Search(),
            transport, lambda: "2026-08-01T00:00:00Z",
        )
        with tempfile.TemporaryDirectory() as directory:
            repository = AcquisitionRepository(Path(directory) / "acquisition")
            repository.register_source(configured)
            result = AcquisitionEngine(
                repository, AdapterRegistry((adapter,)),
                lambda: "2026-08-01T00:00:00Z",
            ).run_source(configured.source_id, "pdf-timeout")
        self.assertEqual(result.status, RunStatus.PARTIAL)
        self.assertEqual(result.failures, 1)
        self.assertEqual(result.diagnostics[-1]["failure_code"], "candidate_fetch_timeout")
        self.assertEqual(result.diagnostics[-1]["failure_class"], "transient_adapter")
        self.assertTrue(result.diagnostics[-1]["retryable"])
        self.assertEqual(transport.requests, [listing, url])

    def test_redirect_aliases_collapse_before_engine_candidate_emission(self) -> None:
        first = "https://ir.example.com/alias-a-2026-04-30-earnings-call-transcript"
        second = "https://ir.example.com/alias-b-2026-04-30-earnings-call-transcript"
        final = "https://ir.example.com/2026-04-30-earnings-call-transcript.html"
        body = "Firm A quarterly earnings call transcript April 30, 2026. Operator. " \
               "Chief Executive Officer. Prepared remarks."
        transport = Transport({
            first: html(final, body), second: html(final, body), final: html(final, body),
        })
        configured = SourceProfile(
            "source-a", "Firm A transcripts", True, "earnings_transcript",
            {"mode": "discovery", "discovery_hints": [first, second],
             "discovery_class": "standard"},
            {"firm_id": "firm-a", "artifact_id": "earnings_transcript"},
        )
        adapter = EarningsTranscriptPullAdapter(
            DiscoveryPolicyCatalog({"standard": policy()}, "standard"), Search(),
            transport, lambda: "2026-08-01T00:00:00Z",
        )
        page = adapter.discover(configured, None)
        self.assertEqual(len(page.candidates), 1)
        aliases = page.candidates[0].provenance.metadata["observed_aliases"]
        self.assertEqual(set(aliases), {first, second, final})
        adapter.retrieve(configured, page.candidates[0])
        self.assertEqual(transport.requests, [first, second, final])

        engine_transport = Transport({
            first: html(final, body), second: html(final, body), final: html(final, body),
        })
        engine_adapter = EarningsTranscriptPullAdapter(
            DiscoveryPolicyCatalog({"standard": policy()}, "standard"), Search(),
            engine_transport, lambda: "2026-08-01T00:00:00Z",
        )
        with tempfile.TemporaryDirectory() as directory:
            repository = AcquisitionRepository(Path(directory) / "acquisition")
            repository.register_source(configured)
            result = AcquisitionEngine(
                repository, AdapterRegistry((engine_adapter,)),
                lambda: "2026-08-01T00:00:00Z",
            ).run_source(configured.source_id, "redirect-alias")
            history = [
                item for item in repository.history()
                if item.get("record_type") == "retrieval_attempt"
            ]
        self.assertEqual(result.status, RunStatus.COMPLETE)
        self.assertEqual(result.candidates_discovered, 1)
        self.assertEqual(result.candidates_unique, 1)
        self.assertEqual(len(result.outcomes), 1)
        self.assertEqual(len(history), 1)
        retained = history[0]["candidate"]["provenance"]
        self.assertEqual(set(retained["metadata"]["observed_aliases"]), {
            first, second, final,
        })
        self.assertEqual(set(retained["locations"]), {first, second, final})
        self.assertEqual(history[0]["diagnostics"]["final_url"], final)
        self.assertNotIn("ambiguous duplicate", json.dumps(result.to_dict()))

    def test_failed_expected_period_proposals_do_not_suppress_valid_fallback(self) -> None:
        expected = "https://ir.example.com/2026-04-30-earnings-call-transcript.html"
        fallback = "https://ir.example.com/2026-01-30-earnings-call-transcript.html"
        listing = "https://ir.example.com/transcripts/"
        valid = html(
            fallback,
            "Firm A quarterly earnings call transcript January 30, 2026. Operator. "
            "Chief Executive Officer. Prepared remarks.",
        )
        for failed in (
            html(expected, "", status=404),
            html(expected, "Quarterly results without transcript speaker evidence."),
        ):
            with self.subTest(status=failed.status, content=failed.content):
                source = SourceProfile(
                    "source-a", "Firm A", True, "earnings_transcript",
                    {"listing_urls": [], "allowed_hosts": ["ir.example.com"],
                     "candidate_proposals": [
                         {"url": expected, "label": "Q2 2026 earnings call transcript"},
                         {"url": fallback, "label": "Q1 2026 earnings call transcript"},
                     ], "maximum_candidates": 2, "firm_identity_terms": ["Firm A"],
                     "expected_reporting_period": "2026-Q2"},
                    {"firm_id": "firm-a", "artifact_id": "earnings_transcript"},
                )
                result = EarningsCallTranscriptAcquisition(
                    source, Transport({expected: failed, fallback: valid}),
                    lambda: "2026-08-01T00:00:00Z",
                ).acquire(IntervalAcquisitionRequest(
                    "firm-a", "earnings_transcript", date(2000, 1, 1), date(2026, 8, 2)
                ))
                self.assertEqual(len(result.artifacts), 1)
                self.assertEqual(result.artifacts[0].candidate.provenance.metadata[
                    "requested_url"
                ], fallback)

    def test_validated_expected_period_still_suppresses_historical_fallback(self) -> None:
        expected = "https://ir.example.com/2026-04-30-earnings-call-transcript.html"
        fallback = "https://ir.example.com/2026-01-30-earnings-call-transcript.html"
        source = SourceProfile(
            "source-a", "Firm A", True, "earnings_transcript",
            {"listing_urls": [], "allowed_hosts": ["ir.example.com"],
             "candidate_proposals": [
                 {"url": expected, "label": "Q2 2026 earnings call transcript"},
                 {"url": fallback, "label": "Q1 2026 earnings call transcript"},
             ], "maximum_candidates": 2, "firm_identity_terms": ["Firm A"],
             "expected_reporting_period": "2026-Q2"},
            {"firm_id": "firm-a", "artifact_id": "earnings_transcript"},
        )
        responses = {
            expected: html(expected, "Firm A quarterly earnings call transcript April 30, "
                           "2026. Operator. Chief Executive Officer. Prepared remarks."),
            fallback: html(fallback, "Firm A quarterly earnings call transcript January 30, "
                           "2026. Operator. Chief Executive Officer. Prepared remarks."),
        }
        result = EarningsCallTranscriptAcquisition(
            source, Transport(responses), lambda: "2026-08-01T00:00:00Z",
        ).acquire(IntervalAcquisitionRequest(
            "firm-a", "earnings_transcript", date(2000, 1, 1), date(2026, 8, 2)
        ))
        self.assertEqual(len(result.artifacts), 1)
        self.assertEqual(result.artifacts[0].candidate.provenance.metadata[
            "requested_url"
        ], expected)

        hint = "https://ir.example.com/transcripts/"
        engine_transport = Transport({
            hint: html(
                hint,
                f"<a href='{expected}'>Q2 2026 earnings call transcript</a>"
                f"<a href='{fallback}'>Q1 2026 earnings call transcript</a>",
            ),
            **responses,
        })
        configured = profile(hint)
        adapter = EarningsTranscriptPullAdapter(
            DiscoveryPolicyCatalog({"standard": policy()}, "standard"), Search(),
            engine_transport, lambda: "2026-08-01T00:00:00Z",
        )
        with tempfile.TemporaryDirectory() as directory:
            repository = AcquisitionRepository(Path(directory) / "acquisition")
            repository.register_source(configured)
            engine_result = AcquisitionEngine(
                repository, AdapterRegistry((adapter,)),
                lambda: "2026-08-01T00:00:00Z",
            ).run_source(configured.source_id, "expected-precedence")
        self.assertEqual(engine_result.status, RunStatus.COMPLETE)
        self.assertEqual(engine_result.durable_acquisitions, 1)
        self.assertEqual(engine_result.skips, 0)
        self.assertEqual(engine_transport.requests, [hint, expected])

    def test_unexpected_programming_exception_is_not_reported_as_provider_failure(self) -> None:
        hint = "https://ir.example.com/transcripts/"
        candidate = "https://ir.example.com/2026-04-30-earnings-call-transcript.html"
        configured = profile(hint)

        for phase in ("discovery", "retrieval"):
            with self.subTest(phase=phase), tempfile.TemporaryDirectory() as directory:
                transport = Transport({
                    hint: html(
                        hint,
                        f"<a href='{candidate}'>Q2 earnings call transcript</a>",
                    ),
                    candidate: html(
                        candidate,
                        "Firm A earnings call transcript April 30, 2026. Operator. ",
                    ),
                })
                adapter = EarningsTranscriptPullAdapter(
                    DiscoveryPolicyCatalog({"standard": policy()}, "standard"), Search(),
                    transport, lambda: "2026-08-01T00:00:00Z",
                )
                repository = AcquisitionRepository(Path(directory) / "acquisition")
                repository.register_source(configured)
                engine = AcquisitionEngine(
                    repository, AdapterRegistry((adapter,)),
                    lambda: "2026-08-01T00:00:00Z",
                )
                target = (
                    patch.object(
                        BoundedTranscriptDiscovery, "discover",
                        side_effect=NameError("discovery implementation defect"),
                    )
                    if phase == "discovery"
                    else patch.object(
                        EarningsCallTranscriptAcquisition,
                        "_transcript_validation_failure",
                        side_effect=NameError("validator implementation defect"),
                    )
                )
                with target:
                    result = engine.run_source(configured.source_id, f"bug-{phase}")
                self.assertEqual(result.status, RunStatus.FAILED)
                self.assertEqual(result.failures, 1)
                self.assertEqual(
                    result.diagnostics[-1]["failure_class"], "malformed_adapter"
                )
                self.assertFalse(result.diagnostics[-1]["retryable"])
                self.assertNotEqual(
                    result.diagnostics[-1]["failure_class"], "transient_adapter"
                )

    def test_listing_is_fetched_once_while_order_and_validation_remain_owned(self) -> None:
        hint = "https://ir.example.com/transcripts/"
        older = "https://ir.example.com/2026-01-30-earnings-call-transcript.html"
        expected = "https://ir.example.com/2026-04-30-earnings-call-transcript.html"
        listing = html(
            hint,
            f"<a href='{older}'>Q1 2026 earnings call transcript</a>"
            f"<a href='{expected}'>Q2 2026 earnings call transcript</a>",
        )
        transport = Transport({
            hint: listing,
            expected: html(expected, "Quarterly results without speaker evidence."),
        })
        adapter = EarningsTranscriptPullAdapter(
            DiscoveryPolicyCatalog({"standard": policy()}, "standard"), Search(),
            transport, lambda: "2026-08-01T00:00:00Z",
        )
        page = adapter.discover(profile(hint), None)
        self.assertEqual(transport.requests, [hint])
        self.assertEqual(
            [item.provenance.metadata["resolved_url"] for item in page.candidates],
            [expected, older],
        )
        with self.assertRaises(AdapterFailure) as raised:
            adapter.retrieve(profile(hint), page.candidates[0])
        self.assertEqual(raised.exception.code, "candidate_validation_mismatch")
        self.assertEqual(transport.requests, [hint, expected])
        self.assertEqual(transport.requests.count(hint), 1)

    def test_sequential_discovery_has_no_cached_candidate_bodies_or_stale_state(self) -> None:
        hint = "https://ir.example.com/transcripts/"
        first = "https://ir.example.com/2026-04-30-earnings-call-transcript.html"
        second = "https://ir.example.com/2026-07-30-earnings-call-transcript.html"
        transport = Transport({
            hint: html(hint, f"<a href='{first}'>Q2 2026 earnings call transcript</a>"),
            first: html(first, "Firm A quarterly earnings call transcript April 30, 2026. "
                              "Operator. Chief Executive Officer. Prepared remarks."),
            second: html(second, "Firm A quarterly earnings call transcript July 30, 2026. "
                                "Operator. Chief Executive Officer. Prepared remarks."),
        })
        adapter = EarningsTranscriptPullAdapter(
            DiscoveryPolicyCatalog({"standard": policy()}, "standard"), Search(),
            transport, lambda: "2026-08-01T00:00:00Z",
        )
        first_page = adapter.discover(profile(hint), None)
        self.assertEqual(transport.requests, [hint])
        self.assertFalse(hasattr(adapter, "_retrievals"))

        transport.responses[hint] = html(
            hint, f"<a href='{second}'>Q3 2026 earnings call transcript</a>"
        )
        second_page = adapter.discover(profile(hint), None)
        self.assertNotEqual(
            first_page.candidates[0].candidate_id, second_page.candidates[0].candidate_id
        )
        result = adapter.retrieve(profile(hint), second_page.candidates[0])
        self.assertIn(b"July 30", result.content)
        self.assertEqual(transport.requests, [hint, hint, second])


if __name__ == "__main__":
    unittest.main()
