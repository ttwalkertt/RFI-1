"""TASK-054 explicit externally managed firm-profile reload acceptance tests."""

from __future__ import annotations

import hashlib
import json
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from dataclasses import asdict
from pathlib import Path
from unittest.mock import patch

from rfi.acquisition import (
    AcquisitionRepository,
    CandidateDocument,
    DiscoveryPage,
    DiscoveryProvenance,
    RetrievalResult,
    SourceProfile,
)
from rfi.admin import create_admin_server
from rfi.cli import initialize
from rfi.firm_configuration import prepare_firm_configuration
from rfi.firms import FirmRepository
from rfi.pull import (
    PullRequest,
    PullRunRepository,
    PullWorkflow,
    RetrievalAdapterCapability,
    RetrievalAdapterRegistration,
    RetrievalAdapterRegistry,
)
from rfi.source_profiles import SourceProfileRepository, load_canonical_template
from rfi.storage import RepositoryDatabase

ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / "docs/microsoft.firm-config.example.json"
HINT = "https://stockanalysis.com/stocks/msft/transcripts/"


class BlockingTranscriptAdapter:
    """Hold retrieval after Pull Workflow has captured its immutable profile snapshot."""

    mechanism = "earnings_transcript"

    def __init__(self) -> None:
        self.entered = threading.Event()
        self.release = threading.Event()

    def discover(self, profile: SourceProfile, continuation: str | None) -> DiscoveryPage:
        del profile, continuation
        self.entered.set()
        if not self.release.wait(3):
            raise AssertionError("blocking transcript fixture was not released")
        return DiscoveryPage((), None, {"coverage": "complete"})

    def retrieve(self, profile: SourceProfile, candidate: object) -> RetrievalResult:
        del profile, candidate
        raise AssertionError("empty discovery cannot retrieve")


