"""Acceptance coverage for confirmed-unavailable Lore ancestor tombstones."""

from __future__ import annotations

import io
import tempfile
import unittest
from email.message import Message
from pathlib import Path
from typing import Any
from urllib.error import HTTPError

from rfi.mailing_lists import (
    AcquisitionLimits,
    ArchiveMessage,
    ConnectivityState,
    FixtureMailingListArchive,
    LINUX_BLOCK_SOURCE,
    LoreArchive,
    MailingListAcquisitionService,
    MailingListError,
    MailingListQueryService,
    MailingListRepository,
    SelectionCriteria,
)
from rfi.storage import RepositoryDatabase


def raw_message(message_id: str, parent: str | None = None) -> bytes:
    headers = [
        f"Message-ID: {message_id}",
        "Subject: Re: confirmed unavailable ancestor",
        "From: Test <test@example.com>",
        "Date: Wed, 22 Jul 2026 12:00:00 +0000",
    ]
    if parent:
        headers.append(f"In-Reply-To: {parent}")
    return ("\r\n".join(headers) + "\r\n\r\nRetained child\r\n").encode()


class ConfirmedMissingArchive(FixtureMailingListArchive):
    def __init__(self, child: str, parent: str) -> None:
        super().__init__({
            child: ArchiveMessage(raw_message(child, parent), "fixture:retained-child")
        })
        self.parent = parent
        self.parent_enumerations = 0

    def fetch(self, external_message_id: str) -> ArchiveMessage:
        if external_message_id == self.parent:
            token = external_message_id.strip("<>")
            raise MailingListError(
                "archive_message_not_found",
                "confirmed absent from Lore",
                details={
                    "message_id": external_message_id,
                    "attempts": [
                        {
                            "location": f"https://lore.kernel.org/linux-block/{token}/raw",
                            "http_status": 404,
                        },
                        {
                            "location": f"https://lore.kernel.org/all/{token}/raw",
                            "http_status": 404,
                        },
                    ],
                },
            )
        return super().fetch(external_message_id)

    def direct_children(
        self, external_message_id: str, limit: int
    ) -> tuple[tuple[str, ...], bool]:
        if external_message_id == self.parent:
            self.parent_enumerations += 1
        return super().direct_children(external_message_id, limit)


