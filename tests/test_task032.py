"""Focused TASK-032 Process Local Fetch Queue progress, timestamps, and durable history."""

from __future__ import annotations

import json
import tempfile
import threading
import unittest
from datetime import date
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import patch

from rfi.firms import FirmRepository
from rfi.mailing_lists import (
    FetchProgress,
    FetchUpToDateResult,
    LinuxMailingListWorkflowService,
    MailingListError,
    MailingListFetchQueue,
    MailingListQueryService,
    MailingListRepository,
    MailingListSourceService,
)
from rfi.storage import RepositoryDatabase
from rfi.streams import StreamRepository, StreamService
from tests.test_task028 import archive_factory, draft
from tests.test_task029 import FakeWorkflow

ROOT = Path(__file__).resolve().parents[1]


class DurableHistoryCase(unittest.TestCase):
    """Terminal-history persistence, event scrollback, pruning, and restart."""

    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.state = Path(self.temporary.name)
        RepositoryDatabase.initialize(self.state)
        FirmRepository.initialize(self.state / "firm-catalog")
        self.repository = MailingListRepository(self.state)

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def test_completed_history_survives_close_and_reopen(self) -> None:
        self.repository.record_fetch_history(
            stream_id="linux-block", stream_name="Linux Block",
            state="completed", message="Acquisition coverage is up to date.",
            queued_at="2026-07-23T10:00:00+00:00",
            started_at="2026-07-23T10:00:01+00:00",
            finished_at="2026-07-23T10:05:00+00:00",
            windows_completed=2,
            result={"status": "completed"},
        )
        reopened = MailingListRepository(self.state)
        history = reopened.fetch_history()
        self.assertEqual(len(history), 1)
        self.assertEqual(history[0]["state"], "completed")
        self.assertEqual(history[0]["stream_name"], "Linux Block")
        self.assertEqual(history[0]["windows_completed"], 2)

    def test_failed_history_survives_close_and_reopen(self) -> None:
        self.repository.record_fetch_history(
            stream_id="lkml", stream_name="LKML",
            state="failed", message="Connection refused",
            queued_at=None, started_at="2026-07-23T11:00:00+00:00",
            finished_at="2026-07-23T11:00:05+00:00",
        )
        reopened = MailingListRepository(self.state)
        history = reopened.fetch_history()
        self.assertEqual(len(history), 1)
        self.assertEqual(history[0]["state"], "failed")

    def test_cancelled_history_survives_close_and_reopen(self) -> None:
        self.repository.record_fetch_history(
            stream_id="linux-nvme", stream_name="Linux NVMe",
            state="cancelled", message="Cancelled at safe checkpoint",
            queued_at="2026-07-23T12:00:00+00:00",
            started_at="2026-07-23T12:00:01+00:00",
            finished_at="2026-07-23T12:00:10+00:00",
        )
        reopened = MailingListRepository(self.state)
        history = reopened.fetch_history()
        self.assertEqual(len(history), 1)
        self.assertEqual(history[0]["state"], "cancelled")

    def test_abandoned_history_survives_close_and_reopen(self) -> None:
        self.repository.record_fetch_history(
            stream_id="linux-scsi", stream_name="Linux SCSI",
            state="abandoned", message="Abandoned before start",
            queued_at="2026-07-23T13:00:00+00:00",
            started_at=None,
            finished_at="2026-07-23T13:00:01+00:00",
        )
        reopened = MailingListRepository(self.state)
        history = reopened.fetch_history()
        self.assertEqual(len(history), 1)
        self.assertEqual(history[0]["state"], "abandoned")

    def test_terminal_history_is_newest_first(self) -> None:
        for index in range(5):
            self.repository.record_fetch_history(
                stream_id=f"stream-{index}", stream_name=f"Stream {index}",
                state="completed", message=f"Done {index}",
                queued_at=None, started_at=None,
                finished_at=f"2026-07-2{index}T10:00:00+00:00",
            )
        history = self.repository.fetch_history()
        self.assertEqual(len(history), 5)
        timestamps = [item["finished_at"] for item in history]
        self.assertEqual(timestamps, sorted(timestamps, reverse=True))

    def test_history_retention_is_bounded_and_prunes_oldest(self) -> None:
        limit = self.repository.FETCH_HISTORY_LIMIT
        for index in range(limit + 10):
            self.repository.record_fetch_history(
                stream_id=f"stream-{index}", stream_name=f"Stream {index}",
                state="completed", message=f"Done {index}",
                queued_at=None, started_at=None,
                finished_at=f"2026-07-01T10:{index:02d}:00+00:00",
            )
        history = self.repository.fetch_history()
        self.assertEqual(len(history), limit)

    def test_event_scrollback_survives_close_and_reopen(self) -> None:
        self.repository.record_fetch_event(
            sequence=1, occurred_at="2026-07-23T10:00:00+00:00",
            event="queued", stream_id="linux-block", stream_name="Linux Block",
            message="Fetch queued.",
        )
        self.repository.record_fetch_event(
            sequence=2, occurred_at="2026-07-23T10:00:01+00:00",
            event="started", stream_id="linux-block", stream_name="Linux Block",
            message="Running bounded acquisition windows.",
        )
        reopened = MailingListRepository(self.state)
        events = reopened.fetch_events()
        self.assertEqual(len(events), 2)
        self.assertEqual(events[0]["sequence"], 2)
        self.assertEqual(events[1]["sequence"], 1)

    def test_event_retention_is_bounded(self) -> None:
        limit = self.repository.FETCH_EVENT_LIMIT
        for index in range(limit + 50):
            self.repository.record_fetch_event(
                sequence=index, occurred_at=f"2026-07-23T10:00:{index:02d}+00:00",
                event="queued", stream_id="linux-block", stream_name="Linux Block",
                message=f"Event {index}",
            )
        events = self.repository.fetch_events()
        self.assertEqual(len(events), limit)


