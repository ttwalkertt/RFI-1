#!/usr/bin/env python3
"""Build, browse, retrieve, assemble, and prove the TASK-006 access subsystem."""

from __future__ import annotations

import argparse
import hashlib
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

from rfi.acquisition import AcquisitionRepository  # noqa: E402
from rfi.knowledge import KnowledgeRepository, KnowledgeStatus  # noqa: E402
from rfi.retrieval import (  # noqa: E402
    CharacterNgramVectorizer,
    EvidenceAssembler,
    MetadataConstraints,
    ResultClass,
    RetrievalError,
    RetrievalQuery,
    RetrievalRepository,
    compare_evidence_packages,
)
from rfi.source_objects import SourceInput, SourceObjectRepository  # noqa: E402


def canonical(value: Any) -> str:
    """Render stable operator output from repository-owned contracts."""
    return json.dumps(value, indent=2, sort_keys=True)


class InputArtifacts:
    """Exact artifact reader for offline proof inputs."""

    def __init__(self, inputs: list[SourceInput]) -> None:
        self.content = {item.artifact_id: item.content for item in inputs}

    def read_artifact(self, artifact_id: str) -> bytes:
        """Return exact proof bytes by immutable identity."""
        if artifact_id not in self.content:
            raise RetrievalError(f"proof artifact is absent: {artifact_id}")
        return self.content[artifact_id]


def fixture_inputs() -> list[SourceInput]:
    """Return the checked two-issuer offline SEC proof corpus."""
    paths = (
        ROOT / "fixtures/knowledge/stx-submission.txt",
        ROOT / "fixtures/knowledge/wdc-submission.txt",
    )
    result: list[SourceInput] = []
    for number, path in enumerate(paths, start=1):
        content = path.read_bytes()
        result.append(
            SourceInput(
                f"document-task006-fixture-{number}",
                f"artifact-{hashlib.sha256(content).hexdigest()}",
                content,
            )
        )
    return result


def acquisition_inputs(root: Path) -> list[SourceInput]:
    """Adapt the public acquisition repository contract to source construction."""
    repository = AcquisitionRepository(root)
    result: list[SourceInput] = []
    for document_id, record in sorted(repository.document_index()["documents"].items()):
        artifact_ids = record["artifacts"]
        if len(artifact_ids) != 1:
            raise RuntimeError(f"proof requires one artifact per document: {document_id}")
        artifact_id = artifact_ids[0]
        result.append(
            SourceInput(document_id, artifact_id, repository.read_artifact(artifact_id))
        )
    return result


def repositories(
    state: Path,
) -> tuple[SourceObjectRepository, KnowledgeRepository, RetrievalRepository]:
    """Open three independent stores through their public repository types."""
    source = SourceObjectRepository(state / "source-objects/catalog.sqlite")
    knowledge = KnowledgeRepository(state / "derived-knowledge")
    retrieval = RetrievalRepository(state / "retrieval", source, knowledge)
    return source, knowledge, retrieval


