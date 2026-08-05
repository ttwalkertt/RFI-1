"""Focused acceptance evidence for TASK-064 StockAnalysis provider architecture."""

from __future__ import annotations

import json
import tempfile
import unittest
from dataclasses import replace
from datetime import date
from pathlib import Path
from unittest.mock import patch
from jsonschema import Draft202012Validator

from rfi.acquisition import (
    AcquisitionEngine,
    AcquisitionRepository,
    AdapterRegistry,
    AdapterFailure,
    AdapterCandidate,
    CandidateDocument,
    RetrievalResult,
    SourceProfile,
    TranscriptAcquisitionSelection,
    TranscriptAcquisitionTarget,
    TranscriptSeed,
    TranscriptEventDisposition,
)
from rfi.acquisition.contracts import ConflictError
from rfi.acquisition.earnings_transcripts import EarningsTranscriptHttpResponse
from rfi.acquisition.providers.stockanalysis import (
    StockAnalysisTranscriptProvider,
    archive_url,
    is_substantial_transcript,
    normalize_provider_identifier,
    validate_document_url,
)
from rfi.acquisition.providers import TranscriptProviderRegistry
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
from rfi.firm_configuration import validate_firm_configuration
from rfi.storage import RepositoryDatabase

ROOT = Path(__file__).resolve().parents[1]
ARCHIVE_URL = "https://stockanalysis.com/stocks/orcl/transcripts/"
DOCUMENT_URL = "https://stockanalysis.com/stocks/orcl/transcripts/592465-q4-2026/"
ARCHIVE = (ROOT / "fixtures/transcripts/stockanalysis-orcl-archive.html").read_bytes()
DOCUMENT = (ROOT / "fixtures/transcripts/stockanalysis-orcl-q4-2026.html").read_bytes()
WDC_ARCHIVE_URL = "https://stockanalysis.com/stocks/wdc/transcripts/"
WDC_DOCUMENT_URL = "https://stockanalysis.com/stocks/wdc/transcripts/548617-q3-2026/"
WDC_UNKNOWN_URL = (
    "https://stockanalysis.com/stocks/wdc/transcripts/"
    "653281-2026-evercore-global-tmt-conference/"
)
WDC_PROVIDER_CLASSIFIED_URL = (
    "https://stockanalysis.com/stocks/wdc/transcripts/"
    "600000-provider-classified-event/"
)
WDC_INVESTOR_DAY_URL = (
    "https://stockanalysis.com/stocks/wdc/transcripts/590000-investor-day/"
)
WDC_ARCHIVE = (ROOT / "fixtures/transcripts/stockanalysis-wdc-archive.html").read_bytes()
WDC_DOCUMENT = (ROOT / "fixtures/transcripts/stockanalysis-wdc-q3-2026.html").read_bytes()
AMZN_ARCHIVE_URL = "https://stockanalysis.com/stocks/amzn/transcripts/"
AMZN_DOCUMENT_URL = "https://stockanalysis.com/stocks/amzn/transcripts/657334-q2-2026/"
AMZN_ARCHIVE = (ROOT / "fixtures/transcripts/stockanalysis-amzn-archive.html").read_bytes()
AMZN_DOCUMENT = (ROOT / "fixtures/transcripts/stockanalysis-amzn-q2-2026.html").read_bytes()


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


def wdc_document_with_date(iso_date: str, display_date: str) -> bytes:
    return WDC_DOCUMENT.replace(
        b'data-event-date="April 30, 2026"',
        f'data-event-date="{display_date}"'.encode(),
    ).replace(
        b'<time datetime="2026-04-30">April 30, 2026</time>',
        f'<time datetime="{iso_date}">{display_date}</time>'.encode(),
    )


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


def wdc_profile() -> SourceProfile:
    configured = profile()
    return SourceProfile(
        "source-wdc-transcript",
        "Western Digital transcripts",
        True,
        configured.mechanism,
        {
            **configured.configuration,
            "discovery_hint_value": "WDC",
        },
        {
            **configured.policy,
            "firm_id": "western-digital",
        },
    )


