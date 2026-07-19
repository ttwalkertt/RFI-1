"""SQLite-backed acquisition repository with filesystem byte authority."""

from __future__ import annotations

import hashlib
import json
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
from rfi.acquisition.persistence import create_immutable, sha256_bytes
from rfi.storage import RepositoryDatabase, StorageError, state_root_for
from rfi.storage.sqlite import canonical_json, utc_now

_SCHEMA = 1


class AcquisitionRepository:
    """Public acquisition contract backed by authoritative SQLite structured state."""

    def __init__(self, root: Path) -> None:
        self._root = root
        self._state_root = state_root_for(root)
        try:
            self._database = RepositoryDatabase.initialize(self._state_root)
        except StorageError as error:
            raise IntegrityError(str(error)) from error
        self._content_root = self._state_root / "content" / "sha256"
        self._content_root.mkdir(parents=True, exist_ok=True)

    @property
    def root(self) -> Path:
        """Return the caller-selected repository boundary."""
        return self._root

    @property
    def database_path(self) -> Path:
        """Return the private database location for operational tooling."""
        return self._database.path

    @property
    def content_root(self) -> Path:
        """Return the private immutable content root for integrity tooling."""
        return self._content_root

    def register_source(self, profile: SourceProfile) -> bool:
        """Register one immutable governed source; exact repetition is idempotent."""
        record = {"schema_version": _SCHEMA, "record_type": "source", **profile.to_dict()}
        payload = canonical_json(record)
        try:
            with self._database.transaction() as connection:
                prior = connection.execute(
                    "SELECT canonical_json FROM governed_sources WHERE source_id = ?",
                    (profile.source_id,),
                ).fetchone()
                if prior is not None:
                    if str(prior[0]) != payload:
                        raise ConflictError(
                            f"immutable governed source already differs: {profile.source_id}"
                        )
                    return False
                connection.execute(
                    "INSERT INTO governed_sources(source_id,enabled,mechanism,canonical_json) "
                    "VALUES (?,?,?,?)",
                    (profile.source_id, int(profile.enabled), profile.mechanism, payload),
                )
                self._database.advance_revision(connection)
            return True
        except StorageError as error:
            raise IntegrityError(str(error)) from error

    def sources(self) -> list[dict[str, Any]]:
        with self._database.connect(read_only=True) as connection:
            rows = connection.execute(
                "SELECT canonical_json FROM governed_sources ORDER BY source_id"
            ).fetchall()
        return [self._decode(row[0], "governed source") for row in rows]

    def source(self, source_id: str) -> dict[str, Any]:
        require_identifier(source_id, "source_id")
        with self._database.connect(read_only=True) as connection:
            row = connection.execute(
                "SELECT canonical_json FROM governed_sources WHERE source_id = ?", (source_id,)
            ).fetchone()
        if row is None:
            raise ContractError(f"unknown governed source: {source_id}")
        return self._decode(row[0], "governed source")

    def record_success(
        self,
        attempt_id: str,
        candidate: CandidateDocument,
        result: RetrievalResult,
        checkpoint: Checkpoint | None = None,
        fail_at: FailurePoint | None = None,
    ) -> AcquisitionReceipt:
        """Write bytes first, then publish all structured success facts atomically."""
        require_identifier(attempt_id, "attempt_id")
        source = self.source(candidate.source_id)
        if not source["enabled"]:
            raise ContractError(f"source is disabled: {candidate.source_id}")
        if checkpoint is not None:
            self._validate_checkpoint(candidate.source_id, checkpoint)
        digest = sha256_bytes(result.content)
        artifact_id = f"artifact-{digest}"
        observation_id = self._observation_id(attempt_id, artifact_id)
        content_reference = f"sha256/{digest[:2]}/{digest}"
        content_path = self._content_root / digest[:2] / digest
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
            "observation_id": observation_id,
            "candidate": candidate.to_dict(),
            "retrieval_provider_identifiers": result.provider_identifiers,
            "diagnostics": result.diagnostics,
            "checkpoint_requested": checkpoint.to_dict() if checkpoint else None,
        }
        observation = {
            "schema_version": _SCHEMA,
            "record_type": "artifact_observation",
            "observation_id": observation_id,
            "attempt_id": attempt_id,
            "artifact_id": artifact_id,
            "document_id": candidate.document_id,
            "source_id": candidate.source_id,
            "candidate_id": candidate.candidate_id,
            "outcome": RetrievalOutcome.SUCCESS.value,
            "observed_at": result.retrieved_at,
            "mechanism": result.mechanism,
            "candidate": candidate.to_dict(),
            "retrieval_provider_identifiers": result.provider_identifiers,
            "diagnostics": result.diagnostics,
            "source_profile_revision_id": source.get("policy", {}).get(
                "source_profile_revision_id"
            ),
            "retrieval_adapter_id": source.get("policy", {}).get("retrieval_adapter_id"),
        }
        attempt_payload = canonical_json(attempt)
        observation_payload = canonical_json(observation)
        with self._database.connect(read_only=True) as connection:
            preexisting = connection.execute(
                "SELECT canonical_json FROM acquisition_attempts WHERE attempt_id = ?",
                (attempt_id,),
            ).fetchone()
        if preexisting is not None:
            if str(preexisting[0]) != attempt_payload:
                raise ConflictError(f"immutable attempt identity already differs: {attempt_id}")
            return AcquisitionReceipt(
                attempt_id,
                observation_id,
                artifact_id,
                candidate.document_id,
                checkpoint,
                True,
                False,
            )
        if fail_at == FailurePoint.BEFORE_ARTIFACT:
            self._fail(fail_at)
        content_created = create_immutable(content_path, result.content)
        if fail_at == FailurePoint.AFTER_ARTIFACT:
            self._fail(fail_at)
        try:
            with self._database.transaction() as connection:
                prior = connection.execute(
                    "SELECT canonical_json FROM acquisition_attempts WHERE attempt_id = ?",
                    (attempt_id,),
                ).fetchone()
                if prior is not None:
                    if str(prior[0]) != attempt_payload:
                        raise ConflictError(
                            f"immutable attempt identity already differs: {attempt_id}"
                        )
                    return AcquisitionReceipt(
                        attempt_id,
                        observation_id,
                        artifact_id,
                        candidate.document_id,
                        checkpoint,
                        True,
                        False,
                    )
                existing_artifact = connection.execute(
                    "SELECT sha256,byte_count,media_type,content_reference FROM artifacts "
                    "WHERE artifact_id = ?",
                    (artifact_id,),
                ).fetchone()
                artifact_created = existing_artifact is None
                if existing_artifact is None:
                    connection.execute(
                        "INSERT INTO artifacts VALUES (?,?,?,?,?,?)",
                        (
                            artifact_id,
                            digest,
                            len(result.content),
                            result.media_type.lower(),
                            content_reference,
                            result.retrieved_at,
                        ),
                    )
                elif tuple(existing_artifact) != (
                    digest,
                    len(result.content),
                    result.media_type.lower(),
                    content_reference,
                ):
                    raise ConflictError(f"immutable artifact already differs: {artifact_id}")
                connection.execute(
                    "INSERT INTO acquisition_attempts VALUES (?,?,?,?,?,?,?,?,?,?)",
                    (
                        attempt_id,
                        candidate.source_id,
                        candidate.candidate_id,
                        candidate.document_id,
                        RetrievalOutcome.SUCCESS.value,
                        result.retrieved_at,
                        result.mechanism,
                        artifact_id,
                        observation_id,
                        attempt_payload,
                    ),
                )
                connection.execute(
                    "INSERT INTO artifact_observations VALUES (?,?,?,?,?,?,?)",
                    (
                        observation_id,
                        attempt_id,
                        artifact_id,
                        candidate.document_id,
                        candidate.source_id,
                        result.retrieved_at,
                        observation_payload,
                    ),
                )
                connection.execute(
                    "INSERT INTO documents(document_id,current_artifact_id,durable_status) "
                    "VALUES (?,?,'durable') ON CONFLICT(document_id) DO UPDATE SET "
                    "current_artifact_id=excluded.current_artifact_id",
                    (candidate.document_id, artifact_id),
                )
                if checkpoint is not None:
                    self._insert_checkpoint(
                        connection, candidate.source_id, attempt_id, checkpoint
                    )
                if fail_at in {FailurePoint.BEFORE_INDEX, FailurePoint.BEFORE_CHECKPOINT}:
                    self._fail(fail_at)
                self._database.advance_revision(connection)
            return AcquisitionReceipt(
                attempt_id,
                observation_id,
                artifact_id,
                candidate.document_id,
                checkpoint,
                False,
                artifact_created,
            )
        except StorageError as error:
            raise IntegrityError(str(error)) from error
        except BaseException:
            if content_created:
                # The bytes-first protocol intentionally retains the orphan for diagnosis.
                pass
            raise

    def record_outcome(
        self,
        attempt_id: str,
        candidate: CandidateDocument,
        outcome: RetrievalOutcome,
        occurred_at: str,
        mechanism: str,
        diagnostics: dict[str, Any],
    ) -> bool:
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
        payload = canonical_json(record)
        try:
            with self._database.transaction() as connection:
                prior = connection.execute(
                    "SELECT canonical_json FROM acquisition_attempts WHERE attempt_id = ?",
                    (attempt_id,),
                ).fetchone()
                if prior is not None:
                    if str(prior[0]) != payload:
                        raise ConflictError(
                            f"immutable attempt identity already differs: {attempt_id}"
                        )
                    return False
                connection.execute(
                    "INSERT INTO acquisition_attempts VALUES (?,?,?,?,?,?,?,?,?,?)",
                    (
                        attempt_id,
                        candidate.source_id,
                        candidate.candidate_id,
                        candidate.document_id,
                        outcome.value,
                        occurred_at,
                        mechanism,
                        None,
                        None,
                        payload,
                    ),
                )
                self._database.advance_revision(connection)
            return True
        except StorageError as error:
            raise IntegrityError(str(error)) from error

    def history(self) -> list[dict[str, Any]]:
        with self._database.connect(read_only=True) as connection:
            attempts = connection.execute(
                "SELECT attempt_id,canonical_json FROM acquisition_attempts"
            ).fetchall()
            checkpoints = connection.execute(
                "SELECT event_id,canonical_json FROM checkpoint_events"
            ).fetchall()
        records = [(str(row[0]), self._decode(row[1], "attempt")) for row in attempts]
        records.extend((str(row[0]), self._decode(row[1], "checkpoint")) for row in checkpoints)
        return [record for _, record in sorted(records, key=lambda item: item[0])]

    def artifact_metadata(self) -> list[dict[str, Any]]:
        with self._database.connect(read_only=True) as connection:
            rows = connection.execute(
                "SELECT artifact_id,sha256,byte_count,media_type "
                "FROM artifacts ORDER BY artifact_id"
            ).fetchall()
        return [
            {
                "schema_version": _SCHEMA,
                "record_type": "artifact",
                "artifact_id": row[0],
                "sha256": row[1],
                "size": row[2],
                "media_type": row[3],
            }
            for row in rows
        ]

    def observations(self) -> list[dict[str, Any]]:
        with self._database.connect(read_only=True) as connection:
            rows = connection.execute(
                "SELECT canonical_json FROM artifact_observations "
                "ORDER BY observed_at,observation_id"
            ).fetchall()
        return [self._decode(row[0], "artifact observation") for row in rows]

    def read_artifact(self, artifact_id: str) -> bytes:
        require_identifier(artifact_id, "artifact_id")
        with self._database.connect(read_only=True) as connection:
            row = connection.execute(
                "SELECT sha256,byte_count,content_reference FROM artifacts WHERE artifact_id = ?",
                (artifact_id,),
            ).fetchone()
        if row is None:
            raise IntegrityError(f"artifact is absent: {artifact_id}")
        path = self._content_path(str(row[2]))
        try:
            content = path.read_bytes()
        except OSError as error:
            raise IntegrityError(f"artifact content is missing: {artifact_id}") from error
        digest = sha256_bytes(content)
        if digest != row[0] or len(content) != row[1] or artifact_id != f"artifact-{digest}":
            raise IntegrityError(f"artifact integrity mismatch: {artifact_id}")
        return content

    def verify_integrity(self, include_derived: bool = True) -> dict[str, Any]:
        del include_derived
        try:
            database = self._database.validate()
        except StorageError as error:
            raise IntegrityError(str(error)) from error
        metadata = self.artifact_metadata()
        referenced = {str(item["sha256"]) for item in metadata}
        for item in metadata:
            self.read_artifact(str(item["artifact_id"]))
        actual = {path.name for path in self._content_root.glob("*/*") if path.is_file()}
        missing = referenced - actual
        orphaned = actual - referenced
        if missing:
            raise IntegrityError("structured state references missing content")
        if orphaned:
            raise IntegrityError("content store contains orphaned content")
        with self._database.connect(read_only=True) as connection:
            counts = {
                "sources": connection.execute(
                    "SELECT count(*) FROM governed_sources"
                ).fetchone()[0],
                "artifacts": connection.execute("SELECT count(*) FROM artifacts").fetchone()[0],
                "attempts": connection.execute(
                    "SELECT count(*) FROM acquisition_attempts"
                ).fetchone()[0],
                "observations": connection.execute(
                    "SELECT count(*) FROM artifact_observations"
                ).fetchone()[0],
                "checkpoint_events": connection.execute(
                    "SELECT count(*) FROM checkpoint_events"
                ).fetchone()[0],
            }
        return {**counts, "database": database["result"], "result": "PASS"}

    def document_index(self) -> dict[str, Any]:
        documents: dict[str, dict[str, Any]] = {}
        for record in self.history():
            if (
                record.get("record_type") != "retrieval_attempt"
                or record.get("outcome") != "success"
            ):
                continue
            entry = documents.setdefault(
                str(record["document_id"]),
                {
                    "document_id": record["document_id"],
                    "source_ids": [],
                    "artifacts": [],
                    "attempt_ids": [],
                    "provenance": [],
                },
            )
            for key, value in (
                ("source_ids", record["source_id"]),
                ("artifacts", record["artifact_id"]),
                ("attempt_ids", record["attempt_id"]),
            ):
                if value not in entry[key]:
                    entry[key].append(value)
            entry["provenance"].append(
                {
                    "attempt_id": record["attempt_id"],
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

    def checkpoints(self) -> dict[str, Any]:
        with self._database.connect(read_only=True) as connection:
            rows = connection.execute(
                "SELECT source_id,position,cursor,event_id "
                "FROM current_checkpoints ORDER BY source_id"
            ).fetchall()
        return {
            "schema_version": _SCHEMA,
            "sources": {
                str(row[0]): {
                    "position": int(row[1]),
                    "cursor": row[2],
                    "attempt_id": str(row[3]).removeprefix("checkpoint-"),
                }
                for row in rows
            },
        }

    def advance_checkpoint(
        self, source_id: str, successful_attempt_id: str, checkpoint: Checkpoint
    ) -> bool:
        require_identifier(source_id, "source_id")
        require_identifier(successful_attempt_id, "attempt_id")
        self._validate_checkpoint(source_id, checkpoint)
        try:
            with self._database.transaction() as connection:
                attempt = connection.execute(
                    "SELECT source_id,outcome FROM acquisition_attempts WHERE attempt_id = ?",
                    (successful_attempt_id,),
                ).fetchone()
                if attempt is None or attempt[1] != RetrievalOutcome.SUCCESS.value:
                    raise ContractError(
                        "checkpoint requires an existing successful retrieval attempt"
                    )
                if attempt[0] != source_id:
                    raise ContractError(
                        "checkpoint source differs from its successful retrieval attempt"
                    )
                event_id = f"checkpoint-{successful_attempt_id}"
                prior = connection.execute(
                    "SELECT canonical_json FROM checkpoint_events WHERE event_id = ?", (event_id,)
                ).fetchone()
                event = self._checkpoint_record(source_id, successful_attempt_id, checkpoint)
                payload = canonical_json(event)
                if prior is not None:
                    if str(prior[0]) != payload:
                        raise ConflictError("immutable checkpoint event already differs")
                    return False
                self._insert_checkpoint(connection, source_id, successful_attempt_id, checkpoint)
                self._database.advance_revision(connection)
            return True
        except StorageError as error:
            raise IntegrityError(str(error)) from error

    def delete_derived_state(self) -> None:
        """SQLite query projections are transactional and require no deletion."""

    def replay(self, fail_at: FailurePoint | None = None) -> ReplayResult:
        """Verify authority and return deterministic relational projection digests."""
        self.verify_integrity()
        if fail_at == FailurePoint.DURING_REPLAY:
            self._fail(fail_at)
        index = self.document_index()
        checkpoints = self.checkpoints()
        return ReplayResult(
            len(index["documents"]),
            len(checkpoints["sources"]),
            sum(item.get("record_type") == "retrieval_attempt" for item in self.history()),
            hashlib.sha256(canonical_json(index).encode()).hexdigest(),
            hashlib.sha256(canonical_json(checkpoints).encode()).hexdigest(),
        )

    def repository_revision(self) -> int:
        return self._database.revision()

    def _validate_checkpoint(self, source_id: str, checkpoint: Checkpoint) -> None:
        current = self.checkpoints()["sources"].get(source_id)
        if current is None:
            return
        if checkpoint.position < current["position"]:
            raise ConflictError("checkpoint position cannot move backward")
        if checkpoint.position == current["position"] and checkpoint.cursor != current["cursor"]:
            raise ConflictError("checkpoint position is already bound to a different cursor")

    def _insert_checkpoint(
        self, connection: Any, source_id: str, attempt_id: str, checkpoint: Checkpoint
    ) -> None:
        event_id = f"checkpoint-{attempt_id}"
        event = self._checkpoint_record(source_id, attempt_id, checkpoint)
        connection.execute(
            "INSERT INTO checkpoint_events VALUES (?,?,?,?,?,?)",
            (
                event_id,
                source_id,
                attempt_id,
                str(checkpoint.position),
                checkpoint.cursor,
                canonical_json(event),
            ),
        )
        current = connection.execute(
            "SELECT position,cursor,event_id FROM current_checkpoints WHERE source_id = ?",
            (source_id,),
        ).fetchone()
        current_position = int(current[0]) if current is not None else None
        if current is None or checkpoint.position > current_position or (
            checkpoint.position == current_position and event_id < current[2]
        ):
            connection.execute(
                "INSERT INTO current_checkpoints VALUES (?,?,?,?) "
                "ON CONFLICT(source_id) DO UPDATE SET event_id=excluded.event_id,"
                "position=excluded.position,cursor=excluded.cursor",
                (source_id, event_id, str(checkpoint.position), checkpoint.cursor),
            )

    @staticmethod
    def _checkpoint_record(
        source_id: str, attempt_id: str, checkpoint: Checkpoint
    ) -> dict[str, Any]:
        return {
            "schema_version": _SCHEMA,
            "record_type": "checkpoint_advanced",
            "attempt_id": attempt_id,
            "source_id": source_id,
            "checkpoint": checkpoint.to_dict(),
        }

    def _content_path(self, reference: str) -> Path:
        parts = reference.split("/")
        if len(parts) != 3 or parts[0] != "sha256" or len(parts[1]) != 2 or len(parts[2]) != 64:
            raise IntegrityError("artifact content reference is invalid")
        path = self._state_root / "content" / parts[0] / parts[1] / parts[2]
        try:
            path.relative_to(self._state_root / "content")
        except ValueError as error:
            raise IntegrityError("artifact content reference is invalid") from error
        return path

    @staticmethod
    def _observation_id(attempt_id: str, artifact_id: str) -> str:
        payload = canonical_json({"attempt_id": attempt_id, "artifact_id": artifact_id}).encode()
        return f"observation-{hashlib.sha256(payload).hexdigest()}"

    @staticmethod
    def _decode(value: str, label: str) -> dict[str, Any]:
        try:
            decoded = json.loads(value)
        except json.JSONDecodeError as error:
            raise IntegrityError(f"{label} structured state is corrupt") from error
        if not isinstance(decoded, dict):
            raise IntegrityError(f"{label} structured state is invalid")
        return decoded

    @staticmethod
    def _fail(point: FailurePoint) -> None:
        raise PartialFailure(f"injected failure at {point.value}")
