"""TASK-040 identity catalog and deterministic SEC synthesis acceptance tests."""

from __future__ import annotations

import sqlite3
import tempfile
import unittest
from pathlib import Path

from rfi.firms import FirmDraft, FirmRepository
from rfi.pull.adapters import RetrievalAdapterRegistry
from rfi.pull.planning import PullPlanner
from rfi.source_profiles import (
    RetrievalCandidate, SourceProfileDraft, SourceProfileItem,
    SourceProfileRepository, SourceProfileService, load_canonical_template,
)
from rfi.storage.sqlite import DATABASE_NAME, RepositoryDatabase, SCHEMA_VERSION


class Task040Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        RepositoryDatabase.initialize(self.root)
        self.firms = FirmRepository.initialize(self.root / "firm-catalog")
        self.template = load_canonical_template()
        self.profiles = SourceProfileRepository.initialize(
            self.root / "source-profiles", self.template
        )

    def tearDown(self) -> None:
        self.temp.cleanup()

    @staticmethod
    def firm(firm_id: str) -> FirmDraft:
        return FirmDraft(firm_id, firm_id.title(), "2020-01-01")

    def test_catalog_is_deterministic_and_populates_only_matching_firms(self) -> None:
        self.firms.create(self.firm("alphabet"))
        identity = self.firms.external_identity("alphabet", "sec")
        self.assertEqual(identity.identifier, "0001652044")  # type: ignore[union-attr]
        self.assertEqual(identity.verification_status, "verified")  # type: ignore[union-attr]
        FirmRepository.open(self.root / "firm-catalog")
        with RepositoryDatabase.open(self.root).connect(read_only=True) as connection:
            self.assertEqual(connection.execute(
                "SELECT count(*) FROM firm_external_identities"
            ).fetchone()[0], 1)

    def test_synthesis_override_reset_and_non_sec_behavior(self) -> None:
        self.firms.create(self.firm("alphabet"))
        self.firms.create(self.firm("private-firm"))
        service = SourceProfileService(self.profiles, self.firms, self.template)
        base = service.detail("alphabet")
        ten_k = next(x for x in base.items if x.artifact_id == "sec_10k")
        self.assertEqual(ten_k.retrieval_candidates[0].locator, "CIK:0001652044")
        self.assertIn("sec_10k", base.synthesized_artifact_ids)
        override = RetrievalCandidate("identifier", 1, locator="CIK:0000002488")
        saved = self.profiles.publish(SourceProfileDraft("alphabet", (
            SourceProfileItem("sec_10k", True, (override,)),
        )), None)
        shown = service.detail("alphabet")
        item = next(x for x in shown.items if x.artifact_id == "sec_10k")
        self.assertEqual(item.retrieval_candidates, (override,))
        self.assertNotIn("sec_10k", shown.synthesized_artifact_ids)
        self.profiles.publish(SourceProfileDraft("alphabet", (
            SourceProfileItem("sec_10k", True),
        )), saved.source_profile_revision_id)
        reset = service.detail("alphabet")
        item = next(x for x in reset.items if x.artifact_id == "sec_10k")
        self.assertEqual(item.retrieval_candidates[0].locator, "CIK:0001652044")
        private = service.detail("private-firm")
        private_sec = next(x for x in private.items if x.artifact_id == "sec_10k")
        non_sec = next(x for x in base.items if x.artifact_id == "press_release")
        self.assertFalse(private_sec.retrieval_candidates)
        self.assertFalse(non_sec.retrieval_candidates)

    def test_planner_consumes_synthesis_without_persisting_runtime_urls(self) -> None:
        firm = self.firms.create(self.firm("alphabet"))
        profile = self.profiles.publish(SourceProfileDraft("alphabet", (
            SourceProfileItem("sec_10k", True),
        )), None)
        planner = PullPlanner(self.template, RetrievalAdapterRegistry(), self.firms)
        plan = planner.plan(firm, profile)
        candidate = plan.artifacts[0].candidates[0]
        self.assertEqual(candidate.locator, "CIK:0001652044")
        self.assertEqual(candidate.url, "")
        with RepositoryDatabase.open(self.root).connect(read_only=True) as connection:
            payload = connection.execute(
                "SELECT canonical_json FROM source_profile_revisions"
            ).fetchone()[0]
        self.assertNotIn("CIK:0001652044", payload)
        self.assertNotIn("sec.gov", payload)

    def test_version_nine_repository_migrates(self) -> None:
        path = self.root / DATABASE_NAME
        with sqlite3.connect(path) as connection:
            connection.execute("DROP TABLE firm_external_identities")
            connection.execute("UPDATE schema_metadata SET schema_version=9")
        result = RepositoryDatabase.open(self.root).validate()
        self.assertEqual(result["schema_version"], SCHEMA_VERSION)


if __name__ == "__main__":
    unittest.main()
