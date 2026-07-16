"""Offline TASK-004 tests for the commercial SEC provider boundary."""

from __future__ import annotations

import json
import os
import socket
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from rfi.acquisition.contracts import ContractError
from rfi.acquisition.engine import AcquisitionEngine, AdapterFailure, AdapterRegistry, RunStatus
from rfi.acquisition.repository import AcquisitionRepository
from rfi.acquisition.sec_api import (
    ENVIRONMENT_VARIABLE,
    HttpResponse,
    SecApiAdapter,
    credential_from_environment,
    load_live_profiles,
    validate_live_profile,
)

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "fixtures/sec-api"
SECRET = "test-secret-that-must-never-appear"


class FixtureTransport:
    """Deterministic in-memory replacement for every provider network operation."""

    def __init__(self) -> None:
        self.filings = json.loads((FIXTURES / "query-filings.json").read_text())
        self.submission = (FIXTURES / "complete-submission.txt").read_bytes()
        self.requests: list[dict[str, object]] = []
        self.responses: list[HttpResponse | BaseException] = []

    def request(
        self,
        method: str,
        url: str,
        headers: dict[str, str],
        body: bytes | None,
        timeout_seconds: float,
        maximum_bytes: int,
    ) -> HttpResponse:
        self.requests.append(
            {
                "method": method,
                "url": url,
                "authorization_present": bool(headers.get("Authorization")),
                "timeout": timeout_seconds,
                "maximum_bytes": maximum_bytes,
            }
        )
        if self.responses:
            response = self.responses.pop(0)
            if isinstance(response, BaseException):
                raise response
            return response
        if method == "POST":
            payload = json.loads(body or b"{}")
            query = payload["query"]
            ticker = "STX" if "ticker:STX" in query else "WDC"
            form = next(form for form in ("10-K", "10-Q", "8-K") if f'"{form}"' in query)
            offset = int(payload["from"])
            size = int(payload["size"])
            content = json.dumps(
                {"total": {"value": len(self.filings[ticker][form]), "relation": "eq"},
                 "filings": self.filings[ticker][form][offset : offset + size]}
            ).encode()
            return HttpResponse(
                200,
                {"content-type": "application/json", "x-rate-limit-remaining": "fixture"},
                content,
            )
        exact = self.submission.replace(
            b"fixture-complete-submission", url.encode("utf-8")
        )
        return HttpResponse(200, {"content-type": "text/plain"}, exact)


def profile(ticker: str = "STX"):
    return next(
        item for item in load_live_profiles(ROOT) if item.configuration["ticker"] == ticker
    )


