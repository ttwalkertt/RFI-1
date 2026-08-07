"""Focused acceptance evidence for TASK-070 transcript classification."""

from __future__ import annotations

import tempfile
import unittest
from datetime import date
from pathlib import Path

from rfi.acquisition import (
    AcquisitionEngine,
    AcquisitionRepository,
    AdapterRegistry,
    CandidateDocument,
    EarningsTranscriptHttpResponse,
    SourceProfile,
    TranscriptAcquisitionSelection,
    TranscriptAcquisitionTarget,
    TranscriptEventDisposition,
    TranscriptMetadataObservation,
    TranscriptSeed,
)
from rfi.acquisition.providers.stockanalysis import StockAnalysisTranscriptProvider
from rfi.acquisition.transcript_classification import classify_transcript_event
from rfi.artifacts import ArtifactQuery, ArtifactQueryService
from rfi.discovery import (
    DiscoveryPolicy,
    DiscoveryPolicyCatalog,
    EarningsTranscriptPullAdapter,
)
from rfi.firms import FirmRepository
from rfi.firms.contracts import FirmDraft, FirmStatus
from rfi.pull import (
    PullRequest,
    PullRunRepository,
    PullWorkflow,
    RetrievalAdapterCapability,
    RetrievalAdapterRegistration,
    RetrievalAdapterRegistry,
)
from rfi.source_profiles import (
    RetrievalCandidate,
    SourceProfileDraft,
    SourceProfileItem,
    SourceProfileRepository,
    load_canonical_template,
)

ROOT = Path(__file__).resolve().parents[1]
ARCHIVE_URL = "https://stockanalysis.com/stocks/orcl/transcripts/"
Q1_URL = "https://stockanalysis.com/stocks/orcl/transcripts/700001-q1-2026/"
CONFERENCE_URL = (
    "https://stockanalysis.com/stocks/orcl/transcripts/700002-ubs-technology-conference/"
)
Q4_URL = "https://stockanalysis.com/stocks/orcl/transcripts/700003-q4-2025/"
BASE_DOCUMENT = (
    ROOT / "fixtures/transcripts/stockanalysis-orcl-q4-2026.html"
).read_bytes()


def transcript_document(title: str, event_date: str, display_date: str) -> bytes:
    """Retain substantial provider structure while varying trusted event metadata."""
    return (
        BASE_DOCUMENT.replace(
            b"Oracle Q4 2026 Earnings Call Transcript", title.encode()
        )
        .replace(
            b"Oracle Corporation Q4 2026 Earnings Call Transcript", title.encode()
        )
        .replace(b"2026-06-15", event_date.encode())
        .replace(b"June 15, 2026", display_date.encode())
    )


ARCHIVE = b"""<!doctype html><html><body><ul>
<li class="rounded-lg border border-sharp bg-contrast">
<a href="/stocks/orcl/transcripts/700001-q1-2026/">
Oracle Corporation Q1 2026 Earnings Call Transcript</a></li>
<li class="rounded-lg border border-sharp bg-contrast">
<a href="/stocks/orcl/transcripts/700002-ubs-technology-conference/">
UBS Global Technology and AI Conference</a></li>
<li class="rounded-lg border border-sharp bg-contrast">
<a href="/stocks/orcl/transcripts/700003-q4-2025/">
Oracle Corporation Q4 2025 Earnings Call Transcript</a></li>
</ul></body></html>"""

Q1_DOCUMENT = transcript_document(
    "Oracle Corporation Q1 2026 Earnings Call Transcript",
    "2025-09-08",
    "September 8, 2025",
)
CONFERENCE_DOCUMENT = transcript_document(
    "UBS Global Technology and AI Conference",
    "2025-07-10",
    "July 10, 2025",
).replace(b' data-event-type="Earnings Call"', b"")
Q4_DOCUMENT = transcript_document(
    "Oracle Corporation Q4 2025 Earnings Call Transcript",
    "2025-06-03",
    "June 3, 2025",
)


class Transport:
    def __init__(self) -> None:
        self.requests: list[str] = []
        self.responses = {
            ARCHIVE_URL: ARCHIVE,
            Q1_URL: Q1_DOCUMENT,
            CONFERENCE_URL: CONFERENCE_DOCUMENT,
            Q4_URL: Q4_DOCUMENT,
        }

    def get(self, url: str) -> EarningsTranscriptHttpResponse:
        self.requests.append(url)
        return EarningsTranscriptHttpResponse(
            url, 200, "text/html", self.responses[url]
        )


