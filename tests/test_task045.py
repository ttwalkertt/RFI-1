"""Focused TASK-045 source observations, canonical lineage, and repair proofs."""

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
from rfi.mailing_lists.parser import parse_message
from rfi.storage import RepositoryDatabase, StorageError, create_backup, restore_backup


NVME = MailingListSource(
    "task045-nvme", "task045-nvme", "TASK-045 NVMe",
    "https://lore.kernel.org/task045-nvme/",
)


def raw(
    message_id: str, subject: str, *, parent: str | None = None,
    references: tuple[str, ...] = (), list_id: str = "linux-block.example",
    body: str = "body",
) -> bytes:
    headers = [
        f"Message-ID: {message_id}", f"Subject: {subject}",
        "From: Author <author@example.com>",
        "Date: Tue, 28 Jul 2026 12:00:00 +0000", f"List-Id: <{list_id}>",
    ]
    if parent:
        headers.append(f"In-Reply-To: {parent}")
    if references:
        headers.append("References: " + " ".join(references))
    return ("\r\n".join(headers) + "\r\n\r\n" + body + "\r\n").encode()


class MissingParentArchive(FixtureMailingListArchive):
    def fetch(self, external_message_id: str) -> ArchiveMessage:
        if external_message_id not in self.messages:
            raise MailingListError(
                "archive_message_not_found", "confirmed absent",
                details={"attempts": [
                    {"location": "https://lore.kernel.org/list/raw", "http_status": 404},
                    {"location": "https://lore.kernel.org/all/raw", "http_status": 404},
                ]},
            )
        return super().fetch(external_message_id)


