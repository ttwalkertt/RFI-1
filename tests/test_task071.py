"""Focused contracts and vertical-slice behavior for TASK-071."""

from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from datetime import date
from pathlib import Path
from typing import Any
from unittest import mock

from rfi.acquisition import (
    AcquisitionRepository,
    CandidateDocument,
    DiscoveryProvenance,
    RetrievalResult,
    SourceProfile,
)
from rfi.artifacts import ArtifactQuery, ArtifactQueryService
from rfi.firms import FirmRepository
from rfi.firms.contracts import FirmDraft, FirmStatus
from rfi.research import (
    InvestigationStatus,
    ModelBudget,
    ModelToolCall,
    ModelTurn,
    OpenAIResponsesInvestigator,
    ResearchError,
    TranscriptInvestigator,
    TranscriptKnowledgeAccess,
    TranscriptScope,
)
from rfi.source_profiles import load_canonical_template


class ScriptedSession:
    """Question-neutral model substitute that exercises iterative access."""

    def __init__(
        self,
        cite_unknown: bool = False,
        wrong_period: bool = False,
        omit_latest: bool = False,
    ) -> None:
        self.step = 0
        self.cite_unknown = cite_unknown
        self.wrong_period = wrong_period
        self.omit_latest = omit_latest

    def next_turn(
        self, tool_outputs: tuple[tuple[str, dict[str, Any]], ...]
    ) -> ModelTurn:
        self.step += 1
        if self.step == 1:
            return self._call("describe", "describe_corpus", {})
        if self.step == 2:
            return self._call("search", "search_transcripts", {
                "query": "cloud demand",
                "match": "any",
                "order": "relevance",
                "date_from": None,
                "date_through": None,
                "document_ids": [],
                "limit": 4,
                "max_per_document": 1,
            })
        if self.step == 3:
            hits = tool_outputs[0][1]["hits"]
            return self._call("expand", "expand_segments", {
                "segment_ids": [item["segment_id"] for item in hits[:2]],
                "context_radius": 0,
            })
        evidence = tool_outputs[0][1]["evidence"]
        evidence_ids = [item["evidence_id"] for item in evidence]
        if self.cite_unknown:
            evidence_ids = ["transcript-segment-not-observed"]
        if self.omit_latest:
            evidence_ids = evidence_ids[:1]
        periods = [item["event_date"] for item in evidence]
        if self.wrong_period:
            periods.append("2099-01-01")
        if self.omit_latest:
            periods = periods[:1]
        return self._call("submit", "submit_investigation", {
            "status": "supported",
            "answer": "Management described cloud demand in both retained periods.",
            "claims": [{
                "text": "Cloud demand was discussed in both periods.",
                "evidence_ids": evidence_ids,
                "periods": periods,
                "interpretation": "This compares two retained statements.",
                "limitations": "Speaker labels are unavailable.",
            }],
            "gaps": ["Retained coverage is not complete."],
            "failed_searches": [],
            "stopping_reason": "Expanded evidence from two retained dates answered the question.",
        })

    @staticmethod
    def _call(call_id: str, name: str, arguments: dict[str, Any]) -> ModelTurn:
        return ModelTurn(
            (ModelToolCall(call_id, name, arguments),),
            (),
            usage={"input_tokens": 10, "output_tokens": 5, "total_tokens": 15},
        )


class ScriptedModel:
    """Replaceable test implementation of the public LLM boundary."""

    def __init__(
        self,
        cite_unknown: bool = False,
        wrong_period: bool = False,
        omit_latest: bool = False,
    ) -> None:
        self.cite_unknown = cite_unknown
        self.wrong_period = wrong_period
        self.omit_latest = omit_latest
        self.received_tools: tuple[dict[str, Any], ...] = ()

    @property
    def runtime_identity(self) -> str:
        return "scripted:task071-v1"

    def start(
        self,
        question: str,
        instructions: str,
        tools: tuple[dict[str, Any], ...],
        budget: ModelBudget,
    ) -> ScriptedSession:
        self.received_tools = tools
        return ScriptedSession(
            self.cite_unknown, self.wrong_period, self.omit_latest
        )


