"""Filesystem persistence behind repository-domain acquisition contracts."""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from pathlib import Path
from typing import Any

from rfi.acquisition.contracts import ConflictError, IntegrityError


def canonical_json(value: Any) -> bytes:
    """Encode portable records deterministically."""
    return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")


def sha256_bytes(content: bytes) -> str:
    """Return the SHA-256 digest for exact bytes."""
    return hashlib.sha256(content).hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    """Load one JSON object or report authoritative corruption."""
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise IntegrityError(f"cannot read JSON record {path}: {error}") from error
    if not isinstance(value, dict):
        raise IntegrityError(f"JSON record is not an object: {path}")
    return value


def fsync_directory(path: Path) -> None:
    """Flush directory entries where the platform supports directory fsync."""
    descriptor = os.open(path, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def atomic_replace(path: Path, content: bytes) -> None:
    """Durably replace derived state through a same-directory atomic rename."""
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        fsync_directory(path.parent)
    finally:
        temporary.unlink(missing_ok=True)


def create_immutable(path: Path, content: bytes) -> bool:
    """Create immutable-by-contract content; return False for an exact existing record."""
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o444)
    except FileExistsError:
        try:
            existing = path.read_bytes()
        except OSError as error:
            raise IntegrityError(
                f"cannot inspect existing immutable record {path}: {error}"
            ) from error
        if existing != content:
            raise ConflictError(f"immutable identity already has different content: {path.name}")
        return False
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        fsync_directory(path.parent)
    except BaseException:
        path.unlink(missing_ok=True)
        raise
    return True


class RepositoryLayout:
    """Private physical layout for authoritative and derived acquisition state."""

    def __init__(self, root: Path) -> None:
        self.root = root
        self.authoritative = root / "authoritative"
        self.sources = self.authoritative / "sources"
        self.artifacts = self.authoritative / "artifacts"
        self.observations = self.authoritative / "artifact-observations"
        self.ledger = self.authoritative / "retrieval-ledger"
        self.derived = root / "derived"
        self.index = self.derived / "document-index.json"
        self.checkpoints = self.derived / "checkpoints.json"

    def initialize(self) -> None:
        """Create private storage directories without establishing domain records."""
        for path in (
            self.sources,
            self.artifacts,
            self.observations,
            self.ledger,
            self.derived,
        ):
            path.mkdir(parents=True, exist_ok=True)