class Task054Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.state = Path(self.temporary.name) / "state"
        self.write(self.value())
        initialize(self.state)
        self.server = create_admin_server(self.state, port=0)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        host, port = self.server.server_address
        self.base = f"http://{host}:{port}"

    def tearDown(self) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=3)
        self.temporary.cleanup()

    @staticmethod
    def value() -> dict[str, object]:
        return json.loads(EXAMPLE.read_text(encoding="utf-8"))

    def write(self, value: object) -> None:
        directory = self.state / "firm-config"
        directory.mkdir(parents=True, exist_ok=True)
        (directory / "microsoft.firm-config.json").write_text(
            json.dumps(value, indent=2) + "\n", encoding="utf-8"
        )

    def request(
        self, path: str, method: str = "GET", payload: dict | None = None
    ) -> tuple[int, dict | str]:
        body = json.dumps(payload).encode() if payload is not None else None
        request = urllib.request.Request(
            self.base + path,
            data=body,
            method=method,
            headers={"Content-Type": "application/json"} if body is not None else {},
        )
        try:
            with urllib.request.urlopen(request, timeout=5) as response:
                content = response.read().decode()
                return response.status, (
                    json.loads(content)
                    if "json" in response.headers["Content-Type"]
                    else content
                )
        except urllib.error.HTTPError as error:
            value = json.loads(error.read())
            error.close()
            return error.code, value

    def database_snapshot(self) -> dict[str, object]:
        database = RepositoryDatabase.open(self.state)
        tables = (
            "firms",
            "firm_revisions",
            "firm_external_identities",
            "source_profiles",
            "source_profile_revisions",
            "firm_config_authorities",
        )
        with database.connect(read_only=True) as connection:
            return {
                "authority_revision": database.revision(),
                **{
                    table: tuple(
                        tuple(row)
                        for row in connection.execute(f"SELECT * FROM {table}").fetchall()
                    )
                    for table in tables
                },
            }

    def transcript_profile(self) -> tuple[str, tuple[str, ...]]:
        profile = SourceProfileRepository.open(
            self.state / "source-profiles", load_canonical_template()
        ).get("microsoft")
        assert profile is not None
        transcript = next(
            item for item in profile.items if item.artifact_id == "earnings_transcript"
        )
        return (
            profile.source_profile_revision_id,
            transcript.retrieval_candidates[0].discovery_hints,
        )

    def configure_hint(self) -> None:
        value = self.value()
        value["sources"]["earnings_transcript"]["discovery_hints"] = [HINT]  # type: ignore[index]
        self.write(value)

    def test_ui_exposes_confirmed_cancelable_and_bounded_reload_workflow(self) -> None:
        status, html = self.request("/firms")
        self.assertEqual(status, 200)
        assert isinstance(html, str)
        for marker in (
            'id="reload-firm-profiles"',
            "Reload Firm Profiles",
            "if(!confirm(message))return",
            "even when files are unchanged",
            "Existing acquisitions, retained artifacts, observations, and historical evidence",
            "button.disabled=true",
            "Reloading Firm Profiles…",
            "finally{button.disabled=false;button.textContent=prior}",
            "await load();if(selected)await showFirm(selected)",
            "result.repository_authority_revision",
        ):
            self.assertIn(marker, html)

    def test_reload_projects_changed_hint_without_restart_and_returns_exact_revision(self) -> None:
        prior_profile, prior_hints = self.transcript_profile()
        self.assertNotIn(HINT, prior_hints)
        self.configure_hint()
        before = RepositoryDatabase.open(self.state).revision()

        status, result = self.request(
            "/api/firm-configurations/reload", "POST", {}
        )

        self.assertEqual(status, 200)
        assert isinstance(result, dict)
        self.assertEqual(
            result,
            {
                "status": "reloaded",
                "files": 1,
                "firms": 1,
                "profiles": 1,
                "external_identities": 1,
                "repository_authority_revision": before + 1,
                "authority": "external-json",
            },
        )
        current_profile, hints = self.transcript_profile()
        self.assertNotEqual(current_profile, prior_profile)
        self.assertEqual(hints[0], HINT)
        self.assertEqual(result["repository_authority_revision"],
                         RepositoryDatabase.open(self.state).revision())

    def test_reload_rejects_scope_controls_and_non_post_methods(self) -> None:
        before = self.database_snapshot()
        status, rejected = self.request(
            "/api/firm-configurations/reload", "POST", {"firm_id": "microsoft"}
        )
        self.assertEqual(status, 400)
        assert isinstance(rejected, dict)
        self.assertEqual(rejected["error_code"], "invalid_request")
        self.assertEqual(
            self.request(
                "/api/firm-configurations/reload?firm_id=microsoft", "POST", {}
            )[0],
            400,
        )
        self.assertEqual(self.request("/api/firm-configurations/reload")[0], 404)
        self.assertEqual(self.database_snapshot(), before)

    def test_concurrent_reload_is_rejected_and_guard_releases_after_success(self) -> None:
        entered = threading.Event()
        release = threading.Event()
        actual = prepare_firm_configuration

        def blocking(state: Path):  # noqa: ANN202
            entered.set()
            if not release.wait(3):
                raise AssertionError("concurrent reload fixture was not released")
            return actual(state)

        first: list[tuple[int, dict | str]] = []
        with patch("rfi.admin.server.prepare_firm_configuration", side_effect=blocking):
            worker = threading.Thread(
                target=lambda: first.append(self.request(
                    "/api/firm-configurations/reload", "POST", {}
                )),
                daemon=True,
            )
            worker.start()
            self.assertTrue(entered.wait(2))
            status, conflict = self.request(
                "/api/firm-configurations/reload", "POST", {}
            )
            self.assertEqual(status, 409)
            assert isinstance(conflict, dict)
            self.assertEqual(
                conflict["error_code"], "firm_configuration_reload_in_progress"
            )
            release.set()
            worker.join(timeout=3)
        self.assertEqual(first[0][0], 200)
        self.assertEqual(
            self.request("/api/firm-configurations/reload", "POST", {})[0], 200
        )

    def test_structural_failure_is_diagnostic_and_writes_nothing(self) -> None:
        before = self.database_snapshot()
        (self.state / "firm-config" / "microsoft.firm-config.json").write_text(
            "{", encoding="utf-8"
        )
        status, failure = self.request(
            "/api/firm-configurations/reload", "POST", {}
        )
        self.assertEqual(status, 400)
        assert isinstance(failure, dict)
        self.assertEqual(failure["error_code"], "firm_configuration_invalid")
        self.assertIn("malformed JSON", failure["diagnostics"][0])
        self.assertEqual(self.database_snapshot(), before)

    def test_injected_failure_rolls_back_and_retry_matches_clean_progression(self) -> None:
        self.configure_hint()
        before = self.database_snapshot()

        def fail(state: Path):  # noqa: ANN202
            return prepare_firm_configuration(state, fail_after_firms=1)

        with patch("rfi.admin.server.prepare_firm_configuration", side_effect=fail):
            status, failure = self.request(
                "/api/firm-configurations/reload", "POST", {}
            )
        self.assertEqual(status, 400)
        assert isinstance(failure, dict)
        self.assertIn("injected materialization failure", failure["diagnostics"])
        self.assertEqual(self.database_snapshot(), before)

        status, success = self.request(
            "/api/firm-configurations/reload", "POST", {}
        )
        self.assertEqual(status, 200)
        assert isinstance(success, dict)
        after = self.database_snapshot()
        self.assertEqual(
            after["authority_revision"], int(before["authority_revision"]) + 1
        )
        self.assertEqual(
            success["repository_authority_revision"], after["authority_revision"]
        )
        self.assertEqual(len(after["firm_revisions"]), len(before["firm_revisions"]) + 1)
        self.assertEqual(
            len(after["source_profile_revisions"]),
            len(before["source_profile_revisions"]) + 1,
        )

    def test_repeated_reload_retains_init_equivalent_revision_behavior(self) -> None:
        firms = FirmRepository.open(self.state / "firm-catalog")
        profiles = SourceProfileRepository.open(
            self.state / "source-profiles", load_canonical_template()
        )
        before = RepositoryDatabase.open(self.state).revision()
        first = self.request("/api/firm-configurations/reload", "POST", {})[1]
        second = self.request("/api/firm-configurations/reload", "POST", {})[1]
        assert isinstance(first, dict) and isinstance(second, dict)
        self.assertEqual(first["repository_authority_revision"], before + 1)
        self.assertEqual(second["repository_authority_revision"], before + 2)
        self.assertEqual(len(firms.history("microsoft")), 3)
        self.assertEqual(len(profiles.history("microsoft")), 3)

    def test_admin_startup_remains_validation_only_before_and_after_file_edit(self) -> None:
        before = self.database_snapshot()
        first = create_admin_server(self.state, port=0)
        first.server_close()
        self.assertEqual(self.database_snapshot(), before)
        self.configure_hint()
        second = create_admin_server(self.state, port=0)
        second.server_close()
        self.assertEqual(self.database_snapshot(), before)

    def test_reload_preserves_acquisition_artifact_attempt_and_observation(self) -> None:
        acquisition = AcquisitionRepository(self.state / "acquisition")
        source = SourceProfile(
            "source-task054", "TASK-054 retained evidence", True, "fixture-reader",
            policy={"firm_id": "microsoft", "artifact_id": "sec_10k"},
        )
        acquisition.register_source(source)
        candidate = CandidateDocument(
            "candidate-task054", "source-task054", "document-task054",
            DiscoveryProvenance(
                "2026-08-01T00:00:00Z", "fixture-reader",
                locations=("https://example.test/evidence",),
            ),
        )
        content = b"TASK-054 immutable evidence"
        acquisition.record_success(
            "attempt-task054", candidate,
            RetrievalResult(content, "text/plain", "2026-08-01T00:01:00Z", "fixture-reader"),
        )
        before = (
            acquisition.sources(), acquisition.history(), acquisition.observations(),
            acquisition.artifact_metadata(), hashlib.sha256(content).hexdigest(),
        )
        self.configure_hint()
        self.assertEqual(
            self.request("/api/firm-configurations/reload", "POST", {})[0], 200
        )
        after = (
            acquisition.sources(), acquisition.history(), acquisition.observations(),
            acquisition.artifact_metadata(),
            hashlib.sha256(acquisition.read_artifact(f"artifact-{before[4]}")).hexdigest(),
        )
        self.assertEqual(after, before)

    def test_pull_snapshot_isolation_and_no_broad_reload_lock(self) -> None:
        old_revision, old_hints = self.transcript_profile()
        adapter = BlockingTranscriptAdapter()
        registry = RetrievalAdapterRegistry((RetrievalAdapterRegistration(
            RetrievalAdapterCapability(
                "blocking-transcript", ("earnings_transcript",), ("discovery",)
            ),
            adapter,
        ),))
        workflow = PullWorkflow(
            FirmRepository.open(self.state / "firm-catalog"),
            SourceProfileRepository.open(
                self.state / "source-profiles", load_canonical_template()
            ),
            load_canonical_template(),
            AcquisitionRepository(self.state / "acquisition"),
            registry,
            PullRunRepository(self.state / "task054-pulls"),
            identifier_factory=iter(("inflight", "later")).__next__,
        )
        self.server.pull_workflow = workflow
        in_flight_id = workflow.initiate(PullRequest(("microsoft",)))
        worker = threading.Thread(target=workflow.execute, args=(in_flight_id,), daemon=True)
        worker.start()
        self.assertTrue(adapter.entered.wait(2))

        self.configure_hint()
        status, reloaded = self.request(
            "/api/firm-configurations/reload", "POST", {}
        )
        self.assertEqual(status, 200, "reload must complete while acquisition is blocked")
        assert isinstance(reloaded, dict)
        new_revision, new_hints = self.transcript_profile()
        self.assertNotEqual(new_revision, old_revision)
        self.assertEqual(new_hints[0], HINT)

        adapter.release.set()
        worker.join(timeout=3)
        in_flight = workflow.results(in_flight_id)
        self.assertEqual(
            in_flight["profile_snapshots"][0]["source_profile_revision_id"], old_revision
        )
        in_flight_transcript = next(
            item for item in in_flight["profile_snapshots"][0]["items"]
            if item["artifact_id"] == "earnings_transcript"
        )
        self.assertEqual(
            tuple(in_flight_transcript["retrieval_candidates"][0]["discovery_hints"]),
            old_hints,
        )
        later = workflow.run(PullRequest(("microsoft",)))
        later_snapshot = workflow.results(later.run_id)["profile_snapshots"][0]
        self.assertEqual(later_snapshot["source_profile_revision_id"], new_revision)
        later_transcript = next(
            item for item in later_snapshot["items"]
            if item["artifact_id"] == "earnings_transcript"
        )
        self.assertEqual(later_transcript["retrieval_candidates"][0]["discovery_hints"][0], HINT)


if __name__ == "__main__":
    unittest.main()