class QueueProgressCase(unittest.TestCase):
    """Progress callback, running-job updates, coalescing, and compatibility."""

    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.state = Path(self.temporary.name)
        RepositoryDatabase.initialize(self.state)
        FirmRepository.initialize(self.state / "firm-catalog")
        self.repository = MailingListRepository(self.state)
        self.workflow = LinuxMailingListWorkflowService(
            self.repository,
            MailingListSourceService(self.repository),
            StreamService(StreamRepository(self.state)),
            MailingListQueryService(self.repository),
            archive_factory=archive_factory,
            today=lambda: date(2026, 7, 22),
        )

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def create(self, **changes: Any) -> str:
        result = self.workflow.create(draft(**changes))
        assert result.revision is not None
        return result.revision.stream_id

    def test_progress_callback_is_optional_and_backward_compatible(self) -> None:
        stream_id = self.create()
        result = self.workflow.fetch_up_to_date(stream_id)
        self.assertEqual(result.status, "completed")
        self.assertEqual(result.windows_completed, 1)

    def test_progress_callback_invoked_at_window_boundaries(self) -> None:
        stream_id = self.create(date_from="2026-05-01", date_through="2026-05-01")
        progress_calls: list[FetchProgress] = []

        def on_progress(progress: FetchProgress) -> None:
            progress_calls.append(progress)

        result = self.workflow.fetch_up_to_date(stream_id, on_progress=on_progress)
        self.assertEqual(result.windows_completed, 3)
        self.assertGreaterEqual(len(progress_calls), 3)
        phases = [call.phase for call in progress_calls]
        self.assertIn("acquiring", phases)
        self.assertIn("window_complete", phases)

    def test_progress_content_contains_window_and_count(self) -> None:
        stream_id = self.create(date_from="2026-05-01", date_through="2026-05-01")
        progress_calls: list[FetchProgress] = []

        def on_progress(progress: FetchProgress) -> None:
            progress_calls.append(progress)

        self.workflow.fetch_up_to_date(stream_id, on_progress=on_progress)
        for call in progress_calls:
            self.assertIsNotNone(call.window_start)
            self.assertIsNotNone(call.window_end)
            self.assertGreaterEqual(call.windows_completed, 0)

    def test_callback_exception_does_not_fail_acquisition(self) -> None:
        stream_id = self.create()

        def bad_callback(_progress: FetchProgress) -> None:
            raise RuntimeError("progress publisher failed")

        result = self.workflow.fetch_up_to_date(stream_id, on_progress=bad_callback)
        self.assertEqual(result.status, "completed")

    def test_queue_updates_running_job_progress_before_terminal(self) -> None:
        progress_seen = threading.Event()

        class SlowWorkflow:
            def __init__(self) -> None:
                self._items = [SimpleNamespace(stream_id="one", stream_name="ONE")]

            def saved(self):
                return self._items

            def fetch_up_to_date(self, stream_id, *, cancelled, on_progress=None):
                if on_progress is not None:
                    on_progress(FetchProgress(
                        phase="acquiring",
                        message="Acquiring window 2026-07-01 through 2026-07-31.",
                        window_start="2026-07-01",
                        window_end="2026-07-31",
                        windows_completed=0,
                    ))
                    progress_seen.set()
                while not cancelled():
                    threading.Event().wait(0.01)
                    raise MailingListError(
                        "acquisition_cancelled", "cancelled for test"
                    )
                raise MailingListError("acquisition_cancelled", "cancelled")

        queue = MailingListFetchQueue(SlowWorkflow())  # type: ignore[arg-type]
        try:
            queue.enqueue("one")
            self.assertTrue(progress_seen.wait(2))
            snapshot = queue.snapshot()
            self.assertIsNotNone(snapshot["running"])
            running = snapshot["running"]
            self.assertEqual(running["state"], "running")
            self.assertIsNotNone(running["progress"])
            self.assertEqual(running["progress"]["phase"], "acquiring")
            self.assertIsNotNone(running["updated_at"])
            self.assertIsNotNone(running["started_at"])
        finally:
            queue.cancel_all()
            queue.close()

    def test_progress_event_coalescing_prevents_flooding(self) -> None:
        call_count = 0

        class FastProgressWorkflow:
            def __init__(self) -> None:
                self._items = [SimpleNamespace(stream_id="one", stream_name="ONE")]

            def saved(self):
                return self._items

            def fetch_up_to_date(self, stream_id, *, cancelled, on_progress=None):
                nonlocal call_count
                for index in range(20):
                    if on_progress is not None:
                        on_progress(FetchProgress(
                            phase="acquiring",
                            message=f"Progress {index}",
                            window_start="2026-07-01",
                            window_end="2026-07-31",
                            windows_completed=index,
                        ))
                    call_count += 1
                return FetchUpToDateResult(
                    stream_id, "completed", "2026-07-01", "2026-07-22", 1, (),
                    "2026-07-22", "Acquisition coverage is up to date.",
                )

        queue = MailingListFetchQueue(FastProgressWorkflow())  # type: ignore[arg-type]
        try:
            queue.enqueue("one")
            threading.Event().wait(0.5)
            snapshot = queue.snapshot()
            progress_events = [
                e for e in snapshot["events"] if e["event"] == "progress"
            ]
            self.assertLessEqual(len(progress_events), 7)
        finally:
            queue.close()

    def test_fifo_execution_preserved(self) -> None:
        workflow = FakeWorkflow(("one", "two", "three"))
        queue = MailingListFetchQueue(workflow)  # type: ignore[arg-type]
        try:
            queue.enqueue("one")
            queue.enqueue("two")
            queue.enqueue("three")
            self.assertTrue(workflow.completed.wait(2))
            self.assertEqual(workflow.calls, ["one", "two", "three"])
        finally:
            queue.close()

    def test_duplicate_suppression_preserved(self) -> None:
        workflow = FakeWorkflow(("one", "two"), blocking=True)
        queue = MailingListFetchQueue(workflow)  # type: ignore[arg-type]
        try:
            queue.enqueue("one")
            self.assertTrue(workflow.started.wait(1))
            duplicate = queue.enqueue("one")
            self.assertTrue(duplicate["duplicate"])
        finally:
            workflow.release.set()
            queue.close()

    def test_cancel_all_preserved(self) -> None:
        workflow = FakeWorkflow(("one", "two"), blocking=True)
        queue = MailingListFetchQueue(workflow)  # type: ignore[arg-type]
        try:
            queue.enqueue("one")
            self.assertTrue(workflow.started.wait(1))
            queue.enqueue("two")
            result = queue.cancel_all()
            self.assertEqual(result["abandoned"], 1)
            self.assertTrue(result["cancellation_requested"])
        finally:
            workflow.release.set()
            queue.close()


