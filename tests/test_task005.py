from __future__ import annotations

import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from rfi.knowledge import (  # noqa: E402
    KnowledgeError,
    KnowledgeRepository,
    KnowledgeStatus,
)
from rfi.source_objects import (  # noqa: E402
    SourceInput,
    SourceObjectError,
    SourceObjectRepository,
)


def submission(
    cik: str = "0001137789",
    name: str = "SEAGATE TECHNOLOGY HOLDINGS PLC",
    accession: str = "0001137789-25-000157",
    include_accession: bool = True,
    close_document: bool = True,
) -> bytes:
    accession_line = f"ACCESSION NUMBER:\t\t{accession}\n" if include_accession else ""
    closing = "</DOCUMENT>\n" if close_document else ""
    return (
        f"<SEC-DOCUMENT>{accession}.txt : 20250801\n"
        f"{accession_line}"
        "CONFORMED SUBMISSION TYPE:\t10-K\n"
        "CONFORMED PERIOD OF REPORT:\t20250627\n"
        "FILED AS OF DATE:\t\t20250801\n"
        "FILER:\n"
        "\tCOMPANY DATA:\n"
        f"\t\tCOMPANY CONFORMED NAME:\t\t{name}\n"
        f"\t\tCENTRAL INDEX KEY:\t\t\t{cik}\n"
        "<DOCUMENT>\n"
        "<TYPE>10-K\n"
        "<SEQUENCE>1\n"
        "<FILENAME>report.htm\n"
        "<DESCRIPTION>ANNUAL REPORT\n"
        "<TEXT><html>bounded evidence</html></TEXT>\n"
        f"{closing}"
    ).encode()


def source_input(document: str = "document-sec-test", **values) -> SourceInput:
    content = submission(**values)
    digest = hashlib.sha256(content).hexdigest()
    return SourceInput(document, f"artifact-{digest}", content)


class SourceObjectSubsystemTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.input = source_input()
        self.repository = SourceObjectRepository(self.root / "source/catalog.sqlite")

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def test_deterministic_identity_structure_navigation_and_exact_context(self) -> None:
        first = self.repository.rebuild([self.input])
        identities = [item.source_object_id for item in self.repository.inventory()]
        second_repository = SourceObjectRepository(self.root / "replacement/catalog.sqlite")
        second = second_repository.rebuild([self.input])
        self.assertEqual(
            identities,
            [item.source_object_id for item in second_repository.inventory()],
        )
        self.assertEqual(first.objects, second.objects)
        fields = [
            item
            for item in self.repository.by_document(self.input.document_id)
            if item.kind == "field"
        ]
        cik = next(item for item in fields if item.role == "central-index-key")
        self.assertEqual(self.repository.field_value(cik.source_object_id), "0001137789")
        context = self.repository.bounded_context(cik.source_object_id, self.input.content)
        self.assertIn(b"0001137789", context)
        self.assertEqual(
            self.repository.verify({self.input.artifact_id: self.input.content})["result"], "PASS"
        )

    def test_malformed_unsupported_and_integrity_failures_are_visible(self) -> None:
        malformed = source_input(document="document-malformed", close_document=False)
        unsupported_content = b"not an SEC submission"
        unsupported = SourceInput(
            "document-unsupported",
            f"artifact-{hashlib.sha256(unsupported_content).hexdigest()}",
            unsupported_content,
        )
        result = self.repository.rebuild([malformed, unsupported])
        self.assertEqual(result.incomplete, 1)
        self.assertEqual(result.unsupported, 1)
        self.assertEqual(
            {item["status"] for item in self.repository.parse_outcomes()},
            {"incomplete", "unsupported"},
        )
        self.repository.rebuild([self.input])
        with self.assertRaises(SourceObjectError):
            self.repository.verify({self.input.artifact_id: b"corrupt"})

    def test_partial_rebuild_failure_does_not_replace_current_catalog(self) -> None:
        self.repository.rebuild([self.input])
        before = [item.source_object_id for item in self.repository.inventory()]
        with self.assertRaises(SourceObjectError):
            self.repository.rebuild([source_input(document="document-new")], True)
        self.assertEqual(before, [item.source_object_id for item in self.repository.inventory()])

    def test_input_artifact_identity_must_match_exact_content(self) -> None:
        invalid = SourceInput(self.input.document_id, self.input.artifact_id, b"different")
        with self.assertRaises(SourceObjectError):
            self.repository.rebuild([invalid])


class DerivedKnowledgeSubsystemTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.inputs = [
            source_input(),
            source_input(
                document="document-sec-second",
                accession="0001137789-25-000317",
            ),
        ]
        self.source = SourceObjectRepository(self.root / "source/catalog.sqlite")
        self.source.rebuild(self.inputs)
        self.knowledge = KnowledgeRepository(self.root / "knowledge")

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def test_entities_observations_relationships_and_bidirectional_provenance(self) -> None:
        result = self.knowledge.rebuild(self.source)
        self.assertEqual(result["objects"], 5)
        inventory = self.knowledge.inventory()
        self.assertEqual(
            {item.object_type for item in inventory}, {"entity", "observation", "relationship"}
        )
        observation = next(item for item in inventory if item.object_type == "observation")
        reference = observation.provenance[0]
        source_object = self.source.get(reference.source_object_id)
        self.assertEqual(source_object.artifact_id, reference.artifact_id)
        self.assertIn(observation.object_id, {
            item.object_id for item in self.knowledge.by_source_object(reference.source_object_id)
        })
        self.assertEqual(self.knowledge.verify(self.source)["result"], "PASS")

    def test_independent_rebuilds_preserve_identity_and_provenance(self) -> None:
        first = self.knowledge.rebuild(self.source)
        object_versions = {
            item.object_id: item.version_id for item in self.knowledge.inventory()
        }
        self.source.path.unlink()
        self.source.rebuild(self.inputs)
        self.assertEqual(self.knowledge.verify(self.source)["result"], "PASS")
        second = self.knowledge.rebuild(self.source)
        self.assertEqual(first["generation_id"], second["generation_id"])
        self.assertEqual(
            object_versions,
            {item.object_id: item.version_id for item in self.knowledge.inventory()},
        )

    def test_correction_is_versioned_and_prior_version_is_superseded(self) -> None:
        self.knowledge.rebuild(self.source)
        observation = next(
            item for item in self.knowledge.inventory() if item.object_type == "observation"
        )
        payload = dict(observation.payload)
        payload["review_note"] = "operator-confirmed"
        corrected = self.knowledge.correct(
            observation.object_id,
            payload,
            KnowledgeStatus.CONFIRMED,
            "reviewed against filing header",
        )
        self.assertEqual(corrected.supersedes_version_id, observation.version_id)
        versions = [
            item
            for item in self.knowledge.inventory(include_superseded=True)
            if item.object_id == observation.object_id
        ]
        self.assertEqual(len(versions), 2)
        self.assertEqual(self.knowledge.get(observation.object_id).version_id, corrected.version_id)

    def test_ambiguity_incomplete_derivation_and_provenance_loss_fail_closed(self) -> None:
        ambiguous = source_input(
            document="document-ambiguous", name="SEAGATE ALTERNATE LEGAL NAME"
        )
        incomplete = source_input(document="document-incomplete", include_accession=False)
        self.source.rebuild([self.inputs[0], ambiguous, incomplete])
        self.knowledge.rebuild(self.source)
        entity = next(item for item in self.knowledge.inventory() if item.object_type == "entity")
        self.assertEqual(entity.status, KnowledgeStatus.CONFLICTED)
        categories = {item.category for item in self.knowledge.failures()}
        self.assertEqual(
            categories, {"ambiguous-entity-resolution", "incomplete-extraction"}
        )
        self.source.rebuild([incomplete])
        with self.assertRaises(KnowledgeError):
            self.knowledge.verify(self.source)

    def test_partial_knowledge_rebuild_keeps_current_generation(self) -> None:
        initial = self.knowledge.rebuild(self.source)
        with self.assertRaises(KnowledgeError):
            self.knowledge.rebuild(self.source, fail_before_publish=True)
        pointer = json.loads(self.knowledge.pointer.read_text())
        self.assertEqual(pointer["generation_id"], initial["generation_id"])

    def test_storage_and_import_boundaries_are_independent(self) -> None:
        source_code = (SRC / "rfi/source_objects/repository.py").read_text()
        knowledge_code = (SRC / "rfi/knowledge/repository.py").read_text()
        self.assertNotIn("rfi.knowledge", source_code)
        self.assertNotIn("sqlite3", knowledge_code)
        self.assertNotEqual(self.source.path.parent, self.knowledge.root)


if __name__ == "__main__":
    unittest.main()
