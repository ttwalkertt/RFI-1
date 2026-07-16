"""Independent SQLite persistence and lifecycle for source objects."""

from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import tempfile
from dataclasses import asdict
from pathlib import Path

from rfi.source_objects.contracts import (
    ParseStatus,
    SourceInput,
    SourceObject,
    SourceObjectError,
    SourceRebuildResult,
)
from rfi.source_objects.parser import parse_sec_submission

_SCHEMA = 1


class SourceObjectRepository:
    """A replaceable source catalog with no knowledge-subsystem dependency."""

    def __init__(self, path: Path) -> None:
        self.path = path

    def rebuild(
        self, inputs: list[SourceInput], fail_before_publish: bool = False
    ) -> SourceRebuildResult:
        """Build a complete catalog beside the current one and publish atomically."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        descriptor, name = tempfile.mkstemp(prefix=f".{self.path.name}.", dir=self.path.parent)
        os.close(descriptor)
        temporary = Path(name)
        try:
            connection = sqlite3.connect(temporary)
            try:
                self._create_schema(connection)
                for source in sorted(inputs, key=lambda item: (item.document_id, item.artifact_id)):
                    expected_id = f"artifact-{hashlib.sha256(source.content).hexdigest()}"
                    if source.artifact_id != expected_id:
                        raise SourceObjectError(
                            f"source input content does not match artifact identity: "
                            f"{source.artifact_id}"
                        )
                    self._store_parse(connection, source)
                connection.commit()
            finally:
                connection.close()
            result = self._result(temporary)
            if fail_before_publish:
                raise SourceObjectError("injected source rebuild failure before publication")
            os.replace(temporary, self.path)
            return result
        finally:
            temporary.unlink(missing_ok=True)

    def inventory(self) -> list[SourceObject]:
        """Return all current objects without exposing the SQLite schema."""
        rows = self._query(
            "SELECT object_json FROM source_objects ORDER BY source_object_id", ()
        )
        return [self._decode(row[0]) for row in rows]

    def get(self, source_object_id: str) -> SourceObject:
        """Read one object by stable contract identity."""
        rows = self._query(
            "SELECT object_json FROM source_objects WHERE source_object_id = ?",
            (source_object_id,),
        )
        if not rows:
            raise SourceObjectError(f"unknown source object: {source_object_id}")
        return self._decode(rows[0][0])

    def by_document(self, document_id: str) -> list[SourceObject]:
        """Navigate from a repository document to its structural objects."""
        rows = self._query(
            "SELECT object_json FROM source_objects WHERE document_id = ? "
            "ORDER BY byte_start, byte_end, source_object_id",
            (document_id,),
        )
        return [self._decode(row[0]) for row in rows]

    def field_value(self, source_object_id: str) -> str:
        """Return a normalized field value retained in the source contract."""
        item = self.get(source_object_id)
        if item.kind != "field" or "value" not in item.attributes:
            raise SourceObjectError(f"source object is not a normalized field: {source_object_id}")
        return item.attributes["value"]

    def parse_outcomes(self) -> list[dict[str, str]]:
        """Expose complete, incomplete, unsupported, and failed parser outcomes."""
        rows = self._query(
            "SELECT document_id, artifact_id, status, message FROM parses "
            "ORDER BY document_id, artifact_id",
            (),
        )
        return [
            {"document_id": row[0], "artifact_id": row[1], "status": row[2], "message": row[3]}
            for row in rows
        ]

    def bounded_context(self, source_object_id: str, content: bytes, radius: int = 120) -> bytes:
        """Return bounded exact context after verifying the caller supplied artifact bytes."""
        item = self.get(source_object_id)
        artifact_id = f"artifact-{hashlib.sha256(content).hexdigest()}"
        if artifact_id != item.artifact_id:
            raise SourceObjectError("content does not match the immutable artifact identity")
        digest = hashlib.sha256(content[item.byte_start:item.byte_end]).hexdigest()
        if digest != item.content_sha256:
            raise SourceObjectError("artifact bytes do not satisfy source-object provenance")
        start = max(0, item.byte_start - radius)
        end = min(len(content), item.byte_end + radius)
        return content[start:end]

    def verify(self, content_by_artifact: dict[str, bytes] | None = None) -> dict[str, int | str]:
        """Verify catalog identities, hierarchy, spans, and optional immutable bytes."""
        items = self.inventory()
        identities = {item.source_object_id for item in items}
        for item in items:
            if item.byte_start < 0 or item.byte_end < item.byte_start:
                raise SourceObjectError(f"invalid byte span: {item.source_object_id}")
            if item.parent_id is not None and item.parent_id not in identities:
                raise SourceObjectError(f"missing parent: {item.source_object_id}")
            if content_by_artifact is not None:
                content = content_by_artifact.get(item.artifact_id)
                if content is None:
                    raise SourceObjectError(f"missing artifact bytes: {item.artifact_id}")
                artifact_id = f"artifact-{hashlib.sha256(content).hexdigest()}"
                if artifact_id != item.artifact_id:
                    raise SourceObjectError(f"artifact identity mismatch: {item.artifact_id}")
                actual = hashlib.sha256(content[item.byte_start:item.byte_end]).hexdigest()
                if actual != item.content_sha256:
                    raise SourceObjectError(f"content digest mismatch: {item.source_object_id}")
        return {
            "objects": len(items),
            "artifacts": len({item.artifact_id for item in items}),
            "result": "PASS",
        }

    def _store_parse(self, connection: sqlite3.Connection, source: SourceInput) -> None:
        try:
            result = parse_sec_submission(source)
        except Exception as error:
            connection.execute(
                "INSERT INTO parses VALUES (?, ?, ?, ?)",
                (source.document_id, source.artifact_id, ParseStatus.FAILED.value, str(error)),
            )
            return
        connection.execute(
            "INSERT INTO parses VALUES (?, ?, ?, ?)",
            (source.document_id, source.artifact_id, result.status.value, result.message),
        )
        for item in result.objects:
            value = json.dumps(asdict(item), sort_keys=True, separators=(",", ":"))
            connection.execute(
                "INSERT INTO source_objects VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    item.source_object_id,
                    item.document_id,
                    item.artifact_id,
                    item.kind,
                    item.role,
                    item.byte_start,
                    item.byte_end,
                    item.parent_id,
                    item.content_sha256,
                    value,
                ),
            )

    def _create_schema(self, connection: sqlite3.Connection) -> None:
        connection.executescript(
            "CREATE TABLE metadata (schema_version INTEGER NOT NULL);"
            "INSERT INTO metadata VALUES (1);"
            "CREATE TABLE parses (document_id TEXT NOT NULL, artifact_id TEXT NOT NULL, "
            "status TEXT NOT NULL, message TEXT, PRIMARY KEY(document_id, artifact_id));"
            "CREATE TABLE source_objects (source_object_id TEXT PRIMARY KEY, "
            "document_id TEXT NOT NULL, artifact_id TEXT NOT NULL, kind TEXT NOT NULL, "
            "role TEXT NOT NULL, byte_start INTEGER NOT NULL, byte_end INTEGER NOT NULL, "
            "parent_id TEXT, content_sha256 TEXT NOT NULL, object_json TEXT NOT NULL);"
            "CREATE INDEX objects_document ON source_objects(document_id);"
            "CREATE INDEX objects_artifact ON source_objects(artifact_id);"
        )

    def _query(self, statement: str, parameters: tuple[str, ...]) -> list[tuple]:
        if not self.path.is_file():
            raise SourceObjectError(f"source-object catalog is absent: {self.path}")
        connection = sqlite3.connect(f"file:{self.path}?mode=ro", uri=True)
        try:
            version = connection.execute("SELECT schema_version FROM metadata").fetchone()
            if version != (_SCHEMA,):
                raise SourceObjectError("unsupported source-object catalog schema")
            return list(connection.execute(statement, parameters))
        except sqlite3.Error as error:
            raise SourceObjectError(f"cannot inspect source-object catalog: {error}") from error
        finally:
            connection.close()

    def _decode(self, value: str) -> SourceObject:
        data = json.loads(value)
        return SourceObject(**data)

    def _result(self, path: Path) -> SourceRebuildResult:
        connection = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
        try:
            objects = connection.execute("SELECT COUNT(*) FROM source_objects").fetchone()[0]
            artifacts = connection.execute("SELECT COUNT(*) FROM parses").fetchone()[0]
            incomplete = connection.execute(
                "SELECT COUNT(*) FROM parses WHERE status = ?", (ParseStatus.INCOMPLETE.value,)
            ).fetchone()[0]
            unsupported = connection.execute(
                "SELECT COUNT(*) FROM parses WHERE status = ?", (ParseStatus.UNSUPPORTED.value,)
            ).fetchone()[0]
        finally:
            connection.close()
        return SourceRebuildResult(
            artifacts=artifacts,
            objects=objects,
            incomplete=incomplete,
            unsupported=unsupported,
            catalog_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
        )
