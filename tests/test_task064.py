"""Focused acceptance evidence for TASK-064 StockAnalysis provider architecture."""

from __future__ import annotations

import json
import tempfile
import unittest
from datetime import date
from pathlib import Path
from jsonschema import Draft202012Validator

from rfi.acquisition import (
    AcquisitionEngine,
    AcquisitionRepository,
    AdapterRegistry,
    AdapterFailure,
    SourceProfile,
    TranscriptAcquisitionSelection,
    TranscriptAcquisitionTarget,
    TranscriptSeed,
)
from rfi.acquisition.earnings_transcripts import EarningsTranscriptHttpResponse
from rfi.acquisition.providers.stockanalysis import (
    StockAnalysisTranscriptProvider,
    archive_url,
    normalize_provider_identifier,
    validate_document_url,
)
from rfi.discovery import (
    DiscoveryPolicy,
    DiscoveryPolicyCatalog,
    EarningsTranscriptPullAdapter,
    TranscriptTerminalSelectionPolicy,
    TranscriptAcquisitionOrchestrator,
)
from rfi.source_profiles import (
    RetrievalCandidate,
    SourceProfileDraft,
    SourceProfileItem,
    SourceProfileRepository,
    load_canonical_template,
)
from rfi.source_profiles.contracts import SourceProfileError
from rfi.firms import FirmDraft, FirmRepository
from rfi.firms.contracts import FirmStatus

ROOT = Path(__file__).resolve().parents[1]
ARCHIVE_URL = "https://stockanalysis.com/stocks/orcl/transcripts/"
DOCUMENT_URL = "https://stockanalysis.com/stocks/orcl/transcripts/592465-q4-2026/"
ARCHIVE = (ROOT / "fixtures/transcripts/stockanalysis-orcl-archive.html").read_bytes()
DOCUMENT = (ROOT / "fixtures/transcripts/stockanalysis-orcl-q4-2026.html").read_bytes()


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


def response(url: str, content: bytes) -> EarningsTranscriptHttpResponse:
    return EarningsTranscriptHttpResponse(url, 200, "text/html", content)


def profile() -> SourceProfile:
    return SourceProfile(
        "source-orcl-transcript",
        "Oracle transcripts",
        True,
        "earnings_transcript",
        {
            "mode": "discovery",
            "provider": "stockanalysis",
            "discovery_hint_kind": "provider_identifier",
            "discovery_hint_value": "ORCL",
            "discovery_class": "standard",
            "discovery_hints": [],
        },
        {
            "firm_id": "oracle",
            "artifact_id": "earnings_transcript",
            "retrieval_adapter_id": "earnings-call-transcript",
        },
    )


def policies(**overrides: int) -> DiscoveryPolicyCatalog:
    values = {
        "max_search_queries": 0,
        "max_results_per_query": 1,
        "max_unique_eligible_links_per_page": 20,
        "max_depth": 1,
        "max_pages": 10,
        "max_distinct_hosts": 2,
        "max_bytes": 2_000_000,
        "max_elapsed_seconds": 60,
        "max_candidate_evaluations": 10,
        "max_redirects": 2,
    }
    values.update(overrides)
    return DiscoveryPolicyCatalog({"standard": DiscoveryPolicy(**values)}, "standard")