class PrematureModel(ScriptedModel):
    """Model substitute that attempts to declare insufficiency without investigation."""

    def start(
        self,
        question: str,
        instructions: str,
        tools: tuple[dict[str, Any], ...],
        budget: ModelBudget,
    ) -> ScriptedSession:
        class PrematureSession(ScriptedSession):
            def next_turn(
                self, tool_outputs: tuple[tuple[str, dict[str, Any]], ...]
            ) -> ModelTurn:
                return self._call("submit", "submit_investigation", {
                    "status": "insufficient",
                    "answer": "There is not enough evidence.",
                    "claims": [],
                    "gaps": ["No evidence inspected."],
                    "failed_searches": [],
                    "stopping_reason": "Stopped immediately.",
                })

        return PrematureSession()


class RecoverySession:
    """Target only the evaluator-required early fixture period."""

    def __init__(self) -> None:
        self.step = 0

    def next_turn(
        self, tool_outputs: tuple[tuple[str, dict[str, Any]], ...]
    ) -> ModelTurn:
        self.step += 1
        if self.step == 1:
            return ScriptedSession._call("recover-search", "search_transcripts", {
                "query": "cloud demand",
                "match": "any",
                "order": "oldest",
                "date_from": "2024-10-22",
                "date_through": "2024-10-22",
                "document_ids": [],
                "limit": 4,
                "max_per_document": 1,
            })
        if self.step == 2:
            hits = tool_outputs[0][1]["hits"]
            return ScriptedSession._call("recover-expand", "expand_segments", {
                "segment_ids": [hits[0]["segment_id"]],
                "context_radius": 0,
            })
        evidence = tool_outputs[0][1]["evidence"]
        return ScriptedSession._call("recover-submit", "submit_investigation", {
            "status": "supported",
            "answer": "Early-period demand evidence repairs the missing boundary.",
            "claims": [{
                "text": "The early retained period described improving cloud demand.",
                "evidence_ids": [evidence[0]["evidence_id"]],
                "periods": [evidence[0]["event_date"]],
                "interpretation": "This supplies the missing temporal boundary.",
                "limitations": "Speaker labels are unavailable.",
            }],
            "gaps": [],
            "failed_searches": [],
            "stopping_reason": "The exact evaluator-required period was expanded.",
        })


class RecoveryAwareModel(ScriptedModel):
    """Use a fresh, scoped session only after the first evaluated closure."""

    def __init__(self) -> None:
        super().__init__(omit_latest=True)
        self.sessions = 0

    def start(
        self,
        question: str,
        instructions: str,
        tools: tuple[dict[str, Any], ...],
        budget: ModelBudget,
    ) -> ScriptedSession | RecoverySession:
        self.sessions += 1
        if self.sessions == 1:
            return ScriptedSession(omit_latest=True)
        return RecoverySession()


