from __future__ import annotations

import json
import socket
import sys
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from rfi.acquisition import (  # noqa: E402
    AcquisitionEngine,
    AcquisitionKernel,
    AcquisitionRepository,
    AdapterFailure,
    AdapterRegistry,
    DiscoveryPage,
    EngineFailurePoint,
    FailureClass,
    FixtureCatalogAdapter,
    FixtureFeedAdapter,
    RetrievalOutcome,
    RunStatus,
    fixture_profiles,
)
from rfi.acquisition.contracts import ContractError, IntegrityError  # noqa: E402

FIXTURES = ROOT / "fixtures/acquisition"


def fixed_clock() -> str:
    return "2026-04-01T00:00:00Z"


class EngineCase(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.state = Path(self.temporary.name)
        self.repository = AcquisitionRepository(self.state)
        for profile in fixture_profiles():
            self.repository.register_source(profile)
        self.catalog = FixtureCatalogAdapter(FIXTURES, "catalog-states.json")
        self.feed = FixtureFeedAdapter(FIXTURES, "feed-pages.json")
        self.registry = AdapterRegistry((self.catalog, self.feed))
        self.engine = AcquisitionEngine(self.repository, self.registry, fixed_clock)
        self.kernel = AcquisitionKernel(self.engine, self.repository)

    def tearDown(self) -> None:
        self.temporary.cleanup()


class AdapterAndOrderingTests(EngineCase):
    def test_registry_rejects_duplicate_and_missing_mechanisms(self) -> None:
        with self.assertRaises(ContractError):
            self.registry.register(FixtureCatalogAdapter(FIXTURES, "catalog-states.json"))
        with self.assertRaises(ContractError):
            AdapterRegistry().select(fixture_profiles()[0])

    def test_explicit_registration_and_multi_source_kernel_execution(self) -> None:
        self.assertEqual(
            self.registry.registrations(),
            {
                "fixture-catalog": "FixtureCatalogAdapter",
                "fixture-feed": "FixtureFeedAdapter",
            },
        )
        with patch.object(socket, "socket", side_effect=AssertionError("network used")):
            results = self.kernel.run_enabled("complete")
        self.assertEqual(
            [item.source_id for item in results],
            sorted(item.source_id for item in results),
        )
        self.assertTrue(all(item.status == RunStatus.COMPLETE for item in results))
        self.assertEqual(self.repository.verify_integrity()["sources"], 2)
        self.assertEqual(len(self.repository.document_index()["documents"]), 5)

    def test_catalog_ordering_skip_and_bounded_checkpoint(self) -> None:
        result = self.engine.run_source("source-fixture-catalog", "catalog")
        self.assertEqual(result.status, RunStatus.COMPLETE)
        self.assertEqual(
            [item.candidate_id for item in result.outcomes],
            [
                "candidate-catalog-a-v1",
                "candidate-catalog-b-policy",
                "candidate-catalog-c-v1",
            ],
        )
        self.assertEqual(result.skips, 1)
        self.assertEqual(result.checkpoint_after.position, 3)
        self.assertEqual(len(self.repository.artifact_metadata()), 2)
        self.assertIn(
            "skipped",
            {item.get("outcome") for item in self.repository.history()},
        )

    def test_pagination_and_duplicate_handling_with_equal_page_boundaries(self) -> None:
        result = self.engine.run_source("source-fixture-feed", "pages")
        self.assertEqual(result.status, RunStatus.COMPLETE)
        self.assertEqual(result.pages, 2)
        self.assertEqual(result.provider_continuations, ("page-2",))
        self.assertEqual(result.candidates_discovered, 5)
        self.assertEqual(result.candidates_unique, 3)
        self.assertEqual(result.duplicates, 2)
        self.assertEqual(result.durable_acquisitions, 3)
        self.assertEqual(result.checkpoint_after.position, 3)
        duplicate_records = [
            item
            for item in self.repository.history()
            if item.get("outcome") == RetrievalOutcome.DUPLICATE.value
        ]
        self.assertEqual(len(duplicate_records), 2)

    def test_malformed_discovery_is_observable_and_writes_no_evidence(self) -> None:
        self.feed.malformed_discovery = True
        result = self.engine.run_source("source-fixture-feed", "malformed")
        self.assertEqual(result.status, RunStatus.FAILED)
        self.assertEqual(result.failures, 1)
        self.assertEqual(result.diagnostics[-1]["failure_class"], "malformed_adapter")
        self.assertEqual(self.repository.history(), [])
        self.assertIsNone(result.checkpoint_after)

    def test_ambiguous_duplicate_candidate_fails_without_checkpoint(self) -> None:
        original = self.feed.discover

        def ambiguous(profile, continuation):
            page = original(profile, continuation)
            if continuation == "page-2":
                changed = replace(
                    page.candidates[1],
                    document_id="document-feed-conflicting",
                )
                return DiscoveryPage((page.candidates[0], changed), None, page.diagnostics)
            return page

        self.feed.discover = ambiguous  # type: ignore[method-assign]
        result = self.engine.run_source("source-fixture-feed", "ambiguous")
        self.assertEqual(result.status, RunStatus.FAILED)
        self.assertEqual(result.diagnostics[-1]["failure_class"], "malformed_adapter")
        self.assertIsNone(result.checkpoint_after)

    def test_provider_continuation_cycle_fails_observably(self) -> None:
        original = self.feed.discover

        def cyclic(profile, continuation):
            page = original(profile, continuation)
            if continuation == "page-2":
                return DiscoveryPage(page.candidates, "page-2", page.diagnostics)
            return page

        self.feed.discover = cyclic  # type: ignore[method-assign]
        result = self.engine.run_source("source-fixture-feed", "cycle")
        self.assertEqual(result.status, RunStatus.FAILED)
        self.assertIn("continuation cycle", result.diagnostics[-1]["message"])
        self.assertIsNone(result.checkpoint_after)


class IdempotencyRevisionTests(EngineCase):
    def test_equivalent_complete_run_preserves_repository_state(self) -> None:
        first = self.engine.run_source("source-fixture-feed", "same")
        history = self.repository.history()
        artifacts = self.repository.artifact_metadata()
        index = self.repository.document_index()
        checkpoint = self.repository.checkpoints()
        second = self.engine.run_source("source-fixture-feed", "same")
        self.assertEqual(first.status, RunStatus.COMPLETE)
        self.assertEqual(second.status, RunStatus.COMPLETE)
        self.assertEqual(second.durable_acquisitions, 0)
        self.assertEqual(self.repository.history(), history)
        self.assertEqual(self.repository.artifact_metadata(), artifacts)
        self.assertEqual(self.repository.document_index(), index)
        self.assertEqual(self.repository.checkpoints(), checkpoint)

    def test_revision_adds_artifact_without_rewriting_prior_evidence(self) -> None:
        self.engine.run_source("source-fixture-catalog", "initial")
        before_history = self.repository.history()
        before_artifacts = self.repository.artifact_metadata()
        self.catalog.state = "revised"
        revised = self.engine.run_source("source-fixture-catalog", "revision")
        entry = self.repository.document_index()["documents"]["document-catalog-a"]
        self.assertEqual(revised.status, RunStatus.COMPLETE)
        self.assertEqual(revised.checkpoint_before.position, 3)
        self.assertEqual(revised.checkpoint_after.position, 4)
        self.assertEqual(len(entry["artifacts"]), 2)
        self.assertTrue(all(item in self.repository.history() for item in before_history))
        self.assertTrue(
            all(item in self.repository.artifact_metadata() for item in before_artifacts)
        )


class FailureAndResumptionTests(EngineCase):
    def test_transient_mid_page_failure_is_partial_and_resumes_safely(self) -> None:
        self.feed.transient_retrieval_failures.add("candidate-feed-b-v1")
        partial = self.engine.run_source("source-fixture-feed", "partial")
        self.assertEqual(partial.status, RunStatus.PARTIAL)
        self.assertIsNone(partial.checkpoint_after)
        self.assertEqual(partial.durable_acquisitions, 1)
        self.assertEqual(partial.failures, 1)
        durable_history = self.repository.history()
        self.feed.transient_retrieval_failures.clear()
        resumed = self.engine.run_source("source-fixture-feed", "resume")
        self.assertEqual(resumed.status, RunStatus.COMPLETE)
        self.assertEqual(resumed.duplicates, 3)
        self.assertEqual(resumed.checkpoint_after.position, 3)
        self.assertTrue(all(item in self.repository.history() for item in durable_history))
        self.assertEqual(len(self.repository.document_index()["documents"]), 3)

    def test_discovery_failure_before_first_page_has_no_durable_effect(self) -> None:
        self.feed.transient_discovery_failures.add("start")
        result = self.engine.run_source("source-fixture-feed", "before-page")
        self.assertEqual(result.status, RunStatus.PARTIAL)
        self.assertEqual(result.pages, 0)
        self.assertEqual(self.repository.history(), [])
        self.assertIsNone(result.checkpoint_after)

    def test_discovery_failure_after_durable_page_resumes_safely(self) -> None:
        self.feed.transient_discovery_failures.add("page-2")
        partial = self.engine.run_source("source-fixture-feed", "after-page")
        self.assertEqual(partial.status, RunStatus.PARTIAL)
        self.assertEqual(partial.pages, 1)
        self.assertEqual(partial.durable_acquisitions, 2)
        self.assertIsNone(partial.checkpoint_after)
        self.feed.transient_discovery_failures.clear()
        resumed = self.engine.run_source("source-fixture-feed", "after-page-resume")
        self.assertEqual(resumed.status, RunStatus.COMPLETE)
        self.assertEqual(resumed.duplicates, 4)
        self.assertEqual(resumed.checkpoint_after.position, 3)

    def test_failure_after_all_candidates_before_checkpoint_is_safe(self) -> None:
        partial = self.engine.run_source(
            "source-fixture-catalog",
            "before-checkpoint",
            EngineFailurePoint.BEFORE_CHECKPOINT_FINALIZATION,
        )
        self.assertEqual(partial.status, RunStatus.PARTIAL)
        self.assertEqual(partial.durable_acquisitions, 2)
        self.assertIsNone(partial.checkpoint_after)
        resumed = self.engine.run_source("source-fixture-catalog", "checkpoint-resume")
        self.assertEqual(resumed.status, RunStatus.COMPLETE)
        self.assertEqual(resumed.duplicates, 2)
        self.assertEqual(resumed.checkpoint_after.position, 3)

    def test_permanent_failure_is_blocked_and_classified(self) -> None:
        original = self.feed.retrieve

        def fail(profile, candidate):
            if candidate.candidate_id == "candidate-feed-a-v1":
                raise AdapterFailure(
                    FailureClass.PERMANENT_RETRIEVAL, "fixture permanently absent", False
                )
            return original(profile, candidate)

        self.feed.retrieve = fail  # type: ignore[method-assign]
        result = self.engine.run_source("source-fixture-feed", "permanent")
        self.assertEqual(result.status, RunStatus.BLOCKED)
        self.assertEqual(result.diagnostics[-1]["failure_class"], "permanent_retrieval")
        self.assertIsNone(result.checkpoint_after)


class ReplayIntegrityAndConflictTests(EngineCase):
    def test_repository_conflict_propagates_as_structured_failure(self) -> None:
        profile = fixture_profiles()[0]
        candidate = self.catalog.discover(profile, None).candidates[1]
        repository_candidate = self.engine._repository_candidate(profile, candidate)
        attempt_id = self.engine._attempt_id(
            f"run-{profile.source_id}-conflict", candidate, "success"
        )
        self.repository.record_outcome(
            attempt_id,
            repository_candidate,
            RetrievalOutcome.FAILED,
            candidate.provenance.discovered_at,
            profile.mechanism,
            {"reason": "conflict fixture"},
        )
        result = self.engine.run_source(profile.source_id, "conflict")
        self.assertEqual(result.status, RunStatus.FAILED)
        self.assertEqual(result.diagnostics[-1]["failure_class"], "repository_conflict")
        self.assertIsNone(result.checkpoint_after)

    def test_multi_source_replay_requires_neither_adapters_nor_network(self) -> None:
        self.kernel.run_enabled("replay")
        history = self.repository.history()
        artifacts = {
            item["artifact_id"]: self.repository.read_artifact(item["artifact_id"])
            for item in self.repository.artifact_metadata()
        }
        index = self.repository.document_index()
        checkpoints = self.repository.checkpoints()
        self.repository.delete_derived_state()
        disabled_registry = AdapterRegistry()
        del disabled_registry
        with patch.object(socket, "socket", side_effect=AssertionError("network used")):
            replay = self.repository.replay()
        self.assertEqual(replay.documents, 5)
        self.assertEqual(self.repository.history(), history)
        self.assertEqual(self.repository.document_index(), index)
        self.assertEqual(self.repository.checkpoints(), checkpoints)
        self.assertEqual(
            {
                item["artifact_id"]: self.repository.read_artifact(item["artifact_id"])
                for item in self.repository.artifact_metadata()
            },
            artifacts,
        )
        self.assertEqual(self.repository.verify_integrity()["result"], "PASS")

    def test_artifact_corruption_after_engine_run_is_detected(self) -> None:
        self.engine.run_source("source-fixture-catalog", "corruption")
        artifact_id = self.repository.artifact_metadata()[0]["artifact_id"]
        path = self.state / "authoritative/artifacts" / f"{artifact_id}.content"
        path.chmod(0o644)
        path.write_bytes(b"corrupted")
        with self.assertRaises(IntegrityError):
            self.repository.verify_integrity()

    def test_repository_integrity_failure_is_structured(self) -> None:
        self.engine.run_source("source-fixture-catalog", "before-corruption")
        ledger = sorted((self.state / "authoritative/retrieval-ledger").glob("*.json"))[0]
        ledger.chmod(0o644)
        ledger.write_text("not-json\n", encoding="utf-8")
        self.catalog.state = "revised"
        result = self.engine.run_source("source-fixture-catalog", "after-corruption")
        self.assertEqual(result.status, RunStatus.FAILED)
        self.assertEqual(result.diagnostics[-1]["failure_class"], "repository_integrity")

    def test_clean_demonstrations_have_identical_repository_derived_state(self) -> None:
        self.kernel.run_enabled("deterministic")
        first = json.dumps(
            {
                "history": self.repository.history(),
                "artifacts": self.repository.artifact_metadata(),
                "index": self.repository.document_index(),
                "checkpoints": self.repository.checkpoints(),
            },
            sort_keys=True,
        )
        with tempfile.TemporaryDirectory() as directory:
            repository = AcquisitionRepository(Path(directory))
            for profile in fixture_profiles():
                repository.register_source(profile)
            catalog = FixtureCatalogAdapter(FIXTURES, "catalog-states.json")
            feed = FixtureFeedAdapter(FIXTURES, "feed-pages.json")
            engine = AcquisitionEngine(repository, AdapterRegistry((catalog, feed)), fixed_clock)
            AcquisitionKernel(engine, repository).run_enabled("deterministic")
            second = json.dumps(
                {
                    "history": repository.history(),
                    "artifacts": repository.artifact_metadata(),
                    "index": repository.document_index(),
                    "checkpoints": repository.checkpoints(),
                },
                sort_keys=True,
            )
        self.assertEqual(first, second)


if __name__ == "__main__":
    unittest.main()
