"""Task-specific Linux mailing-list workflow over existing repository services."""

from __future__ import annotations

import hashlib
import re
from dataclasses import asdict, dataclass, replace
from datetime import UTC, date, datetime, timedelta
from typing import Any, Callable

from rfi.mailing_lists.contracts import (
    AcquisitionManifest,
    AcquisitionMessage,
    AcquisitionRunStatus,
    LoreTransportPolicy,
    MailingListError,
    MailingListSource,
    SelectionCriteria,
    AcquisitionLimits,
    normalize_lore_archive,
)
from rfi.mailing_lists.provider import LoreArchive
from rfi.mailing_lists.repository import MailingListRepository
from rfi.mailing_lists.service import (
    MailingListAcquisitionService,
    MailingListQueryService,
    MailingListSourceService,
)
from rfi.streams import StreamDraft, StreamError, StreamRevision, StreamRun, StreamService
from rfi.streams.definition import normalize_draft, semantic_fingerprint

_REPOSITORY_ID = re.compile(r"[a-z][a-z0-9._-]{0,99}")


@dataclass(frozen=True)
class LoreCatalogEntry:
    archive_id: str
    display_name: str
    canonical_url: str
    description: str


LORE_CATALOG = (
    LoreCatalogEntry(
        "linux-block", "Linux block layer", "https://lore.kernel.org/linux-block/",
        "Block I/O, storage stacks, request queues, and related driver development.",
    ),
    LoreCatalogEntry(
        "linux-nvme", "Linux NVMe", "https://lore.kernel.org/linux-nvme/",
        "Linux NVMe host, target, transport, and device discussions.",
    ),
    LoreCatalogEntry(
        "linux-scsi", "Linux SCSI", "https://lore.kernel.org/linux-scsi/",
        "Linux SCSI subsystem, transports, drivers, and storage devices.",
    ),
    LoreCatalogEntry(
        "lkml", "Linux kernel mailing list", "https://lore.kernel.org/lkml/",
        "The main Linux kernel development mailing-list archive.",
    ),
)


@dataclass(frozen=True)
class MailingListWorkflowDraft:
    archive_url: str
    stream_name: str
    description: str
    date_from: str
    date_through: str
    keywords: tuple[str, ...]
    subjects: tuple[str, ...]
    participants: tuple[str, ...]
    seed_limit: int
    total_limit: int
    descendant_depth: int


@dataclass(frozen=True)
class MailingListWorkflowReview:
    draft: MailingListWorkflowDraft
    archive: LoreCatalogEntry
    source: MailingListSource
    stream: StreamDraft
    fingerprint: str
    records_to_create: tuple[str, ...]
    actions_on_create_and_test: tuple[str, ...]
    actions_not_performed: tuple[str, ...]
    warnings: tuple[str, ...]


@dataclass(frozen=True)
class ArchiveValidationResult:
    reachable: bool
    archive: LoreCatalogEntry
    observed_title: str
    observed_updated: str
    canonical_url: str


@dataclass(frozen=True)
class WorkflowCreateResult:
    status: str
    source: MailingListSource
    source_created: bool
    revision: StreamRevision | None
    failed_stage: str | None
    message: str
    retry_safe: bool


@dataclass(frozen=True)
class WorkflowTestResult:
    status: str
    failed_stage: str | None
    message: str
    retry_safe: bool
    stream_id: str
    source_id: str
    acquisition: AcquisitionManifest | dict[str, Any] | None
    stream_run: StreamRun | None
    messages: tuple[AcquisitionMessage, ...]
    configuration_ready: bool
    test_evidence_status: str
    incomplete_or_truncated: bool


@dataclass(frozen=True)
class SavedMailingListWorkflow:
    stream_id: str
    stream_name: str
    revision_id: str
    revision_number: int
    source_id: str
    archive_name: str
    archive_url: str
    latest_acquisition_run_id: str | None
    latest_acquisition_status: str | None
    latest_stream_run_id: str | None
    latest_stream_status: str | None
    configuration_status: str
    test_evidence_status: str
    effective_last_fetch_date: str | None