def proof(
    inputs: list[SourceInput],
    state: Path,
    acquisition: AcquisitionRepository | None = None,
) -> dict[str, Any]:
    """Run the functional, inspection, rebuild, replaceability, and failure proofs."""
    source, knowledge, retrieval = repositories(state)
    source_result = source.rebuild(inputs)
    knowledge_result = knowledge.rebuild(source)
    first = retrieval.rebuild()
    artifacts = InputArtifacts(inputs)
    source_query = RetrievalQuery(
        "central index key Seagate",
        result_classes=(ResultClass.SOURCE_EVIDENCE,),
        constraints=MetadataConstraints(entity_ids=("1137789",)),
        max_results=5,
    )
    knowledge_query = RetrievalQuery(
        "Seagate issuer filing",
        result_classes=(ResultClass.DERIVED_KNOWLEDGE,),
        constraints=MetadataConstraints(entity_ids=("1137789",)),
        max_results=5,
    )
    combined_query = RetrievalQuery(
        "Seagate annual report",
        constraints=MetadataConstraints(
            entity_ids=("1137789",), document_types=("10-K",)
        ),
        max_results=8,
        candidate_limit=30,
        context_radius=96,
        evidence_budget_bytes=20_000,
    )
    empty_query = RetrievalQuery(
        "foreign annual report",
        constraints=MetadataConstraints(document_types=("20-F",)),
        max_results=5,
    )
    bounded_query = RetrievalQuery(
        "issuer filing evidence",
        max_results=1,
        candidate_limit=20,
        evidence_budget_bytes=4_000,
    )
    budget_query = RetrievalQuery(
        "Seagate issuer filing evidence",
        max_results=5,
        candidate_limit=20,
        context_radius=100,
        evidence_budget_bytes=100,
    )
    deterministic_source_query = RetrievalQuery(
        "central index key",
        result_classes=(ResultClass.SOURCE_EVIDENCE,),
        constraints=MetadataConstraints(
            entity_ids=("1137789",),
            document_types=("10-K",),
            source_roles=("central-index-key",),
        ),
        max_results=10,
        minimum_score=0.0,
    )
    deterministic_knowledge_query = RetrievalQuery(
        "Seagate issuer",
        result_classes=(ResultClass.DERIVED_KNOWLEDGE,),
        constraints=MetadataConstraints(
            entity_ids=("1137789",), knowledge_types=("entity",)
        ),
        max_results=10,
        minimum_score=0.0,
    )
    source_response = retrieval.search(source_query)
    knowledge_response = retrieval.search(knowledge_query)
    combined_response = retrieval.search(combined_query)
    empty_response = retrieval.search(empty_query)
    bounded_response = retrieval.search(bounded_query)
    assembler = EvidenceAssembler(source, artifacts)
    package = assembler.assemble(combined_response)
    bounded_package = assembler.assemble(bounded_response)
    budget_package = assembler.assemble(retrieval.search(budget_query))
    deterministic_source_package = assembler.assemble(
        retrieval.search(deterministic_source_query)
    )
    deterministic_knowledge_package = assembler.assemble(
        retrieval.search(deterministic_knowledge_query)
    )
    second = retrieval.rebuild()
    before_failure = json.loads(retrieval.pointer.read_text())["generation_id"]
    atomic_failure = "not-run"
    try:
        retrieval.rebuild(fail_before_publish=True)
    except RetrievalError as error:
        atomic_failure = str(error)
    after_failure = json.loads(retrieval.pointer.read_text())["generation_id"]
    with tempfile.TemporaryDirectory(prefix=".task006-failures-", dir=state) as temporary:
        failure_root = Path(temporary)
        alternative = RetrievalRepository(
            failure_root / "alternative",
            source,
            knowledge,
            CharacterNgramVectorizer(),
        )
        alternative.rebuild()
        alternative_assembler = EvidenceAssembler(source, artifacts)
        alternative_package = alternative_assembler.assemble(
            alternative.search(combined_query)
        )
        alternative_bounded_package = alternative_assembler.assemble(
            alternative.search(bounded_query)
        )
        alternative_budget_package = alternative_assembler.assemble(
            alternative.search(budget_query)
        )
        alternative_source_package = alternative_assembler.assemble(
            alternative.search(deterministic_source_query)
        )
        alternative_knowledge_package = alternative_assembler.assemble(
            alternative.search(deterministic_knowledge_query)
        )
        contract_comparison = compare_evidence_packages(
            package,
            alternative_package,
            source,
            artifacts,
            require_both_classes=True,
        )
        deterministic_source_comparison = compare_evidence_packages(
            deterministic_source_package,
            alternative_source_package,
            source,
            artifacts,
            require_same_selection=True,
        )
        deterministic_knowledge_comparison = compare_evidence_packages(
            deterministic_knowledge_package,
            alternative_knowledge_package,
            source,
            artifacts,
            require_same_selection=True,
        )
        budget_comparison = compare_evidence_packages(
            budget_package,
            alternative_budget_package,
            source,
            artifacts,
            require_budget_reporting=True,
        )
        truncation_comparison = compare_evidence_packages(
            bounded_package,
            alternative_bounded_package,
            source,
            artifacts,
            require_truncation_reporting=True,
        )
        corrupt = RetrievalRepository(failure_root / "corrupt", source, knowledge)
        corrupt_result = corrupt.rebuild()
        corrupt_path = (
            corrupt.generations / str(corrupt_result["generation_id"]) / "index.json"
        )
        corrupt_path.write_text("{}\n", encoding="utf-8")
        corrupt_health = asdict(corrupt.health())
        missing_health = asdict(
            RetrievalRepository(failure_root / "missing", source, knowledge).health()
        )
    conflict_comparison = conflict_replaceability_proof()
    observation = next(
        item for item in knowledge.inventory() if item.object_type == "observation"
    )
    provenance = [source.get(item.source_object_id) for item in observation.provenance]
    reverse = knowledge.by_source_object(observation.provenance[0].source_object_id)
    excluded = [item for item in combined_response.trace.decisions if not item.included]
    result = {
        "result": "PASS",
        "bounded_corpus": {
            "documents": len(inputs),
            "artifacts": len({item.artifact_id for item in inputs}),
            "bytes": sum(len(item.content) for item in inputs),
        },
        "authoritative_subsystems": {
            "source_rebuild": asdict(source_result),
            "knowledge_rebuild": knowledge_result,
            "source_integrity": source.verify(
                {item.artifact_id: item.content for item in inputs}
            ),
            "knowledge_integrity": knowledge.verify(source),
        },
        "governed_retrieval": {
            "index_rebuild": first,
            "health": asdict(retrieval.health()),
            "source_result_ids": [
                item.source_object.source_object_id
                for item in source_response.source_results
            ],
            "knowledge_result_ids": [
                item.derived_object.object_id
                for item in knowledge_response.knowledge_results
            ],
            "combined": asdict(combined_response),
            "empty_result": asdict(empty_response),
            "bounded_result": asdict(bounded_response),
        },
        "evidence_package": asdict(package),
        "bounded_evidence_package": asdict(bounded_package),
        "budget_evidence_package": asdict(budget_package),
        "inspection_workflow": {
            "governed_sources": acquisition.sources() if acquisition else ["offline-fixtures"],
            "repository_documents": (
                acquisition.document_index()["documents"]
                if acquisition
                else {
                    item.document_id: {"artifacts": [item.artifact_id]}
                    for item in inputs
                }
            ),
            "immutable_artifacts": (
                acquisition.artifact_metadata()
                if acquisition
                else [
                    {
                        "artifact_id": item.artifact_id,
                        "sha256": item.artifact_id.removeprefix("artifact-"),
                        "size": len(item.content),
                    }
                    for item in inputs
                ]
            ),
            "source_inventory_count": len(source.inventory()),
            "knowledge_inventory_count": len(knowledge.inventory()),
            "derived_to_source": {
                "derived": asdict(observation),
                "sources": [asdict(item) for item in provenance],
            },
            "source_to_derived": {
                "source_object_id": observation.provenance[0].source_object_id,
                "derived": [asdict(item) for item in reverse],
            },
            "included_reason": next(
                item.reason
                for item in combined_response.trace.decisions
                if item.included
            ),
            "excluded_examples": [asdict(item) for item in excluded[:10]],
            "trace_id": combined_response.trace.trace_id,
            "evidence_package_id": package.package_id,
        },
        "rebuild_and_replaceability": {
            "generation_reproduced": first["generation_id"] == second["generation_id"],
            "failed_rebuild": atomic_failure,
            "failed_rebuild_kept_current": before_failure == after_failure,
            "alternative_vectorizer": alternative.vectorizer.name,
            "contract_level_replaceability": {
                "combined_source_and_knowledge": contract_comparison,
                "deterministic_source_selection": deterministic_source_comparison,
                "deterministic_knowledge_selection": deterministic_knowledge_comparison,
                "budget_reporting": budget_comparison,
                "truncation_and_coverage_reporting": truncation_comparison,
                "conflict_and_ambiguity_reporting": conflict_comparison,
            },
            "retrieval_storage": str(retrieval.root),
            "authoritative_storage_unchanged": {
                "source": str(source.path),
                "knowledge": str(knowledge.root),
            },
        },
        "failure_evidence": {
            "fresh_index_state": missing_health,
            "corrupt_index_state": corrupt_health,
            "empty_result_visible": not empty_response.source_results
            and not empty_response.knowledge_results,
            "bounded_truncation_visible": bounded_response.trace.truncated,
            "incomplete_coverage_visible": bool(bounded_package.coverage_gaps),
        },
    }
    checks = (
        result["rebuild_and_replaceability"]["generation_reproduced"],
        result["rebuild_and_replaceability"]["failed_rebuild_kept_current"],
        all(
            item["result"] == "PASS"
            for item in result["rebuild_and_replaceability"][
                "contract_level_replaceability"
            ].values()
        ),
        result["failure_evidence"]["empty_result_visible"],
        result["failure_evidence"]["bounded_truncation_visible"],
        result["failure_evidence"]["incomplete_coverage_visible"],
    )
    if not all(checks):
        raise RuntimeError("TASK-006 proof invariant failed")
    return result


