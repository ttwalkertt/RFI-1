from __future__ import annotations

import hashlib
import io
import json
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from rfi.intelligence import (  # noqa: E402
    DeterministicPlanner,
    DeterministicReasoner,
    IntelligenceOrchestrator,
    PackageGateway,
)
from rfi.knowledge import KnowledgeRepository  # noqa: E402
from rfi.retrieval import EvidenceAssembler, RetrievalRepository  # noqa: E402
from rfi.source_objects import SourceInput, SourceObjectRepository  # noqa: E402
from rfi.workspace import (  # noqa: E402
    AnnotationKind,
    InvestigationStatus,
    WorkspaceError,
    WorkspaceRepository,
    WorkspaceService,
)


class ArtifactMap:
    def __init__(self, inputs: list[SourceInput]) -> None:
        self.items = {item.artifact_id: item.content for item in inputs}

    def read_artifact(self, artifact_id: str) -> bytes:
        return self.items[artifact_id]


def fixture(name: str, document_id: str) -> SourceInput:
    content = (ROOT / "fixtures/knowledge" / name).read_bytes()
    return SourceInput(
        document_id,
        f"artifact-{hashlib.sha256(content).hexdigest()}",
        content,
    )


class WorkspaceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.workspace_path = self.root / "workspace"
        self.repository = WorkspaceRepository.create(self.workspace_path)
        self.inputs = [
            fixture("stx-submission.txt", "document-task008-stx"),
            fixture("wdc-submission.txt", "document-task008-wdc"),
        ]
        source = SourceObjectRepository(self.root / "source/catalog.sqlite")
        source.rebuild(self.inputs)
        knowledge = KnowledgeRepository(self.root / "knowledge")
        knowledge.rebuild(source)
        retrieval = RetrievalRepository(self.root / "retrieval", source, knowledge)
        retrieval.rebuild()
        assembler = EvidenceAssembler(source, ArtifactMap(self.inputs))
        gateway = PackageGateway(retrieval.search, assembler.assemble)
        self.executor = IntelligenceOrchestrator(
            DeterministicPlanner(), DeterministicReasoner(), gateway
        )

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def create(self):
        return self.repository.create_investigation(
            "Storage vendor filing comparison",
            "Compare bounded annual filing evidence for consulting preparation.",
            customer="Example customer",
            engagement="Call preparation",
        )

    def test_full_lifecycle_reopen_rerun_compare_export_backup_restore(self) -> None:
        investigation = self.create()
        service = WorkspaceService(self.repository, self.executor)
        first = service.execute(
            investigation.investigation_id,
            "Compare Seagate and Western Digital annual filings",
            usage={
                "planning_ms": 2,
                "retrieval_ms": 4,
                "model_ms": 3,
                "model_calls": 1,
                "input_tokens": 100,
                "output_tokens": 20,
                "estimated_cost": 0.012,
                "cost_currency": "USD",
            },
        )
        reopened = WorkspaceRepository.open(self.workspace_path)
        inspected = reopened.execution(first)
        package = inspected["terminal"]["payload"]["record"]["packages"][0]
        self.assertTrue(package["context_references"])
        self.assertNotIn("text", package["context_references"][0])
        note = reopened.add_annotation(
            investigation.investigation_id,
            AnnotationKind.INTERPRETATION,
            "Use this bounded result as call preparation, not a revenue analysis.",
            first,
        )
        second = WorkspaceService(reopened, self.executor).execute(
            investigation.investigation_id,
            "Compare Seagate and Western Digital annual filings",
        )
        comparison = reopened.compare(first, second)
        self.assertTrue(comparison.identical)
        self.assertFalse(comparison.evidence_changed)
        self.assertNotEqual(comparison.metric_deltas["execution_ms"], None)
        export = reopened.export(investigation.investigation_id)
        self.assertIn("Provenance and claim-mapping appendix", export.read_text())
        self.assertIn(note, reopened.investigation(investigation.investigation_id).annotation_ids)
        backup = reopened.backup(self.root / "workspace.zip")
        self.assertTrue(WorkspaceRepository.verify_backup(backup).valid)
        restored = WorkspaceRepository.restore(backup, self.root / "restored")
        self.assertTrue(restored.verify().valid)
        self.assertEqual(
            len(restored.events(investigation.investigation_id)),
            len(reopened.events(investigation.investigation_id)),
        )

    def test_append_only_chain_detects_corruption(self) -> None:
        self.create()
        event = next(self.repository.journal_root.glob("*.json"))
        payload = json.loads(event.read_text())
        payload["payload"]["title"] = "tampered"
        event.write_text(json.dumps(payload))
        report = self.repository.verify()
        self.assertFalse(report.valid)
        self.assertTrue(any("digest mismatch" in item for item in report.failures))
        with self.assertRaises(WorkspaceError):
            WorkspaceRepository.open(self.workspace_path)

    def test_interrupted_execution_is_recoverable_and_visible(self) -> None:
        investigation = self.create()
        execution_id = self.repository.begin_execution(
            investigation.investigation_id, "Question before interruption"
        )
        self.assertIn(execution_id, self.repository.verify().open_executions)
        self.repository.fail_execution(
            investigation.investigation_id,
            execution_id,
            "operator process terminated",
            interrupted=True,
        )
        self.assertNotIn(execution_id, self.repository.verify().open_executions)
        self.assertEqual(
            self.repository.execution(execution_id)["terminal"]["event_type"],
            "execution-interrupted",
        )

    def test_executor_failure_is_journaled_without_losing_start(self) -> None:
        class FailingExecutor:
            def execute(self, need, budget=None):
                raise RuntimeError("stale retrieval index")

        investigation = self.create()
        execution_id = WorkspaceService(self.repository, FailingExecutor()).execute(
            investigation.investigation_id, "Question"
        )
        view = self.repository.execution(execution_id)
        self.assertIsNotNone(view["start"])
        self.assertEqual(view["terminal"]["event_type"], "execution-failed")
        self.assertIn("stale retrieval index", view["terminal"]["payload"]["reason"])

    def test_partial_write_is_visible_then_quarantined_without_chain_change(self) -> None:
        investigation = self.create()
        before = self.repository.events()
        with self.assertRaises(WorkspaceError):
            self.repository._append(
                "test-partial", investigation.investigation_id, {}, simulate_partial=True
            )
        self.assertFalse(self.repository.verify().valid)
        recovered = self.repository.recover_partial_writes()
        self.assertTrue(recovered)
        self.assertTrue(self.repository.verify().valid)
        self.assertEqual(before, self.repository.events())

    def test_invalid_annotation_and_closed_execution_fail_without_event(self) -> None:
        investigation = self.create()
        count = len(self.repository.events())
        with self.assertRaises(WorkspaceError):
            self.repository.add_annotation(
                investigation.investigation_id, AnnotationKind.OBSERVATION, "  "
            )
        self.assertEqual(count, len(self.repository.events()))
        self.repository.set_status(investigation.investigation_id, InvestigationStatus.CLOSED)
        with self.assertRaises(WorkspaceError):
            self.repository.begin_execution(investigation.investigation_id, "question")

    def test_backup_and_restore_fail_closed(self) -> None:
        self.create()
        with self.assertRaises(WorkspaceError):
            self.repository.backup(self.workspace_path / "inside.zip")
        invalid = self.root / "invalid.zip"
        with zipfile.ZipFile(invalid, "w") as archive:
            archive.writestr("workspace.json", "{}")
        self.assertFalse(WorkspaceRepository.verify_backup(invalid).valid)
        with self.assertRaises(WorkspaceError):
            WorkspaceRepository.restore(invalid, self.root / "invalid-restore")
        backup = self.repository.backup(self.root / "valid.zip")
        destination = self.root / "exists"
        destination.mkdir()
        with self.assertRaises(WorkspaceError):
            WorkspaceRepository.restore(backup, destination)

    def test_missing_export_is_integrity_failure(self) -> None:
        investigation = self.create()
        export = self.repository.export(investigation.investigation_id)
        export.unlink()
        report = self.repository.verify()
        self.assertFalse(report.valid)
        self.assertIn("export referenced by journal is missing", report.failures)

    def test_diagnostics_are_redacted_and_not_durable(self) -> None:
        stream = io.StringIO()
        self.repository.diagnostic(
            stream, "provider-failure", {"api_key": "sensitive", "message": "outage"}
        )
        self.assertNotIn("sensitive", stream.getvalue())
        self.assertIn("[REDACTED]", stream.getvalue())
        self.assertFalse(any("diagnostic" in path.name for path in self.workspace_path.rglob("*")))

    def test_workspace_depends_only_on_public_intelligence_contracts(self) -> None:
        content = "\n".join(
            path.read_text(encoding="utf-8")
            for path in (SRC / "rfi/workspace").glob("*.py")
        )
        for forbidden in (
            "SourceObjectRepository",
            "KnowledgeRepository",
            "RetrievalRepository",
            "AcquisitionRepository",
            "sqlite3",
            "current-generation.json",
        ):
            self.assertNotIn(forbidden, content)
        for package in ("acquisition", "source_objects", "knowledge", "retrieval", "intelligence"):
            upstream = "\n".join(
                path.read_text(encoding="utf-8")
                for path in (SRC / "rfi" / package).glob("*.py")
            )
            self.assertNotIn("rfi.workspace", upstream)


if __name__ == "__main__":
    unittest.main()
