from __future__ import annotations

import json
import socket
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from rfi.acquisition import (  # noqa: E402
    AcquisitionRepository,
    CandidateDocument,
    Checkpoint,
    DiscoveryProvenance,
    FailurePoint,
    RetrievalOutcome,
    RetrievalResult,
    SourceProfile,
)
from rfi.acquisition.contracts import (  # noqa: E402
    ConflictError,
    ContractError,
    IntegrityError,
    PartialFailure,
)
from rfi.acquisition.demo import fixture_candidate, fixture_profile, run_demo  # noqa: E402


class RepositoryCase(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.state = Path(self.temporary.name)
        self.repository = AcquisitionRepository(self.state)
        self.repository.register_source(fixture_profile())
        self.candidate = fixture_candidate()
        self.content = b"exact fixture evidence\x00\xff\n"
        self.result = RetrievalResult(
            content=self.content,
            media_type="application/octet-stream",
            retrieved_at="2026-01-02T03:05:00Z",
            mechanism="fixture-reader",
            provider_identifiers={"catalog": "external-77"},
            diagnostics={"status": 200},
        )
        self.checkpoint = Checkpoint(7, "cursor-seven")

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def succeed(self, attempt_id: str = "attempt-success-7"):
        return self.repository.record_success(
            attempt_id, self.candidate, self.result, self.checkpoint
        )


class ContractAndRegistryTests(RepositoryCase):
    def test_identity_domains_are_explicit_and_independent(self) -> None:
        receipt = self.succeed()
        record = next(
            item
            for item in self.repository.history()
            if item["record_type"] == "retrieval_attempt"
        )
        self.assertNotEqual(record["source_id"], record["document_id"])
        self.assertNotEqual(record["candidate_id"], receipt.artifact_id)
        self.assertNotEqual(record["attempt_id"], receipt.artifact_id)
        self.assertEqual(record["retrieval_provider_identifiers"], {"catalog": "external-77"})
        self.assertNotIn("external-77", receipt.artifact_id)

    def test_source_registration_is_deterministic_and_idempotent(self) -> None:
        self.assertFalse(self.repository.register_source(fixture_profile()))
        self.assertEqual(len(self.repository.sources()), 1)

    def test_conflicting_source_definition_is_rejected(self) -> None:
        conflicting = SourceProfile(
            source_id=fixture_profile().source_id,
            name="Conflicting name",
            enabled=True,
            mechanism="fixture-reader",
        )
        with self.assertRaises(ConflictError):
            self.repository.register_source(conflicting)

    def test_malformed_source_definitions_are_rejected(self) -> None:
        invalid_profiles = [
            {"source_id": "INVALID", "name": "x", "enabled": True, "mechanism": "fixture"},
            {"source_id": "source-ok", "name": " ", "enabled": True, "mechanism": "fixture"},
            {
                "source_id": "source-ok",
                "name": "x",
                "enabled": True,
                "mechanism": "fixture",
                "configuration": {"bad": object()},
            },
        ]
        for values in invalid_profiles:
            with self.subTest(values=values), self.assertRaises(ContractError):
                SourceProfile(**values)

    def test_disabled_source_cannot_be_acquired(self) -> None:
        profile = SourceProfile("source-disabled", "Disabled", False, "fixture-reader")
        self.repository.register_source(profile)
        candidate = CandidateDocument(
            "candidate-disabled",
            profile.source_id,
            "document-disabled",
            self.candidate.provenance,
        )
        with self.assertRaises(ContractError):
            self.repository.record_success("attempt-disabled", candidate, self.result)


class ArtifactAndLedgerTests(RepositoryCase):
    def test_exact_bytes_and_integrity_metadata_are_preserved(self) -> None:
        receipt = self.succeed()
        self.assertEqual(self.repository.read_artifact(receipt.artifact_id), self.content)
        metadata = self.repository.artifact_metadata()[0]
        self.assertEqual(metadata["size"], len(self.content))
        self.assertEqual(receipt.artifact_id, f"artifact-{metadata['sha256']}")
        self.assertEqual(self.repository.verify_integrity()["result"], "PASS")

    def test_artifact_corruption_is_detected(self) -> None:
        receipt = self.succeed()
        content_path = self.state / "authoritative/artifacts" / f"{receipt.artifact_id}.content"
        content_path.chmod(0o644)
        content_path.write_bytes(b"corrupt")
        with self.assertRaises(IntegrityError):
            self.repository.verify_integrity()

    def test_derived_index_corruption_is_reported_not_silently_repaired(self) -> None:
        self.succeed()
        index_path = self.state / "derived/document-index.json"
        index_path.write_text('{"schema_version":1,"documents":{}}\n', encoding="utf-8")
        with self.assertRaises(IntegrityError):
            self.repository.verify_integrity()
        self.assertEqual(self.repository.replay().documents, 1)
        self.assertEqual(self.repository.verify_integrity()["result"], "PASS")

    def test_immutable_attempt_is_exactly_idempotent(self) -> None:
        first = self.succeed()
        second = self.succeed()
        attempts = [
            item
            for item in self.repository.history()
            if item["record_type"] == "retrieval_attempt"
        ]
        self.assertFalse(first.idempotent)
        self.assertTrue(second.idempotent)
        self.assertEqual(len(attempts), 1)

    def test_conflicting_attempt_identity_is_rejected_without_rewriting_history(self) -> None:
        self.succeed()
        original = json.dumps(self.repository.history(), sort_keys=True)
        changed = RetrievalResult(
            content=b"materially different",
            media_type=self.result.media_type,
            retrieved_at=self.result.retrieved_at,
            mechanism=self.result.mechanism,
        )
        with self.assertRaises(ConflictError):
            self.repository.record_success(
                "attempt-success-7", self.candidate, changed, self.checkpoint
            )
        self.assertEqual(json.dumps(self.repository.history(), sort_keys=True), original)

    def test_failed_skipped_and_duplicate_outcomes_are_auditable(self) -> None:
        for number, outcome in enumerate(
            (RetrievalOutcome.FAILED, RetrievalOutcome.SKIPPED, RetrievalOutcome.DUPLICATE),
            start=1,
        ):
            self.repository.record_outcome(
                f"attempt-outcome-{number}",
                self.candidate,
                outcome,
                f"2026-01-02T03:0{number}:00Z",
                "fixture-reader",
                {"reason": outcome.value},
            )
        attempts = self.repository.history()
        self.assertEqual({item["outcome"] for item in attempts}, {"failed", "skipped", "duplicate"})
        self.assertTrue(all(item["artifact_id"] is None for item in attempts))
        self.assertEqual(self.repository.checkpoints()["sources"], {})


class LifecycleReplayTests(RepositoryCase):
    def test_complete_fixture_lifecycle_and_diagnostics(self) -> None:
        fixture = ROOT / "fixtures/acquisition/sample-document.txt"
        result = run_demo(self.state / "demonstration", fixture)
        self.assertEqual(result["result"], "PASS")
        self.assertTrue(result["exact_bytes_preserved"])
        self.assertTrue(result["idempotent_repeat"])
        self.assertTrue(result["conflict_detected"])
        self.assertEqual(
            result["failed_attempt_diagnostics"]["error_type"], "FixtureUnavailable"
        )

    def test_index_loss_preserves_authoritative_state_and_rebuilds_deterministically(self) -> None:
        receipt = self.succeed()
        original_index = self.repository.document_index()
        history = self.repository.history()
        artifact = self.repository.read_artifact(receipt.artifact_id)
        first = self.repository.replay()
        self.repository.delete_derived_state()
        with self.assertRaises(IntegrityError):
            self.repository.document_index()
        second = self.repository.replay()
        self.assertEqual(self.repository.document_index(), original_index)
        self.assertEqual(self.repository.history(), history)
        self.assertEqual(self.repository.read_artifact(receipt.artifact_id), artifact)
        self.assertEqual(first.index_sha256, second.index_sha256)
        self.assertEqual(first.checkpoint_sha256, second.checkpoint_sha256)

    def test_replay_has_no_network_dependency(self) -> None:
        self.succeed()
        self.repository.delete_derived_state()
        with patch.object(socket, "socket", side_effect=AssertionError("network used")):
            result = self.repository.replay()
        self.assertEqual(result.documents, 1)

    def test_checkpoint_is_source_scoped_and_monotonic(self) -> None:
        self.succeed()
        checkpoint = self.repository.checkpoints()["sources"][self.candidate.source_id]
        self.assertEqual(checkpoint["position"], 7)
        later_result = RetrievalResult(
            self.content,
            self.result.media_type,
            "2026-01-02T04:05:00Z",
            self.result.mechanism,
        )
        with self.assertRaises(ConflictError):
            self.repository.record_success(
                "attempt-backward", self.candidate, later_result, Checkpoint(6, "backward")
            )
        self.assertEqual(
            self.repository.checkpoints()["sources"][self.candidate.source_id]["position"], 7
        )

    def test_replay_failure_does_not_publish_partial_derived_state(self) -> None:
        self.succeed()
        self.repository.delete_derived_state()
        with self.assertRaises(PartialFailure):
            self.repository.replay(FailurePoint.DURING_REPLAY)
        with self.assertRaises(IntegrityError):
            self.repository.document_index()
        self.assertEqual(self.repository.checkpoints()["sources"], {})


class FailureOrderingTests(RepositoryCase):
    def inject(self, point: FailurePoint) -> None:
        with self.assertRaises(PartialFailure):
            self.repository.record_success(
                f"attempt-{point.value}",
                self.candidate,
                self.result,
                self.checkpoint,
                point,
            )

    def test_failure_before_artifact_has_no_durable_effect(self) -> None:
        self.inject(FailurePoint.BEFORE_ARTIFACT)
        self.assertEqual(self.repository.artifact_metadata(), [])
        self.assertEqual(self.repository.history(), [])

    def test_failure_after_artifact_preserves_orphan_evidence_but_no_success(self) -> None:
        self.inject(FailurePoint.AFTER_ARTIFACT)
        self.assertEqual(len(self.repository.artifact_metadata()), 1)
        self.assertEqual(self.repository.history(), [])
        self.assertEqual(self.repository.checkpoints()["sources"], {})

    def test_failure_before_index_leaves_replayable_ledger_without_progress(self) -> None:
        self.inject(FailurePoint.BEFORE_INDEX)
        self.assertEqual(len(self.repository.history()), 1)
        with self.assertRaises(IntegrityError):
            self.repository.document_index()
        self.assertEqual(self.repository.checkpoints()["sources"], {})
        self.assertEqual(self.repository.replay().documents, 1)

    def test_failure_before_checkpoint_has_index_but_does_not_advance(self) -> None:
        self.inject(FailurePoint.BEFORE_CHECKPOINT)
        self.assertEqual(len(self.repository.document_index()["documents"]), 1)
        self.assertEqual(self.repository.checkpoints()["sources"], {})
        retry = self.repository.record_success(
            "attempt-before_checkpoint", self.candidate, self.result, self.checkpoint
        )
        self.assertTrue(retry.idempotent)
        self.assertEqual(
            self.repository.checkpoints()["sources"][self.candidate.source_id]["position"], 7
        )


class ScopeBoundaryTests(unittest.TestCase):
    def test_product_package_contains_only_acquisition_substrate(self) -> None:
        files = {
            path.relative_to(SRC / "rfi").as_posix()
            for path in (SRC / "rfi").rglob("*.py")
        }
        self.assertEqual(
            files,
            {
                "__init__.py",
                "acquisition/__init__.py",
                "acquisition/contracts.py",
                "acquisition/demo.py",
                "acquisition/persistence.py",
                "acquisition/repository.py",
            },
        )

    def test_no_network_or_downstream_imports_exist(self) -> None:
        prohibited = (
            "requests",
            "urllib.request",
            "http.client",
            "socket",
            "openai",
            "embedding",
            "vector",
            "observation",
            "projection",
        )
        content = "\n".join(
            path.read_text(encoding="utf-8")
            for path in (SRC / "rfi").rglob("*.py")
        ).lower()
        for term in prohibited:
            with self.subTest(term=term):
                self.assertNotIn(term, content)


if __name__ == "__main__":
    unittest.main()
