"""Durable, operator-readable execution journal for Pull Workflow runs."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any

from rfi.pull.contracts import PullError


class PullRunRepository:
    """Persist current run progress and terminal results independently by run ID."""

    def __init__(self, root: Path) -> None:
        self.root = root
        self.runs = root / "runs"
        self.runs.mkdir(parents=True, exist_ok=True)

    def create(self, run_id: str, value: dict[str, Any]) -> None:
        """Create one durable run identity without replacing an existing run."""
        path = self._path(run_id)
        content = self._content(value)
        try:
            with path.open("xb") as output:
                output.write(content)
                output.flush()
                os.fsync(output.fileno())
        except FileExistsError as error:
            raise PullError(f"pull run already exists: {run_id}") from error

    def save(self, run_id: str, value: dict[str, Any]) -> None:
        """Atomically publish updated progress for an existing run."""
        path = self._path(run_id)
        if not path.is_file():
            raise PullError(f"unknown pull run: {run_id}")
        descriptor, temporary = tempfile.mkstemp(prefix=f".{run_id}-", dir=self.runs)
        try:
            with os.fdopen(descriptor, "wb") as output:
                output.write(self._content(value))
                output.flush()
                os.fsync(output.fileno())
            os.replace(temporary, path)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)

    def get(self, run_id: str) -> dict[str, Any]:
        """Read one durable run record."""
        path = self._path(run_id)
        if not path.is_file():
            raise PullError(f"unknown pull run: {run_id}")
        value = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(value, dict) or value.get("run_id") != run_id:
            raise PullError(f"invalid pull run record: {run_id}")
        return value

    def list(self) -> tuple[dict[str, Any], ...]:
        """Return all durable run records newest first."""
        return tuple(
            sorted(
                (self.get(path.stem) for path in self.runs.glob("*.json")),
                key=lambda item: str(item.get("requested_at", "")),
                reverse=True,
            )
        )

    def _path(self, run_id: str) -> Path:
        if not run_id.startswith("pull-") or not run_id[5:].isalnum():
            raise PullError(f"invalid pull run identifier: {run_id}")
        return self.runs / f"{run_id}.json"

    @staticmethod
    def _content(value: dict[str, Any]) -> bytes:
        return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()
