"""Offline acceptance tests for additional artifact-specific SEC form adapters."""

from __future__ import annotations

import inspect
import json
import socket
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

from rfi.acquisition import (
    AcquisitionRepository,
    AdapterFailure,
    DirectUrlAdapter,
    SecForm10QAdapter,
    SecForm20FAdapter,
    SecForm6KAdapter,
    SecForm8KAdapter,
    SecHttpResponse,
)
from rfi.acquisition.contracts import SourceProfile
from rfi.artifacts import ArtifactQuery, ArtifactQueryService
from rfi.firms import FirmRepository, sample_firms
from rfi.pull import (
    ArtifactOutcome,
    PullRequest,
    PullRunRepository,
    PullStatus,
    PullWorkflow,
    RetrievalAdapterCapability,
    RetrievalAdapterError,
    RetrievalAdapterRegistration,
    RetrievalAdapterRegistry,
    create_pull_workflow,
)
from rfi.source_profiles import (
    RetrievalCandidate,
    SourceProfileDraft,
    SourceProfileItem,
    SourceProfileRepository,
    load_canonical_template,
)

from tests.test_task016 import SecFixtureTransport, fixed_clock, provider

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "fixtures/sec-numbered-forms"
POLICIES = (
    (SecForm10QAdapter, "sec_10q", "10-Q", "no_eligible_form_10q", "0001137789-26-000101"),
    (SecForm8KAdapter, "sec_8k", "8-K", "no_eligible_form_8k", "0001137789-26-000201"),
    (SecForm20FAdapter, "sec_20f", "20-F", "no_eligible_form_20f", "0001137789-26-000301"),
    (SecForm6KAdapter, "sec_6k", "6-K", "no_eligible_form_6k", "0001137789-26-000401"),
)


class NumberedFormTransport(SecFixtureTransport):
    """Return distinct exact primary bytes selected by the requested archive identity."""

    def request(
        self,
        url: str,
        headers: dict[str, str],
        timeout_seconds: float,
        maximum_bytes: int,
    ) -> SecHttpResponse:
        response = super().request(url, headers, timeout_seconds, maximum_bytes)
        if "/submissions/" in url:
            return response
        filename = url.rsplit("/", 1)[-1]
        content = (FIXTURES / filename).read_bytes()
        return SecHttpResponse(
            200,
            {"content-type": "text/html", "content-length": str(len(content))},
            content,
            url,
        )


def fixture_provider():
    """Build the real provider client over bounded TASK-022 bytes."""
    transport = NumberedFormTransport(
        (FIXTURES / "CIK0001137789.json").read_bytes(),
        (FIXTURES / "primary-document.htm").read_bytes(),
    )
    return provider(transport)


def source(adapter_type: type, artifact_id: str) -> SourceProfile:
    return SourceProfile(
        f"source-task022-{artifact_id}",
        f"TASK-022 {artifact_id}",
        True,
        adapter_type.mechanism,
        {"mode": "identifier", "locator": "CIK:0001137789"},
        {
            "firm_id": "seagate",
            "artifact_id": artifact_id,
            "source_profile_revision_id": "fixture-task022",
            "retrieval_adapter_id": adapter_type.adapter_id,
        },
    )


def adapter_registry(adapters: tuple[object, ...]) -> RetrievalAdapterRegistry:
    registrations = [
        RetrievalAdapterRegistration(
            RetrievalAdapterCapability("direct-url", (), ("direct_url",)),
            DirectUrlAdapter(fixed_clock),
        )
    ]
    registrations.extend(
        RetrievalAdapterRegistration(
            RetrievalAdapterCapability(
                adapter.adapter_id, adapter.artifact_ids, adapter.retrieval_modes
            ),
            adapter,
        )
        for adapter in adapters
    )
    return RetrievalAdapterRegistry(tuple(registrations))


class NumberedFormPolicyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.client, self.transport, _timing = fixture_provider()

    def test_capabilities_are_exact_and_registration_order_independent(self) -> None:
        adapters = tuple(item[0](self.client, fixed_clock) for item in POLICIES)
        forward = adapter_registry(adapters)
        reverse = adapter_registry(tuple(reversed(adapters)))
        candidate = RetrievalCandidate("identifier", 1, locator="CIK:0001137789")
        for adapter_type, artifact_id, _form, _code, _accession in POLICIES:
            with self.subTest(artifact_id=artifact_id):
                selected = forward.select(artifact_id, candidate)
                self.assertEqual(selected.capability.adapter_id, adapter_type.adapter_id)
                self.assertEqual(
                    selected.capability.adapter_id,
                    reverse.select(artifact_id, candidate).capability.adapter_id,
                )
                self.assertEqual(len(forward.compatible(artifact_id, candidate)), 1)
        with self.assertRaisesRegex(RetrievalAdapterError, "no compatible"):
            forward.select("proxy_statement", candidate)

    def test_exact_form_amendment_reordering_tie_break_and_period_provenance(self) -> None:
        filings = self.client.filings("1137789")
        for adapter_type, artifact_id, form, _code, accession in POLICIES:
            with self.subTest(form=form):
                adapter = adapter_type(self.client, fixed_clock)
                selected, counts = adapter.select_filing(filings)
                self.assertEqual(selected.accession_number, accession)
                self.assertEqual(selected.form, form)
                self.assertEqual(counts["amendments_excluded"], 1)
                reversed_selected, _ = adapter.select_filing(tuple(reversed(filings)))
                self.assertEqual(reversed_selected, selected)

                lower = replace(selected, accession_number="0001137789-26-900001")
                higher = replace(selected, accession_number="0001137789-26-900002")
                tied, _ = adapter.select_filing((lower, higher))
                self.assertEqual(tied.accession_number, higher.accession_number)

                page = adapter.discover(source(adapter_type, artifact_id), None)
                candidate = page.candidates[0]
                metadata = candidate.provenance.metadata
                self.assertEqual(metadata["form_type"], form)
                self.assertEqual(metadata["period_of_report"], selected.report_date)
                self.assertEqual(metadata["artifact_role"], "primary_filing_document")
                self.assertTrue(str(metadata["archive_path"]).endswith(selected.primary_document))
                result = adapter.retrieve(source(adapter_type, artifact_id), candidate)
                self.assertIn(selected.primary_document, str(result.diagnostics["archive_url"]))
                self.assertEqual(result.provider_identifiers["sec_accession"], accession)

    def test_form_specific_no_match_missing_identity_conflict_and_malformed_ordering(self) -> None:
        filings = self.client.filings("1137789")
        for adapter_type, _artifact_id, form, code, _accession in POLICIES:
            adapter = adapter_type(self.client, fixed_clock)
            eligible = next(item for item in filings if item.form == form)
            with self.subTest(form=form):
                with self.assertRaises(AdapterFailure) as no_match:
                    adapter.select_filing((replace(eligible, form=f"{form}/A"),))
                self.assertEqual(no_match.exception.code, code)
                with self.assertRaises(AdapterFailure) as missing:
                    adapter.select_filing((replace(eligible, primary_document=""),))
                self.assertEqual(missing.exception.code, "missing_filing_identity")
                with self.assertRaises(AdapterFailure) as ambiguous:
                    adapter.select_filing(
                        (eligible, replace(eligible, primary_document="conflict.htm"))
                    )
                self.assertEqual(ambiguous.exception.code, "ambiguous_filing_result")
                with self.assertRaises(AdapterFailure) as malformed:
                    adapter.select_filing((replace(eligible, filing_date="bad-date"),))
                self.assertEqual(malformed.exception.code, "malformed_provider_response")

    def test_fixture_is_columnar_and_primary_document_is_not_an_exhibit(self) -> None:
        value = json.loads((FIXTURES / "CIK0001137789.json").read_text())
        recent = value["filings"]["recent"]
        self.assertEqual(len({len(items) for items in recent.values()}), 1)
        self.assertFalse(any("exhibit" in item.casefold() for item in recent["primaryDocument"]))

    def test_provider_accepts_authoritative_third_party_accession_prefix(self) -> None:
        document = self.client.primary_document(
            "1137789", "0001193125-26-268170", "current-8k.htm"
        )
        self.assertTrue(document.archive_url.endswith("/current-8k.htm"))
        self.assertIn("/data/1137789/000119312526268170/", document.archive_url)


class NumberedFormVerticalSliceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.template = load_canonical_template()
        self.firms = FirmRepository.initialize(self.root / "firm-catalog")
        self.firms.create(sample_firms()[0])
        self.profiles = SourceProfileRepository.initialize(
            self.root / "source-profiles", self.template
        )
        self.acquisition = AcquisitionRepository(self.root / "acquisition")
        client, self.transport, _timing = fixture_provider()
        self.adapters = tuple(item[0](client, fixed_clock) for item in POLICIES)
        self.workflow = PullWorkflow(
            self.firms,
            self.profiles,
            self.template,
            self.acquisition,
            adapter_registry(self.adapters),
            PullRunRepository(self.root / "pull-workflows"),
            fixed_clock,
            iter((f"task022{index}" for index in range(100))).__next__,
        )
        enabled = {item[1]: item[0] for item in POLICIES}
        items = tuple(
            SourceProfileItem(
                artifact.artifact_id,
                artifact.artifact_id in enabled,
                (
                    RetrievalCandidate("identifier", 1, locator="CIK:0001137789"),
                )
                if artifact.artifact_id in enabled
                else (),
            )
            for artifact in self.template.artifacts
        )
        self.profiles.publish(SourceProfileDraft("seagate", items), None)

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def test_pull_rerun_query_restart_network_block_and_integrity(self) -> None:
        readiness = self.workflow.configured_firms()[0]
        self.assertEqual((readiness.enabled_artifacts, readiness.runnable_artifacts), (4, 4))
        capabilities = self.workflow.adapter_capabilities()
        for adapter_type, artifact_id, _form, _code, _accession in POLICIES:
            self.assertTrue(
                any(
                    item["adapter_id"] == adapter_type.adapter_id
                    and item["artifact_ids"] == [artifact_id]
                    for item in capabilities
                )
            )

        first = self.workflow.run(PullRequest(("seagate",)))
        self.assertEqual(first.status, PullStatus.COMPLETED)
        self.assertEqual(
            {item.artifact_id: item.outcome for item in first.firms[0].artifacts},
            {item[1]: ArtifactOutcome.SUCCESS for item in POLICIES},
        )
        self.assertEqual(len(self.acquisition.artifact_metadata()), 4)
        self.assertEqual(len(self.acquisition.observations()), 4)

        service = ArtifactQueryService(self.acquisition, self.firms, self.template)
        summaries = service.query(ArtifactQuery(limit=10)).items
        self.assertEqual(
            {item.canonical_artifact_id for item in summaries},
            {item[1] for item in POLICIES},
        )
        self.assertEqual(
            {
                item["canonical_artifact_id"]
                for item in service.canonical_types(
                    "seagate", "regulatory_financial"
                )
            },
            {item[1] for item in POLICIES},
        )
        for summary in summaries:
            detail = service.detail(summary.document_id)
            self.assertEqual(
                detail.observation.metadata["artifact_role"],
                "primary_filing_document",
            )
            primary = str(detail.observation.metadata["primary_document"])
            self.assertEqual(
                service.content(summary.document_id).content,
                (FIXTURES / primary).read_bytes(),
            )

        repeat = self.workflow.run(PullRequest(("seagate",)))
        self.assertEqual(repeat.status, PullStatus.COMPLETED)
        self.assertEqual(
            {item.artifact_id: item.outcome for item in repeat.firms[0].artifacts},
            {item[1]: ArtifactOutcome.NO_CHANGE for item in POLICIES},
        )
        self.assertEqual(len(self.acquisition.artifact_metadata()), 4)
        # The current latest-only pull checkpoint returns no_change before retrieval;
        # therefore an equivalent rerun creates no additional observation.
        self.assertEqual(len(self.acquisition.observations()), 4)
        content_files = [
            path
            for path in self.acquisition.content_root.rglob("*")
            if path.is_file()
        ]
        self.assertEqual(len(content_files), 4)

        before = service.query(ArtifactQuery(limit=10)).items
        with patch.object(socket, "socket", side_effect=AssertionError("network blocked")):
            restarted_repository = AcquisitionRepository(self.root / "acquisition")
            restarted = ArtifactQueryService(
                restarted_repository,
                FirmRepository.open(self.root / "firm-catalog"),
                self.template,
            )
            after = restarted.query(ArtifactQuery(limit=10)).items
            integrity = restarted_repository.verify_integrity()
        self.assertEqual(after, before)
        self.assertEqual(integrity["artifacts"], 4)

    def test_adapters_have_no_sqlite_or_persistence_dependency(self) -> None:
        module_paths = [
            ROOT / "src/rfi/acquisition/sec_numbered_form.py",
            *(
                ROOT / f"src/rfi/acquisition/sec_form_{suffix}.py"
                for suffix in ("10k", "10q", "8k", "20f", "6k")
            ),
        ]
        combined = "\n".join(path.read_text() for path in module_paths).casefold()
        for forbidden in ("sqlite", "repositorydatabase", "execute(", "cursor(", "select *"):
            self.assertNotIn(forbidden, combined)
        for adapter in self.adapters:
            parameters = inspect.signature(adapter.__init__).parameters
            self.assertEqual(tuple(parameters), ("provider", "clock"))
        workflow_source = (ROOT / "src/rfi/pull/workflow.py").read_text()
        for form in ("10-Q", "8-K", "20-F", "6-K"):
            self.assertNotIn(form, workflow_source)
        production = create_pull_workflow(self.root)
        claims = {
            tuple(item["artifact_ids"]): item["adapter_id"]
            for item in production.adapter_capabilities()
            if item["artifact_ids"]
        }
        self.assertEqual(
            claims,
            {
                ("sec_10k",): "sec-form-10k",
                ("sec_10q",): "sec-form-10q",
                ("sec_8k",): "sec-form-8k",
                ("sec_20f",): "sec-form-20f",
                ("sec_6k",): "sec-form-6k",
            },
        )


if __name__ == "__main__":
    unittest.main()
