#!/usr/bin/env python3
"""Operate and prove the TASK-008 durable consulting workspace."""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import sys
import tempfile
from dataclasses import asdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from rfi.intelligence import (  # noqa: E402
    ClaimKind,
    CompletionStatus,
    DeterministicPlanner,
    DeterministicReasoner,
    InformationNeed,
    IntelligenceClaim,
    IntelligenceOrchestrator,
    PackageGateway,
    ReasoningDraft,
    RetrievalPlan,
)
from rfi.knowledge import KnowledgeRepository  # noqa: E402
from rfi.retrieval import EvidenceAssembler, RetrievalError, RetrievalRepository  # noqa: E402
from rfi.source_objects import SourceInput, SourceObjectRepository  # noqa: E402
from rfi.workspace import (  # noqa: E402
    AnnotationKind,
    OperationalMetrics,
    WorkspaceError,
    WorkspaceRepository,
    WorkspaceService,
)


class InputArtifacts:
    """Public artifact reader for checked proof inputs."""

    def __init__(self, inputs: list[SourceInput]) -> None:
        self.items = {item.artifact_id: item.content for item in inputs}

    def read_artifact(self, artifact_id: str) -> bytes:
        """Return immutable bytes by public artifact identity."""
        if artifact_id not in self.items:
            raise RetrievalError(f"missing evidence artifact: {artifact_id}")
        return self.items[artifact_id]


def fixture_inputs() -> list[SourceInput]:
    """Load the deterministic STX and WDC consulting proof corpus."""
    result: list[SourceInput] = []
    for number, name in enumerate(("stx-submission.txt", "wdc-submission.txt"), start=1):
        content = (ROOT / "fixtures/knowledge" / name).read_bytes()
        result.append(
            SourceInput(
                f"document-task008-{number}",
                f"artifact-{hashlib.sha256(content).hexdigest()}",
                content,
            )
        )
    return result


def executor(state: Path, alternate: bool = False) -> IntelligenceOrchestrator:
    """Build authorities and return only the public TASK-007 executor downstream."""
    inputs = fixture_inputs()
    source = SourceObjectRepository(state / "source/catalog.sqlite")
    source.rebuild(inputs)
    knowledge = KnowledgeRepository(state / "knowledge")
    knowledge.rebuild(source)
    retrieval = RetrievalRepository(state / "retrieval", source, knowledge)
    retrieval.rebuild()
    assembler = EvidenceAssembler(source, InputArtifacts(inputs))
    gateway = PackageGateway(retrieval.search, assembler.assemble)
    return IntelligenceOrchestrator(
        DeterministicPlanner(alternate_wording=alternate),
        DeterministicReasoner(alternate_wording=alternate),
        gateway,
    )


class BadPlanner:
    """Malformed planner substitute for workspace failure proof."""

    def plan(self, need: Any, budget: Any) -> RetrievalPlan:
        """Return an invalid empty plan."""
        return RetrievalPlan("", "", (), budget)

    def follow_up(
        self,
        need: Any,
        plan: Any,
        completed_steps: Any,
        missing_requirements: Any,
    ) -> None:
        """Decline follow-up."""
        return None


class BadReasoner:
    """Unsupported-claim substitute for workspace failure proof."""

    def reason(self, need: Any, plan: Any, evidence: Any) -> ReasoningDraft:
        """Return an invalid unmapped claim."""
        claim = IntelligenceClaim(
            "invalid-claim",
            "Unsupported conclusion.",
            ClaimKind.DERIVED_KNOWLEDGE,
            (),
            "No mapping.",
            1.0,
        )
        return ReasoningDraft(
            claim.text, (claim,), (), (), (), CompletionStatus.COMPLETE
        )


class FailingGateway:
    """Retrieval outage substitute."""

    def retrieve(self, query: Any) -> Any:
        """Fail with an operator-visible retrieval condition."""
        raise RetrievalError("stale retrieval index")


