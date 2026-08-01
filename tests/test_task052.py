"""Focused regression evidence for TASK-052 configured transcript discovery hints."""

from __future__ import annotations

import json
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

from rfi.acquisition import EarningsTranscriptHttpResponse, SourceProfile
from rfi.discovery import (
    DiscoveryPolicy,
    DiscoveryPolicyCatalog,
    DiscoverySearchResponse,
    EarningsTranscriptPullAdapter,
)
from rfi.firm_configuration import (
    FirmConfigurationError,
    prepare_firm_configuration,
    validate_firm_configuration,
)
from rfi.source_profiles import SourceProfileRepository, load_canonical_template
from rfi.storage import RepositoryDatabase


EXAMPLE = Path("docs/microsoft.firm-config.example.json")
HINT = "https://stockanalysis.com/stocks/amzn/transcripts/"


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
    return replace(DiscoveryPolicy(4, 10, 20, 2, 30, 8, 20_971_520, 60), **changes)


def source(hints: list[str]) -> SourceProfile:
    return SourceProfile(
        "source-amazon", "Amazon transcripts", True, "earnings_transcript",
        {"mode": "discovery", "discovery_hints": hints,
         "discovery_class": "standard"},
        {"firm_id": "amazon", "artifact_id": "earnings_transcript"},
    )


class ConfiguredTranscriptHintTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.state = Path(self.temporary.name)
        RepositoryDatabase.initialize(self.state)

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def write(self, hint: object = HINT) -> None:
        value = json.loads(EXAMPLE.read_text(encoding="utf-8"))
        value["sources"]["earnings_transcript"]["discovery_hints"] = [hint]
        directory = self.state / "firm-config"
        directory.mkdir(exist_ok=True)
        directory.joinpath("microsoft.firm-config.json").write_text(
            json.dumps(value), encoding="utf-8"
        )

    def test_valid_hint_loads_and_projects_unchanged_to_canonical_candidate(self) -> None:
        self.write()
        loaded = validate_firm_configuration(self.state)
        self.assertEqual(
            loaded[0].value["sources"]["earnings_transcript"]["discovery_hints"],
            [HINT],
        )
        prepare_firm_configuration(self.state)
        profile = SourceProfileRepository.open(
            self.state / "source-profiles", load_canonical_template()
        ).get("microsoft")
        transcript = next(
            item for item in profile.items if item.artifact_id == "earnings_transcript"
        )
        candidate = transcript.retrieval_candidates[0]
        self.assertEqual(candidate.discovery_hints[0], HINT)
        self.assertEqual(candidate.discovery_class, "extended")
        release = next(item for item in profile.items if item.artifact_id == "press_release")
        self.assertNotIn(HINT, release.retrieval_candidates[0].discovery_hints)

    def test_malformed_and_unsupported_hints_fail_with_json_pointer(self) -> None:
        for hint in ("not a URL", "ftp://stockanalysis.com/amzn"):
            with self.subTest(hint=hint):
                self.write(hint)
                with self.assertRaises(FirmConfigurationError) as raised:
                    prepare_firm_configuration(self.state)
                self.assertIn(
                    "/sources/earnings_transcript/discovery_hints/0",
                    str(raised.exception),
                )

    def test_missing_source_hint_preserves_identity_search_behavior(self) -> None:
        search = RecordingSearch()
        adapter = EarningsTranscriptPullAdapter(
            DiscoveryPolicyCatalog({"standard": policy()}, "standard"), search,
            RecordingTransport({}), lambda: "2026-07-30T12:00:00+00:00",
        )
        page = adapter.discover(source(["Amazon.com, Inc."]), None)
        self.assertEqual(len(search.queries), 1)
        self.assertEqual(page.diagnostics["configured_hint_status"], "not_supplied")
        self.assertEqual(page.diagnostics["coverage"], "indeterminate")

    def test_hint_is_consumed_before_search_and_candidate_still_fails_validation(self) -> None:
        candidate = (
            "https://stockanalysis.com/stocks/amzn/earnings-call-transcript.html"
        )
        listing = EarningsTranscriptHttpResponse(
            HINT, 200, "text/html",
            f"<html><a href='{candidate}'>AMZN earnings call transcript</a></html>".encode(),
        )
        invalid = EarningsTranscriptHttpResponse(
            candidate, 200, "text/html",
            b"<!doctype html><html>Quarterly earnings call transcript. "
            b"Different Corporation. Operator: Welcome. CEO: Remarks. 2026-01-28</html>",
        )
        search = RecordingSearch()
        transport = RecordingTransport({HINT: listing, candidate: invalid})
        adapter = EarningsTranscriptPullAdapter(
            DiscoveryPolicyCatalog({"standard": policy()}, "standard"), search,
            transport, lambda: "2026-07-30T12:00:00+00:00",
        )
        page = adapter.discover(source([HINT, "Amazon.com, Inc."]), None)
        self.assertEqual(search.queries, [])
        self.assertEqual(transport.requests[0], HINT)
        self.assertEqual(page.diagnostics["configured_hint_count"], 1)
        self.assertEqual(page.diagnostics["configured_hint_status"], "used")
        self.assertGreater(page.diagnostics["validation_failures"], 0)
        self.assertEqual(page.candidates, ())
        self.assertEqual(page.diagnostics["coverage"], "incomplete")

    def test_hinted_candidate_identity_uses_retrieved_url_not_configuration_hint(self) -> None:
        candidate = (
            "https://stockanalysis.com/stocks/amzn/earnings-call-transcript-2026.html"
        )
        listing = EarningsTranscriptHttpResponse(
            HINT, 200, "text/html",
            (
                f"<html><a href='{candidate}'>"
                "Amazon Q1 2026 earnings call transcript</a></html>"
            ).encode(),
        )
        transcript = EarningsTranscriptHttpResponse(
            candidate, 200, "text/html",
            b"<!doctype html><html>Amazon.com, Inc. quarterly earnings call transcript "
            b"April 30, 2026. Operator: Welcome. Chief Executive Officer: Remarks.</html>",
        )
        adapter = EarningsTranscriptPullAdapter(
            DiscoveryPolicyCatalog({"standard": policy()}, "standard"), RecordingSearch(),
            RecordingTransport({HINT: listing, candidate: transcript}),
            lambda: "2026-07-30T12:00:00+00:00",
        )
        page = adapter.discover(source([HINT, "Amazon.com, Inc."]), None)
        self.assertEqual(len(page.candidates), 1)
        produced = page.candidates[0]
        self.assertNotIn(HINT, produced.candidate_id)
        self.assertNotIn(HINT, produced.document_id)
        self.assertEqual(produced.provenance.locations[-1], candidate)


if __name__ == "__main__":
    unittest.main()