def amazon_profile() -> SourceProfile:
    configured = profile()
    return SourceProfile(
        "source-amazon-transcript",
        "Amazon transcripts",
        True,
        configured.mechanism,
        {
            **configured.configuration,
            "discovery_hint_value": "AMZN",
            "discovery_class": "standard",
        },
        {
            **configured.policy,
            "firm_id": "amazon",
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


def retain_amazon_transcript(
    repository: AcquisitionRepository,
    artifact: bytes = AMZN_DOCUMENT,
) -> tuple[AdapterCandidate, RetrievalResult, str]:
    provider = StockAnalysisTranscriptProvider(
        Transport({AMZN_DOCUMENT_URL: response(AMZN_DOCUMENT_URL, artifact)}),
        lambda: "2026-08-05T00:00:00+00:00",
    )
    configured = amazon_profile()
    candidate = provider.discover(
        configured,
        TranscriptSeed("stockanalysis", "url", AMZN_DOCUMENT_URL, "learned"),
        TranscriptAcquisitionTarget("amazon"),
    ).candidates[0]
    result = provider.retrieve(configured, candidate)
    repository_candidate = CandidateDocument(
        candidate.candidate_id,
        configured.source_id,
        candidate.document_id,
        candidate.provenance,
    )
    checkpoint = AcquisitionEngine._target_checkpoint(  # noqa: SLF001
        2026 * 4 + 3,
        {candidate.candidate_id: candidate.canonical()},
    )
    receipt = repository.record_success(
        "attempt-task064-amazon-retained",
        repository_candidate,
        result,
        checkpoint,
    )
    return candidate, result, receipt.artifact_id


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

    def test_archive_url_seed_uses_the_existing_archive_discovery_path(self) -> None:
        transport = Transport({ARCHIVE_URL: response(ARCHIVE_URL, ARCHIVE)})
        page = self.provider(transport).discover(
            profile(),
            TranscriptSeed("stockanalysis", "url", ARCHIVE_URL, "operator_supplied"),
            TranscriptAcquisitionTarget("oracle"),
        )

        self.assertEqual(transport.requests, [ARCHIVE_URL])
        self.assertEqual(page.diagnostics["provider_surface"], "archive")
        self.assertEqual(page.diagnostics["seed_kind"], "url")
        self.assertEqual(
            [
                candidate.provenance.metadata["resolved_url"]
                for candidate in page.candidates
            ],
            [
                DOCUMENT_URL,
                "https://stockanalysis.com/stocks/orcl/transcripts/581200-q3-2026/",
            ],
        )

    def test_archive_url_seed_rejects_an_unrelated_provider_identifier(self) -> None:
        transport = Transport({})
        with self.assertRaisesRegex(AdapterFailure, "unrelated provider identifier"):
            self.provider(transport).discover(
                profile(),
                TranscriptSeed(
                    "stockanalysis", "url", WDC_ARCHIVE_URL, "operator_supplied"
                ),
                TranscriptAcquisitionTarget("oracle"),
            )
        self.assertEqual(transport.requests, [])

    def test_wdc_archive_preserves_order_and_related_links_without_classification(self) -> None:
        provider = StockAnalysisTranscriptProvider(
            Transport({WDC_ARCHIVE_URL: response(WDC_ARCHIVE_URL, WDC_ARCHIVE)}),
            lambda: "2026-08-05T00:00:00+00:00",
        )
        page = provider.discover(
            wdc_profile(),
            TranscriptSeed("stockanalysis", "provider_identifier", "WDC", "configured"),
            TranscriptAcquisitionTarget("western-digital"),
        )
        observations = [
            candidate.transcript_metadata_observation for candidate in page.candidates
        ]
        self.assertEqual(
            [candidate.provenance.metadata["link_label"] for candidate in page.candidates],
            [
                "2026 Evercore Global TMT Conference",
                "Earnings Call: Q3 2026",
                "Provider-classified non-earnings event",
                "Investor Day",
            ],
        )
        self.assertEqual(
            [item.event_disposition for item in observations if item is not None],
            [
                TranscriptEventDisposition.UNKNOWN,
                TranscriptEventDisposition.UNKNOWN,
                TranscriptEventDisposition.UNKNOWN,
                TranscriptEventDisposition.UNKNOWN,
            ],
        )
        self.assertEqual(page.diagnostics["candidate_excluded_count"], 0)
        self.assertEqual(page.candidates[0].provenance.metadata["archive_position"], 1)
        related = observations[1].related_artifact_observations  # type: ignore[union-attr]
        self.assertEqual(
            [item.provider_label for item in related],
            ["Slides", "Earnings release", "Quarterly report"],
        )
        self.assertNotIn(
            "/global-slides.pdf", [item.observed_url for item in related]
        )
        self.assertNotIn(
            "/global-annual-report.pdf", [item.observed_url for item in related]
        )

    def test_unknown_archive_entry_remains_an_eligible_fallback(self) -> None:
        unknown_only = WDC_ARCHIVE.replace(
            b'<li class="rounded-lg border border-sharp bg-contrast">\n'
            b'      <a href="/stocks/wdc/transcripts/548617-q3-2026/"',
            b'<li data-removed="true"><a href="/not-a-transcript/"',
        )
        provider = StockAnalysisTranscriptProvider(
            Transport({WDC_ARCHIVE_URL: response(WDC_ARCHIVE_URL, unknown_only)}),
            lambda: "2026-08-05T00:00:00+00:00",
        )
        page = provider.discover(
            wdc_profile(),
            TranscriptSeed("stockanalysis", "provider_identifier", "WDC", "configured"),
            TranscriptAcquisitionTarget("western-digital"),
        )
        self.assertEqual(page.candidates[0].provenance.metadata["link_label"],
                         "2026 Evercore Global TMT Conference")
        self.assertEqual(
            page.candidates[0].transcript_metadata_observation.event_disposition,
            TranscriptEventDisposition.UNKNOWN,
        )

    def test_substantial_transcript_gate_uses_turns_and_text_not_event_label(self) -> None:
        provider = StockAnalysisTranscriptProvider(
            Transport({WDC_DOCUMENT_URL: response(WDC_DOCUMENT_URL, WDC_DOCUMENT)}),
            lambda: "2026-08-05T00:00:00+00:00",
        )
        candidate = provider.discover(
            wdc_profile(),
            TranscriptSeed("stockanalysis", "url", WDC_DOCUMENT_URL, "learned"),
            TranscriptAcquisitionTarget("western-digital"),
        ).candidates[0]
        result = provider.retrieve(wdc_profile(), candidate)
        observation = result.transcript_metadata_observation
        self.assertIsNotNone(observation)
        self.assertEqual(observation.event_label, "Earnings Call: Q3 2026")
        self.assertEqual(
            observation.event_disposition,
            TranscriptEventDisposition.UNKNOWN,
        )
        self.assertEqual(result.diagnostics["substantial_transcript"], True)
        self.assertTrue(is_substantial_transcript(
            turns=result.speaker_turn_observations,
            normalized_text="\n".join(
                paragraph
                for turn in result.speaker_turn_observations
                for paragraph in turn.paragraphs
            ),
        ))
        self.assertFalse(is_substantial_transcript(
            turns=result.speaker_turn_observations,
            normalized_text=(
                "\n".join(
                    paragraph
                    for turn in result.speaker_turn_observations
                    for paragraph in turn.paragraphs
                )
                + "\nDetached provider summary text"
            ),
        ))
        no_semantic_fields = WDC_DOCUMENT.replace(
            b' data-event-type="Earnings Call" data-fiscal-period="Q3 2026"', b""
        )
        provider = StockAnalysisTranscriptProvider(
            Transport({WDC_DOCUMENT_URL: response(WDC_DOCUMENT_URL, no_semantic_fields)}),
            lambda: "2026-08-05T00:00:00+00:00",
        )
        candidate = provider.discover(
            wdc_profile(),
            TranscriptSeed("stockanalysis", "url", WDC_DOCUMENT_URL, "learned"),
            TranscriptAcquisitionTarget("western-digital"),
        ).candidates[0]
        result = provider.retrieve(wdc_profile(), candidate)
        self.assertEqual(result.transcript_metadata_observation.event_label,
                         "Earnings Call: Q3 2026")
        self.assertNotIn("event_type_label", result.diagnostics["provider_metadata"])
        self.assertNotIn("fiscal_period_label", result.diagnostics["provider_metadata"])
        self.assertEqual(
            result.transcript_metadata_observation.event_disposition,
            TranscriptEventDisposition.UNKNOWN,
        )

        insubstantial = WDC_DOCUMENT.replace(
            b'<div data-speaker="Management" data-role="Provider role label" '
            b'data-section="Prepared Remarks"><p>These are the complete captured fixture '
            b'remarks, preserved exactly as provider text for deterministic validation.'
            b'</p></div>',
            b"",
        )
        provider = StockAnalysisTranscriptProvider(
            Transport({WDC_DOCUMENT_URL: response(WDC_DOCUMENT_URL, insubstantial)}),
            lambda: "2026-08-05T00:00:00+00:00",
        )
        candidate = provider.discover(
            wdc_profile(),
            TranscriptSeed("stockanalysis", "url", WDC_DOCUMENT_URL, "learned"),
            TranscriptAcquisitionTarget("western-digital"),
        ).candidates[0]
        with self.assertRaisesRegex(AdapterFailure, "substantial parsed transcript"):
            provider.retrieve(wdc_profile(), candidate)

    def test_questionable_unknown_artifact_is_allowed_when_transcript_is_substantial(self) -> None:
        without_relationships = WDC_DOCUMENT.replace(
            b'<aside id="related-artifacts">',
            b'<aside id="provider-summary" data-provider-summary="true">',
        ).replace(b"data-related-kind", b"data-untrusted-kind")
        provider = StockAnalysisTranscriptProvider(
            Transport({WDC_DOCUMENT_URL: response(WDC_DOCUMENT_URL, without_relationships)}),
            lambda: "2026-08-05T00:00:00+00:00",
        )
        candidate = provider.discover(
            wdc_profile(),
            TranscriptSeed("stockanalysis", "url", WDC_DOCUMENT_URL, "learned"),
            TranscriptAcquisitionTarget("western-digital"),
        ).candidates[0]
        result = provider.retrieve(wdc_profile(), candidate)
        self.assertEqual(
            result.transcript_metadata_observation.event_disposition,
            TranscriptEventDisposition.UNKNOWN,
        )
        self.assertTrue(result.diagnostics["substantial_transcript"])

    def test_related_artifacts_do_not_change_substance_or_event_disposition(self) -> None:
        without_relationships = WDC_DOCUMENT.replace(
            b'<aside id="related-artifacts">',
            b'<aside id="provider-summary" data-provider-summary="true">',
        ).replace(b"data-related-kind", b"data-untrusted-kind")
        results = []
        for artifact in (WDC_DOCUMENT, without_relationships):
            provider = StockAnalysisTranscriptProvider(
                Transport({WDC_DOCUMENT_URL: response(WDC_DOCUMENT_URL, artifact)}),
                lambda: "2026-08-05T00:00:00+00:00",
            )
            candidate = provider.discover(
                wdc_profile(),
                TranscriptSeed("stockanalysis", "url", WDC_DOCUMENT_URL, "learned"),
                TranscriptAcquisitionTarget("western-digital"),
            ).candidates[0]
            results.append(provider.retrieve(wdc_profile(), candidate))
        with_related, without_related = results
        self.assertEqual(len(with_related.related_artifact_observations), 3)
        self.assertEqual(without_related.related_artifact_observations, ())
        self.assertEqual(
            with_related.speaker_turn_observations,
            without_related.speaker_turn_observations,
        )
        self.assertEqual(
            with_related.diagnostics["transcript_word_count"],
            without_related.diagnostics["transcript_word_count"],
        )
        self.assertEqual(
            with_related.transcript_metadata_observation.event_disposition,
            TranscriptEventDisposition.UNKNOWN,
        )
        self.assertEqual(
            without_related.transcript_metadata_observation.event_disposition,
            TranscriptEventDisposition.UNKNOWN,
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
        self.assertEqual([item.provider_label for item in related], [
            "Earnings release", "Slides", "Annual report", "Audio",
        ])
        self.assertTrue(all(
            item.relationship_kind == "explicitly_related_to_transcript"
            and item.source_provenance == DOCUMENT_URL
            for item in related
        ))
        self.assertEqual(
            result.transcript_metadata_observation.event_disposition,
            TranscriptEventDisposition.UNKNOWN,
        )
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

    def test_trusted_date_observations_are_normalized_and_conflicts_are_unset(self) -> None:
        equivalent = DOCUMENT.replace(
            b'<article id="transcript"',
            b'<article id="transcript" data-event-date="June 15, 2026"',
        )
        conflicting = DOCUMENT.replace(
            b'<article id="transcript"',
            b'<article id="transcript" data-event-date="June 14, 2026"',
        )
        for artifact, expected in (
            (equivalent, date(2026, 6, 15)),
            (conflicting, None),
        ):
            with self.subTest(expected=expected):
                provider = self.provider(Transport({
                    DOCUMENT_URL: response(DOCUMENT_URL, artifact)
                }))
                candidate = provider.discover(
                    profile(),
                    TranscriptSeed("stockanalysis", "url", DOCUMENT_URL, "learned"),
                    TranscriptAcquisitionTarget("oracle"),
                ).candidates[0]
                result = provider.retrieve(profile(), candidate)
                self.assertEqual(result.trusted_event_date, expected)

        unrelated_same_class = DOCUMENT.replace(
            b"</article>",
            b'<p class="text-sm font-semibold text-faded">Summary</p></article>',
        )
        provider = self.provider(Transport({
            DOCUMENT_URL: response(DOCUMENT_URL, unrelated_same_class)
        }))
        candidate = provider.discover(
            profile(), TranscriptSeed("stockanalysis", "url", DOCUMENT_URL, "learned"),
            TranscriptAcquisitionTarget("oracle"),
        ).candidates[0]
        self.assertEqual(
            provider.retrieve(profile(), candidate).trusted_event_date,
            date(2026, 6, 15),
        )

    def test_related_label_fallback_is_scoped_to_the_explicit_related_surface(self) -> None:
        artifact = DOCUMENT.replace(
            b'<aside id="provider-summary"',
            b'<a href="https://navigation.example.test/report">Annual Report</a>'
            b'<aside id="provider-summary"',
        )
        provider = self.provider(Transport({
            DOCUMENT_URL: response(DOCUMENT_URL, artifact)
        }))
        candidate = provider.discover(
            profile(), TranscriptSeed("stockanalysis", "url", DOCUMENT_URL, "learned"),
            TranscriptAcquisitionTarget("oracle"),
        ).candidates[0]
        result = provider.retrieve(profile(), candidate)
        self.assertEqual(len(result.related_artifact_observations), 4)
        self.assertNotIn(
            "https://navigation.example.test/report",
            [item.observed_url for item in result.related_artifact_observations],
        )

    def test_provider_metadata_diagnostics_are_allowlisted_and_bounded(self) -> None:
        oversized = ("diagnostic-marker-" + ("x" * 5_000)).encode()
        artifact = DOCUMENT.replace(
            b'data-company="Oracle Corporation"',
            b'data-company="' + oversized + b'" data-untrusted="transcript-body-marker"',
        )
        provider = self.provider(Transport({
            DOCUMENT_URL: response(DOCUMENT_URL, artifact)
        }))
        candidate = provider.discover(
            profile(), TranscriptSeed("stockanalysis", "url", DOCUMENT_URL, "learned"),
            TranscriptAcquisitionTarget("oracle"),
        ).candidates[0]
        result = provider.retrieve(profile(), candidate)
        metadata = result.diagnostics["provider_metadata"]
        self.assertEqual(set(metadata), {
            "company_label", "document_title", "event_type_label",
            "fiscal_period_label", "ticker_label",
        })
        self.assertLessEqual(len(metadata["company_label"]), 256)
        rendered = json.dumps(result.diagnostics, sort_keys=True)
        self.assertNotIn("transcript-body-marker", rendered)
        self.assertLess(len(rendered.encode()), 4096)

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
    def test_registry_accepts_provider_neutral_factories(self) -> None:
        class OtherTranscriptProvider:
            provider = "other"

            def __init__(self, transport: object, clock: object) -> None:
                self.transport = transport
                self.clock = clock

        registry = TranscriptProviderRegistry((
            StockAnalysisTranscriptProvider,
            OtherTranscriptProvider,
        ))
        self.assertEqual(registry.registrations(), {
            "other": "OtherTranscriptProvider",
            "stockanalysis": "StockAnalysisTranscriptProvider",
        })

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

    def test_generic_transcript_hint_remains_provider_neutral(self) -> None:
        hint = "https://stockanalysis.com/quote/tyo/7741/transcripts/"
        configured = json.loads(
            (ROOT / "docs/microsoft.firm-config.example.json").read_text()
        )
        configured["sources"]["earnings_transcript"] = {
            "discovery_class": "extended",
            "discovery_hints": [hint],
        }
        schema = json.loads(
            (ROOT / "src/rfi/resources/firm-config-v1.schema.json").read_text()
        )
        self.assertEqual(tuple(Draft202012Validator(schema).iter_errors(configured)), ())

        with tempfile.TemporaryDirectory() as directory:
            state = Path(directory)
            RepositoryDatabase.initialize(state)
            target = state / "firm-config"
            target.mkdir()
            target.joinpath("microsoft.firm-config.json").write_text(
                json.dumps(configured), encoding="utf-8"
            )
            loaded = validate_firm_configuration(state)

        transcript = next(
            item for item in loaded[0].profile.items
            if item.artifact_id == "earnings_transcript"
        )
        candidate = transcript.retrieval_candidates[0]
        self.assertEqual(candidate.provider, "")
        self.assertEqual(candidate.discovery_hint_kind, "")
        self.assertEqual(candidate.discovery_hint_value, "")
        self.assertEqual(candidate.discovery_hints[0], hint)

        generic = SourceProfile(
            "source-hoya-transcript", "HOYA transcripts", True,
            "earnings_transcript",
            {
                "mode": "discovery",
                "discovery_class": candidate.discovery_class,
                "discovery_hints": list(candidate.discovery_hints),
            },
            {"firm_id": "hoya", "artifact_id": "earnings_transcript"},
        )
        trials = TranscriptAcquisitionOrchestrator(
            None, "earnings-call-transcript"
        ).plan(generic, TranscriptAcquisitionTarget("hoya"))
        self.assertEqual(trials[0].provider, "")
        self.assertEqual(trials[0].seed_kind, "configured_fallback")
        self.assertEqual(trials[0].starting_seed, hint)
        adapter_trials = EarningsTranscriptPullAdapter(
            policies(), transport=Transport({})
        ).acquisition_trials(generic)
        self.assertEqual(adapter_trials[0].provider, "")
        self.assertEqual(adapter_trials[0].starting_seed, hint)

    def test_provider_backed_configuration_does_not_route_generic_hints(self) -> None:
        quote_hint = "https://stockanalysis.com/quote/tyo/7741/transcripts/"
        configured = profile()
        configured.configuration["discovery_hints"] = [quote_hint]
        trials = TranscriptAcquisitionOrchestrator(
            None, "earnings-call-transcript"
        ).plan(configured, TranscriptAcquisitionTarget("oracle"))
        self.assertEqual(len(trials), 1)
        self.assertEqual(trials[0].provider, "stockanalysis")
        self.assertEqual(trials[0].seed_kind, "provider_identifier")
        self.assertEqual(trials[0].starting_seed, "ORCL")
        self.assertNotIn(quote_hint, trials[0].starting_seeds)

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

    def test_provider_trials_share_the_run_candidate_evaluation_budget(self) -> None:
        learned_url = (
            "https://stockanalysis.com/stocks/orcl/transcripts/learned-q3-2026/"
        )

        class Repository:
            @staticmethod
            def discovery_anchors(*_args: object) -> tuple[dict[str, object], ...]:
                return ({"provider": "stockanalysis", "requested_url": learned_url},)

        adapter = EarningsTranscriptPullAdapter(
            policies(max_candidate_evaluations=1),
            transport=Transport({
                ARCHIVE_URL: response(ARCHIVE_URL, ARCHIVE),
                DOCUMENT_URL: response(DOCUMENT_URL, DOCUMENT),
            }),
            repository=Repository(),  # type: ignore[arg-type]
            clock=lambda: "2026-08-04T00:00:00+00:00",
        )
        trials = adapter.acquisition_trials(profile())
        configured = adapter.discover_trial(profile(), trials[0])
        self.assertEqual(configured.diagnostics["candidate_evaluated_count"], 0)
        adapter.retrieve(profile(), configured.candidates[0])
        learned = adapter.discover_trial(profile(), trials[1])
        self.assertEqual(len(configured.candidates), 1)
        self.assertEqual(learned.candidates, ())
        self.assertEqual(learned.diagnostics["run_unique_candidate_count"], 1)
        self.assertEqual(learned.diagnostics["exhausted_budget"],
                         "")

    def test_wdc_configured_acquisition_succeeds_before_learned_duplicate(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            firms = FirmRepository.initialize(root / "firms")
            firms.create(FirmDraft(
                "western-digital", "Western Digital Corporation", "2026-01-01",
                status=FirmStatus.ACTIVE,
            ))
            repository = AcquisitionRepository(root / "acquisition")
            configured = wdc_profile()
            repository.register_source(configured)
            q3_without_related = WDC_DOCUMENT.replace(
                b'<aside id="related-artifacts">',
                b'<aside id="provider-summary" data-provider-summary="true">',
            ).replace(b"data-related-kind", b"data-untrusted-kind")
            transport = Transport({
                WDC_ARCHIVE_URL: response(WDC_ARCHIVE_URL, WDC_ARCHIVE),
                WDC_UNKNOWN_URL: response(
                    WDC_UNKNOWN_URL,
                    wdc_document_with_date("2026-06-03", "June 3, 2026"),
                ),
                WDC_DOCUMENT_URL: response(WDC_DOCUMENT_URL, q3_without_related),
                WDC_PROVIDER_CLASSIFIED_URL: response(
                    WDC_PROVIDER_CLASSIFIED_URL,
                    wdc_document_with_date("2026-05-18", "May 18, 2026"),
                ),
                WDC_INVESTOR_DAY_URL: response(
                    WDC_INVESTOR_DAY_URL,
                    wdc_document_with_date("2026-05-05", "May 5, 2026"),
                ),
            })
            adapter = EarningsTranscriptPullAdapter(
                policies(max_candidate_evaluations=10),
                transport=transport,
                repository=repository,
                clock=lambda: "2026-08-05T00:00:00+00:00",
            ).with_selection(
                TranscriptAcquisitionSelection.first_in_date_range(
                    date(2026, 4, 1), date(2026, 5, 1)
                )
            )
            with patch.object(
                repository,
                "discovery_anchors",
                return_value=({
                    "provider": "stockanalysis",
                    "requested_url": WDC_UNKNOWN_URL,
                },),
            ):
                result = AcquisitionEngine(
                    repository,
                    AdapterRegistry((adapter,)),
                    lambda: "2026-08-05T00:00:00+00:00",
                ).run_source(configured.source_id, "task064-wdc-correction")
        self.assertEqual(result.durable_acquisitions, 1)
        self.assertEqual(transport.requests, [
            WDC_ARCHIVE_URL,
            WDC_UNKNOWN_URL,
            WDC_DOCUMENT_URL,
            WDC_PROVIDER_CLASSIFIED_URL,
            WDC_INVESTOR_DAY_URL,
        ])
        rendered = json.dumps(result.diagnostics, sort_keys=True)
        self.assertIn('"evaluated_event_disposition": "unknown"', rendered)
        self.assertIn('"validated_event_date": "2026-04-30"', rendered)
        self.assertIn('"candidate_evaluated_count": 4', rendered)
        self.assertNotIn('"related_artifact_count": 3', rendered)

    def test_amazon_configured_trial_reuses_retained_artifact_before_learned_seed(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            firms = FirmRepository.initialize(root / "firms")
            firms.create(FirmDraft(
                "amazon", "Amazon.com, Inc.", "2026-01-01",
                status=FirmStatus.ACTIVE,
            ))
            repository = AcquisitionRepository(root / "acquisition")
            configured = amazon_profile()
            repository.register_source(configured)
            retained_candidate, retained_result, artifact_id = retain_amazon_transcript(
                repository
            )
            transport = Transport({
                AMZN_ARCHIVE_URL: response(AMZN_ARCHIVE_URL, AMZN_ARCHIVE),
            })
            adapter = EarningsTranscriptPullAdapter(
                policies(max_candidate_evaluations=1),
                transport=transport,
                repository=repository,
                clock=lambda: "2026-08-05T00:01:00+00:00",
            )
            result = AcquisitionEngine(
                repository,
                AdapterRegistry((adapter,)),
                lambda: "2026-08-05T00:01:00+00:00",
            ).run_source(configured.source_id, "task064-amazon-retained")
            hydrated = repository.retained_retrieval(CandidateDocument(
                retained_candidate.candidate_id,
                configured.source_id,
                retained_candidate.document_id,
                retained_candidate.provenance,
            ))
        self.assertIsNotNone(hydrated)
        assert hydrated is not None
        self.assertEqual(hydrated.artifact_id, artifact_id)
        self.assertEqual(hydrated.retrieval.content, retained_result.content)
        self.assertEqual(hydrated.retrieval.trusted_event_date, date(2026, 7, 30))
        self.assertEqual(hydrated.retrieval.speaker_turn_observations, ())
        self.assertEqual(
            hydrated.retrieval.transcript_metadata_observation.trusted_event_date,
            date(2026, 7, 30),
        )
        self.assertEqual(
            hydrated.retrieval.provider_identifiers,
            {"provider": "stockanalysis", "provider_identifier": "amzn"},
        )
        self.assertEqual(result.status.value, "complete")
        self.assertEqual(result.unchanged, 1)
        self.assertEqual(result.retrieval_attempts, 0)
        self.assertEqual(transport.requests, [AMZN_ARCHIVE_URL])
        trials = [item for item in result.diagnostics if "trial_id" in item]
        self.assertEqual(len(trials), 1)
        self.assertEqual(trials[0]["trial_outcome"], "validated_success")
        self.assertEqual(trials[0]["validation_outcome"], "validated")
        self.assertEqual(trials[0]["candidate_evaluated_count"], 0)
        self.assertEqual(trials[0]["retained_artifact_reuse_count"], 1)
        self.assertEqual(trials[0]["retained_trusted_event_date"], "2026-07-30")
        self.assertEqual(trials[0]["retained_artifact_id"], artifact_id)

    def test_nonqualifying_retained_amazon_occurrences_remain_provenance_only(
        self,
    ) -> None:
        without_date = AMZN_DOCUMENT.replace(
            b' data-event-date="July 30, 2026"', b""
        ).replace(
            b'<time datetime="2026-07-30">July 30, 2026</time>', b""
        )
        one_candidate_archive = AMZN_ARCHIVE.replace(
            b'    <li class="rounded-lg border border-sharp bg-contrast">\n'
            b'      <a href="/stocks/amzn/transcripts/650000-questionable-event/">'
            b'Questionable provider event</a>\n    </li>\n',
            b"",
        )
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            FirmRepository.initialize(root / "firms").create(FirmDraft(
                "amazon", "Amazon.com, Inc.", "2026-01-01",
                status=FirmStatus.ACTIVE,
            ))
            repository = AcquisitionRepository(root / "acquisition")
            configured = amazon_profile()
            repository.register_source(configured)
            retain_amazon_transcript(repository, without_date)
            transport = Transport({
                AMZN_ARCHIVE_URL: response(AMZN_ARCHIVE_URL, one_candidate_archive),
            })
            adapter = EarningsTranscriptPullAdapter(
                policies(max_candidate_evaluations=1),
                transport=transport,
                repository=repository,
                clock=lambda: "2026-08-05T00:01:00+00:00",
            )
            result = AcquisitionEngine(
                repository, AdapterRegistry((adapter,)),
                lambda: "2026-08-05T00:01:00+00:00",
            ).run_source(configured.source_id, "task064-amazon-nonqualifying")
        self.assertEqual(result.durable_acquisitions, 0)
        self.assertEqual(result.retrieval_attempts, 0)
        self.assertEqual(result.duplicates, 1)
        self.assertEqual(transport.requests, [AMZN_ARCHIVE_URL])
        trials = [item for item in result.diagnostics if "trial_id" in item]
        self.assertEqual(len(trials), 2)
        self.assertTrue(all(item["candidate_evaluated_count"] == 0 for item in trials))
        rendered = json.dumps(result.diagnostics, sort_keys=True)
        self.assertIn('"duplicate_occurrence_count": 1', rendered)
        self.assertIn('"occurrence_count": 2', rendered)
        self.assertNotIn("ambiguous duplicate candidate", rendered)
        self.assertIn("no_qualifying_validated_artifact", rendered)

    def test_tampered_retained_amazon_artifact_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            FirmRepository.initialize(root / "firms").create(FirmDraft(
                "amazon", "Amazon.com, Inc.", "2026-01-01",
                status=FirmStatus.ACTIVE,
            ))
            repository = AcquisitionRepository(root / "acquisition")
            configured = amazon_profile()
            repository.register_source(configured)
            _candidate, _result, artifact_id = retain_amazon_transcript(repository)
            digest = artifact_id.removeprefix("artifact-")
            content_path = repository.content_root / digest[:2] / digest
            content_path.chmod(0o600)
            content_path.write_bytes(b"tampered")
            transport = Transport({
                AMZN_ARCHIVE_URL: response(AMZN_ARCHIVE_URL, AMZN_ARCHIVE),
            })
            result = AcquisitionEngine(
                repository,
                AdapterRegistry((EarningsTranscriptPullAdapter(
                    policies(), transport=transport, repository=repository,
                    clock=lambda: "2026-08-05T00:01:00+00:00",
                ),)),
                lambda: "2026-08-05T00:01:00+00:00",
            ).run_source(configured.source_id, "task064-amazon-tampered")
        self.assertEqual(result.status.value, "failed")
        self.assertEqual(transport.requests, [AMZN_ARCHIVE_URL])
        self.assertIn("repository_integrity", json.dumps(result.diagnostics))

    def test_retained_reuse_does_not_weaken_immutable_artifact_conflicts(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            FirmRepository.initialize(root / "firms").create(FirmDraft(
                "amazon", "Amazon.com, Inc.", "2026-01-01",
                status=FirmStatus.ACTIVE,
            ))
            repository = AcquisitionRepository(root / "acquisition")
            configured = amazon_profile()
            repository.register_source(configured)
            candidate, result, _artifact_id = retain_amazon_transcript(repository)
            repository_candidate = CandidateDocument(
                candidate.candidate_id,
                configured.source_id,
                candidate.document_id,
                candidate.provenance,
            )
            with self.assertRaisesRegex(ConflictError, "immutable artifact already differs"):
                repository.record_success(
                    "attempt-task064-amazon-media-conflict",
                    repository_candidate,
                    replace(result, media_type="application/json"),
                )

    def test_duplicate_archive_and_learned_occurrences_are_not_ambiguous(self) -> None:
        archive = f'''<!doctype html><ul>
          <li class="rounded-lg border border-sharp bg-contrast">
            <a href="{WDC_UNKNOWN_URL}">Opaque provider event label</a>
          </li></ul>'''.encode()
        artifact = WDC_DOCUMENT.replace(
            WDC_DOCUMENT_URL.encode(), WDC_UNKNOWN_URL.encode()
        ).replace(
            b' data-event-date="April 30, 2026"', b""
        ).replace(
            b'<time datetime="2026-04-30">April 30, 2026</time>', b""
        )
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            firms = FirmRepository.initialize(root / "firms")
            firms.create(FirmDraft(
                "western-digital", "Western Digital Corporation", "2026-01-01",
                status=FirmStatus.ACTIVE,
            ))
            repository = AcquisitionRepository(root / "acquisition")
            configured = wdc_profile()
            repository.register_source(configured)
            adapter = EarningsTranscriptPullAdapter(
                policies(max_candidate_evaluations=2),
                transport=Transport({
                    WDC_ARCHIVE_URL: response(WDC_ARCHIVE_URL, archive),
                    WDC_UNKNOWN_URL: response(WDC_UNKNOWN_URL, artifact),
                }),
                repository=repository,
                clock=lambda: "2026-08-05T00:00:00+00:00",
            )
            with patch.object(
                repository,
                "discovery_anchors",
                return_value=({
                    "provider": "stockanalysis",
                    "requested_url": WDC_UNKNOWN_URL,
                },),
            ):
                result = AcquisitionEngine(
                    repository,
                    AdapterRegistry((adapter,)),
                    lambda: "2026-08-05T00:00:00+00:00",
                ).run_source(configured.source_id, "task064-duplicate-occurrence")
        rendered = json.dumps(result.diagnostics, sort_keys=True)
        self.assertEqual(result.failures, 0)
        self.assertEqual(result.duplicates, 1)
        self.assertIn('"duplicate_occurrence_count": 1', rendered)
        self.assertNotIn("ambiguous duplicate candidate", rendered)

    def test_latest_missing_date_is_neutrally_rejected_by_durable_validation(self) -> None:
        without_date = DOCUMENT.replace(
            b'<time datetime="2026-06-15">June 15, 2026</time>', b""
        )
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            firms = FirmRepository.initialize(root / "firms")
            firms.create(FirmDraft(
                "oracle", "Oracle Corporation", "2026-01-01",
                status=FirmStatus.ACTIVE,
            ))
            repository = AcquisitionRepository(root / "acquisition")
            configured = profile()
            repository.register_source(configured)
            adapter = EarningsTranscriptPullAdapter(
                policies(max_candidate_evaluations=1),
                transport=Transport({
                    ARCHIVE_URL: response(ARCHIVE_URL, ARCHIVE),
                    DOCUMENT_URL: response(DOCUMENT_URL, without_date),
                }),
                repository=repository,
                clock=lambda: "2026-08-04T00:00:00+00:00",
            )
            result = AcquisitionEngine(
                repository, AdapterRegistry((adapter,)),
                lambda: "2026-08-04T00:00:00+00:00",
            ).run_source(configured.source_id, "task064-missing-date")
            self.assertEqual(result.durable_acquisitions, 0)
            self.assertEqual(result.failures, 0)
            self.assertEqual(result.skips, 1)
            self.assertIn("event_date_unavailable", json.dumps(result.diagnostics))
            self.assertNotIn("deferred candidate retrieval lacks validated position",
                             json.dumps(result.diagnostics))

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