class TombstoneAcquisitionCase(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.state = Path(self.temporary.name)
        RepositoryDatabase.initialize(self.state)
        self.repository = MailingListRepository(self.state)
        self.repository.configure_source(LINUX_BLOCK_SOURCE)
        self.child = "<task030-child@kernel.example>"
        self.parent = "<task030-missing-parent@kernel.example>"
        self.archive = ConfirmedMissingArchive(self.child, self.parent)
        self.run_ids = iter(("mailrun-task030-first", "mailrun-task030-second"))
        self.service = MailingListAcquisitionService(
            self.repository,
            self.archive,
            clock=lambda: "2026-07-22T12:00:00+00:00",
            identifiers=self.run_ids.__next__,
        )
        self.query = MailingListQueryService(self.repository)

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def acquire(self):
        return self.service.acquire(
            LINUX_BLOCK_SOURCE.source_id,
            SelectionCriteria(message_ids=(self.child,)),
            AcquisitionLimits(seed_limit=1, context_limit=5, descendant_depth=1),
            coverage_batch_id="task030-window",
        )

    def test_tombstone_closes_path_advances_coverage_and_rebuilds(self) -> None:
        manifest = self.acquire()
        self.assertEqual(manifest.state, ConnectivityState.CONNECTED)
        self.assertEqual(manifest.run_status.value, "succeeded")
        self.assertTrue(manifest.required_ancestry_complete)
        self.assertTrue(manifest.descendant_policy_complete)
        self.assertTrue(manifest.coverage_complete)
        self.assertEqual(manifest.tombstone_message_ids, (self.parent,))
        self.assertEqual(manifest.message_count, 2)
        self.assertEqual(self.archive.parent_enumerations, 0)

        messages = {
            item.summary.external_message_id: item
            for item in self.query.acquisition_messages(manifest.run_id)
        }
        tombstone = messages[self.parent]
        self.assertTrue(tombstone.summary.is_tombstone)
        self.assertEqual(tombstone.source_link, "")
        self.assertEqual(tombstone.summary.depth, 0)
        self.assertEqual(messages[self.child].summary.depth, 1)
        self.assertEqual(
            self.query.ancestors(messages[self.child].summary.message_key)[0].message_key,
            tombstone.summary.message_key,
        )
        content = self.query.content(tombstone.summary.message_key)
        self.assertEqual(
            content.media_type, "application/vnd.rfi.mailing-list-tombstone+json"
        )
        self.assertIn(b'"content_synthesized":false', content.content)
        self.assertEqual(self.repository.validate_connectivity()["result"], "PASS")

        before = [
            (item.message_key, item.depth, item.is_tombstone)
            for item in self.query.projection(
                self.query.discussions(LINUX_BLOCK_SOURCE.source_id)[0].discussion_id
            ).messages
        ]
        self.service.rebuild()
        after = [
            (item.message_key, item.depth, item.is_tombstone)
            for item in self.query.projection(
                self.query.discussions(LINUX_BLOCK_SOURCE.source_id)[0].discussion_id
            ).messages
        ]
        self.assertEqual(after, before)

        repeated = self.acquire()
        self.assertEqual(repeated.artifact_count_created, 0)
        self.assertEqual(repeated.idempotent_messages, 2)
        self.assertEqual(repeated.tombstone_message_ids, (self.parent,))

    def test_non_confirmed_failure_remains_incomplete(self) -> None:
        class RejectedArchive(ConfirmedMissingArchive):
            def fetch(inner_self, external_message_id: str) -> ArchiveMessage:
                if external_message_id == inner_self.parent:
                    raise MailingListError(
                        "archive_request_rejected", "Lore returned HTTP 403"
                    )
                return super().fetch(external_message_id)

        service = MailingListAcquisitionService(
            self.repository,
            RejectedArchive(self.child, self.parent),
            identifiers=lambda: "mailrun-task030-rejected",
        )
        manifest = service.acquire(
            LINUX_BLOCK_SOURCE.source_id,
            SelectionCriteria(message_ids=(self.child,)),
            AcquisitionLimits(seed_limit=1, context_limit=5, descendant_depth=0),
        )
        self.assertEqual(manifest.state, ConnectivityState.INCOMPLETE)
        self.assertFalse(manifest.coverage_complete)
        self.assertEqual(manifest.tombstone_message_ids, ())


class LoreClassificationCase(unittest.TestCase):
    @staticmethod
    def error(url: str, status: int) -> HTTPError:
        return HTTPError(url, status, "test response", Message(), io.BytesIO(b"Not Found"))

    def test_two_404_responses_are_classified_as_confirmed_absence(self) -> None:
        requested: list[str] = []

        def opener(request: Any, **_kwargs: Any):
            requested.append(request.full_url)
            raise self.error(request.full_url, 404)

        archive = LoreArchive(
            LINUX_BLOCK_SOURCE, opener=opener, sleeper=lambda _seconds: None
        )
        with self.assertRaises(MailingListError) as raised:
            archive.fetch("<missing@kernel.example>")
        self.assertEqual(raised.exception.code, "archive_message_not_found")
        self.assertEqual(
            [item["http_status"] for item in raised.exception.details["attempts"]],
            [404, 404],
        )
        self.assertIn("/linux-block/", requested[0])
        self.assertIn("/all/", requested[1])

    def test_case_sensitive_lore_path_is_recovered_from_exact_message_id_search(self) -> None:
        canonical = "<DM4PR11MB5375ABC@dm4pr11mb5375.namprd11.prod.outlook.com>"
        exact_token = "DM4PR11MB5375ABC@DM4PR11MB5375.namprd11.prod.outlook.com"
        exact_location = f"https://lore.kernel.org/linux-block/{exact_token}/raw"
        exact_thread = f"https://lore.kernel.org/linux-block/{exact_token}/t.atom"
        search = f'''<?xml version="1.0"?><feed xmlns="http://www.w3.org/2005/Atom">
          <title>exact Message-ID search</title><entry>
            <link href="https://lore.kernel.org/linux-block/{exact_token}/"/>
          </entry></feed>'''.encode()
        raw = raw_message(f"<{exact_token}>")
        thread = f'''<?xml version="1.0"?><feed
          xmlns="http://www.w3.org/2005/Atom"
          xmlns:thr="http://purl.org/syndication/thread/1.0">
          <title>case-sensitive thread</title>
          <entry><link href="https://lore.kernel.org/linux-block/child@example.com/"/>
          <thr:in-reply-to href="https://lore.kernel.org/linux-block/{exact_token}/"/>
          </entry></feed>'''.encode()
        requested: list[str] = []

        def opener(request: Any, **_kwargs: Any):
            requested.append(request.full_url)
            if request.full_url == exact_location:
                return type("Response", (), {
                    "headers": {},
                    "__enter__": lambda self: self,
                    "__exit__": lambda self, *_args: None,
                    "read": lambda self, limit: raw[:limit],
                })()
            if request.full_url == exact_thread:
                return type("Response", (), {
                    "headers": {},
                    "__enter__": lambda self: self,
                    "__exit__": lambda self, *_args: None,
                    "read": lambda self, limit: thread[:limit],
                })()
            if "?q=" in request.full_url:
                return type("Response", (), {
                    "headers": {},
                    "__enter__": lambda self: self,
                    "__exit__": lambda self, *_args: None,
                    "read": lambda self, limit: search[:limit],
                })()
            raise self.error(request.full_url, 404)

        archive = LoreArchive(
            LINUX_BLOCK_SOURCE, opener=opener, sleeper=lambda _seconds: None
        )
        observed = archive.fetch(canonical)

        self.assertEqual(observed.raw, raw)
        self.assertEqual(observed.location, exact_location)
        self.assertIn(exact_location, requested)

        restarted = LoreArchive(
            LINUX_BLOCK_SOURCE, opener=opener, sleeper=lambda _seconds: None
        )
        children, has_more = restarted.direct_children(canonical, 5)
        self.assertEqual(children, ("<child@example.com>",))
        self.assertFalse(has_more)
        self.assertIn(exact_thread, requested)

    def test_404_then_403_is_not_confirmed_absence(self) -> None:
        calls = 0

        def opener(request: Any, **_kwargs: Any):
            nonlocal calls
            calls += 1
            raise self.error(request.full_url, 404 if calls == 1 else 403)

        archive = LoreArchive(
            LINUX_BLOCK_SOURCE, opener=opener, sleeper=lambda _seconds: None
        )
        with self.assertRaises(MailingListError) as raised:
            archive.fetch("<missing@kernel.example>")
        self.assertEqual(raised.exception.code, "archive_request_rejected")

    def test_advertised_list_link_still_uses_cross_archive_fallback(self) -> None:
        message_id = "<cross-list@kernel.example>"
        token = message_id.strip("<>")
        list_location = f"https://lore.kernel.org/linux-block/{token}/raw"
        all_location = f"https://lore.kernel.org/all/{token}/raw"
        raw = raw_message(message_id)
        requested: list[str] = []

        def opener(request: Any, **_kwargs: Any):
            requested.append(request.full_url)
            if request.full_url == all_location:
                return type("Response", (), {
                    "headers": {},
                    "__enter__": lambda self: self,
                    "__exit__": lambda self, *_args: None,
                    "read": lambda self, limit: raw[:limit],
                })()
            raise self.error(request.full_url, 404)

        archive = LoreArchive(
            LINUX_BLOCK_SOURCE, opener=opener, sleeper=lambda _seconds: None
        )
        self.assertEqual(
            archive._message_id_from_url(list_location.removesuffix("raw")),
            message_id,
        )

        observed = archive.fetch(message_id)

        self.assertEqual(observed.raw, raw)
        self.assertEqual(observed.location, all_location)
        self.assertEqual(observed.fallback_archive_url, "https://lore.kernel.org/all/")
        self.assertIn(list_location, requested)
        self.assertIn(all_location, requested)


class OperatorDisclosureCase(unittest.TestCase):
    def test_page_distinguishes_tombstones_from_messages(self) -> None:
        html = (
            Path(__file__).resolve().parents[1]
            / "src/rfi/admin/linux_mailing_lists.html"
        ).read_text(encoding="utf-8")
        self.assertIn("Connected with unavailable ancestors", html)
        self.assertIn("Confirmed Lore 404 tombstone", html)
        self.assertIn("No message body was synthesized", html)


if __name__ == "__main__":
    unittest.main()
