"""Focused hardening coverage for governed Lore transport and stream registries."""

from __future__ import annotations

import io
import json
import tempfile
import threading
import time
import unittest
from dataclasses import asdict, replace
from pathlib import Path
from urllib.error import HTTPError

from rfi.firms import FirmRepository
from rfi.mailing_lists import (
    AcquisitionLimits,
    AcquisitionRunStatus,
    ArchiveMessage,
    LoreArchive,
    LoreTransportPolicy,
    MailingListAcquisitionService,
    MailingListError,
    MailingListRepository,
    MailingListSource,
    SelectionCriteria,
)
from rfi.storage import RepositoryDatabase
from rfi.streams import StreamRepository, StreamService, default_registry
from tests.test_task023 import raw_message


class FakeResponse:
    def __init__(self, content: bytes, headers: dict[str, str] | None = None) -> None:
        self.content = content
        self.headers = headers or {}

    def __enter__(self) -> FakeResponse:
        return self

    def __exit__(self, *_args: object) -> None:
        return None

    def read(self, limit: int) -> bytes:
        return self.content[:limit]


class FakeTime:
    def __init__(self) -> None:
        self.now = 0.0
        self.sleeps: list[float] = []

    def monotonic(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self.now += seconds


class SequenceOpener:
    def __init__(self, values: list[object]) -> None:
        self.values = values
        self.calls = 0

    def __call__(self, *_args: object, **_kwargs: object) -> FakeResponse:
        value = self.values[self.calls]
        self.calls += 1
        if isinstance(value, BaseException):
            raise value
        assert isinstance(value, FakeResponse)
        return value


def source(source_id: str, **policy: object) -> MailingListSource:
    return MailingListSource(
        source_id,
        source_id.removesuffix("-lore"),
        source_id,
        f"https://lore.kernel.org/{source_id.removesuffix('-lore')}/",
        transport=LoreTransportPolicy(**policy),
    )


class LoreTransportCase(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.state = Path(self.temporary.name)
        RepositoryDatabase.initialize(self.state)
        FirmRepository.initialize(self.state / "firm-catalog")
        self.repository = MailingListRepository(self.state)

    def tearDown(self) -> None:
        self.temporary.cleanup()

    @staticmethod
    def error(status: int, retry_after: str | None = None) -> HTTPError:
        headers = {} if retry_after is None else {"Retry-After": retry_after}
        return HTTPError(
            "https://lore.kernel.org/test/raw", status, "failure", headers, io.BytesIO()
        )

    def service(
        self, configured: MailingListSource, opener: SequenceOpener, fake_time: FakeTime,
        run_id: str,
    ) -> MailingListAcquisitionService:
        self.repository.configure_source(configured)
        return MailingListAcquisitionService(
            self.repository,
            LoreArchive(
                configured,
                opener=opener,
                monotonic=fake_time.monotonic,
                sleeper=fake_time.sleep,
            ),
            identifiers=lambda: run_id,
            clock=lambda: "2026-07-20T00:00:00+00:00",
        )

    def acquire_one(self, service: MailingListAcquisitionService, source_id: str):
        return service.acquire(
            source_id,
            SelectionCriteria(message_ids=("<transport-test@example.com>",)),
            AcquisitionLimits(seed_limit=1, context_limit=2, descendant_depth=0),
        )

    def test_429_retry_after_is_honored_before_success(self) -> None:
        configured = source(
            "rate-test-lore", minimum_request_interval_seconds=0.1,
            maximum_attempts_per_request=2, backoff_initial_seconds=0.2,
            backoff_maximum_seconds=5.0,
        )
        opener = SequenceOpener([
            self.error(429, "3"),
            FakeResponse(raw_message("<transport-test@example.com>", "rate recovered")),
        ])
        fake_time = FakeTime()
        service = self.service(configured, opener, fake_time, "mailrun-rate")
        manifest = self.acquire_one(service, configured.source_id)
        self.assertEqual(manifest.run_status, AcquisitionRunStatus.SUCCEEDED)
        self.assertEqual(opener.calls, 2)
        self.assertGreaterEqual(sum(fake_time.sleeps), 3.0)

    def test_503_retries_and_recovers(self) -> None:
        configured = source(
            "service-test-lore", minimum_request_interval_seconds=0.1,
            maximum_attempts_per_request=2, backoff_initial_seconds=0,
            backoff_maximum_seconds=1,
        )
        opener = SequenceOpener([
            self.error(503),
            FakeResponse(raw_message("<transport-test@example.com>", "service recovered")),
        ])
        manifest = self.acquire_one(
            self.service(configured, opener, FakeTime(), "mailrun-service"),
            configured.source_id,
        )
        self.assertEqual(manifest.run_status, AcquisitionRunStatus.SUCCEEDED)
        self.assertEqual(opener.calls, 2)

    def test_timeout_before_useful_work_records_retryable_failure(self) -> None:
        configured = source(
            "timeout-test-lore", minimum_request_interval_seconds=0.1,
            maximum_attempts_per_request=1,
        )
        opener = SequenceOpener([TimeoutError("timed out")])
        service = self.service(configured, opener, FakeTime(), "mailrun-timeout")
        with self.assertRaises(MailingListError) as raised:
            self.acquire_one(service, configured.source_id)
        self.assertTrue(raised.exception.retryable)
        run = self.repository.acquisition_runs(configured.source_id)[0]
        self.assertEqual(run["lifecycle_status"], "retryable_failure")
        self.assertEqual(run["connectivity_state"], "incomplete")
        self.assertEqual(run["message_count"], 0)
        self.assertEqual(self.repository.rows("SELECT * FROM mailing_list_run_items"), [])
        self.assertEqual(self.repository.artifacts.artifact_metadata(), [])

    def test_retry_exhaustion_is_not_an_empty_truncated_run(self) -> None:
        configured = source(
            "exhausted-test-lore", minimum_request_interval_seconds=0.1,
            maximum_attempts_per_request=3, backoff_initial_seconds=0,
            backoff_maximum_seconds=1,
        )
        opener = SequenceOpener([self.error(429), self.error(429), self.error(429)])
        service = self.service(configured, opener, FakeTime(), "mailrun-exhausted")
        with self.assertRaisesRegex(MailingListError, "no usable messages"):
            self.acquire_one(service, configured.source_id)
        run = self.repository.acquisition_runs(configured.source_id)[0]
        self.assertEqual(opener.calls, 3)
        self.assertEqual(run["lifecycle_status"], "retryable_failure")
        self.assertNotEqual(run["connectivity_state"], "truncated")
        self.assertEqual(run["error_code"], "archive_rate_limited")

    def test_partial_success_is_durable_and_explicit(self) -> None:
        good = "<partial-good@example.com>"
        bad = "<partial-bad@example.com>"

        class PartialArchive:
            descendant_enumeration_complete = True

            def discover(self, _criteria: object, _limit: int):
                return (good, bad), False

            def fetch(self, external_id: str) -> ArchiveMessage:
                if external_id == bad:
                    raise MailingListError(
                        "archive_unavailable", "one seed unavailable", retryable=True
                    )
                return ArchiveMessage(raw_message(good, "partial success"), "fixture:partial")

            def direct_children(self, _external_id: str, _limit: int):
                return (), False

        configured = source("partial-test-lore")
        self.repository.configure_source(configured)
        service = MailingListAcquisitionService(
            self.repository,
            PartialArchive(),
            identifiers=lambda: "mailrun-partial",
            clock=lambda: "2026-07-20T00:00:00+00:00",
        )
        manifest = service.acquire(
            configured.source_id,
            SelectionCriteria(message_ids=(good, bad)),
            AcquisitionLimits(seed_limit=2, context_limit=2, descendant_depth=0),
        )
        self.assertEqual(manifest.run_status, AcquisitionRunStatus.PARTIAL)
        self.assertTrue(manifest.retryable)
        self.assertEqual(manifest.message_count, 1)
        self.assertEqual(len(self.repository.artifacts.artifact_metadata()), 1)
        self.assertEqual(len(self.repository.rows("SELECT * FROM mailing_list_run_items")), 1)
        run_item = self.repository.rows(
            "SELECT connectivity_state FROM mailing_list_run_items WHERE run_id=?",
            (manifest.run_id,),
        )[0]
        self.assertEqual(run_item["connectivity_state"], "connected")
        discussions = self.repository.rows("SELECT * FROM mailing_list_discussions")
        self.assertEqual(len(discussions), 1)
        self.assertEqual(discussions[0]["connectivity_state"], "connected")

    def test_terminal_http_rejection_is_recorded_as_terminal(self) -> None:
        configured = source(
            "terminal-test-lore", minimum_request_interval_seconds=0.1,
            maximum_attempts_per_request=3,
        )
        opener = SequenceOpener([self.error(404), self.error(404)])
        service = self.service(configured, opener, FakeTime(), "mailrun-terminal")
        with self.assertRaises(MailingListError) as raised:
            self.acquire_one(service, configured.source_id)
        self.assertFalse(raised.exception.retryable)
        run = self.repository.acquisition_runs(configured.source_id)[0]
        self.assertEqual(run["lifecycle_status"], "terminal_failure")
        self.assertEqual(run["error_code"], "archive_request_rejected")

    def test_exact_message_falls_back_to_all_and_records_provenance_flag(self) -> None:
        configured = source(
            "fallback-test-lore", minimum_request_interval_seconds=0.1,
            maximum_attempts_per_request=1,
        )
        opener = SequenceOpener([
            self.error(404),
            FakeResponse(raw_message("<transport-test@example.com>", "fallback recovered")),
        ])
        service = self.service(configured, opener, FakeTime(), "mailrun-fallback")

        manifest = self.acquire_one(service, configured.source_id)

        self.assertEqual(
            manifest.fallback_message_ids, ("<transport-test@example.com>",)
        )
        observations = self.repository.artifacts.observations()
        metadata = observations[0]["candidate"]["provenance"]["metadata"]
        self.assertTrue(metadata["cross_archive_fallback"])
        self.assertEqual(metadata["fallback_archive_url"], "https://lore.kernel.org/all/")

    def test_response_size_bound_is_terminal_and_retains_no_evidence(self) -> None:
        configured = source(
            "size-test-lore", minimum_request_interval_seconds=0.1,
            maximum_response_bytes=1024,
        )
        opener = SequenceOpener([
            FakeResponse(b"x" * 1025, {"Content-Length": "1025"}),
        ])
        service = self.service(configured, opener, FakeTime(), "mailrun-size")
        with self.assertRaises(MailingListError) as raised:
            self.acquire_one(service, configured.source_id)
        self.assertEqual(raised.exception.code, "response_too_large")
        self.assertFalse(raised.exception.retryable)
        self.assertEqual(self.repository.artifacts.artifact_metadata(), [])

    def test_source_policy_differs_by_source_and_concurrency_is_source_wide(self) -> None:
        first = source(
            "policy-one-lore", minimum_request_interval_seconds=0.25,
            maximum_concurrency=1, timeout_seconds=7, maximum_response_bytes=2048,
        )
        second = source(
            "policy-two-lore", minimum_request_interval_seconds=2.0,
            maximum_concurrency=3, timeout_seconds=30, maximum_response_bytes=4096,
        )
        self.assertNotEqual(asdict(first.transport), asdict(second.transport))
        self.repository.configure_source(first)
        governed = self.repository.artifacts.source(first.source_id)
        self.assertEqual(governed["configuration"]["archive_base_url"], first.archive_base_url)
        self.assertEqual(governed["configuration"]["list_id"], first.list_id)
        self.assertEqual(governed["policy"]["transport"], asdict(first.transport))

        entered = threading.Event()
        release = threading.Event()
        lock = threading.Lock()
        active = 0
        maximum = 0

        def opener(*_args: object, **_kwargs: object) -> FakeResponse:
            nonlocal active, maximum
            with lock:
                active += 1
                maximum = max(maximum, active)
                entered.set()
            release.wait(2)
            with lock:
                active -= 1
            return FakeResponse(raw_message("<concurrency@example.com>", "concurrency"))

        constrained = replace(first, source_id="concurrency-test-lore")
        archive_one = LoreArchive(constrained, opener=opener, sleeper=lambda _value: None)
        archive_two = LoreArchive(constrained, opener=opener, sleeper=lambda _value: None)
        threads = [
            threading.Thread(target=archive.fetch, args=("<concurrency@example.com>",))
            for archive in (archive_one, archive_two)
        ]
        threads[0].start()
        self.assertTrue(entered.wait(1))
        threads[1].start()
        time.sleep(0.05)
        self.assertEqual(maximum, 1)
        release.set()
        for thread in threads:
            thread.join(2)
        self.assertEqual(maximum, 1)


class RegistryBoundaryCase(unittest.TestCase):
    def test_core_depends_on_finite_registered_contracts(self) -> None:
        root = Path(__file__).resolve().parents[1]
        core = "\n".join(
            (root / path).read_text(encoding="utf-8")
            for path in ("src/rfi/streams/service.py", "src/rfi/streams/repository.py")
        )
        for term in ("mailing_list_", "mail.message", "connected_discussion"):
            self.assertNotIn(term, core)
        registrations = default_registry().registrations()
        self.assertEqual(
            {item.capability.schema_id for item in registrations},
            {"mail.message", "sec.filing"},
        )
        self.assertTrue(all(item.projection_provider for item in registrations))
        self.assertTrue(all(item.expansion_handlers for item in registrations))

    def test_stream_contract_has_no_provider_or_cursor_configuration(self) -> None:
        root = Path(__file__).resolve().parents[1]
        html = (root / "src/rfi/admin/streams.html").read_text(encoding="utf-8")
        for field in ('name="provider"', 'name="archive_base_url"', 'name="list_id"',
                      'name="initial_date"', 'name="incremental"'):
            self.assertNotIn(field, html)
        self.assertNotIn(
            '"source"', (root / "fixtures/streams/task025-topology.json").read_text()
        )


class MigrationBoundaryCase(unittest.TestCase):
    def test_v3_migration_adds_run_outcomes_and_governed_transport_policy(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            state = Path(temporary)
            RepositoryDatabase.initialize(state)
            FirmRepository.initialize(state / "firm-catalog")
            mailing = MailingListRepository(state)
            configured = source("migration-policy-lore")
            mailing.configure_source(configured)
            with RepositoryDatabase.open(state).connect() as connection:
                governed = self._without_transport(
                    str(
                        connection.execute(
                            "SELECT canonical_json FROM governed_sources WHERE source_id=?",
                            (configured.source_id,),
                        ).fetchone()[0]
                    )
                )
                connection.execute(
                    "UPDATE governed_sources SET canonical_json=? WHERE source_id=?",
                    (governed, configured.source_id),
                )
                for column in ("retryable", "error_code", "lifecycle_status"):
                    connection.execute(
                        f"ALTER TABLE mailing_list_runs DROP COLUMN {column}"
                    )
                connection.execute("UPDATE schema_metadata SET schema_version=3")
            migrated = RepositoryDatabase.open(state)
            self.assertEqual(migrated.validate()["schema_version"], 5)
            restored = MailingListRepository(state).source(configured.source_id)
            self.assertEqual(restored.transport, LoreTransportPolicy())
            with migrated.connect(read_only=True) as connection:
                columns = {
                    str(row[1]) for row in connection.execute(
                        "PRAGMA table_info(mailing_list_runs)"
                    )
                }
            self.assertTrue({"lifecycle_status", "error_code", "retryable"} <= columns)

    @staticmethod
    def _without_transport(raw: str) -> str:
        value = json.loads(raw)
        value["policy"].pop("transport")
        return json.dumps(value, sort_keys=True, separators=(",", ":"))
