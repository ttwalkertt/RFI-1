"""Minimal process-local FIFO for Linux mailing-list catch-up operations."""

from __future__ import annotations

import threading
import uuid
from collections import deque
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from typing import Any, Callable, Protocol

from rfi.mailing_lists.contracts import FetchProgress, MailingListError
from rfi.mailing_lists.workflow import LinuxMailingListWorkflowService


class FetchHistoryStore(Protocol):
    """Persistence boundary for durable operator-facing terminal history."""

    FETCH_HISTORY_LIMIT: int
    FETCH_EVENT_LIMIT: int

    def record_fetch_history(
        self, *, stream_id: str, stream_name: str, state: str, message: str,
        queued_at: str | None, started_at: str | None, finished_at: str,
        windows_completed: int = 0, result: dict[str, Any] | None = None,
    ) -> None: ...

    def record_fetch_event(
        self, *, sequence: int, occurred_at: str, event: str,
        stream_id: str | None, stream_name: str | None, message: str,
    ) -> None: ...

    def fetch_history(self) -> tuple[dict[str, Any], ...]: ...

    def fetch_events(self) -> tuple[dict[str, Any], ...]: ...


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
    progress: dict[str, Any] | None = None
    latest_progress_message: str | None = None
    last_progress_at: str | None = None
    updated_at: str | None = None


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

    PROGRESS_EVENT_MIN_INTERVAL = 3
    STALE_PROGRESS_SECONDS = 180
    WORKER_MONITOR_SECONDS = 0.25

    def __init__(
        self,
        workflow: LinuxMailingListWorkflowService,
        *,
        history: FetchHistoryStore | None = None,
        clock: Callable[[], str] | None = None,
        now: Callable[[], datetime] | None = None,
        identifiers: Callable[[], str] | None = None,
        event_limit: int = 200,
        job_limit: int = 100,
        stale_progress_seconds: int = STALE_PROGRESS_SECONDS,
        worker_monitor_seconds: float = WORKER_MONITOR_SECONDS,
    ) -> None:
        self.workflow = workflow
        self.history = history
        self.clock = clock or (lambda: datetime.now(UTC).isoformat())
        self.now = now or (lambda: datetime.now(UTC))
        self.identifiers = identifiers or (lambda: f"fetch-{uuid.uuid4().hex}")
        self.event_limit = event_limit
        self.job_limit = job_limit
        self.stale_progress_seconds = stale_progress_seconds
        self.worker_monitor_seconds = worker_monitor_seconds
        self._condition = threading.Condition()
        self._pending: deque[str] = deque()
        self._jobs: dict[str, FetchJob] = {}
        self._job_order: deque[str] = deque()
        self._events: deque[QueueEvent] = deque(maxlen=event_limit)
        self._sequence = 0
        self._running_job_id: str | None = None
        self._running_cancel = threading.Event()
        self._progress_updates_since_event = 0
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
                self._persist_history(job)
            cancellation_requested = self._running_job_id is not None
            if cancellation_requested:
                running = self._jobs[self._running_job_id]
                if running.state == "running":
                    self._running_cancel.set()
                    running.updated_at = self.clock()
                    self._event(
                        "cancellation_requested", running.stream_id, running.stream_name,
                        "Cancellation will take effect at the next safe acquisition checkpoint.",
                    )
                else:
                    cancellation_requested = False
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
            running = None
            if self._running_job_id is not None:
                candidate = self._jobs[self._running_job_id]
                if candidate.state == "running":
                    running = asdict(candidate)
            recent = [
                asdict(self._jobs[job_id]) for job_id in reversed(self._job_order)
                if self._jobs[job_id].state not in {"queued", "running"}
            ]
            durable_history: tuple[dict[str, Any], ...] = ()
            durable_events: tuple[dict[str, Any], ...] = ()
            if self.history is not None:
                durable_history = self.history.fetch_history()
                durable_events = self.history.fetch_events()
            return {
                "running": running,
                "queued": queued,
                "recent": recent,
                "events": [asdict(item) for item in self._events],
                "event_limit": self.event_limit,
                "history": list(durable_history),
                "history_limit": (
                    self.history.FETCH_HISTORY_LIMIT if self.history else 0
                ),
                "durable_events": list(durable_events),
                "durable_event_limit": (
                    self.history.FETCH_EVENT_LIMIT if self.history else 0
                ),
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
                self._progress_updates_since_event = 0
                job.state = "running"
                job.started_at = self.clock()
                job.updated_at = job.started_at
                job.message = "Running bounded acquisition windows."
                self._event("started", job.stream_id, job.stream_name, job.message)

            def on_progress(progress: FetchProgress) -> None:
                with self._condition:
                    job.progress = asdict(progress)
                    job.progress["occurred_at"] = self.clock()
                    job.last_progress_at = job.progress["occurred_at"]
                    job.updated_at = job.last_progress_at
                    job.latest_progress_message = progress.message
                    job.message = progress.message
                    self._maybe_progress_event(job)

            result_box: dict[str, Any] = {}
            error_box: dict[str, BaseException] = {}
            done = threading.Event()

            def execute_fetch() -> None:
                try:
                    result_box["result"] = self.workflow.fetch_up_to_date(
                        job.stream_id,
                        cancelled=self._running_cancel.is_set,
                        on_progress=on_progress,
                    )
                except BaseException as error:
                    error_box["error"] = error
                finally:
                    done.set()

            fetch_thread = threading.Thread(
                target=execute_fetch,
                name=f"mailing-list-fetch-{job.job_id}",
                daemon=True,
            )
            fetch_thread.start()

            terminalized = False

            def terminalize(state: str, event: str, message: str) -> None:
                nonlocal terminalized
                if terminalized:
                    return
                terminalized = True
                job.state = state
                job.finished_at = self.clock()
                job.updated_at = job.finished_at
                job.message = message
                self._event(event, job.stream_id, job.stream_name, job.message)
                self._persist_history(job)

            try:
                while not done.wait(self.worker_monitor_seconds):
                    with self._condition:
                        if terminalized or job.state != "running":
                            continue
                        if self._running_cancel.is_set():
                            continue
                        stale_seconds = self._stale_seconds(job)
                        if stale_seconds is None or stale_seconds < self.stale_progress_seconds:
                            continue
                        self._running_cancel.set()
                        terminalize(
                            "failed",
                            "failed",
                            (
                                "Fetch stalled without meaningful progress for "
                                f"{self.stale_progress_seconds} seconds; "
                                "cancellation was requested "
                                "at the next safe checkpoint."
                            ),
                        )

                error = error_box.get("error")
                result = result_box.get("result")
                with self._condition:
                    if not terminalized:
                        if isinstance(error, MailingListError):
                            if error.code == "acquisition_cancelled":
                                terminalize(
                                    "cancelled",
                                    "cancelled",
                                    "Running fetch was cancelled at a safe checkpoint.",
                                )
                            else:
                                terminalize("failed", "failed", str(error))
                        elif error is not None:
                            terminalize(
                                "failed",
                                "failed",
                                "Fetch failed unexpectedly; inspect server diagnostics.",
                            )
                        else:
                            if result is None:
                                terminalize(
                                    "failed",
                                    "failed",
                                    "Fetch worker returned no result; inspect server diagnostics.",
                                )
                            else:
                                job.result = asdict(result)
                                terminalize("completed", "completed", result.message)
            finally:
                with self._condition:
                    if job.state == "running":
                        terminalize(
                            "failed",
                            "failed",
                            "Fetch worker exited without a terminal state; marked failed.",
                        )
                    self._running_job_id = None
                    self._condition.notify_all()

    def _maybe_progress_event(self, job: FetchJob) -> None:
        self._progress_updates_since_event += 1
        if self._progress_updates_since_event < self.PROGRESS_EVENT_MIN_INTERVAL:
            return
        self._progress_updates_since_event = 0
        self._event(
            "progress", job.stream_id, job.stream_name, job.message,
        )

    def _stale_seconds(self, job: FetchJob) -> float | None:
        candidate = job.last_progress_at or job.started_at
        if candidate is None:
            return None
        try:
            timestamp = datetime.fromisoformat(candidate)
        except ValueError:
            return None
        if timestamp.tzinfo is None:
            timestamp = timestamp.replace(tzinfo=UTC)
        now = self.now()
        if now.tzinfo is None:
            now = now.replace(tzinfo=UTC)
        return (now - timestamp).total_seconds()

    def _event(
        self, event: str, stream_id: str | None, stream_name: str | None, message: str
    ) -> None:
        self._sequence += 1
        entry = QueueEvent(
            self._sequence, self.clock(), event, stream_id, stream_name, message
        )
        self._events.append(entry)
        if event != "progress":
            self._persist_event(entry)

    def _persist_event(self, entry: QueueEvent) -> None:
        if self.history is None:
            return
        try:
            self.history.record_fetch_event(
                sequence=entry.sequence, occurred_at=entry.occurred_at,
                event=entry.event, stream_id=entry.stream_id,
                stream_name=entry.stream_name, message=entry.message,
            )
        except Exception:
            pass

    def _persist_history(self, job: FetchJob) -> None:
        if self.history is None:
            return
        try:
            self.history.record_fetch_history(
                stream_id=job.stream_id, stream_name=job.stream_name,
                state=job.state, message=job.message,
                queued_at=job.queued_at, started_at=job.started_at,
                finished_at=job.finished_at or self.clock(),
                windows_completed=(
                    job.result.get("windows_completed", 0) if job.result else 0
                ),
                result=job.result,
            )
        except Exception:
            pass

    def _trim_jobs(self) -> None:
        while len(self._job_order) > self.job_limit:
            candidate = self._job_order[0]
            if self._jobs[candidate].state in {"queued", "running"}:
                return
            self._job_order.popleft()
            del self._jobs[candidate]
