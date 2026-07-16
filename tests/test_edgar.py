"""Offline native SEC EDGAR adapter and lifecycle tests."""

from __future__ import annotations

import json
import os
import socket
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from rfi.acquisition.contracts import ContractError
from rfi.acquisition.edgar import (
    EdgarAdapter,
    EdgarHttpResponse,
    USER_AGENT_VARIABLE,
    load_edgar_profiles,
    user_agent_from_environment,
    validate_edgar_profile,
)
from rfi.acquisition.engine import (
    AcquisitionEngine,
    AcquisitionKernel,
    AdapterFailure,
    AdapterRegistry,
)
from rfi.acquisition.repository import AcquisitionRepository

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "fixtures/edgar"
TEST_USER_AGENT = "RFI-1-tests test-contact@example.invalid"


class FakeTime:
    def __init__(self) -> None:
        self.value = 0.0
        self.sleeps: list[float] = []

    def monotonic(self) -> float:
        return self.value

    def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self.value += seconds


class EdgarFixtureTransport:
    def __init__(self) -> None:
        self.requests: list[dict[str, object]] = []
        self.responses: list[EdgarHttpResponse | BaseException] = []
        self.submission = (FIXTURES / "complete-submission.txt").read_bytes()

    def request(
        self,
        url: str,
        headers: dict[str, str],
        timeout_seconds: float,
        maximum_bytes: int,
    ) -> EdgarHttpResponse:
        self.requests.append(
            {
                "url": url,
                "user_agent_present": bool(headers.get("User-Agent")),
                "timeout": timeout_seconds,
                "maximum_bytes": maximum_bytes,
            }
        )
        if self.responses:
            value = self.responses.pop(0)
            if isinstance(value, BaseException):
                raise value
            return value
        if "/submissions/CIK" in url:
            name = url.rsplit("/", 1)[1]
            return EdgarHttpResponse(
                200,
                {"content-type": "application/json"},
                (FIXTURES / name).read_bytes(),
            )
        exact = self.submission.replace(
            b"synthetic-native-edgar-fixture", url.encode("utf-8")
        )
        return EdgarHttpResponse(200, {"content-type": "text/plain"}, exact)


def profile(ticker: str = "STX"):
    return next(
        value for value in load_edgar_profiles(ROOT) if value.configuration["ticker"] == ticker
    )


def adapter(transport: EdgarFixtureTransport | None = None):
    timing = FakeTime()
    instance = EdgarAdapter(
        TEST_USER_AGENT,
        transport or EdgarFixtureTransport(),
        lambda: "2026-07-15T00:00:00Z",
        timing.monotonic,
        timing.sleep,
    )
    return instance, timing


