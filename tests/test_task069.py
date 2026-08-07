"""Focused acceptance evidence for TASK-069 public transcript selection."""

from __future__ import annotations

import io
import json
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from datetime import date
from pathlib import Path
from unittest.mock import Mock, patch

from rfi.acquisition import (
    AcquisitionRepository,
    DiscoveryPage,
    EarningsTranscriptHttpResponse,
    TranscriptAcquisitionSelection,
    TranscriptSelectionMode,
)
from rfi.cli import main
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
    PullStatus,
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
Q4_URL = "https://stockanalysis.com/stocks/orcl/transcripts/592465-q4-2026/"
Q3_URL = "https://stockanalysis.com/stocks/orcl/transcripts/581200-q3-2026/"
Q2_URL = "https://stockanalysis.com/stocks/orcl/transcripts/570100-q2-2026/"
Q1_URL = "https://stockanalysis.com/stocks/orcl/transcripts/560100-q1-2026/"
Q4_2025_URL = "https://stockanalysis.com/stocks/orcl/transcripts/550100-q4-2025/"
ARCHIVE = (ROOT / "fixtures/transcripts/stockanalysis-orcl-archive.html").read_bytes()
ARCHIVE = ARCHIVE.replace(
    b"  </ul>",
    b'''    <li class="rounded-lg border border-sharp bg-contrast">
      <a href="/stocks/orcl/transcripts/570100-q2-2026/">
        Oracle Corporation (ORCL) Q2 2026 Earnings Call Transcript</a>
    </li>
    <li class="rounded-lg border border-sharp bg-contrast">
      <a href="/stocks/orcl/transcripts/560100-q1-2026/">
        Oracle Corporation (ORCL) Q1 2026 Earnings Call Transcript</a>
    </li>
    <li class="rounded-lg border border-sharp bg-contrast">
      <a href="/stocks/orcl/transcripts/550100-q4-2025/">
        Oracle Corporation (ORCL) Q4 2025 Earnings Call Transcript</a>
    </li>
  </ul>''',
)
Q4_DOCUMENT = (
    ROOT / "fixtures/transcripts/stockanalysis-orcl-q4-2026.html"
).read_bytes()


def transcript_document(
    period: str, event_date: str, display_date: str, period_words: str
) -> bytes:
    return (
        Q4_DOCUMENT.replace(b"Q4 2026", period.encode())
        .replace(b"2026-06-15", event_date.encode())
        .replace(b"June 15, 2026", display_date.encode())
        .replace(b"fourth quarter", period_words.encode())
        .replace(b"q4-2026", period.casefold().replace(" ", "-").encode())
    )


Q3_DOCUMENT = transcript_document("Q3 2026", "2026-03-10", "March 10, 2026", "third quarter")
Q2_DOCUMENT = transcript_document("Q2 2026", "2025-12-09", "December 9, 2025", "second quarter")
Q1_DOCUMENT = transcript_document("Q1 2026", "2025-09-08", "September 8, 2025", "first quarter")
Q4_2025_DOCUMENT = transcript_document(
    "Q4 2025", "2025-06-03", "June 3, 2025", "fourth quarter"
)


class Transport:
    """Deterministic StockAnalysis transport with request accounting."""

    def __init__(self) -> None:
        self.requests: list[str] = []
        self.responses = {
            ARCHIVE_URL: EarningsTranscriptHttpResponse(
                ARCHIVE_URL, 200, "text/html", ARCHIVE
            ),
            Q4_URL: EarningsTranscriptHttpResponse(
                Q4_URL, 200, "text/html", Q4_DOCUMENT
            ),
            Q3_URL: EarningsTranscriptHttpResponse(
                Q3_URL, 200, "text/html", Q3_DOCUMENT
            ),
            Q2_URL: EarningsTranscriptHttpResponse(
                Q2_URL, 200, "text/html", Q2_DOCUMENT
            ),
            Q1_URL: EarningsTranscriptHttpResponse(
                Q1_URL, 200, "text/html", Q1_DOCUMENT
            ),
            Q4_2025_URL: EarningsTranscriptHttpResponse(
                Q4_2025_URL, 200, "text/html", Q4_2025_DOCUMENT
            ),
        }

    def get(self, url: str) -> EarningsTranscriptHttpResponse:
        self.requests.append(url)
        return self.responses[url]


