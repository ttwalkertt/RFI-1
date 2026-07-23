"""Focused TASK-031 durable Lore relationship-continuation evidence."""

from __future__ import annotations

import tempfile
import unittest
from datetime import date
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from rfi.mailing_lists import (
    AcquisitionLimits,
    ArchiveMessage,
    FixtureMailingListArchive,
    LINUX_BLOCK_SOURCE,
    MailingListAcquisitionService,
    MailingListError,
    MailingListQueryService,
    MailingListRepository,
    MailingListSourceService,
    LinuxMailingListWorkflowService,
    LoreArchive,
    RelationshipAcquisitionStatus,
    SelectionCriteria,
)
from rfi.storage import RepositoryDatabase
from rfi.firms import FirmRepository
from rfi.streams import StreamRepository, StreamService
from tests.test_task028 import draft
from rfi.cli import parser as cli_parser
from tests.test_task023 import raw_message


class PagedTrackingArchive(FixtureMailingListArchive):
    """Force one relationship identifier per provider page and retain call evidence."""

    def __init__(self, messages, calls, *, fail_once=False):
        super().__init__(messages)
        self.calls = calls
        self.fail_once = fail_once

    def direct_children(self, external_message_id: str, limit: int):
        return self.direct_children_page(external_message_id, limit, 0)

    def direct_children_page(self, external_message_id: str, limit: int, offset: int):
        self.calls.append((external_message_id, offset, min(limit, 1)))
        if self.fail_once:
            self.fail_once = False
            raise MailingListError("fixture_provider_failure", "provider failed", retryable=True)
        return super().direct_children_page(external_message_id, min(limit, 1), offset)


class WindowedSeedArchive(PagedTrackingArchive):
    def __init__(self, messages, calls, seeds):
        super().__init__(messages, calls)
        self.seeds = seeds

    def probe(self):
        return {"status": "reachable", "archive": "task031-fixture"}

    def discover(self, criteria, limit):
        return self.discover_page(criteria, limit, 0)

    def discover_page(self, criteria, limit, offset):
        if criteria.date_from != "2026-05-01":
            return (), False
        page = self.seeds[offset:offset + limit]
        return tuple(page), offset + len(page) < len(self.seeds)


def large_discussion():
    root = "<task031-root@kernel.example>"
    ancestor_two = "<task031-a2@kernel.example>"
    ancestor_one = "<task031-a1@kernel.example>"
    seed = "<task031-seed@kernel.example>"
    shared_seed = "<task031-shared-seed@kernel.example>"
    reply_one = "<task031-r1@kernel.example>"
    reply_two = "<task031-r2@kernel.example>"
    reply_three = "<task031-r3@kernel.example>"
    parent = {
        ancestor_two: root,
        ancestor_one: ancestor_two,
        seed: ancestor_one,
        shared_seed: root,
        reply_one: root,
        reply_two: reply_one,
        reply_three: root,
    }
    messages = {
        message_id: ArchiveMessage(
            raw_message(
                message_id,
                f"[PATCH] TASK-031 {index}",
                parent.get(message_id),
                body="resumable relationship fixture",
            ),
            f"fixture:{message_id}",
        )
        for index, message_id in enumerate(
            (root, ancestor_two, ancestor_one, seed, shared_seed,
             reply_one, reply_two, reply_three)
        )
    }
    return messages, root, seed, shared_seed


