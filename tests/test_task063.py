"""Focused acceptance evidence for TASK-063 bounded transcript resolution."""

from __future__ import annotations

import json
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

from rfi.acquisition import (
    AcquisitionEngine,
    AcquisitionRepository,
    AdapterAcquisitionTrial,
    AdapterRegistry,
    RunStatus,
    SourceProfile,
    TranscriptAcquisitionSelection,
    TranscriptAcquisitionTarget,
    TranscriptDocumentStatus,
    classify_transcript_document,
)
from rfi.acquisition.earnings_transcripts import (
    EarningsCallTranscriptAcquisition,
    EarningsTranscriptHttpResponse,
    ReportingPeriod,
)
from rfi.discovery import (
    BoundedTranscriptResolver,
    BudgetedTranscriptTransport,
    DiscoveryPolicy,
    DiscoveryPolicyCatalog,
    DiscoverySearchResponse,
    EarningsTranscriptPullAdapter,
)
from rfi.firms import FirmRepository
from rfi.firms.contracts import FirmDraft, FirmStatus


def html(url: str, body: str, status: int = 200) -> EarningsTranscriptHttpResponse:
    return EarningsTranscriptHttpResponse(
        url, status, "text/html", f"<!doctype html><html>{body}</html>".encode()
    )


def transcript(date_value: str, extra: str = "") -> str:
    return (
        f"Firm A quarterly earnings call transcript {date_value}. "
        "Operator. Chief Executive Officer. Prepared remarks. " + extra
    )


class Transport:
    def __init__(
        self, responses: dict[str, EarningsTranscriptHttpResponse | Exception]
    ) -> None:
        self.responses = responses
        self.requests: list[str] = []

    def get(self, url: str) -> EarningsTranscriptHttpResponse:
        self.requests.append(url)
        value = self.responses[url]
        if isinstance(value, Exception):
            raise value
        return value


class Search:
    endpoint = "https://search.example.invalid/"

    def __init__(self) -> None:
        self.queries: list[str] = []

    def search(self, query: str, limit: int) -> DiscoverySearchResponse:
        self.queries.append(query)
        return DiscoverySearchResponse((), 0)


def policies(**overrides: int) -> DiscoveryPolicyCatalog:
    values = {
        "max_search_queries": 2,
        "max_results_per_query": 5,
        "max_unique_eligible_links_per_page": 100,
        "max_depth": 2,
        "max_pages": 20,
        "max_distinct_hosts": 8,
        "max_bytes": 2_000_000,
        "max_elapsed_seconds": 60,
        "max_candidate_evaluations": 40,
        "max_redirects": 10,
    }
    values.update(overrides)
    return DiscoveryPolicyCatalog(
        {"standard": DiscoveryPolicy(**values)}, "standard"
    )


def source(*hints: str) -> SourceProfile:
    return SourceProfile(
        "source-a",
        "Firm A transcripts",
        True,
        "earnings_transcript",
        {
            "mode": "discovery",
            "discovery_class": "standard",
            "discovery_hints": list(hints or ("identity:Firm A",)),
        },
        {
            "firm_id": "firm-a",
            "artifact_id": "earnings_transcript",
            "retrieval_adapter_id": "earnings-call-transcript",
        },
    )


