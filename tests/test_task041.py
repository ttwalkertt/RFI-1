"""TASK-041 externally owned firm-configuration materialization acceptance tests."""

from __future__ import annotations

import hashlib
import json
import tempfile
import threading
import unittest
from dataclasses import replace
from http.client import HTTPConnection
from pathlib import Path

from rfi.acquisition import (
    AcquisitionRepository,
    CandidateDocument,
    DiscoveryProvenance,
    RetrievalResult,
    SourceProfile,
)
from rfi.admin import create_admin_server
from rfi.cli import initialize
from rfi.cli import main as cli_main
from rfi.firm_configuration import (
    FirmConfigurationError,
    load_firm_configurations,
    materialize_firm_configurations,
    prepare_firm_configuration,
)
from rfi.firms import FirmDraft, FirmRepository
from rfi.sec import SecApplicability, SecRepository, SecSourceKnowledge
from rfi.source_profiles import (
    SourceProfileDraft,
    SourceProfileItem,
    SourceProfileRepository,
    SourceProfileService,
    load_canonical_template,
)
from rfi.storage import RepositoryDatabase

ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / "docs/microsoft.firm-config.example.json"


class FirmConfigurationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.state = self.root / "state"

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def initialize_empty(self) -> RepositoryDatabase:
        RepositoryDatabase.initialize(self.state)
        FirmRepository.initialize(self.state / "firm-catalog")
        SourceProfileRepository.initialize(
            self.state / "source-profiles", load_canonical_template()
        )
        return RepositoryDatabase.open(self.state)

    def value(self) -> dict[str, object]:
        return json.loads(EXAMPLE.read_text(encoding="utf-8"))

    def write(self, value: object, name: str = "microsoft.firm-config.json") -> Path:
        directory = self.state / "firm-config"
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / name
        path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")
        return path

    def test_valid_microsoft_loads_comments_identity_profile_and_read_projection(self) -> None:
        self.write(self.value())
        initialize(self.state)
        firms = FirmRepository.open(self.state / "firm-catalog")
        microsoft = firms.get("microsoft")
        self.assertEqual(microsoft.subtitle, "Cloud, software, and platform operator")
        self.assertEqual(microsoft.relevance, 90)
        self.assertEqual(
            microsoft.notes,
            "Authoritative firm configuration comments remain uninterpreted text.",
        )
        identity = firms.external_identity("microsoft", "sec")
        self.assertEqual(identity.identifier, "0000789019")  # type: ignore[union-attr]
        authority = firms.configuration_authority("microsoft")
        self.assertEqual(authority["configuration"], self.value())  # type: ignore[index]
        template = load_canonical_template()
        profiles = SourceProfileRepository.open(self.state / "source-profiles", template)
        view = SourceProfileService(profiles, firms, template).detail("microsoft")
        self.assertEqual(
            {item.artifact_id for item in view.items if item.enabled},
            {"sec_10k", "sec_10q", "sec_8k"},
        )
        ten_k = next(item for item in view.items if item.artifact_id == "sec_10k")
        self.assertEqual(ten_k.retrieval_candidates[0].locator, "CIK:0000789019")

    def test_malformed_schema_priority_unknown_and_subtitle_fail_before_mutation(self) -> None:
        database = self.initialize_empty()
        cases: list[tuple[str, str, object, str]] = []
        cases.append(("malformed", "bad.firm-config.json", "{", "malformed JSON"))
        value = self.value()
        value["firm"]["priority"] = 101  # type: ignore[index]
        cases.append(("priority", "priority.firm-config.json", value, "maximum of 100"))
        value = self.value()
        value["firm"]["unknown"] = True  # type: ignore[index]
        cases.append(("unknown", "unknown.firm-config.json", value, "Additional properties"))
        value = self.value()
        del value["firm"]["subtitle"]  # type: ignore[index]
        cases.append(("subtitle", "subtitle.firm-config.json", value, "'subtitle' is a required"))
        for label, name, value, expected in cases:
            with self.subTest(label=label):
                directory = self.state / "firm-config"
                for old in directory.glob("*") if directory.exists() else ():
                    old.unlink()
                path = directory / name
                directory.mkdir(parents=True, exist_ok=True)
                if isinstance(value, str):
                    path.write_text(value, encoding="utf-8")
                else:
                    path.write_text(json.dumps(value), encoding="utf-8")
                before = database.revision()
                with self.assertRaisesRegex(FirmConfigurationError, expected):
                    prepare_firm_configuration(self.state)
                self.assertEqual(database.revision(), before)
                with database.connect(read_only=True) as connection:
                    self.assertEqual(connection.execute(
                        "SELECT count(*) FROM firms"
                    ).fetchone()[0], 0)

    def test_duplicate_firm_and_sec_identity_fail_complete_set_before_mutation(self) -> None:
        database = self.initialize_empty()
        first = self.value()
        second = self.value()
        self.write(first)
        self.write(second, "second.firm-config.json")
        before = database.revision()
        with self.assertRaisesRegex(FirmConfigurationError, "duplicate stable identity"):
            prepare_firm_configuration(self.state)
        self.assertEqual(database.revision(), before)

        (self.state / "firm-config" / "second.firm-config.json").unlink()
        second = self.value()
        second["config_id"] = "other-firm"
        second["firm"]["id"] = "other-firm"  # type: ignore[index]
        second["firm"]["display_name"] = "Other Firm"  # type: ignore[index]
        second["firm"]["legal_name"] = "Other Firm Inc."  # type: ignore[index]
        second["firm"]["aliases"] = []  # type: ignore[index]
        second["firm"]["domains"] = ["other.example"]  # type: ignore[index]
        second["firm"]["identifiers"] = [  # type: ignore[index]
            {"kind": "cik", "value": "0000789019", "market": "SEC"}
        ]
        self.write(second, "other.firm-config.json")
        with self.assertRaisesRegex(FirmConfigurationError, "duplicate external SEC identity"):
            prepare_firm_configuration(self.state)
        self.assertEqual(database.revision(), before)

        second["sources"]["sec"]["cik"] = "0000000001"  # type: ignore[index]
        second["firm"]["identifiers"] = [  # type: ignore[index]
            {"kind": "cik", "value": "0000000001", "market": "SEC"},
            {"kind": "ticker", "value": "MSFT", "market": "NASDAQ"},
        ]
        self.write(second, "other.firm-config.json")
        with self.assertRaisesRegex(FirmConfigurationError, "identifiers/1: conflicts"):
            prepare_firm_configuration(self.state)
        self.assertEqual(database.revision(), before)

    def test_transaction_failure_rolls_back_complete_materialization(self) -> None:
        database = self.initialize_empty()
        self.write(self.value())
        configurations = load_firm_configurations(self.state, database)
        before = database.revision()
        with self.assertRaisesRegex(FirmConfigurationError, "injected"):
            materialize_firm_configurations(
                self.state, database, configurations, fail_after_firms=1
            )
        self.assertEqual(database.revision(), before)
        with database.connect(read_only=True) as connection:
            for table in (
                "firms", "firm_revisions", "firm_external_identities",
                "source_profiles", "source_profile_revisions", "firm_config_authorities",
            ):
                self.assertEqual(connection.execute(
                    f"SELECT count(*) FROM {table}"
                ).fetchone()[0], 0)

    def test_malformed_file_refuses_cli_startup_and_missing_managed_file_stays_owned(self) -> None:
        directory = self.state / "firm-config"
        directory.mkdir(parents=True)
        (directory / "bad.firm-config.json").write_text("{", encoding="utf-8")
        self.assertEqual(cli_main(("init", "--state", str(self.state))), 2)
        with RepositoryDatabase.open(self.state).connect(read_only=True) as connection:
            self.assertEqual(connection.execute("SELECT count(*) FROM firms").fetchone()[0], 0)

        (directory / "bad.firm-config.json").unlink()
        self.write(self.value())
        self.assertEqual(cli_main(("init", "--state", str(self.state))), 0)
        (directory / "microsoft.firm-config.json").unlink()
        before = RepositoryDatabase.open(self.state).revision()
        with self.assertRaisesRegex(FirmConfigurationError, "file is missing"):
            prepare_firm_configuration(self.state)
        self.assertEqual(RepositoryDatabase.open(self.state).revision(), before)

    def test_repeated_startup_replaces_editor_projection_and_preserves_history(self) -> None:
        self.initialize_empty()
        firms = FirmRepository.open(self.state / "firm-catalog")
        firms.create(FirmDraft(
            "microsoft", "Editor Microsoft", "2019-01-01", subtitle="Editor subtitle"
        ))
        template = load_canonical_template()
        profiles = SourceProfileRepository.open(self.state / "source-profiles", template)
        profiles.publish(SourceProfileDraft(
            "microsoft", (SourceProfileItem("annual_report", True),), "editor profile"
        ), None)
        self.write(self.value())
        prepare_firm_configuration(self.state)
        self.assertEqual(firms.get("microsoft").canonical_name, "Microsoft")
        self.assertEqual(len(firms.history("microsoft")), 2)
        prepare_firm_configuration(self.state)
        self.assertEqual(firms.get("microsoft").canonical_name, "Microsoft")
        self.assertEqual(len(firms.history("microsoft")), 3)
        self.assertEqual(len(profiles.history("microsoft")), 3)

    def test_evidence_artifact_provenance_and_sec_workflow_knowledge_are_preserved(self) -> None:
        self.initialize_empty()
        firms = FirmRepository.open(self.state / "firm-catalog")
        firms.create(FirmDraft("microsoft", "Old Microsoft", "2019-01-01"))
        acquisition = AcquisitionRepository(self.state / "acquisition")
        source = SourceProfile(
            "source-task041",
            "TASK-041 preservation fixture",
            True,
            "fixture-reader",
            policy={
                "firm_id": "microsoft",
                "artifact_id": "sec_10k",
                "source_profile_revision_id": "editor-profile",
                "retrieval_adapter_id": "fixture-task041",
            },
        )
        acquisition.register_source(source)
        candidate = CandidateDocument(
            "candidate-task041", "source-task041", "document-task041",
            DiscoveryProvenance(
                "2026-07-27T00:00:00Z", "fixture-reader",
                {"accession": "0000789019-26-000001"},
                ("https://example.test/filing",),
            ),
        )
        content = b"TASK-041 immutable artifact bytes"
        acquisition.record_success(
            "attempt-task041", candidate,
            RetrievalResult(content, "text/plain", "2026-07-27T00:01:00Z", "fixture-reader"),
        )
        sec = SecRepository(self.state)
        knowledge = SecSourceKnowledge(
            "microsoft", SecApplicability.DIRECT, "Runtime Microsoft Issuer", "789019",
            "runtime-regime", "verified", "2026-07-27T00:02:00+00:00",
        )
        sec.persist_source(knowledge, None)
        before_history = acquisition.history()
        before_observations = acquisition.observations()
        before_metadata = acquisition.artifact_metadata()
        before_digest = hashlib.sha256(content).hexdigest()
        self.write(self.value())
        prepare_firm_configuration(self.state)
        self.assertEqual(acquisition.history(), before_history)
        self.assertEqual(acquisition.observations(), before_observations)
        self.assertEqual(acquisition.artifact_metadata(), before_metadata)
        self.assertEqual(hashlib.sha256(acquisition.read_artifact(
            f"artifact-{before_digest}"
        )).hexdigest(), before_digest)
        self.assertEqual(sec.source("microsoft"), knowledge)

    def test_repository_and_api_writes_are_rejected_while_reads_remain_available(self) -> None:
        self.write(self.value())
        initialize(self.state)
        firms = FirmRepository.open(self.state / "firm-catalog")
        current = firms.get("microsoft")
        with self.assertRaisesRegex(Exception, "externally managed"):
            firms.revise(
                "microsoft", replace(firms.to_draft(current), canonical_name="Conflict"),
                current.revision_id,
            )
        profiles = SourceProfileRepository.open(
            self.state / "source-profiles", load_canonical_template()
        )
        current_profile = profiles.get("microsoft")
        assert current_profile is not None
        with self.assertRaisesRegex(Exception, "externally managed"):
            profiles.publish(
                profiles.to_draft(current_profile),
                current_profile.source_profile_revision_id,
            )

        server = create_admin_server(self.state, port=0)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            connection = HTTPConnection(*server.server_address, timeout=5)
            connection.request("GET", "/api/firms/microsoft")
            response = connection.getresponse()
            detail = json.loads(response.read())
            self.assertEqual(response.status, 200)
            self.assertEqual(detail["configuration_authority"]["authority"], "external-json")
            connection.request(
                "PUT", "/api/firms/microsoft",
                json.dumps({
                    "expected_revision_id": detail["revision_id"],
                    "firm": {**detail, "canonical_name": "Conflict"},
                }),
                {"Content-Type": "application/json"},
            )
            response = connection.getresponse()
            body = json.loads(response.read())
            self.assertEqual(response.status, 400)
            self.assertIn("externally managed", body["error"])
            connection.request("GET", "/api/firms/microsoft/source-profile")
            response = connection.getresponse()
            profile = json.loads(response.read())
            self.assertEqual(response.status, 200)
            self.assertEqual(profile["configuration_authority"]["authority"], "external-json")
            connection.request(
                "PUT", "/api/firms/microsoft/source-profile",
                json.dumps({
                    "expected_revision_id": profile["source_profile_revision_id"],
                    "profile": {
                        "items": profile["items"],
                        "operator_notes": profile["operator_notes"],
                    },
                }),
                {"Content-Type": "application/json"},
            )
            response = connection.getresponse()
            body = json.loads(response.read())
            self.assertEqual(response.status, 400)
            self.assertIn("externally managed", body["error"])
            connection.close()
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)


if __name__ == "__main__":
    unittest.main()