def fixture_proof(root: Path) -> dict[str, Any]:
    """Run lifecycle, journal, comparison, export, backup, and failure proofs."""
    workspace_path = root / "workspace"
    upstream = root / "upstream"
    repository = WorkspaceRepository.create(workspace_path, "TASK-008 proof workspace")
    investigation = repository.create_investigation(
        "Storage vendor filing comparison",
        "Prepare a bounded, provenance-preserving comparison for an operator call.",
        customer="Proof customer",
        engagement="Call preparation",
    )
    question = "Compare Seagate and Western Digital annual filings"
    first_executor = executor(upstream / "first")
    first_record = first_executor.execute(InformationNeed(question))
    first_id = repository.begin_execution(
        investigation.investigation_id,
        question,
        {"planner": "deterministic", "reasoner": "deterministic", "run": 1},
    )
    repository.complete_execution(
        investigation.investigation_id,
        first_id,
        first_record,
        OperationalMetrics(
            execution_ms=12,
            planning_ms=2,
            retrieval_ms=6,
            model_ms=4,
            evidence_bytes=sum(item.bytes_used for item in first_record.trace.evidence_packages),
            retrieval_count=len(first_record.trace.retrieval_queries),
            iteration_count=first_record.trace.iterations,
            model_calls=1,
            input_tokens=150,
            output_tokens=42,
            estimated_cost=0.013,
            cost_currency="USD",
        ),
    )
    reopened = WorkspaceRepository.open(workspace_path)
    annotation_id = reopened.add_annotation(
        investigation.investigation_id,
        AnnotationKind.INTERPRETATION,
        "The corpus supports filing-coverage comparison, not performance conclusions.",
        first_id,
    )
    second_executor = executor(upstream / "second", alternate=True)
    second_record = second_executor.execute(InformationNeed(question))
    second_id = reopened.begin_execution(
        investigation.investigation_id,
        question,
        {"planner": "deterministic-alternate", "reasoner": "deterministic-alternate"},
    )
    reopened.complete_execution(
        investigation.investigation_id,
        second_id,
        second_record,
        OperationalMetrics(
            execution_ms=15,
            planning_ms=3,
            retrieval_ms=7,
            model_ms=5,
            evidence_bytes=sum(item.bytes_used for item in second_record.trace.evidence_packages),
            retrieval_count=len(second_record.trace.retrieval_queries),
            iteration_count=second_record.trace.iterations,
        ),
    )
    comparison = reopened.compare(first_id, second_id)
    insufficient_id = WorkspaceService(reopened, first_executor).execute(
        investigation.investigation_id,
        "What revenue did Seagate report in its annual filing?",
    )

    planner_executor = IntelligenceOrchestrator(
        BadPlanner(), DeterministicReasoner(), FailingGateway()
    )
    planner_id = WorkspaceService(reopened, planner_executor).execute(
        investigation.investigation_id, "Planner failure proof"
    )
    retrieval_executor = IntelligenceOrchestrator(
        DeterministicPlanner(), DeterministicReasoner(), FailingGateway()
    )
    retrieval_id = WorkspaceService(reopened, retrieval_executor).execute(
        investigation.investigation_id, "Seagate annual filing"
    )
    model_executor = IntelligenceOrchestrator(
        DeterministicPlanner(), BadReasoner(),
        PackageGateway(
            first_executor.gateway.retrieve,
            lambda package: package,
        ),
    )
    model_id = WorkspaceService(reopened, model_executor).execute(
        investigation.investigation_id, "Seagate annual filing"
    )
    interrupted_id = reopened.begin_execution(
        investigation.investigation_id, "Interrupted execution proof"
    )
    open_before_recovery = reopened.verify().open_executions
    reopened.fail_execution(
        investigation.investigation_id,
        interrupted_id,
        "operator terminated execution",
        interrupted=True,
    )

    event_count = len(reopened.events())
    try:
        reopened._append(
            "partial-proof", investigation.investigation_id, {}, simulate_partial=True
        )
    except WorkspaceError:
        partial_visible = not reopened.verify().valid
    else:
        partial_visible = False
    quarantined = reopened.recover_partial_writes()
    partial_recovered = reopened.verify().valid and len(reopened.events()) == event_count

    invalid_annotation_visible = False
    try:
        reopened.add_annotation(
            investigation.investigation_id, AnnotationKind.OBSERVATION, ""
        )
    except WorkspaceError:
        invalid_annotation_visible = True

    export = reopened.export(investigation.investigation_id)
    backup_failure_visible = False
    try:
        reopened.backup(workspace_path / "invalid.zip")
    except WorkspaceError:
        backup_failure_visible = True
    backup = reopened.backup(root / "workspace-backup.zip")
    backup_integrity = WorkspaceRepository.verify_backup(backup)
    restored = WorkspaceRepository.restore(backup, root / "restored-workspace")
    restore_failure_visible = False
    try:
        WorkspaceRepository.restore(backup, root / "restored-workspace")
    except WorkspaceError:
        restore_failure_visible = True

    corrupt_copy = WorkspaceRepository.restore(backup, root / "corrupt-workspace")
    first_event = next(corrupt_copy.journal_root.glob("*.json"))
    first_event.write_text(first_event.read_text() + "corruption", encoding="utf-8")
    corruption_visible = not corrupt_copy.verify().valid

    diagnostic = io.StringIO()
    reopened.diagnostic(
        diagnostic,
        "model-failure",
        {"api_key": "must-not-appear", "failure": "provider unavailable"},
    )
    diagnostic_payload = diagnostic.getvalue().strip()
    execution_views = {
        "insufficient": reopened.execution(insufficient_id),
        "planner_failure": reopened.execution(planner_id),
        "retrieval_failure_or_stale_index": reopened.execution(retrieval_id),
        "model_failure": reopened.execution(model_id),
        "interrupted": reopened.execution(interrupted_id),
    }
    checks = {
        "create_execute_persist_reopen": bool(reopened.execution(first_id)["terminal"]),
        "evidence_references_inspectable": bool(
            reopened.execution(first_id)["terminal"]["payload"]["record"]["packages"]
        ),
        "operator_annotation_distinct": annotation_id.startswith("annotation-"),
        "rerun_comparison": comparison.evidence_changed is False,
        "reasoning_or_conclusion_change_visible": (
            comparison.reasoning_changed or comparison.conclusions_changed
        ),
        "insufficient_evidence_visible": execution_views["insufficient"]["terminal"]
        ["payload"]["record"]["result"]["status"] == "incomplete",
        "planner_failure_visible": execution_views["planner_failure"]["terminal"]
        ["payload"]["record"]["result"]["status"] == "failed",
        "retrieval_and_stale_index_visible": bool(
            execution_views["retrieval_failure_or_stale_index"]["terminal"]
            ["payload"]["record"]["trace"]["failures"]
        ),
        "model_failure_visible": execution_views["model_failure"]["terminal"]
        ["payload"]["record"]["result"]["status"] == "failed",
        "interruption_recoverable": interrupted_id in open_before_recovery,
        "partial_write_visible_and_recoverable": partial_visible and partial_recovered,
        "invalid_annotation_visible": invalid_annotation_visible,
        "export_complete": export.is_file(),
        "backup_failure_visible": backup_failure_visible,
        "backup_integrity": backup_integrity.valid,
        "restore_integrity": restored.verify().valid,
        "restore_failure_visible": restore_failure_visible,
        "corruption_visible": corruption_visible,
        "diagnostic_redacted": "must-not-appear" not in diagnostic_payload,
    }
    if not all(checks.values()):
        raise RuntimeError(f"TASK-008 proof invariant failed: {checks}")
    return {
        "result": "PASS",
        "workspace": asdict(reopened.investigation(investigation.investigation_id)),
        "journal": [asdict(item) for item in reopened.events(investigation.investigation_id)],
        "first_execution": reopened.execution(first_id),
        "comparison": asdict(comparison),
        "operational_metrics": reopened.metrics(investigation.investigation_id),
        "failure_proofs": execution_views,
        "partial_write_quarantine": quarantined,
        "export": {
            "path": export.as_posix(),
            "sha256": hashlib.sha256(export.read_bytes()).hexdigest(),
            "content": export.read_text(encoding="utf-8"),
        },
        "backup": {
            "path": backup.as_posix(),
            "integrity": asdict(backup_integrity),
        },
        "restore_integrity": asdict(restored.verify()),
        "logging": {
            "durable_events": len(reopened.events()),
            "transient_redacted_example": diagnostic_payload,
            "journal_retention": "indefinite-reference-snapshots",
            "diagnostic_retention": "transient-only",
        },
        "checks": checks,
    }


