"""Backward-compatibility coverage for source-profile digest schemas."""

from __future__ import annotations

import hashlib
import json
import sys
import tempfile
import unittest
from dataclasses import asdict, replace
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from rfi.admin import create_admin_server  # noqa: E402
from rfi.concepts import ConceptRepository  # noqa: E402
from rfi.firms import FirmDraft, FirmRepository, FirmStatus, sample_firms  # noqa: E402
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
        self.firms = FirmRepository.initialize(self.state / "firms")
        self.firms.create(next(
            item for item in sample_firms() if item.firm_id == "seagate"
        ))
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
                candidate.pop("provider")
                candidate.pop("discovery_hint_kind")
                candidate.pop("discovery_hint_value")
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

    @staticmethod
    def _strip_provider_fields(material: dict[str, object]) -> None:
        for item in material["items"]:  # type: ignore[index]
            for candidate in item["retrieval_candidates"]:
                candidate.pop("provider")
                candidate.pop("discovery_hint_kind")
                candidate.pop("discovery_hint_value")

    def _insert_payload(self, payload: dict[str, object]) -> None:
        revision_id = str(payload["source_profile_revision_id"])
        with self.repository._database.transaction() as connection:
            connection.execute(
                "INSERT INTO source_profile_revisions VALUES (?,?,?,?,?,?)",
                (
                    revision_id,
                    payload["firm_id"],
                    payload["revision_number"],
                    payload["supersedes_revision_id"],
                    payload["created_at"],
                    canonical_json(payload),
                ),
            )
            current = connection.execute(
                "SELECT 1 FROM source_profiles WHERE firm_id=?", (payload["firm_id"],)
            ).fetchone()
            if current is None:
                connection.execute(
                    "INSERT INTO source_profiles VALUES (?,?)",
                    (payload["firm_id"], revision_id),
                )
            else:
                connection.execute(
                    "UPDATE source_profiles SET current_revision_id=? WHERE firm_id=?",
                    (revision_id, payload["firm_id"]),
                )

    def _legacy_payload(
        self,
        schema: int,
        number: int,
        supersedes: str | None,
    ) -> dict[str, object]:
        normalized = self.repository.normalize(self.draft(f"schema-{schema}"))
        created_at = "2026-07-29T12:00:00+00:00"
        material: dict[str, object] = {
            **asdict(normalized),
            "revision_number": number,
            "created_at": created_at,
            "updated_at": f"2026-07-29T12:00:0{number}+00:00",
            "supersedes_revision_id": supersedes,
        }
        self._strip_provider_fields(material)
        if schema == 1:
            for item in material["items"]:  # type: ignore[index]
                for candidate in item["retrieval_candidates"]:
                    candidate.pop("discovery_class")
        elif schema == 3:
            material["digest_schema_version"] = 3
        elif schema != 2:
            raise AssertionError(f"unsupported test schema: {schema}")
        revision_id = "source-profile-revision-" + hashlib.sha256(
            _canonical(material)
        ).hexdigest()
        return {**material, "source_profile_revision_id": revision_id}

    def _live_meta_payload(self) -> dict[str, object]:
        enabled = {
            "sec_10k", "sec_10q", "sec_8k", "annual_report", "earnings_release",
            "press_release", "corporate_news", "product_page",
        }
        sec_candidates = {
            artifact_id: (RetrievalCandidate(
                "identifier",
                1,
                url="https://data.sec.gov/submissions/CIK0001326801.json",
                locator="0001326801",
            ),)
            for artifact_id in ("sec_10k", "sec_10q", "sec_8k")
        }
        draft = SourceProfileDraft(
            "meta",
            tuple(
                SourceProfileItem(
                    artifact.artifact_id,
                    artifact.artifact_id in enabled,
                    sec_candidates.get(artifact.artifact_id, ()),
                )
                for artifact in self.template.artifacts
                if artifact.artifact_id != "management_transcript"
            ),
        )
        material: dict[str, object] = {
            **asdict(self.repository.normalize(draft)),
            "revision_number": 1,
            "created_at": "2026-07-26T21:37:31.836815+00:00",
            "updated_at": "2026-07-26T21:37:31.836815+00:00",
            "supersedes_revision_id": None,
        }
        material["items"] = [
            item for item in material["items"]  # type: ignore[index]
            if item["artifact_id"] != "management_transcript"
        ]
        self._strip_provider_fields(material)
        for item in material["items"]:  # type: ignore[index]
            for candidate in item["retrieval_candidates"]:
                candidate.pop("discovery_class")
        revision_id = "source-profile-revision-" + hashlib.sha256(
            _canonical(material)
        ).hexdigest()
        return {**material, "source_profile_revision_id": revision_id}

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

    def test_live_meta_revision_authenticates_through_startup_without_writes(self) -> None:
        live_revision_id = (
            "source-profile-revision-"
            "1346e6e31eb2f1cdc28a3f73f660bac7f203b765659f61b535003ad2c81ff93b"
        )
        self.firms.create(FirmDraft(
            "meta", "Meta Platforms, Inc.", "2026-01-01",
            status=FirmStatus.ACTIVE,
        ))
        ConceptRepository.initialize(self.state)
        payload = self._live_meta_payload()
        self.assertEqual(payload["source_profile_revision_id"], live_revision_id)
        self.assertNotIn("digest_schema_version", payload)
        self._insert_payload(payload)
        database_path = self.state / "repository.sqlite3"
        before_bytes = database_path.read_bytes()
        with self.repository._database.connect(read_only=True) as connection:
            before_payload = connection.execute(
                "SELECT canonical_json FROM source_profile_revisions WHERE revision_id=?",
                (live_revision_id,),
            ).fetchone()[0]

        sentinel = object()
        with patch("rfi.admin.server.AdminConsole", return_value=sentinel):
            server = create_admin_server(self.state, port=0)
        self.assertIs(server, sentinel)
        profiles = SourceProfileRepository.open(
            self.state / "source-profiles", self.template
        )

        revision = profiles.get("meta")
        self.assertIsNotNone(revision)
        assert revision is not None
        self.assertEqual(revision.source_profile_revision_id, live_revision_id)
        self.assertEqual(revision.digest_schema_version, 1)
        self.assertEqual(database_path.read_bytes(), before_bytes)
        with self.repository._database.connect(read_only=True) as connection:
            after_payload = connection.execute(
                "SELECT canonical_json FROM source_profile_revisions WHERE revision_id=?",
                (live_revision_id,),
            ).fetchone()[0]
        self.assertEqual(after_payload, before_payload)

    def test_schemas_one_through_three_keep_exact_historical_projections(self) -> None:
        expected_ids: list[str] = []
        supersedes: str | None = None
        for schema in (1, 2, 3):
            payload = self._legacy_payload(schema, schema, supersedes)
            revision_id = str(payload["source_profile_revision_id"])
            self._insert_payload(payload)
            expected_ids.append(revision_id)
            supersedes = revision_id
        opened = SourceProfileRepository.open(
            self.state / "source-profiles", self.template
        )
        history = opened.history("seagate")
        self.assertEqual(
            [revision.source_profile_revision_id for revision in history], expected_ids
        )
        self.assertEqual(
            [revision.digest_schema_version for revision in history], [1, 2, 3]
        )
        for revision in history:
            candidate = next(
                item for item in revision.items if item.artifact_id == "engineering_blog"
            ).retrieval_candidates[0]
            self.assertEqual(
                (candidate.provider, candidate.discovery_hint_kind,
                 candidate.discovery_hint_value),
                ("", "", ""),
            )

    def test_legacy_payload_is_authenticated_before_current_defaults(self) -> None:
        payload = self._legacy_payload(1, 1, None)
        payload["operator_notes"] = "tampered"
        self._insert_payload(payload)
        with patch(
            "rfi.source_profiles.repository.RetrievalCandidate",
            side_effect=AssertionError("current defaults were synthesized before authentication"),
        ):
            with self.assertRaisesRegex(SourceProfileError, "digest mismatch"):
                self.repository.get("seagate")

    def test_mixed_legacy_and_current_history_authenticates_discovery_class(self) -> None:
        legacy_id, _ = self.insert_legacy()
        current = self.repository.publish(
            replace(self.draft("current"), items=(SourceProfileItem(
                "earnings_transcript", True, (RetrievalCandidate(
                    "discovery", 1, discovery_class="standard",
                    provider="stockanalysis", discovery_hint_kind="provider_identifier",
                    discovery_hint_value="STX",
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
        self.assertEqual(
            (candidate.provider, candidate.discovery_hint_kind,
             candidate.discovery_hint_value),
            ("stockanalysis", "provider_identifier", "STX"),
        )
        with self.repository._database.connect(read_only=True) as connection:
            payload = json.loads(connection.execute(
                "SELECT canonical_json FROM source_profile_revisions WHERE revision_id=?",
                (current.source_profile_revision_id,),
            ).fetchone()[0])
        self.assertEqual(payload["digest_schema_version"], 4)
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
                    "discovery", 1, discovery_class="standard",
                    provider="stockanalysis", discovery_hint_kind="provider_identifier",
                    discovery_hint_value="STX",
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
            item["retrieval_candidates"][0]["discovery_hint_value"] = "MSFT"
            connection.execute(
                "UPDATE source_profile_revisions SET canonical_json=? WHERE revision_id=?",
                (canonical_json(value), current.source_profile_revision_id),
            )
        with self.assertRaisesRegex(SourceProfileError, "digest mismatch"):
            self.repository.verify()


if __name__ == "__main__":
    unittest.main()
