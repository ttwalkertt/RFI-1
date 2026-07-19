"""SQLite-backed durable Pull Workflow execution journal."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from rfi.pull.contracts import PullError
from rfi.storage import RepositoryDatabase, StorageError, state_root_for
from rfi.storage.sqlite import canonical_json


class PullRunRepository:
    """Persist current run progress and terminal results transactionally by run ID."""

    def __init__(self, root: Path) -> None:
        self.root = root
        self.runs = root / "runs"  # legacy diagnostic location; never authoritative
        try:
            self._database = RepositoryDatabase.initialize(state_root_for(root))
        except StorageError as error:
            raise PullError(str(error)) from error

    def create(self, run_id: str, value: dict[str, Any]) -> None:
        self._validate_id(run_id)
        try:
            with self._database.transaction() as connection:
                connection.execute(
                    "INSERT INTO pull_runs VALUES (?,?,?,?,?)",
                    (
                        run_id,
                        str(value.get("status", "")),
                        str(value.get("requested_at", "")),
                        str(value.get("completed_at", "")),
                        canonical_json(value),
                    ),
                )
                self._database.advance_revision(connection)
        except StorageError as error:
            code = "pull run already exists" if error.code == "integrity_constraint" else str(error)
            message = f"{code}: {run_id}" if error.code == "integrity_constraint" else code
            raise PullError(message) from error

    def save(self, run_id: str, value: dict[str, Any]) -> None:
        self._validate_id(run_id)
        try:
            with self._database.transaction() as connection:
                changed = connection.execute(
                    "UPDATE pull_runs SET status=?,completed_at=?,canonical_json=? WHERE run_id=?",
                    (
                        str(value.get("status", "")),
                        str(value.get("completed_at", "")),
                        canonical_json(value),
                        run_id,
                    ),
                ).rowcount
                if changed != 1:
                    raise PullError(f"unknown pull run: {run_id}")
                self._database.advance_revision(connection)
        except StorageError as error:
            raise PullError(str(error)) from error

    def get(self, run_id: str) -> dict[str, Any]:
        self._validate_id(run_id)
        with self._database.connect(read_only=True) as connection:
            row = connection.execute(
                "SELECT canonical_json FROM pull_runs WHERE run_id = ?", (run_id,)
            ).fetchone()
        if row is None:
            raise PullError(f"unknown pull run: {run_id}")
        try:
            value = json.loads(str(row[0]))
        except json.JSONDecodeError as error:
            raise PullError(f"invalid pull run record: {run_id}") from error
        if not isinstance(value, dict) or value.get("run_id") != run_id:
            raise PullError(f"invalid pull run record: {run_id}")
        return value

    def list(self) -> tuple[dict[str, Any], ...]:
        with self._database.connect(read_only=True) as connection:
            rows = connection.execute(
                "SELECT canonical_json FROM pull_runs ORDER BY requested_at DESC,run_id DESC"
            ).fetchall()
        return tuple(json.loads(str(row[0])) for row in rows)

    @staticmethod
    def _validate_id(run_id: str) -> None:
        if not run_id.startswith("pull-") or not run_id[5:].isalnum():
            raise PullError(f"invalid pull run identifier: {run_id}")