class SelectionCapturingAdapter:
    """Provider-neutral seam proving the typed selection reaches an adapter."""

    mechanism = "earnings_transcript"

    def __init__(self) -> None:
        self.selections: list[TranscriptAcquisitionSelection] = []

    def with_selection(
        self, selection: TranscriptAcquisitionSelection
    ) -> SelectionCapturingAdapter:
        self.selections.append(selection)
        return self

    def discover(self, _profile: object, _continuation: object) -> DiscoveryPage:
        return DiscoveryPage((), None, {"coverage": "complete"})

    def retrieve(self, _profile: object, _candidate: object) -> object:
        raise AssertionError("empty discovery must not retrieve")


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


def configured_state(root: Path) -> tuple[
    FirmRepository, SourceProfileRepository, object, AcquisitionRepository
]:
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
                    if artifact.artifact_id == "earnings_transcript"
                    else (),
                )
                for artifact in template.artifacts
            ),
        ),
        None,
    )
    return firms, profiles, template, AcquisitionRepository(root / "acquisition")


def workflow_with_adapter(
    root: Path, adapter: object, identifiers: object
) -> tuple[PullWorkflow, AcquisitionRepository]:
    firms, profiles, template, repository = configured_state(root)
    registry = RetrievalAdapterRegistry((RetrievalAdapterRegistration(
        RetrievalAdapterCapability(
            "earnings-call-transcript", ("earnings_transcript",), ("discovery",)
        ),
        adapter,  # type: ignore[arg-type]
    ),))
    workflow = PullWorkflow(
        firms,
        profiles,
        template,  # type: ignore[arg-type]
        repository,
        registry,
        PullRunRepository(root / "pull-workflows"),
        lambda: "2026-08-07T12:00:00+00:00",
        identifiers,  # type: ignore[arg-type]
    )
    return workflow, repository


class TranscriptSelectionCliTests(unittest.TestCase):
    def invoke(self, *arguments: str) -> tuple[int, Mock, Mock, str, str]:
        workflow = Mock()
        workflow.run.return_value = Mock(
            status=PullStatus.COMPLETED, __dataclass_fields__={}
        )
        stdout = io.StringIO()
        stderr = io.StringIO()
        with patch("rfi.cli._open_state") as opened, patch(
            "rfi.cli.create_pull_workflow", return_value=workflow
        ), patch("rfi.cli.asdict", return_value={"status": "completed"}), \
                redirect_stdout(stdout), redirect_stderr(stderr):
            code = main(("pull", "--firm", "oracle", *arguments))
        return code, workflow, opened, stdout.getvalue(), stderr.getvalue()

    def test_omitted_selection_preserves_latest_pull_request(self) -> None:
        code, workflow, opened, stdout, stderr = self.invoke()

        self.assertEqual(code, 0)
        self.assertEqual(stderr, "")
        self.assertEqual(json.loads(stdout), {"status": "completed"})
        opened.assert_called_once()
        workflow.run.assert_called_once_with(PullRequest(("oracle",)))

    def test_valid_range_translates_to_existing_typed_selection(self) -> None:
        code, workflow, opened, _stdout, stderr = self.invoke(
            "--selection", "first_in_date_range",
            "--start-date", "2024-08-07",
            "--end-date", "2026-08-07",
        )
        expected = TranscriptAcquisitionSelection.first_in_date_range(
            date(2024, 8, 7), date(2026, 8, 7)
        )

        self.assertEqual(code, 0)
        self.assertEqual(stderr, "")
        opened.assert_called_once()
        workflow.run.assert_called_once_with(PullRequest(("oracle",), False, expected))

    def test_invalid_combinations_fail_before_state_or_acquisition(self) -> None:
        cases = (
            ("--selection", "first_in_date_range", "--end-date", "2026-08-07"),
            ("--selection", "first_in_date_range", "--start-date", "2024-08-07"),
            (
                "--selection", "first_in_date_range",
                "--start-date", "2026-08-08", "--end-date", "2026-08-07",
            ),
            ("--selection", "latest", "--start-date", "2024-08-07"),
        )
        for arguments in cases:
            with self.subTest(arguments=arguments):
                code, workflow, opened, _stdout, stderr = self.invoke(*arguments)
                self.assertEqual(code, 2)
                self.assertIn("rfi: error:", stderr)
                opened.assert_not_called()
                workflow.run.assert_not_called()

    def test_malformed_date_and_unknown_selection_fail_in_argument_parsing(self) -> None:
        cases = (
            (
                "--selection", "first_in_date_range",
                "--start-date", "August-7-2024", "--end-date", "2026-08-07",
            ),
            ("--selection", "earliest"),
        )
        for arguments in cases:
            stderr = io.StringIO()
            with self.subTest(arguments=arguments), patch(
                "rfi.cli.pull_sources"
            ) as acquisition, redirect_stderr(stderr), self.assertRaises(SystemExit) as raised:
                main(("pull", "--firm", "oracle", *arguments))
            self.assertEqual(raised.exception.code, 2)
            self.assertIn("error:", stderr.getvalue())
            acquisition.assert_not_called()


