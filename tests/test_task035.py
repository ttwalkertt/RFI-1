"""Acceptance proofs for TASK-035 canonical message identity and observations."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from rfi.mailing_lists import (
    AcquisitionLimits,
    ArchiveMessage,
    FixtureMailingListArchive,
    LINUX_BLOCK_SOURCE,
    MailingListAcquisitionService,
    MailingListError,
    MailingListRepository,
    MailingListSource,
    SelectionCriteria,
)
from rfi.storage import RepositoryDatabase, create_backup, restore_backup


MESSAGE_ID = "<Task035@Example.COM>"
NORMALIZED_ID = "<Task035@example.com>"


def raw_message(message_id: str = MESSAGE_ID, body: str = "canonical body") -> bytes:
    return (
        f"Message-ID: {message_id}\r\nSubject: TASK-035\r\n"
        "From: Test <test@example.com>\r\n"
        "Date: Sat, 25 Jul 2026 12:00:00 +0000\r\n\r\n"
        f"{body}\r\n"
    ).encode()


class CanonicalMessageCase(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.state = self.root / "state"
        RepositoryDatabase.initialize(self.state)
        self.repository = MailingListRepository(self.state)
        self.repository.configure_source(LINUX_BLOCK_SOURCE)
        self.ids = iter(f"mailrun-task035-{index}" for index in range(20))
        self.archive = FixtureMailingListArchive({
            NORMALIZED_ID: ArchiveMessage(raw_message(), "fixture:task035")
        })

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def service(self, source_id: str = LINUX_BLOCK_SOURCE.source_id,
                archive: FixtureMailingListArchive | None = None
                ) -> MailingListAcquisitionService:
        return MailingListAcquisitionService(
            self.repository, archive or self.archive,
            clock=lambda: "2026-07-25T12:00:00+00:00",
            identifiers=self.ids.__next__,
        )

    def acquire(self, service: MailingListAcquisitionService | None = None,
                source_id: str = LINUX_BLOCK_SOURCE.source_id):
        return (service or self.service(source_id)).acquire(
            source_id, SelectionCriteria(message_ids=(NORMALIZED_ID,)),
            AcquisitionLimits(seed_limit=1, context_limit=2, descendant_depth=0),
        )

    def test_first_materialization_and_overlapping_run_reuse(self) -> None:
        first = self.acquire()
        second = self.acquire()
        canonical = self.repository.rows(
            "SELECT * FROM canonical_mailing_list_messages"
        )
        observations = self.repository.rows(
            "SELECT * FROM mailing_list_run_items ORDER BY run_id"
        )
        self.assertEqual(len(canonical), 1)
        self.assertEqual(canonical[0]["normalized_message_id"], NORMALIZED_ID)
        self.assertEqual(len(observations), 2)
        self.assertEqual(
            {row["canonical_message_id"] for row in observations},
            {canonical[0]["canonical_message_id"]},
        )
        self.assertEqual(observations[0]["observation_type"], "fetched")
        self.assertEqual(observations[0]["artifact_created"], 1)
        self.assertEqual(observations[0]["canonical_created"], 1)
        self.assertEqual(observations[1]["observation_type"], "reused")
        self.assertEqual(observations[1]["artifact_created"], 0)
        self.assertEqual(observations[1]["canonical_created"], 0)
        self.assertEqual(first.artifact_count_created, 1)
        self.assertEqual(second.artifact_count_created, 0)
        self.assertEqual(len(self.repository.artifacts.artifact_metadata()), 1)

    def test_cross_source_reuse_preserves_both_provenances(self) -> None:
        self.acquire()
        second_source = MailingListSource(
            "task035-other", "task035-other", "TASK-035 other list",
            "https://lore.kernel.org/task035-other/",
        )
        self.repository.configure_source(second_source)
        second = self.acquire(self.service(second_source.source_id), second_source.source_id)
        canonical = self.repository.rows("SELECT * FROM canonical_mailing_list_messages")
        observations = self.repository.rows(
            "SELECT source_id,canonical_message_id,observation_type,content_fetched,"
            "artifact_created,canonical_created FROM mailing_list_run_items ORDER BY run_id"
        )
        self.assertEqual(len(canonical), 1)
        self.assertEqual({row["source_id"] for row in observations}, {
            LINUX_BLOCK_SOURCE.source_id, second_source.source_id,
        })
        self.assertEqual({row["canonical_message_id"] for row in observations}, {
            canonical[0]["canonical_message_id"]
        })
        self.assertEqual(observations[1]["observation_type"], "fetched")
        self.assertEqual(observations[1]["content_fetched"], 1)
        self.assertEqual(second.artifact_count_created, 0)

    def test_conflicting_bytes_quarantine_without_changing_canonical(self) -> None:
        self.acquire()
        before = self.repository.rows("SELECT * FROM canonical_mailing_list_messages")[0]
        conflict_archive = FixtureMailingListArchive({
            NORMALIZED_ID: ArchiveMessage(raw_message(body="different"), "fixture:conflict")
        })
        manifest = self.acquire(self.service(archive=conflict_archive))
        self.assertEqual(manifest.conflict_count, 1)
        after = self.repository.rows("SELECT * FROM canonical_mailing_list_messages")[0]
        self.assertEqual(after["artifact_id"], before["artifact_id"])
        diagnostics = self.repository.rows("SELECT * FROM mailing_list_message_conflicts")
        self.assertEqual(len(diagnostics), 1)
        self.assertEqual(diagnostics[0]["normalized_message_id"], NORMALIZED_ID)

    def test_unavailable_then_available_keeps_both_evidence_forms(self) -> None:
        missing = "<missing-task035@example.com>"
        child = "<child-task035@example.com>"

        class MissingParent(FixtureMailingListArchive):
            def fetch(inner, external_message_id: str) -> ArchiveMessage:
                if external_message_id == missing:
                    raise MailingListError(
                        "archive_message_not_found", "confirmed absent",
                        details={"attempts": [
                            {"location": "https://lore.kernel.org/a/raw", "http_status": 404},
                            {"location": "https://lore.kernel.org/all/a/raw", "http_status": 404},
                        ]},
                    )
                return super().fetch(external_message_id)

        unavailable_archive = MissingParent({
            child: ArchiveMessage(raw_message(child).replace(
                b"Subject: TASK-035", f"In-Reply-To: {missing}\r\nSubject: TASK-035".encode()
            ), "fixture:child")
        })
        first_service = self.service(archive=unavailable_archive)
        first_service.acquire(
            LINUX_BLOCK_SOURCE.source_id, SelectionCriteria(message_ids=(child,)),
            AcquisitionLimits(seed_limit=1, context_limit=2, descendant_depth=0),
        )
        available = FixtureMailingListArchive({
            missing: ArchiveMessage(raw_message(missing), "fixture:now-available")
        })
        second_service = self.service(archive=available)
        second_service.acquire(
            LINUX_BLOCK_SOURCE.source_id, SelectionCriteria(message_ids=(missing,)),
            AcquisitionLimits(seed_limit=1, context_limit=2, descendant_depth=0),
        )
        rows = self.repository.rows(
            "SELECT observation_type,canonical_message_id FROM mailing_list_run_items "
            "WHERE external_message_id=? ORDER BY run_id", (missing,),
        )
        self.assertEqual([row["observation_type"] for row in rows], ["unavailable", "fetched"])
        self.assertIsNone(rows[0]["canonical_message_id"])
        self.assertIsNotNone(rows[1]["canonical_message_id"])

    def test_integrity_constraints_and_backup_restore(self) -> None:
        self.acquire()
        backup = self.root / "task035.zip"
        self.assertEqual(create_backup(self.state, backup)["result"], "PASS")
        restored = self.root / "restored"
        self.assertEqual(restore_backup(backup, restored)["result"], "PASS")
        restored_rows = MailingListRepository(restored).rows(
            "SELECT normalized_message_id FROM canonical_mailing_list_messages"
        )
        self.assertEqual(restored_rows[0]["normalized_message_id"], NORMALIZED_ID)
        self.assertEqual(RepositoryDatabase.open(restored).validate()["result"], "PASS")

    def test_v6_upgrade_backfills_without_rewriting_runs_or_projections(self) -> None:
        manifest = self.acquire()
        before_messages = self.repository.rows(
            "SELECT message_key,artifact_id,document_id FROM mailing_list_messages"
        )
        database = RepositoryDatabase.open(self.state)
        with database.connect() as connection:
            connection.execute("PRAGMA foreign_keys=OFF")
            connection.execute(
                "CREATE TABLE task035_old_run_items ("
                "run_id TEXT NOT NULL REFERENCES mailing_list_runs(run_id),"
                "source_id TEXT NOT NULL REFERENCES mailing_list_sources(source_id),"
                "external_message_id TEXT NOT NULL,"
                "artifact_id TEXT NOT NULL REFERENCES artifacts(artifact_id),"
                "document_id TEXT NOT NULL REFERENCES documents(document_id),"
                "inclusion_reason TEXT NOT NULL, is_seed INTEGER NOT NULL,"
                "connectivity_state TEXT NOT NULL, PRIMARY KEY(run_id,external_message_id)) STRICT"
            )
            connection.execute(
                "INSERT INTO task035_old_run_items SELECT run_id,source_id,external_message_id,"
                "artifact_id,document_id,inclusion_reason,is_seed,connectivity_state "
                "FROM mailing_list_run_items"
            )
            connection.execute("DROP TABLE mailing_list_run_items")
            connection.execute(
                "ALTER TABLE task035_old_run_items RENAME TO mailing_list_run_items"
            )
            connection.execute("DROP TABLE mailing_list_message_conflicts")
            connection.execute("DROP TABLE canonical_mailing_list_messages")
            connection.execute("UPDATE schema_metadata SET schema_version=6")
        upgraded = RepositoryDatabase.open(self.state)
        self.assertEqual(upgraded.validate()["schema_version"], 12)
        observations = MailingListRepository(self.state).rows(
            "SELECT run_id,canonical_message_id,observation_type "
            "FROM mailing_list_run_items"
        )
        self.assertEqual(observations[0]["run_id"], manifest.run_id)
        self.assertIsNotNone(observations[0]["canonical_message_id"])
        self.assertEqual(observations[0]["observation_type"], "reused")
        self.assertEqual(
            MailingListRepository(self.state).rows(
                "SELECT message_key,artifact_id,document_id FROM mailing_list_messages"
            ),
            before_messages,
        )


if __name__ == "__main__":
    unittest.main()