class IdentifierRecoverySession:
    """Correct one invented document ID after structured harness feedback."""

    def __init__(self) -> None:
        self.step = 0
        self.warning: dict[str, Any] | None = None

    def next_turn(
        self, tool_outputs: tuple[tuple[str, dict[str, Any]], ...]
    ) -> ModelTurn:
        self.step += 1
        if self.step == 1:
            return ScriptedSession._call("describe", "describe_corpus", {})
        if self.step == 2:
            return ScriptedSession._call("bad-search", "search_transcripts", {
                "query": "cloud demand", "match": "any", "order": "relevance",
                "date_from": None, "date_through": None,
                "document_ids": ["invented-document"], "limit": 4,
                "max_per_document": 1,
            })
        if self.step == 3:
            self.warning = tool_outputs[0][1]["warning"]
            return ScriptedSession._call("valid-search", "search_transcripts", {
                "query": "cloud demand", "match": "any", "order": "relevance",
                "date_from": None, "date_through": None,
                "document_ids": [], "limit": 4, "max_per_document": 1,
            })
        if self.step == 4:
            hits = tool_outputs[0][1]["hits"]
            return ScriptedSession._call("expand", "expand_segments", {
                "segment_ids": [hits[0]["segment_id"]], "context_radius": 0,
            })
        evidence = tool_outputs[0][1]["evidence"][0]
        return ScriptedSession._call("submit", "submit_investigation", {
            "status": "supported", "answer": "Cloud demand was discussed.",
            "claims": [{
                "text": "Cloud demand was discussed in a retained period.",
                "evidence_ids": [evidence["evidence_id"]],
                "periods": [evidence["event_date"]],
                "interpretation": "The passage directly discusses demand.",
                "limitations": "This is one retained period.",
            }],
            "gaps": [], "failed_searches": [],
            "stopping_reason": "Corrected the invalid identifier and expanded evidence.",
        })


class IdentifierRecoveryModel(ScriptedModel):
    def __init__(self) -> None:
        super().__init__()
        self.session = IdentifierRecoverySession()

    def start(
        self,
        question: str,
        instructions: str,
        tools: tuple[dict[str, Any], ...],
        budget: ModelBudget,
    ) -> IdentifierRecoverySession:
        return self.session


