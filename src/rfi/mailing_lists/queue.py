"""Minimal process-local FIFO for Linux mailing-list catch-up operations."""

from __future__ import annotations

import threading
import uuid
from collections import deque
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from typing import Any, Callable

from rfi.mailing_lists.contracts import MailingListError
from rfi.mailing_lists.workflow import LinuxMailingListWorkflowService


@dataclass
class FetchJob:
    job_id: str
    stream_id: str
    stream_name: str
    state: str
    queued_at: str
    started_at: str | None = None
    finished_at: str | None = None
    message: str = ""
    result: dict[str, Any] | None = None


@dataclass(frozen=True)
class QueueEvent:
    sequence: int
    occurred_at: str
    event: str
    stream_id: str | None
    stream_name: str | None
    message: str


class MailingListFetchQueue:
    """One-worker FIFO with duplicate suppression and cooperative cancellation."""

    def __init__(
        self,
        workflow: LinuxMailingListWorkflowService,
        *,
        clock: Callable[[], str] | None = None,
        identifiers: Callable[[], str] | None = None,
        event_limit: int = 200,
        job_limit: int = 100,
    ) -> None:
        self.workflow = workflow
        self.clock = clock or (lambda: datetime.now(UTC).isoformat())
        self.identifiers = identifiers or (lambda: f"fetch-{uuid.uuid4().hex}")
        self.event_limit = event_limit
        self.job_limit = job_limit
        self._condition = threading.Condition()
        self._pending: deque[str] = deque()
        self._jobs: dict[str, FetchJob] = {}
        self._job_order: deque[str] = deque()
        self._events: deque[QueueEvent] = deque(maxlen=event_limit)
        self._sequence = 0
        self._running_job_id: str | None = None
        self._running_cancel = threading.Event()
        self._closing = False
        self._worker = threading.Thread(
            target=self._work, name="mailing-list-fetch-queue", daemon=True
        )
        self._worker.start()

    def enqueue(self, stream_id: str) -> dict[str, Any]:
        summary = next(
            (item for item in self.workflow.saved() if item.stream_id == stream_id), None
        )
        if summary is None:
            raise MailingListError("unknown_stream", f"unknown mailing-list stream: {stream_id}")
        with self._condition:
            duplicate = next(
                (
                    job for job in self._jobs.values()
                    if job.stream_id == stream_id and job.state in {"queued", "running"}
                ),
                None,
            )
            if duplicate is not None:
                self._event(
                    "duplicate_ignored", stream_id, summary.stream_name,
                    "A queued or running fetch already covers this stream.",
                )
                return {"accepted": False, "duplicate": True, "job": asdict(duplicate)}
            job = FetchJob(
                self.identifiers(), stream_id, summary.stream_name, "queued", self.clock(),
                message="Waiting for the single acquisition worker.",
            )
            self._jobs[job.job_id] = job
            self._job_order.append(job.job_id)
            self._pending.append(job.job_id)
            self._event(
                "queued", stream_id, summary.stream_name,
                "Fetch up to date was added to the FIFO queue.",
            )
            self._trim_jobs()
            self._condition.notify()
            return {"accepted": True, "duplicate": False, "job": asdict(job)}

    def enqueue_all(self) -> dict[str, Any]:
        results = [self.enqueue(item.stream_id) for item in self.workflow.saved()]
        return {
            "eligible": len(results),
            "queued": sum(bool(item["accepted"]) for item in results),
            "duplicates_ignored": sum(bool(item["duplicate"]) for item in results),
            "items": results,
        }

    def cancel_all(self) -> dict[str, int | bool]:
        with self._condition:
            abandoned = 0
            while self._pending:
                job = self._jobs[self._pending.popleft()]
                if job.state != "queued":
                    continue
                job.state = "abandoned"
                job.finished_at = self.clock()
                job.message = "Queued fetch was abandoned before it started."
                abandoned += 1
                self._event(
                    "abandoned", job.stream_id, job.stream_name, job.message
                )
            cancellation_requested = self._running_job_id is not None
            if cancellation_requested:
                running = self._jobs[self._running_job_id]
                self._running_cancel.set()
                self._event(
                    "cancellation_requested", running.stream_id, running.stream_name,
                    "Cancellation will take effect at the next safe acquisition checkpoint.",
                )
            self._condition.notify_all()
            return {
                "abandoned": abandoned,
                "cancellation_requested": cancellation_requested,
            }

    def snapshot(self) -> dict[str, Any]:
        with self._condition:
            queued = [
                asdict(self._jobs[job_id]) for job_id in self._pending
                if self._jobs[job_id].state == "queued"
            ]
            running = (
                asdict(self._jobs[self._running_job_id])
                if self._running_job_id is not None else None
            )
            recent = [
                asdict(self._jobs[job_id]) for job_id in reversed(self._job_order)
                if self._jobs[job_id].state not in {"queued", "running"}
            ]
            return {
                "running": running,
                "queued": queued,
                "recent": recent,
                "events": [asdict(item) for item in self._events],
                "event_limit": self.event_limit,
                "restart_behavior": "process_local_queue_resets_durable_evidence_remains",
            }

    def close(self) -> None:
        with self._condition:
            self._closing = True
            self._running_cancel.set()
            self._condition.notify_all()
        self._worker.join(timeout=2)

    def _work(self) -> None:
        while True:
            with self._condition:
                while not self._pending and not self._closing:
                    self._condition.wait()
                if self._closing:
                    return
                job_id = self._pending.popleft()
                job = self._jobs[job_id]
                if job.state != "queued":
                    continue
                self._running_job_id = job_id
                self._running_cancel = threading.Event()
                job.state = "running"
                job.started_at = self.clock()
                job.message = "Running bounded acquisition windows."
                self._event("started", job.stream_id, job.stream_name, job.message)
            try:
                result = self.workflow.fetch_up_to_date(
                    job.stream_id, cancelled=self._running_cancel.is_set
                )
            except MailingListError as error:
                with self._condition:
                    if error.code == "acquisition_cancelled":
                        job.state = "cancelled"
                        job.message = "Running fetch was cancelled at a safe checkpoint."
                        event = "cancelled"
                    else:
                        job.state = "failed"
                        job.message = str(error)
                        event = "failed"
                    job.finished_at = self.clock()
                    self._event(event, job.stream_id, job.stream_name, job.message)
            except Exception:
                with self._condition:
                    job.state = "failed"
                    job.finished_at = self.clock()
                    job.message = "Fetch failed unexpectedly; inspect server diagnostics."
                    self._event("failed", job.stream_id, job.stream_name, job.message)
            else:
                with self._condition:
                    job.state = "completed"
                    job.finished_at = self.clock()
                    job.message = result.message
                    job.result = asdict(result)
                    self._event("completed", job.stream_id, job.stream_name, job.message)
            finally:
                with self._condition:
                    self._running_job_id = None
                    self._condition.notify_all()

    def _event(
        self, event: str, stream_id: str | None, stream_name: str | None, message: str
    ) -> None:
        self._sequence += 1
        self._events.append(
            QueueEvent(self._sequence, self.clock(), event, stream_id, stream_name, message)
        )

    def _trim_jobs(self) -> None:
        while len(self._job_order) > self.job_limit:
            candidate = self._job_order[0]
            if self._jobs[candidate].state in {"queued", "running"}:
                return
            self._job_order.popleft()
            del self._jobs[candidate]
