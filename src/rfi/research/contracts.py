"""Public contracts for retained-transcript access and iterative investigation."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Protocol


class ResearchError(RuntimeError):
    """Raised when governed transcript investigation cannot safely continue."""


class InvestigationStatus(StrEnum):
    """Evidence sufficiency of one non-authoritative investigation result."""

    SUPPORTED = "supported"
    PARTIAL = "partial"
    INSUFFICIENT = "insufficient"
    FAILED = "failed"


@dataclass(frozen=True)
class TranscriptScope:
    """Repository-owned artifact scope, independent of persistence layout."""

    firm_ids: tuple[str, ...]
    canonical_artifact_ids: tuple[str, ...] = (
        "earnings_transcript",
        "management_transcript",
    )
    source_effective_from: str | None = None
    source_effective_through: str | None = None


@dataclass(frozen=True)
class TranscriptDocument:
    """Compact retained-document orientation exposed by the access layer."""

    document_id: str
    artifact_id: str
    title: str
    firm_id: str
    canonical_artifact_id: str
    event_date: str
    event_kind: str | None
    provider: str | None
    checksum_sha256: str
    content_size: int
    segment_count: int
    speaker_context_available: bool
    provenance_locations: tuple[str, ...]


@dataclass(frozen=True)
class TranscriptSegment:
    """Exact retained-byte paragraph address used by the transcript IQA."""

    segment_id: str
    document_id: str
    artifact_id: str
    ordinal: int
    byte_start: int
    byte_end: int
    content_sha256: str
    text: str
    event_date: str
    title: str
    canonical_artifact_id: str
    event_kind: str | None
    speaker_label: str | None = None


@dataclass(frozen=True)
class CorpusDescription:
    """Model/operator orientation and capability dictionary."""

    authority: str
    repository_snapshot: str
    scope: TranscriptScope
    documents: tuple[TranscriptDocument, ...]
    segment_count: int
    date_from: str | None
    date_through: str | None
    canonical_artifact_counts: dict[str, int]
    event_kind_counts: dict[str, int]
    metadata_gaps: tuple[str, ...]
    capabilities: dict[str, str]


@dataclass(frozen=True)
class SearchHit:
    """Compact candidate returned before exact evidence expansion."""

    segment_id: str
    document_id: str
    title: str
    event_date: str
    canonical_artifact_id: str
    event_kind: str | None
    ordinal: int
    score: float
    excerpt: str


@dataclass(frozen=True)
class SearchResult:
    """Bounded lexical search response with honest empty-result semantics."""

    query: str
    normalized_terms: tuple[str, ...]
    order: str
    hits: tuple[SearchHit, ...]
    total_matches: int
    truncated: bool
    coverage_note: str


@dataclass(frozen=True)
class EvidenceExcerpt:
    """Verified exact context and provenance for one cited segment."""

    evidence_id: str
    document_id: str
    artifact_id: str
    title: str
    event_date: str
    canonical_artifact_id: str
    event_kind: str | None
    speaker_label: str | None
    context_byte_start: int
    context_byte_end: int
    context_sha256: str
    text: str
    provenance_locations: tuple[str, ...]


@dataclass(frozen=True)
class ModelBudget:
    """Hard local bounds independent of provider account limits."""

    max_tool_calls: int = 12
    max_model_turns: int = 10
    max_output_tokens_per_turn: int = 1_800
    max_tool_output_chars: int = 75_000

    def __post_init__(self) -> None:
        """Reject ineffective or unexpectedly expansive local execution bounds."""
        bounds = (
            ("max_tool_calls", self.max_tool_calls, 1, 40),
            ("max_model_turns", self.max_model_turns, 1, 30),
            ("max_output_tokens_per_turn", self.max_output_tokens_per_turn, 128, 10_000),
            ("max_tool_output_chars", self.max_tool_output_chars, 1_000, 1_000_000),
        )
        for name, value, minimum, maximum in bounds:
            if not isinstance(value, int) or isinstance(value, bool):
                raise ResearchError(f"{name} must be an integer")
            if not minimum <= value <= maximum:
                raise ResearchError(
                    f"{name} must be between {minimum} and {maximum}"
                )


@dataclass(frozen=True)
class ModelToolCall:
    """Provider-neutral model request to use one allowlisted access operation."""

    call_id: str
    name: str
    arguments: dict[str, Any]


@dataclass(frozen=True)
class ModelTurn:
    """One provider response, normalized before harness control decisions."""

    tool_calls: tuple[ModelToolCall, ...]
    response_items: tuple[dict[str, Any], ...]
    text: str = ""
    usage: dict[str, int] = field(default_factory=dict)


class InvestigationSession(Protocol):
    """Replaceable stateful model session behind the investigating harness."""

    def next_turn(
        self, tool_outputs: tuple[tuple[str, dict[str, Any]], ...]
    ) -> ModelTurn:
        """Return the next normalized turn for zero or more tool results."""


class InvestigationModel(Protocol):
    """Replaceable LLM boundary; no repository operation is exposed here."""

    @property
    def runtime_identity(self) -> str:
        """Return a non-secret provider/model identity for traces."""

    def start(
        self,
        question: str,
        instructions: str,
        tools: tuple[dict[str, Any], ...],
        budget: ModelBudget,
    ) -> InvestigationSession:
        """Begin one bounded investigation session."""


@dataclass(frozen=True)
class InvestigationClaim:
    """One model interpretation mapped only to expanded retained evidence."""

    text: str
    evidence_ids: tuple[str, ...]
    periods: tuple[str, ...]
    interpretation: str
    limitations: str


@dataclass(frozen=True)
class InvestigationRecord:
    """Closed investigation output before consistency adjudication."""

    proposed_status: InvestigationStatus
    proposed_answer: str
    candidate_claims: tuple[InvestigationClaim, ...]
    admissible_evidence: tuple[EvidenceExcerpt, ...]
    gaps: tuple[str, ...]
    failed_searches: tuple[str, ...]
    stopping_reason: str


@dataclass(frozen=True)
class ClaimAssessment:
    """Closed-record disposition for one candidate claim."""

    claim_index: int
    disposition: str
    reasons: tuple[str, ...]


@dataclass(frozen=True)
class RecoveryRequest:
    """One evaluator-issued, deficiency-scoped recovery instruction."""

    deficiencies: tuple[str, ...]
    required_periods: tuple[str, ...]
    required_document_ids: tuple[str, ...]
    covered_periods: tuple[str, ...]


@dataclass(frozen=True)
class ConsistencyAssessment:
    """Categorical support and completeness calibration without retrieval."""

    support_calibration: str
    completeness_calibration: str
    lead_paragraph: str
    claim_assessments: tuple[ClaimAssessment, ...]
    findings: tuple[str, ...]
    claimed_periods: tuple[str, ...]
    covered_periods: tuple[str, ...]
    recovery_request: RecoveryRequest | None


@dataclass(frozen=True)
class TraceEntry:
    """One inspectable model or access-layer action."""

    sequence: int
    action: str
    detail: dict[str, Any]


@dataclass(frozen=True)
class InvestigationResult:
    """Validated non-authoritative answer and evidence-sufficiency assessment."""

    question: str
    status: InvestigationStatus
    answer: str
    claims: tuple[InvestigationClaim, ...]
    evidence: tuple[EvidenceExcerpt, ...]
    gaps: tuple[str, ...]
    failed_searches: tuple[str, ...]
    stopping_reason: str
    assessment: ConsistencyAssessment


@dataclass(frozen=True)
class InvestigationRun:
    """Result plus complete iterative trace and bounded runtime metadata."""

    run_id: str
    repository_snapshot: str
    runtime_identity: str
    investigation_record: InvestigationRecord
    result: InvestigationResult
    trace: tuple[TraceEntry, ...]
    model_usage: dict[str, int]


@dataclass(frozen=True)
class ReportClaimMapping:
    """Stable accepted-claim mapping for downstream report consumers."""

    claim_index: int
    evidence_ids: tuple[str, ...]
    periods: tuple[str, ...]


@dataclass(frozen=True)
class ReportRecovery:
    """Recorded single-cycle recovery history, copied without reinterpretation."""

    occurred: bool
    deficiencies: tuple[str, ...]
    required_periods: tuple[str, ...]
    required_document_ids: tuple[str, ...]
    covered_periods: tuple[str, ...]
    additional_tool_calls: int
    second_evaluation_performed: bool


@dataclass(frozen=True)
class ReportAuthority:
    """Run and authority identities required for independent audit."""

    run_id: str
    repository_snapshot: str
    runtime_identity: str
    harness_identity: str
    iqa_identity: str
    repository_authority: str
    model_usage: dict[str, int]


@dataclass(frozen=True)
class ResearchReport:
    """Authoritative Stage-1 analytical output derived from final adjudication."""

    schema_version: str
    report_id: str
    question: str
    scope: TranscriptScope
    status: InvestigationStatus
    lead_paragraph: str
    accepted_claims: tuple[InvestigationClaim, ...]
    claim_to_evidence_mappings: tuple[ReportClaimMapping, ...]
    evidence: tuple[EvidenceExcerpt, ...]
    gaps: tuple[str, ...]
    qualifications: tuple[str, ...]
    corpus_limitations: tuple[str, ...]
    support_calibration: str
    completeness_calibration: str
    recovery: ReportRecovery
    authority: ReportAuthority
    trace_reference: str
