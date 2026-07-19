from __future__ import annotations

import json
import tempfile
import threading
import unittest
import urllib.parse
import urllib.request
from pathlib import Path

from rfi.acquisition import (
    AcquisitionRepository,
    CandidateDocument,
    DiscoveryProvenance,
    RetrievalResult,
    SourceProfile,
)
from rfi.admin import create_admin_server
from rfi.artifacts import ArtifactQueryError, ArtifactQueryService
from rfi.concepts import ConceptRepository
from rfi.firms import FirmRepository, sample_firms
from rfi.pull import PullRequest, PullRunRepository, PullWorkflow
from rfi.source_profiles import (
    RetrievalCandidate,
    SourceProfileDraft,
    SourceProfileItem,
    SourceProfileRepository,
    load_canonical_template,
)
from tests.test_task015 import ScriptedDirectAdapter, fixed_clock
from tests.test_task015 import retrieval_registry


class MultipleArtifactObservationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.state = Path(self.temporary.name) / "state"
        ConceptRepository.initialize(self.state)
        self.firms = FirmRepository.initialize(self.state / "firm-catalog")
        self.firms.create(sample_firms()[0])
        self.template = load_canonical_template()
        SourceProfileRepository.initialize(self.state / "source-profiles", self.template)
        self.repository = AcquisitionRepository(self.state / "acquisition")
        self.repository.register_source(
            SourceProfile(
                "source-seagate-observations",
                "Seagate observation fixture",
                True,
                "fixture-reader",
                policy={
                    "firm_id": "seagate",
                    "artifact_id": "sec_10k",
                    "source_profile_revision_id": "profile-seagate-one",
                    "retrieval_adapter_id": "fixture-observation-adapter",
                },
            )
        )
        self.service = ArtifactQueryService(self.repository, self.firms, self.template)
        self.document_id = "document-seagate-observation-proof"
        self.content = b"<h1>One immutable stored artifact</h1>"

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def acquire(self, number: int) -> tuple[str, str]:
        observed = f"2026-07-18T12:0{number}:00Z"
        candidate = CandidateDocument(
            "candidate-seagate-observation",
            "source-seagate-observations",
            self.document_id,
            DiscoveryProvenance(
                observed,
                "fixture-reader",
                {"provider": "fixture", "accession": "unchanged-annual-report"},
                (f"https://fixture.test/discovery/{number}", "https://fixture.test/artifact"),
                {
                    "adapter_id": "fixture-observation-adapter",
                    "provider": "Fixture Provider",
                    "form_type": "10-K",
                    "filing_date": "2026-06-30",
                    "acceptance_datetime": "2026-06-30T12:00:00Z",
                    "period_of_report": "2026-06-30",
                    "observation_number": number,
                },
            ),
        )
        receipt = self.repository.record_success(
            f"attempt-observation-{number}",
            candidate,
            RetrievalResult(
                self.content,
                "text/html",
                observed,
                "fixture-reader",
                {"provider": "fixture"},
                {"pull_number": number},
            ),
        )
        return receipt.artifact_id, receipt.observation_id

    def test_duplicate_pull_creates_observation_without_copying_content(self) -> None:
        first_artifact, first_observation = self.acquire(1)
        stored_before = self.repository.read_artifact(first_artifact)
        second_artifact, second_observation = self.acquire(2)

        self.assertEqual(first_artifact, second_artifact)
        self.assertNotEqual(first_observation, second_observation)
        self.assertEqual(len(self.repository.artifact_metadata()), 1)
        self.assertEqual(len(self.repository.observations()), 2)
        self.assertEqual(self.repository.read_artifact(first_artifact), stored_before)
        self.assertEqual(stored_before, self.content)
        content_files = list(
            (self.state / "acquisition/authoritative/artifacts").glob("*.content")
        )
        self.assertEqual(len(content_files), 1)
        self.assertEqual(self.repository.verify_integrity()["observations"], 2)

    def test_first_last_explicit_navigation_and_stale_cursor(self) -> None:
        artifact_id, first_id = self.acquire(1)
        _artifact_id, second_id = self.acquire(2)

        first = self.service.detail(self.document_id, "first")
        last = self.service.detail(self.document_id)
        explicit = self.service.detail(self.document_id, second_id)
        self.assertEqual(first.observation.observation_id, first_id)
        self.assertEqual(last.observation.observation_id, second_id)
        self.assertEqual(explicit, last)

        following = self.service.next(first.observation_cursor)
        preceding = self.service.previous(last.observation_cursor)
        self.assertEqual(following.observation.observation_id, second_id)
        self.assertEqual(preceding.observation.observation_id, first_id)
        self.assertEqual(first.summary.artifact_id, artifact_id)
        self.assertEqual(following.summary, first.summary)
        self.assertEqual(preceding.summary, last.summary)
        self.assertEqual(self.service.content(self.document_id).content, self.content)
        with self.assertRaises(ArtifactQueryError) as boundary:
            self.service.next(last.observation_cursor)
        self.assertEqual(boundary.exception.code, "observation_boundary")

        stale = first.observation_cursor
        self.acquire(3)
        with self.assertRaises(ArtifactQueryError) as raised:
            self.service.next(stale)
        self.assertEqual(raised.exception.code, "stale_cursor")

    def test_replay_preserves_observation_order_and_deduplicated_bytes(self) -> None:
        artifact_id, _first_id = self.acquire(1)
        self.acquire(2)
        before = self.repository.observations()
        index_before = self.repository.document_index()
        bytes_before = self.repository.read_artifact(artifact_id)

        self.repository.delete_derived_state()
        replay = self.repository.replay()

        self.assertEqual(self.repository.observations(), before)
        self.assertEqual(self.repository.document_index(), index_before)
        self.assertEqual(self.repository.read_artifact(artifact_id), bytes_before)
        self.assertEqual(replay.documents, 1)
        self.assertEqual(
            self.repository.document_index()["documents"][self.document_id]["artifacts"],
            [artifact_id],
        )

    def test_legacy_successful_attempt_projects_without_repository_mutation(self) -> None:
        _artifact_id, observation_id = self.acquire(1)
        observation_path = (
            self.state
            / "acquisition/authoritative/artifact-observations"
            / f"{observation_id}.json"
        )
        observation_path.unlink()
        repository = AcquisitionRepository(self.state / "acquisition")

        projected = repository.observations()

        self.assertEqual(len(projected), 1)
        self.assertTrue(projected[0]["legacy_projection"])
        self.assertFalse(observation_path.exists())
        self.assertEqual(repository.replay().documents, 1)
        self.assertEqual(repository.verify_integrity()["result"], "PASS")

    def test_browser_defaults_to_last_and_preserves_preview_during_navigation(self) -> None:
        html = (Path(__file__).parents[1] / "src/rfi/admin/artifact_browser.html").read_text()
        self.assertIn("Previous observation", html)
        self.assertIn("Next observation", html)
        self.assertIn("api('/api/artifacts/'+encodeURIComponent(documentId))", html)
        self.assertIn("if(previewArtifact!==s.artifact_id)", html)
        self.assertIn("observation_cursor", html)

    def test_browser_api_defaults_last_and_navigates_observation_metadata(self) -> None:
        artifact_id, first_id = self.acquire(1)
        self.acquire(2)
        server = create_admin_server(self.state, port=0)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        host, port = server.server_address
        base = f"http://{host}:{port}"
        detail_url = base + "/api/artifacts/" + urllib.parse.quote(self.document_id)
        try:
            with urllib.request.urlopen(detail_url, timeout=3) as response:
                last = json.loads(response.read())
            previous_url = (
                detail_url
                + "/observations/previous?cursor="
                + urllib.parse.quote(last["observation_cursor"])
            )
            with urllib.request.urlopen(previous_url, timeout=3) as response:
                previous = json.loads(response.read())
            self.assertEqual(previous["observation"]["observation_id"], first_id)
            self.assertEqual(previous["summary"]["artifact_id"], artifact_id)
            self.assertEqual(last["summary"], previous["summary"])
            self.assertNotEqual(last["observation"], previous["observation"])
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=3)


