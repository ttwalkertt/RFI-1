"""Versioned JSON-generation persistence for independently derived knowledge."""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from dataclasses import asdict
from pathlib import Path
from typing import Any

from rfi.knowledge.contracts import (
    DerivationFailure,
    DerivedObject,
    KnowledgeError,
    KnowledgeStatus,
    ProvenanceReference,
)
from rfi.knowledge.derivation import DeterministicSecDeriver
from rfi.source_objects.contracts import SourceObjectReader

_SCHEMA = 1


def _canonical(value: Any) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()


class KnowledgeRepository:
    """Knowledge lifecycle independent of source catalog storage and rebuild mechanics."""

    def __init__(self, root: Path) -> None:
        self.root = root
        self.generations = root / "generations"
        self.pointer = root / "current-generation.json"

    def rebuild(
        self,
        source: SourceObjectReader,
        deriver: DeterministicSecDeriver | None = None,
        fail_before_publish: bool = False,
    ) -> dict[str, int | str]:
        """Replace the current derived view from only stable source-object contracts."""
        objects, failures = (deriver or DeterministicSecDeriver()).derive(source)
        generation_id = self._publish_generation(objects, failures)
        if fail_before_publish:
            raise KnowledgeError("injected knowledge rebuild failure before publication")
        self._atomic_write(
            self.pointer,
            _canonical({"schema_version": _SCHEMA, "generation_id": generation_id}),
        )
        return {
            "generation_id": generation_id,
            "objects": len(objects),
            "failures": len(failures),
            "result": "PASS",
        }

    def inventory(self, include_superseded: bool = False) -> list[DerivedObject]:
        """Return current versions or every version in the current generation."""
        generation = self._generation()
        manifest = self._load(generation / "manifest.json")
        version_ids = manifest["version_ids"]
        if not include_superseded:
            version_ids = list(manifest["current_versions"].values())
        return sorted(
            [
                self._decode(
                    self._load(generation / "versions" / f"{version_id}.json")
                )
                for version_id in version_ids
            ],
            key=lambda item: (item.object_id, item.version_id),
        )

    def get(self, object_id: str) -> DerivedObject:
        """Return the current version of one stable knowledge identity."""
        items = {item.object_id: item for item in self.inventory()}
        if object_id not in items:
            raise KnowledgeError(f"unknown current knowledge object: {object_id}")
        return items[object_id]

    def failures(self) -> list[DerivationFailure]:
        """Return visible derivation failures for the current generation."""
        values = self._load(self._generation() / "failures.json")["failures"]
        return [DerivationFailure(**value) for value in values]

    def by_source_object(self, source_object_id: str) -> list[DerivedObject]:
        """Navigate from source evidence to all associated current derived objects."""
        return [
            item
            for item in self.inventory()
            if any(ref.source_object_id == source_object_id for ref in item.provenance)
        ]

    def correct(
        self,
        object_id: str,
        payload: dict[str, Any],
        status: KnowledgeStatus,
        reason: str,
    ) -> DerivedObject:
        """Append an explicit correction version and supersede the prior current version."""
        if not reason.strip():
            raise KnowledgeError("correction reason must not be blank")
        current = self.get(object_id)
        material = {
            "object_id": current.object_id,
            "payload": payload,
            "status": status.value,
            "confidence": current.confidence,
            "provenance": [asdict(item) for item in current.provenance],
            "derivation_id": "operator-correction-v1",
            "supersedes_version_id": current.version_id,
            "reason": reason,
        }
        version_id = f"knowledge-version-{hashlib.sha256(_canonical(material)).hexdigest()}"
        corrected = DerivedObject(
            object_id=current.object_id,
            version_id=version_id,
            object_type=current.object_type,
            semantic_key=current.semantic_key,
            payload=payload,
            status=status,
            confidence=current.confidence,
            provenance=current.provenance,
            derivation_id="operator-correction-v1",
            supersedes_version_id=current.version_id,
            annotations={"correction_reason": reason},
        )
        versions = self.inventory(include_superseded=True) + [corrected]
        failures = self.failures()
        generation_id = self._publish_generation(versions, failures, {object_id: version_id})
        self._atomic_write(
            self.pointer,
            _canonical({"schema_version": _SCHEMA, "generation_id": generation_id}),
        )
        return corrected

    def verify(self, source: SourceObjectReader) -> dict[str, int | str]:
        """Validate history, current pointers, supersession, and exact provenance assertions."""
        all_versions = self.inventory(include_superseded=True)
        version_ids = {item.version_id for item in all_versions}
        for item in all_versions:
            if not 0.0 <= item.confidence <= 1.0:
                raise KnowledgeError(f"invalid confidence: {item.version_id}")
            if item.supersedes_version_id and item.supersedes_version_id not in version_ids:
                raise KnowledgeError(f"missing superseded version: {item.version_id}")
            if not item.provenance:
                raise KnowledgeError(f"knowledge object has no provenance: {item.version_id}")
            for reference in item.provenance:
                try:
                    actual = source.get(reference.source_object_id)
                except Exception as error:
                    raise KnowledgeError(
                        f"provenance source object is absent: {item.version_id}"
                    ) from error
                asserted = (
                    reference.document_id,
                    reference.artifact_id,
                    reference.byte_start,
                    reference.byte_end,
                    reference.content_sha256,
                )
                observed = (
                    actual.document_id,
                    actual.artifact_id,
                    actual.byte_start,
                    actual.byte_end,
                    actual.content_sha256,
                )
                if asserted != observed:
                    raise KnowledgeError(f"provenance inconsistency: {item.version_id}")
        return {
            "objects": len(self.inventory()),
            "versions": len(all_versions),
            "failures": len(self.failures()),
            "result": "PASS",
        }

    def _publish_generation(
        self,
        objects: list[DerivedObject],
        failures: list[DerivationFailure],
        current_override: dict[str, str] | None = None,
    ) -> str:
        by_version = {item.version_id: item for item in objects}
        current = {item.object_id: item.version_id for item in objects}
        if current_override:
            current.update(current_override)
        manifest = {
            "schema_version": _SCHEMA,
            "version_ids": sorted(by_version),
            "current_versions": dict(sorted(current.items())),
            "failure_ids": sorted(item.failure_id for item in failures),
        }
        payload = {
            "manifest": manifest,
            "versions": [asdict(by_version[key]) for key in sorted(by_version)],
            "failures": [
                asdict(item) for item in sorted(failures, key=lambda item: item.failure_id)
            ],
        }
        generation_id = f"knowledge-generation-{hashlib.sha256(_canonical(payload)).hexdigest()}"
        destination = self.generations / generation_id
        destination.mkdir(parents=True, exist_ok=True)
        (destination / "versions").mkdir(exist_ok=True)
        for version_id, item in sorted(by_version.items()):
            self._write_exact(
                destination / "versions" / f"{version_id}.json",
                _canonical(asdict(item)),
            )
        self._write_exact(destination / "manifest.json", _canonical(manifest))
        self._write_exact(
            destination / "failures.json",
            _canonical({"failures": [asdict(item) for item in failures]}),
        )
        return generation_id

    def _generation(self) -> Path:
        pointer = self._load(self.pointer)
        if pointer.get("schema_version") != _SCHEMA:
            raise KnowledgeError("unsupported knowledge pointer schema")
        path = self.generations / pointer["generation_id"]
        if not path.is_dir():
            raise KnowledgeError("current knowledge generation is absent")
        return path

    def _decode(self, value: dict[str, Any]) -> DerivedObject:
        value = dict(value)
        value["status"] = KnowledgeStatus(value["status"])
        value["provenance"] = tuple(ProvenanceReference(**item) for item in value["provenance"])
        return DerivedObject(**value)

    def _load(self, path: Path) -> dict[str, Any]:
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise KnowledgeError(f"cannot read knowledge state {path}: {error}") from error
        if not isinstance(value, dict):
            raise KnowledgeError(f"knowledge record is not an object: {path}")
        return value

    def _write_exact(self, path: Path, content: bytes) -> None:
        if path.exists():
            if path.read_bytes() != content:
                raise KnowledgeError(f"generation content conflict: {path.name}")
            return
        path.write_bytes(content)

    def _atomic_write(self, path: Path, content: bytes) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        descriptor, name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
        temporary = Path(name)
        try:
            with os.fdopen(descriptor, "wb") as stream:
                stream.write(content)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, path)
        finally:
            temporary.unlink(missing_ok=True)
