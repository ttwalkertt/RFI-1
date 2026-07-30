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
    SecForm10KAdapter,
    SecForm10QAdapter,
    SecForm8KAdapter,
    SecHttpResponse,
    SecProviderClient,
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
from rfi.pull import (
    ArtifactOutcome,
    PullRequest,
    PullRunRepository,
    PullStatus,
    PullWorkflow,
    RetrievalAdapterCapability,
    RetrievalAdapterRegistration,
    RetrievalAdapterRegistry,
)
from rfi.pull.planning import PullPlanner
from rfi.sec import SecApplicability, SecRepository, SecSourceKnowledge
from rfi.source_profiles import (
    SourceProfileDraft,
    SourceProfileItem,
    SourceProfileRepository,
    SourceProfileService,
    load_canonical_template,
)
from rfi.source_profiles.contracts import RetrievalCandidate, SourceProfileRevision
from rfi.storage import RepositoryDatabase

ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / "docs/microsoft.firm-config.example.json"


class MicrosoftSecTransport:
    """Offline production-provider replacement for the managed Microsoft pull path."""

    def __init__(self) -> None:
        self.requests: list[str] = []
        self.time = 0.0
        self.submissions = json.dumps(
            {
                "cik": "0000789019",
                "entityType": "operating",
                "name": "MICROSOFT CORP",
                "filings": {
                    "recent": {
                        "accessionNumber": [
                            "0000789019-26-000003",
                            "0000789019-26-000002",
                            "0000789019-26-000001",
                        ],
                        "filingDate": ["2026-07-03", "2026-07-02", "2026-07-01"],
                        "reportDate": ["2026-07-03", "2026-06-30", "2026-06-30"],
                        "acceptanceDateTime": [
                            "2026-07-03T12:00:00Z",
                            "2026-07-02T12:00:00Z",
                            "2026-07-01T12:00:00Z",
                        ],
                        "form": ["8-K", "10-Q", "10-K"],
                        "primaryDocument": ["msft-8k.htm", "msft-10q.htm", "msft-10k.htm"],
                    },
                    "files": [],
                },
            },
            separators=(",", ":"),
        ).encode()

    def monotonic(self) -> float:
        return self.time

    def sleep(self, seconds: float) -> None:
        self.time += seconds

    def request(
        self,
        url: str,
        headers: dict[str, str],
        timeout_seconds: float,
        maximum_bytes: int,
    ) -> SecHttpResponse:
        del timeout_seconds, maximum_bytes
        self.requests.append(url)
        self.assert_runtime_identity(headers)
        if "/submissions/" in url:
            content = self.submissions
            media_type = "application/json"
        else:
            content = f"<html><body>{url}</body></html>".encode()
            media_type = "text/html"
        return SecHttpResponse(
            200,
            {"content-type": media_type, "content-length": str(len(content))},
            content,
            url,
        )

    @staticmethod
    def assert_runtime_identity(headers: dict[str, str]) -> None:
        if not headers.get("User-Agent"):
            raise AssertionError("SEC fixture request omitted runtime identity")


