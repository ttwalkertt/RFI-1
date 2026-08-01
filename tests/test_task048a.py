"""Focused integration and bounded-accounting evidence for TASK-048A."""

from __future__ import annotations

import json
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

from rfi.acquisition import (
    AcquisitionEngine,
    AcquisitionRepository,
    AdapterRegistry,
    EarningsTranscriptHttpResponse,
    EarningsTranscriptTransport,
    RunStatus,
    SourceProfile,
)
from rfi.discovery import (
    BoundedTranscriptDiscovery,
    BudgetedTranscriptTransport,
    DiscoveryPolicy,
    DiscoveryPolicyCatalog,
    DiscoveryPolicyError,
    DiscoverySearchResponse,
    DISCOVERY_BUDGET_FIELDS,
    EarningsTranscriptPullAdapter,
    load_discovery_policies,
)
from rfi.firm_configuration import prepare_firm_configuration
from rfi.pull import create_pull_workflow
from rfi.source_profiles import SourceProfileRepository, load_canonical_template
from rfi.storage import RepositoryDatabase


class TranscriptTransport(EarningsTranscriptTransport):
    def __init__(self, responses: dict[str, EarningsTranscriptHttpResponse]) -> None:
        self.responses = responses

    def get(self, url: str) -> EarningsTranscriptHttpResponse:
        value = self.responses[url]
        if isinstance(value, Exception):
            raise value
        return value


class Search:
    endpoint = "https://search.example/results"

    def __init__(self, responses: tuple[DiscoverySearchResponse, ...]) -> None:
        self.responses = list(responses)
        self.queries: list[tuple[str, int]] = []

    def search(self, query: str, limit: int) -> DiscoverySearchResponse:
        self.queries.append((query, limit))
        return self.responses.pop(0)


def policy(**changes: int) -> DiscoveryPolicy:
    return replace(DiscoveryPolicy(4, 10, 1000, 2, 30, 8, 20_971_520, 60), **changes)


def profile(*, hints: list[str], discovery_class: str = "standard") -> SourceProfile:
    return SourceProfile(
        "source-example", "Example transcripts", True, "earnings_transcript",
        {"mode": "discovery", "discovery_hints": hints,
         "discovery_class": discovery_class},
        {"firm_id": "example", "artifact_id": "earnings_transcript"},
    )