class Task045Case(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.state = Path(self.temporary.name)
        RepositoryDatabase.initialize(self.state)
        self.repository = MailingListRepository(self.state)
        self.repository.configure_source(LINUX_BLOCK_SOURCE)
        self.repository.configure_source(NVME)
        self.run_number = 0

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def acquire(
        self, source: MailingListSource, messages: dict[str, ArchiveMessage],
        seeds: tuple[str, ...], *, context_limit: int = 20,
    ):
        self.run_number += 1
        return MailingListAcquisitionService(
            self.repository, FixtureMailingListArchive(messages),
            identifiers=lambda: f"mailrun-task045-{self.run_number}",
            clock=lambda: f"2026-07-28T12:{self.run_number:02d}:00+00:00",
        ).acquire(
            source.source_id, SelectionCriteria(message_ids=seeds),
            AcquisitionLimits(
                seed_limit=len(seeds), context_limit=context_limit, descendant_depth=0
            ),
        )

    def test_cross_source_byte_variants_share_canonical_node_and_keep_documents(self) -> None:
        shared = "<task045-shared@example.com>"
        block_bytes = raw(shared, "shared", list_id="linux-block.example")
        nvme_bytes = raw(shared, "shared", list_id="linux-nvme.example")
        self.acquire(LINUX_BLOCK_SOURCE, {
            shared: ArchiveMessage(block_bytes, "fixture:block")
        }, (shared,))
        result = self.acquire(NVME, {
            shared: ArchiveMessage(nvme_bytes, "fixture:nvme")
        }, (shared,))
        self.assertEqual(result.conflict_count, 0)
        rows = self.repository.rows(
            "SELECT source_id,artifact_id,document_id,canonical_message_id "
            "FROM mailing_list_messages WHERE external_message_id=? ORDER BY source_id",
            (shared,),
        )
        self.assertEqual(len(rows), 2)
        self.assertEqual(len({row["canonical_message_id"] for row in rows}), 1)
        self.assertEqual(len({row["artifact_id"] for row in rows}), 2)
        self.assertEqual(len({row["document_id"] for row in rows}), 2)

    def test_schema_v11_migration_backfills_links_without_losing_evidence(self) -> None:
        message_id = "<task045-migration@example.com>"
        self.acquire(LINUX_BLOCK_SOURCE, {
            message_id: ArchiveMessage(raw(message_id, "migration"), "fixture:migration")
        }, (message_id,))
        before = {
            table: int(self.repository.rows(f"SELECT count(*) AS count FROM {table}")[0]["count"])
            for table in ("artifacts", "documents", "mailing_list_runs", "mailing_list_run_items")
        }
        with self.repository._database.transaction() as connection:
            connection.execute("DROP TABLE mailing_list_relationship_claims")
            connection.execute(
                "ALTER TABLE mailing_list_messages DROP COLUMN canonical_message_id"
            )
            connection.execute(
                "UPDATE schema_metadata SET schema_version=11 WHERE singleton=1"
            )
        migrated = RepositoryDatabase.open(self.state)
        self.assertEqual(migrated.validate()["schema_version"], 13)
        reopened = MailingListRepository(self.state)
        after = {
            table: int(reopened.rows(f"SELECT count(*) AS count FROM {table}")[0]["count"])
            for table in before
        }
        self.assertEqual(after, before)
        linked = reopened.rows(
            "SELECT canonical_message_id FROM mailing_list_messages "
            "WHERE source_id=? AND external_message_id=?",
            (LINUX_BLOCK_SOURCE.source_id, message_id),
        )
        self.assertTrue(linked[0]["canonical_message_id"])

    def test_corpus_lineage_branches_across_source_discussions(self) -> None:
        shared = "<task045-branch-root@example.com>"
        block_child = "<task045-block-child@example.com>"
        nvme_child = "<task045-nvme-child@example.com>"
        self.acquire(LINUX_BLOCK_SOURCE, {
            shared: ArchiveMessage(raw(shared, "root"), "fixture:block-root"),
            block_child: ArchiveMessage(
                raw(block_child, "block child", parent=shared), "fixture:block-child"
            ),
        }, (block_child,))
        self.acquire(NVME, {
            shared: ArchiveMessage(
                raw(shared, "root", list_id="linux-nvme.example"), "fixture:nvme-root"
            ),
            nvme_child: ArchiveMessage(
                raw(nvme_child, "nvme child", parent=shared,
                    list_id="linux-nvme.example"), "fixture:nvme-child"
            ),
        }, (nvme_child,))
        lineage = self.repository.canonical_lineage(shared)
        self.assertEqual(len(lineage["nodes"]), 3)
        self.assertEqual(len(lineage["edges"]), 2)
        root_node = next(
            item for item in lineage["nodes"] if item["normalized_message_id"] == shared
        )
        self.assertEqual(len(root_node["observations"]), 2)
        self.assertEqual(len({item["discussion_id"] for item in root_node["observations"]}), 2)
        block = self.repository.canonical_lineage(
            shared, source_id=LINUX_BLOCK_SOURCE.source_id
        )
        nvme = self.repository.canonical_lineage(shared, source_id=NVME.source_id)
        self.assertEqual(len(block["edges"]), 1)
        self.assertEqual(len(nvme["edges"]), 1)

    def test_different_immediate_parents_are_ambiguous_not_overwritten(self) -> None:
        child = "<task045-ambiguous-child@example.com>"
        left = "<task045-left@example.com>"
        right = "<task045-right@example.com>"
        self.acquire(LINUX_BLOCK_SOURCE, {
            left: ArchiveMessage(raw(left, "left"), "fixture:left"),
            child: ArchiveMessage(raw(child, "child", parent=left), "fixture:child-left"),
        }, (child,))
        self.acquire(NVME, {
            right: ArchiveMessage(
                raw(right, "right", list_id="linux-nvme.example"), "fixture:right"
            ),
            child: ArchiveMessage(
                raw(child, "child", parent=right, list_id="linux-nvme.example"),
                "fixture:child-right",
            ),
        }, (child,))
        lineage = self.repository.canonical_lineage(child)
        child_node = next(
            item for item in lineage["nodes"] if item["normalized_message_id"] == child
        )
        self.assertTrue(child_node["immediate_parent_ambiguous"])
        self.assertEqual(len(lineage["edges"]), 2)

    def test_references_are_ancestry_claims_and_malformed_reply_is_parser_evidence(self) -> None:
        root = "<task045-ref-root@example.com>"
        middle = "<task045-ref-middle@example.com>"
        child = "<task045-ref-child@example.com>"
        malformed = raw(child, "child", references=(root, middle)).replace(
            b"References:", f"In-Reply-To: {root} {middle}\r\nReferences:".encode()
        )
        self.acquire(LINUX_BLOCK_SOURCE, {
            child: ArchiveMessage(malformed, "fixture:malformed")
        }, (child,))
        claims = self.repository.rows(
            "SELECT claim_role,evidence_type,reference_ordinal FROM "
            "mailing_list_relationship_claims WHERE child_external_message_id=? "
            "ORDER BY reference_ordinal", (child,),
        )
        self.assertEqual(len(claims), 2)
        self.assertTrue(all(item["claim_role"] == "ancestor_reference" for item in claims))
        parsed = parse_message(malformed)
        self.assertIn("ambiguous In-Reply-To", parsed.parse_warnings)
        self.assertEqual(len(parsed.in_reply_to_ids), 2)

    def test_unresolved_parent_is_boundary_not_placeholder_node(self) -> None:
        parent = "<task045-unresolved@example.com>"
        child = "<task045-boundary-child@example.com>"
        self.run_number += 1
        MailingListAcquisitionService(
            self.repository,
            MissingParentArchive({
                child: ArchiveMessage(raw(child, "child", parent=parent), "fixture:child")
            }),
            identifiers=lambda: f"mailrun-task045-{self.run_number}",
        ).acquire(
            LINUX_BLOCK_SOURCE.source_id, SelectionCriteria(message_ids=(child,)),
            AcquisitionLimits(seed_limit=1, context_limit=5, descendant_depth=0),
        )
        lineage = self.repository.canonical_lineage(child)
        self.assertEqual(len(lineage["nodes"]), 1)
        self.assertEqual(
            lineage["unresolved_boundaries"][0]["referenced_normalized_message_id"],
            parent,
        )
        self.assertIsNone(self.repository.canonical_message(parent))

        original_claim = dict(self.repository.rows(
            "SELECT * FROM mailing_list_relationship_claims "
            "WHERE child_external_message_id=?", (child,),
        )[0])
        self.acquire(LINUX_BLOCK_SOURCE, {
            parent: ArchiveMessage(raw(parent, "later parent"), "fixture:later-parent")
        }, (parent,))
        resolved = self.repository.canonical_lineage(child)
        self.assertEqual(len(resolved["edges"]), 1)
        self.assertEqual(resolved["unresolved_boundaries"], [])
        self.assertEqual(dict(self.repository.rows(
            "SELECT * FROM mailing_list_relationship_claims WHERE claim_id=?",
            (original_claim["claim_id"],),
        )[0]), original_claim)

    def test_agreeing_source_claims_derive_one_edge_with_two_observations(self) -> None:
        parent = "<task045-agree-parent@example.com>"
        child = "<task045-agree-child@example.com>"
        self.acquire(LINUX_BLOCK_SOURCE, {
            parent: ArchiveMessage(raw(parent, "parent"), "fixture:block-parent"),
            child: ArchiveMessage(raw(child, "child", parent=parent), "fixture:block-child"),
        }, (child,))
        self.acquire(NVME, {
            parent: ArchiveMessage(
                raw(parent, "parent", list_id="linux-nvme.example"), "fixture:nvme-parent"
            ),
            child: ArchiveMessage(
                raw(child, "child", parent=parent, list_id="linux-nvme.example"),
                "fixture:nvme-child",
            ),
        }, (child,))
        lineage = self.repository.canonical_lineage(child)
        self.assertEqual(len(lineage["edges"]), 1)
        self.assertEqual(len(lineage["edges"][0]["claims"]), 2)

    def test_validation_rejects_broken_canonical_links_and_claim_references(self) -> None:
        parent = "<task045-validate-parent@example.com>"
        child = "<task045-validate-child@example.com>"
        other = "<task045-validate-other@example.com>"
        self.acquire(LINUX_BLOCK_SOURCE, {
            parent: ArchiveMessage(raw(parent, "parent"), "fixture:parent"),
            child: ArchiveMessage(raw(child, "child", parent=parent), "fixture:child"),
            other: ArchiveMessage(raw(other, "other"), "fixture:other"),
        }, (child, other))
        child_canonical = self.repository.canonical_message(child)
        other_canonical = self.repository.canonical_message(other)
        assert child_canonical is not None and other_canonical is not None
        with self.repository._database.transaction() as connection:
            connection.execute(
                "UPDATE mailing_list_messages SET canonical_message_id=? "
                "WHERE source_id=? AND external_message_id=?",
                (
                    other_canonical["canonical_message_id"],
                    LINUX_BLOCK_SOURCE.source_id,
                    child,
                ),
            )
        with self.assertRaises(StorageError):
            self.repository._database.validate()
        with self.repository._database.transaction() as connection:
            connection.execute(
                "UPDATE mailing_list_messages SET canonical_message_id=? "
                "WHERE source_id=? AND external_message_id=?",
                (
                    child_canonical["canonical_message_id"],
                    LINUX_BLOCK_SOURCE.source_id,
                    child,
                ),
            )
            connection.execute(
                "UPDATE mailing_list_relationship_claims "
                "SET referenced_normalized_message_id=? "
                "WHERE child_external_message_id=?",
                (other, child),
            )
        with self.assertRaises(StorageError):
            self.repository._database.validate()

    def test_same_source_changed_bytes_is_terminal_and_has_no_frontier(self) -> None:
        message_id = "<task045-same-source@example.com>"
        self.acquire(LINUX_BLOCK_SOURCE, {
            message_id: ArchiveMessage(raw(message_id, "first"), "fixture:first")
        }, (message_id,))
        result = self.acquire(LINUX_BLOCK_SOURCE, {
            message_id: ArchiveMessage(
                raw(message_id, "changed", body="changed"), "fixture:changed"
            )
        }, (message_id,))
        self.assertEqual(result.relationship_status, "failed")
        self.assertEqual(result.error_code, "message_id_conflict")
        self.assertFalse(result.retryable)
        self.assertIsNone(result.relationship_continuation)
        self.assertFalse(result.coverage_complete)

    def test_invalid_legacy_frontier_is_rejected(self) -> None:
        missing = "<task045-missing-frontier@example.com>"
        with self.repository._database.transaction() as connection:
            payload = {
                "run_id": "mailrun-task045-invalid-frontier",
                "source_id": LINUX_BLOCK_SOURCE.source_id,
                "requested_at": "2026-07-28T12:00:00+00:00",
                "coverage_batch_id": "task045-frontier",
                "discovery_offset": 5,
                "relationship_status": "failed",
                "relationship_continuation": {
                    "version": 1, "phase": "replies", "seeds": [missing],
                    "discovery_has_more": True, "acquired_ids": [missing],
                    "ancestry_stack": [],
                    "reply_stack": [{"message_id": missing, "pending": []}],
                    "completed_reply_ids": [], "policy_truncated": False,
                },
            }
            from rfi.storage.sqlite import canonical_json
            connection.execute(
                "INSERT INTO mailing_list_runs VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                (payload["run_id"], LINUX_BLOCK_SOURCE.source_id,
                 payload["requested_at"], "incomplete", 1, 1, 1, 0,
                 canonical_json(payload), "partial", "continuation_corrupt", 0),
            )
        self.assertIsNone(self.repository.relationship_resume_state(
            LINUX_BLOCK_SOURCE.source_id, "task045-frontier", 5
        ))

    def test_repair_reuses_candidate_artifact_with_new_provenance_and_is_idempotent(self) -> None:
        message_id = "<task045-repair@example.com>"
        self.acquire(LINUX_BLOCK_SOURCE, {
            message_id: ArchiveMessage(raw(message_id, "repair"), "fixture:block")
        }, (message_id,))
        candidate_raw = raw(message_id, "repair", list_id="linux-nvme.example")
        parsed = parse_message(candidate_raw)
        candidate_doc, _created = self.repository._retain_conflict_candidate(
            NVME, "historical-failed-nvme", message_id, parsed, candidate_raw,
            "fixture:nvme", "relationship_context", "2026-07-28T13:00:00+00:00", None,
        )
        canonical = self.repository.canonical_message(message_id)
        assert canonical is not None
        conflict_id = self.repository._record_message_conflict(
            message_id, "artifact-" + __import__("hashlib").sha256(candidate_raw).hexdigest(),
            candidate_doc, NVME.source_id, "historical-failed-nvme", canonical,
        )
        historical = self.repository.rows(
            "SELECT * FROM mailing_list_message_conflict_observations WHERE conflict_id=?",
            (conflict_id,),
        )
        first = self.repository.repair_cross_source_conflicts(
            NVME.source_id, historical_run_id="historical-failed-nvme"
        )
        second = self.repository.repair_cross_source_conflicts(
            NVME.source_id, historical_run_id="historical-failed-nvme"
        )
        self.assertEqual(first["repaired"], [conflict_id])
        self.assertEqual(second["repaired"], [])
        self.assertEqual(self.repository.rows(
            "SELECT * FROM mailing_list_message_conflict_observations WHERE conflict_id=?",
            (conflict_id,),
        ), historical)
        repair_rows = self.repository.rows(
            "SELECT run_id,artifact_id,canonical_message_id FROM mailing_list_run_items "
            "WHERE source_id=? AND external_message_id=?", (NVME.source_id, message_id),
        )
        self.assertEqual(len(repair_rows), 1)
        self.assertTrue(str(repair_rows[0]["run_id"]).startswith("mailrepair-"))
        self.assertEqual(
            repair_rows[0]["artifact_id"],
            "artifact-" + __import__("hashlib").sha256(candidate_raw).hexdigest(),
        )
        self.assertEqual(RepositoryDatabase.open(self.state).validate()["result"], "PASS")
        backup = self.state / "task045.zip"
        # Backup destination must not sit inside the state content inventory.
        with tempfile.TemporaryDirectory() as target_name:
            target = Path(target_name)
            archive = target / "task045.zip"
            create_backup(self.state, archive)
            restored = target / "restored"
            restore_backup(archive, restored)
            self.assertEqual(RepositoryDatabase.open(restored).validate()["result"], "PASS")

    def test_each_repair_eligibility_predicate_fails_closed_independently(self) -> None:
        required = (
            "recorded_candidate",
            "parsed_identity",
            "source_absent",
            "global_mismatch_only",
            "representative_other_source",
            "no_accepted_source_variant",
        )
        for rejected in required:
            with self.subTest(rejected=rejected):
                predicates = {name: name != rejected for name in required}
                self.assertEqual(
                    self.repository._failed_repair_predicates(predicates), [rejected]
                )
        self.assertEqual(
            self.repository._failed_repair_predicates({name: True for name in required}), []
        )


if __name__ == "__main__":
    unittest.main()
