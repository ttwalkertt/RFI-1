from __future__ import annotations

import hashlib
import json
import tempfile
import threading
import time
import unittest
import urllib.request
from email.message import Message
from pathlib import Path
from unittest.mock import Mock, patch

from rfi.acquisition import (
    AcquisitionRepository,
    AdapterCandidate,
    AdapterFailure,
    AdapterRegistry,
    DirectUrlAdapter,
    DiscoveryPage,
    FailureClass,
    RetrievalResult,
)
from rfi.acquisition.contracts import DiscoveryProvenance, SourceProfile
from rfi.admin import create_admin_server
from rfi.cli import main
from rfi.concepts import ConceptRepository
from rfi.firms import FirmRepository, sample_firms
from rfi.pull import (
    ArtifactOutcome,
    PullRequest,
    PullRunRepository,
    PullStage,
    PullStatus,
    PullWorkflow,
)
from rfi.source_profiles import (
    RetrievalCandidate,
    SourceProfileDraft,
    SourceProfileItem,
    SourceProfileRepository,
    load_canonical_template,
)


def fixed_clock() -> str:
    return "2026-07-18T12:00:00Z"


class ScriptedDirectAdapter:
    """Deterministic direct-url adapter used to prove workflow semantics."""

    mechanism = "direct_url"

    def __init__(self) -> None:
        self.contents: dict[str, bytes] = {}
        self.failures: set[str] = set()

    def discover(
        self, profile: SourceProfile, continuation: str | None
    ) -> DiscoveryPage:
        del continuation
        digest = hashlib.sha256(profile.source_id.encode()).hexdigest()
        document_id = str(profile.policy["document_id"])
        return DiscoveryPage(
            (
                AdapterCandidate(
                    f"candidate-{digest[:20]}",
                    document_id,
                    1,
                    f"revision-{digest[20:40]}",
                    DiscoveryProvenance(
                        fixed_clock(),
                        self.mechanism,
                        locations=(str(profile.configuration["url"]),),
                    ),
                ),
            ),
            None,
        )

    def retrieve(
        self, profile: SourceProfile, candidate: AdapterCandidate
    ) -> RetrievalResult:
        del candidate
        url = str(profile.configuration["url"])
        if url in self.failures:
            raise AdapterFailure(
                FailureClass.PERMANENT_RETRIEVAL,
                f"scripted retrieval failure: {url}",
                False,
            )
        return RetrievalResult(
            self.contents[url],
            "text/plain",
            fixed_clock(),
            self.mechanism,
        )


class FakeHttpResponse:
    """Minimal exact-byte response for the production direct URL adapter."""

    def __init__(self, content: bytes) -> None:
        self._content = content
        self.status = 200
        self.headers = Message()
        self.headers["Content-Type"] = "application/pdf"

    def __enter__(self) -> FakeHttpResponse:
        return self

    def __exit__(self, *arguments: object) -> None:
        del arguments

    def read(self) -> bytes:
        return self._content

    def geturl(self) -> str:
        return "https://fixture.test/final.pdf"