class TranscriptInvestigationTests(unittest.TestCase):
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
        self._retain(
            "first",
            date(2024, 10, 22),
            "Earnings Call: Q1 2025",
            "Cloud demand was improving, although customer inventory remained elevated.\n"
            "The team expected a gradual recovery in nearline shipments.\n",
            "earnings_transcript",
        )
        self._retain(
            "second",
            date(2025, 7, 29),
            "Earnings Call: Q4 2025",
            "Cloud demand strengthened and customer qualification activity accelerated.\n"
            "Management said nearline shipments reached a new record.\n",
            "earnings_transcript",
        )
        self.service = ArtifactQueryService(
            self.repository, self.firms, load_canonical_template()
        )
        self.access = TranscriptKnowledgeAccess(
            self.service, TranscriptScope(("seagate",))
        )

    def tearDown(self) -> None:
        self.access.close()
        self.temporary.cleanup()

    def _retain(
        self,
        suffix: str,
        event_date: date,
        title: str,
        body: str,
        canonical_artifact_id: str,
    ) -> None:
        observed = "2026-08-09T12:00:00+00:00"
        content = (
            f"Title: {title}\nCompany: Seagate Technology\n"
            f"Event date: {event_date.isoformat()}\n\n{body}"
        ).encode()
        candidate = CandidateDocument(
            f"candidate-{suffix}",
            "source-seagate-transcripts",
            f"document-{suffix}",
            DiscoveryProvenance(
                observed,
                "fixture-transcript",
                {"provider": "fixture", "provider_identifier": "STX"},
                (f"https://fixture.test/{suffix}",),
                {"firm_id": "seagate"},
            ),
        )
        self.repository.record_success(
            f"attempt-{suffix}",
            candidate,
            RetrievalResult(
                content,
                "text/plain",
                observed,
                "fixture-transcript",
                {"provider": "fixture", "provider_identifier": "STX"},
                {
                    "trusted_event_date": event_date.isoformat(),
                    "trusted_event_date_available": True,
                    "transcript_event_kind": "earnings_call",
                    "provider_metadata": {"document_title": title},
                },
                trusted_event_date=event_date,
            ),
            canonical_artifact_id=canonical_artifact_id,
        )

    def test_corpus_uses_event_chronology_and_exact_public_artifact_bytes(self) -> None:
        corpus = self.access.describe_corpus()
        self.assertEqual(corpus.date_from, "2024-10-22")
        self.assertEqual(corpus.date_through, "2025-07-29")
        self.assertEqual(len(corpus.documents), 2)
        self.assertEqual(corpus.segment_count, 4)
        self.assertFalse(corpus.documents[0].speaker_context_available)
        service_page = self.service.query(ArtifactQuery(
            firm_ids=("seagate",), canonical_artifact_ids=("earnings_transcript",)
        ))
        self.assertEqual(
            {item.source_effective.basis for item in service_page.items},
            {"trusted_event_date"},
        )

        result = self.access.search(
            "cloud demand", match="any", limit=4, max_per_document=1
        )
        self.assertEqual(len(result.hits), 2)
        excerpts = self.access.expand(
            tuple(item.segment_id for item in result.hits), context_radius=0
        )
        self.assertEqual(len(excerpts), 2)
        for excerpt in excerpts:
            content = self.access._artifacts.content(excerpt.document_id).content
            exact = content[excerpt.context_byte_start:excerpt.context_byte_end]
            self.assertEqual(hashlib.sha256(exact).hexdigest(), excerpt.context_sha256)
            self.assertEqual(exact.decode().strip(), excerpt.text)

        latest = self.access.search(
            "cloud demand", match="all", order="latest", limit=1
        )
        oldest = self.access.search(
            "cloud demand", match="all", order="oldest", limit=1
        )
        self.assertEqual(oldest.hits[0].event_date, "2024-10-22")
        self.assertEqual(latest.hits[0].event_date, "2025-07-29")

    def test_search_reports_empty_results_without_claiming_universal_absence(self) -> None:
        result = self.access.search("Martian dividend colony", match="any")
        self.assertEqual(result.total_matches, 0)
        self.assertEqual(result.hits, ())
        self.assertIn("not proof", result.coverage_note)

    def test_invalid_identifier_feedback_is_actionable_and_not_failed_search(self) -> None:
        model = IdentifierRecoveryModel()
        run = TranscriptInvestigator(self.access, model).investigate(
            "What retained evidence discusses cloud demand?"
        )
        self.assertEqual(run.result.status, InvestigationStatus.SUPPORTED)
        self.assertEqual(run.result.failed_searches, ())
        warning = model.session.warning
        self.assertIsNotNone(warning)
        assert warning is not None
        self.assertEqual(warning["category"], "tool_protocol_failure")
        self.assertEqual(warning["code"], "invalid_identifier")
        self.assertIn("not evidence", warning["evidence_implication"])
        self.assertEqual(warning["requested_identifiers"], ["invented-document"])
        self.assertEqual(len(warning["valid_identifiers"]), 2)

    def test_harness_iterates_and_accepts_only_expanded_evidence(self) -> None:
        model = ScriptedModel()
        run = TranscriptInvestigator(self.access, model).investigate(
            "How did cloud demand change?"
        )
        self.assertEqual(run.result.status, InvestigationStatus.SUPPORTED)
        self.assertEqual(len(run.result.evidence), 2)
        self.assertEqual(len(run.investigation_record.admissible_evidence), 2)
        self.assertTrue(run.result.answer.startswith(
            run.result.assessment.lead_paragraph
        ))
        self.assertEqual(
            run.trace[-1].action, "consistency_pass"
        )
        self.assertFalse(run.trace[-1].detail["retrieval_performed"])
        self.assertEqual(run.model_usage["total_tokens"], 60)
        self.assertEqual(
            [item.action for item in run.trace].count("tool_call"), 4
        )
        self.assertEqual(
            {item["name"] for item in model.received_tools},
            {
                "describe_corpus", "search_transcripts", "expand_segments",
                "inspect_document", "submit_investigation",
            },
        )
        self.assertNotIn("rework_request", [item.action for item in run.trace])

    def test_consistency_pass_rejects_unexpanded_model_citation(self) -> None:
        run = TranscriptInvestigator(
            self.access, ScriptedModel(cite_unknown=True)
        ).investigate("How did cloud demand change?")
        self.assertEqual(run.result.status, InvestigationStatus.INSUFFICIENT)
        self.assertEqual(run.result.claims, ())
        self.assertIn(
            "unexpanded or search-only",
            run.result.assessment.claim_assessments[0].reasons[0],
        )

    def test_consistency_pass_rejects_period_without_same_date_evidence(self) -> None:
        run = TranscriptInvestigator(
            self.access, ScriptedModel(wrong_period=True)
        ).investigate("How did cloud demand change?")
        self.assertEqual(run.result.status, InvestigationStatus.INSUFFICIENT)
        self.assertIn(
            "period without evidence",
            run.result.assessment.claim_assessments[0].reasons[0],
        )

    def test_one_recovery_cycle_repairs_evaluator_scoped_temporal_deficiency(
        self,
    ) -> None:
        run = TranscriptInvestigator(
            self.access, RecoveryAwareModel()
        ).investigate("How did demand change across the retained calls?")
        self.assertEqual(run.result.status, InvestigationStatus.SUPPORTED)
        self.assertEqual(run.result.assessment.support_calibration, "strong")
        self.assertEqual(run.result.assessment.findings, ())
        self.assertEqual(
            [
                item.action for item in run.trace
                if item.action in {
                    "rework_request", "recovery_tool_call", "investigation_closed",
                    "consistency_pass",
                }
            ],
            [
                "investigation_closed", "consistency_pass", "rework_request",
                "recovery_tool_call", "recovery_tool_call", "recovery_tool_call",
                "investigation_closed", "consistency_pass",
            ],
        )
        recovery_calls = [
            item for item in run.trace if item.action == "recovery_tool_call"
        ]
        self.assertEqual(
            recovery_calls[0].detail["arguments"]["date_from"], "2024-10-22"
        )

    def test_harness_enforces_tool_budget(self) -> None:
        with self.assertRaisesRegex(ResearchError, "tool-call budget"):
            TranscriptInvestigator(
                self.access,
                ScriptedModel(),
                ModelBudget(max_tool_calls=2),
            ).investigate("How did cloud demand change?")

    def test_harness_rejects_uninvestigated_insufficiency(self) -> None:
        with self.assertRaisesRegex(ResearchError, "before corpus orientation and search"):
            TranscriptInvestigator(self.access, PrematureModel()).investigate(
                "What evidence exists?"
            )

    def test_model_budget_rejects_ineffective_or_expansive_bounds(self) -> None:
        with self.assertRaisesRegex(ResearchError, "max_tool_calls"):
            ModelBudget(max_tool_calls=0)
        with self.assertRaisesRegex(ResearchError, "max_output_tokens_per_turn"):
            ModelBudget(max_output_tokens_per_turn=100_000)

    def test_openai_adapter_is_replaceable_and_sends_bounded_non_retained_request(
        self,
    ) -> None:
        response = _HTTPResponse({
            "output": [{
                "type": "function_call",
                "call_id": "call-orient",
                "name": "describe_corpus",
                "arguments": "{}",
            }],
            "usage": {"input_tokens": 12, "output_tokens": 4, "total_tokens": 16},
        })
        model = OpenAIResponsesInvestigator("fixture-model")
        with mock.patch.dict("os.environ", {"OPENAI_API_KEY": "fixture-secret"}), mock.patch(
            "urllib.request.urlopen", return_value=response
        ) as urlopen:
            session = model.start(
                "What changed?",
                "Use retained evidence.",
                ({
                    "type": "function",
                    "name": "describe_corpus",
                    "description": "Orient.",
                    "parameters": {
                        "type": "object", "properties": {}, "required": [],
                        "additionalProperties": False,
                    },
                    "strict": True,
                },),
                ModelBudget(max_output_tokens_per_turn=256),
            )
            turn = session.next_turn(())
        self.assertEqual(turn.tool_calls[0].name, "describe_corpus")
        self.assertEqual(turn.usage["total_tokens"], 16)
        request = urlopen.call_args.args[0]
        payload = json.loads(request.data)
        self.assertFalse(payload["store"])
        self.assertEqual(payload["max_output_tokens"], 256)
        self.assertEqual(payload["tool_choice"], "required")
        self.assertIn("urgency_factor=0.00", payload["instructions"])
        self.assertFalse(payload["parallel_tool_calls"])
        self.assertNotIn("reasoning", payload)
        self.assertNotIn("fixture-secret", json.dumps(payload))

    def test_openai_adapter_forces_structured_submission_on_final_turn(self) -> None:
        response = _HTTPResponse({
            "output": [{
                "type": "function_call",
                "call_id": "call-submit",
                "name": "submit_investigation",
                "arguments": "{}",
            }],
        })
        model = OpenAIResponsesInvestigator("fixture-model")
        submit_tool = ({
            "type": "function",
            "name": "submit_investigation",
            "description": "Submit.",
            "parameters": {
                "type": "object", "properties": {}, "required": [],
                "additionalProperties": False,
            },
            "strict": True,
        },)
        with mock.patch.dict("os.environ", {"OPENAI_API_KEY": "fixture-secret"}), mock.patch(
            "urllib.request.urlopen", return_value=response
        ) as urlopen:
            session = model.start(
                "What changed?", "Use retained evidence.", submit_tool,
                ModelBudget(max_model_turns=1),
            )
            session.next_turn(())
        request = urlopen.call_args.args[0]
        self.assertEqual(
            json.loads(request.data)["tool_choice"],
            {"type": "function", "name": "submit_investigation"},
        )
        self.assertIn("urgency_factor=1.00", json.loads(request.data)["instructions"])
        self.assertIn(
            "Citable expanded evidence is exactly: none",
            json.loads(request.data)["instructions"],
        )

    def test_openai_final_schema_allows_only_expanded_evidence_and_dates(self) -> None:
        response = _HTTPResponse({
            "output": [{
                "type": "function_call",
                "call_id": "call-expand",
                "name": "expand_segments",
                "arguments": '{"segment_ids":["candidate"],"context_radius":0}',
            }],
        })
        model = OpenAIResponsesInvestigator("fixture-model")
        tools = (*self.access.tool_schemas(), TranscriptInvestigator._submit_schema())
        with mock.patch.dict("os.environ", {"OPENAI_API_KEY": "fixture-secret"}), mock.patch(
            "urllib.request.urlopen", return_value=response
        ) as urlopen:
            session = model.start(
                "What changed?", "Use retained evidence.", tools,
                ModelBudget(max_model_turns=2),
            )
            session.next_turn(())
            session.next_turn((("call-expand", {
                "evidence": [{
                    "evidence_id": "expanded-one", "event_date": "2025-07-29",
                }],
            }),))
        payload = json.loads(urlopen.call_args_list[1].args[0].data)
        submit = next(item for item in payload["tools"] if item["name"] == "submit_investigation")
        claim = submit["parameters"]["properties"]["claims"]["items"]
        self.assertEqual(
            claim["properties"]["evidence_ids"]["items"]["enum"], ["expanded-one"]
        )
        self.assertEqual(
            claim["properties"]["periods"]["items"]["enum"], ["2025-07-29"]
        )


class _HTTPResponse:
    """Minimal context-managed HTTP response for provider-boundary tests."""

    def __init__(self, payload: dict[str, Any]) -> None:
        self.payload = payload

    def __enter__(self) -> _HTTPResponse:
        return self

    def __exit__(self, *arguments: object) -> None:
        return None

    def read(self) -> bytes:
        return json.dumps(self.payload).encode()


if __name__ == "__main__":
    unittest.main()
