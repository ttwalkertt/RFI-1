"""Offline acceptance tests for deterministic SEC Form 10-K retrieval."""

from __future__ import annotations

import json
import socket
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

from rfi.acquisition import (
    AcquisitionRepository,
    AdapterFailure,
    DirectUrlAdapter,
    SecFilingMetadata,
    SecForm10KAdapter,
    SecHttpResponse,
    SecProviderClient,
    SecResponseTooLarge,
)
from rfi.acquisition.contracts import SourceProfile
from rfi.firms import FirmRepository, sample_firms
from rfi.pull import (
    ArtifactOutcome,
    PullRequest,
    PullRunRepository,
    PullStatus,
    PullWorkflow,
    RetrievalAdapterCapability,
    RetrievalAdapterError,
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
FIXTURES = ROOT / "fixtures/sec-10k"
USER_AGENT = "RFI-1-task016 fixture-contact@example.invalid"


def fixed_clock() -> str:
    return "2026-07-18T12:00:00Z"


class FakeTime:
    """Deterministic pacing clock that never blocks tests."""

    def __init__(self) -> None:
        self.value = 0.0
        self.sleeps: list[float] = []

    def monotonic(self) -> float:
        return self.value

    def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self.value += seconds


class SecFixtureTransport:
    """Exact production-transport replacement with injectable failures."""

    def __init__(self, submissions: bytes | None = None, primary: bytes | None = None) -> None:
        self.submissions = submissions or (FIXTURES / "CIK0001137789.json").read_bytes()
        self.primary = primary or (FIXTURES / "stx-2025-10k.htm").read_bytes()
        self.responses: list[SecHttpResponse | BaseException] = []
        self.requests: list[dict[str, object]] = []

    def request(
        self,
        url: str,
        headers: dict[str, str],
        timeout_seconds: float,
        maximum_bytes: int,
    ) -> SecHttpResponse:
        self.requests.append(
            {
                "url": url,
                "runtime_identity_present": bool(headers.get("User-Agent")),
                "timeout_seconds": timeout_seconds,
                "maximum_bytes": maximum_bytes,
            }
        )
        if self.responses:
            value = self.responses.pop(0)
            if isinstance(value, BaseException):
                raise value
            return value
        if "/submissions/" in url:
            content = self.submissions
            media_type = "application/json"
        else:
            content = self.primary
            media_type = "text/html; charset=utf-8"
        return SecHttpResponse(
            200,
            {"content-type": media_type, "content-length": str(len(content))},
            content,
            url,
        )


def provider(
    transport: SecFixtureTransport | None = None,
) -> tuple[SecProviderClient, SecFixtureTransport, FakeTime]:
    fixture = transport or SecFixtureTransport()
    timing = FakeTime()
    client = SecProviderClient(
        lambda: USER_AGENT,
        fixture,
        minimum_request_interval_seconds=0.1,
        monotonic=timing.monotonic,
        sleeper=timing.sleep,
    )
    return client, fixture, timing


def registry(adapter: SecForm10KAdapter) -> RetrievalAdapterRegistry:
    return RetrievalAdapterRegistry(
        (
            RetrievalAdapterRegistration(
                RetrievalAdapterCapability("direct-url", (), ("direct_url",)),
                DirectUrlAdapter(fixed_clock),
            ),
            RetrievalAdapterRegistration(
                RetrievalAdapterCapability(
                    adapter.adapter_id,
                    adapter.artifact_ids,
                    adapter.retrieval_modes,
                ),
                adapter,
            ),
        )
    )


def source(locator: str = "CIK:0001137789") -> SourceProfile:
    return SourceProfile(
        "source-task016-seagate-10k",
        "Seagate: Annual report on Form 10-K",
        True,
        "sec-form-10k",
        {
            "mode": "identifier",
            "priority": 1,
            "url": "",
            "locator": locator,
            "preferred_domains": [],
            "discovery_hints": [],
            "expected_media_type": "",
            "parser_hint": "",
            "operator_notes": "",
        },
        {
            "firm_id": "seagate",
            "artifact_id": "sec_10k",
            "source_profile_revision_id": "fixture",
            "retrieval_adapter_id": "sec-form-10k",
            "document_id": "document-seagate-sec_10k",
        },
    )


class CapabilitySelectionTests(unittest.TestCase):
    def test_capability_declaration_and_selection(self) -> None:
        client, _transport, _timing = provider()
        adapter = SecForm10KAdapter(client, fixed_clock)
        adapters = registry(adapter)
        candidate = RetrievalCandidate("identifier", 1, locator="CIK:0001137789")
        selected = adapters.select("sec_10k", candidate)
        self.assertEqual(selected.capability.adapter_id, "sec-form-10k")
        self.assertEqual(
            adapters.registrations()[1],
            {
                "adapter_id": "sec-form-10k",
                "artifact_ids": ["sec_10k"],
                "retrieval_modes": ["identifier"],
                "acquisition_mechanism": "sec-form-10k",
                "implementation": "SecForm10KAdapter",
            },
        )
        with self.assertRaisesRegex(RetrievalAdapterError, "no compatible"):
            adapters.select("sec_10q", candidate)

    def test_distinct_capabilities_may_share_acquisition_mechanism(self) -> None:
        client, _transport, _timing = provider()
        ten_k = SecForm10KAdapter(client, fixed_clock)
        ten_q = type("OtherAdapter", (), {"mechanism": ten_k.mechanism})()
        adapters = RetrievalAdapterRegistry(
            (
                RetrievalAdapterRegistration(
                    RetrievalAdapterCapability("sec-form-10k", ("sec_10k",), ("identifier",)),
                    ten_k,
                ),
                RetrievalAdapterRegistration(
                    RetrievalAdapterCapability("sec-form-10q", ("sec_10q",), ("identifier",)),
                    ten_q,  # type: ignore[arg-type]
                ),
            )
        )
        candidate = RetrievalCandidate("identifier", 1, locator="CIK:0001137789")
        self.assertEqual(
            adapters.select("sec_10k", candidate).capability.adapter_id,
            "sec-form-10k",
        )
        self.assertEqual(
            adapters.select("sec_10q", candidate).capability.adapter_id,
            "sec-form-10q",
        )
        self.assertEqual(
            adapters.acquisition_registry("sec-form-10k").registrations(),
            {ten_k.mechanism: "SecForm10KAdapter"},
        )
        self.assertEqual(
            adapters.acquisition_registry("sec-form-10q").registrations(),
            {ten_k.mechanism: "OtherAdapter"},
        )

    def test_duplicate_adapter_identity_is_rejected(self) -> None:
        first = type("FirstAdapter", (), {"mechanism": "first"})()
        second = type("SecondAdapter", (), {"mechanism": "second"})()
        with self.assertRaisesRegex(RetrievalAdapterError, "already registered"):
            RetrievalAdapterRegistry(
                (
                    RetrievalAdapterRegistration(
                        RetrievalAdapterCapability("same", ("sec_10k",), ("identifier",)),
                        first,  # type: ignore[arg-type]
                    ),
                    RetrievalAdapterRegistration(
                        RetrievalAdapterCapability("same", ("sec_10q",), ("identifier",)),
                        second,  # type: ignore[arg-type]
                    ),
                )
            )

    def test_overlapping_effective_capability_is_rejected(self) -> None:
        first = type("FirstAdapter", (), {"mechanism": "shared"})()
        second = type("SecondAdapter", (), {"mechanism": "shared"})()
        with self.assertRaisesRegex(RetrievalAdapterError, "ambiguous"):
            RetrievalAdapterRegistry(
                (
                    RetrievalAdapterRegistration(
                        RetrievalAdapterCapability("one", ("sec_10k",), ("identifier",)),
                        first,  # type: ignore[arg-type]
                    ),
                    RetrievalAdapterRegistration(
                        RetrievalAdapterCapability("two", ("sec_10k",), ("identifier",)),
                        second,  # type: ignore[arg-type]
                    ),
                )
            )

    def test_selection_is_deterministic_across_registration_order(self) -> None:
        first = type("FirstAdapter", (), {"mechanism": "shared"})()
        second = type("SecondAdapter", (), {"mechanism": "shared"})()
        registrations = (
            RetrievalAdapterRegistration(
                RetrievalAdapterCapability("z-ten-k", ("sec_10k",), ("identifier",)),
                first,  # type: ignore[arg-type]
            ),
            RetrievalAdapterRegistration(
                RetrievalAdapterCapability("a-ten-q", ("sec_10q",), ("identifier",)),
                second,  # type: ignore[arg-type]
            ),
        )
        candidate = RetrievalCandidate("identifier", 1, locator="CIK:0001137789")
        forward = RetrievalAdapterRegistry(registrations)
        reverse = RetrievalAdapterRegistry(tuple(reversed(registrations)))
        self.assertEqual(forward.registrations(), reverse.registrations())
        self.assertEqual(
            forward.select("sec_10k", candidate).capability.adapter_id,
            reverse.select("sec_10k", candidate).capability.adapter_id,
        )


class Form10KPolicyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.client, self.transport, self.timing = provider()
        self.adapter = SecForm10KAdapter(self.client, fixed_clock)

    def test_exact_form_filter_amendment_exclusion_and_primary_mapping(self) -> None:
        page = self.adapter.discover(source(), None)
        candidate = page.candidates[0]
        self.assertEqual(
            candidate.document_id,
            "document-sec-1137789-000113778925000002",
        )
        self.assertEqual(candidate.provenance.metadata["form_type"], "10-K")
        self.assertFalse(candidate.provenance.metadata["amendment"])
        self.assertEqual(
            candidate.provenance.metadata["primary_document"],
            "stx-2025-10k.htm",
        )
        self.assertEqual(page.diagnostics["amendment_records_excluded"], 1)
        result = self.adapter.retrieve(source(), candidate)
        self.assertEqual(result.content, (FIXTURES / "stx-2025-10k.htm").read_bytes())
        self.assertEqual(result.provider_identifiers["sec_accession"], "0001137789-25-000002")
        self.assertIn("stx-2025-10k.htm", str(result.diagnostics["archive_url"]))
        self.assertEqual(len(self.transport.requests), 2)
        self.assertEqual(len(self.timing.sleeps), 1)

    def test_reordered_metadata_and_explicit_accession_tie_break_are_deterministic(self) -> None:
        original = json.loads(self.transport.submissions)
        recent = original["filings"]["recent"]
        order = [3, 2, 0, 1]
        for key, values in recent.items():
            recent[key] = [values[index] for index in order]
        reordered_client, _fixture, _timing = provider(
            SecFixtureTransport(json.dumps(original).encode())
        )
        reordered = SecForm10KAdapter(reordered_client, fixed_clock).discover(source(), None)
        first = self.adapter.discover(source(), None).candidates[0]
        self.assertEqual(reordered.candidates[0].canonical(), first.canonical())

        filings = self.client.filings("1137789")
        base = next(item for item in filings if item.form == "10-K")
        lower = replace(base, accession_number="0001137789-25-000010")
        higher = replace(base, accession_number="0001137789-25-000011")
        selected, _counts = self.adapter.select_filing((lower, higher))
        self.assertEqual(selected.accession_number, higher.accession_number)

    def test_no_match_conflict_and_malformed_dates_are_distinct(self) -> None:
        filings = self.client.filings("1137789")
        amendment = replace(filings[0], form="10-K/A")
        with self.assertRaises(AdapterFailure) as no_match:
            self.adapter.select_filing((amendment,))
        self.assertEqual(no_match.exception.code, "no_eligible_form_10k")

        eligible = next(item for item in filings if item.form == "10-K")
        conflicting = replace(eligible, primary_document="conflict.htm")
        with self.assertRaises(AdapterFailure) as ambiguous:
            self.adapter.select_filing((eligible, conflicting))
        self.assertEqual(ambiguous.exception.code, "ambiguous_filing_result")

        malformed = replace(eligible, acceptance_datetime="not-a-time")
        with self.assertRaises(AdapterFailure) as invalid:
            self.adapter.select_filing((malformed,))
        self.assertEqual(invalid.exception.code, "malformed_provider_response")


class SecProviderFailureTests(unittest.TestCase):
    def test_malformed_shape_missing_identity_and_issuer_conflict_fail_closed(self) -> None:
        malformed_values = (
            b"{}",
            json.dumps({"cik": "1137789", "filings": {"recent": {}}}).encode(),
            (FIXTURES / "CIK0001137789.json").read_bytes().replace(
                b'"0001137789"', b'"0000106040"', 1
            ),
        )
        for content in malformed_values:
            with self.subTest(content=content[:20]):
                client, _fixture, _timing = provider(SecFixtureTransport(content))
                with self.assertRaises(AdapterFailure) as caught:
                    client.filings("1137789")
                self.assertEqual(caught.exception.code, "malformed_provider_response")

        missing_primary = json.dumps(
            {
                "cik": "1137789",
                "filings": {
                    "recent": {
                        "accessionNumber": ["0001137789-25-000001"],
                        "filingDate": ["2025-01-01"],
                        "reportDate": [""],
                        "acceptanceDateTime": ["2025-01-01T00:00:00Z"],
                        "form": ["10-K"],
                        "primaryDocument": [""],
                    }
                },
            }
        ).encode()
        client, _fixture, _timing = provider(SecFixtureTransport(missing_primary))
        adapter = SecForm10KAdapter(client, fixed_clock)
        with self.assertRaises(AdapterFailure) as missing:
            adapter.discover(source(), None)
        self.assertEqual(missing.exception.code, "missing_filing_identity")

    def test_bounded_transport_failure_taxonomy(self) -> None:
        cases = (
            ([socket.timeout(), socket.timeout()], "network_timeout"),
            ([SecHttpResponse(429, {}, b"", "https://data.sec.gov/x")] * 2, "rate_limited"),
            (
                [SecHttpResponse(503, {}, b"", "https://data.sec.gov/x")] * 2,
                "temporary_service_failure",
            ),
            ([SecHttpResponse(404, {}, b"", "https://data.sec.gov/x")], "issuer_not_found"),
            (
                [SecHttpResponse(400, {}, b"", "https://data.sec.gov/x")],
                "permanent_request_failure",
            ),
        )
        for responses, code in cases:
            with self.subTest(code=code):
                transport = SecFixtureTransport()
                transport.responses.extend(responses)
                client, fixture, _timing = provider(transport)
                with self.assertRaises(AdapterFailure) as caught:
                    client.filings("1137789")
                self.assertEqual(caught.exception.code, code)
                self.assertLessEqual(len(fixture.requests), 2)
                self.assertNotIn(USER_AGENT, json.dumps(client.usage()))

    def test_content_validation_failures_are_visible(self) -> None:
        client, fixture, _timing = provider()
        cases = (
            SecHttpResponse(
                200,
                {"content-type": "application/pdf"},
                b"pdf",
                "https://www.sec.gov/x",
            ),
            SecHttpResponse(200, {"content-type": "text/html"}, b"", "https://www.sec.gov/x"),
            SecHttpResponse(
                200,
                {"content-type": "text/html", "content-length": "99"},
                b"<html></html>",
                "https://www.sec.gov/x",
            ),
            SecHttpResponse(
                200,
                {"content-type": "text/html"},
                b"<html></html>",
                "https://evil.test/x",
            ),
        )
        expected = (
            "unsupported_artifact_representation",
            "empty_artifact_content",
            "truncated_artifact_content",
            "unsafe_redirect",
        )
        for response, code in zip(cases, expected, strict=True):
            with self.subTest(code=code):
                fixture.responses.append(response)
                with self.assertRaises(AdapterFailure) as caught:
                    client.primary_document("1137789", "0001137789-25-000002", "file.htm")
                self.assertEqual(caught.exception.code, code)
        fixture.responses.append(SecResponseTooLarge("large"))
        with self.assertRaises(AdapterFailure) as oversized:
            client.primary_document("1137789", "0001137789-25-000002", "file.htm")
        self.assertEqual(oversized.exception.code, "artifact_size_limit_exceeded")

    def test_missing_runtime_identity_and_invalid_cik_stop_before_network(self) -> None:
        fixture = SecFixtureTransport()
        client = SecProviderClient(lambda: "", fixture)
        with self.assertRaises(AdapterFailure) as identity:
            client.filings("1137789")
        self.assertEqual(identity.exception.code, "invalid_runtime_identity")
        self.assertEqual(fixture.requests, [])
        adapter = SecForm10KAdapter(client, fixed_clock)
        with self.assertRaises(AdapterFailure) as cik:
            adapter.discover(source("ticker:STX"), None)
        self.assertEqual(cik.exception.code, "invalid_sec_issuer_identifier")
        self.assertEqual(fixture.requests, [])


class PullVerticalSliceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.template = load_canonical_template()
        self.firms = FirmRepository.initialize(self.root / "firm-catalog")
        self.firms.create(sample_firms()[0])
        self.profiles = SourceProfileRepository.initialize(
            self.root / "source-profiles", self.template
        )
        self.acquisition = AcquisitionRepository(self.root / "acquisition")
        client, self.transport, _timing = provider()
        self.adapter = SecForm10KAdapter(client, fixed_clock)
        self.workflow = PullWorkflow(
            self.firms,
            self.profiles,
            self.template,
            self.acquisition,
            registry(self.adapter),
            PullRunRepository(self.root / "pull-workflows"),
            fixed_clock,
            iter((f"task016{index}" for index in range(10))).__next__,
        )

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def publish(self, include_problem: bool = False) -> None:
        items = tuple(
            SourceProfileItem(
                artifact.artifact_id,
                artifact.artifact_id == "sec_10k"
                or (include_problem and artifact.artifact_id == "press_release"),
                (
                    RetrievalCandidate("identifier", 1, locator="CIK:0001137789"),
                )
                if artifact.artifact_id == "sec_10k"
                else (),
            )
            for artifact in self.template.artifacts
        )
        self.profiles.publish(SourceProfileDraft("seagate", items), None)

    def test_readiness_pull_provenance_rerun_replay_rebuild_and_integrity(self) -> None:
        self.publish()
        readiness = self.workflow.configured_firms()[0]
        self.assertEqual((readiness.enabled_artifacts, readiness.runnable_artifacts), (1, 1))
        first = self.workflow.run(PullRequest(("seagate",)))
        self.assertEqual(first.status, PullStatus.COMPLETED)
        self.assertEqual(first.firms[0].artifacts[0].outcome, ArtifactOutcome.SUCCESS)
        attempt = first.firms[0].artifacts[0].attempts[0]
        self.assertEqual(attempt.adapter_id, "sec-form-10k")
        self.assertIn(
            "document-sec-1137789-000113778925000002",
            attempt.details["document_ids"],  # type: ignore[index]
        )
        artifact_id = attempt.artifact_ids[0]
        self.assertEqual(
            self.acquisition.read_artifact(artifact_id),
            (FIXTURES / "stx-2025-10k.htm").read_bytes(),
        )
        repeat = self.workflow.run(PullRequest(("seagate",)))
        self.assertEqual(repeat.firms[0].artifacts[0].outcome, ArtifactOutcome.NO_CHANGE)
        self.assertEqual(len(self.acquisition.artifact_metadata()), 1)
        self.assertEqual(len(self.acquisition.document_index()["documents"]), 1)
        before = self.acquisition.verify_integrity()
        self.acquisition.delete_derived_state()
        with patch("socket.socket", side_effect=AssertionError("network unavailable")):
            replay = self.acquisition.replay()
            after = self.acquisition.verify_integrity()
        self.assertEqual((replay.documents, before["artifacts"], after["artifacts"]), (1, 1, 1))

    def test_other_enabled_unconfigured_artifact_produces_partial_firm(self) -> None:
        self.publish(include_problem=True)
        result = self.workflow.run(PullRequest(("seagate",)))
        outcomes = {item.artifact_id: item.outcome for item in result.firms[0].artifacts}
        self.assertEqual(result.status, PullStatus.PARTIAL)
        self.assertEqual(outcomes["sec_10k"], ArtifactOutcome.SUCCESS)
        self.assertEqual(outcomes["press_release"], ArtifactOutcome.CONFIGURATION_PROBLEM)

    def test_operator_console_exposes_adapter_and_provenance_diagnostics(self) -> None:
        html = (ROOT / "src/rfi/admin/pull_sources.html").read_text(encoding="utf-8")
        server = (ROOT / "src/rfi/admin/server.py").read_text(encoding="utf-8")
        workflow = (ROOT / "src/rfi/pull/workflow.py").read_text(encoding="utf-8")
        for marker in ("/api/pulls/adapters", "adapter_id", "attemptDetails", "provenance"):
            self.assertIn(marker, html + server + workflow)
        self.assertNotIn('artifact.artifact_id == "sec_10k"', workflow)
        self.assertNotIn("10-K", workflow)


if __name__ == "__main__":
    unittest.main()