class TranscriptSelectionWorkflowTests(unittest.TestCase):
    def test_durable_pull_restores_and_passes_exact_typed_selection(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            adapter = SelectionCapturingAdapter()
            workflow, _repository = workflow_with_adapter(
                Path(directory), adapter, iter(("capture",)).__next__
            )
            selection = TranscriptAcquisitionSelection.first_in_date_range(
                date(2024, 8, 7), date(2026, 8, 7)
            )
            run_id = workflow.initiate(PullRequest(("oracle",), False, selection))
            durable = workflow.results(run_id)["request"]["transcript_selection"]
            result = workflow.execute(run_id)

        self.assertEqual(durable, selection.to_dict())
        self.assertEqual(result.status, PullStatus.COMPLETED)
        self.assertEqual(adapter.selections, [selection])
        self.assertIsInstance(adapter.selections[0], TranscriptAcquisitionSelection)

    def test_retained_newest_does_not_block_three_repeated_public_range_pulls(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            transport = Transport()
            root = Path(directory)
            firms, profiles, template, repository = configured_state(root)
            adapter = EarningsTranscriptPullAdapter(
                policies(),
                transport=transport,
                repository=repository,
                clock=lambda: "2026-08-07T12:00:00+00:00",
            )
            workflow = PullWorkflow(
                firms,
                profiles,
                template,  # type: ignore[arg-type]
                repository,
                RetrievalAdapterRegistry((RetrievalAdapterRegistration(
                    RetrievalAdapterCapability(
                        adapter.adapter_id, adapter.artifact_ids, adapter.retrieval_modes
                    ),
                    adapter,
                ),)),
                PullRunRepository(root / "pull-workflows"),
                lambda: "2026-08-07T12:00:00+00:00",
                iter(("latest", "first", "second", "third")).__next__,
            )
            selection = TranscriptAcquisitionSelection.first_in_date_range(
                date(2025, 6, 3), date(2026, 6, 15)
            )
            request = PullRequest(("oracle",), False, selection)

            latest = workflow.run(PullRequest(("oracle",)))
            first = workflow.run(request)
            second = workflow.run(request)
            third = workflow.run(request)
            success_records = tuple(
                item for item in repository.history() if item.get("outcome") == "success"
            )
            checkpoint = next(iter(repository.checkpoints()["sources"].values()))

        self.assertEqual(latest.summary.success, 1)
        self.assertEqual(first.summary.success, 1)
        self.assertEqual(second.summary.success, 1)
        self.assertEqual(third.summary.success, 1)
        selected_dates = []
        learned_direct_trials = []
        for result in (first, second, third):
            diagnostics = result.firms[0].artifacts[0].attempts[0].details
            assert diagnostics is not None
            engine_diagnostics = diagnostics["engine_diagnostics"]
            terminal = next(
                item for item in engine_diagnostics
                if item.get("terminal_selection_outcome") == "selected"
            )
            selected_dates.append(terminal["selected_validated_event_date"])
            self.assertGreaterEqual(terminal["retained_qualified_candidate_count"], 1)
            learned_direct_trials.extend(
                item for item in engine_diagnostics
                if item.get("provider_surface") == "direct_document"
            )
        self.assertEqual(
            selected_dates, ["2025-06-03", "2025-09-08", "2025-12-09"]
        )
        self.assertEqual(
            {
                item["candidate"]["provenance"]["metadata"]["requested_url"]
                for item in success_records
            },
            {Q4_URL, Q4_2025_URL, Q1_URL, Q2_URL},
        )
        self.assertEqual(len({item["artifact_id"] for item in success_records}), 4)
        self.assertEqual(transport.requests.count(Q4_URL), 1)
        self.assertTrue(learned_direct_trials)
        self.assertTrue(
            all(item["candidate_evaluated_count"] == 0 for item in learned_direct_trials)
        )
        self.assertNotIn("2026-06-15", selected_dates)
        self.assertEqual(checkpoint["position"], 2026 * 4 + 2)


if __name__ == "__main__":
    unittest.main()
