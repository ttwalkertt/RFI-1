from __future__ import annotations

import base64
import io
import json
import tempfile
import threading
import unittest
from contextlib import redirect_stdout
from email.utils import parsedate_to_datetime
from http.client import HTTPConnection
from pathlib import Path
from unittest.mock import patch
from xml.etree import ElementTree

from rfi.admin import create_admin_server
from rfi.cli import initialize, main, seed
from rfi.feeds import (
    FeedError,
    FeedPollRequest,
    FeedRunOutcome,
    FeedService,
    HttpResponse,
    parse_feed,
)
from rfi.firms import FirmRepository, sample_firms
from rfi.pull import PullRequest, PullRunRepository, PullWorkflow
from rfi.pull.adapters import RetrievalAdapterRegistry
from rfi.source_profiles import SourceProfileRepository, load_canonical_template
from rfi.storage import RepositoryDatabase
from rfi.acquisition import AcquisitionRepository


FIXTURES = Path(__file__).parents[1] / "fixtures" / "feeds"


class ScriptedTransport:
    def __init__(self, values: dict[str, HttpResponse | Exception]) -> None:
        self.values = values
        self.calls: list[str] = []

    def fetch(self, url: str) -> HttpResponse:
        self.calls.append(url)
        value = self.values[url]
        if isinstance(value, Exception):
            raise value
        return value


def response(path: str, url: str, media_type: str = "application/rss+xml") -> HttpResponse:
    return HttpResponse((FIXTURES / path).read_bytes(), media_type, url, 200)


class Identifiers:
    def __init__(self) -> None:
        self.value = 0

    def __call__(self) -> str:
        self.value += 1
        return f"task067{self.value:04d}"


