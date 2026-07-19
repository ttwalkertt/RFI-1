"""Verified backup and restore for SQLite state plus immutable content objects."""

from __future__ import annotations

import hashlib
import json
import shutil
import sqlite3
import tempfile
import zipfile
from pathlib import Path
from typing import Any

from rfi.storage.sqlite import DATABASE_NAME, RepositoryDatabase, StorageError, utc_now

BACKUP_FORMAT_VERSION = 1


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _verify_content(state: Path, database: RepositoryDatabase) -> int:
    with database.connect(read_only=True) as connection:
        rows = connection.execute(
            "SELECT sha256,byte_count,content_reference FROM artifacts ORDER BY artifact_id"
        ).fetchall()
    referenced: set[Path] = set()
    for row in rows:
        parts = str(row[2]).split("/")
        if len(parts) != 3 or parts[0] != "sha256":
            raise StorageError("backup_failure", "repository content reference is invalid")
        path = state / "content" / parts[0] / parts[1] / parts[2]
        referenced.add(path)
        if not path.is_file() or _sha256(path) != row[0] or path.stat().st_size != row[1]:
            raise StorageError("backup_failure", "referenced immutable content failed verification")
    actual = set((state / "content").rglob("*")) if (state / "content").exists() else set()
    actual = {path for path in actual if path.is_file()}
    if actual != referenced:
        raise StorageError(
            "backup_failure", "content inventory contains missing or orphaned objects"
        )
    return len(referenced)


def create_backup(state: Path, destination: Path) -> dict[str, Any]:
    """Create one consistent, checksummed hybrid repository ZIP."""
    database = RepositoryDatabase.open(state)
    database.validate()
    _verify_content(state, database)
    if destination.exists():
        raise StorageError("backup_failure", "backup destination already exists")
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="rfi-backup-") as temporary_name:
        temporary = Path(temporary_name)
        snapshot = temporary / DATABASE_NAME
        source = database.connect(read_only=True)
        target = sqlite3.connect(snapshot)
        try:
            source.backup(target)
        except sqlite3.Error as error:
            raise StorageError("backup_failure", "SQLite backup could not be created") from error
        finally:
            target.close()
            source.close()
        RepositoryDatabase(temporary).validate()
        members: dict[str, dict[str, Any]] = {
            DATABASE_NAME: {"sha256": _sha256(snapshot), "size": snapshot.stat().st_size}
        }
        content_root = state / "content"
        if content_root.exists():
            for path in sorted(item for item in content_root.rglob("*") if item.is_file()):
                relative = path.relative_to(state).as_posix()
                members[relative] = {"sha256": _sha256(path), "size": path.stat().st_size}
        manifest = {
            "backup_format_version": BACKUP_FORMAT_VERSION,
            "schema_version": database.validate()["schema_version"],
            "created_at": utc_now(),
            "members": members,
        }
        manifest_path = temporary / "backup-manifest.json"
        manifest_path.write_text(
            json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        try:
            with zipfile.ZipFile(destination, "x", compression=zipfile.ZIP_DEFLATED) as archive:
                archive.write(snapshot, DATABASE_NAME)
                archive.write(manifest_path, "backup-manifest.json")
                for relative in sorted(members):
                    if relative != DATABASE_NAME:
                        archive.write(state / relative, relative)
        except (OSError, zipfile.BadZipFile) as error:
            destination.unlink(missing_ok=True)
            raise StorageError("backup_failure", "hybrid repository backup failed") from error
    return {
        "backup": str(destination),
        "members": len(members),
        "sha256": _sha256(destination),
        "result": "PASS",
    }


def restore_backup(archive_path: Path, state: Path) -> dict[str, Any]:
    """Verify and restore a backup into a fresh state location."""
    if state.exists() and any(state.iterdir()):
        raise StorageError("restore_failure", "restore target must be a fresh empty directory")
    try:
        with zipfile.ZipFile(archive_path) as archive:
            names = archive.namelist()
            if len(names) != len(set(names)) or "backup-manifest.json" not in names:
                raise StorageError("restore_failure", "backup member inventory is invalid")
            manifest = json.loads(archive.read("backup-manifest.json"))
            if manifest.get("backup_format_version") != BACKUP_FORMAT_VERSION:
                raise StorageError("restore_failure", "backup format is unsupported")
            members = manifest.get("members")
            if not isinstance(members, dict) or DATABASE_NAME not in members:
                raise StorageError("restore_failure", "backup manifest is invalid")
            expected_names = set(members) | {"backup-manifest.json"}
            if set(names) != expected_names:
                raise StorageError("restore_failure", "backup inventory does not match manifest")
            state.mkdir(parents=True, exist_ok=True)
            for name, facts in members.items():
                target = state / name
                try:
                    target.relative_to(state)
                except ValueError as error:
                    raise StorageError(
                        "restore_failure", "unsafe backup member rejected"
                    ) from error
                content = archive.read(name)
                if (
                    hashlib.sha256(content).hexdigest() != facts.get("sha256")
                    or len(content) != facts.get("size")
                ):
                    raise StorageError("restore_failure", "backup member checksum mismatch")
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(content)
    except StorageError:
        if state.exists():
            shutil.rmtree(state)
        raise
    except (OSError, zipfile.BadZipFile, json.JSONDecodeError, KeyError) as error:
        if state.exists():
            shutil.rmtree(state)
        raise StorageError("restore_failure", "backup archive is unreadable or corrupt") from error
    try:
        restored_database = RepositoryDatabase.open(state)
        validation = restored_database.validate()
        _verify_content(state, restored_database)
    except StorageError:
        shutil.rmtree(state)
        raise
    return {
        "state": str(state),
        "members": len(manifest["members"]),
        "schema_version": validation["schema_version"],
        "result": "PASS",
    }
