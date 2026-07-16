"""Append-only workspace persistence, projections, comparison, export, and recovery."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import tempfile
import uuid
import zipfile
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, TextIO

from rfi.intelligence import ExecutionRecord

from rfi.workspace.contracts import (
    AnnotationKind,
    ExecutionComparison,
    ExecutionOutcome,
    IntegrityReport,
    InvestigationStatus,
    InvestigationSummary,
    JournalEvent,
    OperationalMetrics,
    WorkspaceError,
)


def _canonical(value: Any) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":"), default=str) + "\n").encode()


def _digest(value: Any) -> str:
    return hashlib.sha256(_canonical(value)).hexdigest()


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _identifier(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex}"


def _redact(value: Any) -> Any:
    """Remove likely credential values from transient diagnostic structures."""
    if isinstance(value, dict):
        return {
            str(key): "[REDACTED]" if any(
                term in str(key).lower() for term in ("secret", "token", "password", "api_key")
            ) else _redact(item)
            for key, item in value.items()
        }
    if isinstance(value, (list, tuple)):
        return [_redact(item) for item in value]
    return value


class WorkspaceRepository:
    """Filesystem-native durable workspace with no upstream storage knowledge."""

    SCHEMA_VERSION = 1

    def __init__(self, root: Path) -> None:
        self.root = root
        self.metadata_path = root / "workspace.json"
        self.journal_root = root / "journal"
        self.exports_root = root / "exports"

    @classmethod
    def create(cls, root: Path, title: str = "RFI consulting workspace") -> WorkspaceRepository:
        """Create a new independently backupable workspace."""
        if root.exists() and any(root.iterdir()):
            raise WorkspaceError("workspace destination is not empty")
        root.mkdir(parents=True, exist_ok=True)
        repository = cls(root)
        repository.journal_root.mkdir()
        repository.exports_root.mkdir()
        metadata = {
            "schema_version": cls.SCHEMA_VERSION,
            "workspace_id": _identifier("workspace"),
            "title": title.strip() or "RFI consulting workspace",
            "created_at": _now(),
            "journal_retention": "indefinite-reference-snapshots",
            "diagnostic_retention": "transient-only",
        }
        repository._atomic_json(repository.metadata_path, metadata)
        return repository

    @classmethod
    def open(cls, root: Path) -> WorkspaceRepository:
        """Open only verified workspace state."""
        repository = cls(root)
        report = repository.verify()
        if not report.valid:
            raise WorkspaceError("workspace integrity failure: " + "; ".join(report.failures))
        return repository

    def _atomic_json(self, path: Path, value: Any) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
        temporary = Path(temporary_name)
        try:
            with os.fdopen(descriptor, "wb") as handle:
                handle.write(_canonical(value))
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, path)
        finally:
            temporary.unlink(missing_ok=True)

    def _raw_events(self) -> list[dict[str, Any]]:
        paths = sorted(self.journal_root.glob("[0-9]*.json")) if self.journal_root.exists() else []
        events: list[dict[str, Any]] = []
        for path in paths:
            try:
                events.append(json.loads(path.read_text(encoding="utf-8")))
            except (OSError, json.JSONDecodeError) as error:
                raise WorkspaceError(f"unreadable journal event {path.name}: {error}") from error
        return events

    def events(self, investigation_id: str | None = None) -> tuple[JournalEvent, ...]:
        """Return immutable events after verifying the complete chain."""
        report = self.verify()
        if not report.valid:
            raise WorkspaceError("journal integrity failure: " + "; ".join(report.failures))
        items = (JournalEvent(**item) for item in self._raw_events())
        return tuple(
            item for item in items
            if investigation_id is None or item.investigation_id == investigation_id
        )

    def _append(
        self,
        event_type: str,
        investigation_id: str | None,
        payload: dict[str, Any],
        simulate_partial: bool = False,
    ) -> JournalEvent:
        report = self.verify()
        if not report.valid:
            raise WorkspaceError("refusing append to corrupt journal")
        previous = self._raw_events()
        sequence = len(previous) + 1
        material = {
            "sequence": sequence,
            "event_id": _identifier("event"),
            "timestamp": _now(),
            "event_type": event_type,
            "investigation_id": investigation_id,
            "payload": payload,
            "previous_hash": previous[-1]["event_hash"] if previous else None,
        }
        value = {**material, "event_hash": _digest(material)}
        target = self.journal_root / f"{sequence:020d}.json"
        partial = self.journal_root / f".{sequence:020d}.{uuid.uuid4().hex}.partial"
        partial.write_bytes(_canonical(value))
        if simulate_partial:
            raise WorkspaceError(f"simulated partial journal write: {partial.name}")
        os.replace(partial, target)
        return JournalEvent(**value)

    def create_investigation(
        self,
        title: str,
        purpose: str,
        customer: str | None = None,
        engagement: str | None = None,
    ) -> InvestigationSummary:
        """Create one consulting problem as an append-only event."""
        if not title.strip() or not purpose.strip():
            raise WorkspaceError("investigation title and purpose are required")
        investigation_id = _identifier("investigation")
        self._append(
            "investigation-created",
            investigation_id,
            {
                "title": title.strip(),
                "purpose": purpose.strip(),
                "customer": customer.strip() if customer else None,
                "engagement": engagement.strip() if engagement else None,
                "status": InvestigationStatus.OPEN,
            },
        )
        return self.investigation(investigation_id)

    def set_status(
        self, investigation_id: str, status: InvestigationStatus
    ) -> InvestigationSummary:
        """Append an operator-visible investigation status transition."""
        self.investigation(investigation_id)
        self._append("investigation-status", investigation_id, {"status": status})
        return self.investigation(investigation_id)

    def add_annotation(
        self,
        investigation_id: str,
        kind: AnnotationKind,
        text: str,
        execution_id: str | None = None,
    ) -> str:
        """Append a distinct operator-authored annotation."""
        self.investigation(investigation_id)
        if not text.strip() or len(text) > 20_000:
            raise WorkspaceError("annotation must contain 1 to 20,000 characters")
        if execution_id and execution_id not in self._execution_ids(investigation_id):
            raise WorkspaceError("annotation references an unknown execution")
        annotation_id = _identifier("annotation")
        self._append(
            "operator-annotation",
            investigation_id,
            {
                "annotation_id": annotation_id,
                "kind": kind,
                "text": text.strip(),
                "execution_id": execution_id,
                "authority": "operator-annotation",
            },
        )
        return annotation_id

    def begin_execution(
        self,
        investigation_id: str,
        question: str,
        configuration: dict[str, Any] | None = None,
    ) -> str:
        """Durably record intent before invoking any downstream subsystem."""
        investigation = self.investigation(investigation_id)
        if investigation.status == InvestigationStatus.CLOSED:
            raise WorkspaceError("cannot execute a closed investigation")
        if not question.strip():
            raise WorkspaceError("execution question is required")
        execution_id = _identifier("execution")
        self._append(
            "execution-started",
            investigation_id,
            {
                "execution_id": execution_id,
                "question": question.strip(),
                "configuration": _redact(configuration or {}),
                "outcome": ExecutionOutcome.STARTED,
            },
        )
        return execution_id

    def complete_execution(
        self,
        investigation_id: str,
        execution_id: str,
        record: ExecutionRecord,
        metrics: OperationalMetrics,
    ) -> JournalEvent:
        """Append a frozen reference projection of public TASK-007 contracts."""
        started = self._started_execution(investigation_id, execution_id)
        if self._terminal_execution(execution_id) is not None:
            raise WorkspaceError("execution already has a terminal journal event")
        if record.trace.need.text != started["question"]:
            raise WorkspaceError("execution result question differs from durable start record")
        projection = self._execution_projection(record)
        return self._append(
            "execution-completed",
            investigation_id,
            {
                "execution_id": execution_id,
                "outcome": ExecutionOutcome.COMPLETED,
                "intelligence_execution_id": record.result.execution_id,
                "record": projection,
                "metrics": asdict(metrics),
                "retention": "reference-snapshot-no-source-context",
            },
        )

    def fail_execution(
        self,
        investigation_id: str,
        execution_id: str,
        reason: str,
        interrupted: bool = False,
        metrics: OperationalMetrics | None = None,
    ) -> JournalEvent:
        """Append visible terminal failure without rewriting the start event."""
        self._started_execution(investigation_id, execution_id)
        if self._terminal_execution(execution_id) is not None:
            raise WorkspaceError("execution already has a terminal journal event")
        if not reason.strip():
            raise WorkspaceError("failure reason is required")
        return self._append(
            "execution-interrupted" if interrupted else "execution-failed",
            investigation_id,
            {
                "execution_id": execution_id,
                "outcome": (
                    ExecutionOutcome.INTERRUPTED if interrupted else ExecutionOutcome.FAILED
                ),
                "reason": reason.strip(),
                "metrics": asdict(metrics) if metrics else None,
            },
        )

    def _execution_projection(self, record: ExecutionRecord) -> dict[str, Any]:
        """Retain public identities and conclusions while omitting source/model content."""
        plan = asdict(record.trace.plan) if record.trace.plan else None
        packages = []
        for package in record.trace.evidence_packages:
            packages.append(
                {
                    "package_id": package.package_id,
                    "retrieval_trace_id": package.trace.trace_id,
                    "index_generation_id": package.trace.index_generation_id,
                    "authority_fingerprint": package.trace.authority_fingerprint,
                    "query": asdict(package.query),
                    "source_object_ids": [
                        item.source_object.source_object_id for item in package.source_evidence
                    ],
                    "derived_object_ids": [
                        item.derived_object.object_id for item in package.derived_knowledge
                    ],
                    "context_references": [
                        {
                            "source_object_id": item.provenance.source_object_id,
                            "document_id": item.provenance.document_id,
                            "artifact_id": item.provenance.artifact_id,
                            "byte_start": item.provenance.byte_start,
                            "byte_end": item.provenance.byte_end,
                            "content_sha256": item.provenance.content_sha256,
                        }
                        for item in package.contexts
                    ],
                    "complete": package.complete,
                    "omissions": package.omissions,
                    "coverage_gaps": package.coverage_gaps,
                    "contradictions": package.contradictions,
                    "bytes_used": package.bytes_used,
                }
            )
        result = asdict(record.result)
        trace = {
            "events": [asdict(item) for item in record.trace.events],
            "iterations": record.trace.iterations,
            "stop_reason": record.trace.stop_reason,
            "failures": record.trace.failures,
        }
        return {"plan": plan, "packages": packages, "result": result, "trace": trace}

    def _started_execution(self, investigation_id: str, execution_id: str) -> dict[str, Any]:
        for event in self.events(investigation_id):
            if (
                event.event_type == "execution-started"
                and event.payload.get("execution_id") == execution_id
            ):
                return event.payload
        raise WorkspaceError("unknown execution")

    def _terminal_execution(self, execution_id: str) -> JournalEvent | None:
        terminal = {"execution-completed", "execution-failed", "execution-interrupted"}
        return next(
            (
                event for event in self.events()
                if event.event_type in terminal
                and event.payload.get("execution_id") == execution_id
            ),
            None,
        )

    def _execution_ids(self, investigation_id: str) -> tuple[str, ...]:
        return tuple(
            event.payload["execution_id"]
            for event in self.events(investigation_id)
            if event.event_type == "execution-started"
        )

    def investigations(self) -> tuple[InvestigationSummary, ...]:
        """List current investigation projections."""
        identifiers = [
            event.investigation_id for event in self.events()
            if event.event_type == "investigation-created"
            and event.investigation_id is not None
        ]
        return tuple(self.investigation(item) for item in identifiers)

    def investigation(self, investigation_id: str) -> InvestigationSummary:
        """Rebuild one current projection without mutable investigation records."""
        relevant = self.events(investigation_id)
        created = next(
            (event for event in relevant if event.event_type == "investigation-created"), None
        )
        if created is None:
            raise WorkspaceError("unknown investigation")
        status = InvestigationStatus(created.payload["status"])
        for event in relevant:
            if event.event_type == "investigation-status":
                status = InvestigationStatus(event.payload["status"])
        return InvestigationSummary(
            investigation_id,
            created.payload["title"],
            created.payload["purpose"],
            created.payload.get("customer"),
            created.payload.get("engagement"),
            status,
            created.timestamp,
            relevant[-1].timestamp,
            self._execution_ids(investigation_id),
            tuple(
                event.payload["annotation_id"]
                for event in relevant if event.event_type == "operator-annotation"
            ),
            tuple(
                event.payload["export_id"]
                for event in relevant if event.event_type == "investigation-exported"
            ),
        )

    def execution(self, execution_id: str) -> dict[str, Any]:
        """Return start and terminal journal views for inspection."""
        start = next(
            (
                event for event in self.events()
                if event.event_type == "execution-started"
                and event.payload.get("execution_id") == execution_id
            ),
            None,
        )
        if start is None:
            raise WorkspaceError("unknown execution")
        terminal = self._terminal_execution(execution_id)
        return {
            "start": asdict(start),
            "terminal": asdict(terminal) if terminal else None,
        }

    def compare(self, first_execution_id: str, second_execution_id: str) -> ExecutionComparison:
        """Compare stable semantics rather than implementation-specific prose alone."""
        first = self.execution(first_execution_id)
        second = self.execution(second_execution_id)
        if first["terminal"] is None or second["terminal"] is None:
            raise WorkspaceError("both executions must have terminal events")
        first_payload = first["terminal"]["payload"]
        second_payload = second["terminal"]["payload"]
        first_record = first_payload.get("record", {})
        second_record = second_payload.get("record", {})

        def field(record: dict[str, Any], path: tuple[str, ...]) -> Any:
            value: Any = record
            for key in path:
                value = value.get(key) if isinstance(value, dict) else None
            return value

        dimensions = {
            "question_changed": first["start"]["payload"]["question"]
            != second["start"]["payload"]["question"],
            "configuration_changed": first["start"]["payload"]["configuration"]
            != second["start"]["payload"]["configuration"],
            "plan_changed": first_record.get("plan") != second_record.get("plan"),
            "retrieval_changed": [
                (item.get("retrieval_trace_id"), item.get("query"))
                for item in first_record.get("packages", [])
            ] != [
                (item.get("retrieval_trace_id"), item.get("query"))
                for item in second_record.get("packages", [])
            ],
            "evidence_changed": [
                (item.get("source_object_ids"), item.get("derived_object_ids"))
                for item in first_record.get("packages", [])
            ] != [
                (item.get("source_object_ids"), item.get("derived_object_ids"))
                for item in second_record.get("packages", [])
            ],
            "reasoning_changed": field(first_record, ("result", "claims"))
            != field(second_record, ("result", "claims")),
            "conclusions_changed": field(first_record, ("result", "response"))
            != field(second_record, ("result", "response")),
            "status_changed": (
                first_payload.get("outcome"), field(first_record, ("result", "status"))
            ) != (
                second_payload.get("outcome"), field(second_record, ("result", "status"))
            ),
        }
        first_metrics = first_payload.get("metrics") or {}
        second_metrics = second_payload.get("metrics") or {}
        deltas = {
            key: (
                second_metrics.get(key) - first_metrics.get(key)
                if isinstance(first_metrics.get(key), (int, float))
                and isinstance(second_metrics.get(key), (int, float))
                else None
            )
            for key in sorted(set(first_metrics) | set(second_metrics))
        }
        return ExecutionComparison(
            first_execution_id,
            second_execution_id,
            not any(dimensions.values()),
            **dimensions,
            metric_deltas=deltas,
            details={
                "first_package_ids": field(first_record, ("result", "evidence_package_ids")),
                "second_package_ids": field(second_record, ("result", "evidence_package_ids")),
                "first_stopping_reason": field(first_record, ("result", "stopping_reason")),
                "second_stopping_reason": field(second_record, ("result", "stopping_reason")),
            },
        )

    def metrics(self, investigation_id: str | None = None) -> dict[str, Any]:
        """Aggregate only recorded telemetry; unavailable values remain unavailable."""
        events = self.events(investigation_id)
        values = [
            event.payload["metrics"] for event in events
            if event.event_type == "execution-completed" and event.payload.get("metrics")
        ]
        return {
            "executions": len(values),
            "total_execution_ms": sum(item["execution_ms"] for item in values),
            "total_evidence_bytes": sum(item["evidence_bytes"] for item in values),
            "total_retrievals": sum(item["retrieval_count"] for item in values),
            "total_iterations": sum(item["iteration_count"] for item in values),
            "input_tokens": sum(
                item["input_tokens"] for item in values if item.get("input_tokens") is not None
            ) or None,
            "output_tokens": sum(
                item["output_tokens"] for item in values if item.get("output_tokens") is not None
            ) or None,
            "estimated_cost": sum(
                item["estimated_cost"] for item in values
                if item.get("estimated_cost") is not None
            ) or None,
        }

    def export(self, investigation_id: str) -> Path:
        """Create a bounded Markdown consulting artifact with a JSON evidence appendix."""
        investigation = self.investigation(investigation_id)
        export_id = _identifier("export")
        path = self.exports_root / f"{export_id}.md"
        annotations = [
            event.payload for event in self.events(investigation_id)
            if event.event_type == "operator-annotation"
        ]
        executions = [
            self.execution(item) for item in investigation.execution_ids
            if self._terminal_execution(item) is not None
        ]
        lines = [
            f"# {investigation.title}",
            "",
            investigation.purpose,
            "",
            f"Status: {investigation.status.value}",
            "",
            "## Execution conclusions and uncertainty",
            "",
        ]
        for execution in executions:
            start = execution["start"]["payload"]
            terminal = execution["terminal"]["payload"]
            record = terminal.get("record", {})
            result = record.get("result", {})
            lines.extend(
                [
                    f"### {start['question']}",
                    "",
                    result.get("response", terminal.get("reason", "No result.")),
                    "",
                    "Uncertainty: " + "; ".join(result.get("uncertainties", ())),
                    "",
                    "Evidence gaps: " + "; ".join(result.get("evidence_gaps", ())),
                    "",
                    "Evidence package references: "
                    + ", ".join(result.get("evidence_package_ids", ())),
                    "",
                ]
            )
        lines.extend(["## Operator annotations", ""])
        for annotation in annotations:
            lines.append(f"- [{annotation['kind']}] {annotation['text']}")
        appendix = {
            "investigation_id": investigation_id,
            "execution_references": [
                {
                    "execution_id": item["start"]["payload"]["execution_id"],
                    "record": item["terminal"]["payload"].get("record"),
                }
                for item in executions
            ],
            "operator_annotations": annotations,
        }
        lines.extend(
            [
                "",
                "## Provenance and claim-mapping appendix",
                "",
                "```json",
                json.dumps(appendix, indent=2, sort_keys=True, default=str),
                "```",
                "",
            ]
        )
        self._atomic_text(path, "\n".join(lines))
        file_hash = hashlib.sha256(path.read_bytes()).hexdigest()
        self._append(
            "investigation-exported",
            investigation_id,
            {
                "export_id": export_id,
                "relative_path": path.relative_to(self.root).as_posix(),
                "sha256": file_hash,
                "format": "markdown-with-json-appendix",
            },
        )
        return path

    def _atomic_text(self, path: Path, content: str) -> None:
        descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
        temporary = Path(temporary_name)
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
                handle.write(content)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, path)
        finally:
            temporary.unlink(missing_ok=True)

    def backup(self, destination: Path) -> Path:
        """Create a self-verifying ZIP snapshot without modifying workspace history."""
        report = self.verify()
        if not report.valid:
            raise WorkspaceError("refusing backup of corrupt workspace")
        if destination.resolve().is_relative_to(self.root.resolve()):
            raise WorkspaceError("backup destination must be outside workspace")
        destination.parent.mkdir(parents=True, exist_ok=True)
        temporary = destination.with_name(f".{destination.name}.{uuid.uuid4().hex}.partial")
        files = sorted(path for path in self.root.rglob("*") if path.is_file())
        manifest = {
            "schema_version": self.SCHEMA_VERSION,
            "created_at": _now(),
            "workspace_id": json.loads(self.metadata_path.read_text())["workspace_id"],
            "files": [
                {
                    "path": path.relative_to(self.root).as_posix(),
                    "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                    "size": path.stat().st_size,
                }
                for path in files
            ],
        }
        try:
            with zipfile.ZipFile(temporary, "w", zipfile.ZIP_DEFLATED) as archive:
                for path in files:
                    archive.write(path, path.relative_to(self.root).as_posix())
                archive.writestr("BACKUP-MANIFEST.json", _canonical(manifest))
            self.verify_backup(temporary)
            os.replace(temporary, destination)
        except (OSError, zipfile.BadZipFile, WorkspaceError) as error:
            temporary.unlink(missing_ok=True)
            raise WorkspaceError(f"backup failed: {error}") from error
        return destination

    @classmethod
    def verify_backup(cls, path: Path) -> IntegrityReport:
        """Verify archive structure, inventory, size, and SHA-256 digests."""
        failures: list[str] = []
        checked = 0
        try:
            with zipfile.ZipFile(path) as archive:
                manifest = json.loads(archive.read("BACKUP-MANIFEST.json"))
                expected = {item["path"]: item for item in manifest["files"]}
                observed = set(archive.namelist()) - {"BACKUP-MANIFEST.json"}
                if observed != set(expected):
                    failures.append("backup inventory differs from manifest")
                for name, item in expected.items():
                    content = archive.read(name)
                    checked += 1
                    if len(content) != item["size"]:
                        failures.append(f"backup size mismatch: {name}")
                    if hashlib.sha256(content).hexdigest() != item["sha256"]:
                        failures.append(f"backup digest mismatch: {name}")
        except (OSError, KeyError, json.JSONDecodeError, zipfile.BadZipFile) as error:
            failures.append(f"invalid backup: {error}")
        return IntegrityReport(not failures, 0, checked, (), tuple(failures))

    @classmethod
    def restore(cls, backup: Path, destination: Path) -> WorkspaceRepository:
        """Restore through a verified staging directory and atomic publication."""
        report = cls.verify_backup(backup)
        if not report.valid:
            raise WorkspaceError("restore rejected invalid backup: " + "; ".join(report.failures))
        if destination.exists():
            raise WorkspaceError("restore destination already exists")
        destination.parent.mkdir(parents=True, exist_ok=True)
        staging = destination.with_name(f".{destination.name}.{uuid.uuid4().hex}.restore")
        try:
            staging.mkdir()
            with zipfile.ZipFile(backup) as archive:
                for name in archive.namelist():
                    if name == "BACKUP-MANIFEST.json":
                        continue
                    target = staging / name
                    if not target.resolve().is_relative_to(staging.resolve()):
                        raise WorkspaceError("backup contains unsafe path")
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_bytes(archive.read(name))
            repository = cls(staging)
            restored = repository.verify()
            if not restored.valid:
                raise WorkspaceError("restored workspace failed integrity verification")
            os.replace(staging, destination)
        except (OSError, zipfile.BadZipFile, WorkspaceError) as error:
            shutil.rmtree(staging, ignore_errors=True)
            raise WorkspaceError(f"restore failed: {error}") from error
        return cls.open(destination)

    def verify(self) -> IntegrityReport:
        """Verify metadata, event sequence/hash chain, exports, and incomplete writes."""
        failures: list[str] = []
        files_checked = 0
        if not self.metadata_path.is_file():
            failures.append("workspace metadata missing")
        else:
            try:
                metadata = json.loads(self.metadata_path.read_text(encoding="utf-8"))
                files_checked += 1
                if metadata.get("schema_version") != self.SCHEMA_VERSION:
                    failures.append("unsupported workspace schema")
                if not metadata.get("workspace_id"):
                    failures.append("workspace identity missing")
            except (OSError, json.JSONDecodeError):
                failures.append("workspace metadata corrupt")
        partials = list(self.journal_root.glob("*.partial"))
        if partials:
            failures.append(f"partial journal writes present: {len(partials)}")
        previous: str | None = None
        raw: list[dict[str, Any]] = []
        try:
            raw = self._raw_events()
        except WorkspaceError as error:
            failures.append(str(error))
        for expected, event in enumerate(raw, start=1):
            files_checked += 1
            material = {key: value for key, value in event.items() if key != "event_hash"}
            if event.get("sequence") != expected:
                failures.append(f"journal sequence mismatch at {expected}")
            if event.get("previous_hash") != previous:
                failures.append(f"journal chain mismatch at {expected}")
            if event.get("event_hash") != _digest(material):
                failures.append(f"journal digest mismatch at {expected}")
            previous = event.get("event_hash")
        for event in raw:
            if event.get("event_type") == "investigation-exported":
                payload = event.get("payload", {})
                path = self.root / payload.get("relative_path", "")
                if not path.is_file():
                    failures.append("export referenced by journal is missing")
                else:
                    files_checked += 1
                    if hashlib.sha256(path.read_bytes()).hexdigest() != payload.get("sha256"):
                        failures.append("export digest mismatch")
        started = {
            event["payload"]["execution_id"] for event in raw
            if event.get("event_type") == "execution-started"
        }
        terminal = {
            event["payload"]["execution_id"] for event in raw
            if event.get("event_type") in {
                "execution-completed", "execution-failed", "execution-interrupted"
            }
        }
        return IntegrityReport(
            not failures,
            len(raw),
            files_checked,
            tuple(sorted(started - terminal)),
            tuple(failures),
        )

    def recover_partial_writes(self) -> tuple[str, ...]:
        """Quarantine uncommitted partial files; committed history is never changed."""
        quarantine = self.root / "quarantine"
        recovered: list[str] = []
        for path in sorted(self.journal_root.glob("*.partial")):
            quarantine.mkdir(exist_ok=True)
            target = quarantine / path.name
            os.replace(path, target)
            recovered.append(target.relative_to(self.root).as_posix())
        return tuple(recovered)

    @staticmethod
    def diagnostic(stream: TextIO, category: str, detail: dict[str, Any]) -> None:
        """Emit redacted transient JSON diagnostics; never write them to workspace state."""
        stream.write(
            json.dumps(
                {"timestamp": _now(), "category": category, "detail": _redact(detail)},
                sort_keys=True,
            ) + "\n"
        )