def conflict_replaceability_proof() -> dict[str, Any]:
    """Prove that competing interpretations survive either vector implementation."""
    original = fixture_inputs()[0]
    alternate_content = original.content.replace(
        b"SEAGATE TECHNOLOGY HOLDINGS PLC", b"SEAGATE ALTERNATE LEGAL NAME"
    )
    ambiguous = SourceInput(
        "document-task006-vectorizer-conflict",
        f"artifact-{hashlib.sha256(alternate_content).hexdigest()}",
        alternate_content,
    )
    inputs = [original, ambiguous]
    artifacts = InputArtifacts(inputs)
    with tempfile.TemporaryDirectory(prefix="rfi-task006-conflict-") as temporary:
        root = Path(temporary)
        source = SourceObjectRepository(root / "source/catalog.sqlite")
        source.rebuild(inputs)
        knowledge = KnowledgeRepository(root / "knowledge")
        knowledge.rebuild(source)
        primary = RetrievalRepository(root / "primary", source, knowledge)
        alternative = RetrievalRepository(
            root / "alternative", source, knowledge, CharacterNgramVectorizer()
        )
        primary.rebuild()
        alternative.rebuild()
        query = RetrievalQuery(
            "Seagate legal name ambiguity",
            result_classes=(ResultClass.DERIVED_KNOWLEDGE,),
            constraints=MetadataConstraints(
                knowledge_types=("entity",),
                knowledge_statuses=(KnowledgeStatus.CONFLICTED,),
            ),
            max_results=5,
        )
        assembler = EvidenceAssembler(source, artifacts)
        return compare_evidence_packages(
            assembler.assemble(primary.search(query)),
            assembler.assemble(alternative.search(query)),
            source,
            artifacts,
            require_same_selection=True,
            require_conflict_reporting=True,
        )