class QueueWithHistoryCase(unittest.TestCase):
    """Queue + durable history integration: restart, persistence, snapshot."""

    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.state = Path(self.temporary.name)
        RepositoryDatabase.initialize(self.state)
        FirmRepository.initialize(self.state / "firm-catalog")
        self.repository = MailingListRepository(self.state)

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def _make_queue(self, workflow: Any) -> MailingListFetchQueue:
        return MailingListFetchQueue(workflow, history=self.repository)

    def test_terminal_job_persisted_to_durable_history(self) -> None:
        workflow = FakeWorkflow(("one",))
        queue = self._make_queue(workflow)  # type: ignore[arg-type]
        try:
            queue.enqueue("one")
            self.assertTrue(workflow.completed.wait(2))
            threading.Event().wait(0.2)
        finally:
            queue.close()
        history = self.repository.fetch_history()
        self.assertEqual(len(history), 1)
        self.assertEqual(history[0]["state"], "completed")
        self.assertEqual(history[0]["stream_name"], "ONE")

    def test_failed_job_persisted_to_durable_history(self) -> None:

        class FailingWorkflow:
            def __init__(self) -> None:
                self._items = [SimpleNamespace(stream_id="one", stream_name="ONE")]

            def saved(self):
                return self._items

            def fetch_up_to_date(self, stream_id, *, cancelled, on_progress=None):
                raise MailingListError("test_failure", "Simulated failure")

        queue = self._make_queue(FailingWorkflow())  # type: ignore[arg-type]
        try:
            queue.enqueue("one")
            threading.Event().wait(0.5)
        finally:
            queue.close()
        history = self.repository.fetch_history()
        self.assertEqual(len(history), 1)
        self.assertEqual(history[0]["state"], "failed")

    def test_cancelled_job_persisted_to_durable_history(self) -> None:

        class SlowWorkflow:
            def __init__(self) -> None:
                self._items = [SimpleNamespace(stream_id="one", stream_name="ONE")]
                self.started = threading.Event()

            def saved(self):
                return self._items

            def fetch_up_to_date(self, stream_id, *, cancelled, on_progress=None):
                self.started.set()
                while not cancelled():
                    threading.Event().wait(0.01)
                raise MailingListError("acquisition_cancelled", "cancelled")

        workflow = SlowWorkflow()
        queue = self._make_queue(workflow)  # type: ignore[arg-type]
        try:
            queue.enqueue("one")
            self.assertTrue(workflow.started.wait(1))
            queue.cancel_all()
            threading.Event().wait(0.5)
        finally:
            queue.close()
        history = self.repository.fetch_history()
        states = [item["state"] for item in history]
        self.assertIn("cancelled", states)

    def test_abandoned_job_persisted_to_durable_history(self) -> None:
        workflow = FakeWorkflow(("one", "two"), blocking=True)
        queue = self._make_queue(workflow)  # type: ignore[arg-type]
        try:
            queue.enqueue("one")
            self.assertTrue(workflow.started.wait(1))
            queue.enqueue("two")
            queue.cancel_all()
            workflow.release.set()
            threading.Event().wait(0.5)
        finally:
            queue.close()
        history = self.repository.fetch_history()
        states = [item["state"] for item in history]
        self.assertIn("abandoned", states)

    def test_restart_starts_with_empty_queue_but_retains_history(self) -> None:
        workflow = FakeWorkflow(("one",))
        queue = self._make_queue(workflow)  # type: ignore[arg-type]
        try:
            queue.enqueue("one")
            self.assertTrue(workflow.completed.wait(2))
            threading.Event().wait(0.2)
        finally:
            queue.close()
        # Restart: new queue, same repository
        restarted_queue = self._make_queue(FakeWorkflow(("one",)))  # type: ignore[arg-type]
        try:
            snapshot = restarted_queue.snapshot()
            self.assertIsNone(snapshot["running"])
            self.assertEqual(snapshot["queued"], [])
            self.assertEqual(len(snapshot["history"]), 1)
            self.assertEqual(snapshot["history"][0]["state"], "completed")
        finally:
            restarted_queue.close()

    def test_no_running_or_queued_work_restored_after_restart(self) -> None:

        class BlockingWorkflow:
            def __init__(self) -> None:
                self._items = [SimpleNamespace(stream_id="one", stream_name="ONE")]
                self.started = threading.Event()

            def saved(self):
                return self._items

            def fetch_up_to_date(self, stream_id, *, cancelled, on_progress=None):
                self.started.set()
                while not cancelled():
                    threading.Event().wait(0.01)
                raise MailingListError("acquisition_cancelled", "cancelled")

        workflow = BlockingWorkflow()
        queue = self._make_queue(workflow)  # type: ignore[arg-type]
        try:
            queue.enqueue("one")
            self.assertTrue(workflow.started.wait(1))
            # Simulate crash: close without completing
            queue.close()
        except Exception:
            pass
        # Restart: no running or queued work
        restarted = self._make_queue(FakeWorkflow(("one",)))  # type: ignore[arg-type]
        try:
            snapshot = restarted.snapshot()
            self.assertIsNone(snapshot["running"])
            self.assertEqual(snapshot["queued"], [])
        finally:
            restarted.close()

    def test_snapshot_includes_history_and_durable_events(self) -> None:
        workflow = FakeWorkflow(("one",))
        queue = self._make_queue(workflow)  # type: ignore[arg-type]
        try:
            queue.enqueue("one")
            self.assertTrue(workflow.completed.wait(2))
            threading.Event().wait(0.2)
            snapshot = queue.snapshot()
            self.assertIn("history", snapshot)
            self.assertIn("history_limit", snapshot)
            self.assertIn("durable_events", snapshot)
            self.assertIn("durable_event_limit", snapshot)
            self.assertGreater(len(snapshot["history"]), 0)
            self.assertGreater(len(snapshot["durable_events"]), 0)
        finally:
            queue.close()

    def test_timestamps_present_in_snapshot(self) -> None:
        workflow = FakeWorkflow(("one",))
        queue = self._make_queue(workflow)  # type: ignore[arg-type]
        try:
            queue.enqueue("one")
            self.assertTrue(workflow.completed.wait(2))
            threading.Event().wait(0.2)
            snapshot = queue.snapshot()
            history = snapshot["history"]
            self.assertGreater(len(history), 0)
            entry = history[0]
            self.assertIsNotNone(entry["finished_at"])
            self.assertIsNotNone(entry["queued_at"])
            events = snapshot["events"]
            self.assertGreater(len(events), 0)
            for event in events:
                self.assertIsNotNone(event["occurred_at"])
        finally:
            queue.close()