class BoundedTranscriptResolutionTests(unittest.TestCase):
    def repository(
        self, directory: str, configured: SourceProfile
    ) -> AcquisitionRepository:
        firms = FirmRepository.initialize(Path(directory) / "firms")
        firms.create(FirmDraft(
            "firm-a", "Firm A", "2025-01-01", status=FirmStatus.ACTIVE
        ))
        repository = AcquisitionRepository(Path(directory) / "acquisition")
        repository.register_source(configured)
        return repository

    @staticmethod
    def learned(*urls: str) -> tuple[dict[str, object], ...]:
        return tuple({
            "normalized_url": url,
            "requested_url": url,
            "resolved_url": url,
        } for url in urls)

    def test_direct_learned_pages_are_fetched_once_without_archive_crawl(self) -> None:
        first = "https://ir.example.com/q2-2026-earnings-call-transcript.html"
        equivalent = "HTTPS://IR.EXAMPLE.COM:443/q2-2026-earnings-call-transcript.html#top"
        second = "https://ir.example.com/q1-2026-earnings-call-transcript.html"
        archive = "https://ir.example.com/transcripts/archive"
        fallback = "https://configured.example.com/transcripts/"
        configured = source(fallback, "identity:Firm A")
        transport = Transport({
            first: html(first, transcript("April 30, 2026", f"<a href='{archive}'>Archive</a>")),
            second: html(
                second,
                transcript("January 30, 2026", f"<a href='{archive}'>Archive</a>"),
            ),
            fallback: html(fallback, "unused configured fallback"),
        })
        search = Search()

        with tempfile.TemporaryDirectory() as directory:
            repository = self.repository(directory, configured)
            adapter = EarningsTranscriptPullAdapter(
                policies(), search, transport, lambda: "2026-08-03T00:00:00Z",
                repository=repository,
            )
            anchors = self.learned(first, equivalent, second)
            with patch.object(repository, "discovery_anchors", return_value=anchors):
                trials = adapter.acquisition_trials(configured)
                result = AcquisitionEngine(
                    repository, AdapterRegistry((adapter,)),
                    lambda: "2026-08-03T00:00:00Z",
                ).run_source(configured.source_id, "direct-learned")
            success = next(
                item for item in repository.history() if item.get("outcome") == "success"
            )

        self.assertEqual(len(trials), 2)
        self.assertEqual(trials[0].seed_kind, "resolution_session")
        self.assertEqual(trials[0].duplicate_seed_count, 4)
        self.assertEqual(trials[0].seeds, (first, second))
        self.assertEqual(result.status, RunStatus.COMPLETE)
        self.assertEqual(result.durable_acquisitions, 1)
        self.assertEqual(transport.requests, [first, second])
        self.assertNotIn(archive, transport.requests)
        self.assertNotIn(fallback, transport.requests)
        self.assertTrue(success["diagnostics"]["response_cache_reused"])
        self.assertEqual(search.queries, [])

    def test_listing_resolution_is_one_hop_and_never_submits_search(self) -> None:
        listing = "https://ir.example.com/transcripts/"
        nested = "https://ir.example.com/transcripts/archive"
        candidate = "https://ir.example.com/q2-2026-earnings-call-transcript.html"
        configured = source(listing, "identity:Firm A")
        transport = Transport({
            listing: html(
                listing,
                f"<a href='{nested}'>Transcript archive</a>"
                f"<a href='{candidate}'>Q2 2026 earnings call transcript</a>",
            ),
            candidate: html(candidate, transcript("April 30, 2026")),
            nested: html(nested, "must not be fetched"),
        })
        search = Search()

        with tempfile.TemporaryDirectory() as directory:
            repository = self.repository(directory, configured)
            adapter = EarningsTranscriptPullAdapter(
                policies(), search, transport, lambda: "2026-08-03T00:00:00Z",
                repository=repository,
            )
            result = AcquisitionEngine(
                repository, AdapterRegistry((adapter,)),
                lambda: "2026-08-03T00:00:00Z",
            ).run_source(configured.source_id, "one-hop")

        page = next(item for item in result.diagnostics if "resolution_mode" in item)
        self.assertEqual(result.durable_acquisitions, 1)
        self.assertEqual(transport.requests, [listing, candidate])
        self.assertNotIn(nested, transport.requests)
        self.assertEqual(search.queries, [])
        self.assertEqual(page["resolution_mode"], "bounded_one_hop")
        self.assertFalse(page["recursive_traversal"])
        self.assertEqual(page["traversed_hyperlinks"], 0)
        self.assertEqual(
            page["page_classification_counts"], {"transcript_listing": 1}
        )

    def test_configured_fallback_reuses_learned_phase_budget(self) -> None:
        learned = "https://ir.example.com/investor-relations"
        fallback = "https://ir.example.com/transcripts/"
        candidate = "https://ir.example.com/q2-2026-earnings-call-transcript.html"
        configured = source(fallback, "identity:Firm A")
        transport = Transport({
            learned: html(learned, "Investor relations home page"),
            fallback: html(
                fallback,
                f"<a href='{candidate}'>Q2 2026 earnings call transcript</a>",
            ),
            candidate: html(candidate, transcript("April 30, 2026")),
        })

        with tempfile.TemporaryDirectory() as directory:
            repository = self.repository(directory, configured)
            adapter = EarningsTranscriptPullAdapter(
                policies(), Search(), transport, lambda: "2026-08-03T00:00:00Z",
                repository=repository,
            )
            with patch.object(
                repository, "discovery_anchors", return_value=self.learned(learned)
            ):
                result = AcquisitionEngine(
                    repository, AdapterRegistry((adapter,)),
                    lambda: "2026-08-03T00:00:00Z",
                ).run_source(configured.source_id, "fallback")

        fallback_page = next(
            item for item in result.diagnostics
            if item.get("seed_kind") == "configured_fallback"
        )
        self.assertEqual(result.durable_acquisitions, 1)
        self.assertEqual(transport.requests, [learned, fallback, candidate])
        self.assertEqual(fallback_page["pages"], 2)

    def test_run_budget_cannot_reset_for_configured_fallback(self) -> None:
        learned = "https://ir.example.com/investor-relations"
        fallback = "https://ir.example.com/transcripts/"
        configured = source(fallback, "identity:Firm A")
        transport = Transport({
            learned: html(learned, "Investor relations home page"),
            fallback: html(fallback, "must be rejected before fetch"),
        })

        with tempfile.TemporaryDirectory() as directory:
            repository = self.repository(directory, configured)
            adapter = EarningsTranscriptPullAdapter(
                policies(max_pages=1), Search(), transport,
                lambda: "2026-08-03T00:00:00Z", repository=repository,
            )
            with patch.object(
                repository, "discovery_anchors", return_value=self.learned(learned)
            ):
                result = AcquisitionEngine(
                    repository, AdapterRegistry((adapter,)),
                    lambda: "2026-08-03T00:00:00Z",
                ).run_source(configured.source_id, "shared-budget")

        self.assertIn(result.status, {RunStatus.PARTIAL, RunStatus.BLOCKED})
        self.assertEqual(result.failures, 1)
        self.assertEqual(transport.requests, [learned])
        self.assertIn("budget was exhausted", result.diagnostics[-1]["message"])
        self.assertIsNone(result.checkpoint_after)

    def test_unique_candidate_ceiling_is_shared_with_fallback(self) -> None:
        learned = "https://ir.example.com/transcripts/learned"
        fallback = "https://ir.example.com/transcripts/configured"
        first = "https://ir.example.com/q2-2026-earnings-call-transcript.html"
        second = "https://ir.example.com/q1-2026-earnings-call-transcript.html"
        configured = source(fallback, "identity:Firm A")
        transport = Transport({
            learned: html(
                learned,
                f"<a href='{first}'>Q2 2026 earnings call transcript</a>"
                f"<a href='{second}'>Q1 2026 earnings call transcript</a>",
            ),
            first: html(first, "Quarterly results without transcript speaker evidence"),
            second: html(second, transcript("January 30, 2026")),
            fallback: html(fallback, "must not receive a fresh candidate allowance"),
        })

        with tempfile.TemporaryDirectory() as directory:
            repository = self.repository(directory, configured)
            adapter = EarningsTranscriptPullAdapter(
                policies(max_candidate_evaluations=1), Search(), transport,
                lambda: "2026-08-03T00:00:00Z", repository=repository,
            )
            with patch.object(
                repository, "discovery_anchors", return_value=self.learned(learned)
            ):
                result = AcquisitionEngine(
                    repository, AdapterRegistry((adapter,)),
                    lambda: "2026-08-03T00:00:00Z",
                ).run_source(configured.source_id, "candidate-budget")

        self.assertIn(result.status, {RunStatus.PARTIAL, RunStatus.BLOCKED})
        self.assertEqual(transport.requests, [learned, first])
        self.assertNotIn(second, transport.requests)
        self.assertNotIn(fallback, transport.requests)
        self.assertEqual(result.diagnostics[-1]["failure_code"], "max_candidate_evaluations")

    def test_first_in_range_preserves_global_earliest_selection(self) -> None:
        later_seed = "https://ir.example.com/q2-2025-earnings-call-transcript.html"
        earlier_seed = "https://ir.example.com/q1-2025-earnings-call-transcript.html"
        configured = source("identity:Firm A")
        selection = TranscriptAcquisitionSelection.first_in_date_range(
            date(2025, 1, 1), date(2025, 12, 31)
        )
        transport = Transport({
            later_seed: html(later_seed, transcript("April 30, 2025")),
            earlier_seed: html(earlier_seed, transcript("January 30, 2025")),
        })

        with tempfile.TemporaryDirectory() as directory:
            repository = self.repository(directory, configured)
            adapter = EarningsTranscriptPullAdapter(
                policies(), Search(), transport, lambda: "2026-08-03T00:00:00Z",
                repository=repository, selection=selection,
            )
            with patch.object(
                repository, "discovery_anchors",
                return_value=self.learned(later_seed, earlier_seed),
            ):
                result = AcquisitionEngine(
                    repository, AdapterRegistry((adapter,)),
                    lambda: "2026-08-03T00:00:00Z",
                ).run_source(configured.source_id, "first-range")
            success = next(
                item for item in repository.history() if item.get("outcome") == "success"
            )

        self.assertEqual(result.status, RunStatus.COMPLETE)
        self.assertEqual(result.durable_acquisitions, 1)
        self.assertEqual(
            success["diagnostics"]["validated_event_date"], "2025-01-30"
        )
        self.assertEqual(transport.requests, [later_seed, earlier_seed])

    def test_operator_injection_never_adds_configured_fallback(self) -> None:
        supplied = "https://operator.example.com/transcripts/"
        fallback = "https://configured.example.com/transcripts/"
        candidate = "https://operator.example.com/q2-2026-earnings-call-transcript.html"
        configured = source(fallback, "identity:Firm A")
        transport = Transport({
            supplied: html(
                supplied,
                f"<a href='{candidate}'>Q2 2026 earnings call transcript</a>",
            ),
            candidate: html(candidate, transcript("April 30, 2026")),
            fallback: html(fallback, "must not be fetched"),
        })

        with tempfile.TemporaryDirectory() as directory:
            repository = self.repository(directory, configured)
            adapter = EarningsTranscriptPullAdapter(
                policies(), Search(), transport, lambda: "2026-08-03T00:00:00Z",
                repository=repository,
            )
            target = TranscriptAcquisitionTarget("firm-a")
            result = AcquisitionEngine(
                repository, AdapterRegistry((adapter,)),
                lambda: "2026-08-03T00:00:00Z",
            ).run_source_trial(
                configured.source_id,
                "operator-only",
                AdapterAcquisitionTrial(
                    "transcript-trial-1", supplied, "single_seed", target,
                    "operator_supplied", (supplied,),
                ),
            )

        self.assertEqual(result.durable_acquisitions, 1)
        self.assertEqual(transport.requests, [supplied, candidate])
        self.assertNotIn(fallback, transport.requests)

    def test_synthetic_company_shapes_do_not_expand_shared_archives(self) -> None:
        for firm in ("amzn", "ibm", "wdc"):
            with self.subTest(firm=firm), tempfile.TemporaryDirectory() as directory:
                first = f"https://stockanalysis.com/stocks/{firm}/transcripts/q2-2026/"
                second = f"https://stockanalysis.com/stocks/{firm}/transcripts/q1-2026/"
                archive = f"https://stockanalysis.com/stocks/{firm}/transcripts/"
                configured = source(archive, "identity:Firm A")
                transport = Transport({
                    first: html(
                        first, transcript("April 30, 2026", f"<a href='{archive}'>Archive</a>"),
                    ),
                    second: html(
                        second, transcript("January 30, 2026", f"<a href='{archive}'>Archive</a>"),
                    ),
                    archive: html(archive, "must not be fetched"),
                })
                repository = self.repository(directory, configured)
                adapter = EarningsTranscriptPullAdapter(
                    policies(), Search(), transport,
                    lambda: "2026-08-03T00:00:00Z", repository=repository,
                )
                with patch.object(
                    repository, "discovery_anchors",
                    return_value=self.learned(first, second),
                ):
                    result = AcquisitionEngine(
                        repository, AdapterRegistry((adapter,)),
                        lambda: "2026-08-03T00:00:00Z",
                    ).run_source(configured.source_id, firm)

                self.assertEqual(result.durable_acquisitions, 1)
                self.assertEqual(transport.requests, [first, second])
                self.assertNotIn(archive, transport.requests)

    def test_classifier_is_structural_and_independent_of_durable_validation(self) -> None:
        wrong_firm = "https://ir.example.com/q2-2026-earnings-call-transcript.html"
        archive = "https://ir.example.com/transcripts/"
        configured = source("identity:Firm A")
        response = html(
            wrong_firm,
            "Other Corp. quarterly earnings call transcript April 30, 2026. "
            "Operator. Chief Executive Officer. Prepared remarks. "
            f"<a href='{archive}'>Archive</a>",
        )
        assessment = classify_transcript_document(response, wrong_firm)
        self.assertEqual(
            assessment.status, TranscriptDocumentStatus.TRANSCRIPT_DOCUMENT
        )

        transport = Transport({wrong_firm: response})
        with tempfile.TemporaryDirectory() as directory:
            repository = self.repository(directory, configured)
            adapter = EarningsTranscriptPullAdapter(
                policies(), Search(), transport, lambda: "2026-08-03T00:00:00Z",
                repository=repository,
            )
            with patch.object(
                repository, "discovery_anchors", return_value=self.learned(wrong_firm)
            ):
                result = AcquisitionEngine(
                    repository, AdapterRegistry((adapter,)),
                    lambda: "2026-08-03T00:00:00Z",
                ).run_source(configured.source_id, "wrong-firm-boundary")

        page = next(item for item in result.diagnostics if "resolution_mode" in item)
        self.assertEqual(
            page["page_classification_counts"], {"transcript_document": 1}
        )
        self.assertEqual(result.durable_acquisitions, 0)
        self.assertEqual(transport.requests, [wrong_firm])
        self.assertNotIn(archive, transport.requests)
        self.assertIn("candidate_validation_mismatch", json.dumps(result.to_dict()))

    def test_structural_document_remains_document_when_date_is_out_of_range(self) -> None:
        seed = "https://ir.example.com/q2-2026-earnings-call-transcript.html"
        archive = "https://ir.example.com/transcripts/"
        configured = source("identity:Firm A")
        selection = TranscriptAcquisitionSelection.first_in_date_range(
            date(2025, 1, 1), date(2025, 12, 31)
        )
        transport = Transport({
            seed: html(
                seed,
                transcript("April 30, 2026", f"<a href='{archive}'>Archive</a>"),
            )
        })

        with tempfile.TemporaryDirectory() as directory:
            repository = self.repository(directory, configured)
            adapter = EarningsTranscriptPullAdapter(
                policies(), Search(), transport, lambda: "2026-08-03T00:00:00Z",
                repository=repository, selection=selection,
            )
            with patch.object(
                repository, "discovery_anchors", return_value=self.learned(seed)
            ):
                result = AcquisitionEngine(
                    repository, AdapterRegistry((adapter,)),
                    lambda: "2026-08-03T00:00:00Z",
                ).run_source(configured.source_id, "wrong-date-boundary")

        page = next(item for item in result.diagnostics if "resolution_mode" in item)
        self.assertEqual(
            page["page_classification_counts"], {"transcript_document": 1}
        )
        self.assertEqual(result.durable_acquisitions, 0)
        self.assertEqual(transport.requests, [seed])
        self.assertNotIn(archive, transport.requests)
        self.assertIn("selection_date_mismatch", json.dumps(result.to_dict()))

    def test_sanitized_amazon_capture_has_bounded_before_after_work(self) -> None:
        fixture = json.loads(Path(
            "fixtures/transcripts/task063-amazon-sanitized-topology.json"
        ).read_text(encoding="utf-8"))
        seeds = tuple(item["url"] for item in fixture["learned_seeds"])
        archive = fixture["shared_archive"]
        responses = {
            item["url"]: html(
                item["url"],
                transcript(
                    item["event_date"],
                    f"Amazon.com, Inc. <a href='{archive}'>All transcripts</a>",
                ),
            )
            for item in fixture["learned_seeds"]
        }
        transport = Transport(responses)
        budgeted = BudgetedTranscriptTransport(transport, policies().resolve("standard"))

        with patch.object(
            EarningsCallTranscriptAcquisition,
            "_transcript_validation_failure",
            side_effect=AssertionError("resolver called the private validator"),
        ):
            resolved = BoundedTranscriptResolver(
                budgeted, policies().resolve("standard")
            ).resolve(
                seeds, "retained_anchor", "resolution_session", "learned",
                ReportingPeriod.parse("2016-Q3"), ReportingPeriod.parse("2016-Q4"),
            )

        legacy = [item["legacy_work"] for item in fixture["learned_seeds"]]
        expected = fixture["expected_task063_work"]
        self.assertEqual(sum(item["pages_fetched"] for item in legacy), 26)
        self.assertEqual(sum(item["raw_hyperlinks"] for item in legacy), 2932)
        self.assertEqual(sum(item["candidate_proposals"] for item in legacy), 128)
        self.assertEqual(transport.requests, list(seeds))
        self.assertNotIn(archive, transport.requests)
        self.assertFalse(any(
            url in transport.requests for url in fixture["shared_archive_candidates"]
        ))
        self.assertEqual(budgeted.pages, expected["seed_pages_fetched"])
        self.assertEqual(resolved.diagnostics["raw_hyperlinks"], 0)
        self.assertEqual(resolved.diagnostics["traversed_hyperlinks"], 0)
        self.assertEqual(len(resolved.candidate_proposals), 2)
        self.assertEqual(
            resolved.diagnostics["page_classification_counts"],
            {"transcript_document": 2},
        )


if __name__ == "__main__":
    unittest.main()
