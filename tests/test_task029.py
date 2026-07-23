"""Focused TASK-029 operator-console and catch-up queue evidence."""

from __future__ import annotations

import tempfile
import threading
import unittest
from datetime import date, timedelta
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import patch

from rfi.firms import FirmRepository
from rfi.mailing_lists import (
    AcquisitionLimits,
    ArchiveMessage,
    FetchUpToDateResult,
    LinuxMailingListWorkflowService,
    MailingListError,
    MailingListFetchQueue,
    MailingListQueryService,
    MailingListRepository,
    MailingListSourceService,
    MailingListAcquisitionService,
    SelectionCriteria,
)
from rfi.storage import RepositoryDatabase
from rfi.streams import StreamError, StreamRepository, StreamService
from tests.test_task028 import FixtureWorkflowArchive, archive_factory, draft
from tests.test_task023 import raw_message

ROOT = Path(__file__).resolve().parents[1]


class CatchUpCase(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.state = Path(self.temporary.name)
        RepositoryDatabase.initialize(self.state)
        FirmRepository.initialize(self.state / "firm-catalog")
        repository = MailingListRepository(self.state)
        self.workflow = LinuxMailingListWorkflowService(
            repository,
            MailingListSourceService(repository),
            StreamService(StreamRepository(self.state)),
            MailingListQueryService(repository),
            archive_factory=archive_factory,
            today=lambda: date(2026, 7, 22),
        )

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def create(self, **changes: Any) -> str:
        result = self.workflow.create(draft(**changes))
        assert result.revision is not None
        return result.revision.stream_id

    def test_effective_last_fetch_uses_complete_contiguous_repository_coverage(self) -> None:
        stream_id = self.create()
        tested = self.workflow.test(stream_id)
        self.assertEqual(tested.status, "ready")
        self.assertEqual(self.workflow.effective_last_fetch(stream_id), "2026-07-16")
        result = self.workflow.fetch_up_to_date(stream_id)
        self.assertEqual(result.window_start, "2026-07-14")
        self.assertEqual(result.window_end, "2026-07-22")
        self.assertEqual(result.effective_last_fetch_date, "2026-07-22")

        restarted_repository = MailingListRepository(self.state)
        restarted = LinuxMailingListWorkflowService(
            restarted_repository,
            MailingListSourceService(restarted_repository),
            StreamService(StreamRepository(self.state)),
            MailingListQueryService(restarted_repository),
            archive_factory=archive_factory,
            today=lambda: date(2026, 7, 22),
        )
        self.assertEqual(restarted.effective_last_fetch(stream_id), "2026-07-22")

    def test_long_catch_up_is_split_into_bounded_windows(self) -> None:
        stream_id = self.create(date_from="2026-05-01", date_through="2026-05-01")
        result = self.workflow.fetch_up_to_date(stream_id)
        self.assertEqual(result.windows_completed, 3)
        runs = self.workflow.repository.acquisition_coverage(
            self.workflow.stream_service.detail(stream_id).draft.input_ids[0]
        )
        spans = [
            (
                item["criteria"]["date_from"],
                item["criteria"]["date_through"],
            )
            for item in runs
        ]
        self.assertEqual(
            spans,
            [
                ("2026-05-01", "2026-06-01"),
                ("2026-06-02", "2026-07-03"),
                ("2026-07-04", "2026-07-22"),
            ],
        )
        self.assertTrue(
            all(
                date.fromisoformat(end) - date.fromisoformat(start)
                <= timedelta(days=31)
                for start, end in spans
            )
        )

    def test_seed_saturated_span_is_exhausted_in_bounded_batches_and_published(self) -> None:
        message_ids = tuple(f"<paged-{index}@kernel.example>" for index in range(3))
        root_ids = tuple(f"<paged-root-{index}@kernel.example>" for index in range(3))
        messages = {
            **{
                root_id: ArchiveMessage(
                    raw_message(root_id, f"[PATCH] root {index}", body="root context"),
                    f"fixture:{root_id}",
                )
                for index, root_id in enumerate(root_ids)
            },
            **{
                message_id: ArchiveMessage(
                raw_message(
                    message_id, f"Re: [PATCH] paged {index}", root_ids[index],
                    body="deterministic queue"
                ),
                f"fixture:{message_id}",
                )
                for index, message_id in enumerate(message_ids)
            },
        }
        self.workflow.archive_factory = lambda _source: FixtureWorkflowArchive(messages)
        stream_id = self.create(
            date_from="2026-07-17", date_through="2026-07-17",
            seed_limit=1, total_limit=10,
        )

        result = self.workflow.fetch_up_to_date(stream_id)

        self.assertEqual(result.status, "completed")
        self.assertEqual(result.windows_completed, 1)
        self.assertEqual(len(result.acquisition_run_ids), 3)
        self.assertEqual(result.effective_last_fetch_date, "2026-07-22")
        runs = [
            self.workflow.query_service.acquisition_run(run_id)["manifest"]
            for run_id in result.acquisition_run_ids
        ]
        self.assertEqual([item["discovery_offset"] for item in runs], [0, 1, 2])
        self.assertEqual([item["coverage_complete"] for item in runs], [False, False, True])
        self.assertEqual([item["relationship_count"] for item in runs], [1, 1, 1])
        self.assertEqual([item["discussion_count"] for item in runs], [1, 1, 1])
        self.assertTrue(all(item["message_count"] <= 10 for item in runs))
        summaries = self.workflow.stream_service.list_streams()
        self.assertEqual(summaries[0].latest_run_status, "succeeded")
        self.assertGreater(summaries[0].membership_count, 0)
        projections = self.workflow.repository.rows(
            "SELECT count(*) AS count FROM artifact_stream_projections"
        )
        self.assertGreater(int(projections[0]["count"]), 0)
        self.assertEqual(self.workflow.saved()[0].test_evidence_status, "complete_connected")

    def test_provider_relationship_failure_does_not_advance_coverage(self) -> None:
        stream_id = self.create()
        self.workflow.test(stream_id)

        class FrontierUnknownArchive(FixtureWorkflowArchive):
            @property
            def descendant_enumeration_complete(self) -> bool:
                return False

        base = archive_factory(self.workflow.repository.source("linux-block-lore"))
        self.workflow.archive_factory = lambda _source: FrontierUnknownArchive(base.messages)
        result = self.workflow.fetch_up_to_date(stream_id)
        self.assertEqual(result.status, "failed")
        self.assertEqual(result.effective_last_fetch_date, "2026-07-16")

        self.workflow.archive_factory = archive_factory
        recovered = self.workflow.fetch_up_to_date(stream_id)
        self.assertEqual(recovered.status, "completed")
        self.assertEqual(recovered.effective_last_fetch_date, "2026-07-22")
        coverage = self.workflow.repository.acquisition_coverage(
            self.workflow.stream_service.detail(stream_id).draft.input_ids[0]
        )
        self.assertTrue(any(not item["coverage_complete"] for item in coverage))
        self.assertTrue(any(item["coverage_complete"] for item in coverage))

    def test_reply_depth_policy_limit_advances_exhausted_discovery_coverage(self) -> None:
        root = "<workflow-policy-root@kernel.example>"
        one = "<workflow-policy-one@kernel.example>"
        two = "<workflow-policy-two@kernel.example>"
        messages = {
            root: ArchiveMessage(
                raw_message(root, "[PATCH] bounded policy", body="deterministic queue"),
                "fixture:root",
            ),
            one: ArchiveMessage(
                raw_message(one, "Re: [PATCH] bounded policy", root), "fixture:one"
            ),
            two: ArchiveMessage(
                raw_message(two, "Re: [PATCH] bounded policy", one), "fixture:two"
            ),
        }
        self.workflow.archive_factory = lambda _source: FixtureWorkflowArchive(messages)
        stream_id = self.create(
            date_from="2026-07-17", date_through="2026-07-17",
            seed_limit=10, total_limit=11, descendant_depth=1,
        )
        orphan = "<workflow-unrelated-orphan@kernel.example>"
        incomplete = MailingListAcquisitionService(
            self.workflow.repository,
            FixtureWorkflowArchive({
                orphan: ArchiveMessage(
                    raw_message(
                        orphan,
                        "[PATCH] unrelated incomplete evidence",
                        "<workflow-unavailable-parent@kernel.example>",
                    ),
                    "fixture:unrelated-orphan",
                )
            }),
        ).acquire(
            self.workflow.stream_service.detail(stream_id).draft.input_ids[0],
            SelectionCriteria(message_ids=(orphan,)),
            AcquisitionLimits(seed_limit=1, context_limit=2, descendant_depth=1),
            coverage_batch_id="workflow-unrelated-incomplete-batch",
        )
        self.assertEqual(incomplete.state, "incomplete")

        result = self.workflow.fetch_up_to_date(stream_id)

        self.assertEqual(result.status, "completed")
        self.assertEqual(result.effective_last_fetch_date, "2026-07-22")
        manifest = self.workflow.query_service.acquisition_run(
            result.acquisition_run_ids[-1]
        )["manifest"]
        self.assertTrue(manifest["discovery_complete"])
        self.assertTrue(manifest["descendant_policy_complete"])
        self.assertTrue(manifest["descendant_policy_limited"])
        self.assertFalse(manifest["unexpected_truncation"])
        self.assertTrue(manifest["coverage_complete"])

    def test_projection_publication_failure_is_explicit_after_coverage(self) -> None:
        stream_id = self.create()
        with patch.object(
            self.workflow.stream_service, "run",
            side_effect=StreamError("projection_failed", "projection did not publish"),
        ), self.assertRaises(MailingListError) as raised:
            self.workflow.fetch_up_to_date(stream_id)

        self.assertEqual(raised.exception.code, "stream_projection_failed")
        self.assertTrue(raised.exception.retryable)
        self.assertEqual(self.workflow.effective_last_fetch(stream_id), "2026-07-22")

    def test_editor_save_creates_authoritative_revision_and_modal_is_required(self) -> None:
        stream_id = self.create()
        saved = self.workflow.save(stream_id, draft(description="Updated operator purpose"))
        assert saved.revision is not None
        self.assertEqual(saved.status, "revised")
        self.assertEqual(saved.revision.revision_number, 2)
        html = (ROOT / "src/rfi/admin/linux_mailing_lists.html").read_text()
        self.assertIn('id="save-dialog"', html)
        self.assertIn("Authoritative revision saved", html)
        self.assertIn("showModal()", html)
        self.assertIn('id="summary-mode"', html)
        self.assertIn('id="editor-mode"', html)
        self.assertIn("Fetch All up to date", html)
        self.assertIn("Cancel / Abandon all Fetches", html)
        self.assertIn("max-height:360px;overflow:auto", html)

    def test_acquisition_cancellation_is_not_swallowed_as_partial_evidence(self) -> None:
        stream_id = self.create()
        revision = self.workflow.stream_service.detail(stream_id)
        source_id = revision.draft.input_ids[0]
        service = MailingListAcquisitionService(
            self.workflow.repository,
            archive_factory(self.workflow.repository.source(source_id)),
        )
        checkpoints = 0

        def cancelled() -> bool:
            nonlocal checkpoints
            checkpoints += 1
            return checkpoints >= 3

        with self.assertRaises(MailingListError) as raised:
            service.acquire(
                source_id,
                SelectionCriteria(
                    date_from="2026-07-16", date_through="2026-07-16",
                    topic_terms=("deterministic queue",),
                ),
                AcquisitionLimits(5, 15, 3),
                cancelled=cancelled,
            )
        self.assertEqual(raised.exception.code, "acquisition_cancelled")
        self.assertEqual(self.workflow.repository.acquisition_runs(source_id), ())


class FakeWorkflow:
    def __init__(self, names: tuple[str, ...], *, blocking: bool = False) -> None:
        self.items = tuple(
            SimpleNamespace(stream_id=name, stream_name=name.upper()) for name in names
        )
        self.blocking = blocking
        self.calls: list[str] = []
        self.started = threading.Event()
        self.release = threading.Event()
        self.completed = threading.Event()

    def saved(self):
        return self.items

    def fetch_up_to_date(self, stream_id: str, *, cancelled):
        self.calls.append(stream_id)
        self.started.set()
        if self.blocking:
            while not self.release.wait(0.01):
                if cancelled():
                    raise MailingListError("acquisition_cancelled", "cancelled")
        if len(self.calls) == len(self.items):
            self.completed.set()
        return FetchUpToDateResult(
            stream_id, "completed", "2026-07-20", "2026-07-22", 1, (),
            "2026-07-22", "Acquisition coverage is up to date.",
        )


class QueueCase(unittest.TestCase):
    def test_fifo_duplicate_suppression_and_fetch_all(self) -> None:
        workflow = FakeWorkflow(("one", "two", "three"), blocking=True)
        queue = MailingListFetchQueue(workflow)  # type: ignore[arg-type]
        try:
            first = queue.enqueue("one")
            self.assertTrue(first["accepted"])
            self.assertTrue(workflow.started.wait(1))
            all_result = queue.enqueue_all()
            self.assertEqual(all_result["queued"], 2)
            self.assertEqual(all_result["duplicates_ignored"], 1)
            duplicate = queue.enqueue("two")
            self.assertTrue(duplicate["duplicate"])
            workflow.release.set()
            self.assertTrue(workflow.completed.wait(1))
            self.assertEqual(workflow.calls, ["one", "two", "three"])
            events = [item["event"] for item in queue.snapshot()["events"]]
            self.assertIn("duplicate_ignored", events)
            self.assertEqual(events.count("started"), 3)
            self.assertEqual(events.count("completed"), 3)
        finally:
            queue.close()

    def test_cancel_abandons_queued_work_and_cancels_running_checkpoint(self) -> None:
        workflow = FakeWorkflow(("one", "two"), blocking=True)
        queue = MailingListFetchQueue(workflow)  # type: ignore[arg-type]
        try:
            queue.enqueue("one")
            self.assertTrue(workflow.started.wait(1))
            queue.enqueue("two")
            result = queue.cancel_all()
            self.assertEqual(result["abandoned"], 1)
            self.assertTrue(result["cancellation_requested"])
            for _index in range(100):
                snapshot = queue.snapshot()
                if snapshot["recent"] and any(
                    item["state"] == "cancelled" for item in snapshot["recent"]
                ):
                    break
                threading.Event().wait(0.01)
            states = {item["stream_id"]: item["state"] for item in queue.snapshot()["recent"]}
            self.assertEqual(states, {"one": "cancelled", "two": "abandoned"})
            events = [item["event"] for item in queue.snapshot()["events"]]
            self.assertIn("cancellation_requested", events)
            self.assertIn("abandoned", events)
            self.assertIn("cancelled", events)
        finally:
            workflow.release.set()
            queue.close()

    def test_process_restart_starts_with_an_empty_operational_queue(self) -> None:
        workflow = FakeWorkflow(("one",))
        first = MailingListFetchQueue(workflow)  # type: ignore[arg-type]
        first.close()
        restarted = MailingListFetchQueue(workflow)  # type: ignore[arg-type]
        try:
            snapshot = restarted.snapshot()
            self.assertIsNone(snapshot["running"])
            self.assertEqual(snapshot["queued"], [])
            self.assertEqual(snapshot["events"], [])
            self.assertIn("durable_evidence_remains", snapshot["restart_behavior"])
        finally:
            restarted.close()


if __name__ == "__main__":
    unittest.main()
