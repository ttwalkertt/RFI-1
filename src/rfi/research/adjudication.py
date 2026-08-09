"""Non-retrieving consistency and calibration pass for closed investigations."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from rfi.research.contracts import (
    ClaimAssessment,
    ConsistencyAssessment,
    EvidenceExcerpt,
    InvestigationClaim,
    InvestigationRecord,
    InvestigationResult,
    InvestigationStatus,
    RecoveryRequest,
    ResearchError,
    TraceEntry,
)

_TEMPORAL_QUESTION = re.compile(
    r"\b(across|between|change[ds]?|earliest|evolv\w*|first|last|latest|over time|trend\w*)\b",
    re.IGNORECASE,
)
_FULL_RETAINED_SCOPE = re.compile(
    r"\b(across (?:all )?(?:the )?retained|entire retained|through (?:the )?latest|"
    r"over (?:all )?(?:the )?retained)\b",
    re.IGNORECASE,
)
_CHRONOLOGY_SCOPE = re.compile(
    r"\b(first|earliest)\b.*\b(last|latest|most recently)\b|"
    r"\b(last|latest|most recently)\b.*\b(first|earliest)\b",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class CorpusWindow:
    """Orientation facts captured before the evidence set was closed."""

    date_from: str | None
    date_through: str | None
    document_ids_by_period: dict[str, tuple[str, ...]]


class ClosedRecordAdjudicator:
    """Answer only what a completed investigation record responsibly supports."""

    def adjudicate(
        self,
        question: str,
        record: InvestigationRecord,
        corpus: CorpusWindow,
        trace: tuple[TraceEntry, ...],
    ) -> InvestigationResult:
        """Validate and calibrate without calling an access or model boundary."""
        evidence = {item.evidence_id: item for item in record.admissible_evidence}
        temporal = bool(_TEMPORAL_QUESTION.search(question))
        accepted: list[InvestigationClaim] = []
        assessments: list[ClaimAssessment] = []
        findings: list[str] = []
        repair_deficiencies: list[str] = []
        repair_periods: list[str] = []

        for index, claim in enumerate(record.candidate_claims):
            reasons = self._claim_reasons(claim, evidence, temporal)
            if reasons:
                assessments.append(ClaimAssessment(index, "rejected", tuple(reasons)))
                findings.extend(f"claim {index + 1}: {reason}" for reason in reasons)
                if claim.periods:
                    repair_deficiencies.append(
                        f"repair rejected claim {index + 1}: {'; '.join(reasons)}"
                    )
                    repair_periods.extend(claim.periods)
                continue
            assessments.append(ClaimAssessment(index, "supported", ()))
            accepted.append(claim)

        claimed_periods = tuple(sorted({
            period for claim in record.candidate_claims for period in claim.periods
        }))
        covered_periods = tuple(sorted({
            period for claim in accepted for period in claim.periods
        }))
        missing_periods: tuple[str, ...] = ()
        if accepted:
            missing_periods = self._assess_temporal_completeness(
                question, corpus, trace, covered_periods, findings
            )
            if missing_periods:
                repair_deficiencies.append(
                    "repair missing retained temporal boundary evidence"
                )
                repair_periods.extend(missing_periods)

        if not accepted:
            status = InvestigationStatus.INSUFFICIENT
            support = "none"
            completeness = "insufficient"
        elif findings or record.proposed_status is not InvestigationStatus.SUPPORTED:
            status = InvestigationStatus.PARTIAL
            support = "bounded"
            completeness = "partial"
        else:
            status = InvestigationStatus.SUPPORTED
            support = "strong"
            completeness = "complete"

        if record.proposed_status is InvestigationStatus.INSUFFICIENT and accepted:
            findings.append(
                "the investigation proposed insufficiency despite supported candidate claims"
            )
            status = InvestigationStatus.PARTIAL
            support = "bounded"
            completeness = "partial"
        if status is InvestigationStatus.INSUFFICIENT and not record.gaps:
            findings.append("the closed record does not explain its evidence gap")

        lead = self._lead(
            status, covered_periods, corpus, record.gaps, tuple(findings)
        )
        assessment = ConsistencyAssessment(
            support,
            completeness,
            lead,
            tuple(assessments),
            tuple(dict.fromkeys(findings)),
            claimed_periods,
            covered_periods,
            (
                RecoveryRequest(
                    tuple(dict.fromkeys(repair_deficiencies)),
                    tuple(dict.fromkeys(repair_periods)),
                    tuple(dict.fromkeys(
                        document_id
                        for period in repair_periods
                        for document_id in corpus.document_ids_by_period.get(period, ())
                    )),
                    covered_periods,
                )
                if (
                    status is InvestigationStatus.PARTIAL
                    and repair_deficiencies
                    and repair_periods
                )
                else None
            ),
        )
        cited = tuple(dict.fromkeys(
            evidence_id for claim in accepted for evidence_id in claim.evidence_ids
        ))
        answer = lead
        if accepted:
            answer += "\n\nSupported findings: " + " ".join(
                claim.text for claim in accepted
            )
        gaps = tuple(dict.fromkeys((*record.gaps, *assessment.findings)))
        return InvestigationResult(
            question,
            status,
            answer,
            tuple(accepted),
            tuple(evidence[item] for item in cited),
            gaps,
            record.failed_searches,
            (
                f"Closed-record consistency pass calibrated the result as {status.value}; "
                f"investigation stopping reason: {record.stopping_reason}"
            ),
            assessment,
        )

    @staticmethod
    def _claim_reasons(
        claim: InvestigationClaim,
        evidence: dict[str, EvidenceExcerpt],
        temporal: bool,
    ) -> list[str]:
        reasons = []
        if not claim.text or not claim.interpretation or not claim.limitations:
            reasons.append("required claim text, interpretation, or limitations are blank")
        if not claim.evidence_ids:
            reasons.append("claim has no evidence citations")
        unknown = [item for item in claim.evidence_ids if item not in evidence]
        if unknown:
            reasons.append("claim cites unexpanded or search-only evidence")
        known_dates = {
            evidence[item].event_date for item in claim.evidence_ids if item in evidence
        }
        if any(period not in known_dates for period in claim.periods):
            reasons.append("claim names a period without evidence from that event date")
        if temporal and not claim.periods:
            reasons.append("temporal claim has no explicit evidence-backed period")
        return reasons

    @staticmethod
    def _assess_temporal_completeness(
        question: str,
        corpus: CorpusWindow,
        trace: tuple[TraceEntry, ...],
        covered_periods: tuple[str, ...],
        findings: list[str],
    ) -> tuple[str, ...]:
        missing: list[str] = []
        if _FULL_RETAINED_SCOPE.search(question):
            required = tuple(
                item for item in (corpus.date_from, corpus.date_through) if item
            )
            missing = [item for item in required if item not in covered_periods]
            if missing:
                findings.append(
                    "the answer does not cover the full retained temporal scope; "
                    f"missing boundary period(s): {', '.join(missing)}"
                )
        if _CHRONOLOGY_SCOPE.search(question):
            orders = {
                str(item.detail.get("arguments", {}).get("order"))
                for item in trace
                if item.action == "tool_call"
                and item.detail.get("name") == "search_transcripts"
            }
            missing_orders = {"oldest", "latest"} - orders
            if missing_orders:
                findings.append(
                    "first/latest chronology was not tested with both oldest and latest search"
                )
        return tuple(missing)

    @staticmethod
    def _lead(
        status: InvestigationStatus,
        periods: tuple[str, ...],
        corpus: CorpusWindow,
        gaps: tuple[str, ...],
        findings: tuple[str, ...],
    ) -> str:
        if periods:
            supported_range = (
                periods[0] if len(periods) == 1 else f"{periods[0]} through {periods[-1]}"
            )
        else:
            supported_range = "no retained period"
        if status is InvestigationStatus.SUPPORTED:
            return (
                "The closed investigation record supports the stated findings for "
                f"{supported_range}; every accepted period is mapped to expanded evidence."
            )
        if status is InvestigationStatus.PARTIAL:
            boundary = (
                f"the retained corpus spans {corpus.date_from} through {corpus.date_through}"
                if corpus.date_from and corpus.date_through
                else "the requested scope is broader"
            )
            reason = findings[0] if findings else "material coverage remains incomplete"
            return (
                f"The closed investigation record supports only a partial answer for "
                f"{supported_range}; {boundary}, and {reason}."
            )
        reason = gaps[0] if gaps else (
            findings[0] if findings else "no candidate claim survived evidence validation"
        )
        return (
            "The closed investigation record is insufficient to answer the question "
            f"responsibly: {reason.rstrip('.')}."
        )


def parse_investigation_record(
    payload: dict[str, Any],
    expanded: dict[str, EvidenceExcerpt],
    observed_failed_searches: tuple[str, ...],
) -> InvestigationRecord:
    """Parse a model submission into an immutable closed evidence record."""
    try:
        status = InvestigationStatus(str(payload["status"]))
        answer = str(payload["answer"]).strip()
        claims = tuple(
            InvestigationClaim(
                str(item["text"]).strip(),
                tuple(str(value) for value in item["evidence_ids"]),
                tuple(str(value) for value in item["periods"]),
                str(item["interpretation"]).strip(),
                str(item["limitations"]).strip(),
            )
            for item in payload["claims"]
        )
        gaps = tuple(str(value).strip() for value in payload["gaps"] if str(value).strip())
        submitted_failed = tuple(
            str(value).strip()
            for value in payload["failed_searches"]
            if str(value).strip()
        )
        stopping_reason = str(payload["stopping_reason"]).strip()
    except (KeyError, TypeError, ValueError) as error:
        raise ResearchError("submitted investigation record is malformed") from error
    if not answer or not stopping_reason:
        raise ResearchError("submitted investigation record lacks an answer or stopping reason")
    failed = tuple(dict.fromkeys((*observed_failed_searches, *submitted_failed)))
    return InvestigationRecord(
        status,
        answer,
        claims,
        tuple(expanded.values()),
        gaps,
        failed,
        stopping_reason,
    )
