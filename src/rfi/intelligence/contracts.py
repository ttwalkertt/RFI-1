"""Stable provider-neutral contracts for bounded source-grounded intelligence."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Protocol

from rfi.retrieval import EvidencePackage, RetrievalQuery, ResultClass


class IntelligenceError(RuntimeError):
    """Raised when governed reasoning cannot safely continue."""


class CompletionStatus(StrEnum):
    """Externally visible outcome of an intelligence execution."""

    COMPLETE = "complete"
    INCOMPLETE = "incomplete"
    REFUSED = "refused"
    FAILED = "failed"


class ClaimKind(StrEnum):
    """Authority class asserted by a claim."""

    SOURCE_EVIDENCE = "source-evidence"
    DERIVED_KNOWLEDGE = "derived-knowledge"
    MODEL_INFERENCE = "model-inference"


class StopReason(StrEnum):
    """Why bounded orchestration terminated."""

    REQUIREMENTS_SATISFIED = "requirements-satisfied"
    EVIDENCE_INSUFFICIENT = "evidence-insufficient"
    ITERATION_LIMIT = "iteration-limit"
    EVIDENCE_BUDGET = "evidence-budget"
    REFUSED = "refused"
    FAILURE = "failure"


class RetentionMode(StrEnum):
    """Governed persistence policy for model-facing execution material."""

    NONE = "none"
    METADATA = "metadata"
    FULL = "full"


@dataclass(frozen=True)
class InformationNeed:
    """Repository-owned request passed to planners without provider details."""

    text: str
    request_id: str = ""


@dataclass(frozen=True)
class IntelligenceBudget:
    """Hard orchestration and disclosure limits."""

    max_iterations: int = 4
    max_packages: int = 4
    max_total_evidence_bytes: int = 64_000
    max_model_input_chars: int = 80_000


@dataclass(frozen=True)
class RetrievalStep:
    """One inspectable governed retrieval action."""

    step_id: str
    purpose: str
    query: RetrievalQuery
    required_result_classes: tuple[ResultClass, ...]
    required_terms: tuple[str, ...] = ()


@dataclass(frozen=True)
class RetrievalPlan:
    """Structured plan independent of planner/model implementation."""

    plan_id: str
    interpretation: str
    steps: tuple[RetrievalStep, ...]
    budget: IntelligenceBudget
    refusal_reason: str | None = None


@dataclass(frozen=True)
class EvidenceReference:
    """Stable reference to an item in one consumed TASK-006 package."""

    evidence_id: str
    package_id: str
    authority: ClaimKind
    object_id: str
    document_ids: tuple[str, ...]
    source_object_ids: tuple[str, ...]


@dataclass(frozen=True)
class IntelligenceClaim:
    """One claim with mandatory evidence mapping and explicit authority class."""

    claim_id: str
    text: str
    kind: ClaimKind
    evidence_ids: tuple[str, ...]
    support_explanation: str
    confidence: float
    uncertainty: str | None = None


@dataclass(frozen=True)
class ContradictionReport:
    """Contradiction or ambiguity preserved from consumed packages."""

    description: str
    package_ids: tuple[str, ...]
    evidence_ids: tuple[str, ...] = ()


@dataclass(frozen=True)
class ReasoningDraft:
    """Provider output awaiting repository-owned grounding validation."""

    response: str
    claims: tuple[IntelligenceClaim, ...]
    uncertainties: tuple[str, ...]
    evidence_gaps: tuple[str, ...]
    contradictions: tuple[ContradictionReport, ...]
    requested_status: CompletionStatus


@dataclass(frozen=True)
class ModelEvidence:
    """Bounded provider-facing projection of public evidence-package contracts."""

    evidence: tuple[EvidenceReference, ...]
    package_ids: tuple[str, ...]
    content: str
    chars: int
    truncated: bool


@dataclass(frozen=True)
class ExecutionEvent:
    """Ordered operator-visible orchestration event."""

    sequence: int
    category: str
    detail: str
    step_id: str | None = None
    package_id: str | None = None


@dataclass(frozen=True)
class ExecutionTrace:
    """Inspectable planning, retrieval, model, iteration, and stopping history."""

    execution_id: str
    need: InformationNeed
    plan: RetrievalPlan | None
    events: tuple[ExecutionEvent, ...]
    retrieval_queries: tuple[RetrievalQuery, ...]
    package_ids: tuple[str, ...]
    evidence_packages: tuple[EvidencePackage, ...]
    model_input: ModelEvidence | None
    raw_model_output: ReasoningDraft | None
    iterations: int
    stop_reason: StopReason
    failures: tuple[str, ...]


@dataclass(frozen=True)
class IntelligenceResult:
    """Stable governed result independent of planner/model provider."""

    result_id: str
    execution_id: str
    status: CompletionStatus
    response: str
    claims: tuple[IntelligenceClaim, ...]
    evidence: tuple[EvidenceReference, ...]
    uncertainties: tuple[str, ...]
    evidence_gaps: tuple[str, ...]
    contradictions: tuple[ContradictionReport, ...]
    retrieval_trace_ids: tuple[str, ...]
    evidence_package_ids: tuple[str, ...]
    stopping_reason: StopReason


@dataclass(frozen=True)
class ExecutionRecord:
    """Complete in-memory result and operator trace."""

    result: IntelligenceResult
    trace: ExecutionTrace


@dataclass(frozen=True)
class RuntimePolicy:
    """Credential-free runtime and retention configuration."""

    planner_provider: str = "deterministic"
    reasoner_provider: str = "deterministic"
    retention: RetentionMode = RetentionMode.METADATA
    sensitive_content_allowed: bool = False
    credential_env_names: tuple[str, ...] = field(default_factory=tuple)


class EvidenceGateway(Protocol):
    """Only retrieval dependency allowed to the reasoning subsystem."""

    def retrieve(self, query: RetrievalQuery) -> EvidencePackage:
        """Return one governed, provenance-complete TASK-006 package."""


class Planner(Protocol):
    """Replaceable structured planning implementation."""

    def plan(self, need: InformationNeed, budget: IntelligenceBudget) -> RetrievalPlan:
        """Translate an information need into bounded retrieval steps."""

    def follow_up(
        self,
        need: InformationNeed,
        plan: RetrievalPlan,
        completed_steps: tuple[RetrievalStep, ...],
        missing_requirements: tuple[str, ...],
    ) -> RetrievalStep | None:
        """Return one explicit follow-up step, or stop."""


class Reasoner(Protocol):
    """Replaceable provider behind a repository-owned evidence input."""

    def reason(
        self,
        need: InformationNeed,
        plan: RetrievalPlan,
        evidence: ModelEvidence,
    ) -> ReasoningDraft:
        """Return an untrusted draft for grounding validation."""
