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

from rfi.knowledge import KnowledgeRepository, KnowledgeStatus  # noqa: E402
from rfi.retrieval import (  # noqa: E402
    CharacterNgramVectorizer,
    EvidenceAssembler,
    MetadataConstraints,
    ResultClass,
    RetrievalError,
    RetrievalQuery,
    RetrievalRepository,
    RetrievalState,
    compare_evidence_packages,
    evidence_contract_schema,
)
from rfi.source_objects import SourceInput, SourceObjectRepository  # noqa: E402


def fixture_input(path: str, document_id: str) -> SourceInput:
    content = (ROOT / path).read_bytes()
    return SourceInput(
        document_id,
        f"artifact-{hashlib.sha256(content).hexdigest()}",
        content,
    )


class ArtifactMap:
    def __init__(self, inputs: list[SourceInput]) -> None:
        self.items = {item.artifact_id: item.content for item in inputs}

    def read_artifact(self, artifact_id: str) -> bytes:
        return self.items[artifact_id]


class FailingVectorizer:
    @property
    def name(self) -> str:
        return "always-fails-v1"

    def vector(self, text: str) -> tuple[float, ...]:
        raise RuntimeError("injected embedding outage")


class GovernedRetrievalTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.inputs = [
            fixture_input(
                "fixtures/knowledge/stx-submission.txt", "document-task006-stx"
            ),
            fixture_input(
                "fixtures/knowledge/wdc-submission.txt", "document-task006-wdc"
            ),
        ]
        self.source = SourceObjectRepository(self.root / "source/catalog.sqlite")
        self.source.rebuild(self.inputs)
        self.knowledge = KnowledgeRepository(self.root / "knowledge")
        self.knowledge.rebuild(self.source)
        self.retrieval = RetrievalRepository(
            self.root / "retrieval", self.source, self.knowledge
        )
        self.rebuild = self.retrieval.rebuild()
        self.artifacts = ArtifactMap(self.inputs)

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def test_source_and_knowledge_vector_retrieval_with_metadata(self) -> None:
        query = RetrievalQuery(
            "Seagate annual report 10-K",
            constraints=MetadataConstraints(
                entity_ids=("1137789",), document_types=("10-K",)
            ),
            max_results=12,
            candidate_limit=20,
        )
        response = self.retrieval.search(query)
        self.assertTrue(response.source_results)
        self.assertTrue(response.knowledge_results)
        self.assertTrue(
            all(
                item.result_class == ResultClass.SOURCE_EVIDENCE
                for item in response.source_results
            )
        )
        self.assertTrue(
            all(
                item.result_class == ResultClass.DERIVED_KNOWLEDGE
                for item in response.knowledge_results
            )
        )
        excluded = [item for item in response.trace.decisions if not item.included]
        self.assertTrue(any(item.reason.startswith("metadata:") for item in excluded))
        self.assertEqual(response.trace.failures, ())

    def test_deterministic_filtering_empty_results_and_unsupported_constraint(self) -> None:
        query = RetrievalQuery(
            "annual report",
            constraints=MetadataConstraints(document_types=("20-F",)),
            max_results=5,
        )
        first = self.retrieval.search(query)
        second = self.retrieval.search(query)
        self.assertEqual(first, second)
        self.assertFalse(first.source_results)
        self.assertFalse(first.knowledge_results)
        self.assertIn("no candidate", first.trace.coverage_notes[0])
        with self.assertRaisesRegex(RetrievalError, "unsupported metadata"):
            self.retrieval.search(
                RetrievalQuery(
                    "test",
                    constraints=MetadataConstraints(unsupported=("sentiment",)),
                )
            )

    def test_bounded_results_trace_and_deduplicated_context_expansion(self) -> None:
        response = self.retrieval.search(
            RetrievalQuery(
                "filing issuer report",
                result_classes=(ResultClass.DERIVED_KNOWLEDGE,),
                max_results=2,
                candidate_limit=10,
                context_radius=32,
            )
        )
        self.assertEqual(len(response.knowledge_results), 2)
        self.assertTrue(response.trace.truncated)
        self.assertTrue(
            any(item.reason == "result-limit" for item in response.trace.decisions)
        )
        package = EvidenceAssembler(self.source, self.artifacts).assemble(response)
        provenance_count = sum(
            len(item.derived_object.provenance) for item in package.derived_knowledge
        )
        self.assertLessEqual(len(package.contexts), provenance_count)
        self.assertTrue(
            all(
                item.context_byte_start <= item.provenance.byte_start
                and item.context_byte_end >= item.provenance.byte_end
                for item in package.contexts
            )
        )

    def test_evidence_budget_and_missing_artifact_failures_are_visible(self) -> None:
        response = self.retrieval.search(
            RetrievalQuery(
                "Seagate",
                max_results=5,
                evidence_budget_bytes=100,
                context_radius=100,
            )
        )
        package = EvidenceAssembler(self.source, self.artifacts).assemble(response)
        self.assertTrue(package.omissions)
        self.assertFalse(package.complete)
        self.assertLessEqual(package.bytes_used, package.byte_budget)
        with self.assertRaisesRegex(RetrievalError, "artifact is unavailable"):
            EvidenceAssembler(self.source, ArtifactMap([])).assemble(response)

    def test_rebuild_is_stable_failed_publish_is_atomic_and_staleness_fails_closed(self) -> None:
        second = self.retrieval.rebuild()
        self.assertEqual(self.rebuild["generation_id"], second["generation_id"])
        with self.assertRaisesRegex(RetrievalError, "before publication"):
            self.retrieval.rebuild(fail_before_publish=True)
        self.assertEqual(
            json.loads(self.retrieval.pointer.read_text())["generation_id"],
            self.rebuild["generation_id"],
        )
        item = self.knowledge.inventory()[0]
        self.knowledge.correct(
            item.object_id,
            {**item.payload, "reviewed": True},
            KnowledgeStatus.CONFIRMED,
            "TASK-006 stale-index proof",
        )
        self.assertEqual(self.retrieval.health().state, RetrievalState.STALE)
        with self.assertRaisesRegex(RetrievalError, "retrieval state is stale"):
            self.retrieval.search(RetrievalQuery("filing"))

    def test_corrupt_index_and_vector_generation_fail_closed(self) -> None:
        generation = str(self.rebuild["generation_id"])
        path = self.retrieval.generations / generation / "index.json"
        path.write_text("{}", encoding="utf-8")
        self.assertEqual(self.retrieval.health().state, RetrievalState.CORRUPT)
        with self.assertRaisesRegex(RetrievalError, "retrieval state is corrupt"):
            self.retrieval.search(RetrievalQuery("filing"))
        failing = RetrievalRepository(
            self.root / "failing", self.source, self.knowledge, FailingVectorizer()
        )
        with self.assertRaisesRegex(RetrievalError, "vector generation failed"):
            failing.rebuild()
        self.assertEqual(failing.health().state, RetrievalState.MISSING)

    def test_provenance_inconsistency_prevents_index_publication(self) -> None:
        self.source.rebuild([self.inputs[1]])
        replacement = RetrievalRepository(
            self.root / "invalid-provenance", self.source, self.knowledge
        )
        with self.assertRaisesRegex(RetrievalError, "provenance validation failed"):
            replacement.rebuild()
        self.assertEqual(replacement.health().state, RetrievalState.MISSING)

    def test_vectorizer_replaceability_preserves_governed_package_contract(self) -> None:
        alternative = RetrievalRepository(
            self.root / "character-retrieval",
            self.source,
            self.knowledge,
            CharacterNgramVectorizer(),
        )
        alternative.rebuild()
        query = RetrievalQuery(
            "Seagate annual report",
            constraints=MetadataConstraints(
                entity_ids=("1137789",), document_types=("10-K",)
            ),
            max_results=8,
            candidate_limit=20,
            context_radius=32,
            evidence_budget_bytes=4_000,
        )
        assembler = EvidenceAssembler(self.source, self.artifacts)
        comparison = compare_evidence_packages(
            assembler.assemble(self.retrieval.search(query)),
            assembler.assemble(alternative.search(query)),
            self.source,
            self.artifacts,
            require_both_classes=True,
        )
        self.assertEqual(comparison["result"], "PASS")
        self.assertTrue(comparison["same_public_schema_and_field_types"])
        self.assertTrue(comparison["source_and_derived_classes_preserved"])
        self.assertTrue(comparison["all_returned_provenance_valid"])
        self.assertEqual(comparison["vectorizer_specific_public_fields"], [])
        self.assertNotIn("vectorizer", evidence_contract_schema()["EvidencePackage"])
        self.assertIn("legitimately", comparison["ranking_or_selection_explanation"])

    def test_vectorizer_replaceability_covers_determinism_budget_and_truncation(self) -> None:
        alternative = RetrievalRepository(
            self.root / "character-reporting",
            self.source,
            self.knowledge,
            CharacterNgramVectorizer(),
        )
        alternative.rebuild()
        assembler = EvidenceAssembler(self.source, self.artifacts)
        exact_query = RetrievalQuery(
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
        exact = compare_evidence_packages(
            assembler.assemble(self.retrieval.search(exact_query)),
            assembler.assemble(alternative.search(exact_query)),
            self.source,
            self.artifacts,
            require_same_selection=True,
        )
        self.assertTrue(exact["same_selected_evidence"])
        self.assertTrue(exact["same_selected_evidence_semantics"])
        budget_query = RetrievalQuery(
            "Seagate issuer filing evidence",
            max_results=5,
            candidate_limit=20,
            context_radius=100,
            evidence_budget_bytes=100,
        )
        budget = compare_evidence_packages(
            assembler.assemble(self.retrieval.search(budget_query)),
            assembler.assemble(alternative.search(budget_query)),
            self.source,
            self.artifacts,
            require_budget_reporting=True,
        )
        self.assertTrue(budget["omission_reporting_present"])
        self.assertTrue(budget["coverage_reporting_present"])
        truncated_query = RetrievalQuery(
            "issuer filing evidence", max_results=1, candidate_limit=20
        )
        truncated = compare_evidence_packages(
            assembler.assemble(self.retrieval.search(truncated_query)),
            assembler.assemble(alternative.search(truncated_query)),
            self.source,
            self.artifacts,
            require_truncation_reporting=True,
        )
        self.assertTrue(truncated["truncation_reporting_present"])
        self.assertTrue(truncated["coverage_reporting_present"])

    def test_conflicted_knowledge_is_not_hidden_or_presented_as_source(self) -> None:
        alternate = self.inputs[0].content.replace(
            b"SEAGATE TECHNOLOGY HOLDINGS PLC", b"SEAGATE ALTERNATE LEGAL NAME"
        )
        ambiguous = SourceInput(
            "document-task006-ambiguous",
            f"artifact-{hashlib.sha256(alternate).hexdigest()}",
            alternate,
        )
        inputs = [self.inputs[0], ambiguous]
        self.source.rebuild(inputs)
        self.knowledge.rebuild(self.source)
        self.artifacts = ArtifactMap(inputs)
        self.retrieval.rebuild()
        response = self.retrieval.search(
            RetrievalQuery(
                "Seagate legal name",
                result_classes=(ResultClass.DERIVED_KNOWLEDGE,),
                constraints=MetadataConstraints(
                    knowledge_types=("entity",),
                    knowledge_statuses=(KnowledgeStatus.CONFLICTED,),
                ),
                max_results=5,
            )
        )
        package = EvidenceAssembler(self.source, self.artifacts).assemble(response)
        self.assertEqual(len(package.derived_knowledge), 1)
        self.assertFalse(package.source_evidence)
        self.assertTrue(package.contradictions)
        self.assertTrue(any("conflicted" in item for item in package.coverage_gaps))
        alternative = RetrievalRepository(
            self.root / "conflict-character",
            self.source,
            self.knowledge,
            CharacterNgramVectorizer(),
        )
        alternative.rebuild()
        comparison = compare_evidence_packages(
            package,
            EvidenceAssembler(self.source, self.artifacts).assemble(
                alternative.search(response.trace.query)
            ),
            self.source,
            self.artifacts,
            require_same_selection=True,
            require_conflict_reporting=True,
        )
        self.assertTrue(comparison["conflict_and_ambiguity_reporting_present"])


if __name__ == "__main__":
    unittest.main()
