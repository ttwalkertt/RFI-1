"""Backward-compatibility coverage for source-profile digest schemas."""

from __future__ import annotations

import hashlib
import json
import sys
import tempfile
import unittest
from dataclasses import asdict, replace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from rfi.firms import FirmRepository, sample_firms  # noqa: E402
from rfi.source_profiles import (  # noqa: E402
    RetrievalCandidate,
    SourceProfileDraft,
    SourceProfileError,
    SourceProfileItem,
    SourceProfileRepository,
    load_canonical_template,
)
from rfi.storage.sqlite import canonical_json  # noqa: E402


def _canonical(value: object) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()


class SourceProfileDigestCompatibilityTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.state = Path(self.temporary.name)
        firms = FirmRepository.initialize(self.state / "firms")
        firms.create(next(item for item in sample_firms() if item.firm_id == "seagate"))
        self.template = load_canonical_template()
        self.repository = SourceProfileRepository.initialize(
            self.state / "source-profiles", self.template
        )

    def tearDown(self) -> None:
        self.temporary.cleanup()

    @staticmethod
    def draft(notes: str = "legacy") -> SourceProfileDraft:
        return SourceProfileDraft(
            "seagate",
            (
                SourceProfileItem(
                    "engineering_blog",
                    True,
                    (
                        RetrievalCandidate(
                            "discovery",
                            1,
                            preferred_domains=("example.com",),
                            discovery_hints=("storage",),
                        ),
                    ),
                ),
            ),
            notes,
        )

    def insert_legacy(self) -> tuple[str, str]:
        normalized = self.repository.normalize(self.draft())
        created_at = "2026-07-29T12:00:00+00:00"
        material = {
            **asdict(normalized),
            "revision_number": 1,
            "created_at": created_at,
            "updated_at": created_at,
            "supersedes_revision_id": None,
        }
        for item in material["items"]:
            for candidate in item["retrieval_candidates"]:
                candidate.pop("discovery_class")
        revision_id = "source-profile-revision-" + hashlib.sha256(
            _canonical(material)
        ).hexdigest()
        payload = {
            "firm_id": normalized.firm_id,
            "source_profile_revision_id": revision_id,
            "revision_number": 1,
            "items": material["items"],
            "operator_notes": normalized.operator_notes,
            "created_at": created_at,
            "updated_at": created_at,
            "supersedes_revision_id": None,
        }
        with self.repository._database.transaction() as connection:
            connection.execute(
                "INSERT INTO source_profile_revisions VALUES (?,?,?,?,?,?)",
                (revision_id, "seagate", 1, None, created_at, canonical_json(payload)),
            )
            for ordinal, item in enumerate(payload["items"]):
                connection.execute(
                    "INSERT INTO source_profile_items VALUES (?,?,?,?,?)",
                    (
                        revision_id,
                        item["artifact_id"],
                        ordinal,
                        int(item["enabled"]),
                        item["operator_notes"],
                    ),
                )
                for candidate in item["retrieval_candidates"]:
                    connection.execute(
                        "INSERT INTO retrieval_candidates VALUES (?,?,?,?,?)",
                        (
                            revision_id,
                            item["artifact_id"],
                            candidate["priority"],
                            candidate["mode"],
                            canonical_json(candidate),
                        ),
                    )
            connection.execute(
                "INSERT INTO source_profiles VALUES (?,?)", ("seagate", revision_id)
            )
        return revision_id, canonical_json(payload)

    def test_legacy_shape_digest_chain_and_read_only_open(self) -> None:
        revision_id, payload = self.insert_legacy()
        self.assertNotIn('"discovery_class"', payload)
        database_path = self.state / "repository.sqlite3"
        before_bytes = database_path.read_bytes()
        with self.repository._database.connect(read_only=True) as connection:
            before_rows = tuple(
                tuple(row)
                for row in connection.execute(
                    "SELECT * FROM source_profile_revisions ORDER BY revision_id"
                ).fetchall()
            )
        opened = SourceProfileRepository.open(self.state / "source-profiles", self.template)
        self.assertEqual(opened.verify(), {"profiles": 1, "revisions": 1, "result": "PASS"})
        revision = opened.get("seagate")
        self.assertEqual(revision.source_profile_revision_id, revision_id)
        self.assertEqual(revision.digest_schema_version, 1)
        candidate = next(
            item for item in revision.items if item.artifact_id == "engineering_blog"
        ).retrieval_candidates[0]
        self.assertEqual(candidate.discovery_class, "")
        self.assertEqual(database_path.read_bytes(), before_bytes)
        with self.repository._database.connect(read_only=True) as connection:
            after_rows = tuple(
                tuple(row)
                for row in connection.execute(
                    "SELECT * FROM source_profile_revisions ORDER BY revision_id"
                ).fetchall()
            )
        self.assertEqual(after_rows, before_rows)

    def test_mixed_legacy_and_current_history_authenticates_discovery_class(self) -> None:
        legacy_id, _ = self.insert_legacy()
        current = self.repository.publish(
            replace(self.draft("current"), items=(SourceProfileItem(
                "earnings_transcript", True, (RetrievalCandidate(
                    "discovery", 1, preferred_domains=("example.com",),
                    discovery_hints=("earnings",), discovery_class="standard"
                ),)
            ),)),
            legacy_id,
        )
        self.assertEqual(current.digest_schema_version, 4)
        self.assertEqual(current.supersedes_revision_id, legacy_id)
        history = self.repository.history("seagate")
        self.assertEqual([item.digest_schema_version for item in history], [1, 4])
        candidate = next(
            item for item in history[1].items if item.artifact_id == "earnings_transcript"
        ).retrieval_candidates[0]
        self.assertEqual(candidate.discovery_class, "standard")
        self.assertEqual(self.repository.verify()["result"], "PASS")

    def test_tampering_is_rejected_for_legacy_and_current_shapes(self) -> None:
        legacy_id, _ = self.insert_legacy()
        with self.repository._database.transaction() as connection:
            value = json.loads(
                connection.execute(
                    "SELECT canonical_json FROM source_profile_revisions WHERE revision_id=?",
                    (legacy_id,),
                ).fetchone()[0]
            )
            value["operator_notes"] = "tampered"
            connection.execute(
                "UPDATE source_profile_revisions SET canonical_json=? WHERE revision_id=?",
                (canonical_json(value), legacy_id),
            )
        with self.assertRaisesRegex(SourceProfileError, "digest mismatch"):
            self.repository.verify()

        self.tearDown()
        self.setUp()
        current = self.repository.publish(
            replace(self.draft("current"), items=(SourceProfileItem(
                "earnings_transcript", True, (RetrievalCandidate(
                    "discovery", 1, preferred_domains=("example.com",),
                    discovery_hints=("earnings",), discovery_class="standard"
                ),)
            ),)),
            None,
        )
        with self.repository._database.transaction() as connection:
            value = json.loads(connection.execute(
                "SELECT canonical_json FROM source_profile_revisions WHERE revision_id=?",
                (current.source_profile_revision_id,),
            ).fetchone()[0])
            item = next(
                item for item in value["items"] if item["artifact_id"] == "earnings_transcript"
            )
            item["retrieval_candidates"][0]["discovery_class"] = "extended"
            connection.execute(
                "UPDATE source_profile_revisions SET canonical_json=? WHERE revision_id=?",
                (canonical_json(value), current.source_profile_revision_id),
            )
        with self.assertRaisesRegex(SourceProfileError, "digest mismatch"):
            self.repository.verify()


if __name__ == "__main__":
    unittest.main()