def policies() -> DiscoveryPolicyCatalog:
    return DiscoveryPolicyCatalog(
        {
            "standard": DiscoveryPolicy(
                max_search_queries=0,
                max_results_per_query=1,
                max_unique_eligible_links_per_page=20,
                max_depth=1,
                max_pages=10,
                max_distinct_hosts=2,
                max_bytes=2_000_000,
                max_elapsed_seconds=60,
                max_candidate_evaluations=10,
                max_redirects=2,
            )
        },
        "standard",
    )


def configured_workflow(
    root: Path, transport: Transport
) -> tuple[PullWorkflow, AcquisitionRepository, FirmRepository, object]:
    template = load_canonical_template()
    firms = FirmRepository.initialize(root / "firm-catalog")
    firms.create(FirmDraft(
        "oracle", "Oracle Corporation", "2026-01-01", status=FirmStatus.ACTIVE
    ))
    profiles = SourceProfileRepository.initialize(root / "source-profiles", template)
    profiles.publish(
        SourceProfileDraft(
            "oracle",
            tuple(
                SourceProfileItem(
                    artifact.artifact_id,
                    artifact.artifact_id == "earnings_transcript",
                    (
                        RetrievalCandidate(
                            "discovery",
                            1,
                            discovery_class="standard",
                            provider="stockanalysis",
                            discovery_hint_kind="provider_identifier",
                            discovery_hint_value="ORCL",
                        ),
                    )
                    if artifact.artifact_id == "earnings_transcript" else (),
                )
                for artifact in template.artifacts
            ),
        ),
        None,
    )
    repository = AcquisitionRepository(root / "acquisition")
    adapter = EarningsTranscriptPullAdapter(
        policies(),
        transport=transport,
        repository=repository,
        clock=lambda: "2026-08-07T12:00:00+00:00",
    )
    registry = RetrievalAdapterRegistry((RetrievalAdapterRegistration(
        RetrievalAdapterCapability(
            adapter.adapter_id, adapter.artifact_ids, adapter.retrieval_modes
        ),
        adapter,
    ),))
    workflow = PullWorkflow(
        firms,
        profiles,
        template,
        repository,
        registry,
        PullRunRepository(root / "pull-workflows"),
        lambda: "2026-08-07T12:00:00+00:00",
        iter(("first", "second")).__next__,
    )
    return workflow, repository, firms, template


class TranscriptClassificationTests(unittest.TestCase):
    def test_deterministic_event_kinds_are_provider_and_firm_neutral(self) -> None:
        cases = {
            "Earnings Call: Q4 2026": ("earnings_transcript", "earnings_call"),
            "Q4 2026 Earnings Conference Call": (
                "earnings_transcript", "earnings_call"
            ),
            "UBS Global Technology and AI Conference": (
                "management_transcript", "conference"
            ),
            "2026 Investor Day": ("management_transcript", "investor_day"),
            "Executive Fireside Chat": ("management_transcript", "fireside_chat"),
            "Annual Analyst Briefing": ("management_transcript", "analyst_event"),
            "Wells Fargo TMT Summit": ("management_transcript", "conference"),
        }
        for title, expected in cases.items():
            with self.subTest(title=title):
                result = classify_transcript_event(TranscriptMetadataObservation(
                    title,
                    date(2026, 1, 1),
                    TranscriptEventDisposition.UNKNOWN,
                ))
                self.assertEqual(
                    (result.canonical_artifact_id, result.event_kind.value), expected
                )

    def test_unknown_substantial_event_fails_closed_for_earnings(self) -> None:
        result = classify_transcript_event(TranscriptMetadataObservation(
            "Management discussion",
            date(2026, 1, 1),
            TranscriptEventDisposition.UNKNOWN,
        ))
        self.assertFalse(result.qualifies_as_earnings)
        self.assertEqual(result.canonical_artifact_id, "management_transcript")
        self.assertEqual(result.basis, "deterministic_fail_closed_unknown")