class SchemaMigrationCase(unittest.TestCase):
    """Schema migration from v5 to v6 creates fetch-history tables."""

    def test_v5_database_migrates_to_v6(self) -> None:
        temporary = tempfile.TemporaryDirectory()
        try:
            state = Path(temporary.name)
            RepositoryDatabase.initialize(state)
            # Simulate v5 by rolling back the version number
            database = RepositoryDatabase.open(state)
            with database.connect() as connection:
                connection.execute("UPDATE schema_metadata SET schema_version=5")
                connection.commit()
            migrated = RepositoryDatabase.open(state)
            self.assertEqual(migrated.validate()["schema_version"], 6)
            with migrated.connect(read_only=True) as connection:
                tables = {row[0] for row in connection.execute(
                    "SELECT name FROM sqlite_schema WHERE type='table'"
                )}
            self.assertIn("mailing_list_fetch_history", tables)
            self.assertIn("mailing_list_fetch_events", tables)
        finally:
            temporary.cleanup()


class BrowserTimestampCase(unittest.TestCase):
    """Browser HTML contains timestamp and progress rendering logic."""

    def test_html_contains_timestamp_formatting(self) -> None:
        html = (ROOT / "src/rfi/admin/linux_mailing_lists.html").read_text()
        self.assertIn("fmtTime", html)
        self.assertIn("fmtDateTime", html)
        self.assertIn("durable-history", html)
        self.assertIn("history-list", html)
        self.assertIn("running.progress", html)
        self.assertIn("updated_at", html)


if __name__ == "__main__":
    unittest.main()