@dataclass(frozen=True)
class FetchUpToDateResult:
    stream_id: str
    status: str
    window_start: str
    window_end: str
    windows_completed: int
    acquisition_run_ids: tuple[str, ...]
    effective_last_fetch_date: str | None
    message: str


class LinuxMailingListWorkflowService:
    """Operator-task façade that preserves source, stream, and acquisition authorities."""

    def __init__(
        self,
        repository: MailingListRepository,
        source_service: MailingListSourceService,
        stream_service: StreamService,
        query_service: MailingListQueryService,
        *,
        archive_factory: Callable[[MailingListSource], LoreArchive] = LoreArchive,
        today: Callable[[], date] | None = None,
    ) -> None:
        self.repository = repository
        self.source_service = source_service
        self.stream_service = stream_service
        self.query_service = query_service
        self.archive_factory = archive_factory
        self.today = today or (lambda: datetime.now(UTC).date())

    def catalog(self) -> tuple[LoreCatalogEntry, ...]:
        return LORE_CATALOG

    def defaults(self, archive_url: str | None = None) -> MailingListWorkflowDraft:
        archive = archive_url or LORE_CATALOG[0].canonical_url
        through = self.today()
        return MailingListWorkflowDraft(
            archive, "Linux Block Mailing List", "Bounded Linux block-layer discussion evidence",
            (through - timedelta(days=7)).isoformat(), through.isoformat(), (), (), (), 5, 50, 3,
        )

    def review(self, value: Any) -> MailingListWorkflowReview:
        draft = self._draft(value)
        archive_id, canonical_url = normalize_lore_archive(draft.archive_url)
        archive = next(
            (item for item in LORE_CATALOG if item.canonical_url == canonical_url),
            LoreCatalogEntry(
                archive_id, archive_id.replace("-", " ").title(), canonical_url,
                "Operator-supplied Lore mailing-list archive.",
            ),
        )
        source = self._source(archive)
        selection = self._selection(draft)
        stream_id = self._stream_id(draft, source.source_id, selection)
        stream = StreamDraft(
            stream_id, draft.stream_name, draft.description, True, "external",
            (source.source_id,), "mail.message", selection,
            {
                "strategy": "connected_discussion", "ancestor_closure": True,
                "descendant_depth": draft.descendant_depth,
            },
            {"seed_limit": draft.seed_limit, "expanded_limit": draft.total_limit},
        )
        validation = self.stream_service.validate(
            stream, provisional_external_sources=(source.source_id,)
        )
        if not validation.valid:
            first = validation.errors[0]
            raise MailingListError(first["code"], first["message"])
        warnings = ()
        if not draft.keywords and not draft.subjects and not draft.participants:
            warnings = (
                "The initial sample is bounded by date and hard limits but has no "
                "relevance filter.",
            )
        records = []
        if not any(item.source_id == source.source_id for item in self.repository.sources()):
            records.append("governed Lore source")
        try:
            self.stream_service.detail(stream.stream_id)
        except StreamError:
            records.append("mailing-list stream and immutable revision 1")
        else:
            records.append("no new configuration if the generated definition is already current")
        return MailingListWorkflowReview(
            draft, archive, source, stream,
            hashlib.sha256(
                f"{canonical_url}:{semantic_fingerprint(stream)}".encode()
            ).hexdigest(),
            tuple(records),
            (
                "validate archive reachability", "create or resolve the governed source",
                "create or resolve the stream revision", "retrieve a bounded Lore sample",
                "reconstruct connected discussion context", "store immutable evidence",
                "execute the saved stream projection", "show the retained messages",
            ),
            (
                "mirror the archive", "schedule background polling", "delete prior evidence",
                "modify an existing governed source", "persist anything during review",
            ),
            warnings,
        )

    def validate_archive(self, value: Any) -> ArchiveValidationResult:
        review = self.review(value)
        observed = self.archive_factory(review.source).probe()
        return ArchiveValidationResult(
            True, review.archive, observed["title"], observed["updated"],
            observed["canonical_url"],
        )

    def create(self, value: Any) -> WorkflowCreateResult:
        review = self.review(value)
        self.archive_factory(review.source).probe()
        source_created = False
        try:
            existing = next(
                (
                    source for source in self.repository.sources()
                    if source.source_id == review.source.source_id
                ),
                None,
            )
            if existing is None:
                source, source_created = self.source_service.create(asdict(review.source))
            else:
                _, existing_url = normalize_lore_archive(existing.archive_base_url)
                if existing_url != review.source.archive_base_url:
                    raise MailingListError(
                        "source_conflict", "configured mailing-list source differs"
                    )
                source = existing
        except MailingListError as error:
            return WorkflowCreateResult(
                "failed", review.source, False, None, "creating governed source",
                str(error), error.retryable,
            )
        try:
            try:
                current = self.stream_service.detail(review.stream.stream_id)
            except StreamError:
                current = None
            if current and normalize_draft(current.draft) == normalize_draft(review.stream):
                revision = current
                status = "no_change"
                message = (
                    "The governed source and stream definition already exist; nothing changed."
                )
            else:
                revision = self.stream_service.save(review.stream, None)
                status = "created"
                message = "The governed source and mailing-list stream were created."
            return WorkflowCreateResult(
                status, source, source_created, revision, None, message, True
            )
        except StreamError as error:
            return WorkflowCreateResult(
                "partial", source, source_created, None, "creating stream revision",
                f"The governed source is durable, but the stream was not created: {error}", True,
            )

    def save(self, stream_id: str, value: Any) -> WorkflowCreateResult:
        """Save an edited workflow as the next authoritative revision of one stream."""
        current = self.stream_service.detail(stream_id)
        draft = self._draft(value)
        archive_id, canonical_url = normalize_lore_archive(draft.archive_url)
        archive = next(
            (item for item in LORE_CATALOG if item.canonical_url == canonical_url),
            LoreCatalogEntry(
                archive_id, archive_id.replace("-", " ").title(), canonical_url,
                "Operator-supplied Lore mailing-list archive.",
            ),
        )
        source = self._source(archive)
        source_created = False
        if not any(item.source_id == source.source_id for item in self.repository.sources()):
            source, source_created = self.source_service.create(asdict(source))
        intended = StreamDraft(
            stream_id, draft.stream_name, draft.description, True, "external",
            (source.source_id,), "mail.message", self._selection(draft),
            {
                "strategy": "connected_discussion", "ancestor_closure": True,
                "descendant_depth": draft.descendant_depth,
            },
            {"seed_limit": draft.seed_limit, "expanded_limit": draft.total_limit},
        )
        validation = self.stream_service.validate(intended)
        if not validation.valid:
            first = validation.errors[0]
            raise MailingListError(first["code"], first["message"])
        if normalize_draft(current.draft) == normalize_draft(intended):
            return WorkflowCreateResult(
                "no_change", source, source_created, current, None,
                "The authoritative stream revision is already current.", True,
            )
        revision = self.stream_service.save(intended, current.revision_id)
        return WorkflowCreateResult(
            "revised", source, source_created, revision, None,
            f"Saved authoritative stream revision {revision.revision_number}.", True,
        )

    def test(self, stream_id: str) -> WorkflowTestResult:
        revision = self.stream_service.detail(stream_id)
        if (
            revision.draft.input_kind != "external"
            or revision.draft.schema_id != "mail.message"
        ):
            raise MailingListError(
                "not_mailing_list_workflow", "selected stream is not a Lore mailing-list stream"
            )
        source_id = revision.draft.input_ids[0]
        source = self.repository.source(source_id)
        criteria = self._criteria(revision.draft)
        context_limit = (
            revision.draft.bounds["expanded_limit"]
            - revision.draft.bounds["seed_limit"]
        )
        limits = AcquisitionLimits(
            revision.draft.bounds["seed_limit"], context_limit,
            int(revision.draft.expansion.get("descendant_depth", 0)),
        )
        before = {item["run_id"] for item in self.repository.acquisition_runs(source_id)}
        acquisition_service = MailingListAcquisitionService(
            self.repository, self.archive_factory(source)
        )
        try:
            manifest = acquisition_service.acquire(source_id, criteria, limits)
        except MailingListError as error:
            latest = self._new_acquisition(source_id, before)
            message = str(error)
            retry_safe = error.retryable
            if error.code == "no_seed_matches":
                message = (
                    "No Lore messages matched the bounded scope. Revise the dates or relevance "
                    "controls, then retry safely."
                )
                retry_safe = True
            evidence_status = "empty" if error.code == "no_seed_matches" else "failed"
            return WorkflowTestResult(
                "failed", "retrieving bounded sample", message, retry_safe,
                stream_id, source_id, latest, None, (), True, evidence_status,
                evidence_status == "failed",
            )
        messages = self.query_service.acquisition_messages(manifest.run_id)
        if manifest.run_status != AcquisitionRunStatus.SUCCEEDED:
            return WorkflowTestResult(
                "failed", "retrieving bounded sample",
                "Lore returned only a partial acquisition; retained evidence is inspectable "
                "but verification did not complete.",
                manifest.retryable, stream_id, source_id, manifest, None, messages, True,
                "partial", True,
            )
        if manifest.message_count == 0:
            return WorkflowTestResult(
                "failed", "retrieving bounded sample",
                "No Lore messages matched the bounded scope. Revise the dates or relevance "
                "controls, then retry safely.",
                True, stream_id, source_id, manifest, None, (), True, "empty", False,
            )
        try:
            stream_run = self.stream_service.run(stream_id)
        except StreamError as error:
            return WorkflowTestResult(
                "failed", "publishing stream result", str(error), True, stream_id, source_id,
                manifest, None, messages, True, "failed", manifest.truncated,
            )
        incomplete = (
            not manifest.discovery_complete
            or not manifest.required_ancestry_complete
            or not manifest.descendant_policy_complete
            or manifest.unexpected_truncation
            or manifest.state.value in {
                "incomplete", "quarantined"
            }
        )
        return WorkflowTestResult(
            "tested_incomplete" if incomplete else "ready", None,
            (
                "The bounded Lore test stored inspectable evidence with an explicit acquisition "
                "incompleteness warning. The saved configuration remains executable."
                if incomplete
                else "The saved configuration is executable and the bounded test evidence is "
                + (
                    "structurally connected with explicitly unavailable ancestor tombstones."
                    if manifest.tombstone_message_ids
                    else "complete and connected."
                )
            ),
            True, stream_id, source_id, manifest, stream_run, messages, True,
            "incomplete_or_truncated" if incomplete else
            "complete_with_tombstones" if manifest.tombstone_message_ids else
            "complete_connected", incomplete,
        )

    def saved(self) -> tuple[SavedMailingListWorkflow, ...]:
        result = []
        sources = {item.source_id: item for item in self.repository.sources()}
        for summary in self.stream_service.list_streams():
            revision = self.stream_service.detail(summary.stream_id)
            if (
                revision.draft.input_kind != "external"
                or revision.draft.schema_id != "mail.message"
            ):
                continue
            source = sources.get(revision.draft.input_ids[0])
            if source is None or source.provider != "lore-public-inbox":
                continue
            compatible_ids = {
                item["run_id"] for item in self._compatible_coverage_runs(revision.draft)
            }
            acquisition_runs = tuple(
                item for item in self.repository.acquisition_runs(source.source_id)
                if item["run_id"] in compatible_ids
            )
            latest = acquisition_runs[-1] if acquisition_runs else None
            acquisition_status = str(latest["lifecycle_status"]) if latest else None
            connectivity_status = str(latest["connectivity_state"]) if latest else None
            no_results = latest is not None and (
                int(latest["message_count"]) == 0
                and (
                    acquisition_status == "succeeded"
                    or latest["error_code"] == "no_seed_matches"
                )
            )
            test_evidence_status = (
                "failed" if acquisition_status == "succeeded"
                and summary.latest_run_status == "failed"
                else "complete_with_tombstones" if acquisition_status == "succeeded"
                and connectivity_status == "connected"
                and int(latest.get("tombstone_count", 0)) > 0
                else "complete_connected" if acquisition_status == "succeeded"
                and connectivity_status == "connected"
                and int(latest["message_count"]) > 0
                else "incomplete_or_truncated" if acquisition_status == "succeeded"
                and int(latest["message_count"]) > 0
                else "empty" if no_results
                else "partial" if acquisition_status == "partial"
                else "failed" if acquisition_status in {
                    "retryable_failure", "terminal_failure"
                } or acquisition_status == "succeeded"
                and summary.latest_run_status == "failed"
                else "untested"
            )
            result.append(SavedMailingListWorkflow(
                summary.stream_id, summary.name, summary.revision_id, summary.revision_number,
                source.source_id, source.display_name, source.archive_base_url,
                str(latest["run_id"]) if latest else None, acquisition_status,
                summary.latest_run_id, summary.latest_run_status, "ready",
                test_evidence_status, self._effective_last_fetch(revision.draft),
            ))
        return tuple(result)

    def effective_last_fetch(self, stream_id: str) -> str | None:
        return self._effective_last_fetch(self.stream_service.detail(stream_id).draft)

    def fetch_up_to_date(
        self, stream_id: str, *, cancelled: Callable[[], bool] | None = None
    ) -> FetchUpToDateResult:
        """Acquire deterministic overlapping bounded windows through today."""
        revision = self.stream_service.detail(stream_id)
        if revision.draft.input_kind != "external" or revision.draft.schema_id != "mail.message":
            raise MailingListError(
                "not_mailing_list_workflow", "selected stream is not a Lore mailing-list stream"
            )
        criteria = self._criteria(revision.draft)
        if criteria.date_from is None:
            raise MailingListError("invalid_date", "saved stream has no acquisition start date")
        effective = self._effective_last_fetch(revision.draft)
        start = (
            date.fromisoformat(effective) - timedelta(days=2)
            if effective else date.fromisoformat(criteria.date_from)
        )
        through = self.today()
        source_id = revision.draft.input_ids[0]
        source = self.repository.source(source_id)
        limits = AcquisitionLimits(
            revision.draft.bounds["seed_limit"],
            revision.draft.bounds["expanded_limit"] - revision.draft.bounds["seed_limit"],
            int(revision.draft.expansion.get("descendant_depth", 0)),
        )
        run_ids: list[str] = []
        completed = 0
        cursor = start
        status = "completed"
        message = "Acquisition coverage is up to date."
        while cursor <= through:
            if cancelled is not None and cancelled():
                raise MailingListError(
                    "acquisition_cancelled", "mailing-list catch-up was cancelled"
                )
            window_end = min(cursor + timedelta(days=31), through)
            window = replace(
                criteria, date_from=cursor.isoformat(), date_through=window_end.isoformat()
            )
            before = {item["run_id"] for item in self.repository.acquisition_runs(source_id)}
            service = MailingListAcquisitionService(
                self.repository, self.archive_factory(source)
            )
            offset = 0
            batch_id = hashlib.sha256(
                f"{revision.revision_id}:{cursor.isoformat()}:{window_end.isoformat()}".encode()
            ).hexdigest()[:32]
            while True:
                try:
                    manifest = service.acquire(
                        source_id, window, limits, cancelled=cancelled,
                        discovery_offset=offset, coverage_batch_id=batch_id,
                        prior_batches_complete=True,
                    )
                except MailingListError as error:
                    latest = self._new_acquisition(source_id, before)
                    if latest is not None and str(latest["run_id"]) not in run_ids:
                        run_ids.append(str(latest["run_id"]))
                    if error.code == "no_seed_matches" and offset == 0:
                        completed += 1
                        cursor = window_end + timedelta(days=1)
                        break
                    raise
                if cancelled is not None and cancelled():
                    raise MailingListError(
                        "acquisition_cancelled",
                        "mailing-list catch-up was cancelled after preserving completed evidence",
                    )
                run_ids.append(manifest.run_id)
                if (
                    manifest.run_status != AcquisitionRunStatus.SUCCEEDED
                    or manifest.state.value in {"incomplete", "quarantined"}
                    or not manifest.required_ancestry_complete
                    or not manifest.descendant_policy_complete
                    or manifest.unexpected_truncation
                ):
                    completed += 1
                    status = "completed_with_incomplete_evidence"
                    message = (
                        "Catch-up stopped at an incomplete relationship batch; retained "
                        "evidence remains inspectable and coverage was not advanced."
                    )
                    break
                if manifest.discovery_has_more:
                    offset += len(manifest.seed_ids)
                    continue
                completed += 1
                cursor = window_end + timedelta(days=1)
                break
            if status != "completed":
                break
        if status == "completed":
            try:
                self.stream_service.run(stream_id)
            except StreamError as error:
                raise MailingListError(
                    "stream_projection_failed",
                    "Acquisition coverage is current, but publishing the saved stream "
                    f"projection failed: {error}",
                    retryable=True,
                )
        return FetchUpToDateResult(
            stream_id, status, start.isoformat(), through.isoformat(), completed,
            tuple(run_ids), self._effective_last_fetch(revision.draft), message,
        )

    def result(self, run_id: str) -> dict[str, Any]:
        return {
            "run": self.query_service.acquisition_run(run_id),
            "messages": [
                asdict(item) for item in self.query_service.acquisition_messages(run_id)
            ],
        }

    def draft_for(self, stream_id: str) -> MailingListWorkflowDraft:
        revision = self.stream_service.detail(stream_id)
        if revision.draft.input_kind != "external" or revision.draft.schema_id != "mail.message":
            raise MailingListError(
                "not_mailing_list_workflow", "selected stream is not a Lore mailing-list stream"
            )
        source = self.repository.source(revision.draft.input_ids[0])
        criteria = self._criteria(revision.draft)
        return MailingListWorkflowDraft(
            source.archive_base_url, revision.draft.name, revision.draft.description,
            criteria.date_from or "", criteria.date_through or "",
            criteria.topic_terms, criteria.subject_terms, criteria.participant_terms,
            revision.draft.bounds["seed_limit"], revision.draft.bounds["expanded_limit"],
            int(revision.draft.expansion.get("descendant_depth", 0)),
        )

    def _compatible_coverage_runs(self, draft: StreamDraft) -> tuple[dict[str, Any], ...]:
        criteria = self._criteria(draft)
        expected = self._relevance_key(asdict(criteria))
        return tuple(
            item for item in self.repository.acquisition_coverage(draft.input_ids[0])
            if self._relevance_key(item.get("criteria", {})) == expected
        )

    def _effective_last_fetch(self, draft: StreamDraft) -> str | None:
        criteria = self._criteria(draft)
        if criteria.date_from is None:
            return None
        intervals = []
        for item in self._compatible_coverage_runs(draft):
            scope = item.get("criteria", {})
            try:
                start = date.fromisoformat(str(scope["date_from"]))
                through = date.fromisoformat(str(scope["date_through"]))
            except (KeyError, TypeError, ValueError):
                continue
            complete = (
                item["error_code"] == "no_seed_matches"
                or item["lifecycle_status"] == AcquisitionRunStatus.SUCCEEDED.value
                and item["connectivity_state"] == "connected"
                and not item["truncated"]
                and (
                    not item.get("pagination_managed")
                    or item.get("coverage_complete")
                )
            )
            if complete:
                intervals.append((start, through))
        anchor = date.fromisoformat(criteria.date_from)
        covered: date | None = None
        for start, through in sorted(intervals):
            if covered is None:
                if start <= anchor <= through:
                    covered = through
            elif start <= covered + timedelta(days=1):
                covered = max(covered, through)
        return covered.isoformat() if covered is not None else None

    @staticmethod
    def _relevance_key(value: dict[str, Any]) -> tuple[tuple[str, ...], ...]:
        return tuple(
            tuple(str(item) for item in value.get(field, ()) or ())
            for field in ("topic_terms", "subject_terms", "participant_terms", "message_ids")
        )

    def _draft(self, value: Any) -> MailingListWorkflowDraft:
        if isinstance(value, MailingListWorkflowDraft):
            draft = value
        elif isinstance(value, dict):
            allowed = {
                "archive_url", "stream_name", "description", "date_from", "date_through",
                "keywords", "subjects", "participants", "seed_limit", "total_limit",
                "descendant_depth",
            }
            unknown = sorted(set(value) - allowed)
            if unknown:
                raise MailingListError("unknown_field", f"Unknown workflow field: {unknown[0]}")
            try:
                draft = MailingListWorkflowDraft(
                    self._text(value, "archive_url"), self._text(value, "stream_name"),
                    str(value.get("description", "")).strip(), self._text(value, "date_from"),
                    self._text(value, "date_through"), self._terms(value, "keywords"),
                    self._terms(value, "subjects"), self._terms(value, "participants"),
                    self._integer(value, "seed_limit"), self._integer(value, "total_limit"),
                    self._integer(value, "descendant_depth"),
                )
            except (TypeError, ValueError) as error:
                raise MailingListError(
                    "invalid_workflow", "Workflow values have invalid types"
                ) from error
        else:
            raise MailingListError("invalid_workflow", "Mailing-list workflow must be an object")
        if len(draft.stream_name) > 120:
            raise MailingListError("invalid_stream_name", "Stream name must be 1-120 characters")
        try:
            date_from = date.fromisoformat(draft.date_from)
            date_through = date.fromisoformat(draft.date_through)
        except ValueError as error:
            raise MailingListError(
                "invalid_date", "Use valid ISO start and through dates"
            ) from error
        if date_from > date_through:
            raise MailingListError("invalid_date", "Starting date must not be after through date")
        if date_through - date_from > timedelta(days=31):
            raise MailingListError("invalid_date", "Initial Lore test window cannot exceed 31 days")
        if date_through > self.today():
            raise MailingListError("invalid_date", "Through date cannot be in the future")
        if not 1 <= draft.seed_limit <= 25:
            raise MailingListError("invalid_limit", "Initial direct-message limit must be 1-25")
        if not draft.seed_limit + 1 <= draft.total_limit <= 100:
            raise MailingListError(
                "invalid_limit",
                "Total message limit must exceed direct messages and be at most 100",
            )
        if not 0 <= draft.descendant_depth <= 10:
            raise MailingListError("invalid_limit", "Discussion depth must be 0-10")
        for terms in (draft.keywords, draft.subjects, draft.participants):
            if len(terms) > 10 or any(len(item) > 100 for item in terms):
                raise MailingListError(
                    "invalid_selection", "Each relevance control accepts up to 10 short values"
                )
        return draft

    def _source(self, archive: LoreCatalogEntry) -> MailingListSource:
        for source in self.repository.sources():
            if source.list_id == archive.archive_id:
                try:
                    _, normalized_existing = normalize_lore_archive(
                        source.archive_base_url
                    )
                except MailingListError:
                    normalized_existing = None
                if normalized_existing != archive.canonical_url:
                    raise MailingListError(
                        "source_conflict",
                        f"Governed source {source.source_id} stores "
                        f"{source.archive_base_url}; requested {archive.canonical_url}. "
                        "The stored governed source must be corrected through a reviewed "
                        "source-governance migration.",
                    )
                return replace(source, archive_base_url=archive.canonical_url)
        occupied = {item.source_id for item in self.repository.sources()}
        base = f"{archive.archive_id}-lore"
        source_id = self._collision_safe(base, archive.canonical_url, occupied)
        return MailingListSource(
            source_id, archive.archive_id, archive.display_name, archive.canonical_url,
            transport=LoreTransportPolicy(),
        )

    def _stream_id(
        self, draft: MailingListWorkflowDraft, source_id: str, selection: dict[str, Any]
    ) -> str:
        base = re.sub(r"[^a-z0-9._-]+", "-", draft.stream_name.casefold()).strip("-._")
        if not base or not base[0].isalpha():
            base = f"mail-{base}".strip("-")
        base = base[:80]
        if not _REPOSITORY_ID.fullmatch(base):
            raise MailingListError(
                "invalid_stream_name", "Stream name cannot form a stable identity"
            )
        existing = {item.stream_id: item for item in self.stream_service.list_streams()}
        if base in existing:
            current = self.stream_service.detail(base).draft
            intended = StreamDraft(
                base, draft.stream_name, draft.description, True, "external", (source_id,),
                "mail.message", selection,
                {"strategy": "connected_discussion", "ancestor_closure": True,
                 "descendant_depth": draft.descendant_depth},
                {"seed_limit": draft.seed_limit, "expanded_limit": draft.total_limit},
            )
            if normalize_draft(current) == normalize_draft(intended):
                return base
        return self._collision_safe(base, f"{source_id}:{draft.stream_name}", set(existing))

    @staticmethod
    def _collision_safe(base: str, key: str, occupied: set[str]) -> str:
        if base not in occupied:
            return base
        digest = hashlib.sha256(key.encode()).hexdigest()
        for length in (8, 12, 16, 24, 32):
            candidate = f"{base[:90 - length]}-{digest[:length]}"
            if candidate not in occupied:
                return candidate
        raise MailingListError("identity_collision", "Could not generate a collision-safe identity")

    @staticmethod
    def _selection(draft: MailingListWorkflowDraft) -> dict[str, Any]:
        groups: list[dict[str, Any]] = [
            {"op": "predicate", "field": "effective_at", "operator": "after_or_on",
             "value": draft.date_from},
            {"op": "predicate", "field": "effective_at", "operator": "before_or_on",
             "value": draft.date_through},
        ]
        for values, field in (
            (draft.keywords, "text"), (draft.subjects, "title"),
            (draft.participants, "authors"),
        ):
            if values:
                groups.append({
                    "op": "any",
                    "items": tuple(
                        {"op": "predicate", "field": field, "operator": "contains", "value": item}
                        for item in values
                    ),
                })
        return {"op": "all", "items": tuple(groups)}

    @staticmethod
    def _criteria(draft: StreamDraft) -> SelectionCriteria:
        values: dict[str, list[str]] = {"text": [], "title": [], "authors": []}
        date_from = None
        date_through = None

        def visit(node: dict[str, Any]) -> None:
            nonlocal date_from, date_through
            if node.get("op") in {"all", "any"}:
                for item in node.get("items", ()):
                    visit(item)
                return
            field = node.get("field")
            value = node.get("value")
            if field in values and isinstance(value, str):
                values[field].append(value)
            elif field == "effective_at" and node.get("operator") == "after_or_on":
                date_from = str(value)
            elif field == "effective_at" and node.get("operator") == "before_or_on":
                date_through = str(value)

        visit(draft.selection)
        return SelectionCriteria(
            date_from=date_from, date_through=date_through,
            topic_terms=tuple(values["text"]), subject_terms=tuple(values["title"]),
            participant_terms=tuple(values["authors"]),
        )

    def _new_acquisition(
        self, source_id: str, before: set[str]
    ) -> dict[str, Any] | None:
        created = [
            item for item in self.repository.acquisition_runs(source_id)
            if item["run_id"] not in before
        ]
        return created[-1] if created else None

    @staticmethod
    def _text(value: dict[str, Any], field: str) -> str:
        item = value.get(field)
        if not isinstance(item, str) or not item.strip():
            raise MailingListError("invalid_workflow", f"{field} is required")
        return item.strip()

    @staticmethod
    def _terms(value: dict[str, Any], field: str) -> tuple[str, ...]:
        item = value.get(field, ())
        if not isinstance(item, (list, tuple)) or any(not isinstance(term, str) for term in item):
            raise MailingListError("invalid_workflow", f"{field} must be a list of text values")
        return tuple(dict.fromkeys(term.strip() for term in item if term.strip()))

    @staticmethod
    def _integer(value: dict[str, Any], field: str) -> int:
        item = value.get(field)
        if isinstance(item, bool) or not isinstance(item, int):
            raise MailingListError("invalid_workflow", f"{field} must be an integer")
        return item
