"""Focused TASK-028 Linux mailing-list operator workflow coverage."""

from __future__ import annotations

import tempfile
import threading
import unittest
import urllib.request
from dataclasses import asdict
from datetime import date
from pathlib import Path
from typing import Any
from unittest.mock import patch

from rfi.admin import create_admin_server
from rfi.cli import initialize
from rfi.firms import FirmRepository
from rfi.mailing_lists import (
    ArchiveMessage,
    FixtureMailingListArchive,
    LinuxMailingListWorkflowService,
    LoreArchive,
    MailingListError,
    MailingListQueryService,
    MailingListRepository,
    MailingListSource,
    MailingListSourceService,
    SelectionCriteria,
    normalize_lore_archive,
)
from rfi.mailing_lists.parser import parse_message
from rfi.storage import RepositoryDatabase
from rfi.streams import StreamDraft, StreamError, StreamRepository, StreamService

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "fixtures/linux-block"


class FixtureWorkflowArchive(FixtureMailingListArchive):
    def probe(self) -> dict[str, str]:
        return {
            "title": "linux-block.vger.kernel.org archive mirror",
            "updated": "2026-07-20T12:00:00Z",
            "canonical_url": "https://lore.kernel.org/linux-block/",
        }


def archive_factory(_source: MailingListSource) -> FixtureWorkflowArchive:
    messages: dict[str, ArchiveMessage] = {}
    for path in sorted(FIXTURES.glob("*.eml")):
        raw = path.read_bytes()
        parsed = parse_message(raw)
        if parsed.external_message_id:
            messages[parsed.external_message_id] = ArchiveMessage(raw, f"fixture:{path.name}")
    return FixtureWorkflowArchive(messages)


def draft(**changes: Any) -> dict[str, Any]:
    value: dict[str, Any] = {
        "archive_url": "https://lore.kernel.org/linux-block/",
        "stream_name": "Linux Block Discussions",
        "description": "Bounded storage evidence",
        "date_from": "2026-07-16",
        "date_through": "2026-07-16",
        "keywords": ["deterministic queue"],
        "subjects": [],
        "participants": [],
        "seed_limit": 5,
        "total_limit": 20,
        "descendant_depth": 3,
    }
    value.update(changes)
    return value