def task041_clock() -> str:
    return "2026-07-27T12:00:00Z"


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
            {"sec_10k", "sec_10q", "sec_8k", "earnings_transcript"},
        )
        transcript = next(
            item for item in view.items if item.artifact_id == "earnings_transcript"
        )
        self.assertEqual(transcript.retrieval_candidates[0].mode, "listing_page")
        self.assertIn(
            "www.microsoft.com", transcript.retrieval_candidates[0].preferred_domains
        )
        ten_k = next(item for item in view.items if item.artifact_id == "sec_10k")
        self.assertEqual(ten_k.retrieval_candidates[0].locator, "CIK:0000789019")
        self.assertEqual(ten_k.retrieval_candidates[0].parser_hint, "")

    def test_display_name_is_presentation_only_and_may_be_an_explicit_alias(self) -> None:
        value = self.value()
        value["firm"]["display_name"] = "Presentation Label"  # type: ignore[index]
        value["firm"]["aliases"] = ["Presentation Label"]  # type: ignore[index]
        self.write(value)

        initialize(self.state)
        firms = FirmRepository.open(self.state / "firm-catalog")
        self.assertEqual(firms.get("microsoft").canonical_name, "Presentation Label")
        self.assertEqual(firms.lookup("Presentation Label")[0].firm_id, "microsoft")

        display_only = self.value()
        display_only["config_id"] = "display-only"
        display_only["firm"]["id"] = "display-only"  # type: ignore[index]
        display_only["firm"]["display_name"] = "Unsearchable Presentation"  # type: ignore[index]
        display_only["firm"]["legal_name"] = "Distinct Legal Corporation"  # type: ignore[index]
        display_only["firm"]["aliases"] = []  # type: ignore[index]
        display_only["firm"]["identifiers"] = []  # type: ignore[index]
        display_only["firm"]["domains"] = ["distinct.example"]  # type: ignore[index]
        display_only["sources"]["sec"] = None  # type: ignore[index]
        self.write(display_only, "display-only.firm-config.json")

        # Reload the complete authoritative set. The display label is still rendered,
        # but it does not independently confer lookup identity.
        prepare_firm_configuration(self.state)
        firms = FirmRepository.open(self.state / "firm-catalog")
        self.assertEqual(firms.get("display-only").canonical_name, "Unsearchable Presentation")
        self.assertEqual(firms.lookup("Unsearchable Presentation"), ())

    def test_microsoft_sec_candidates_plan_and_execute_existing_numbered_form_adapters(
        self,
    ) -> None:
        self.write(self.value())
        initialize(self.state)
        firms = FirmRepository.open(self.state / "firm-catalog")
        template = load_canonical_template()
        profiles = SourceProfileRepository.open(self.state / "source-profiles", template)
        profile = profiles.get("microsoft")
        identity = firms.external_identity("microsoft", "sec")
        self.assertEqual(identity.identifier, "0000789019")  # type: ignore[union-attr]

        transport = MicrosoftSecTransport()
        provider = SecProviderClient(
            lambda: "RFI-1-TASK-041 fixture@example.invalid",
            transport,
            minimum_request_interval_seconds=0.1,
            monotonic=transport.monotonic,
            sleeper=transport.sleep,
        )
        numbered_forms = (
            SecForm10KAdapter(provider, task041_clock),
            SecForm10QAdapter(provider, task041_clock),
            SecForm8KAdapter(provider, task041_clock),
        )
        adapters = RetrievalAdapterRegistry(
            tuple(
                RetrievalAdapterRegistration(
                    RetrievalAdapterCapability(
                        adapter.adapter_id,
                        adapter.artifact_ids,
                        adapter.retrieval_modes,
                    ),
                    adapter,
                )
                for adapter in numbered_forms
            )
        )
        plan = PullPlanner(template, adapters, firms).plan(firms.get("microsoft"), profile)
        expected_adapters = {
            "sec_10k": "sec-form-10k",
            "sec_10q": "sec-form-10q",
            "sec_8k": "sec-form-8k",
        }
        for artifact_id, adapter_id in expected_adapters.items():
            artifact = next(item for item in plan.artifacts if item.artifact_id == artifact_id)
            self.assertEqual(len(artifact.runnable_candidates), 1)
            candidate = artifact.runnable_candidates[0]
            self.assertEqual(candidate.locator, "CIK:0000789019")
            self.assertEqual((candidate.url, candidate.parser_hint), ("", ""))
            self.assertEqual(
                adapters.select(artifact_id, candidate).capability.adapter_id,
                adapter_id,
            )

        with RepositoryDatabase.open(self.state).connect(read_only=True) as connection:
            sec_sources_before = connection.execute(
                "SELECT * FROM sec_sources ORDER BY firm_id"
            ).fetchall()
        workflow = PullWorkflow(
            firms,
            profiles,
            template,
            AcquisitionRepository(self.state / "acquisition"),
            adapters,
            PullRunRepository(self.state / "pull-workflows"),
            task041_clock,
            lambda: "task041microsoft",
        )
        result = workflow.run(PullRequest(("microsoft",)))
        self.assertEqual(result.status, PullStatus.COMPLETED, result)
        durable_plan = workflow.results(result.run_id)["plan"][0]["artifacts"]
        outcomes = {item.artifact_id: item for item in result.firms[0].artifacts}
        for artifact_id, adapter_id in expected_adapters.items():
            self.assertEqual(outcomes[artifact_id].outcome, ArtifactOutcome.SUCCESS)
            self.assertEqual(outcomes[artifact_id].attempts[0].adapter_id, adapter_id)
            planned = next(
                item for item in durable_plan if item["artifact_id"] == artifact_id
            )
            self.assertEqual(
                planned["adapter_selections"],
                [{"priority": 1, "adapter_id": adapter_id}],
            )
        self.assertTrue(
            any("/submissions/CIK0000789019.json" in url for url in transport.requests)
        )
        with RepositoryDatabase.open(self.state).connect(read_only=True) as connection:
            self.assertEqual(
                connection.execute("SELECT * FROM sec_sources ORDER BY firm_id").fetchall(),
                sec_sources_before,
            )

    def test_blank_deterministic_candidate_is_not_runnable(self) -> None:
        self.write(self.value())
        initialize(self.state)
        firms = FirmRepository.open(self.state / "firm-catalog")
        template = load_canonical_template()
        transport = MicrosoftSecTransport()
        provider = SecProviderClient(
            lambda: "RFI-1-TASK-041 fixture@example.invalid", transport
        )
        adapter = SecForm10KAdapter(provider, task041_clock)
        adapters = RetrievalAdapterRegistry(
            (
                RetrievalAdapterRegistration(
                    RetrievalAdapterCapability(
                        adapter.adapter_id, adapter.artifact_ids, adapter.retrieval_modes
                    ),
                    adapter,
                ),
            )
        )
        profile = SourceProfileRevision(
            "microsoft",
            "invalid-blank-candidate-fixture",
            1,
            (SourceProfileItem("sec_10k", True, (RetrievalCandidate("identifier", 1),)),),
            "",
            task041_clock(),
            task041_clock(),
            None,
        )
        artifact = PullPlanner(template, adapters, firms).plan(
            firms.get("microsoft"), profile
        ).artifacts[0]
        self.assertEqual(artifact.runnable_candidates, ())
        self.assertEqual(
            artifact.attemptability_diagnostic,
            "Retrieval candidate lacks required configuration.",
        )

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
        value = self.value()
        del value["sources"]["sec"]["cik"]  # type: ignore[index]
        cases.append(("missing-cik", "missing-cik.firm-config.json", value, "'cik' is a required"))
        value = self.value()
        value["sources"]["sec"]["cik"] = "789019"  # type: ignore[index]
        cases.append(("malformed-cik", "malformed-cik.firm-config.json", value, "does not match"))
        value = self.value()
        value["sources"]["sec"]["cik"] = "0000000000"  # type: ignore[index]
        for identifier in value["firm"]["identifiers"]:  # type: ignore[index]
            if identifier["kind"] == "cik":
                identifier["value"] = "0000000000"
        cases.append(
            (
                "zero-cik",
                "zero-cik.firm-config.json",
                value,
                "enabled SEC artifact requires a verified 10-digit CIK",
            )
        )
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
        microsoft = firms.get("microsoft")
        self.assertEqual((microsoft.firm_id, microsoft.canonical_name), ("microsoft", "Microsoft"))
        self.assertEqual(len(firms.history("microsoft")), 3)
        profile = profiles.get("microsoft")
        self.assertEqual(profile.firm_id, "microsoft")  # type: ignore[union-attr]
        self.assertEqual(len(profiles.history("microsoft")), 3)
        shown = SourceProfileService(profiles, firms, template).detail("microsoft")
        for artifact_id in ("sec_10k", "sec_10q", "sec_8k"):
            item = next(value for value in shown.items if value.artifact_id == artifact_id)
            self.assertEqual(item.retrieval_candidates[0].locator, "CIK:0000789019")

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