class PullWorkflowCase(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.template = load_canonical_template()
        self.firms = FirmRepository.initialize(self.root / "firm-catalog")
        for draft in sample_firms()[:2]:
            self.firms.create(draft)
        self.profiles = SourceProfileRepository.initialize(
            self.root / "source-profiles", self.template
        )
        self.acquisition = AcquisitionRepository(self.root / "acquisition")
        self.adapter = ScriptedDirectAdapter()
        self.workflow = PullWorkflow(
            self.firms,
            self.profiles,
            self.template,
            self.acquisition,
            AdapterRegistry((self.adapter,)),
            PullRunRepository(self.root / "pull-workflows"),
            fixed_clock,
            iter((f"run{index}" for index in range(20))).__next__,
        )

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def draft(
        self,
        firm_id: str,
        configured: dict[str, tuple[bool, tuple[RetrievalCandidate, ...]]],
    ) -> SourceProfileDraft:
        items = tuple(
            SourceProfileItem(
                artifact.artifact_id,
                configured.get(artifact.artifact_id, (False, ()))[0],
                configured.get(artifact.artifact_id, (False, ()))[1],
            )
            for artifact in self.template.artifacts
        )
        return SourceProfileDraft(firm_id, items)

    @staticmethod
    def direct(url: str) -> tuple[RetrievalCandidate, ...]:
        return (RetrievalCandidate("direct_url", 1, url=url),)

    def test_stage_order_snapshot_multi_firm_independence_and_all_outcomes(self) -> None:
        self.adapter.contents = {
            "https://fixture.test/shared": b"same exact artifact",
            "https://fixture.test/later": b"later success",
        }
        self.adapter.failures = {"https://fixture.test/fail"}
        first = self.profiles.publish(
            self.draft(
                "seagate",
                {
                    "annual_report": (True, self.direct("https://fixture.test/fail")),
                    "earnings_release": (
                        True,
                        self.direct("https://fixture.test/later"),
                    ),
                    "press_release": (
                        True,
                        (RetrievalCandidate("feed", 1, url="https://fixture.test/feed"),),
                    ),
                    "corporate_news": (True, ()),
                },
            ),
            None,
        )
        second = self.profiles.publish(
            self.draft(
                "western-digital",
                {"annual_report": (True, self.direct("https://fixture.test/shared"))},
            ),
            None,
        )
        self.adapter.contents["https://fixture.test/later"] = b"same exact artifact"
        result = self.workflow.run(
            PullRequest(("seagate", "western-digital"))
        )
        self.assertEqual(result.status, PullStatus.PARTIAL)
        self.assertEqual(
            result.completed_stages,
            tuple(PullStage),
        )
        self.assertEqual(
            [firm.source_profile_revision_id for firm in result.firms],
            [first.source_profile_revision_id, second.source_profile_revision_id],
        )
        seagate = result.firms[0]
        western = result.firms[1]
        outcomes = {item.artifact_id: item.outcome for item in seagate.artifacts}
        self.assertEqual(
            outcomes,
            {
                "annual_report": ArtifactOutcome.RETRIEVAL_FAILURE,
                "earnings_release": ArtifactOutcome.SUCCESS,
                "press_release": ArtifactOutcome.SKIPPED,
                "corporate_news": ArtifactOutcome.CONFIGURATION_PROBLEM,
            },
        )
        self.assertEqual(western.status, PullStatus.COMPLETED)
        self.assertEqual(western.artifacts[0].outcome, ArtifactOutcome.DUPLICATE)
        skipped = next(
            item for item in seagate.artifacts if item.artifact_id == "press_release"
        )
        self.assertIn(
            "No adapter available for this retrieval mode.",
            skipped.diagnostic,
        )
        durable = self.workflow.results(result.run_id)
        self.assertEqual(
            durable["profile_snapshots"][0]["source_profile_revision_id"],
            first.source_profile_revision_id,
        )
        self.assertEqual(self.acquisition.verify_integrity()["artifacts"], 1)

    def test_no_change_successful_and_failed_workflow_aggregation(self) -> None:
        url = "https://fixture.test/one"
        self.adapter.contents[url] = b"version one"
        revision = self.profiles.publish(
            self.draft("seagate", {"annual_report": (True, self.direct(url))}),
            None,
        )
        successful = self.workflow.run(PullRequest(("seagate",)))
        self.assertEqual(successful.status, PullStatus.COMPLETED)
        self.assertEqual(successful.summary.success, 1)
        unchanged = self.workflow.run(PullRequest(("seagate",)))
        self.assertEqual(unchanged.status, PullStatus.COMPLETED)
        self.assertEqual(unchanged.summary.no_change, 1)

        failed_url = "https://fixture.test/broken"
        self.adapter.failures.add(failed_url)
        self.profiles.publish(
            self.draft(
                "seagate",
                {"annual_report": (True, self.direct(failed_url))},
            ),
            revision.source_profile_revision_id,
        )
        failed = self.workflow.run(PullRequest(("seagate",)))
        self.assertEqual(failed.status, PullStatus.FAILED)
        self.assertEqual(failed.summary.retrieval_failure, 1)

    def test_configured_readiness_counts_and_all_configured_selection(self) -> None:
        self.profiles.publish(
            self.draft(
                "seagate",
                {
                    "annual_report": (
                        True,
                        self.direct("https://fixture.test/ready"),
                    ),
                    "press_release": (True, ()),
                },
            ),
            None,
        )
        firms = self.workflow.configured_firms()
        self.assertEqual(
            (len(firms), firms[0].enabled_artifacts, firms[0].runnable_artifacts),
            (1, 2, 1),
        )
        self.assertEqual(firms[0].incomplete_artifacts, 1)
        self.adapter.contents["https://fixture.test/ready"] = b"ready"
        result = self.workflow.run(PullRequest(all_configured=True))
        self.assertEqual([item.firm_id for item in result.firms], ["seagate"])

    def test_production_direct_url_adapter_ingests_exact_whole_artifact(self) -> None:
        content = b"%PDF-1.7\nwhole authoritative artifact\n"
        adapter = DirectUrlAdapter(
            fixed_clock,
            opener=lambda *args, **kwargs: FakeHttpResponse(content),
        )
        workflow = PullWorkflow(
            self.firms,
            self.profiles,
            self.template,
            self.acquisition,
            AdapterRegistry((adapter,)),
            PullRunRepository(self.root / "production-pull-runs"),
            fixed_clock,
            lambda: "1production",
        )
        self.profiles.publish(
            self.draft(
                "seagate",
                {
                    "annual_report": (
                        True,
                        self.direct("https://fixture.test/report.pdf"),
                    )
                },
            ),
            None,
        )
        result = workflow.run(PullRequest(("seagate",)))
        artifact_id = result.firms[0].artifacts[0].attempts[0].artifact_ids[0]
        self.assertEqual(result.summary.success, 1)
        self.assertEqual(self.acquisition.read_artifact(artifact_id), content)


class PullInterfaceTests(unittest.TestCase):
    def test_cli_invokes_pull_workflow_with_repeated_firms(self) -> None:
        workflow = Mock()
        workflow.run.return_value = Mock(
            status=PullStatus.COMPLETED,
            **{
                "__dataclass_fields__": {},
            },
        )
        result_value = Mock()
        result_value.status = PullStatus.COMPLETED
        with patch("rfi.cli._open_state"), patch(
            "rfi.cli.create_pull_workflow", return_value=workflow
        ), patch("rfi.cli.asdict", return_value={"status": "completed"}):
            code = main(
                [
                    "pull",
                    "--state",
                    "/tmp/rfi-task015-test",
                    "--firm",
                    "seagate",
                    "--firm",
                    "ibm",
                ]
            )
        self.assertEqual(code, 0)
        workflow.run.assert_called_once_with(PullRequest(("seagate", "ibm"), False))

    def test_gui_and_rest_are_thin_workflow_clients(self) -> None:
        root = Path(__file__).resolve().parents[1]
        html = (root / "src/rfi/admin/pull_sources.html").read_text(encoding="utf-8")
        server = (root / "src/rfi/admin/server.py").read_text(encoding="utf-8")
        cli = (root / "src/rfi/cli.py").read_text(encoding="utf-8")
        workflow = (root / "src/rfi/pull/workflow.py").read_text(encoding="utf-8")
        for marker in (
            "/api/pulls/firms",
            "method:'POST'",
            "/results",
            "enabled_artifacts",
            "runnable_artifacts",
            "incomplete_artifacts",
            "progress-bar",
        ):
            self.assertIn(marker, html)
        self.assertIn("pull_workflow.initiate", server)
        self.assertIn("pull_workflow.execute", server)
        self.assertIn("create_pull_workflow(state).run", cli)
        self.assertNotIn("run_source(", server + cli + html)
        self.assertEqual(workflow.count("engine.run_source("), 1)

    def test_rest_initiates_observes_and_returns_durable_results(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            state = Path(temporary)
            ConceptRepository.initialize(state)
            firms = FirmRepository.initialize(state / "firm-catalog")
            firms.create(sample_firms()[0])
            template = load_canonical_template()
            profiles = SourceProfileRepository.initialize(
                state / "source-profiles", template
            )
            profiles.publish(
                SourceProfileDraft(
                    "seagate",
                    tuple(
                        SourceProfileItem(
                            artifact.artifact_id,
                            artifact.artifact_id == "press_release",
                            (
                                RetrievalCandidate(
                                    "feed", 1, url="https://fixture.test/feed"
                                ),
                            )
                            if artifact.artifact_id == "press_release"
                            else (),
                        )
                        for artifact in template.artifacts
                    ),
                ),
                None,
            )
            server = create_admin_server(state, port=0)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            host, port = server.server_address
            base = f"http://{host}:{port}"
            try:
                request = urllib.request.Request(
                    base + "/api/pulls",
                    data=json.dumps({"firm_ids": ["seagate"]}).encode(),
                    method="POST",
                    headers={"Content-Type": "application/json"},
                )
                with urllib.request.urlopen(request, timeout=3) as response:
                    self.assertEqual(response.status, 202)
                    initiated = json.load(response)
                status = {"status": "running"}
                for _ in range(100):
                    with urllib.request.urlopen(
                        base + initiated["status_url"], timeout=3
                    ) as response:
                        status = json.load(response)
                    if status["status"] != "running":
                        break
                    time.sleep(0.01)
                self.assertEqual(status["status"], "completed")
                with urllib.request.urlopen(
                    base + initiated["results_url"], timeout=3
                ) as response:
                    results = json.load(response)
                self.assertEqual(results["summary"]["skipped"], 1)
                self.assertEqual(
                    results["firms"][0]["artifacts"][0]["diagnostic"],
                    "No adapter available for this retrieval mode. Configured mode(s): feed.",
                )
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=3)


if __name__ == "__main__":
    unittest.main()