class WorkflowCase(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.state = Path(self.temporary.name)
        RepositoryDatabase.initialize(self.state)
        FirmRepository.initialize(self.state / "firm-catalog")
        self.repository = MailingListRepository(self.state)
        self.streams = StreamService(StreamRepository(self.state))
        self.query = MailingListQueryService(self.repository)
        self.workflow = LinuxMailingListWorkflowService(
            self.repository,
            MailingListSourceService(self.repository),
            self.streams,
            self.query,
            archive_factory=archive_factory,
            today=lambda: date(2026, 7, 20),
        )

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def test_catalog_url_normalization_and_bounded_defaults(self) -> None:
        self.assertGreaterEqual(len(self.workflow.catalog()), 4)
        self.assertEqual(
            normalize_lore_archive("https://lore.kernel.org/linux-block"),
            ("linux-block", "https://lore.kernel.org/linux-block/"),
        )
        for invalid in (
            "http://lore.kernel.org/linux-block/", "https://example.com/linux-block/",
            "https://lore.kernel.org/linux-block/?q=all",
            "https://lore.kernel.org/linux-block/nested/",
        ):
            with self.subTest(invalid=invalid), self.assertRaises(MailingListError):
                normalize_lore_archive(invalid)
        defaults = self.workflow.defaults()
        self.assertEqual(defaults.seed_limit, 5)
        self.assertEqual(defaults.total_limit, 50)
        self.assertEqual(defaults.date_from, "2026-07-13")
        normalized_source = MailingListSourceService(self.repository).validate({
            "source_id": "legacy-block",
            "list_id": "linux-block",
            "display_name": "Legacy block",
            "archive_base_url": "https://LORE.KERNEL.ORG/linux-block",
            "provider": "lore-public-inbox",
        })
        self.assertEqual(
            normalized_source.archive_base_url, "https://lore.kernel.org/linux-block/"
        )
        with self.assertRaises(MailingListError):
            MailingListSourceService(self.repository).validate({
                "source_id": "bad-block",
                "list_id": "linux-block",
                "display_name": "Bad block",
                "archive_base_url": "https://lore-kernel-org/linux-block",
                "provider": "lore-public-inbox",
            })

    def test_review_and_archive_validation_do_not_persist(self) -> None:
        review = self.workflow.review(draft())
        self.assertEqual(review.source.source_id, "linux-block-lore")
        self.assertEqual(review.stream.stream_id, "linux-block-discussions")
        self.assertIn("governed Lore source", review.records_to_create)
        self.assertEqual(self.repository.sources(), ())
        self.assertEqual(self.streams.list_streams(), ())
        validation = self.workflow.validate_archive(draft())
        self.assertTrue(validation.reachable)
        self.assertIn("archive mirror", validation.observed_title)
        self.assertEqual(self.repository.sources(), ())
        self.assertEqual(self.streams.list_streams(), ())

    def test_invalid_dates_limits_and_empty_hidden_identity_are_actionable(self) -> None:
        cases = (
            (draft(date_from="2026-07-20", date_through="2026-07-19"), "Starting date"),
            (draft(date_from="2026-01-01"), "31 days"),
            (draft(seed_limit=0), "direct-message limit"),
            (draft(total_limit=5), "must exceed"),
            (draft(total_limit=101), "at most 100"),
            (draft(stream_name=""), "stream_name is required"),
        )
        for value, message in cases:
            with self.subTest(message=message), self.assertRaisesRegex(MailingListError, message):
                self.workflow.review(value)

    def test_no_match_and_retryable_retrieval_are_not_reported_ready(self) -> None:
        self.workflow.archive_factory = lambda _source: FixtureWorkflowArchive({})
        created = self.workflow.create(draft())
        assert created.revision is not None
        empty = self.workflow.test(created.revision.stream_id)
        self.assertEqual(empty.status, "failed")
        self.assertTrue(empty.configuration_ready)
        self.assertEqual(empty.test_evidence_status, "empty")
        self.assertIn("No Lore messages matched", empty.message)
        self.assertEqual(self.workflow.saved()[0].configuration_status, "ready")
        self.assertEqual(self.workflow.saved()[0].test_evidence_status, "empty")

        class FailingArchive(FixtureWorkflowArchive):
            def discover(self, *_args: Any) -> tuple[str, ...]:
                raise MailingListError("archive_timeout", "Lore timed out", retryable=True)

        self.workflow.archive_factory = lambda _source: FailingArchive({})
        failed = self.workflow.test(created.revision.stream_id)
        self.assertEqual(failed.status, "failed")
        self.assertTrue(failed.retry_safe)
        self.assertTrue(failed.configuration_ready)
        self.assertEqual(failed.test_evidence_status, "failed")

    def test_partial_create_names_durable_source_and_safe_retry(self) -> None:
        with patch.object(
            self.streams,
            "save",
            side_effect=StreamError("write_failed", "Could not create stream"),
        ):
            result = self.workflow.create(draft())
        self.assertEqual(result.status, "partial")
        self.assertTrue(result.source_created)
        self.assertTrue(result.retry_safe)
        self.assertIn("source is durable", result.message)
        self.assertEqual(len(self.repository.sources()), 1)
        self.assertEqual(self.streams.list_streams(), ())

    def test_create_is_coordinated_idempotent_and_collision_safe(self) -> None:
        created = self.workflow.create(draft())
        self.assertEqual(created.status, "created")
        self.assertTrue(created.source_created)
        self.assertIsNotNone(created.revision)
        repeated = self.workflow.create(draft())
        self.assertEqual(repeated.status, "no_change")
        self.assertFalse(repeated.source_created)
        self.assertEqual(len(self.repository.sources()), 1)
        self.assertEqual(len(self.streams.list_streams()), 1)
        collision = self.workflow.review(draft(description="Different purpose"))
        self.assertRegex(collision.stream.stream_id, r"linux-block-discussions-[0-9a-f]{8}")

    def test_bounded_test_retains_real_projection_and_survives_restart(self) -> None:
        created = self.workflow.create(draft())
        assert created.revision is not None
        result = self.workflow.test(created.revision.stream_id)
        self.assertEqual(result.status, "ready")
        self.assertTrue(result.configuration_ready)
        self.assertEqual(result.test_evidence_status, "complete_connected")
        self.assertGreaterEqual(len(result.messages), 5)
        self.assertTrue(any(item.direct_match for item in result.messages))
        self.assertTrue(any(item.context_only for item in result.messages))
        for item in result.messages:
            self.assertTrue(item.summary.subject)
            self.assertTrue(item.summary.sender)
            self.assertTrue(item.summary.message_date)
            self.assertTrue(item.source_link.startswith("https://lore.kernel.org/linux-block/"))
        assert not isinstance(result.acquisition, dict) and result.acquisition is not None
        stored = self.workflow.result(result.acquisition.run_id)
        self.assertEqual(len(stored["messages"]), len(result.messages))
        restarted = LinuxMailingListWorkflowService(
            MailingListRepository(self.state),
            MailingListSourceService(MailingListRepository(self.state)),
            StreamService(StreamRepository(self.state)),
            MailingListQueryService(MailingListRepository(self.state)),
            archive_factory=archive_factory,
            today=lambda: date(2026, 7, 20),
        )
        saved = restarted.saved()
        self.assertEqual(len(saved), 1)
        self.assertEqual(saved[0].configuration_status, "ready")
        self.assertEqual(saved[0].test_evidence_status, "complete_connected")
        restarted_draft = asdict(restarted.draft_for(saved[0].stream_id))
        for field in ("keywords", "subjects", "participants"):
            restarted_draft[field] = list(restarted_draft[field])
        self.assertEqual(restarted_draft, draft())

    def test_configuration_readiness_is_distinct_from_incomplete_test_evidence(self) -> None:
        created = self.workflow.create(draft(seed_limit=1, total_limit=2))
        assert created.revision is not None
        result = self.workflow.test(created.revision.stream_id)
        self.assertEqual(result.status, "tested_incomplete")
        self.assertTrue(result.configuration_ready)
        self.assertEqual(result.test_evidence_status, "incomplete_or_truncated")
        self.assertTrue(result.incomplete_or_truncated)
        saved = self.workflow.saved()[0]
        self.assertEqual(saved.configuration_status, "ready")
        self.assertEqual(saved.test_evidence_status, "incomplete_or_truncated")

    def test_prior_external_source_is_reused_with_canonical_equivalence(self) -> None:
        prior = MailingListSource(
            "block-archive",
            "linux-block",
            "Prior External Sources record",
            "https://LORE.KERNEL.ORG/linux-block",
        )
        self.repository.configure_source(prior)
        reviewed = self.workflow.review(draft())
        self.assertEqual(reviewed.source.source_id, "block-archive")
        self.assertEqual(
            reviewed.source.archive_base_url, "https://lore.kernel.org/linux-block/"
        )
        self.assertTrue(self.workflow.validate_archive(draft()).reachable)
        created = self.workflow.create(draft())
        self.assertFalse(created.source_created)
        self.assertEqual(
            self.repository.source("block-archive").archive_base_url,
            "https://LORE.KERNEL.ORG/linux-block",
        )
        self.assertEqual(len(self.repository.sources()), 1)

    def test_exact_unused_legacy_source_is_repaired_once_and_survives_restart(self) -> None:
        prior = MailingListSource(
            "linux-block-lore",
            "linux-block",
            "Linux Block Layer",
            "https://lore-kernel-org/linux-block",
        )
        self.repository.configure_source(prior)
        database = RepositoryDatabase.open(self.state)
        with database.connect() as connection:
            connection.execute("UPDATE schema_metadata SET schema_version=4")
        migrated = RepositoryDatabase.open(self.state)
        self.assertEqual(migrated.validate()["schema_version"], 5)
        self.assertEqual(len(self.repository.sources()), 1)
        restarted = MailingListRepository(self.state)
        self.assertEqual(
            restarted.source("linux-block-lore").archive_base_url,
            "https://lore.kernel.org/linux-block/",
        )
        governed = restarted.artifacts.source("linux-block-lore")
        self.assertEqual(
            governed["configuration"]["archive_base_url"],
            "https://lore.kernel.org/linux-block/",
        )
        self.assertFalse(migrated.migrate())
        self.assertEqual(len(restarted.sources()), 1)
        self.assertTrue(self.workflow.validate_archive(draft()).reachable)

    def test_legacy_repair_fails_closed_when_exact_predicate_is_not_met(self) -> None:
        prior = MailingListSource(
            "linux-block-lore",
            "linux-block",
            "Near but not exact legacy state",
            "https://lore-kernel-org/linux-block/",
        )
        self.repository.configure_source(prior)
        database = RepositoryDatabase.open(self.state)
        with database.connect() as connection:
            connection.execute("UPDATE schema_metadata SET schema_version=4")
        RepositoryDatabase.open(self.state)
        self.assertEqual(
            self.repository.source("linux-block-lore").archive_base_url,
            "https://lore-kernel-org/linux-block/",
        )

    def test_legacy_repair_fails_closed_when_source_has_a_dependency(self) -> None:
        prior = MailingListSource(
            "linux-block-lore",
            "linux-block",
            "Linux Block Layer",
            "https://lore-kernel-org/linux-block",
        )
        self.repository.configure_source(prior)
        self.streams.save(StreamDraft(
            "prior-block-stream",
            "Prior block stream",
            "Existing governed reference",
            True,
            "external",
            ("linux-block-lore",),
            "mail.message",
            {"op": "all", "items": [
                {"field": "text", "operator": "contains", "value": "block"}
            ]},
            {"strategy": "connected_discussion", "ancestor_closure": True,
             "descendant_depth": 1},
            {"seed_limit": 1, "expanded_limit": 2},
        ))
        database = RepositoryDatabase.open(self.state)
        with database.connect() as connection:
            connection.execute("UPDATE schema_metadata SET schema_version=4")
        RepositoryDatabase.open(self.state)
        self.assertEqual(
            self.repository.source("linux-block-lore").archive_base_url,
            "https://lore-kernel-org/linux-block",
        )

    def test_legacy_repair_fails_closed_for_acquisition_dependency(self) -> None:
        prior = MailingListSource(
            "linux-block-lore",
            "linux-block",
            "Linux Block Layer",
            "https://lore-kernel-org/linux-block",
        )
        self.repository.configure_source(prior)
        database = RepositoryDatabase.open(self.state)
        with database.connect() as connection:
            connection.execute(
                "INSERT INTO acquisition_attempts VALUES (?,?,?,?,?,?,?,?,?,?)",
                (
                    "attempt-task028-legacy",
                    "linux-block-lore",
                    "candidate-task028-legacy",
                    "document-task028-legacy",
                    "failed",
                    "2026-07-21T00:00:00Z",
                    "lore-public-inbox",
                    None,
                    None,
                    "{}",
                ),
            )
            connection.execute("UPDATE schema_metadata SET schema_version=4")
        RepositoryDatabase.open(self.state)
        self.assertEqual(
            self.repository.source("linux-block-lore").archive_base_url,
            "https://lore-kernel-org/linux-block",
        )

    def test_no_unbounded_or_browser_shadow_selection_exists(self) -> None:
        with self.assertRaisesRegex(MailingListError, "explicit bounds"):
            SelectionCriteria()
        html = (ROOT / "src/rfi/admin/linux_mailing_lists.html").read_text(encoding="utf-8")
        self.assertIn("Create and test stream", html)
        self.assertIn("Reload saved streams", html)
        self.assertNotIn(">Refresh<", html)
        self.assertNotIn("placeholder=", html)
        self.assertNotIn('name="stream_id"', html)
        self.assertIn("class=\"help\"", html)
        self.assertIn("confirm('Reloading saved streams", html)
        self.assertNotIn("source-reconciliation", html)
        self.assertNotIn("Reconcile unused governed source", html)


class FakeResponse:
    def __init__(self, content: bytes) -> None:
        self.content = content
        self.headers: dict[str, str] = {}

    def __enter__(self) -> FakeResponse:
        return self

    def __exit__(self, *_args: object) -> None:
        return None

    def read(self, limit: int) -> bytes:
        return self.content[:limit]


class LoreAtomCase(unittest.TestCase):
    def test_live_adapter_parses_bounded_search_probe_and_thread_relationships(self) -> None:
        search = b'''<?xml version="1.0"?><feed xmlns="http://www.w3.org/2005/Atom">
          <title>search</title><entry>
            <link href="https://lore.kernel.org/linux-block/seed@example.com/"/>
          </entry>
        </feed>'''
        probe = b'''<?xml version="1.0"?><feed xmlns="http://www.w3.org/2005/Atom">
          <title>linux-block archive</title><updated>2026-07-20T00:00:00Z</updated></feed>'''
        thread = b'''<?xml version="1.0"?><feed xmlns="http://www.w3.org/2005/Atom"
          xmlns:thr="http://purl.org/syndication/thread/1.0"><title>thread</title>
          <entry><link href="https://lore.kernel.org/linux-block/root@example.com/"/></entry>
          <entry><link href="https://lore.kernel.org/linux-block/seed@example.com/"/>
          <thr:in-reply-to href="https://lore.kernel.org/linux-block/root@example.com/"/></entry>
        </feed>'''

        def opener(request: Any, **_kwargs: Any) -> FakeResponse:
            url = request.full_url
            if url.endswith("new.atom"):
                return FakeResponse(probe)
            if url.endswith("t.atom"):
                return FakeResponse(thread)
            return FakeResponse(search)

        source = MailingListSource(
            "linux-block-lore", "linux-block", "Linux block layer",
            "https://lore.kernel.org/linux-block/",
        )
        archive = LoreArchive(source, opener=opener, sleeper=lambda _seconds: None)
        observed = archive.probe()
        self.assertEqual(observed["title"], "linux-block archive")
        seeds, truncated = archive.discover(
            SelectionCriteria(
                date_from="2026-07-19", date_through="2026-07-20",
                topic_terms=("zoned",), subject_terms=("PATCH",),
                participant_terms=("Maintainer",),
            ),
            5,
        )
        self.assertEqual(seeds, ("<seed@example.com>",))
        self.assertFalse(truncated)
        children, more = archive.direct_children("<root@example.com>", 5)
        self.assertEqual(children, ("<seed@example.com>",))
        self.assertFalse(more)


class BrowserWorkflowCase(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.state = Path(self.temporary.name) / "state"
        initialize(self.state)
        self.archive_patch = patch("rfi.admin.server.LoreArchive", archive_factory)
        self.archive_patch.start()
        self.server = create_admin_server(self.state, port=0)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.base = f"http://127.0.0.1:{self.server.server_port}"

    def tearDown(self) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)
        self.archive_patch.stop()
        self.temporary.cleanup()

    def request(
        self, path: str, method: str = "GET", value: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        data = None if value is None else __import__("json").dumps(value).encode()
        request = urllib.request.Request(
            self.base + path, data=data, method=method,
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(request, timeout=5) as response:
            return __import__("json").load(response)

    def test_browser_api_delivers_one_workflow_without_external_source_prerequisite(self) -> None:
        with urllib.request.urlopen(self.base + "/linux-mailing-lists", timeout=5) as response:
            html = response.read().decode()
        self.assertIn("Choose mailing list", html)
        self.assertIn("Define bounded scope", html)
        self.assertIn("Create and test stream", html)
        self.assertIn('/help/linux-mailing-lists#linux-mailing-lists', html)
        initial = self.request("/api/linux-mailing-lists")
        self.assertGreaterEqual(len(initial["catalog"]), 4)
        reviewed = self.request(
            "/api/linux-mailing-lists/review", "POST", draft()
        )
        self.assertEqual(reviewed["stream"]["stream_id"], "linux-block-discussions")
        self.assertEqual(MailingListRepository(self.state).sources(), ())
        validated = self.request(
            "/api/linux-mailing-lists/validate-archive", "POST", draft()
        )
        self.assertTrue(validated["reachable"])
        self.assertEqual(MailingListRepository(self.state).sources(), ())
        created = self.request("/api/linux-mailing-lists/create", "POST", draft())
        self.assertEqual(created["status"], "created")
        stream_id = created["revision"]["stream_id"]
        tested = self.request(
            f"/api/linux-mailing-lists/{stream_id}/test", "POST", {}
        )
        self.assertEqual(tested["status"], "ready")
        self.assertTrue(tested["configuration_ready"])
        self.assertEqual(tested["test_evidence_status"], "complete_connected")
        self.assertTrue(any(item["direct_match"] for item in tested["messages"]))
        self.assertTrue(any(item["context_only"] for item in tested["messages"]))
        after = self.request("/api/linux-mailing-lists")
        self.assertEqual(after["saved"][0]["configuration_status"], "ready")
        self.assertEqual(
            after["saved"][0]["test_evidence_status"], "complete_connected"
        )
        run_id = tested["acquisition"]["run_id"]
        retained = self.request(f"/api/linux-mailing-lists/results/{run_id}")
        self.assertEqual(len(retained["messages"]), len(tested["messages"]))

if __name__ == "__main__":
    unittest.main()