class Task067Case(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.state = Path(self.temporary.name)
        RepositoryDatabase.initialize(self.state)
        self.rss_url = "https://publisher.example/rss"
        self.atom_url = "https://publisher.example/atom"
        self.transport = ScriptedTransport({
            self.rss_url: response("rss.xml", self.rss_url),
            self.atom_url: response("atom.xml", self.atom_url, "application/atom+xml"),
            "https://content.example/rss-success": response(
                "artifact-a.html", "https://content.example/rss-success", "text/html"
            ),
            "https://content.example/rss-unavailable": FeedError("HTTP 404"),
            "https://content.example/atom-success": response(
                "artifact-a.html", "https://content.example/atom-success", "text/html"
            ),
            "https://alternate.example/manual": response(
                "manual.txt", "https://alternate.example/manual", "text/plain"
            ),
        })
        self.ids = Identifiers()
        self.service = FeedService(
            self.state, transport=self.transport, identifier_factory=self.ids
        )

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def create_feed(self, *, atom: bool = False, firms: list[str] | None = None):
        return self.service.create({
            "display_name": "Atom Fixture" if atom else "RSS Fixture",
            "feed_url": self.atom_url if atom else self.rss_url,
            "enabled": True,
            "notes": "deterministic",
            "firm_ids": firms or [],
        })

    def test_rss_atom_validation_normalization_and_malformed_failure(self) -> None:
        rss = parse_feed((FIXTURES / "rss.xml").read_bytes(), self.rss_url)
        atom = parse_feed((FIXTURES / "atom.xml").read_bytes(), self.atom_url)
        self.assertEqual((rss.format, atom.format), ("rss", "atom"))
        self.assertEqual(rss.entries[0].entry_key, "rss-entry-success")
        self.assertEqual(atom.entries[0].entry_key, "urn:rfi:fixture:atom:success")
        self.assertEqual(atom.entries[0].author, "Atom Author")
        with self.assertRaisesRegex(FeedError, "malformed"):
            parse_feed((FIXTURES / "malformed.xml").read_bytes(), self.rss_url)
        self.assertTrue(self.service.validate(self.rss_url).valid)
        self.assertTrue(self.service.validate(self.atom_url).valid)

    def test_revisioned_registry_associations_and_retirement_preserve_facts(self) -> None:
        firms = FirmRepository.initialize(self.state / "firm-catalog")
        firms.create(sample_firms()[0])
        created = self.create_feed(firms=[sample_firms()[0].firm_id])
        self.service.poll(FeedPollRequest((created.feed_id,), trigger="test"))
        observed_before = self.service.repository.export_items()
        updated = self.service.update(created.feed_id, {
            "display_name": "Edited RSS Fixture", "feed_url": self.rss_url,
            "enabled": False, "notes": "edited", "firm_ids": [],
        }, created.revision_id)
        self.assertEqual(updated.revision_number, 2)
        self.assertEqual(len(self.service.repository.history(created.feed_id)), 2)
        retired = self.service.retire(created.feed_id, updated.revision_id)
        self.assertEqual(retired.lifecycle_status, "retired")
        self.assertEqual(self.service.repository.list(), ())
        self.assertEqual(len(self.service.repository.history(created.feed_id)), 3)
        self.assertEqual(self.service.repository.export_items(), observed_before)

    def test_malformed_feed_is_partial_and_does_not_interrupt_other_feeds(self) -> None:
        bad = self.create_feed()
        self.create_feed(atom=True)
        self.transport.values[self.rss_url] = response("malformed.xml", self.rss_url)
        result = self.service.poll(FeedPollRequest(trigger="test"))
        self.assertEqual(result.outcome, FeedRunOutcome.PARTIAL)
        self.assertEqual(result.summary["feeds_failed"], 1)
        self.assertEqual(result.summary["feeds_succeeded"], 1)
        failed = next(item for item in result.feeds if item["feed_id"] == bad.feed_id)
        self.assertEqual(failed["status"], "failed")

    def test_poll_continues_after_unavailable_and_persists_authoritative_history(self) -> None:
        self.create_feed()
        self.create_feed(atom=True)
        result = self.service.poll(FeedPollRequest(trigger="test"))
        self.assertEqual(result.outcome, FeedRunOutcome.COMPLETED_WITH_UNAVAILABLE)
        self.assertEqual(result.summary["feeds_succeeded"], 2)
        self.assertEqual(result.summary["artifacts_retained"], 2)
        self.assertEqual(result.summary["tombstones_created"], 1)
        unavailable = self.service.repository.tombstones("unresolved")
        self.assertEqual(unavailable[0]["entry"]["entry_key"], "rss-entry-unavailable")
        self.assertEqual(len(self.service.repository.runs()), 1)
        reopened = FeedService(self.state, transport=self.transport)
        self.assertEqual(reopened.repository.run(result.run_id), result.to_dict())

    def test_unchanged_reordering_material_update_and_duplicate_content(self) -> None:
        feed = self.create_feed()
        first = self.service.poll(FeedPollRequest((feed.feed_id,), trigger="test"))
        second = self.service.poll(FeedPollRequest((feed.feed_id,), trigger="test"))
        self.assertEqual(second.outcome, FeedRunOutcome.COMPLETED_WITH_UNAVAILABLE)
        self.assertEqual(second.summary["entries_unchanged"], 2)
        self.assertEqual(second.summary["entries_unavailable"], 1)
        self.assertEqual(second.summary["acquisition_requests"], 0)
        self.transport.values[self.rss_url] = response("rss-updated.xml", self.rss_url)
        updated = self.service.poll(FeedPollRequest((feed.feed_id,), trigger="test"))
        self.assertEqual(updated.summary["entries_updated"], 1)
        self.assertEqual(updated.summary["artifacts_retained"], 1)
        self.assertEqual(updated.feeds[0]["entry_results"][0]["acquisition_outcome"], "duplicate")
        self.assertEqual(first.summary["artifacts_retained"], 1)

    def test_dismiss_restore_retry_and_manual_upload_fulfillment(self) -> None:
        self.create_feed()
        self.service.poll(FeedPollRequest(trigger="test"))
        tombstone = self.service.repository.tombstones("unresolved")[0]
        dismissed = self.service.repository.set_tombstone_status(
            tombstone["tombstone_id"], "dismissed", "2026-08-06T00:00:00+00:00"
        )
        self.assertEqual(dismissed["status"], "dismissed")
        restored = self.service.repository.set_tombstone_status(
            tombstone["tombstone_id"], "unresolved", "2026-08-06T00:01:00+00:00"
        )
        self.assertEqual(restored["status"], "unresolved")
        retried = self.service.retry(tombstone["tombstone_id"])
        self.assertEqual(retried.summary["tombstones_updated"], 1)
        content = (FIXTURES / "manual.txt").read_bytes()
        fulfilled = self.service.fulfill_upload(
            tombstone["tombstone_id"], base64.b64encode(content).decode(), "text/plain"
        )
        self.assertEqual(fulfilled["status"], "fulfilled")
        persisted = self.service.repository.tombstone(tombstone["tombstone_id"])
        self.assertEqual(persisted["status"], "fulfilled")
        self.assertGreaterEqual(len(persisted["attempts"]), 2)
        self.assertEqual(persisted["fulfillment_attempts"][-1]["outcome"], "fulfilled")

    def test_alternate_url_and_duplicate_manual_fulfillment_link_canonical_bytes(self) -> None:
        rss = b"""<rss><channel><title>Two</title>
          <item><guid>x1</guid><title>X1</title><link>https://content.example/x1</link></item>
          <item><guid>x2</guid><title>X2</title><link>https://content.example/x2</link></item>
        </channel></rss>"""
        url = "https://publisher.example/two"
        self.transport.values[url] = HttpResponse(rss, "application/rss+xml", url, 200)
        self.transport.values["https://content.example/x1"] = FeedError("HTTP 404")
        self.transport.values["https://content.example/x2"] = FeedError("HTTP 404")
        self.service.create({"display_name":"Two", "feed_url":url, "enabled":True,
                             "notes":"", "firm_ids":[]})
        self.service.poll(FeedPollRequest(trigger="test"))
        tombstones = self.service.repository.tombstones("unresolved")
        first = self.service.fulfill_url(
            tombstones[0]["tombstone_id"], "https://alternate.example/manual"
        )
        second = self.service.fulfill_upload(
            tombstones[1]["tombstone_id"],
            base64.b64encode((FIXTURES / "manual.txt").read_bytes()).decode(), "text/plain"
        )
        self.assertEqual(first["artifact_id"], second["artifact_id"])
        self.assertTrue(second["duplicate_content"])

    def test_failed_manual_candidate_preserves_unresolved_tombstone(self) -> None:
        self.create_feed()
        self.service.poll(FeedPollRequest(trigger="test"))
        tombstone = self.service.repository.tombstones("unresolved")[0]
        with self.assertRaises(FeedError):
            self.service.fulfill_upload(tombstone["tombstone_id"], "not-base64", "text/plain")
        current = self.service.repository.tombstone(tombstone["tombstone_id"])
        self.assertEqual(current["status"], "unresolved")
        self.assertEqual(current["fulfillment_attempts"][-1]["outcome"], "failed")

    def test_rss_export_is_valid_and_marks_retained_and_unavailable(self) -> None:
        self.create_feed()
        self.service.poll(FeedPollRequest(trigger="test"))
        root = ElementTree.fromstring(self.service.rss_export())
        items = root.findall("./channel/item")
        self.assertEqual(len(items), 2)
        availability = [
            item.find("{https://rfi.local/ns/feed/1}availability").text
            for item in items
        ]
        self.assertEqual(set(availability), {"retained", "unavailable"})
        dates = {
            item.findtext("title"): item.findtext("pubDate") for item in items
        }
        self.assertEqual(
            dates,
            {
                "Available RSS artifact": "Wed, 06 Aug 2025 12:00:00 +0000",
                "Unavailable RSS artifact": "Wed, 06 Aug 2025 13:00:00 +0000",
            },
        )
        for value in dates.values():
            self.assertEqual(parsedate_to_datetime(value).isoformat(), value.replace(
                "Wed, 06 Aug 2025 ", "2025-08-06T"
            ).replace(" +0000", "+00:00"))

    def test_startup_recovers_stale_running_run_before_new_poll(self) -> None:
        terminal = {
            "schema_version": 1,
            "run_id": "feedrun-terminal",
            "trigger": "ui",
            "requested_at": "2026-08-05T08:00:00+00:00",
            "completed_at": "2026-08-05T08:01:00+00:00",
            "outcome": "completed",
            "selected_feed_ids": [],
            "firm_ids": [],
            "parent_pull_run_id": None,
            "summary": {"feeds_selected": 0},
            "feeds": [],
            "diagnostics": [],
            "termination_reason": "selected feeds exhausted",
        }
        self.service.repository.create_run({**terminal, "completed_at": "", "outcome": "running"})
        self.service.repository.save_run(terminal)
        terminal_before = self.service.repository.run(terminal["run_id"])
        stale = {
            "schema_version": 1,
            "run_id": "feedrun-stale",
            "trigger": "firm-pull",
            "requested_at": "2026-08-06T10:00:00+00:00",
            "completed_at": "",
            "outcome": "running",
            "selected_feed_ids": ["feed-original"],
            "firm_ids": ["firm-original"],
            "parent_pull_run_id": "pull-original",
            "summary": {"feeds_selected": 1, "entries_observed": 2},
            "feeds": [{"feed_id": "feed-original", "status": "completed"}],
            "diagnostics": [{"category": "retained", "message": "prior detail"}],
            "termination_reason": "running",
        }
        self.service.repository.create_run(stale)

        recovery_at = "2026-08-06T11:00:00+00:00"
        restarted = FeedService(
            self.state,
            transport=self.transport,
            clock=lambda: recovery_at,
            identifier_factory=Identifiers(),
        )
        recovered = restarted.repository.run(stale["run_id"])
        self.assertEqual(recovered["run_id"], stale["run_id"])
        for key in (
            "trigger", "requested_at", "selected_feed_ids", "firm_ids",
            "parent_pull_run_id", "summary", "feeds",
        ):
            self.assertEqual(recovered[key], stale[key])
        self.assertEqual(recovered["outcome"], "canceled")
        self.assertEqual(recovered["completed_at"], recovery_at)
        self.assertEqual(recovered["recovered_at"], recovery_at)
        self.assertEqual(recovered["diagnostics"][0], stale["diagnostics"][0])
        self.assertEqual(recovered["diagnostics"][-1]["category"], "startup_recovery")
        self.assertIn("prior process ended", recovered["diagnostics"][-1]["message"])
        self.assertEqual(restarted.repository.run(terminal["run_id"]), terminal_before)

        subsequent = restarted.poll(FeedPollRequest(trigger="cron"))
        self.assertEqual(subsequent.outcome, FeedRunOutcome.COMPLETED)
        recovered_before_repeat = restarted.repository.run(stale["run_id"])
        terminal_before_repeat = restarted.repository.run(terminal["run_id"])
        FeedService(
            self.state,
            transport=self.transport,
            clock=lambda: "2026-08-06T12:00:00+00:00",
        )
        self.assertEqual(
            restarted.repository.run(stale["run_id"]), recovered_before_repeat
        )
        self.assertEqual(
            restarted.repository.run(terminal["run_id"]), terminal_before_repeat
        )

    def test_manual_fulfillment_preview_is_advisory_and_extracts_metadata(self) -> None:
        self.create_feed()
        self.service.poll(FeedPollRequest(trigger="test"))
        tombstone = self.service.repository.tombstones("unresolved")[0]
        before = self.service.repository.tombstone(tombstone["tombstone_id"])
        content = (FIXTURES / "artifact-a.html").read_bytes()
        upload = self.service.preview_upload(
            tombstone["tombstone_id"],
            base64.b64encode(content).decode(),
            "application/octet-stream",
            "folder/report.html",
        )
        self.assertEqual(upload.filename, "report.html")
        self.assertEqual(upload.media_type, "text/html")
        self.assertEqual(upload.byte_count, len(content))
        self.assertEqual(upload.title, "Fixture Artifact A")
        self.assertEqual(upload.publication_date, "2025-08-06T12:00:00Z")
        plain_content = (FIXTURES / "manual.txt").read_bytes()
        plain = self.service.preview_upload(
            tombstone["tombstone_id"],
            base64.b64encode(plain_content).decode(),
            "text/plain",
            "manual.txt",
        )
        self.assertEqual(plain.media_type, "text/plain")
        self.assertIsNone(plain.title)
        self.assertIsNone(plain.publication_date)

        alternate = self.service.preview_url(
            tombstone["tombstone_id"], "https://content.example/rss-success"
        )
        self.assertEqual(alternate.filename, "rss-success")
        self.assertEqual(alternate.source_url, "https://content.example/rss-success")
        self.assertEqual(alternate.media_type, "text/html")
        self.assertEqual(alternate.byte_count, len(content))
        self.assertEqual(alternate.title, "Fixture Artifact A")
        self.assertEqual(alternate.publication_date, "2025-08-06T12:00:00Z")
        self.assertEqual(
            self.service.repository.tombstone(tombstone["tombstone_id"]), before
        )

    def test_overlap_is_rejected(self) -> None:
        self.service.repository.create_run({
            "run_id":"feedrun-held", "trigger":"test", "requested_at":"2026-08-06",
            "completed_at":"", "outcome":"running", "selected_feed_ids":[], "firm_ids":[],
            "summary":{}, "feeds":[], "diagnostics":[], "termination_reason":"running",
        })
        with self.assertRaisesRegex(FeedError, "already running"):
            self.service.poll(FeedPollRequest(trigger="test"))

    def test_firm_pull_polls_each_associated_feed_once_and_embeds_feed_run(self) -> None:
        firms = FirmRepository.initialize(self.state / "firm-catalog")
        firm = sample_firms()[0]
        firms.create(firm)
        template = load_canonical_template()
        profiles = SourceProfileRepository.initialize(self.state / "source-profiles", template)
        feed = self.create_feed(firms=[firm.firm_id])
        workflow = PullWorkflow(
            firms, profiles, template, AcquisitionRepository(self.state / "acquisition"),
            RetrievalAdapterRegistry(()), PullRunRepository(self.state / "pull-workflows"),
            identifier_factory=Identifiers(), feeds=self.service,
        )
        result = workflow.run(PullRequest((firm.firm_id,), False))
        self.assertEqual(result.feed_run["selected_feed_ids"], [feed.feed_id])
        self.assertEqual(result.feed_run["parent_pull_run_id"], result.run_id)
        self.assertEqual(result.feed_run["summary"]["feeds_selected"], 1)
        # One editor validation plus one firm-pull poll.
        self.assertEqual(self.transport.calls.count(self.rss_url), 2)


class Task067CliApiCase(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.state = Path(self.temporary.name)
        with redirect_stdout(io.StringIO()):
            initialize(self.state)
            seed(self.state)
        self.rss_url = "https://publisher.example/rss"
        self.mapping = {
            self.rss_url: response("rss.xml", self.rss_url),
            "https://content.example/rss-success": response(
                "artifact-a.html", "https://content.example/rss-success", "text/html"
            ),
            "https://content.example/rss-unavailable": FeedError("HTTP 404"),
        }
        self.transport = ScriptedTransport(self.mapping)
        FeedService(self.state, transport=self.transport, identifier_factory=Identifiers()).create({
            "display_name":"RSS", "feed_url":self.rss_url, "enabled":True,
            "notes":"", "firm_ids":[],
        })

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def test_cli_human_and_json_use_authoritative_result(self) -> None:
        with patch("rfi.feeds.service.FeedHttpTransport.fetch", self.transport.fetch):
            human = io.StringIO()
            with redirect_stdout(human):
                code = main(["feeds", "poll", "--state", str(self.state)])
            self.assertEqual(code, 0)
            self.assertIn("completed_with_unavailable_entries", human.getvalue())
            structured = io.StringIO()
            with redirect_stdout(structured):
                code = main(["feeds", "poll", "--state", str(self.state), "--json"])
            self.assertEqual(code, 0)
            value = json.loads(structured.getvalue())
            self.assertEqual(value, FeedService(self.state).repository.runs(1)[0])

    def test_admin_page_api_history_and_rss_endpoint(self) -> None:
        server = create_admin_server(self.state, port=0)
        server.feed_service = FeedService(
            self.state, transport=self.transport, identifier_factory=Identifiers()
        )
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            connection = HTTPConnection("127.0.0.1", server.server_address[1], timeout=5)
            connection.request("GET", "/feeds")
            page = connection.getresponse()
            html = page.read().decode()
            self.assertEqual(page.status, 200)
            self.assertIn("Unavailable-entry work queue", html)
            self.assertIn("Export All as RSS", html)
            self.assertIn("Preview candidate", html)
            self.assertIn("Advisory candidate metadata", html)
            self.assertIn('data-enabled="', html)
            self.assertIn("toggleEnabled", html)
            self.assertIn("Artifacts obtained", html)
            self.assertIn("Structured JSON for debugging", html)
            self.assertIn("runs-panel", html)
            self.assertNotIn("No firm associations", html)
            feed = server.feed_service.repository.list()[0]
            toggle = {
                "display_name": feed.display_name,
                "feed_url": feed.feed_url,
                "enabled": False,
                "notes": feed.notes,
                "firm_ids": list(feed.firm_ids),
                "expected_revision_id": feed.revision_id,
            }
            connection.request(
                "PUT", f"/api/feeds/{feed.feed_id}", body=json.dumps(toggle),
                headers={"Content-Type": "application/json"},
            )
            disabled_response = connection.getresponse()
            disabled = json.loads(disabled_response.read())
            self.assertEqual(disabled_response.status, 200)
            self.assertFalse(disabled["enabled"])
            toggle.update(enabled=True, expected_revision_id=disabled["revision_id"])
            connection.request(
                "PUT", f"/api/feeds/{feed.feed_id}", body=json.dumps(toggle),
                headers={"Content-Type": "application/json"},
            )
            enabled_response = connection.getresponse()
            enabled = json.loads(enabled_response.read())
            self.assertEqual(enabled_response.status, 200)
            self.assertTrue(enabled["enabled"])
            connection.request("POST", "/api/feeds/poll", body=b'{"feed_ids":[]}',
                               headers={"Content-Type":"application/json"})
            polled = connection.getresponse()
            value = json.loads(polled.read())
            self.assertEqual(polled.status, 200)
            self.assertIn("feeds", value)
            tombstone = server.feed_service.repository.tombstones("unresolved")[0]
            content = (FIXTURES / "artifact-a.html").read_bytes()
            connection.request(
                "POST",
                f"/api/feeds/unavailable/{tombstone['tombstone_id']}/preview-upload",
                body=json.dumps({
                    "content_base64": base64.b64encode(content).decode(),
                    "media_type": "application/octet-stream",
                    "filename": "review.html",
                }),
                headers={"Content-Type": "application/json"},
            )
            preview_response = connection.getresponse()
            preview = json.loads(preview_response.read())
            self.assertEqual(preview_response.status, 200)
            self.assertEqual(preview["filename"], "review.html")
            self.assertEqual(preview["media_type"], "text/html")
            self.assertEqual(preview["title"], "Fixture Artifact A")
            self.assertEqual(preview["publication_date"], "2025-08-06T12:00:00Z")
            connection.request("GET", "/api/feeds/runs")
            history = json.loads(connection.getresponse().read())
            self.assertEqual(history["items"][0], value)
            connection.request("GET", "/api/feed-items.rss")
            exported = connection.getresponse()
            content = exported.read()
            self.assertEqual(
                exported.getheader("Content-Type"),
                "application/rss+xml; charset=utf-8",
            )
            ElementTree.fromstring(content)
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)


if __name__ == "__main__":
    unittest.main()
