"""Focused proof for the bounded read-only RFI MCP transcript experiment."""

from __future__ import annotations

import ast
import hashlib
import json
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

from rfi.acquisition import AcquisitionRepository
from rfi.acquisition.contracts import (
    CandidateDocument,
    DiscoveryProvenance,
    RetrievalResult,
    SourceProfile,
)
from rfi.artifacts import ArtifactOrder, ArtifactQuery, ArtifactQueryError, ArtifactQueryService
from rfi.firms import FirmRepository
from rfi.firms.contracts import FirmDraft, FirmStatus
from rfi.mcp.access import TranscriptAccessGeneration
from rfi.mcp.contracts import AccessHealth, Outcome, SCHEMA_VERSION, TraceContext
from rfi.mcp.server import StdioMcpServer
from rfi.mcp.surface import RfiMcpSurface
from rfi.source_profiles import load_canonical_template

ROOT = Path(__file__).resolve().parents[1]
LIVE_STATE = ROOT / ".artifacts/task071-live-eval"


class MinimalRfiMcpTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.state = Path(self.temporary.name) / "state"
        self.firms = FirmRepository.initialize(self.state / "firm-catalog")
        self.firms.create(FirmDraft(
            "seagate", "Seagate Technology", "2024-01-01", status=FirmStatus.ACTIVE
        ))
        self.repository = AcquisitionRepository(self.state / "acquisition")
        self.repository.register_source(SourceProfile(
            "source-seagate-transcripts",
            "Seagate retained transcripts",
            True,
            "earnings_transcript",
            policy={
                "firm_id": "seagate",
                "artifact_id": "earnings_transcript",
                "alternate_artifact_ids": ["management_transcript"],
                "retrieval_adapter_id": "fixture-transcript",
            },
        ))
        self.first_artifact = self._retain(
            "first",
            "document-first",
            date(2024, 10, 22),
            "Earnings Call: Q1 2025",
            "Cloud demand was improving, although customer inventory remained elevated.\n"
            "The team expected a gradual recovery in nearline shipments.\n",
        )
        self.second_artifact = self._retain(
            "second",
            "document-second",
            date(2025, 7, 29),
            "Earnings Call: Q4 2025",
            "Cloud demand strengthened and qualification activity accelerated.\n"
            "Nearline shipments reached a new record.\n",
        )
        self.service = ArtifactQueryService(
            self.repository, self.firms, load_canonical_template()
        )
        self.trace_path = self.state / "mcp-trace.jsonl"
        self.surface = RfiMcpSurface(self.service, trace_path=self.trace_path)

    def tearDown(self) -> None:
        self.surface.close()
        self.temporary.cleanup()

    def _retain(
        self,
        suffix: str,
        document_id: str,
        event_date: date,
        title: str,
        body: str,
    ) -> str:
        observed = f"2026-08-09T12:{len(self.repository.observations()):02d}:00+00:00"
        content = (
            f"Title: {title}\nCompany: Seagate Technology\n"
            f"Event date: {event_date.isoformat()}\n\n{body}"
        ).encode()
        candidate = CandidateDocument(
            f"candidate-{suffix}",
            "source-seagate-transcripts",
            document_id,
            DiscoveryProvenance(
                observed,
                "fixture-transcript",
                {"provider": "fixture", "provider_identifier": suffix},
                (f"https://fixture.test/{suffix}",),
                {"firm_id": "seagate"},
            ),
        )
        result = self.repository.record_success(
            f"attempt-{suffix}",
            candidate,
            RetrievalResult(
                content,
                "text/plain",
                observed,
                "fixture-transcript",
                {"provider": "fixture", "provider_identifier": suffix},
                {
                    "trusted_event_date": event_date.isoformat(),
                    "trusted_event_date_available": True,
                    "transcript_event_kind": "earnings_call",
                    "provider_metadata": {"document_title": title},
                },
                trusted_event_date=event_date,
            ),
            canonical_artifact_id="earnings_transcript",
        )
        return result.artifact_id

    def test_discovery_exposes_only_bounded_resources_tools_and_versioned_schemas(self) -> None:
        server = StdioMcpServer(self.surface)
        initialized = server.dispatch({
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {"protocolVersion": "2025-06-18"},
        })
        assert initialized is not None
        self.assertEqual(initialized["result"]["protocolVersion"], "2025-06-18")
        tools = server.dispatch({"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
        assert tools is not None
        self.assertEqual(
            {item["name"] for item in tools["result"]["tools"]},
            {"query_artifacts", "search_transcript_segments", "read_artifact_bytes"},
        )
        templates = server.dispatch({
            "jsonrpc": "2.0", "id": 3, "method": "resources/templates/list"
        })
        assert templates is not None
        self.assertEqual(len(templates["result"]["resourceTemplates"]), 6)
        dictionary = self.surface.read_resource("rfi://dictionary")
        self.assertEqual(dictionary["schema_version"], SCHEMA_VERSION)
        self.assertIn(
            "owned by the investigative runtime",
            dictionary["data"]["completeness"]["answer_sufficiency"],
        )
        capabilities = self.surface.read_resource("rfi://capabilities")
        deferred = {
            item["capability_id"]: item["status"]
            for item in capabilities["data"]["capabilities"]
        }
        self.assertEqual(deferred["artifact.history.v1"], "deferred")

    def test_query_artifacts_matches_repository_semantics_and_preserves_empty_unknown(self) -> None:
        arguments = {
            "firm_ids": ["seagate"],
            "canonical_artifact_ids": ["earnings_transcript"],
            "order": "oldest",
            "limit": 100,
        }
        mcp = self.surface.call_tool("query_artifacts", arguments)
        direct = self.service.query(ArtifactQuery(
            firm_ids=("seagate",),
            canonical_artifact_ids=("earnings_transcript",),
            order=ArtifactOrder.OLDEST,
            limit=100,
        ))
        self.assertEqual(
            [item["document_id"] for item in mcp["data"]["items"]],
            [item.document_id for item in direct.items],
        )
        empty = self.surface.call_tool("query_artifacts", {
            "firm_ids": ["seagate"],
            "canonical_artifact_ids": ["management_transcript"],
        })
        self.assertEqual(empty["outcome"], "empty")
        unknown = self.surface.call_tool("query_artifacts", {"firm_ids": ["invented"]})
        self.assertEqual(unknown["outcome"], "error")
        self.assertEqual(unknown["error"]["code"], "unknown_object")

    def test_immutable_artifact_reads_verify_whole_and_exact_range_digests(self) -> None:
        artifact = self.service.artifact(self.first_artifact)
        exact = self.service.artifact_content(self.first_artifact)
        self.assertEqual(hashlib.sha256(exact.content).hexdigest(), artifact.checksum_sha256)
        result = self.surface.call_tool("read_artifact_bytes", {
            "artifact_id": self.first_artifact,
            "byte_start": 0,
            "byte_end": 32,
            "decode": "both",
        })
        self.assertEqual(result["outcome"], "ok")
        self.assertTrue(result["data"]["whole_artifact_verified"])
        self.assertEqual(
            result["data"]["range_sha256"], hashlib.sha256(exact.content[:32]).hexdigest()
        )
        oversize = self.surface.call_tool("read_artifact_bytes", {
            "artifact_id": self.first_artifact,
            "byte_start": 0,
            "byte_end": len(exact.content) + 1,
        })
        self.assertEqual(oversize["error"]["code"], "invalid_range")
        self.assertIn("no bytes were clipped", oversize["error"]["message"])

    def test_exact_segment_is_stable_verified_and_artifact_addressed(self) -> None:
        search = self.surface.call_tool("search_transcript_segments", {
            "query": "cloud demand", "match": "all", "order": "oldest"
        })
        candidate = search["data"]["hits"][0]
        self.assertEqual(candidate["evidence_state"], "candidate_only")
        exact = self.surface.read_resource(candidate["segment_uri"])
        self.assertEqual(exact["outcome"], "ok")
        self.assertTrue(exact["data"]["segment_verified"])
        retained = self.service.artifact_content(exact["data"]["artifact_id"]).content
        byte_range = exact["data"]["requested_range"]
        span = retained[byte_range["byte_start"]:byte_range["byte_end"]]
        self.assertEqual(hashlib.sha256(span).hexdigest(), exact["data"]["range_sha256"])
        second_generation = TranscriptAccessGeneration(
            self.service,
            firm_ids=("seagate",),
            canonical_artifact_ids=("earnings_transcript", "management_transcript"),
        )
        try:
            self.assertEqual(self.surface.access.segment_ids(), second_generation.segment_ids())
        finally:
            second_generation.close()

    def test_document_revision_makes_generation_stale_and_prevents_artifact_drift(self) -> None:
        search = self.surface.call_tool("search_transcript_segments", {"query": "cloud demand"})
        old_uri = search["data"]["hits"][0]["segment_uri"]
        old_artifact = search["data"]["hits"][0]["artifact_id"]
        replacement = self._retain(
            "first-revision",
            "document-first",
            date(2024, 10, 22),
            "Earnings Call: Q1 2025 revised",
            "This later revision has entirely different retained words.\n",
        )
        self.assertNotEqual(old_artifact, replacement)
        stale = self.surface.read_resource(old_uri)
        self.assertEqual(stale["outcome"], "error")
        self.assertEqual(stale["error"]["code"], "access_stale")
        self.assertEqual(self.surface.access.health, AccessHealth.STALE)
        old_exact = self.surface.call_tool("read_artifact_bytes", {
            "artifact_id": old_artifact, "byte_start": 0, "byte_end": 16
        })
        self.assertEqual(old_exact["outcome"], "ok")
        self.assertEqual(old_exact["data"]["artifact_id"], old_artifact)

    def test_stale_artifact_cursor_and_invalid_identifiers_are_typed_failures(self) -> None:
        for uri in (
            "rfi://documents/invented",
            "rfi://artifacts/artifact-invented",
            "rfi://observations/observation-invented",
            "rfi://transcript-segments/transcript-segment-invented",
        ):
            value = self.surface.read_resource(uri)
            self.assertEqual(value["outcome"], "error")
            self.assertEqual(value["error"]["code"], "unknown_object")
        first = self.surface.call_tool("query_artifacts", {
            "firm_ids": ["seagate"], "limit": 1, "order": "oldest"
        })
        cursor = first["data"]["page"]["next_cursor"]
        self.assertIsNotNone(cursor)
        self._retain(
            "third", "document-third", date(2026, 1, 1), "Earnings Call: Q2 2026", "New text.\n"
        )
        stale = self.surface.call_tool("query_artifacts", {
            "firm_ids": ["seagate"], "limit": 1, "order": "oldest", "cursor": cursor
        })
        self.assertEqual(stale["error"]["code"], "stale_cursor")

    def test_repository_failure_is_not_empty(self) -> None:
        with patch.object(
            self.service,
            "query",
            side_effect=ArtifactQueryError("repository_read_failure", "read failed"),
        ):
            value = self.surface.call_tool("query_artifacts", {"firm_ids": ["seagate"]})
        self.assertEqual(value["outcome"], "error")
        self.assertEqual(value["error"]["code"], "repository_read_failure")
        self.assertIn("No evidence-absence", value["error"]["evidence_implication"])

    def test_partial_build_preserves_omission_and_all_material_bounds(self) -> None:
        self._retain(
            "malformed",
            "document-malformed",
            date(2026, 2, 1),
            "Malformed retained transcript",
            "",
        )
        access = TranscriptAccessGeneration(
            self.service,
            firm_ids=("seagate",),
            canonical_artifact_ids=("earnings_transcript", "management_transcript"),
        )
        try:
            identity = access.identity()
            self.assertEqual(identity.health, AccessHealth.READY)
            self.assertEqual(identity.build_outcome, Outcome.PARTIAL)
            self.assertEqual(identity.eligible_document_count, 3)
            self.assertEqual(identity.indexed_document_count, 2)
            self.assertIn("unsegmentable_transcript", {item.code for item in identity.diagnostics})
            result = access.search({
                "query": "cloud", "limit": 1, "max_per_document": 1
            }, TraceContext())
            self.assertEqual(
                {item["name"] for item in result["bounds_applied"]},
                {
                    "normalized_term_limit",
                    "internal_candidate_limit",
                    "max_per_document",
                    "result_limit",
                },
            )
        finally:
            access.close()

    def test_unavailable_and_corrupt_health_are_distinct(self) -> None:
        with patch.object(
            self.service,
            "query",
            side_effect=ArtifactQueryError("repository_read_failure", "offline"),
        ):
            unavailable = TranscriptAccessGeneration(
                self.service,
                firm_ids=("seagate",),
                canonical_artifact_ids=("earnings_transcript",),
            )
        try:
            self.assertEqual(unavailable.health, AccessHealth.UNAVAILABLE)
        finally:
            unavailable.close()
        segment_id = self.surface.call_tool("search_transcript_segments", {
            "query": "cloud demand", "match": "all", "order": "oldest", "limit": 1
        })["data"]["hits"][0]["segment_id"]
        digest = self.first_artifact.removeprefix("artifact-")
        path = next(self.repository.content_root.rglob(digest))
        original = path.read_bytes()
        original_mode = path.stat().st_mode
        try:
            path.chmod(0o600)
            path.write_bytes(b"corrupt" + original)
            value = self.surface.read_resource(f"rfi://transcript-segments/{segment_id}")
            self.assertEqual(value["error"]["code"], "integrity_failure")
            self.assertEqual(self.surface.access.health, AccessHealth.CORRUPT)
        finally:
            path.write_bytes(original)
            path.chmod(original_mode)

    def test_instrumentation_is_complete_correlated_and_separate_from_runtime_state(self) -> None:
        value = self.surface.call_tool("search_transcript_segments", {
            "query": "cloud demand", "limit": 1, "max_per_document": 1
        })
        exact = self.surface.read_resource(value["data"]["hits"][0]["segment_uri"])
        records = [json.loads(line) for line in self.trace_path.read_text().splitlines()]
        by_id = {item["request_id"]: item for item in records}
        record = by_id[exact["request_id"]]
        required = {
            "capability", "capability_version", "schema_version", "normalized_input",
            "input_sha256", "repository_snapshot", "access_generation", "started_at",
            "ended_at", "outcome", "returned_count", "total_count", "cursor",
            "bounds", "truncated", "referenced_document_ids", "referenced_artifact_ids",
            "referenced_observation_ids", "referenced_segment_ids", "artifact_digests",
            "range_digests", "response_sha256", "response_bytes",
        }
        self.assertTrue(required.issubset(record))
        self.assertNotIn("hypotheses", record)
        self.assertNotIn("sufficiency", record)

    def test_surface_performs_no_retained_repository_mutation(self) -> None:
        revision = self.repository.repository_revision()
        observations = len(self.repository.observations())
        artifacts = len(self.repository.artifact_metadata())
        self.surface.read_resource("rfi://about")
        self.surface.read_resource("rfi://transcript-corpora/seagate?limit=1")
        self.surface.call_tool("search_transcript_segments", {"query": "nearline"})
        self.assertEqual(self.repository.repository_revision(), revision)
        self.assertEqual(len(self.repository.observations()), observations)
        self.assertEqual(len(self.repository.artifact_metadata()), artifacts)

    def test_mcp_package_has_no_task071_investigation_or_persistence_dependencies(self) -> None:
        imports: set[str] = set()
        sources = ""
        for path in (ROOT / "src/rfi/mcp").glob("*.py"):
            source = path.read_text(encoding="utf-8")
            sources += source
            tree = ast.parse(source)
            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom) and node.module:
                    imports.add(node.module)
                if isinstance(node, ast.Import):
                    imports.update(item.name for item in node.names)
        forbidden = {
            "rfi.research.harness", "rfi.research.adjudication", "rfi.research.reporting",
            "rfi.research.openai", "rfi.acquisition.persistence", "rfi.storage.sqlite",
        }
        self.assertFalse(imports.intersection(forbidden))
        self.assertNotIn("content_root", sources)
        self.assertNotIn("investigate_question", sources)
        self.assertNotIn("submit_investigation", sources)


@unittest.skipUnless(LIVE_STATE.exists(), "retained TASK-071 proving state is not available")
class SeagateCorpusParityTests(unittest.TestCase):
    def test_retained_seagate_corpus_matches_task071_inventory(self) -> None:
        artifacts = ArtifactQueryService(
            AcquisitionRepository(LIVE_STATE / "acquisition"),
            FirmRepository.open(LIVE_STATE / "firm-catalog"),
            load_canonical_template(),
        )
        access = TranscriptAccessGeneration(
            artifacts,
            firm_ids=("seagate",),
            canonical_artifact_ids=("earnings_transcript", "management_transcript"),
        )
        try:
            identity = access.identity()
            self.assertEqual(identity.authority_snapshot, "sqlite-revision-8237")
            self.assertEqual(identity.eligible_document_count, 21)
            self.assertEqual(identity.indexed_document_count, 21)
            self.assertEqual(identity.indexed_segment_count, 2268)
            baseline = json.loads(
                (ROOT / ".artifacts/review/TASK-071/evaluation/retained-corpus.json").read_text()
            )
            expected = {
                (item["document_id"], item["artifact_id"], item["segment_count"])
                for item in baseline["documents"]
            }
            actual = {
                (item["document_id"], item["artifact_id"], item["segment_count"])
                for item in access.corpus(limit=100, cursor=None, trace=TraceContext())["documents"]
            }
            self.assertEqual(actual, expected)
        finally:
            access.close()


if __name__ == "__main__":
    unittest.main()
