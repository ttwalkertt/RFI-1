"""Thin Stage-1 output boundary for final governed investigation outcomes."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict
from typing import Any, Mapping

from rfi.research.contracts import (
    EvidenceExcerpt,
    InvestigationClaim,
    InvestigationRun,
    InvestigationStatus,
    ReportAuthority,
    ReportClaimMapping,
    ReportRecovery,
    ResearchReport,
    TranscriptScope,
)


class ResearchReportWriter:
    """Normalize a final governed result without reasoning or external access."""

    SCHEMA_VERSION = "task071.research-report.v1"
    HARNESS_IDENTITY = "rfi.research.TranscriptInvestigator:task071-v1"
    IQA_IDENTITY = "rfi.research.TranscriptKnowledgeAccess:fts5-exact-expansion-v1"

    def write(
        self,
        run: InvestigationRun,
        scope: TranscriptScope,
        trace_reference: str,
    ) -> ResearchReport:
        """Copy the final adjudicated outcome into its stable report contract."""
        return self._write(asdict(run), scope, trace_reference)

    def write_serialized(
        self,
        run: Mapping[str, Any],
        scope: TranscriptScope,
        trace_reference: str,
    ) -> ResearchReport:
        """Normalize an already serialized governed run for package regeneration."""
        return self._write(run, scope, trace_reference)

    def _write(
        self,
        run: Mapping[str, Any],
        scope: TranscriptScope,
        trace_reference: str,
    ) -> ResearchReport:
        result = run["result"]
        assessment = result["assessment"]
        claims = tuple(self._claim(item) for item in result["claims"])
        evidence = tuple(self._evidence(item) for item in result["evidence"])
        trace = tuple(run["trace"])
        corpus = self._corpus_description(trace)
        rework = next(
            (self._detail(item) for item in trace if item["action"] == "rework_request"),
            None,
        )
        recovery_calls = sum(
            item["action"] == "recovery_tool_call" for item in trace
        )
        second_evaluation = any(
            item["action"] == "consistency_pass"
            and int(self._detail(item).get("cycle", 0)) == 1
            for item in trace
        )
        recovery = ReportRecovery(
            occurred=rework is not None,
            deficiencies=tuple(rework.get("deficiencies", ())) if rework else (),
            required_periods=tuple(rework.get("required_periods", ())) if rework else (),
            required_document_ids=(
                tuple(rework.get("required_document_ids", ())) if rework else ()
            ),
            covered_periods=tuple(rework.get("covered_periods", ())) if rework else (),
            additional_tool_calls=recovery_calls,
            second_evaluation_performed=second_evaluation,
        )
        qualifications = tuple(dict.fromkeys(
            item.limitations for item in claims if item.limitations
        ))
        authority = ReportAuthority(
            run_id=str(run["run_id"]),
            repository_snapshot=str(run["repository_snapshot"]),
            runtime_identity=str(run["runtime_identity"]),
            harness_identity=self.HARNESS_IDENTITY,
            iqa_identity=self.IQA_IDENTITY,
            repository_authority=str(corpus.get("authority", "")),
            model_usage={
                str(key): int(value)
                for key, value in run.get("model_usage", {}).items()
            },
        )
        mappings = tuple(
            ReportClaimMapping(index, claim.evidence_ids, claim.periods)
            for index, claim in enumerate(claims)
        )
        values = {
            "schema_version": self.SCHEMA_VERSION,
            "question": str(result["question"]),
            "scope": scope,
            "status": InvestigationStatus(str(result["status"])),
            "lead_paragraph": str(assessment["lead_paragraph"]),
            "accepted_claims": claims,
            "claim_to_evidence_mappings": mappings,
            "evidence": evidence,
            "gaps": tuple(result["gaps"]),
            "qualifications": qualifications,
            "corpus_limitations": tuple(corpus.get("metadata_gaps", ())),
            "support_calibration": str(assessment["support_calibration"]),
            "completeness_calibration": str(assessment["completeness_calibration"]),
            "recovery": recovery,
            "authority": authority,
            "trace_reference": trace_reference,
        }
        canonical = json.dumps(
            asdict(ResearchReport(report_id="", **values)),
            sort_keys=True,
            separators=(",", ":"),
            default=str,
        ).encode()
        report_id = "research-report-" + hashlib.sha256(canonical).hexdigest()
        return ResearchReport(report_id=report_id, **values)

    @staticmethod
    def _detail(trace_item: Mapping[str, Any]) -> Mapping[str, Any]:
        return trace_item["detail"]

    @classmethod
    def _corpus_description(
        cls, trace: tuple[Mapping[str, Any], ...]
    ) -> Mapping[str, Any]:
        for item in trace:
            detail = cls._detail(item)
            if (
                item["action"] == "tool_result"
                and detail.get("name") == "describe_corpus"
            ):
                return detail["output"]
        return {}

    @staticmethod
    def _claim(value: Mapping[str, Any]) -> InvestigationClaim:
        return InvestigationClaim(
            text=str(value["text"]),
            evidence_ids=tuple(value["evidence_ids"]),
            periods=tuple(value["periods"]),
            interpretation=str(value["interpretation"]),
            limitations=str(value["limitations"]),
        )

    @staticmethod
    def _evidence(value: Mapping[str, Any]) -> EvidenceExcerpt:
        return EvidenceExcerpt(
            evidence_id=str(value["evidence_id"]),
            document_id=str(value["document_id"]),
            artifact_id=str(value["artifact_id"]),
            title=str(value["title"]),
            event_date=str(value["event_date"]),
            canonical_artifact_id=str(value["canonical_artifact_id"]),
            event_kind=value.get("event_kind"),
            speaker_label=value.get("speaker_label"),
            context_byte_start=int(value["context_byte_start"]),
            context_byte_end=int(value["context_byte_end"]),
            context_sha256=str(value["context_sha256"]),
            text=str(value["text"]),
            provenance_locations=tuple(value["provenance_locations"]),
        )
