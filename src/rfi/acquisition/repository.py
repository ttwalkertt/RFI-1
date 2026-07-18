"""Repository-owned acquisition lifecycle, replay, and inspection behavior."""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import Any

from rfi.acquisition.contracts import (
    AcquisitionReceipt,
    CandidateDocument,
    Checkpoint,
    ConflictError,
    ContractError,
    FailurePoint,
    IntegrityError,
    PartialFailure,
    ReplayResult,
    RetrievalOutcome,
    RetrievalResult,
    SourceProfile,
    require_identifier,
    validate_json,
)
from rfi.acquisition.persistence import (
    RepositoryLayout,
    atomic_replace,
    canonical_json,
    create_immutable,
    load_json,
    sha256_bytes,
)

_SCHEMA = 1


class AcquisitionRepository:
    """Single-owner POC repository for durable acquisition state."""

    def __init__(self, root: Path) -> None:
        self._layout = RepositoryLayout(root)
        self._layout.initialize()

    @property
    def root(self) -> Path:
        """Return the repository-state boundary, not its private object layout."""
        return self._layout.root

    def register_source(self, profile: SourceProfile) -> bool:
        """Register one immutable governed profile; exact repetition is idempotent."""
        record = {"schema_version": _SCHEMA, "record_type": "source", **profile.to_dict()}
        return create_immutable(
            self._layout.sources / f"{profile.source_id}.json", canonical_json(record)
        )

    def sources(self) -> list[dict[str, Any]]:
        """Return governed source records in deterministic order."""
        return [load_json(path) for path in sorted(self._layout.sources.glob("*.json"))]

    def source(self, source_id: str) -> dict[str, Any]:
        """Return a governed source or reject an unknown identity."""
        require_identifier(source_id, "source_id")
        path = self._layout.sources / f"{source_id}.json"
        if not path.is_file():
            raise ContractError(f"unknown governed source: {source_id}")
        return load_json(path)

    def record_success(
        self,
        attempt_id: str,
        candidate: CandidateDocument,
        result: RetrievalResult,
        checkpoint: Checkpoint | None = None,
        fail_at: FailurePoint | None = None,
    ) -> AcquisitionReceipt:
        """Persist evidence, history, derived access, and then source progress."""
        require_identifier(attempt_id, "attempt_id")
        source = self.source(candidate.source_id)
        if not source["enabled"]:
            raise ContractError(f"source is disabled: {candidate.source_id}")
        if checkpoint is not None:
            self._validate_checkpoint(candidate.source_id, checkpoint)
        artifact_id = f"artifact-{sha256_bytes(result.content)}"
        artifact_created = not (
            self._layout.artifacts / f"{artifact_id}.metadata.json"
        ).exists()
        metadata = {
            "schema_version": _SCHEMA,
            "record_type": "artifact",
            "artifact_id": artifact_id,
            "sha256": sha256_bytes(result.content),
            "size": len(result.content),
            "media_type": result.media_type.lower(),
        }
        attempt = {
            "schema_version": _SCHEMA,
            "record_type": "retrieval_attempt",
            "attempt_id": attempt_id,
            "source_id": candidate.source_id,
            "candidate_id": candidate.candidate_id,
            "document_id": candidate.document_id,
            "outcome": RetrievalOutcome.SUCCESS.value,
            "occurred_at": result.retrieved_at,
            "mechanism": result.mechanism,
            "artifact_id": artifact_id,
            "candidate": candidate.to_dict(),
            "retrieval_provider_identifiers": result.provider_identifiers,
            "diagnostics": result.diagnostics,
            "checkpoint_requested": checkpoint.to_dict() if checkpoint else None,
        }
        self._assert_record_compatible(f"attempt-{attempt_id}", attempt)
        if fail_at == FailurePoint.BEFORE_ARTIFACT:
            self._fail(fail_at)

        self._store_artifact(artifact_id, result.content, metadata)
        if fail_at == FailurePoint.AFTER_ARTIFACT:
            self._fail(fail_at)

        created = self._append_record(f"attempt-{attempt_id}", attempt)
        if fail_at == FailurePoint.BEFORE_INDEX:
            self._fail(fail_at)

        self._write_derived_index(self._derive_index(self.history()))
        if fail_at == FailurePoint.BEFORE_CHECKPOINT:
            self._fail(fail_at)

        if checkpoint is not None:
            self._advance_checkpoint(candidate.source_id, attempt_id, checkpoint)
        return AcquisitionReceipt(
            attempt_id=attempt_id,
            artifact_id=artifact_id,
            document_id=candidate.document_id,
            checkpoint=checkpoint,
            idempotent=not created,
            artifact_created=artifact_created,
        )

    def record_outcome(
        self,
        attempt_id: str,
        candidate: CandidateDocument,
        outcome: RetrievalOutcome,
        occurred_at: str,
        mechanism: str,
        diagnostics: dict[str, Any],
    ) -> bool:
        """Append a failed, skipped, or duplicate attempt without advancing progress."""
        require_identifier(attempt_id, "attempt_id")
        if outcome == RetrievalOutcome.SUCCESS:
            raise ContractError("successful outcomes require exact artifact bytes")
        self.source(candidate.source_id)
        require_identifier(mechanism, "mechanism")
        if not occurred_at:
            raise ContractError("occurred_at must not be blank")
        validate_json(diagnostics, "diagnostics")
        record = {
            "schema_version": _SCHEMA,
            "record_type": "retrieval_attempt",
            "attempt_id": attempt_id,
            "source_id": candidate.source_id,
            "candidate_id": candidate.candidate_id,
            "document_id": candidate.document_id,
            "outcome": outcome.value,
            "occurred_at": occurred_at,
            "mechanism": mechanism,
            "artifact_id": None,
            "candidate": candidate.to_dict(),
            "retrieval_provider_identifiers": {},
            "diagnostics": diagnostics,
            "checkpoint_requested": None,
        }
        return self._append_record(f"attempt-{attempt_id}", record)

    def history(self) -> list[dict[str, Any]]:
        """Return validated append-only records in deterministic identity order."""
        records = [load_json(path) for path in sorted(self._layout.ledger.glob("*.json"))]
        seen: set[tuple[str, str]] = set()
        for record in records:
            record_type = record.get("record_type")
            identity = record.get("attempt_id")
            if record_type not in {"retrieval_attempt", "checkpoint_advanced"} or not isinstance(
                identity, str
            ):
                raise IntegrityError("ledger contains a record with invalid identity or type")
            key = (str(record_type), identity)
            if key in seen:
                raise IntegrityError(f"ledger contains duplicate identity: {key}")
            seen.add(key)
        return records

    def artifact_metadata(self) -> list[dict[str, Any]]:
        """Return all complete immutable artifact metadata records."""
        return [
            load_json(path)
            for path in sorted(self._layout.artifacts.glob("*.metadata.json"))
        ]

    def read_artifact(self, artifact_id: str) -> bytes:
        """Return exact stored evidence after independently checking its integrity."""
        require_identifier(artifact_id, "artifact_id")
        metadata_path, content_path = self._artifact_paths(artifact_id)
        if not metadata_path.is_file() or not content_path.is_file():
            raise IntegrityError(f"artifact is incomplete or absent: {artifact_id}")
        metadata = load_json(metadata_path)
        content = content_path.read_bytes()
        self._verify_artifact_record(metadata, content)
        return content

    def verify_integrity(self, include_derived: bool = True) -> dict[str, Any]:
        """Verify sources, ledger references, artifact hashes, and derived consistency."""
        source_ids = {record["source_id"] for record in self.sources()}
        metadata_by_id = {item["artifact_id"]: item for item in self.artifact_metadata()}
        content_ids = {
            path.name.removesuffix(".content")
            for path in self._layout.artifacts.glob("*.content")
        }
        if content_ids != set(metadata_by_id):
            raise IntegrityError("artifact content and metadata inventories differ")
        for artifact_id, metadata in metadata_by_id.items():
            content = (self._layout.artifacts / f"{artifact_id}.content").read_bytes()
            self._verify_artifact_record(metadata, content)
        records = self.history()
        attempts = 0
        checkpoints = 0
        for record in records:
            if record["source_id"] not in source_ids:
                raise IntegrityError(f"ledger references unknown source: {record['source_id']}")
            if record["record_type"] == "retrieval_attempt":
                attempts += 1
                artifact_id = record["artifact_id"]
                if record["outcome"] == RetrievalOutcome.SUCCESS.value:
                    if artifact_id not in metadata_by_id:
                        raise IntegrityError(f"attempt references absent artifact: {artifact_id}")
                elif artifact_id is not None:
                    raise IntegrityError("non-successful attempt references an artifact")
            else:
                checkpoints += 1
        if include_derived:
            expected_index = self._derive_index(records)
            expected_checkpoints = self._derive_checkpoints(records)
            if self._layout.index.is_file() and load_json(self._layout.index) != expected_index:
                raise IntegrityError("derived document index disagrees with authoritative records")
            if (
                self._layout.checkpoints.is_file()
                and load_json(self._layout.checkpoints) != expected_checkpoints
            ):
                raise IntegrityError(
                    "derived checkpoint view disagrees with authoritative records"
                )
        return {
            "sources": len(source_ids),
            "artifacts": len(metadata_by_id),
            "attempts": attempts,
            "checkpoint_events": checkpoints,
            "result": "PASS",
        }

    def document_index(self) -> dict[str, Any]:
        """Return the disposable document access index."""
        if not self._layout.index.is_file():
            raise IntegrityError("document index is absent; run replay")
        return load_json(self._layout.index)

    def checkpoints(self) -> dict[str, Any]:
        """Return the disposable source-progress view."""
        if not self._layout.checkpoints.is_file():
            return {"schema_version": _SCHEMA, "sources": {}}
        return load_json(self._layout.checkpoints)

    def advance_checkpoint(
        self, source_id: str, successful_attempt_id: str, checkpoint: Checkpoint
    ) -> bool:
        """Finalize source progress against an already durable successful attempt.

        Engines may need to know that a bounded discovery run completed before publishing its
        checkpoint. This public operation preserves the TASK-002 ordering invariant while keeping
        ledger layout and checkpoint-event construction repository-owned.
        """
        require_identifier(source_id, "source_id")
        require_identifier(successful_attempt_id, "attempt_id")
        self.source(source_id)
        successful = next(
            (
                record
                for record in self.history()
                if record["record_type"] == "retrieval_attempt"
                and record["attempt_id"] == successful_attempt_id
                and record["outcome"] == RetrievalOutcome.SUCCESS.value
            ),
            None,
        )
        if successful is None:
            raise ContractError("checkpoint requires an existing successful retrieval attempt")
        if successful["source_id"] != source_id:
            raise ContractError("checkpoint source differs from its successful retrieval attempt")
        return self._advance_checkpoint(source_id, successful_attempt_id, checkpoint)

    def delete_derived_state(self) -> None:
        """Remove only rebuildable acquisition views for replay demonstrations."""
        self._layout.index.unlink(missing_ok=True)
        self._layout.checkpoints.unlink(missing_ok=True)

    def replay(self, fail_at: FailurePoint | None = None) -> ReplayResult:
        """Rebuild all derived acquisition state from local authoritative records."""
        self.verify_integrity(include_derived=False)
        records = self.history()
        index = self._derive_index(records)
        checkpoints = self._derive_checkpoints(records)
        if fail_at == FailurePoint.DURING_REPLAY:
            self._fail(fail_at)
        self._write_derived_index(index)
        atomic_replace(self._layout.checkpoints, canonical_json(checkpoints))
        return ReplayResult(
            documents=len(index["documents"]),
            checkpoints=len(checkpoints["sources"]),
            attempts=sum(item["record_type"] == "retrieval_attempt" for item in records),
            index_sha256=sha256_bytes(canonical_json(index)),
            checkpoint_sha256=sha256_bytes(canonical_json(checkpoints)),
        )

    def _store_artifact(
        self, artifact_id: str, content: bytes, metadata: dict[str, Any]
    ) -> None:
        """Create exact bytes before their immutable metadata record."""
        metadata_path, content_path = self._artifact_paths(artifact_id)
        create_immutable(content_path, content)
        create_immutable(metadata_path, canonical_json(metadata))

    def _artifact_paths(self, artifact_id: str) -> tuple[Path, Path]:
        """Resolve private artifact paths without exposing them in public contracts."""
        return (
            self._layout.artifacts / f"{artifact_id}.metadata.json",
            self._layout.artifacts / f"{artifact_id}.content",
        )

    def _verify_artifact_record(self, metadata: dict[str, Any], content: bytes) -> None:
        """Validate immutable metadata against exact evidence bytes and identity."""
        digest = sha256_bytes(content)
        expected_id = f"artifact-{digest}"
        if metadata.get("sha256") != digest or metadata.get("artifact_id") != expected_id:
            raise IntegrityError(f"artifact integrity mismatch: {metadata.get('artifact_id')}")
        if metadata.get("size") != len(content):
            raise IntegrityError(f"artifact size mismatch: {metadata.get('artifact_id')}")

    def _append_record(self, record_id: str, record: dict[str, Any]) -> bool:
        """Append one immutable ledger record; exact identity repetition is idempotent."""
        return create_immutable(self._layout.ledger / f"{record_id}.json", canonical_json(record))

    def _assert_record_compatible(self, record_id: str, record: dict[str, Any]) -> None:
        """Reject an existing conflicting attempt before creating additional evidence."""
        path = self._layout.ledger / f"{record_id}.json"
        if path.is_file() and path.read_bytes() != canonical_json(record):
            raise ConflictError(f"immutable ledger identity already differs: {record_id}")

    def _advance_checkpoint(
        self, source_id: str, attempt_id: str, checkpoint: Checkpoint
    ) -> bool:
        """Append progress only after preceding required durable effects exist."""
        self._validate_checkpoint(source_id, checkpoint)
        event = {
            "schema_version": _SCHEMA,
            "record_type": "checkpoint_advanced",
            "attempt_id": attempt_id,
            "source_id": source_id,
            "checkpoint": checkpoint.to_dict(),
        }
        created = self._append_record(f"checkpoint-{attempt_id}", event)
        atomic_replace(
            self._layout.checkpoints, canonical_json(self._derive_checkpoints(self.history()))
        )
        return created

    def _validate_checkpoint(self, source_id: str, checkpoint: Checkpoint) -> None:
        """Reject backward or ambiguous progress before creating other durable effects."""
        current = self._derive_checkpoints(self.history())["sources"].get(source_id)
        if current is not None:
            current_position = current["position"]
            if checkpoint.position < current_position:
                raise ConflictError("checkpoint position cannot move backward")
            if checkpoint.position == current_position and checkpoint.cursor != current["cursor"]:
                raise ConflictError("checkpoint position is already bound to a different cursor")

    def _derive_index(self, records: list[dict[str, Any]]) -> dict[str, Any]:
        """Derive routine document access solely from authoritative successful attempts."""
        documents: dict[str, dict[str, Any]] = {}
        attempts: dict[str, dict[str, Any]] = {}
        for record in records:
            if record["record_type"] != "retrieval_attempt":
                continue
            attempt_id = record["attempt_id"]
            if attempt_id in attempts and attempts[attempt_id] != record:
                raise IntegrityError(f"conflicting attempt identity: {attempt_id}")
            attempts[attempt_id] = record
            if record["outcome"] != RetrievalOutcome.SUCCESS.value:
                continue
            document_id = record["document_id"]
            entry = documents.setdefault(
                document_id,
                {
                    "document_id": document_id,
                    "source_ids": [],
                    "artifacts": [],
                    "attempt_ids": [],
                    "provenance": [],
                },
            )
            if record["source_id"] not in entry["source_ids"]:
                entry["source_ids"].append(record["source_id"])
            if record["artifact_id"] not in entry["artifacts"]:
                entry["artifacts"].append(record["artifact_id"])
            if attempt_id not in entry["attempt_ids"]:
                entry["attempt_ids"].append(attempt_id)
                entry["provenance"].append(
                    {
                        "attempt_id": attempt_id,
                        "candidate_id": record["candidate_id"],
                        "discovery": record["candidate"]["provenance"],
                        "retrieval_mechanism": record["mechanism"],
                        "retrieved_at": record["occurred_at"],
                        "retrieval_provider_identifiers": record[
                            "retrieval_provider_identifiers"
                        ],
                    }
                )
        for entry in documents.values():
            for name in ("source_ids", "artifacts", "attempt_ids"):
                entry[name].sort()
            entry["provenance"].sort(key=lambda item: item["attempt_id"])
        return {"schema_version": _SCHEMA, "documents": dict(sorted(documents.items()))}

    def _derive_checkpoints(self, records: list[dict[str, Any]]) -> dict[str, Any]:
        """Derive source progress and reject ambiguous equal-position events."""
        sources: dict[str, dict[str, Any]] = {}
        successful_attempts = {
            record["attempt_id"]: record["source_id"]
            for record in records
            if record["record_type"] == "retrieval_attempt"
            and record["outcome"] == RetrievalOutcome.SUCCESS.value
        }
        for record in records:
            if record["record_type"] != "checkpoint_advanced":
                continue
            if record["attempt_id"] not in successful_attempts:
                raise IntegrityError("checkpoint event lacks a successful retrieval attempt")
            source_id = record["source_id"]
            if successful_attempts[record["attempt_id"]] != source_id:
                raise IntegrityError("checkpoint source differs from its retrieval attempt")
            checkpoint = record["checkpoint"]
            current = sources.get(source_id)
            if current is None or checkpoint["position"] > current["position"]:
                sources[source_id] = {**checkpoint, "attempt_id": record["attempt_id"]}
            elif checkpoint["position"] == current["position"]:
                if checkpoint["cursor"] != current["cursor"]:
                    raise IntegrityError("ambiguous checkpoint cursors at the same position")
                if record["attempt_id"] < current["attempt_id"]:
                    sources[source_id] = {**checkpoint, "attempt_id": record["attempt_id"]}
        return {"schema_version": _SCHEMA, "sources": dict(sorted(sources.items()))}

    def _write_derived_index(self, index: dict[str, Any]) -> None:
        """Persist the rebuildable document index atomically."""
        atomic_replace(self._layout.index, canonical_json(index))

    @staticmethod
    def _fail(point: FailurePoint) -> None:
        """Raise a deterministic observable failure for durability verification."""
        raise PartialFailure(f"injected failure at {point.value}")
