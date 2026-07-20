"""SQLite persistence boundary for revisioned artifact streams."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict
from pathlib import Path
from typing import Any, Iterable

from rfi.acquisition import AcquisitionRepository
from rfi.storage import RepositoryDatabase, StorageError, state_root_for
from rfi.storage.sqlite import canonical_json
from rfi.streams.contracts import (
    ArtifactProjection,
    StreamDraft,
    StreamError,
    StreamMembership,
    StreamRevision,
    StreamRun,
)


def _draft(value: dict[str, Any]) -> StreamDraft:
    return StreamDraft(
        stream_id=str(value["stream_id"]),
        name=str(value["name"]),
        description=str(value.get("description", "")),
        enabled=bool(value.get("enabled", True)),
        input_kind=str(value["input_kind"]),
        input_ids=tuple(str(item) for item in value.get("input_ids", [])),
        schema_id=str(value["schema_id"]),
        selection=dict(value.get("selection", {})),
        expansion=dict(value.get("expansion", {"strategy": "none"})),
        bounds={str(key): int(item) for key, item in value.get("bounds", {}).items()},
        metadata={str(key): str(item) for key, item in value.get("metadata", {}).items()},
    )


def _projection(row: dict[str, Any]) -> ArtifactProjection:
    attributes = json.loads(str(row["attributes_json"]))
    normalized = {
        str(key): tuple(str(item) for item in value) if isinstance(value, list) else str(value)
        for key, value in attributes.items()
    }
    return ArtifactProjection(
        artifact_id=str(row["artifact_id"]),
        document_id=str(row["document_id"]),
        schema_id=str(row["schema_id"]),
        source_id=str(row["source_id"]),
        effective_at=str(row["effective_at"]) if row["effective_at"] is not None else None,
        title=str(row["title"]),
        searchable_text=str(row["searchable_text"]),
        authors=tuple(str(item) for item in json.loads(str(row["authors_json"]))),
        attributes=normalized,
        context_id=str(row["context_id"]) if row["context_id"] is not None else None,
        context_depth=int(row["context_depth"]) if row["context_depth"] is not None else None,
        completeness=(
            str(row["completeness"]) if row["completeness"] is not None else None
        ),
    )


class StreamRepository:
    """Own stream revisions, typed projections, runs, memberships, and lineage."""

    def __init__(self, root: Path) -> None:
        self._state_root = state_root_for(root)
        try:
            self.database = RepositoryDatabase.initialize(self._state_root)
        except StorageError as error:
            raise StreamError("repository_failure", str(error)) from error
        self.artifacts = AcquisitionRepository(self._state_root / "acquisition")

    def rows(self, query: str, parameters: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
        try:
            with self.database.connect(read_only=True) as connection:
                return [dict(row) for row in connection.execute(query, parameters).fetchall()]
        except Exception as error:
            raise StreamError("repository_read_failure", "stream state cannot be read") from error

    def list_revisions(self) -> tuple[StreamRevision, ...]:
        rows = self.rows(
            "SELECT r.* FROM artifact_stream_revisions r JOIN artifact_streams s "
            "ON s.current_revision_id=r.revision_id ORDER BY r.name,r.stream_id"
        )
        return tuple(self._revision(row) for row in rows)

    def revision(self, stream_id: str, revision_id: str | None = None) -> StreamRevision:
        rows = self.rows(
            "SELECT r.* FROM artifact_stream_revisions r JOIN artifact_streams s "
            "ON s.stream_id=r.stream_id WHERE r.stream_id=? AND r.revision_id="
            "COALESCE(?,s.current_revision_id)",
            (stream_id, revision_id),
        )
        if not rows:
            raise StreamError("unknown_stream", f"unknown stream or revision: {stream_id}")
        return self._revision(rows[0])

    def history(self, stream_id: str) -> tuple[StreamRevision, ...]:
        rows = self.rows(
            "SELECT * FROM artifact_stream_revisions WHERE stream_id=? "
            "ORDER BY revision_number DESC", (stream_id,)
        )
        if not rows:
            raise StreamError("unknown_stream", f"unknown stream: {stream_id}")
        return tuple(self._revision(row) for row in rows)

    def dependencies(self, revision_id: str) -> tuple[str, ...]:
        return tuple(
            str(row["upstream_stream_id"])
            for row in self.rows(
                "SELECT upstream_stream_id FROM artifact_stream_dependencies "
                "WHERE revision_id=? ORDER BY ordinal", (revision_id,)
            )
        )

    def consumers(self, stream_id: str) -> tuple[str, ...]:
        return tuple(
            str(row["stream_id"])
            for row in self.rows(
                "SELECT DISTINCT r.stream_id FROM artifact_stream_dependencies d "
                "JOIN artifact_streams s ON s.current_revision_id=d.revision_id "
                "JOIN artifact_stream_revisions r ON r.revision_id=d.revision_id "
                "WHERE d.upstream_stream_id=? ORDER BY r.stream_id", (stream_id,)
            )
        )

    def save(self, draft: StreamDraft, expected_revision_id: str | None = None) -> StreamRevision:
        now = __import__("datetime").datetime.now(__import__("datetime").UTC).isoformat()
        payload = asdict(draft)
        try:
            with self.database.transaction() as connection:
                current = connection.execute(
                    "SELECT current_revision_id FROM artifact_streams WHERE stream_id=?",
                    (draft.stream_id,),
                ).fetchone()
                if current is None:
                    if expected_revision_id is not None:
                        raise StreamError("revision_conflict", "stream does not yet exist")
                    number = 1
                    predecessor = None
                else:
                    predecessor = str(current[0])
                    if expected_revision_id != predecessor:
                        raise StreamError(
                            "revision_conflict", "current stream revision has changed"
                        )
                    number_row = connection.execute(
                        "SELECT revision_number FROM artifact_stream_revisions "
                        "WHERE revision_id=?", (predecessor,)
                    ).fetchone()
                    assert number_row is not None
                    number = int(number_row[0]) + 1
                digest = hashlib.sha256(
                    canonical_json({"stream_id": draft.stream_id, "number": number,
                                    "draft": payload}).encode()
                ).hexdigest()
                revision_id = f"streamrev-{digest[:32]}"
                if current is None:
                    connection.execute(
                        "INSERT INTO artifact_streams VALUES (?,?)",
                        (draft.stream_id, revision_id),
                    )
                connection.execute(
                    "INSERT INTO artifact_stream_revisions VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                    (
                        revision_id, draft.stream_id, number, predecessor, draft.name,
                        draft.description, int(draft.enabled), draft.input_kind,
                        draft.schema_id, now, canonical_json(payload),
                    ),
                )
                if draft.input_kind == "streams":
                    for ordinal, upstream_id in enumerate(draft.input_ids):
                        connection.execute(
                            "INSERT INTO artifact_stream_dependencies VALUES (?,?,?)",
                            (revision_id, upstream_id, ordinal),
                        )
                connection.execute(
                    "UPDATE artifact_streams SET current_revision_id=? WHERE stream_id=?",
                    (revision_id, draft.stream_id),
                )
                self.database.advance_revision(connection)
        except StreamError:
            raise
        except StorageError as error:
            raise StreamError("repository_failure", str(error)) from error
        return self.revision(draft.stream_id)

    def upsert_projections(self, projections: Iterable[ArtifactProjection]) -> int:
        values = tuple(projections)
        if not values:
            return 0
        try:
            with self.database.transaction() as connection:
                for item in values:
                    attributes = {
                        key: list(value) if isinstance(value, tuple) else value
                        for key, value in item.attributes.items()
                    }
                    payload = asdict(item)
                    connection.execute(
                        "INSERT INTO artifact_stream_projections "
                        "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?) "
                        "ON CONFLICT(artifact_id) DO UPDATE SET document_id=excluded.document_id,"
                        "schema_id=excluded.schema_id,source_id=excluded.source_id,"
                        "effective_at=excluded.effective_at,title=excluded.title,"
                        "searchable_text=excluded.searchable_text,"
                        "authors_json=excluded.authors_json,"
                        "attributes_json=excluded.attributes_json,context_id=excluded.context_id,"
                        "context_depth=excluded.context_depth,completeness=excluded.completeness,"
                        "canonical_json=excluded.canonical_json",
                        (
                            item.artifact_id, item.document_id, item.schema_id, item.source_id,
                            item.effective_at, item.title, item.searchable_text,
                            canonical_json(list(item.authors)), canonical_json(attributes),
                            item.context_id, item.context_depth, item.completeness,
                            canonical_json(payload),
                        ),
                    )
                self.database.advance_revision(connection)
        except StorageError as error:
            raise StreamError("repository_failure", str(error)) from error
        return len(values)

    def projections(
        self, schema_id: str, source_ids: tuple[str, ...] = (), artifact_ids: tuple[str, ...] = ()
    ) -> tuple[ArtifactProjection, ...]:
        clauses = ["schema_id=?"]
        parameters: list[Any] = [schema_id]
        if source_ids:
            clauses.append("source_id IN (" + ",".join("?" for _ in source_ids) + ")")
            parameters.extend(source_ids)
        if artifact_ids:
            clauses.append("artifact_id IN (" + ",".join("?" for _ in artifact_ids) + ")")
            parameters.extend(artifact_ids)
        rows = self.rows(
            "SELECT * FROM artifact_stream_projections WHERE " + " AND ".join(clauses)
            + " ORDER BY COALESCE(effective_at,''),artifact_id", tuple(parameters)
        )
        return tuple(_projection(row) for row in rows)

    def external_sources(self) -> tuple[dict[str, Any], ...]:
        rows = self.rows(
            "SELECT source_id,mechanism,canonical_json FROM governed_sources ORDER BY source_id"
        )
        result = []
        for row in rows:
            governed = json.loads(str(row["canonical_json"]))
            item = {
                "source_id": str(row["source_id"]),
                "name": str(governed.get("name", row["source_id"])),
                "mechanism": str(row["mechanism"]),
                "configuration": governed.get("configuration", {}),
                "policy": governed.get("policy", {}),
            }
            result.append(item)
        return tuple(result)

    def context(
        self, schema_id: str, context_ids: tuple[str, ...]
    ) -> tuple[ArtifactProjection, ...]:
        if not context_ids:
            return ()
        placeholders = ",".join("?" for _ in context_ids)
        rows = self.rows(
            "SELECT * FROM artifact_stream_projections WHERE schema_id=? AND context_id IN ("
            + placeholders + ") ORDER BY context_id,context_depth,artifact_id",
            (schema_id, *context_ids),
        )
        return tuple(_projection(row) for row in rows)

    def successful_run(self, revision_id: str, fingerprint: str) -> StreamRun | None:
        rows = self.rows(
            "SELECT * FROM artifact_stream_runs WHERE revision_id=? AND input_fingerprint=? "
            "AND status='succeeded'", (revision_id, fingerprint)
        )
        return self._run(rows[0], True) if rows else None

    def begin_run(self, run_id: str, revision: StreamRevision, fingerprint: str, now: str) -> None:
        payload = {"stream_id": revision.stream_id, "revision_id": revision.revision_id}
        try:
            with self.database.transaction() as connection:
                connection.execute(
                    "INSERT INTO artifact_stream_runs "
                    "(run_id,stream_id,revision_id,requested_at,status,input_fingerprint,"
                    "canonical_json) VALUES (?,?,?,?,?,?,?)",
                    (run_id, revision.stream_id, revision.revision_id, now, "running",
                     fingerprint, canonical_json(payload)),
                )
                self.database.advance_revision(connection)
        except StorageError as error:
            raise StreamError("repository_failure", str(error)) from error

    def fail_run(self, run_id: str, completed_at: str, code: str, message: str) -> None:
        try:
            with self.database.transaction() as connection:
                connection.execute(
                    "UPDATE artifact_stream_runs SET status='failed',completed_at=?,error_code=?,"
                    "canonical_json=? WHERE run_id=? AND status='running'",
                    (completed_at, code, canonical_json({"error": message}), run_id),
                )
                self.database.advance_revision(connection)
        except StorageError as error:
            raise StreamError("repository_failure", str(error)) from error

    def publish_run(
        self, run_id: str, completed_at: str, publications: list[dict[str, Any]]
    ) -> StreamRun:
        direct = sum(item["inclusion_kind"] == "direct" for item in publications)
        context = len(publications) - direct
        plan = canonical_json(publications)
        try:
            with self.database.transaction() as connection:
                run = connection.execute(
                    "SELECT stream_id,revision_id FROM artifact_stream_runs "
                    "WHERE run_id=? AND status='running'", (run_id,)
                ).fetchone()
                if run is None:
                    raise StreamError("invalid_run", "stream run is not publishable")
                connection.execute(
                    "INSERT INTO artifact_stream_run_plans VALUES (?,?)", (run_id, plan)
                )
                self._insert_publications(
                    connection, run_id, str(run[0]), str(run[1]), publications
                )
                connection.execute(
                    "UPDATE artifact_stream_runs SET status='succeeded',completed_at=?,"
                    "direct_count=?,context_count=?,canonical_json=? WHERE run_id=?",
                    (completed_at, direct, context,
                     canonical_json({"published": len(publications)}), run_id),
                )
                self.database.advance_revision(connection)
        except StreamError:
            raise
        except StorageError as error:
            raise StreamError("repository_failure", str(error)) from error
        return self.run(run_id)

    def _insert_publications(
        self, connection: Any, run_id: str, stream_id: str, revision_id: str,
        publications: list[dict[str, Any]],
    ) -> None:
        for ordinal, item in enumerate(publications):
            membership_id = str(item["membership_id"])
            connection.execute(
                "INSERT INTO artifact_stream_memberships VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    membership_id, run_id, stream_id, revision_id, item["artifact_id"],
                    item["document_id"], item["inclusion_kind"], item["inclusion_reason"],
                    item["expansion_strategy"], item.get("completeness"), ordinal,
                    canonical_json(item),
                ),
            )
            for index, lineage in enumerate(item.get("lineage", [])):
                identity = f"{membership_id}\0{index}\0{canonical_json(lineage)}"
                digest = hashlib.sha256(identity.encode()).hexdigest()
                connection.execute(
                    "INSERT INTO artifact_stream_membership_lineage VALUES (?,?,?,?,?,?,?)",
                    (
                        f"lineage-{digest[:32]}", membership_id,
                        lineage.get("upstream_stream_id"), lineage.get("upstream_membership_id"),
                        lineage.get("seed_artifact_id"), lineage["inclusion_reason"],
                        canonical_json(lineage),
                    ),
                )

    def run(self, run_id: str) -> StreamRun:
        rows = self.rows("SELECT * FROM artifact_stream_runs WHERE run_id=?", (run_id,))
        if not rows:
            raise StreamError("unknown_run", f"unknown stream run: {run_id}")
        return self._run(rows[0])

    def runs(self, stream_id: str) -> tuple[StreamRun, ...]:
        return tuple(
            self._run(row) for row in self.rows(
                "SELECT * FROM artifact_stream_runs WHERE stream_id=? "
                "ORDER BY requested_at DESC,run_id DESC", (stream_id,)
            )
        )

    def latest_success(self, stream_id: str) -> StreamRun | None:
        rows = self.rows(
            "SELECT * FROM artifact_stream_runs WHERE stream_id=? AND status='succeeded' "
            "ORDER BY completed_at DESC,run_id DESC LIMIT 1", (stream_id,)
        )
        return self._run(rows[0]) if rows else None

    def memberships(
        self, stream_id: str, run_id: str | None = None, limit: int = 100, offset: int = 0
    ) -> tuple[StreamMembership, ...]:
        if not 1 <= limit <= 500 or offset < 0:
            raise StreamError("invalid_limit", "membership pagination is outside supported bounds")
        selected_run = run_id
        if selected_run is None:
            latest = self.latest_success(stream_id)
            if latest is None:
                return ()
            selected_run = latest.run_id
        rows = self.rows(
            "SELECT m.*,p.* FROM artifact_stream_memberships m "
            "JOIN artifact_stream_projections p ON p.artifact_id=m.artifact_id "
            "WHERE m.stream_id=? AND m.run_id=? ORDER BY m.ordinal LIMIT ? OFFSET ?",
            (stream_id, selected_run, limit, offset),
        )
        memberships = []
        for row in rows:
            lineage = tuple(
                json.loads(str(item["canonical_json"]))
                for item in self.rows(
                    "SELECT canonical_json FROM artifact_stream_membership_lineage "
                    "WHERE membership_id=? ORDER BY lineage_id", (row["membership_id"],)
                )
            )
            memberships.append(
                StreamMembership(
                    membership_id=str(row["membership_id"]), run_id=str(row["run_id"]),
                    stream_id=str(row["stream_id"]), revision_id=str(row["revision_id"]),
                    artifact_id=str(row["artifact_id"]), document_id=str(row["document_id"]),
                    inclusion_kind=str(row["inclusion_kind"]),
                    inclusion_reason=str(row["inclusion_reason"]),
                    expansion_strategy=str(row["expansion_strategy"]),
                    completeness=str(row["completeness"]) if row["completeness"] else None,
                    ordinal=int(row["ordinal"]), projection=_projection(row), lineage=lineage,
                )
            )
        return tuple(memberships)

    def membership(self, membership_id: str) -> StreamMembership:
        rows = self.rows(
            "SELECT stream_id,run_id FROM artifact_stream_memberships WHERE membership_id=?",
            (membership_id,),
        )
        if not rows:
            raise StreamError("unknown_membership", f"unknown membership: {membership_id}")
        items = self.memberships(str(rows[0]["stream_id"]), str(rows[0]["run_id"]), 500)
        return next(item for item in items if item.membership_id == membership_id)

    def delete_materialized_memberships(self) -> None:
        try:
            with self.database.transaction() as connection:
                connection.execute("DELETE FROM artifact_stream_membership_lineage")
                connection.execute("DELETE FROM artifact_stream_memberships")
                self.database.advance_revision(connection)
        except StorageError as error:
            raise StreamError("repository_failure", str(error)) from error

    def rebuild(self) -> dict[str, int | str]:
        plans = self.rows(
            "SELECT p.run_id,p.publication_json,r.stream_id,r.revision_id "
            "FROM artifact_stream_run_plans p JOIN artifact_stream_runs r ON r.run_id=p.run_id "
            "WHERE r.status='succeeded' ORDER BY r.completed_at,r.run_id"
        )
        try:
            with self.database.transaction() as connection:
                connection.execute("DELETE FROM artifact_stream_membership_lineage")
                connection.execute("DELETE FROM artifact_stream_memberships")
                total = 0
                for plan in plans:
                    publications = json.loads(str(plan["publication_json"]))
                    self._insert_publications(
                        connection, str(plan["run_id"]), str(plan["stream_id"]),
                        str(plan["revision_id"]), publications,
                    )
                    total += len(publications)
                self.database.advance_revision(connection)
        except StorageError as error:
            raise StreamError("repository_failure", str(error)) from error
        return {"runs": len(plans), "memberships": total, "result": "PASS"}

    def _revision(self, row: dict[str, Any]) -> StreamRevision:
        value = json.loads(str(row["canonical_json"]))
        return StreamRevision(
            stream_id=str(row["stream_id"]), revision_id=str(row["revision_id"]),
            revision_number=int(row["revision_number"]),
            predecessor_id=str(row["predecessor_id"]) if row["predecessor_id"] else None,
            created_at=str(row["created_at"]), draft=_draft(value),
        )

    @staticmethod
    def _run(row: dict[str, Any], idempotent: bool = False) -> StreamRun:
        return StreamRun(
            run_id=str(row["run_id"]), stream_id=str(row["stream_id"]),
            revision_id=str(row["revision_id"]), requested_at=str(row["requested_at"]),
            completed_at=str(row["completed_at"]) if row["completed_at"] else None,
            status=str(row["status"]), input_fingerprint=str(row["input_fingerprint"]),
            direct_count=int(row["direct_count"]), context_count=int(row["context_count"]),
            error_code=str(row["error_code"]) if row["error_code"] else None,
            idempotent=idempotent,
        )
