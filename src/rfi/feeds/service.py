"""One application-owned feed registry, polling, fulfillment, and export service."""

from __future__ import annotations

import base64
import hashlib
import threading
import uuid
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from xml.sax.saxutils import escape

from rfi.acquisition import (
    AcquisitionEngine,
    AcquisitionRepository,
    AdapterRegistry,
    CandidateDocument,
    DiscoveryProvenance,
    RetrievalResult,
    SourceProfile,
)
from rfi.feeds.adapter import FeedEntryAdapter
from rfi.feeds.contracts import (
    FeedDefinition,
    FeedEntry,
    FeedError,
    FeedPollRequest,
    FeedRunOutcome,
    FeedRunResult,
    FeedValidationResult,
)
from rfi.feeds.parser import parse_feed
from rfi.feeds.repository import FeedRepository
from rfi.feeds.transport import FeedHttpTransport, validate_public_url

MAX_FEED_ARTIFACT_BYTES = 10_000_000


def utc_now() -> str:
    return datetime.now(UTC).isoformat()


class FeedService:
    """Share feed semantics across UI, CLI, pull orchestration, and future schedulers."""

    _process_lock = threading.Lock()

    def __init__(
        self,
        state: Path,
        *,
        transport: FeedHttpTransport | None = None,
        clock: Callable[[], str] = utc_now,
        identifier_factory: Callable[[], str] = lambda: uuid.uuid4().hex,
    ) -> None:
        self.state = state
        self.repository = FeedRepository(state)
        self.acquisition = AcquisitionRepository(state / "acquisition")
        self.transport = transport or FeedHttpTransport()
        self.clock = clock
        self.identifier_factory = identifier_factory

    def validate(self, feed_url: str) -> FeedValidationResult:
        try:
            validate_public_url(feed_url)
            parsed = parse_feed(self.transport.fetch(feed_url).content, feed_url)
            return FeedValidationResult(
                True, parsed.format, parsed.title, len(parsed.entries),
                f"Valid {parsed.format.upper()} feed with {len(parsed.entries)} visible entries.",
            )
        except FeedError as error:
            return FeedValidationResult(False, None, None, 0, str(error)[:512])

    def create(self, value: dict[str, Any]) -> FeedDefinition:
        return self._save(value, None, f"feed-{self.identifier_factory()[:20]}")

    def update(self, feed_id: str, value: dict[str, Any], expected: str) -> FeedDefinition:
        return self._save(value, expected, feed_id)

    def _save(
        self, value: dict[str, Any], expected: str | None, feed_id: str
    ) -> FeedDefinition:
        allowed = {"display_name", "feed_url", "enabled", "notes", "firm_ids"}
        if set(value) - allowed:
            raise FeedError("feed definition contains unsupported fields")
        url = value.get("feed_url")
        if not isinstance(url, str):
            raise FeedError("feed URL is required")
        validation = self.validate(url)
        if not validation.valid or validation.format is None:
            raise FeedError(validation.diagnostic)
        firm_ids = value.get("firm_ids", [])
        if not isinstance(firm_ids, list) or any(not isinstance(item, str) for item in firm_ids):
            raise FeedError("firm_ids must be an array of strings")
        enabled = value.get("enabled", True)
        if not isinstance(enabled, bool):
            raise FeedError("enabled must be true or false")
        return self.repository.create_revision(
            feed_id=feed_id,
            display_name=str(value.get("display_name", "")),
            feed_url=url,
            enabled=enabled,
            notes=str(value.get("notes", "")),
            firm_ids=tuple(firm_ids),
            format=validation.format,
            created_at=self.clock(),
            expected_revision_id=expected,
        )

    def retire(self, feed_id: str, expected: str) -> FeedDefinition:
        current = self.repository.get(feed_id)
        return self.repository.create_revision(
            feed_id=feed_id, display_name=current.display_name, feed_url=current.feed_url,
            enabled=False, notes=current.notes, firm_ids=current.firm_ids, format=current.format,
            created_at=self.clock(), lifecycle_status="retired", expected_revision_id=expected,
        )

    def poll(self, request: FeedPollRequest) -> FeedRunResult:
        if not self._process_lock.acquire(blocking=False):
            raise FeedError("another feed poll is already running")
        try:
            return self._poll(request)
        finally:
            self._process_lock.release()

    def _poll(self, request: FeedPollRequest) -> FeedRunResult:
        if request.feed_ids and request.firm_ids:
            raise FeedError("select feed IDs or firm IDs, not both")
        if request.feed_ids:
            feeds = tuple(
                self.repository.get(feed_id)
                for feed_id in dict.fromkeys(request.feed_ids)
            )
        elif request.firm_ids:
            feeds = self.repository.select_for_firms(tuple(dict.fromkeys(request.firm_ids)))
        else:
            feeds = tuple(item for item in self.repository.list() if item.enabled)
        run_id = f"feedrun-{self.identifier_factory()[:24]}"
        started = self.clock()
        initial = {
            "schema_version": 1, "run_id": run_id, "trigger": request.trigger,
            "requested_at": started, "completed_at": "", "outcome": "running",
            "selected_feed_ids": [item.feed_id for item in feeds],
            "firm_ids": list(request.firm_ids), "parent_pull_run_id": request.parent_pull_run_id,
            "summary": self._summary(()), "feeds": [], "diagnostics": [],
            "termination_reason": "running",
        }
        self.repository.create_run(initial)
        results: list[dict[str, Any]] = []
        for feed in feeds:
            results.append(self._poll_feed(run_id, feed, request.trigger == "retry"))
        summary = self._summary(tuple(results))
        unavailable = summary["entries_unavailable"]
        failures = summary["feeds_failed"]
        outcome = (
            FeedRunOutcome.PARTIAL if failures
            else FeedRunOutcome.COMPLETED_WITH_UNAVAILABLE if unavailable
            else FeedRunOutcome.COMPLETED
        )
        result = FeedRunResult(
            run_id, request.trigger, started, self.clock(), outcome,
            tuple(item.feed_id for item in feeds), tuple(request.firm_ids), summary,
            tuple(results), tuple(
                {
                    "feed_id": item["feed_id"],
                    "category": "feed_failure",
                    "message": item["diagnostic"][:512],
                }
                for item in results if item["status"] == "failed"
            ), request.parent_pull_run_id,
        )
        self.repository.save_run(result.to_dict())
        return result

    def _poll_feed(
        self, run_id: str, feed: FeedDefinition, force_retry: bool = False
    ) -> dict[str, Any]:
        result: dict[str, Any] = {
            "feed_id": feed.feed_id, "display_name": feed.display_name,
            "feed_url": feed.feed_url, "format": feed.format, "status": "completed",
            "entries_observed": 0, "entries_new": 0, "entries_updated": 0,
            "entries_unchanged": 0, "acquisition_requests": 0,
            "artifacts_retained": 0, "duplicates": 0,
            "tombstones_created": 0, "tombstones_updated": 0,
            "entries_unavailable": 0,
            "diagnostic": "feed exhausted",
            "entry_results": [],
        }
        try:
            parsed = parse_feed(self.transport.fetch(feed.feed_url).content, feed.feed_url)
        except FeedError as error:
            result.update(status="failed", diagnostic=str(error)[:512])
            return result
        selected: list[tuple[FeedEntry, str]] = []
        dispositions: dict[str, str] = {}
        unavailable = {
            item["entry"]["entry_key"]: item for item in self.repository.tombstones()
            if item["feed_id"] == feed.feed_id and item["status"] != "fulfilled"
        }
        observed_at = self.clock()
        for entry in parsed.entries:
            disposition, _observation_id, material_hash = self.repository.observe_entry(
                feed, entry, observed_at
            )
            result["entries_observed"] += 1
            result[f"entries_{disposition}"] += 1
            dispositions[entry.entry_key] = disposition
            tombstone = unavailable.get(entry.entry_key)
            if disposition != "unchanged" or (
                tombstone is not None and (tombstone.get("retry_eligible") or force_retry)
            ):
                selected.append((entry, material_hash))
            elif tombstone is not None:
                result["entries_unavailable"] += 1
                self.repository.touch_tombstone_observation(
                    feed.feed_id, entry, observed_at
                )
        result["acquisition_requests"] = len(selected)
        if not selected:
            return result
        for entry_index, (entry, material_hash) in enumerate(selected, 1):
            source_id = "feedsource-" + hashlib.sha256(
                f"{feed.revision_id}\0{entry.entry_key}\0{material_hash}".encode()
            ).hexdigest()[:24]
            source = SourceProfile(
                source_id, feed.display_name, True, FeedEntryAdapter.mechanism,
                {"feed_url": feed.feed_url},
                {"feed_id": feed.feed_id, "feed_revision_id": feed.revision_id,
                 "entry_key": entry.entry_key[:512]},
            )
            self.acquisition.register_source(source)
            adapter = FeedEntryAdapter(((entry, material_hash),), self.transport, self.clock)
            engine = AcquisitionEngine(self.acquisition, AdapterRegistry((adapter,)), self.clock)
            acquisition = engine.run_source(source_id, f"{run_id}-entry-{entry_index}")
            if not acquisition.outcomes:
                diagnostic = next(
                    (
                        str(item.get("message"))
                        for item in acquisition.diagnostics
                        if item.get("message")
                    ),
                    "acquisition engine returned no entry outcome",
                )
                tombstone = self.repository.record_unavailable(
                    feed, entry, self.clock(), "retrieval_failure", diagnostic,
                    any(bool(item.get("retryable")) for item in acquisition.diagnostics), run_id,
                )
                tombstone_counter = (
                    "tombstones_updated"
                    if unavailable.get(entry.entry_key)
                    else "tombstones_created"
                )
                result[tombstone_counter] += 1
                result["entries_unavailable"] += 1
                result["entry_results"].append({
                    "entry_id": entry.entry_key, "title": entry.title, "url": entry.url,
                    "disposition": dispositions[entry.entry_key], "acquisition_outcome": "failed",
                    "attempt_id": None, "artifact_id": None,
                    "tombstone_id": tombstone["tombstone_id"], "diagnostic": diagnostic[:512],
                    "acquisition_run_id": acquisition.run_id,
                })
                continue
            outcome = acquisition.outcomes[0]
            entry_result = {
                "entry_id": entry.entry_key, "title": entry.title,
                "url": entry.url, "disposition": dispositions[entry.entry_key],
                "acquisition_outcome": outcome.outcome, "attempt_id": outcome.attempt_id,
                "artifact_id": None, "tombstone_id": None,
                "diagnostic": outcome.diagnostic[:512],
                "acquisition_run_id": acquisition.run_id,
            }
            attempt = (
                self.acquisition.attempt(outcome.attempt_id)
                if outcome.attempt_id is not None else {}
            )
            artifact_id = attempt.get("artifact_id")
            if outcome.durable and isinstance(artifact_id, str):
                entry_result["artifact_id"] = artifact_id
                result["artifacts_retained"] += 1
                if outcome.outcome == "duplicate":
                    result["duplicates"] += 1
                self.repository.link_artifact(
                    feed.feed_id, entry.entry_key, material_hash, artifact_id,
                    str(outcome.attempt_id), self.clock(),
                )
            else:
                prior = unavailable.get(entry.entry_key)
                category = next((str(item.get("failure_class")) for item in acquisition.diagnostics
                                 if item.get("message") == outcome.diagnostic), "retrieval_failure")
                tombstone = self.repository.record_unavailable(
                    feed, entry, self.clock(), category, outcome.diagnostic,
                    any(bool(item.get("retryable")) for item in acquisition.diagnostics), run_id,
                )
                entry_result["tombstone_id"] = tombstone["tombstone_id"]
                result["tombstones_updated" if prior else "tombstones_created"] += 1
                result["entries_unavailable"] += 1
            result["entry_results"].append(entry_result)
        return result

    @staticmethod
    def _summary(feeds: tuple[dict[str, Any], ...]) -> dict[str, int]:
        keys = (
            "entries_observed", "entries_new", "entries_updated", "entries_unchanged",
            "acquisition_requests", "artifacts_retained", "duplicates",
            "tombstones_created", "tombstones_updated",
            "entries_unavailable",
        )
        result = {key: sum(int(item.get(key, 0)) for item in feeds) for key in keys}
        result.update(
            feeds_selected=len(feeds),
            feeds_succeeded=sum(item.get("status") == "completed" for item in feeds),
            feeds_failed=sum(item.get("status") == "failed" for item in feeds),
        )
        return result

    def retry(self, tombstone_id: str) -> FeedRunResult:
        tombstone = self.repository.tombstone(tombstone_id)
        return self.poll(FeedPollRequest((tombstone["feed_id"],), trigger="retry"))

    def fulfill_upload(self, tombstone_id: str, encoded: str, media_type: str) -> dict[str, Any]:
        try:
            content = base64.b64decode(encoded, validate=True)
        except ValueError as error:
            self.repository.record_fulfillment_attempt(
                tombstone_id, self.clock(), "manual_upload", "failed", "invalid base64 upload"
            )
            raise FeedError("uploaded artifact is not valid base64") from error
        if not content:
            self.repository.record_fulfillment_attempt(
                tombstone_id, self.clock(), "manual_upload", "failed", "empty upload"
            )
            raise FeedError("uploaded artifact is empty")
        if len(content) > MAX_FEED_ARTIFACT_BYTES:
            self.repository.record_fulfillment_attempt(
                tombstone_id,
                self.clock(),
                "manual_upload",
                "failed",
                f"upload exceeds {MAX_FEED_ARTIFACT_BYTES} bytes",
            )
            raise FeedError(
                f"uploaded artifact exceeds {MAX_FEED_ARTIFACT_BYTES} bytes"
            )
        try:
            return self._fulfill(tombstone_id, content, media_type, "manual_upload", None)
        except Exception as error:
            self.repository.record_fulfillment_attempt(
                tombstone_id, self.clock(), "manual_upload", "failed", str(error)
            )
            raise

    def fulfill_url(self, tombstone_id: str, alternate_url: str) -> dict[str, Any]:
        try:
            validate_public_url(alternate_url)
            response = self.transport.fetch(alternate_url)
            return self._fulfill(
                tombstone_id, response.content, response.media_type,
                "manual_alternate_url", alternate_url
            )
        except Exception as error:
            self.repository.record_fulfillment_attempt(
                tombstone_id, self.clock(), "manual_alternate_url", "failed", str(error)
            )
            raise

    def _fulfill(
        self, tombstone_id: str, content: bytes, media_type: str, mechanism: str,
        alternate_url: str | None,
    ) -> dict[str, Any]:
        tombstone = self.repository.tombstone(tombstone_id)
        if tombstone["status"] == "fulfilled":
            raise FeedError("unavailable entry is already fulfilled")
        entry = FeedEntry(**tombstone["entry"])
        digest = hashlib.sha256(content).hexdigest()
        source_id = "feedmanual-" + hashlib.sha256(tombstone_id.encode()).hexdigest()[:24]
        source = SourceProfile(
            source_id, "Manual feed fulfillment", True, "manual_feed_fulfillment",
            {}, {"feed_id": tombstone["feed_id"], "operator_supplied": True},
        )
        self.acquisition.register_source(source)
        candidate = CandidateDocument(
            "feedfulfillment-" + digest[:24], source_id,
            "feeddocument-" + hashlib.sha256(entry.entry_key.encode()).hexdigest()[:24],
            DiscoveryProvenance(
                self.clock(), "manual_feed_fulfillment",
                {"tombstone_id": tombstone_id},
                tuple(value for value in (entry.url, alternate_url) if value),
                {"configured_source": True},
            ),
        )
        attempt_id = "feedattempt-" + hashlib.sha256(
            f"{tombstone_id}\0{digest}\0{mechanism}".encode()
        ).hexdigest()[:24]
        receipt = self.acquisition.record_success(
            attempt_id, candidate,
            RetrievalResult(
                content, media_type.split(";", 1)[0].lower(), self.clock(),
                "manual_feed_fulfillment", {},
                {"fulfillment_method": mechanism, "alternate_url": alternate_url or ""},
            ),
        )
        current = next(item for item in self.repository.export_items(500)
                       if item["feed_id"] == tombstone["feed_id"]
                       and item["entry"]["entry_key"] == entry.entry_key)
        self.repository.link_artifact(
            tombstone["feed_id"], entry.entry_key, current["material_hash"],
            receipt.artifact_id, receipt.attempt_id, self.clock(),
        )
        self.repository.record_fulfillment_attempt(
            tombstone_id, self.clock(), mechanism, "fulfilled",
            f"linked artifact {receipt.artifact_id}",
        )
        return {
            "tombstone_id": tombstone_id, "status": "fulfilled",
            "artifact_id": receipt.artifact_id, "attempt_id": receipt.attempt_id,
            "duplicate_content": receipt.idempotent or not receipt.artifact_created,
            "candidate_metadata": {
                "media_type": media_type,
                "byte_count": len(content),
                "sha256": digest,
            },
        }

    def rss_export(self) -> bytes:
        items = self.repository.export_items(200)
        rows = []
        for item in items:
            entry = item["entry"]
            description = entry.get("summary") or ""
            if item["availability"] == "unavailable":
                description = "[Unavailable artifact] " + description
            rows.append(
                "<item><title>" + escape(entry.get("title") or "Untitled entry") + "</title>"
                + ("<link>" + escape(entry["url"]) + "</link>" if entry.get("url") else "")
                + "<guid isPermaLink=\"false\">"
                + escape(item["feed_id"] + ":" + entry["entry_key"])
                + "</guid>"
                + (
                    "<pubDate>" + escape(entry["published_at"]) + "</pubDate>"
                    if entry.get("published_at")
                    else ""
                )
                + "<description>" + escape(description) + "</description>"
                + "<rfi:availability>" + item["availability"] + "</rfi:availability>"
                + (
                    "<rfi:artifactId>"
                    + escape(item["artifact_id"])
                    + "</rfi:artifactId>"
                    if item.get("artifact_id")
                    else ""
                )
                + "</item>"
            )
        document = (
            '<?xml version="1.0" encoding="utf-8"?>'
            '<rss version="2.0" xmlns:rfi="https://rfi.local/ns/feed/1"><channel>'
            '<title>RFI aggregate feed observations</title><link>https://rfi.local/feeds</link>'
            '<description>Durable normalized repository feed observations.</description>'
            + "".join(rows) + "</channel></rss>"
        )
        return document.encode()
