"""TASK-047 date-delimited acquisition contract and integration evidence."""

from __future__ import annotations

import tempfile
import unittest
from datetime import date
from pathlib import Path

from rfi.acquisition import (
    AcquisitionRepository,
    CandidateDocument,
    DiscoveryProvenance,
    IntervalAcquisitionFailure,
    IntervalAcquisitionRequest,
    IntervalAcquisitionResult,
    IntervalAcquisitionService,
    IntervalArtifactEnvelope,
    IntervalCoverage,
    RetrievalResult,
    SourceProfile,
)
from rfi.acquisition.contracts import ContractError
from rfi.firms import FirmRepository
from rfi.firms.contracts import FirmDraft, FirmStatus
from rfi.source_profiles import load_canonical_template
from rfi.storage import RepositoryDatabase


class ReferenceIntervalAcquisition:
    """Non-production test double; it performs no discovery, HTTP, or parsing."""

    def __init__(self, artifacts: tuple[IntervalArtifactEnvelope, ...], coverage, failures=()):
        self.artifacts = artifacts
        self.coverage = coverage
        self.failures = failures

    def acquire(self, request: IntervalAcquisitionRequest) -> IntervalAcquisitionResult:
        return IntervalAcquisitionResult(
            tuple(item for item in self.artifacts if request.contains(item.artifact_date)),
            self.failures,
            self.coverage,
        )


class DateDelimitedAcquisitionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.state = Path(self.temporary.name) / "state"
        self.firms = FirmRepository.initialize(self.state / "firm-catalog")
        self.firms.create(
            FirmDraft(
                "example-firm",
                "Example Firm",
                "2026-01-01",
                status=FirmStatus.ACTIVE,
            )
        )
        self.repository = AcquisitionRepository(self.state / "acquisition")
        self.repository.register_source(
            SourceProfile(
                "source-task047",
                "TASK-047 test-only source",
                True,
                "fixture-reader",
                policy={"firm_id": "example-firm", "artifact_id": "press_release"},
            )
        )
        self.service = IntervalAcquisitionService(
            self.firms,
            load_canonical_template(),
            self.repository,
            clock=lambda: "2026-07-29T12:00:00Z",
            identifier_factory=self.identifiers,
        )
        self.sequence = 0

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def identifiers(self) -> str:
        self.sequence += 1
        return f"task047-{self.sequence}"

    def request(self, start: str = "2026-01-01", end: str = "2026-02-01"):
        return IntervalAcquisitionRequest(
            "example-firm", "press_release", date.fromisoformat(start), date.fromisoformat(end)
        )

    def envelope(self, key: str, day: str, content: bytes | None = None):
        return IntervalArtifactEnvelope(
            CandidateDocument(
                f"candidate-{key}",
                "source-task047",
                f"document-{key}",
                DiscoveryProvenance(
                    "2026-07-29T11:00:00Z",
                    "fixture-manifest",
                    metadata={
                        "firm_id": "example-firm",
                        "canonical_artifact_id": "press_release",
                    },
                ),
            ),
            date.fromisoformat(day),
            RetrievalResult(
                content or key.encode(),
                "text/plain",
                "2026-07-29T11:01:00Z",
                "fixture-reader",
            ),
        )

    def test_empty_and_no_qualifying_intervals_are_complete(self) -> None:
        empty = self.request("2026-01-01", "2026-01-01")
        result = ReferenceIntervalAcquisition((), IntervalCoverage.COMPLETE).acquire(empty)
        receipt = self.service.record(empty, result)
        self.assertEqual(receipt.coverage, IntervalCoverage.COMPLETE)
        no_match = ReferenceIntervalAcquisition(
            (self.envelope("later", "2026-02-01"),), IntervalCoverage.COMPLETE
        ).acquire(self.request())
        self.assertEqual(no_match.artifacts, ())
        self.assertEqual(
            self.service.record(self.request(), no_match).coverage,
            IntervalCoverage.COMPLETE,
        )

    def test_single_multi_and_closed_open_boundaries(self) -> None:
        request = self.request()
        source = ReferenceIntervalAcquisition(
            (
                self.envelope("before", "2025-12-31"),
                self.envelope("start", "2026-01-01"),
                self.envelope("middle", "2026-01-15"),
                self.envelope("end", "2026-02-01"),
            ),
            IntervalCoverage.COMPLETE,
        )
        result = source.acquire(request)
        self.assertEqual(
            {item.source_artifact_id for item in result.artifacts},
            {"candidate-start", "candidate-middle"},
        )
        receipt = self.service.record(request, result)
        self.assertEqual(len(receipt.artifacts), 2)
        single = source.acquire(self.request("2026-01-01", "2026-01-02"))
        self.assertEqual(len(single.artifacts), 1)

    def test_coverage_and_structured_failures_remain_truthful(self) -> None:
        failure = IntervalAcquisitionFailure(
            "transport_timeout", "bounded transient retries exhausted", True,
            "candidate-missing", {"attempts": 3},
        )
        with self.assertRaisesRegex(ContractError, "complete coverage"):
            IntervalAcquisitionResult((), (failure,), IntervalCoverage.COMPLETE)
        incomplete = self.service.record(
            self.request(), IntervalAcquisitionResult((), (failure,), IntervalCoverage.INCOMPLETE)
        )
        indeterminate = self.service.record(
            self.request(), IntervalAcquisitionResult((), (), IntervalCoverage.INDETERMINATE)
        )
        self.assertEqual(incomplete.coverage, IntervalCoverage.INCOMPLETE)
        self.assertEqual(indeterminate.coverage, IntervalCoverage.INDETERMINATE)
        self.assertEqual(
            [item["coverage"] for item in self.repository.interval_history()],
            ["incomplete", "indeterminate"],
        )

    def test_incomplete_successes_are_retained_and_later_run_fills_hole(self) -> None:
        first_artifact = self.envelope("first", "2026-01-05")
        missing = IntervalAcquisitionFailure("not_found", "candidate unavailable", False, "second")
        first = self.service.record(
            self.request(),
            IntervalAcquisitionResult((first_artifact,), (missing,), IntervalCoverage.INCOMPLETE),
        )
        self.assertEqual(len(first.artifacts), 1)
        second_artifact = self.envelope("second", "2026-01-20")
        recovered = self.service.record(
            self.request(),
            IntervalAcquisitionResult(
                (first_artifact, second_artifact), (), IntervalCoverage.COMPLETE
            ),
        )
        self.assertEqual(len(recovered.artifacts), 2)
        self.assertFalse(recovered.artifacts[0].artifact_created)
        self.assertEqual(len(self.repository.artifact_metadata()), 2)
        self.assertEqual(len(self.repository.observations()), 3)
        self.assertEqual(
            [item["coverage"] for item in self.repository.interval_history()],
            ["incomplete", "complete"],
        )
        self.assertEqual(self.repository.verify_integrity()["result"], "PASS")

    def test_application_uses_canonical_firm_artifact_and_source_policy(self) -> None:
        with self.assertRaisesRegex(ContractError, "unknown canonical artifact type"):
            self.service.record(
                IntervalAcquisitionRequest(
                    "example-firm", "invented_type", date(2026, 1, 1), date(2026, 2, 1)
                ),
                IntervalAcquisitionResult((), (), IntervalCoverage.COMPLETE),
            )
        outside = self.envelope("outside", "2026-02-01")
        with self.assertRaisesRegex(ContractError, "outside"):
            self.service.record(
                self.request(), IntervalAcquisitionResult((outside,), (), IntervalCoverage.COMPLETE)
            )

    def test_schema_12_migrates_additive_interval_history(self) -> None:
        database = RepositoryDatabase.open(self.state)
        with database.connect() as connection:
            connection.execute("DROP TABLE interval_acquisition_artifacts")
            connection.execute("DROP TABLE interval_acquisition_outcomes")
            connection.execute(
                "UPDATE schema_metadata SET schema_version=12 WHERE singleton=1"
            )
        migrated = RepositoryDatabase.open(self.state)
        self.assertEqual(migrated.validate()["schema_version"], 13)
        with migrated.connect(read_only=True) as connection:
            tables = {
                str(row[0])
                for row in connection.execute(
                    "SELECT name FROM sqlite_schema WHERE type='table'"
                )
            }
        self.assertIn("interval_acquisition_outcomes", tables)
        self.assertIn("interval_acquisition_artifacts", tables)


if __name__ == "__main__":
    unittest.main()
