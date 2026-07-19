"""TASK-021 SQLite structured-state foundation contract and operational proofs."""

from __future__ import annotations

import io
import sqlite3
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

from rfi.acquisition import (
    AcquisitionRepository,
    CandidateDocument,
    DiscoveryProvenance,
    FailurePoint,
    RetrievalResult,
    SourceProfile,
)
from rfi.acquisition.contracts import IntegrityError, PartialFailure
from rfi.artifacts import ArtifactQuery, ArtifactQueryError, ArtifactQueryService
from rfi.cli import main
from rfi.firms import FirmRepository, sample_firms
from rfi.source_profiles import load_canonical_template
from rfi.storage import RepositoryDatabase, StorageError, create_backup, restore_backup


class SQLiteFoundationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.state = self.root / "state"

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def initialize(self) -> None:
        self.assertEqual(main(("init", "--state", str(self.state))), 0)

    def repository_with_artifact(self) -> tuple[AcquisitionRepository, str]:
        self.initialize()
        firms = FirmRepository.open(self.state / "firm-catalog")
        firms.create(sample_firms()[0])
        repository = AcquisitionRepository(self.state / "acquisition")
        repository.register_source(
            SourceProfile(
                "source-task021",
                "TASK-021 fixture",
                True,
                "fixture-reader",
                policy={
                    "firm_id": "seagate",
                    "artifact_id": "sec_10k",
                    "retrieval_adapter_id": "fixture-task021",
                },
            )
        )
        candidate = CandidateDocument(
            "candidate-task021",
            "source-task021",
            "document-task021",
            DiscoveryProvenance(
                "2026-07-19T12:00:00Z",
                "fixture-manifest",
                {"accession": "0001137789-25-000001", "form": "10-K"},
                ("https://example.test/task021.htm",),
                {
                    "acceptance_datetime": "2025-08-01T20:00:00Z",
                    "filing_date": "2025-08-01",
                    "canonical_artifact_id": "sec_10k",
                    "firm_id": "seagate",
                    "provider": "fixture",
                },
            ),
        )
        result = RetrievalResult(
            b"<html><body>TASK-021 immutable evidence</body></html>",
            "text/html",
            "2026-07-19T12:01:00Z",
            "fixture-reader",
        )
        first = repository.record_success("attempt-task021-first", candidate, result)
        second = repository.record_success("attempt-task021-second", candidate, result)
        self.assertNotEqual(first.observation_id, second.observation_id)
        return repository, candidate.document_id

    def test_clean_repeated_initialization_and_explicit_seed(self) -> None:
        output = io.StringIO()
        with redirect_stdout(output):
            self.initialize()
            self.initialize()
            self.assertEqual(main(("seed", "--state", str(self.state))), 0)
            self.assertEqual(main(("seed", "--state", str(self.state))), 0)
        text = output.getvalue()
        self.assertIn("created authoritative SQLite repository", text)
        self.assertIn("compatible SQLite repository already existed", text)
        self.assertEqual(len(FirmRepository.open(self.state / "firm-catalog").lookup()), 3)

    def test_schema_version_configuration_constraints_and_no_blob(self) -> None:
        self.initialize()
        database = RepositoryDatabase.open(self.state)
        self.assertEqual(database.validate()["result"], "PASS")
        with database.connect() as connection:
            self.assertEqual(connection.execute("PRAGMA foreign_keys").fetchone()[0], 1)
            columns = connection.execute(
                "SELECT sql FROM sqlite_schema WHERE type='table' ORDER BY name"
            ).fetchall()
            self.assertFalse(any("BLOB" in str(row[0]).upper() for row in columns))
            with self.assertRaises(sqlite3.IntegrityError):
                connection.execute(
                    "INSERT INTO artifact_observations VALUES (?,?,?,?,?,?,?)",
                    ("bad", "missing", "missing", "missing", "missing", "now", "{}"),
                )

    def test_incompatible_schema_and_legacy_state_fail_explicitly(self) -> None:
        legacy = self.root / "legacy"
        legacy.mkdir()
        (legacy / "catalog.json").write_text("{}\n", encoding="utf-8")
        with self.assertRaisesRegex(StorageError, "automatic migration is unsupported"):
            RepositoryDatabase.initialize(legacy)
        self.initialize()
        with RepositoryDatabase.open(self.state).connect() as connection:
            connection.execute("UPDATE schema_metadata SET schema_version=99")
        with self.assertRaisesRegex(StorageError, "version 99 is unsupported"):
            RepositoryDatabase.open(self.state)

    def test_duplicate_identity_restart_query_and_stale_cursor(self) -> None:
        repository, document_id = self.repository_with_artifact()
        self.assertEqual(len(repository.artifact_metadata()), 1)
        self.assertEqual(len(repository.observations()), 2)
        content_files = [item for item in repository.content_root.rglob("*") if item.is_file()]
        self.assertEqual(len(content_files), 1)
        service = ArtifactQueryService(
            repository,
            FirmRepository.open(self.state / "firm-catalog"),
            load_canonical_template(),
        )
        first = service.detail(document_id, "first")
        last = service.detail(document_id, "last")
        self.assertNotEqual(first.observation.observation_id, last.observation.observation_id)
        self.assertEqual(service.content(document_id).content, content_files[0].read_bytes())
        page = service.query(ArtifactQuery(limit=1))
        restarted = ArtifactQueryService(
            AcquisitionRepository(self.state / "acquisition"),
            FirmRepository.open(self.state / "firm-catalog"),
            load_canonical_template(),
        )
        self.assertEqual(restarted.query(ArtifactQuery(limit=1)).items, page.items)
        if page.next_cursor is None:
            # Observation cursors are also snapshot-bound and always available here.
            cursor = first.observation_cursor
            repository.register_source(
                SourceProfile("source-task021-extra", "Extra", True, "fixture-reader")
            )
            with self.assertRaisesRegex(ArtifactQueryError, "repository changed"):
                restarted.next(cursor)

    def test_transaction_rollback_leaves_only_detectable_orphan(self) -> None:
        self.initialize()
        repository = AcquisitionRepository(self.state / "acquisition")
        repository.register_source(
            SourceProfile("source-rollback", "Rollback", True, "fixture-reader")
        )
        candidate = CandidateDocument(
            "candidate-rollback",
            "source-rollback",
            "document-rollback",
            DiscoveryProvenance("now", "fixture-manifest"),
        )
        result = RetrievalResult(b"orphan proof", "text/plain", "now", "fixture-reader")
        with self.assertRaises(PartialFailure):
            repository.record_success(
                "attempt-rollback", candidate, result, fail_at=FailurePoint.BEFORE_INDEX
            )
        self.assertEqual(repository.history(), [])
        self.assertEqual(repository.artifact_metadata(), [])
        with self.assertRaisesRegex(IntegrityError, "orphaned"):
            repository.verify_integrity()

    def test_backup_restore_reproduces_queries_and_checksums(self) -> None:
        repository, document_id = self.repository_with_artifact()
        service = ArtifactQueryService(
            repository,
            FirmRepository.open(self.state / "firm-catalog"),
            load_canonical_template(),
        )
        expected_page = service.query(ArtifactQuery())
        expected_content = service.content(document_id)
        archive = self.root / "backup.zip"
        self.assertEqual(create_backup(self.state, archive)["result"], "PASS")
        restored = self.root / "restored"
        self.assertEqual(restore_backup(archive, restored)["result"], "PASS")
        restored_service = ArtifactQueryService(
            AcquisitionRepository(restored / "acquisition"),
            FirmRepository.open(restored / "firm-catalog"),
            load_canonical_template(),
        )
        self.assertEqual(restored_service.query(ArtifactQuery()).items, expected_page.items)
        self.assertEqual(restored_service.content(document_id), expected_content)

    def test_missing_content_and_parameter_boundary_fail_closed(self) -> None:
        repository, document_id = self.repository_with_artifact()
        content = next(item for item in repository.content_root.rglob("*") if item.is_file())
        content.unlink()
        service = ArtifactQueryService(
            repository,
            FirmRepository.open(self.state / "firm-catalog"),
            load_canonical_template(),
        )
        with self.assertRaisesRegex(ArtifactQueryError, "unavailable or corrupt"):
            service.content(document_id)
        with self.assertRaises(ValueError):
            repository.source("source-task021' OR 1=1 --")

    def test_cli_reports_missing_state_without_sql_details(self) -> None:
        error = io.StringIO()
        with redirect_stderr(error):
            code = main(("verify", "--state", str(self.root / "missing")))
        self.assertEqual(code, 2)
        self.assertIn("not initialized", error.getvalue())
        self.assertNotIn("SELECT", error.getvalue())


if __name__ == "__main__":
    unittest.main()