class TranscriptPullIntegrationTests(unittest.TestCase):
    def test_actual_policy_limit_names_exhausted_budget(self) -> None:
        search = Search((DiscoverySearchResponse(
            ("https://one.example/", "https://two.example/"), 10
        ),))
        bounded = BudgetedTranscriptTransport(
            TranscriptTransport({}), policy(max_results_per_query=1)
        )
        result = BoundedTranscriptDiscovery(search, bounded, bounded.policy).discover(
            ("Example",), ()
        )
        self.assertTrue(result.diagnostics["bounds_exhausted"])
        self.assertEqual(
            result.diagnostics["exhausted_budget"], "max_results_per_query"
        )
        self.assertEqual(result.diagnostics["discovery_failures"], 0)

    def test_non_budget_search_failure_is_not_bound_exhaustion(self) -> None:
        bounded = BudgetedTranscriptTransport(TranscriptTransport({}), policy())
        result = BoundedTranscriptDiscovery(
            Search(()), bounded, bounded.policy
        ).discover(("Example",), ())
        self.assertFalse(result.diagnostics["bounds_exhausted"])
        self.assertEqual(result.diagnostics["exhausted_budget"], "")
        self.assertEqual(result.diagnostics["discovery_failures"], 1)
        self.assertEqual(result.diagnostics["discovery_failure_codes"], "search_failed")

    def test_non_budget_page_fetch_failure_is_not_bound_exhaustion(self) -> None:
        bounded = BudgetedTranscriptTransport(TranscriptTransport({}), policy())
        result = BoundedTranscriptDiscovery(
            Search(()), bounded, bounded.policy
        ).discover((), ("https://missing.example/page",))
        self.assertFalse(result.diagnostics["bounds_exhausted"])
        self.assertEqual(result.diagnostics["exhausted_budget"], "")
        self.assertEqual(result.diagnostics["discovery_failures"], 1)
        self.assertEqual(
            result.diagnostics["discovery_failure_codes"], "page_fetch_failed"
        )

    def test_every_exhausted_result_names_valid_policy_field(self) -> None:
        results = []
        for maximum in (0, 1):
            seed = "https://ir.example/page"
            content = b"<a href='transcripts'>transcript archive</a>"
            bounded = BudgetedTranscriptTransport(
                TranscriptTransport({
                    seed: EarningsTranscriptHttpResponse(
                        seed, 200, "text/html", content
                    )
                }),
                policy(max_depth=maximum),
            )
            result = BoundedTranscriptDiscovery(
                Search(()), bounded, bounded.policy
            ).discover((), (seed,))
            if result.diagnostics["bounds_exhausted"]:
                results.append(result)
        self.assertTrue(results)
        for result in results:
            self.assertIn(
                result.diagnostics["exhausted_budget"], DISCOVERY_BUDGET_FIELDS
            )
            self.assertNotEqual(result.diagnostics["exhausted_budget"], "")

    def test_policy_catalog_is_exact_and_unknown_class_fails(self) -> None:
        catalog = load_discovery_policies()
        self.assertEqual(tuple(catalog.classes), ("extended", "shallow", "standard"))
        self.assertEqual(
            catalog.resolve("shallow"),
            DiscoveryPolicy(2, 5, 1000, 1, 10, 3, 5_242_880, 20),
        )
        self.assertEqual(catalog.resolve("standard"), policy())
        self.assertEqual(
            catalog.resolve("extended"),
            DiscoveryPolicy(8, 15, 1000, 3, 75, 15, 52_428_800, 180),
        )
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            legacy = json.loads(Path("config/discovery-policies.json").read_text())
            value = legacy["classes"]["standard"].pop(
                "max_unique_eligible_links_per_page"
            )
            legacy["classes"]["standard"]["max_links_per_page"] = value
            target = root / "legacy.json"
            target.write_text(json.dumps(legacy))
            self.assertEqual(
                load_discovery_policies(target).resolve("standard")
                .max_unique_eligible_links_per_page,
                1000,
            )
        with self.assertRaisesRegex(DiscoveryPolicyError, "unknown discovery_class"):
            catalog.resolve("unbounded")

    def test_policy_schema_rejects_bad_numeric_values(self) -> None:
        base = json.loads(Path("config/discovery-policies.json").read_text())
        cases = (-1, 0, 1.5, 10_000_000_000)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            schema = root / "schema.json"
            schema.write_text(Path("docs/discovery-policies-v1.schema.json").read_text())
            for index, value in enumerate(cases):
                broken = json.loads(json.dumps(base))
                broken["classes"]["standard"]["max_pages"] = value
                target = root / f"bad-{index}.json"
                target.write_text(json.dumps(broken))
                with self.subTest(value=value), self.assertRaises(DiscoveryPolicyError):
                    load_discovery_policies(target, schema)

    def test_sparse_firm_projection_selects_independent_classes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            state = Path(directory)
            RepositoryDatabase.initialize(state)
            target = state / "firm-config"
            target.mkdir()
            target.joinpath("microsoft.firm-config.json").write_text(
                Path("docs/microsoft.firm-config.example.json").read_text())
            prepare_firm_configuration(state)
            view = SourceProfileRepository.open(
                state / "source-profiles", load_canonical_template()).get("microsoft")
            self.assertIsNotNone(view)
            items = {item.artifact_id: item for item in view.items}
            self.assertEqual(
                items["earnings_transcript"].retrieval_candidates[0].discovery_class,
                "extended",
            )
            self.assertEqual(
                items["press_release"].retrieval_candidates[0].discovery_class,
                "standard",
            )
            raw = json.loads(Path("docs/microsoft.firm-config.example.json").read_text())
            self.assertEqual(raw["sources"]["earnings_transcript"], {"discovery_class": "extended"})
            self.assertNotIn("listing_urls", json.dumps(raw))
            self.assertNotIn("allowed_hosts", json.dumps(raw))

    def test_registry_claims_only_transcript_discovery(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            state = Path(directory)
            RepositoryDatabase.initialize(state)
            capabilities = create_pull_workflow(state).adapter_capabilities()
        item = next(x for x in capabilities if x["adapter_id"] == "earnings-call-transcript")
        self.assertEqual(item["retrieval_modes"], ["discovery"])

    def test_discovery_hands_third_party_url_to_existing_validator(self) -> None:
        transcript = "https://third.example/example-2026-01-28-earnings-call-transcript.html"
        search = Search((DiscoverySearchResponse((transcript,), 100),))
        transport = TranscriptTransport({
            transcript: EarningsTranscriptHttpResponse(
                transcript, 200, "text/html",
                b"<!doctype html><html>Quarterly earnings call transcript. "
                b"Example Corporation. Operator: Welcome. "
                b"Chief Executive Officer: Remarks.</html>")})
        adapter = EarningsTranscriptPullAdapter(
            DiscoveryPolicyCatalog({"standard": policy()}, "standard"), search,
            transport, lambda: "2026-07-30T12:00:00+00:00")
        page = adapter.discover(profile(hints=["Example Corporation"]), None)
        self.assertEqual(len(page.candidates), 1)
        result = adapter.retrieve(profile(hints=["Example Corporation"]), page.candidates[0])
        self.assertEqual(result.content, transport.responses[transcript].content)
        self.assertEqual(page.diagnostics["search_queries"], 1)
        self.assertEqual(page.diagnostics["pages"], 4)  # search, discovery, listing, validation

    def test_exhausted_bound_is_indeterminate_and_not_system_failure(self) -> None:
        search = Search((DiscoverySearchResponse(
            ("https://a.example/", "https://b.example/"), 20
        ),))
        selected = policy(max_results_per_query=1)
        adapter = EarningsTranscriptPullAdapter(
            DiscoveryPolicyCatalog({"standard": selected}, "standard"), search,
            TranscriptTransport({}), lambda: "2026-07-30T12:00:00+00:00")
        source = profile(hints=["Example Corporation"])
        with tempfile.TemporaryDirectory() as directory:
            repository = AcquisitionRepository(Path(directory) / "acquisition")
            repository.register_source(source)
            result = AcquisitionEngine(
                repository, AdapterRegistry((adapter,)),
                lambda: "2026-07-30T12:00:00+00:00").run_source(
                    source.source_id, "bounded")
        self.assertEqual(result.status, RunStatus.COMPLETE)
        self.assertEqual(result.candidates_discovered, 0)
        self.assertEqual(result.failures, 0)

    def test_page_host_byte_and_link_limits_count_requests_and_stop(self) -> None:
        seed = "https://ir.example/events"
        body = (
            b"<a href='one-earnings-call-transcript'>earnings call transcript</a>"
            b"<a href='two-earnings-call-transcript'>earnings call transcript</a>"
        )
        budget = BudgetedTranscriptTransport(
            TranscriptTransport({
                seed: EarningsTranscriptHttpResponse(seed, 200, "text/html", body)
            }),
            policy(max_unique_eligible_links_per_page=1, max_bytes=len(body) + 1))
        result = BoundedTranscriptDiscovery(Search(()), budget, budget.policy).discover((), (seed,))
        self.assertTrue(result.exhausted)
        self.assertEqual(
            result.diagnostics["exhausted_budget"],
            "max_unique_eligible_links_per_page",
        )
        self.assertEqual(result.diagnostics["pages"], 1)
        self.assertEqual(result.diagnostics["bytes"], len(body))
        self.assertEqual(result.diagnostics["distinct_hosts"], 1)

    def test_search_page_host_byte_depth_and_elapsed_bounds_are_named(self) -> None:
        seed = "https://one.example/start"
        next_url = "https://two.example/next"
        html = f"<a href='{next_url}/transcripts'>transcript archive</a>".encode()

        # Seed pages are depth zero, so an admitted traversal from a depth-zero seed
        # exhausts max_depth=0 before a second fetch.
        budget = BudgetedTranscriptTransport(
            TranscriptTransport({
                seed: EarningsTranscriptHttpResponse(seed, 200, "text/html", html)
            }),
            policy(max_depth=0))
        result = BoundedTranscriptDiscovery(Search(()), budget, budget.policy).discover((), (seed,))
        self.assertEqual(result.diagnostics["exhausted_budget"], "max_depth")
        self.assertEqual(result.diagnostics["pages"], 1)

        for field, selected in (
            ("max_pages", policy(max_pages=1)),
            ("max_distinct_hosts", policy(max_distinct_hosts=1)),
            ("max_bytes", policy(max_bytes=1)),
        ):
            transport = TranscriptTransport({
                seed: EarningsTranscriptHttpResponse(seed, 200, "text/html", b"xx"),
                next_url: EarningsTranscriptHttpResponse(next_url, 200, "text/html", b"xx"),
            })
            bounded = BudgetedTranscriptTransport(transport, selected)
            with self.subTest(field=field), self.assertRaises(Exception):
                bounded.get(seed)
                bounded.get(next_url)
            self.assertEqual(bounded.exhausted_budget, field)

        times = iter((0.0, 2.0))
        elapsed = BudgetedTranscriptTransport(
            TranscriptTransport({}), policy(max_elapsed_seconds=1), lambda: next(times))
        with self.assertRaises(TimeoutError):
            elapsed.get(seed)
        self.assertEqual(elapsed.exhausted_budget, "max_elapsed_seconds")

        search = Search((DiscoverySearchResponse((), 1),))
        bounded = BudgetedTranscriptTransport(
            TranscriptTransport({}), policy(max_search_queries=1)
        )
        result = BoundedTranscriptDiscovery(
            search, bounded, bounded.policy
        ).discover(("one", "two"), ())
        self.assertEqual(result.diagnostics["search_queries"], 1)
        self.assertEqual(result.diagnostics["exhausted_budget"], "max_search_queries")


if __name__ == "__main__":
    unittest.main()