class StockAnalysisProviderTests(unittest.TestCase):
    def provider(self, transport: Transport | None = None) -> StockAnalysisTranscriptProvider:
        return StockAnalysisTranscriptProvider(
            transport or Transport({
                ARCHIVE_URL: response(ARCHIVE_URL, ARCHIVE),
                DOCUMENT_URL: response(DOCUMENT_URL, DOCUMENT),
            }),
            lambda: "2026-08-04T00:00:00+00:00",
        )

    def test_provider_identifier_resolution_is_conservative_and_deterministic(self) -> None:
        self.assertEqual(normalize_provider_identifier(" ORCL "), "orcl")
        self.assertEqual(archive_url("ORCL"), ARCHIVE_URL)
        for value in ("", "ORCL/../../msft", "ORCL?x=1", "orcl transcripts"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                normalize_provider_identifier(value)

    def test_archive_admits_only_same_firm_transcript_documents_in_observed_order(self) -> None:
        page = self.provider().discover(
            profile(), TranscriptSeed("stockanalysis", "provider_identifier", "ORCL", "configured"),
            TranscriptAcquisitionTarget("oracle"),
        )
        self.assertEqual([item.provenance.metadata["link_label"] for item in page.candidates], [
            "Oracle Corporation (ORCL) Q4 2026 Earnings Call Transcript",
            "Oracle Corporation (ORCL) Q3 2026 Earnings Call Transcript",
        ])
        self.assertEqual(page.diagnostics["search_queries"], 0)
        self.assertEqual(page.candidates[0].provenance.locations[0], ARCHIVE_URL)
        provenance = json.dumps(page.candidates[0].provenance.to_dict(), sort_keys=True)
        self.assertEqual(provenance.count('"provider"'), 1)
        self.assertEqual(
            page.candidates[0].provenance.provider_identifiers["provider"],
            "stockanalysis",
        )

    def test_direct_document_skips_archive_and_converges_on_candidate_identity(self) -> None:
        transport = Transport({
            ARCHIVE_URL: response(ARCHIVE_URL, ARCHIVE),
            DOCUMENT_URL: response(DOCUMENT_URL, DOCUMENT),
        })
        provider = self.provider(transport)
        archive = provider.discover(
            profile(), TranscriptSeed("stockanalysis", "provider_identifier", "ORCL", "configured"),
            TranscriptAcquisitionTarget("oracle"),
        )
        transport.requests.clear()
        direct = provider.discover(
            profile(), TranscriptSeed("stockanalysis", "url", DOCUMENT_URL, "learned"),
            TranscriptAcquisitionTarget("oracle"),
        )
        self.assertEqual(transport.requests, [])
        self.assertEqual(
            direct.candidates[0].candidate_id, archive.candidates[0].candidate_id
        )
        self.assertEqual(validate_document_url(DOCUMENT_URL)[0], DOCUMENT_URL)

    def test_transcript_extraction_preserves_content_and_neutral_observations(
        self,
    ) -> None:
        provider = self.provider()
        candidate = provider.discover(
            profile(), TranscriptSeed("stockanalysis", "url", DOCUMENT_URL, "learned"),
            TranscriptAcquisitionTarget("oracle"),
        ).candidates[0]
        result = provider.retrieve(profile(), candidate)
        text = result.content.decode()
        self.assertIn("Good afternoon, and welcome", text)
        self.assertIn("I will now hand the call to Doug.", text)
        self.assertNotIn("Provider-generated summary", text)
        self.assertNotIn("Subscription prompt", text)
        self.assertEqual(result.trusted_event_date, date(2026, 6, 15))
        turns = result.speaker_turn_observations
        self.assertEqual([item.ordinal for item in turns], [1, 2, 3, 4])
        self.assertEqual(
            [item.speaker_label for item in turns][1:3],
            ["Safra Catz", "Safra Catz"],
        )
        self.assertEqual(len(turns[1].paragraphs), 2)
        self.assertIn("Good afternoon, and welcome", turns[0].paragraphs[0])
        related = result.related_artifact_observations
        self.assertEqual([item.artifact_kind for item in related], [
            "earnings_release", "presentation_slides", "annual_report", "audio",
        ])
        self.assertEqual(result.diagnostics["related_artifacts_retrieved"], 0)
        self.assertEqual(
            [item.provider for item in result.transcript_learning_feedback],
            ["stockanalysis", "stockanalysis"],
        )
        self.assertEqual(result.diagnostics["speaker_turn_count"], 4)
        self.assertEqual(result.diagnostics["related_artifact_count"], 4)
        self.assertEqual(result.diagnostics["learning_feedback_count"], 2)
        rendered_diagnostics = json.dumps(result.diagnostics, sort_keys=True)
        self.assertEqual(rendered_diagnostics, json.dumps(result.diagnostics, sort_keys=True))
        self.assertLess(len(rendered_diagnostics.encode()), 4096)
        for forbidden in (
            "Good afternoon, and welcome",
            "I will now hand the call to Doug.",
            "speaker_turns",
            '"paragraphs"',
            '"related_artifacts"',
            '"learning_feedback"',
        ):
            self.assertNotIn(forbidden, rendered_diagnostics)
        self.assertNotIn("event_group_id", json.dumps(result.diagnostics))
        decision = TranscriptTerminalSelectionPolicy(
            TranscriptAcquisitionSelection.first_in_date_range(
                date(2026, 1, 1), date(2026, 12, 31)
            )
        ).qualify(candidate, result)
        self.assertTrue(decision.qualifies)
        self.assertEqual(decision.diagnostics["validated_event_date"], "2026-06-15")

    def test_event_date_is_not_inferred_from_document_slug(self) -> None:
        without_date = DOCUMENT.replace(
            b'<time datetime="2026-06-15">June 15, 2026</time>', b""
        ).replace(
            b"</head>",
            b'<script type="application/ld+json">'
            b'{"@type":"Article","datePublished":"2026-06-16"}'
            b"</script></head>",
        )
        transport = Transport({
            ARCHIVE_URL: response(ARCHIVE_URL, ARCHIVE),
            DOCUMENT_URL: response(DOCUMENT_URL, without_date),
        })
        provider = self.provider(transport)
        candidate = provider.discover(
            profile(),
            TranscriptSeed(
                "stockanalysis", "provider_identifier", "ORCL", "configured"
            ),
            TranscriptAcquisitionTarget("oracle"),
        ).candidates[0]
        result = provider.retrieve(profile(), candidate)
        self.assertIsNone(result.trusted_event_date)
        self.assertFalse(result.diagnostics["trusted_event_date_available"])
        for forbidden in (
            "validated_event_date", "trusted_event_date", "validated_position",
            "validated_revision",
        ):
            self.assertNotIn(forbidden, result.diagnostics)
        decision = TranscriptTerminalSelectionPolicy(
            TranscriptAcquisitionSelection.first_in_date_range(
                date(2026, 1, 1), date(2026, 12, 31)
            )
        ).qualify(candidate, result)
        self.assertFalse(decision.qualifies)
        self.assertEqual(decision.validation_outcome, "event_date_unavailable")

    def test_unrecognized_artifact_date_stays_unset_without_fallback(self) -> None:
        unrecognized = DOCUMENT.replace(
            b'<time datetime="2026-06-15">June 15, 2026</time>',
            b'<time datetime="not-a-date">June 15, 2026</time>',
        )
        provider = self.provider(Transport({
            DOCUMENT_URL: response(DOCUMENT_URL, unrecognized)
        }))
        candidate = provider.discover(
            profile(), TranscriptSeed("stockanalysis", "url", DOCUMENT_URL, "learned"),
            TranscriptAcquisitionTarget("oracle"),
        ).candidates[0]
        result = provider.retrieve(profile(), candidate)
        self.assertIsNone(result.trusted_event_date)
        serialized = json.dumps(result.diagnostics, sort_keys=True)
        self.assertNotIn("2026-06-15", serialized)
        self.assertNotIn("event_date", result.diagnostics["provider_metadata"])

    def test_url_validation_rejects_deceptive_hosts_paths_and_cross_firm_routes(self) -> None:
        for url in (
            "https://stockanalysis.com.evil.test/stocks/orcl/transcripts/x/",
            "http://stockanalysis.com/stocks/orcl/transcripts/x/",
            "https://stockanalysis.com/stocks/orcl/earnings/x/",
            "https://stockanalysis.com/stocks/orcl/transcripts/x/?next=msft",
        ):
            with self.subTest(url=url), self.assertRaises(ValueError):
                validate_document_url(url)
        with self.assertRaisesRegex(AdapterFailure, "unrelated provider identifier"):
            self.provider().discover(
                profile(),
                TranscriptSeed(
                    "stockanalysis", "url",
                    "https://stockanalysis.com/stocks/msft/transcripts/123-q4-2026/",
                    "learned",
                ),
                TranscriptAcquisitionTarget("oracle"),
            )

    def test_transient_retries_are_provider_local_and_bounded(self) -> None:
        transport = Transport({ARCHIVE_URL: TimeoutError("fixture timeout")})
        provider = self.provider(transport)
        with self.assertRaisesRegex(AdapterFailure, "retry bound"):
            provider.discover(
                profile(),
                TranscriptSeed(
                    "stockanalysis", "provider_identifier", "ORCL", "configured"
                ),
                TranscriptAcquisitionTarget("oracle"),
            )
        self.assertEqual(transport.requests, [ARCHIVE_URL, ARCHIVE_URL, ARCHIVE_URL])
        self.assertEqual(provider.retry_count, 2)


class ProviderOrchestrationTests(unittest.TestCase):
    def test_firm_configuration_requires_explicit_provider_hint_kind_and_value(self) -> None:
        schema = json.loads(
            (ROOT / "src/rfi/resources/firm-config-v1.schema.json").read_text()
        )
        configured = json.loads(
            (ROOT / "docs/microsoft.firm-config.example.json").read_text()
        )
        self.assertEqual(tuple(Draft202012Validator(schema).iter_errors(configured)), ())
        for missing in ("provider", "discovery_hint"):
            malformed = json.loads(json.dumps(configured))
            del malformed["sources"]["earnings_transcript"][missing]
            with self.subTest(missing=missing):
                self.assertTrue(tuple(Draft202012Validator(schema).iter_errors(malformed)))
        for missing in ("kind", "value"):
            malformed = json.loads(json.dumps(configured))
            del malformed["sources"]["earnings_transcript"]["discovery_hint"][missing]
            with self.subTest(missing=missing):
                self.assertTrue(tuple(Draft202012Validator(schema).iter_errors(malformed)))

    def test_engine_preserves_persistence_checkpoint_and_learning_ownership(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            firms = FirmRepository.initialize(root / "firms")
            firms.create(FirmDraft(
                "oracle", "Oracle Corporation", "2026-01-01", status=FirmStatus.ACTIVE
            ))
            repository = AcquisitionRepository(root / "acquisition")
            configured = profile()
            repository.register_source(configured)
            transport = Transport({
                ARCHIVE_URL: response(ARCHIVE_URL, ARCHIVE),
                DOCUMENT_URL: response(DOCUMENT_URL, DOCUMENT),
            })
            adapter = EarningsTranscriptPullAdapter(
                policies(), transport=transport, repository=repository,
                clock=lambda: "2026-08-04T00:00:00+00:00",
            )
            result = AcquisitionEngine(
                repository, AdapterRegistry((adapter,)),
                lambda: "2026-08-04T00:00:00+00:00",
            ).run_source(configured.source_id, "task064")
            self.assertEqual(result.durable_acquisitions, 1)
            self.assertIsNotNone(result.checkpoint_after)
            learning = repository.discovery_anchors(
                "oracle", configured.source_id, adapter.adapter_id
            )
            self.assertEqual(learning[0]["provider"], "stockanalysis")
            self.assertEqual(learning[0]["requested_url"], DOCUMENT_URL)
            self.assertEqual(transport.requests, [ARCHIVE_URL, DOCUMENT_URL])

    def test_configured_seed_is_first_and_learned_seeds_keep_provider(self) -> None:
        class Repository:
            @staticmethod
            def discovery_anchors(*_args: object) -> tuple[dict[str, object], ...]:
                return (
                    {"provider": "other", "requested_url": "https://example.test/a"},
                    {"provider": "stockanalysis", "requested_url": DOCUMENT_URL},
                )

        trials = TranscriptAcquisitionOrchestrator(
            Repository(), "earnings-call-transcript"  # type: ignore[arg-type]
        ).plan(profile(), TranscriptAcquisitionTarget("oracle"))
        self.assertEqual([(item.provider, item.seed_kind, item.seed_source) for item in trials], [
            ("stockanalysis", "provider_identifier", "configured"),
            ("other", "url", "learned"),
            ("stockanalysis", "url", "learned"),
        ])
        self.assertEqual(trials[0].starting_seed, "ORCL")

    def test_adapter_dispatches_explicit_provider_without_url_inference(self) -> None:
        transport = Transport({ARCHIVE_URL: response(ARCHIVE_URL, ARCHIVE)})
        adapter = EarningsTranscriptPullAdapter(
            policies(), transport=transport,
            clock=lambda: "2026-08-04T00:00:00+00:00",
        )
        trial = adapter.acquisition_trials(profile())[0]
        page = adapter.discover_trial(profile(), trial)
        self.assertEqual(page.diagnostics["provider"], "stockanalysis")
        self.assertEqual(transport.requests, [ARCHIVE_URL])

    def test_source_profile_validation_fails_closed_for_partial_or_unknown_provider(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repository = SourceProfileRepository.initialize(
                Path(directory), load_canonical_template()
            )
            for candidate in (
                RetrievalCandidate("discovery", 1, discovery_hint_value="ORCL"),
                RetrievalCandidate(
                    "discovery", 1, provider="unknown",
                    discovery_hint_kind="provider_identifier", discovery_hint_value="ORCL",
                ),
                RetrievalCandidate(
                    "discovery", 1, provider="stockanalysis",
                    discovery_hint_kind="url", discovery_hint_value="ORCL",
                ),
            ):
                with self.subTest(candidate=candidate), self.assertRaises(SourceProfileError):
                    repository.validate(SourceProfileDraft(
                        "oracle", (SourceProfileItem("earnings_transcript", True, (candidate,)),)
                    ))

    def test_fixture_replay_is_byte_for_byte_deterministic(self) -> None:
        outputs: list[str] = []
        for _ in range(2):
            provider = StockAnalysisTranscriptProvider(
                Transport({
                    ARCHIVE_URL: response(ARCHIVE_URL, ARCHIVE),
                    DOCUMENT_URL: response(DOCUMENT_URL, DOCUMENT),
                }),
                lambda: "2026-08-04T00:00:00+00:00",
            )
            page = provider.discover(
                profile(),
                TranscriptSeed(
                    "stockanalysis", "provider_identifier", "ORCL", "configured"
                ),
                TranscriptAcquisitionTarget("oracle"),
            )
            result = provider.retrieve(profile(), page.candidates[0])
            outputs.append(json.dumps({
                "candidates": [item.canonical() for item in page.candidates],
                "content": result.content.decode(),
                "diagnostics": result.diagnostics,
                "trusted_event_date": (
                    result.trusted_event_date.isoformat()
                    if result.trusted_event_date else None
                ),
                "speaker_turn_observations": [
                    item.to_dict() for item in result.speaker_turn_observations
                ],
                "related_artifact_observations": [
                    item.to_dict() for item in result.related_artifact_observations
                ],
                "transcript_learning_feedback": [
                    item.to_dict() for item in result.transcript_learning_feedback
                ],
            }, sort_keys=True))
        self.assertEqual(outputs[0], outputs[1])


if __name__ == "__main__":
    unittest.main()
