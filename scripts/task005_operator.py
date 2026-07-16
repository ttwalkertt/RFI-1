#!/usr/bin/env python3
"""Build, inspect, and prove TASK-005 source and knowledge subsystems."""

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
from rfi.knowledge import KnowledgeRepository  # noqa: E402
from rfi.source_objects import SourceInput, SourceObjectRepository  # noqa: E402


def canonical(value: Any) -> str:
    """Render stable operator output."""
    return json.dumps(value, indent=2, sort_keys=True)


def acquisition_inputs(root: Path) -> list[SourceInput]:
    """Adapt public acquisition contracts to source construction inputs."""
    repository = AcquisitionRepository(root)
    documents = repository.document_index()["documents"]
    inputs: list[SourceInput] = []
    for document_id, record in sorted(documents.items()):
        artifacts = record["artifacts"]
        if len(artifacts) != 1:
            raise RuntimeError(f"bounded proof requires one current artifact: {document_id}")
        artifact_id = artifacts[0]
        inputs.append(SourceInput(document_id, artifact_id, repository.read_artifact(artifact_id)))
    return inputs


def fixture_inputs() -> list[SourceInput]:
    """Return two offline SEC fixtures under distinct repository document identities."""
    paths = [
        ROOT / "fixtures/knowledge/stx-submission.txt",
        ROOT / "fixtures/knowledge/wdc-submission.txt",
    ]
    inputs: list[SourceInput] = []
    for number, path in enumerate(paths, start=1):
        content = path.read_bytes()
        inputs.append(
            SourceInput(
                f"document-task005-fixture-{number}",
                f"artifact-{hashlib.sha256(content).hexdigest()}",
                content,
            )
        )
    return inputs


def proof(inputs: list[SourceInput], state: Path) -> dict[str, Any]:
    """Run both-direction provenance and independent rebuild proof."""
    source = SourceObjectRepository(state / "source-objects/catalog.sqlite")
    knowledge = KnowledgeRepository(state / "derived-knowledge")
    source_first = source.rebuild(inputs)
    knowledge_first = knowledge.rebuild(source)
    source_ids = [item.source_object_id for item in source.inventory()]
    object_versions = {
        item.object_id: item.version_id for item in knowledge.inventory()
    }
    derived_example = next(
        item for item in knowledge.inventory() if item.object_type == "observation"
    )
    reference = derived_example.provenance[0]
    supporting = source.get(reference.source_object_id)
    reverse = knowledge.by_source_object(reference.source_object_id)
    source_second = source.rebuild(inputs)
    source_identity_preserved = source_ids == [
        item.source_object_id for item in source.inventory()
    ]
    knowledge_valid_after_source_rebuild = knowledge.verify(source)["result"] == "PASS"
    knowledge_second = knowledge.rebuild(source)
    knowledge_identity_preserved = object_versions == {
        item.object_id: item.version_id for item in knowledge.inventory()
    }
    content_by_artifact = {item.artifact_id: item.content for item in inputs}
    outcomes = source.parse_outcomes()
    inventory = knowledge.inventory()
    result = {
        "result": "PASS",
        "bounded_corpus": {
            "documents": len(inputs),
            "artifacts": len({item.artifact_id for item in inputs}),
            "bytes": sum(len(item.content) for item in inputs),
        },
        "source_objects": {
            "first_rebuild": asdict(source_first),
            "second_rebuild": asdict(source_second),
            "by_kind": count_by([item.kind for item in source.inventory()]),
            "by_role": count_by([item.role for item in source.inventory()]),
            "parse_status": count_by([item["status"] for item in outcomes]),
            "integrity": source.verify(content_by_artifact),
        },
        "derived_knowledge": {
            "first_rebuild": knowledge_first,
            "second_rebuild": knowledge_second,
            "by_type": count_by([item.object_type for item in inventory]),
            "by_status": count_by([item.status.value for item in inventory]),
            "integrity": knowledge.verify(source),
        },
        "provenance_example": {
            "derived_object": asdict(derived_example),
            "supporting_source_object": asdict(supporting),
            "immutable_artifact": {
                "artifact_id": supporting.artifact_id,
                "byte_start": supporting.byte_start,
                "byte_end": supporting.byte_end,
                "content_sha256": supporting.content_sha256,
            },
            "reverse_derived_object_ids": [item.object_id for item in reverse],
        },
        "independent_rebuild": {
            "source_identity_preserved": source_identity_preserved,
            "knowledge_valid_after_source_rebuild": knowledge_valid_after_source_rebuild,
            "knowledge_identity_preserved": knowledge_identity_preserved,
            "separate_storage": {
                "source_objects": str(source.path),
                "derived_knowledge": str(knowledge.root),
            },
        },
    }
    checks = result["independent_rebuild"]
    if not all(value is True for key, value in checks.items() if key != "separate_storage"):
        raise RuntimeError("independent rebuild proof failed")
    return result


def count_by(values: list[str]) -> dict[str, int]:
    """Count string values in stable key order."""
    return {value: values.count(value) for value in sorted(set(values))}


def repositories(state: Path) -> tuple[SourceObjectRepository, KnowledgeRepository]:
    """Open both stores without coupling their implementations."""
    return (
        SourceObjectRepository(state / "source-objects/catalog.sqlite"),
        KnowledgeRepository(state / "derived-knowledge"),
    )


def main() -> int:
    """Dispatch construction, proof, and console inspection commands."""
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "command",
        choices=(
            "fixture-proof",
            "real-proof",
            "source-inventory",
            "knowledge-inventory",
            "verify",
        ),
    )
    parser.add_argument("--state", type=Path)
    parser.add_argument("--acquisition-state", type=Path)
    arguments = parser.parse_args()
    if arguments.command == "fixture-proof":
        if arguments.state:
            print(canonical(proof(fixture_inputs(), arguments.state)))
        else:
            with tempfile.TemporaryDirectory(prefix="rfi-task005-") as temporary:
                print(canonical(proof(fixture_inputs(), Path(temporary))))
        return 0
    if arguments.state is None:
        parser.error("--state is required for this command")
    if arguments.command == "real-proof":
        if arguments.acquisition_state is None:
            parser.error("--acquisition-state is required for real-proof")
        print(canonical(proof(acquisition_inputs(arguments.acquisition_state), arguments.state)))
        return 0
    source, knowledge = repositories(arguments.state)
    if arguments.command == "source-inventory":
        print(canonical([asdict(item) for item in source.inventory()]))
    elif arguments.command == "knowledge-inventory":
        print(canonical([asdict(item) for item in knowledge.inventory()]))
    else:
        print(canonical({"source": source.verify(), "knowledge": knowledge.verify(source)}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