def repository(path: Path) -> WorkspaceRepository:
    """Open an existing verified workspace."""
    return WorkspaceRepository.open(path)


def main() -> int:
    """Dispatch proof and stable JSON operator commands."""
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)
    proof_parser = subparsers.add_parser("fixture-proof")
    proof_parser.add_argument("--state", type=Path)
    create_workspace = subparsers.add_parser("init")
    create_workspace.add_argument("--workspace", type=Path, required=True)
    create_workspace.add_argument("--title", default="RFI consulting workspace")
    create = subparsers.add_parser("create")
    create.add_argument("--workspace", type=Path, required=True)
    create.add_argument("--title", required=True)
    create.add_argument("--purpose", required=True)
    list_parser = subparsers.add_parser("list")
    list_parser.add_argument("--workspace", type=Path, required=True)
    show = subparsers.add_parser("show")
    show.add_argument("--workspace", type=Path, required=True)
    show.add_argument("--investigation", required=True)
    note = subparsers.add_parser("note")
    note.add_argument("--workspace", type=Path, required=True)
    note.add_argument("--investigation", required=True)
    note.add_argument("--kind", choices=[item.value for item in AnnotationKind], required=True)
    note.add_argument("--text", required=True)
    compare = subparsers.add_parser("compare")
    compare.add_argument("--workspace", type=Path, required=True)
    compare.add_argument("--first", required=True)
    compare.add_argument("--second", required=True)
    export = subparsers.add_parser("export")
    export.add_argument("--workspace", type=Path, required=True)
    export.add_argument("--investigation", required=True)
    verify = subparsers.add_parser("verify")
    verify.add_argument("--workspace", type=Path, required=True)
    backup = subparsers.add_parser("backup")
    backup.add_argument("--workspace", type=Path, required=True)
    backup.add_argument("--destination", type=Path, required=True)
    restore = subparsers.add_parser("restore")
    restore.add_argument("--backup", type=Path, required=True)
    restore.add_argument("--destination", type=Path, required=True)
    args = parser.parse_args()

    if args.command == "fixture-proof":
        if args.state:
            payload = fixture_proof(args.state)
        else:
            with tempfile.TemporaryDirectory(prefix="rfi-task008-") as temporary:
                payload = fixture_proof(Path(temporary))
    elif args.command == "init":
        payload = asdict(WorkspaceRepository.create(args.workspace, args.title).verify())
    elif args.command == "create":
        payload = asdict(
            repository(args.workspace).create_investigation(args.title, args.purpose)
        )
    elif args.command == "list":
        payload = [asdict(item) for item in repository(args.workspace).investigations()]
    elif args.command == "show":
        active = repository(args.workspace)
        payload = {
            "investigation": asdict(active.investigation(args.investigation)),
            "events": [asdict(item) for item in active.events(args.investigation)],
        }
    elif args.command == "note":
        active = repository(args.workspace)
        payload = {
            "annotation_id": active.add_annotation(
                args.investigation, AnnotationKind(args.kind), args.text
            )
        }
    elif args.command == "compare":
        payload = asdict(repository(args.workspace).compare(args.first, args.second))
    elif args.command == "export":
        payload = {
            "path": repository(args.workspace).export(args.investigation).as_posix()
        }
    elif args.command == "verify":
        payload = asdict(repository(args.workspace).verify())
    elif args.command == "backup":
        payload = {"path": repository(args.workspace).backup(args.destination).as_posix()}
    else:
        payload = asdict(WorkspaceRepository.restore(args.backup, args.destination).verify())
    print(json.dumps(payload, indent=2, sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