class ConfigurationAndIdentityTests(unittest.TestCase):
    def test_profiles_are_exactly_bounded_and_secret_free(self) -> None:
        profiles = load_live_profiles(ROOT)
        self.assertEqual(
            [item.source_id for item in profiles], ["source-sec-stx", "source-sec-wdc"]
        )
        for item in profiles:
            validate_live_profile(item)
            serialized = json.dumps(item.to_dict())
            self.assertNotIn(SECRET, serialized)
            self.assertIn(f"env:{ENVIRONMENT_VARIABLE}", serialized)
            self.assertEqual(
                item.configuration["form_limits"], {"10-K": 1, "10-Q": 2, "8-K": 2}
            )

    def test_missing_credential_fails_without_network(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaisesRegex(ContractError, "credential is absent"):
                credential_from_environment(f"env:{ENVIRONMENT_VARIABLE}")

    def test_wrong_credential_reference_is_rejected(self) -> None:
        with self.assertRaisesRegex(ContractError, "credential_reference"):
            credential_from_environment("file:arbitrary")

    def test_mapping_uses_sec_accession_not_provider_id_or_url(self) -> None:
        adapter = SecApiAdapter(SECRET, FixtureTransport(), lambda: "2026-07-15T00:00:00Z")
        page = adapter.discover(profile(), None)
        candidate = page.candidates[0]
        self.assertEqual(candidate.document_id, "document-sec-1137789-000113778925000001")
        self.assertNotIn("fixture-stx-10k", candidate.document_id)
        self.assertNotIn("http", candidate.document_id)
        self.assertEqual(candidate.provenance.metadata["issuer_cik"], "1137789")
        self.assertEqual(candidate.provenance.metadata["form_type"], "10-K")

    def test_missing_sec_identity_field_is_rejected(self) -> None:
        transport = FixtureTransport()
        bad = {"filings": [{"cik": "1137789"}]}
        transport.responses.append(
            HttpResponse(
                200, {"content-type": "application/json"}, json.dumps(bad).encode()
            )
        )
        adapter = SecApiAdapter(SECRET, transport)
        with self.assertRaisesRegex(AdapterFailure, "identity fields"):
            adapter.discover(profile(), None)


class PaginationAndEngineTests(unittest.TestCase):
    def test_real_contract_pagination_covers_governed_form_limits(self) -> None:
        transport = FixtureTransport()
        adapter = SecApiAdapter(SECRET, transport)
        continuation = None
        candidates = []
        pages = 0
        while True:
            page = adapter.discover(profile(), continuation)
            pages += 1
            candidates.extend(page.candidates)
            continuation = page.next_token
            if continuation is None:
                break
        self.assertEqual(pages, 5)
        self.assertEqual(
            [item.provenance.metadata["form_type"] for item in candidates],
            ["10-K", "10-Q", "10-Q", "8-K", "8-K"],
        )
        self.assertEqual(len(transport.requests), 5)

    def test_offline_engine_run_rerun_replay_and_integrity(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            repository = AcquisitionRepository(Path(temporary))
            profiles = load_live_profiles(ROOT)
            for item in profiles:
                repository.register_source(item)
            transport = FixtureTransport()
            adapter = SecApiAdapter(SECRET, transport, lambda: "2026-07-15T00:00:00Z")
            engine = AcquisitionEngine(
                repository,
                AdapterRegistry((adapter,)),
                lambda: "2026-07-15T00:00:00Z",
            )
            first = engine.run_source("source-sec-stx", "offline-first")
            inventory_before = repository.document_index()
            second = engine.run_source("source-sec-stx", "offline-second")
            self.assertEqual(first.status, RunStatus.COMPLETE)
            self.assertEqual(first.durable_acquisitions, 5)
            self.assertEqual(second.status, RunStatus.COMPLETE)
            self.assertEqual(second.retrieval_attempts, 0)
            self.assertEqual(inventory_before, repository.document_index())
            repository.delete_derived_state()
            with patch("socket.socket", side_effect=AssertionError("network forbidden")):
                replay = repository.replay()
            self.assertEqual(replay.documents, 5)
            self.assertEqual(repository.verify_integrity()["result"], "PASS")


class FailureAndRedactionTests(unittest.TestCase):
    def assert_secret_absent(self, error: BaseException, adapter: SecApiAdapter) -> None:
        rendered = f"{error!s}\n{json.dumps(adapter.usage())}"
        self.assertNotIn(SECRET, rendered)

    def test_authentication_rejection_is_sanitized(self) -> None:
        transport = FixtureTransport()
        transport.responses.append(
            HttpResponse(401, {"content-type": "application/json"}, b"echoed-secret")
        )
        adapter = SecApiAdapter(SECRET, transport)
        with self.assertRaisesRegex(AdapterFailure, "authentication was rejected") as caught:
            adapter.discover(profile(), None)
        self.assert_secret_absent(caught.exception, adapter)

    def test_quota_rejection_retries_boundedly(self) -> None:
        transport = FixtureTransport()
        transport.responses.extend(
            [
                HttpResponse(429, {"x-rate-limit-remaining": "0"}, b""),
                HttpResponse(429, {}, b""),
            ]
        )
        adapter = SecApiAdapter(SECRET, transport, sleeper=lambda _seconds: None)
        with self.assertRaisesRegex(AdapterFailure, "quota or rate limit") as caught:
            adapter.discover(profile(), None)
        self.assertEqual(len(transport.requests), 2)
        self.assert_secret_absent(caught.exception, adapter)

    def test_transient_server_failure_retries_boundedly(self) -> None:
        transport = FixtureTransport()
        transport.responses.extend([HttpResponse(503, {}, b""), HttpResponse(503, {}, b"")])
        adapter = SecApiAdapter(SECRET, transport, sleeper=lambda _seconds: None)
        with self.assertRaisesRegex(AdapterFailure, "transient server"):
            adapter.discover(profile(), None)
        self.assertEqual(len(transport.requests), 2)

    def test_timeout_retries_boundedly(self) -> None:
        transport = FixtureTransport()
        transport.responses.extend([socket.timeout(), socket.timeout()])
        adapter = SecApiAdapter(SECRET, transport, sleeper=lambda _seconds: None)
        with self.assertRaisesRegex(AdapterFailure, "transport failed"):
            adapter.discover(profile(), None)
        self.assertEqual(len(transport.requests), 2)

    def test_malformed_discovery_and_content_type_are_rejected(self) -> None:
        transport = FixtureTransport()
        transport.responses.append(
            HttpResponse(200, {"content-type": "application/json"}, b"not-json")
        )
        adapter = SecApiAdapter(SECRET, transport)
        with self.assertRaisesRegex(AdapterFailure, "malformed JSON"):
            adapter.discover(profile(), None)
        transport = FixtureTransport()
        adapter = SecApiAdapter(SECRET, transport)
        candidate = adapter.discover(profile(), None).candidates[0]
        transport.responses.append(HttpResponse(200, {"content-type": "application/pdf"}, b"pdf"))
        with self.assertRaisesRegex(AdapterFailure, "content type"):
            adapter.retrieve(profile(), candidate)

    def test_empty_and_truncated_artifacts_are_rejected(self) -> None:
        transport = FixtureTransport()
        adapter = SecApiAdapter(SECRET, transport)
        candidate = adapter.discover(profile(), None).candidates[0]
        transport.responses.append(HttpResponse(200, {"content-type": "text/plain"}, b""))
        with self.assertRaisesRegex(AdapterFailure, "empty"):
            adapter.retrieve(profile(), candidate)
        transport.responses.append(HttpResponse(200, {"content-type": "text/plain"}, b"truncated"))
        with self.assertRaisesRegex(AdapterFailure, "complete SEC submission"):
            adapter.retrieve(profile(), candidate)

    def test_invalid_continuation_is_rejected(self) -> None:
        adapter = SecApiAdapter(SECRET, FixtureTransport())
        with self.assertRaisesRegex(AdapterFailure, "continuation token"):
            adapter.discover(profile(), "secret-shaped-token")


if __name__ == "__main__":
    unittest.main()