class DurableContinuationCase(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.state = Path(self.temporary.name)
        RepositoryDatabase.initialize(self.state)
        repository = MailingListRepository(self.state)
        repository.configure_source(LINUX_BLOCK_SOURCE)
        self.messages, self.root, self.seed, self.shared_seed = large_discussion()
        self.calls: list[tuple[str, int, int]] = []

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def service(self, run_number: int, *, fail_once: bool = False):
        repository = MailingListRepository(self.state)
        archive = PagedTrackingArchive(self.messages, self.calls, fail_once=fail_once)
        return MailingListAcquisitionService(
            repository,
            archive,
            clock=lambda: f"2026-07-22T00:00:{run_number:02d}+00:00",
            identifiers=lambda: f"mailrun-task031-{run_number:02d}",
        )

    def acquire(self, run_number: int, *, fail_once: bool = False):
        return self.service(run_number, fail_once=fail_once).acquire(
            LINUX_BLOCK_SOURCE.source_id,
            SelectionCriteria(message_ids=(self.seed, self.shared_seed)),
            AcquisitionLimits(seed_limit=2, context_limit=1, descendant_depth=3),
            coverage_batch_id="task031-durable-batch",
        )

    def test_three_plus_runs_restart_depth_first_pagination_and_deduplication(self) -> None:
        manifests = []
        for run_number in range(1, 20):
            manifest = self.acquire(run_number)
            manifests.append(manifest)
            if manifest.relationship_status != RelationshipAcquisitionStatus.CONTINUATION_PENDING:
                break

        self.assertGreaterEqual(len(manifests), 3)
        self.assertEqual(manifests[0].relationship_status, "continuation_pending")
        self.assertFalse(manifests[0].required_ancestry_complete)
        self.assertTrue(any(item.required_ancestry_complete for item in manifests[1:]))
        self.assertIn(manifests[-1].relationship_status, {"complete", "policy_truncated"})
        self.assertTrue(manifests[-1].coverage_complete)
        self.assertTrue(all(item.message_count <= 3 for item in manifests))
        self.assertTrue(all(item.relationship_records_processed <= 1 for item in manifests))

        root_offsets = [offset for parent, offset, _limit in self.calls if parent == self.root]
        self.assertEqual(root_offsets, sorted(root_offsets))
        self.assertEqual(root_offsets, list(dict.fromkeys(root_offsets)))
        self.assertIn(1, root_offsets)

        repository = MailingListRepository(self.state)
        retained = repository.rows(
            "SELECT external_message_id,artifact_id FROM mailing_list_messages "
            "WHERE source_id=? ORDER BY external_message_id",
            (LINUX_BLOCK_SOURCE.source_id,),
        )
        self.assertEqual(len(retained), len(self.messages))
        self.assertEqual(len({item["artifact_id"] for item in retained}), len(self.messages))
        memberships = repository.rows(
            "SELECT external_message_id,count(*) AS uses FROM mailing_list_run_items "
            "GROUP BY external_message_id ORDER BY external_message_id"
        )
        self.assertTrue(all(int(item["uses"]) == 1 for item in memberships))
        discussion = MailingListQueryService(repository).discussions(
            LINUX_BLOCK_SOURCE.source_id
        )[0]
        self.assertEqual(discussion.message_count, len(self.messages))
        self.assertEqual(discussion.connectivity_state.value, "connected")

    def test_cancelled_retry_preserves_prior_frontier_without_a_shadow_run(self) -> None:
        first = self.acquire(1)
        self.assertEqual(first.relationship_status, "continuation_pending")
        repository = MailingListRepository(self.state)
        before = repository.acquisition_run_manifest(first.run_id)["relationship_continuation"]
        with self.assertRaisesRegex(MailingListError, "cancelled"):
            self.service(2).acquire(
                LINUX_BLOCK_SOURCE.source_id,
                SelectionCriteria(message_ids=(self.seed, self.shared_seed)),
                AcquisitionLimits(seed_limit=2, context_limit=1, descendant_depth=3),
                coverage_batch_id="task031-durable-batch",
                cancelled=lambda: True,
            )
        self.assertEqual(len(repository.acquisition_runs(LINUX_BLOCK_SOURCE.source_id)), 1)
        self.assertEqual(
            repository.acquisition_run_manifest(first.run_id)["relationship_continuation"],
            before,
        )
        resumed = self.acquire(2)
        self.assertEqual(resumed.relationship_status, "continuation_pending")

    def test_provider_failure_is_distinct_and_retry_uses_durable_frontier(self) -> None:
        run_number = 1
        while True:
            manifest = self.acquire(run_number)
            run_number += 1
            continuation = manifest.relationship_continuation or {}
            if continuation.get("phase") == "replies":
                break
        failed = self.acquire(run_number, fail_once=True)
        self.assertEqual(failed.relationship_status, "failed")
        self.assertEqual(failed.run_status.value, "partial")
        self.assertFalse(failed.coverage_complete)
        recovered = self.acquire(run_number + 1)
        self.assertNotEqual(recovered.relationship_status, "failed")

    def test_policy_depth_is_terminal_and_not_pending_or_failed(self) -> None:
        repository = MailingListRepository(self.state)
        service = MailingListAcquisitionService(
            repository,
            PagedTrackingArchive(self.messages, self.calls),
            identifiers=lambda: "mailrun-task031-policy",
        )
        manifest = service.acquire(
            LINUX_BLOCK_SOURCE.source_id,
            SelectionCriteria(message_ids=(self.root,)),
            AcquisitionLimits(seed_limit=1, context_limit=10, descendant_depth=1),
            coverage_batch_id="task031-policy-batch",
        )
        self.assertEqual(manifest.relationship_status, "policy_truncated")
        self.assertTrue(manifest.descendant_policy_complete)
        self.assertTrue(manifest.descendant_policy_limited)
        self.assertTrue(manifest.coverage_complete)

    def test_unrelated_incomplete_evidence_does_not_contaminate_later_run(self) -> None:
        orphan = "<task031-unrelated-orphan@kernel.example>"
        missing_parent = "<task031-unrelated-missing@kernel.example>"
        repository = MailingListRepository(self.state)
        incomplete = MailingListAcquisitionService(
            repository,
            FixtureMailingListArchive({
                orphan: ArchiveMessage(
                    raw_message(orphan, "[PATCH] unrelated orphan", missing_parent),
                    "fixture:unrelated-orphan",
                )
            }),
            identifiers=lambda: "mailrun-task031-unrelated-incomplete",
        ).acquire(
            LINUX_BLOCK_SOURCE.source_id,
            SelectionCriteria(message_ids=(orphan,)),
            AcquisitionLimits(seed_limit=1, context_limit=2, descendant_depth=1),
            coverage_batch_id="task031-unrelated-incomplete-batch",
        )
        self.assertEqual(incomplete.state, "incomplete")

        clean_root = "<task031-clean-policy-root@kernel.example>"
        clean_child = "<task031-clean-policy-child@kernel.example>"
        clean_grandchild = "<task031-clean-policy-grandchild@kernel.example>"
        clean_messages = {
            clean_root: ArchiveMessage(
                raw_message(clean_root, "[PATCH] clean policy root"), "fixture:clean-root"
            ),
            clean_child: ArchiveMessage(
                raw_message(clean_child, "Re: [PATCH] clean policy root", clean_root),
                "fixture:clean-child",
            ),
            clean_grandchild: ArchiveMessage(
                raw_message(
                    clean_grandchild,
                    "Re: [PATCH] clean policy root",
                    clean_child,
                ),
                "fixture:clean-grandchild",
            ),
        }
        clean = MailingListAcquisitionService(
            repository,
            FixtureMailingListArchive(clean_messages),
            identifiers=lambda: "mailrun-task031-clean-policy",
        ).acquire(
            LINUX_BLOCK_SOURCE.source_id,
            SelectionCriteria(message_ids=(clean_root,)),
            AcquisitionLimits(seed_limit=1, context_limit=10, descendant_depth=1),
            coverage_batch_id="task031-clean-policy-batch",
        )

        self.assertEqual(clean.relationship_status, "policy_truncated")
        self.assertEqual(clean.state, "connected")
        self.assertTrue(clean.coverage_complete)

    def test_more_than_fifty_relationship_records_complete_in_three_bounded_runs(self) -> None:
        root = "<task031-large-root@kernel.example>"
        messages = {
            root: ArchiveMessage(raw_message(root, "[PATCH] large root"), "fixture:root")
        }
        for index in range(55):
            message_id = f"<task031-large-{index:02d}@kernel.example>"
            messages[message_id] = ArchiveMessage(
                raw_message(message_id, f"Re: [PATCH] large {index}", root),
                f"fixture:{index}",
            )
        calls: list[tuple[str, int, int]] = []
        manifests = []
        for run_number in range(1, 10):
            repository = MailingListRepository(self.state)
            service = MailingListAcquisitionService(
                repository,
                PagedTrackingArchive(messages, calls),
                identifiers=lambda n=run_number: f"mailrun-task031-large-{n}",
            )
            manifest = service.acquire(
                LINUX_BLOCK_SOURCE.source_id,
                SelectionCriteria(message_ids=(root,)),
                AcquisitionLimits(seed_limit=1, context_limit=20, descendant_depth=2),
                coverage_batch_id="task031-more-than-fifty",
            )
            manifests.append(manifest)
            if manifest.relationship_status != "continuation_pending":
                break
        self.assertEqual(len(manifests), 3)
        self.assertEqual(manifests[-1].relationship_status, "complete")
        self.assertTrue(manifests[-1].coverage_complete)
        self.assertTrue(all(item.message_count <= 21 for item in manifests))
        self.assertEqual(
            len(MailingListRepository(self.state).rows(
                "SELECT message_key FROM mailing_list_messages WHERE source_id=?",
                (LINUX_BLOCK_SOURCE.source_id,),
            )),
            56,
        )

    def test_future_reply_does_not_retroactively_defect_completed_snapshot(self) -> None:
        manifests = []
        for run_number in range(1, 20):
            item = self.acquire(run_number)
            manifests.append(item)
            if item.relationship_status != "continuation_pending":
                break
        self.assertTrue(manifests[-1].coverage_complete)
        late_id = "<task031-late-reply@kernel.example>"
        self.messages[late_id] = ArchiveMessage(
            raw_message(late_id, "Re: completed snapshot", self.root), "fixture:late"
        )
        repository = MailingListRepository(self.state)
        prior = repository.acquisition_run_manifest(manifests[-1].run_id)
        self.assertEqual(prior["relationship_status"], manifests[-1].relationship_status)
        self.assertTrue(prior["coverage_complete"])
        self.assertIsNone(repository.existing_artifact(LINUX_BLOCK_SOURCE.source_id, late_id))


class WorkflowContinuationCase(unittest.TestCase):
    def test_relationships_finish_before_later_seed_page_and_date_windows_advance(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            state = Path(temporary)
            RepositoryDatabase.initialize(state)
            FirmRepository.initialize(state / "firm-catalog")
            repository = MailingListRepository(state)
            messages, _root, seed, shared_seed = large_discussion()
            calls: list[tuple[str, int, int]] = []
            workflow = LinuxMailingListWorkflowService(
                repository,
                MailingListSourceService(repository),
                StreamService(StreamRepository(state)),
                MailingListQueryService(repository),
                archive_factory=lambda _source: WindowedSeedArchive(
                    messages, calls, (seed, shared_seed)
                ),
                today=lambda: date(2026, 7, 22),
            )
            created = workflow.create(draft(
                date_from="2026-05-01", date_through="2026-05-01",
                seed_limit=1, total_limit=2, descendant_depth=3,
            ))
            assert created.revision is not None

            result = workflow.fetch_up_to_date(created.revision.stream_id)

            self.assertEqual(result.status, "completed")
            self.assertEqual(result.message, "Acquisition coverage is up to date.")
            self.assertEqual(result.windows_completed, 3)
            self.assertEqual(result.effective_last_fetch_date, "2026-07-22")
            manifests = [
                workflow.query_service.acquisition_run(run_id)["manifest"]
                for run_id in result.acquisition_run_ids
            ]
            manifests = [item for item in manifests if "discovery_offset" in item]
            offsets = [item["discovery_offset"] for item in manifests]
            first_later_page = offsets.index(1)
            self.assertGreaterEqual(first_later_page, 3)
            self.assertTrue(all(
                item["relationship_status"] != "continuation_pending"
                for item in manifests[first_later_page:]
            ))
            coverage = repository.acquisition_coverage(LINUX_BLOCK_SOURCE.source_id)
            self.assertTrue(any(not item["coverage_complete"] for item in coverage))
            self.assertTrue(any(item["coverage_complete"] for item in coverage))


class SurfaceAndLorePaginationCase(unittest.TestCase):
    def test_cli_browser_and_run_history_expose_the_same_status_terms(self) -> None:
        arguments = cli_parser().parse_args([
            "mailing-list", "--state", "/tmp/task031-state", "acquire", "--live",
            "--message-id", "<seed@example.com>", "--continuation-id", "batch-31",
            "--discovery-offset", "4",
        ])
        self.assertEqual(arguments.continuation_id, "batch-31")
        self.assertEqual(arguments.discovery_offset, 4)
        html = (Path(__file__).resolve().parents[1] /
                "src/rfi/admin/linux_mailing_lists.html").read_text()
        for term in ("continuation_pending", "policy_truncated", "failed"):
            self.assertIn(term, html)

    def test_lore_relationship_page_offset_is_sent_and_parsed(self) -> None:
        calls = []
        feed = b"""<?xml version='1.0'?><feed xmlns='http://www.w3.org/2005/Atom'
          xmlns:thr='http://purl.org/syndication/thread/1.0'>
          <entry><link href='https://lore.kernel.org/linux-block/child@example.com/'/>
          <thr:in-reply-to href='https://lore.kernel.org/linux-block/root@example.com/'/></entry>
          </feed>"""

        class Response:
            headers = {"Content-Length": str(len(feed))}

            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return False

            def read(self, _size):
                return feed

        def opener(request, timeout):
            del timeout
            calls.append(request.full_url)
            return Response()

        archive = LoreArchive(
            LINUX_BLOCK_SOURCE, opener=opener, sleeper=lambda _seconds: None
        )
        children, has_more = archive.direct_children_page(
            "<root@example.com>", 10, 7
        )
        self.assertEqual(children, ("<child@example.com>",))
        self.assertFalse(has_more)
        self.assertEqual(parse_qs(urlsplit(calls[0]).query), {"o": ["7"]})


if __name__ == "__main__":
    unittest.main()