class DuplicatePullWorkflowTests(unittest.TestCase):
    def test_identical_pull_after_profile_revision_reuses_artifact_and_adds_observation(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            template = load_canonical_template()
            firms = FirmRepository.initialize(root / "firm-catalog")
            firms.create(sample_firms()[0])
            profiles = SourceProfileRepository.initialize(root / "source-profiles", template)
            acquisition = AcquisitionRepository(root / "acquisition")
            adapter = ScriptedDirectAdapter()
            url = "https://fixture.test/unchanged"
            adapter.contents[url] = b"unchanged bytes"
            workflow = PullWorkflow(
                firms,
                profiles,
                template,
                acquisition,
                retrieval_registry(adapter),
                PullRunRepository(root / "pull-workflows"),
                fixed_clock,
                iter(("first", "second")).__next__,
            )
            draft = SourceProfileDraft(
                "seagate",
                tuple(
                    SourceProfileItem(
                        artifact.artifact_id,
                        artifact.artifact_id == "annual_report",
                        (
                            (RetrievalCandidate("direct_url", 1, url=url),)
                            if artifact.artifact_id == "annual_report"
                            else ()
                        ),
                    )
                    for artifact in template.artifacts
                ),
            )
            first_revision = profiles.publish(draft, None)
            first = workflow.run(PullRequest(("seagate",)))
            profiles.publish(draft, first_revision.source_profile_revision_id)
            second = workflow.run(PullRequest(("seagate",)))

            self.assertEqual(first.summary.success, 1)
            self.assertEqual(second.summary.duplicate, 1)
            self.assertEqual(len(acquisition.artifact_metadata()), 1)
            self.assertEqual(len(acquisition.observations()), 2)
            self.assertEqual(acquisition.read_artifact(
                acquisition.artifact_metadata()[0]["artifact_id"]
            ), b"unchanged bytes")
            self.assertEqual(acquisition.verify_integrity()["result"], "PASS")


if __name__ == "__main__":
    unittest.main()