def query_from_args(arguments: argparse.Namespace) -> RetrievalQuery:
    """Translate explicit console filters to the same contract future models will use."""
    classes = {
        "both": (ResultClass.SOURCE_EVIDENCE, ResultClass.DERIVED_KNOWLEDGE),
        "source": (ResultClass.SOURCE_EVIDENCE,),
        "knowledge": (ResultClass.DERIVED_KNOWLEDGE,),
    }[arguments.result_class]
    return RetrievalQuery(
        arguments.query,
        result_classes=classes,
        constraints=MetadataConstraints(
            document_ids=tuple(arguments.document_id),
            entity_ids=tuple(arguments.entity_id),
            document_types=tuple(arguments.document_type),
            source_kinds=tuple(arguments.source_kind),
            knowledge_types=tuple(arguments.knowledge_type),
        ),
        max_results=arguments.max_results,
        evidence_budget_bytes=arguments.budget,
    )


def main() -> int:
    """Provide a console-oriented browser over shared governed access semantics."""
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "command",
        choices=(
            "fixture-proof",
            "real-proof",
            "build",
            "health",
            "acquisition-sources",
            "documents",
            "artifacts",
            "sources",
            "source",
            "knowledge",
            "derived",
            "from-source",
            "retrieve",
            "package",
        ),
    )
    parser.add_argument("--state", type=Path)
    parser.add_argument("--acquisition-state", type=Path)
    parser.add_argument("--id")
    parser.add_argument("--query", default="issuer filing")
    parser.add_argument(
        "--class",
        dest="result_class",
        choices=("both", "source", "knowledge"),
        default="both",
    )
    parser.add_argument("--document-id", action="append", default=[])
    parser.add_argument("--entity-id", action="append", default=[])
    parser.add_argument("--document-type", action="append", default=[])
    parser.add_argument("--source-kind", action="append", default=[])
    parser.add_argument("--knowledge-type", action="append", default=[])
    parser.add_argument("--max-results", type=int, default=10)
    parser.add_argument("--budget", type=int, default=16_000)
    arguments = parser.parse_args()
    if arguments.command == "fixture-proof":
        if arguments.state:
            print(canonical(proof(fixture_inputs(), arguments.state)))
        else:
            with tempfile.TemporaryDirectory(prefix="rfi-task006-") as temporary:
                print(canonical(proof(fixture_inputs(), Path(temporary))))
        return 0
    if arguments.state is None:
        parser.error("--state is required for this command")
    if arguments.command == "real-proof":
        if arguments.acquisition_state is None:
            parser.error("--acquisition-state is required for real-proof")
        acquisition = AcquisitionRepository(arguments.acquisition_state)
        print(
            canonical(
                proof(
                    acquisition_inputs(arguments.acquisition_state),
                    arguments.state,
                    acquisition,
                )
            )
        )
        return 0
    source, knowledge, retrieval = repositories(arguments.state)
    if arguments.command in {"acquisition-sources", "documents", "artifacts"}:
        if arguments.acquisition_state is None:
            parser.error("--acquisition-state is required for acquisition inspection")
        acquisition = AcquisitionRepository(arguments.acquisition_state)
        if arguments.command == "acquisition-sources":
            print(canonical(acquisition.sources()))
        elif arguments.command == "documents":
            print(canonical(acquisition.document_index()))
        else:
            print(canonical(acquisition.artifact_metadata()))
    elif arguments.command == "build":
        print(canonical(retrieval.rebuild()))
    elif arguments.command == "health":
        print(canonical(asdict(retrieval.health())))
    elif arguments.command == "sources":
        print(canonical([asdict(item) for item in source.inventory()]))
    elif arguments.command == "knowledge":
        print(canonical([asdict(item) for item in knowledge.inventory()]))
    elif arguments.command == "source":
        if not arguments.id:
            parser.error("--id is required for source")
        item = source.get(arguments.id)
        print(
            canonical(
                {
                    "source_object": asdict(item),
                    "derived_knowledge": [
                        asdict(value)
                        for value in knowledge.by_source_object(item.source_object_id)
                    ],
                }
            )
        )
    elif arguments.command == "derived":
        if not arguments.id:
            parser.error("--id is required for derived")
        item = knowledge.get(arguments.id)
        print(
            canonical(
                {
                    "derived_knowledge": asdict(item),
                    "supporting_sources": [
                        asdict(source.get(value.source_object_id))
                        for value in item.provenance
                    ],
                }
            )
        )
    elif arguments.command == "from-source":
        if not arguments.id:
            parser.error("--id is required for from-source")
        print(
            canonical(
                [
                    asdict(item)
                    for item in knowledge.by_source_object(arguments.id)
                ]
            )
        )
    else:
        query = query_from_args(arguments)
        response = retrieval.search(query)
        if arguments.command == "retrieve":
            print(canonical(asdict(response)))
        else:
            acquisition = arguments.acquisition_state
            artifact_reader = (
                AcquisitionRepository(acquisition)
                if acquisition is not None
                else InputArtifacts(fixture_inputs())
            )
            print(
                canonical(
                    asdict(EvidenceAssembler(source, artifact_reader).assemble(response))
                )
            )
    return 0


if __name__ == "__main__":
    sys.exit(main())
