"""Durable SQLite authority for SEC source knowledge and workflow runs."""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import Any

from rfi.sec.contracts import SecApplicability, SecSourceKnowledge, SecWorkflowError
from rfi.storage import RepositoryDatabase, StorageError, state_root_for
from rfi.storage.sqlite import canonical_json


class SecRepository:
    def __init__(self, root: Path) -> None:
        self._database = RepositoryDatabase.open(state_root_for(root))

    def source(self, firm_id: str) -> SecSourceKnowledge | None:
        with self._database.connect(read_only=True) as connection:
            row = connection.execute(
                "SELECT canonical_json FROM sec_sources WHERE firm_id=?", (firm_id,)
            ).fetchone()
        return self._source(json.loads(str(row[0]))) if row else None

    def persist_source(
        self, source: SecSourceKnowledge, expected: SecSourceKnowledge | None
    ) -> tuple[SecSourceKnowledge, bool]:
        if source.verification_status != "verified":
            raise SecWorkflowError("SEC source persistence requires verified identity")
        existing = self.source(source.firm_id)
        if existing is not None and expected is None:
            raise SecWorkflowError("SEC source appeared during reconciliation")
        if existing != expected:
            raise SecWorkflowError("SEC source changed during reconciliation")
        created = existing is None
        value = self._source_dict(source)
        try:
            with self._database.transaction() as connection:
                if created:
                    connection.execute(
                        "INSERT INTO sec_sources VALUES (?,?,?,?,?,?,?,?,?)",
                        (
                            source.firm_id, source.applicability.value, source.legal_issuer,
                            source.cik, source.filing_regime, source.parent_firm_id,
                            source.verification_status, source.verified_at,
                            canonical_json(value),
                        ),
                    )
                else:
                    connection.execute(
                        "UPDATE sec_sources SET applicability=?,legal_issuer=?,cik=?,"
                        "filing_regime=?,parent_firm_id=?,verification_status=?,verified_at=?,"
                        "canonical_json=? WHERE firm_id=?",
                        (
                            source.applicability.value, source.legal_issuer, source.cik,
                            source.filing_regime, source.parent_firm_id,
                            source.verification_status, source.verified_at,
                            canonical_json(value), source.firm_id,
                        ),
                    )
                self._database.advance_revision(connection)
        except StorageError as error:
            raise SecWorkflowError(str(error)) from error
        return source, created

    def create_run(self, record: dict[str, Any]) -> None:
        with self._database.transaction() as connection:
            connection.execute(
                "INSERT INTO sec_workflow_runs VALUES (?,?,?,?,?,?,?,?)",
                (
                    record["run_id"], record["firm_id"], record["outcome"],
                    record["current_state"], record["requested_at"],
                    record.get("completed_at") or None,
                    int(record.get("cancellation_requested", False)), canonical_json(record),
                ),
            )
            self._database.advance_revision(connection)

    def save_run(self, record: dict[str, Any]) -> None:
        with self._database.transaction() as connection:
            connection.execute(
                "UPDATE sec_workflow_runs SET status=?,current_state=?,completed_at=?,"
                "cancellation_requested=?,canonical_json=? WHERE run_id=?",
                (
                    record["outcome"], record["current_state"],
                    record.get("completed_at") or None,
                    int(record.get("cancellation_requested", False)),
                    canonical_json(record), record["run_id"],
                ),
            )

    def run(self, run_id: str) -> dict[str, Any]:
        with self._database.connect(read_only=True) as connection:
            row = connection.execute(
                "SELECT canonical_json FROM sec_workflow_runs WHERE run_id=?", (run_id,)
            ).fetchone()
        if row is None:
            raise SecWorkflowError(f"unknown SEC workflow run: {run_id}")
        return json.loads(str(row[0]))

    def cancel(self, run_id: str) -> None:
        record = self.run(run_id)
        if record.get("completed_at"):
            return
        record["cancellation_requested"] = True
        self.save_run(record)

    @staticmethod
    def _source_dict(source: SecSourceKnowledge) -> dict[str, Any]:
        value = asdict(source)
        value["applicability"] = source.applicability.value
        return value

    @staticmethod
    def _source(value: dict[str, Any]) -> SecSourceKnowledge:
        value["applicability"] = SecApplicability(value["applicability"])
        return SecSourceKnowledge(**value)

