"""Focused acceptance coverage for the authoritative SEC workflow."""

from __future__ import annotations

import json
import tempfile
import unittest
from datetime import timedelta
from pathlib import Path

from rfi.acquisition import (
    AcquisitionRepository, SecForm10KAdapter, SecHttpResponse, SecProviderClient,
)
from rfi.firms import FirmRepository, sample_firms
from rfi.sec import (
    FirmIdentifierSecResolver, SecApplicability, SecRepository, SecResolution,
    SecRetrievalWorkflow, SecSourceKnowledge, SecWorkflowOutcome, SecWorkflowState,
)

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "fixtures/sec-10k"


def clock() -> str:
    return "2026-07-26T12:00:00+00:00"


class Transport:
    def __init__(self, submissions: bytes | None = None) -> None:
        self.submissions = submissions or (FIXTURES / "CIK0001137789.json").read_bytes()
        self.requests = 0

    def request(self, url: str, headers: dict[str, str], timeout_seconds: float,
                maximum_bytes: int) -> SecHttpResponse:
        self.requests += 1
        content = (self.submissions if "/submissions/" in url
                   else (FIXTURES / "stx-2025-10k.htm").read_bytes())
        media = "application/json" if "/submissions/" in url else "text/html"
        return SecHttpResponse(200, {"content-type": media,
                                    "content-length": str(len(content))}, content, url)


class FixedResolver:
    def __init__(self, resolution: SecResolution) -> None:
        self.resolution = resolution

    def resolve(self, firm: object, verified_at: str) -> SecResolution:
        return self.resolution

    def validate(self, firm: object, source: object, verified_at: str) -> SecResolution:
        return self.resolution


class SecWorkflowTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.firms = FirmRepository.initialize(self.root / "firm-catalog")
        self.firms.create(sample_firms()[0])
        self.repository = SecRepository(self.root)
        self.acquisition = AcquisitionRepository(self.root / "acquisition")
        self.transport = Transport()
        self.provider = SecProviderClient(
            lambda: "RFI-1 task036@example.invalid", self.transport,
            minimum_request_interval_seconds=0.1, monotonic=lambda: 1.0,
            sleeper=lambda _seconds: None,
        )
        self.resolver = FirmIdentifierSecResolver(self.provider)
        self.adapter = SecForm10KAdapter(self.provider, clock)
        self.ids = iter(f"run{i}" for i in range(20))

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def workflow(self, resolver: object | None = None, ttl: timedelta = timedelta(days=30)
                 ) -> SecRetrievalWorkflow:
        return SecRetrievalWorkflow(
            self.firms, self.repository, self.acquisition,
            resolver or self.resolver, self.adapter, clock, self.ids.__next__, ttl,
        )

    def direct_source(self, verified_at: str = "2026-07-26T12:00:00+00:00",
                      cik: str = "1137789") -> SecSourceKnowledge:
        return SecSourceKnowledge(
            "seagate", SecApplicability.DIRECT, "Seagate Technology plc", cik,
            "domestic_periodic", "verified", verified_at,
        )

    def test_missing_source_bootstraps_retrieves_and_repeat_is_idempotent(self) -> None:
        first = self.workflow().run("seagate")
        self.assertEqual(first.outcome, SecWorkflowOutcome.SUCCESS_WITH_SOURCE_BOOTSTRAP)
        saved = self.repository.source("seagate")
        self.assertIsNotNone(saved)
        self.assertEqual(saved.cik, "1137789")  # type: ignore[union-attr]
        self.assertEqual(len(first.artifact_ids), 1)
        second = self.workflow().run("seagate")
        self.assertEqual(second.outcome, SecWorkflowOutcome.SUCCESS)
        self.assertEqual(second.artifact_ids, first.artifact_ids)
        self.assertEqual(len(self.acquisition.artifact_metadata()), 1)
        self.assertEqual(self.acquisition.verify_integrity()["result"], "PASS")

    def test_verified_source_is_used_without_resolution(self) -> None:
        self.repository.persist_source(self.direct_source(), None)
        refusing = FixedResolver(SecResolution(None, (), "resolver must not run"))
        result = self.workflow(refusing).run("seagate")
        self.assertEqual(result.outcome, SecWorkflowOutcome.SUCCESS)
        self.assertFalse(result.source_refreshed)

    def test_stale_source_refreshes_metadata_without_identity_change(self) -> None:
        old = self.direct_source("2025-01-01T00:00:00+00:00")
        self.repository.persist_source(old, None)
        refreshed = self.direct_source()
        result = self.workflow(FixedResolver(SecResolution(refreshed))).run("seagate")
        self.assertEqual(result.outcome, SecWorkflowOutcome.SUCCESS)
        self.assertTrue(result.source_refreshed)
        saved = self.repository.source("seagate")
        self.assertIsNotNone(saved)
        self.assertEqual(saved.verified_at, clock())  # type: ignore[union-attr]

    def test_conflicting_cik_fails_closed_before_ingestion(self) -> None:
        old = self.direct_source("2025-01-01T00:00:00+00:00")
        self.repository.persist_source(old, None)
        conflict = self.direct_source(cik="106040")
        result = self.workflow(FixedResolver(SecResolution(
            conflict, ("106040",), "authoritative conflict"
        ))).run("seagate")
        self.assertEqual(result.outcome, SecWorkflowOutcome.SOURCE_CONFLICT)
        saved = self.repository.source("seagate")
        self.assertIsNotNone(saved)
        self.assertEqual(saved.cik, "1137789")  # type: ignore[union-attr]
        self.assertEqual(len(self.acquisition.artifact_metadata()), 0)

    def test_ambiguity_is_explicit_and_parent_source_is_supported(self) -> None:
        ambiguous = self.workflow(FixedResolver(SecResolution(
            None, ("1137789", "106040"), "competing CIKs"
        ))).run("seagate")
        self.assertEqual(ambiguous.outcome, SecWorkflowOutcome.SOURCE_AMBIGUITY)
        self.assertIsNone(self.repository.source("seagate"))
        parent = SecSourceKnowledge(
            "seagate", SecApplicability.PARENT, "Parent Issuer", "1137789",
            "domestic_periodic", "verified", clock(), "seagate",
        )
        result = self.workflow(FixedResolver(SecResolution(parent))).run("seagate")
        self.assertEqual(result.outcome, SecWorkflowOutcome.SUCCESS_WITH_SOURCE_BOOTSTRAP)
        self.assertEqual(self.repository.source("seagate").applicability,
                         SecApplicability.PARENT)  # type: ignore[union-attr]

    def test_non_applicable_is_explicit_and_does_not_retrieve(self) -> None:
        source = SecSourceKnowledge(
            "seagate", SecApplicability.NON_APPLICABLE, "", None, "none",
            "verified", clock(),
        )
        self.repository.persist_source(source, None)
        result = self.workflow().run("seagate")
        self.assertEqual(result.outcome, SecWorkflowOutcome.NON_APPLICABLE)
        self.assertEqual(self.transport.requests, 0)

    def test_no_qualifying_filing_is_distinct(self) -> None:
        value = json.loads((FIXTURES / "CIK0001137789.json").read_text())
        value["filings"]["recent"]["form"] = ["8-K"] * len(
            value["filings"]["recent"]["form"]
        )
        transport = Transport(json.dumps(value).encode())
        provider = SecProviderClient(
            lambda: "RFI-1 task036@example.invalid", transport,
            minimum_request_interval_seconds=0.1, monotonic=lambda: 1.0,
            sleeper=lambda _seconds: None,
        )
        self.repository.persist_source(self.direct_source(), None)
        workflow = SecRetrievalWorkflow(
            self.firms, self.repository, self.acquisition,
            FirmIdentifierSecResolver(provider), SecForm10KAdapter(provider, clock),
            clock, self.ids.__next__,
        )
        self.assertEqual(workflow.run("seagate").outcome,
                         SecWorkflowOutcome.NO_QUALIFYING_FILING)

    def test_cancellation_is_durable_bounded_and_inspectable(self) -> None:
        workflow = self.workflow()
        run_id = workflow.initiate("seagate")
        workflow.cancel(run_id)
        result = workflow.execute(run_id)
        self.assertEqual(result.outcome, SecWorkflowOutcome.CANCELLED)
        self.assertEqual(result.current_state, SecWorkflowState.CANCELLED)
        self.assertEqual(result.states,
                         (SecWorkflowState.RECEIVED, SecWorkflowState.CANCELLED))
        self.assertEqual(self.transport.requests, 0)
        self.assertEqual(self.repository.run(run_id)["cancellation_requested"], True)


if __name__ == "__main__":
    unittest.main()