class EdgarConfigurationTests(unittest.TestCase):
    def test_profiles_are_exactly_bounded_and_operator_data_free(self) -> None:
        profiles = load_edgar_profiles(ROOT)
        self.assertEqual(
            [value.source_id for value in profiles],
            ["source-edgar-stx", "source-edgar-wdc"],
        )
        for value in profiles:
            validate_edgar_profile(value)
            serialized = json.dumps(value.to_dict())
            self.assertIn(f"env:{USER_AGENT_VARIABLE}", serialized)
            self.assertNotIn(TEST_USER_AGENT, serialized)
            self.assertEqual(value.policy["minimum_request_interval_seconds"], 0.5)

    def test_missing_or_malformed_runtime_identity_stops_before_network(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaisesRegex(ContractError, "runtime identity is absent"):
                user_agent_from_environment(f"env:{USER_AGENT_VARIABLE}")
        with patch.dict(os.environ, {USER_AGENT_VARIABLE: "anonymous-bot"}, clear=True):
            with self.assertRaisesRegex(ContractError, "contact email"):
                user_agent_from_environment(f"env:{USER_AGENT_VARIABLE}")


class EdgarMappingAndLifecycleTests(unittest.TestCase):
    def test_official_columnar_mapping_and_provider_independent_identity(self) -> None:
        transport = EdgarFixtureTransport()
        instance, _timing = adapter(transport)
        page = instance.discover(profile(), None)
        candidate = page.candidates[0]
        self.assertEqual(candidate.document_id, "document-sec-1137789-000113778925000001")
        self.assertEqual(candidate.provenance.metadata["form_type"], "10-K")
        self.assertEqual(candidate.provenance.metadata["provider"], "SEC EDGAR")
        self.assertNotIn("data.sec.gov", candidate.document_id)

    def test_pagination_selects_fixed_form_mix_and_paces_every_request(self) -> None:
        transport = EdgarFixtureTransport()
        instance, timing = adapter(transport)
        continuation = None
        candidates = []
        while True:
            page = instance.discover(profile(), continuation)
            candidates.extend(page.candidates)
            continuation = page.next_token
            if continuation is None:
                break
        self.assertEqual(
            [value.provenance.metadata["form_type"] for value in candidates],
            ["10-K", "10-Q", "10-Q", "8-K", "8-K"],
        )
        self.assertEqual(len(transport.requests), 5)
        self.assertEqual(timing.sleeps, [0.5, 0.5, 0.5, 0.5])
        self.assertNotIn(TEST_USER_AGENT, json.dumps(instance.usage()))

    def test_engine_first_rerun_replay_and_integrity(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            repository = AcquisitionRepository(Path(temporary))
            profiles = load_edgar_profiles(ROOT)
            for value in profiles:
                repository.register_source(value)
            instance, _timing = adapter()
            engine = AcquisitionEngine(
                repository,
                AdapterRegistry((instance,)),
                lambda: "2026-07-15T00:00:00Z",
            )
            kernel = AcquisitionKernel(engine, repository)
            first = kernel.run_enabled("native-offline-first")
            index = repository.document_index()
            artifacts = repository.artifact_metadata()
            second = kernel.run_enabled("native-offline-second")
            self.assertTrue(all(value.status.value == "complete" for value in first + second))
            self.assertEqual(sum(value.durable_acquisitions for value in first), 10)
            self.assertEqual(sum(value.retrieval_attempts for value in second), 0)
            self.assertEqual(index, repository.document_index())
            self.assertEqual(artifacts, repository.artifact_metadata())
            repository.delete_derived_state()
            with patch("socket.socket", side_effect=AssertionError("network forbidden")):
                replay = repository.replay()
            self.assertEqual(replay.documents, 10)
            self.assertEqual(repository.verify_integrity()["artifacts"], 10)


class EdgarFailureTests(unittest.TestCase):
    def test_rate_limit_timeout_and_rejection_are_sanitized_and_bounded(self) -> None:
        cases = (
            ([EdgarHttpResponse(429, {}, b""), EdgarHttpResponse(429, {}, b"")], "fair-access"),
            ([socket.timeout(), socket.timeout()], "transport failed"),
            ([EdgarHttpResponse(403, {}, b"private")], "declared automated client"),
        )
        for responses, message in cases:
            with self.subTest(message=message):
                transport = EdgarFixtureTransport()
                transport.responses.extend(responses)
                instance, _timing = adapter(transport)
                with self.assertRaisesRegex(AdapterFailure, message) as caught:
                    instance.discover(profile(), None)
                rendered = f"{caught.exception}\n{json.dumps(instance.usage())}"
                self.assertNotIn(TEST_USER_AGENT, rendered)
                self.assertLessEqual(len(transport.requests), 2)

    def test_malformed_submissions_and_bad_artifacts_fail_closed(self) -> None:
        transport = EdgarFixtureTransport()
        transport.responses.append(
            EdgarHttpResponse(200, {"content-type": "application/json"}, b"{}")
        )
        instance, _timing = adapter(transport)
        with self.assertRaisesRegex(AdapterFailure, "CIK differs"):
            instance.discover(profile(), None)
        transport = EdgarFixtureTransport()
        instance, _timing = adapter(transport)
        candidate = instance.discover(profile(), None).candidates[0]
        transport.responses.append(
            EdgarHttpResponse(200, {"content-type": "application/pdf"}, b"pdf")
        )
        with self.assertRaisesRegex(AdapterFailure, "content type"):
            instance.retrieve(profile(), candidate)
        transport.responses.append(
            EdgarHttpResponse(200, {"content-type": "text/plain"}, b"truncated")
        )
        with self.assertRaisesRegex(AdapterFailure, "complete submission"):
            instance.retrieve(profile(), candidate)


if __name__ == "__main__":
    unittest.main()
