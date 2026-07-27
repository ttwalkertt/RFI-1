"""Focused TASK-039 acquisition-batch/publication-policy regression evidence."""

from __future__ import annotations

import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

from rfi.firms import FirmRepository
from rfi.mailing_lists import (
    LINUX_BLOCK_SOURCE,
    LinuxMailingListWorkflowService,
    MailingListQueryService,
    MailingListRepository,
    MailingListSourceService,
)
from rfi.storage import RepositoryDatabase
from rfi.streams import StreamError, StreamRepository, StreamService
from tests.test_task028 import draft
from tests.test_task031 import PagedTrackingArchive, large_discussion


class WorkflowArchive(PagedTrackingArchive):
    def probe(self) -> dict[str, str]:
        return {"status": "reachable", "archive": "task039-fixture"}


class SplitLimitPolicyCase(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.state = Path(self.temporary.name)
        RepositoryDatabase.initialize(self.state)
        FirmRepository.initialize(self.state / "firm-catalog")
        self.repository = MailingListRepository(self.state)
        self.messages, _root, self.seed, self.shared_seed = large_discussion()
        self.calls: list[tuple[str, int, int]] = []
        self.stream_repository = StreamRepository(self.state)
        self.streams = StreamService(self.stream_repository)
        self.workflow = LinuxMailingListWorkflowService(
            self.repository,
            MailingListSourceService(self.repository),
            self.streams,
            MailingListQueryService(self.repository),
            archive_factory=lambda _source: WorkflowArchive(
                self.messages, self.calls
            ),
            today=lambda: date(2026, 7, 17),
        )

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def create_stream(self) -> str:
        created = self.workflow.create(draft(
            date_from="2026-07-17",
            date_through="2026-07-17",
            seed_limit=1,
            total_limit=2,
            descendant_depth=3,
            keywords=["resumable relationship fixture"],
        ))
        assert created.revision is not None
        return created.revision.stream_id

    def test_component_larger_than_one_acquisition_batch_publishes_and_pages(self) -> None:
        stream_id = self.create_stream()

        result = self.workflow.fetch_up_to_date(stream_id)

        self.assertEqual(result.status, "completed")
        manifests = [
            self.workflow.query_service.acquisition_run(run_id)["manifest"]
            for run_id in result.acquisition_run_ids
        ]
        self.assertGreaterEqual(len(manifests), 3)
        self.assertTrue(
            all(item["relationship_records_processed"] <= 1 for item in manifests)
        )
        self.assertTrue(all(call_limit == 1 for _parent, _offset, call_limit in self.calls))
        first_page = self.stream_repository.memberships(stream_id, limit=3, offset=0)
        second_page = self.stream_repository.memberships(stream_id, limit=3, offset=3)
        all_members = self.stream_repository.memberships(stream_id, limit=100)
        self.assertGreater(len(all_members), 2)
        self.assertEqual(first_page + second_page, all_members[:6])
        self.assertEqual(len({item.membership_id for item in all_members}), len(all_members))

    def test_complete_component_publication_remains_atomic_on_failure(self) -> None:
        stream_id = self.create_stream()
        original = self.stream_repository._insert_publications

        def fail_after_one(connection, run_id, stream, revision, publications):
            original(connection, run_id, stream, revision, publications[:1])
            raise StreamError("publication_failure", "injected component publication failure")

        with patch.object(
            self.stream_repository, "_insert_publications", side_effect=fail_after_one
        ):
            with self.assertRaisesRegex(Exception, "component publication failure"):
                self.workflow.fetch_up_to_date(stream_id)

        self.assertEqual(self.stream_repository.memberships(stream_id), ())
        failed = self.stream_repository.runs(stream_id)[0]
        self.assertEqual(failed.status, "failed")

        recovered = self.streams.run(stream_id)
        self.assertEqual(recovered.status, "succeeded")
        self.assertGreater(len(self.stream_repository.memberships(stream_id)), 2)

    def test_configuration_translation_preserves_batch_allowance(self) -> None:
        stream_id = self.create_stream()
        revision = self.streams.detail(stream_id)

        self.assertEqual(revision.draft.bounds, {"seed_limit": 1, "expanded_limit": 2})


if __name__ == "__main__":
    unittest.main()