class ManagementTranscriptRetentionTests(unittest.TestCase):
    def test_range_backfill_retains_conference_outside_earnings_corpus(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            transport = Transport()
            workflow, repository, firms, template = configured_workflow(root, transport)
            selection = TranscriptAcquisitionSelection.first_in_date_range(
                date(2025, 1, 1), date(2025, 12, 31)
            )
            request = PullRequest(("oracle",), False, selection)

            first = workflow.run(request)
            second = workflow.run(request)

            service = ArtifactQueryService(repository, firms, template)
            earnings = service.query(ArtifactQuery(
                firm_ids=("oracle",),
                canonical_artifact_ids=("earnings_transcript",),
            ))
            management = service.query(ArtifactQuery(
                firm_ids=("oracle",),
                canonical_artifact_ids=("management_transcript",),
            ))
            management_detail = service.detail(management.items[0].document_id)
            successes = [
                item for item in repository.history()
                if item.get("outcome") == "success"
            ]
            source = next(iter(repository.sources()))
            integrity = repository.verify_integrity()
            checkpoint = next(iter(repository.checkpoints()["sources"].values()))

        self.assertEqual(first.summary.success, 1)
        self.assertEqual(second.summary.success, 1)
        self.assertEqual(earnings.total_items, 2)
        self.assertEqual(management.total_items, 1)
        self.assertEqual(
            management_detail.observation.diagnostics["transcript_event_kind"],
            "conference",
        )
        self.assertEqual(
            management_detail.observation.diagnostics["observed_event_disposition"],
            "unknown",
        )
        self.assertEqual(
            management_detail.observation.diagnostics[
                "transcript_classification_basis"
            ],
            "deterministic_event_label_non_earnings",
        )
        self.assertIn(CONFERENCE_URL, (
            location.location
            for location in management_detail.observation.provenance_locations
        ))
        self.assertEqual(transport.requests.count(CONFERENCE_URL), 1)
        self.assertEqual(
            sum(
                item.get("canonical_artifact_id") == "management_transcript"
                for item in successes
            ),
            1,
        )
        self.assertEqual(
            source["policy"]["alternate_artifact_ids"], ["management_transcript"]
        )
        self.assertEqual(checkpoint["position"], 2025 * 4 + 3)
        self.assertEqual(integrity["result"], "PASS")

    def test_legacy_earnings_mapping_is_corrected_append_only(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            firms = FirmRepository.initialize(root / "firm-catalog")
            firms.create(FirmDraft(
                "oracle", "Oracle Corporation", "2026-01-01",
                status=FirmStatus.ACTIVE,
            ))
            repository = AcquisitionRepository(root / "acquisition")
            source = SourceProfile(
                "source-oracle-transcripts",
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
                    "alternate_artifact_ids": ["management_transcript"],
                    "retrieval_adapter_id": "earnings-call-transcript",
                },
            )
            repository.register_source(source)
            transport = Transport()
            provider = StockAnalysisTranscriptProvider(
                transport, lambda: "2026-08-07T11:00:00+00:00"
            )
            target = TranscriptAcquisitionTarget("oracle")
            conference = provider.discover(
                source,
                TranscriptSeed(
                    "stockanalysis", "provider_identifier", "ORCL", "configured"
                ),
                target,
            ).candidates[1]
            result = provider.retrieve(source, conference)
            repository_candidate = CandidateDocument(
                conference.candidate_id,
                source.source_id,
                conference.document_id,
                conference.provenance,
            )
            original = repository.record_success(
                "attempt-legacy-conference", repository_candidate, result
            )
            selection = TranscriptAcquisitionSelection.first_in_date_range(
                date(2025, 1, 1), date(2025, 12, 31)
            )
            adapter = EarningsTranscriptPullAdapter(
                policies(),
                transport=transport,
                repository=repository,
                selection=selection,
                clock=lambda: "2026-08-07T12:00:00+00:00",
            )
            AcquisitionEngine(
                repository,
                AdapterRegistry((adapter,)),
                lambda: "2026-08-07T12:00:00+00:00",
            ).run_source(source.source_id, "reclassify")
            history = [
                item for item in repository.history()
                if item.get("document_id") == conference.document_id
                and item.get("outcome") == "success"
            ]
            service = ArtifactQueryService(
                repository, firms, load_canonical_template()
            )
            management = service.query(ArtifactQuery(
                canonical_artifact_ids=("management_transcript",)
            ))

        self.assertEqual(len(history), 2)
        self.assertEqual(
            [item["canonical_artifact_id"] for item in history],
            ["management_transcript", "earnings_transcript"],
        )
        self.assertEqual({item["artifact_id"] for item in history}, {
            original.artifact_id
        })
        self.assertEqual(management.total_items, 1)


if __name__ == "__main__":
    unittest.main()
