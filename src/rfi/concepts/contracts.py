"""Public contracts for business concepts, methods, and observations."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Protocol


class ConceptError(RuntimeError):
    """Raised when catalog state or a requested concept change is invalid."""


class CalculationError(ConceptError):
    """Raised when a deterministic method cannot produce a trustworthy result."""


class ConceptStatus(StrEnum):
    """Operator-owned lifecycle state for a concept definition."""

    DRAFT = "draft"
    ACTIVE = "active"
    RETIRED = "retired"
    SUPERSEDED = "superseded"


class MethodKind(StrEnum):
    """Initial method families; custom families use the extension registry."""

    EXTRACTED = "extracted"
    DETERMINISTIC = "deterministic"
    STATE = "state"
    EVENT = "event"
    ASSERTION = "assertion"
    FORECAST = "forecast"
    RELATIONSHIP = "relationship"


class ObservationOrigin(StrEnum):
    """How an observation entered the system without implying authority."""

    EXTRACTED = "extracted"
    CALCULATED = "calculated"
    OPERATOR = "operator"


@dataclass(frozen=True)
class ObservationMethod:
    """One revision-scoped admissible way to observe or derive a concept."""

    method_id: str
    kind: str
    name: str
    result_shape: str
    configuration: dict[str, Any] = field(default_factory=dict)
    aliases: tuple[str, ...] = ()
    extraction_hints: tuple[str, ...] = ()
    expected_evidence_locations: tuple[str, ...] = ()
    required_inputs: tuple[str, ...] = ()
    optional_inputs: tuple[str, ...] = ()
    units: tuple[str, ...] = ()
    dimensions: tuple[str, ...] = ()
    period_expectation: str | None = None
    scope_expectation: str | None = None
    validation_conditions: tuple[str, ...] = ()
    comparison_semantics: str | None = None
    confidence_rules: tuple[str, ...] = ()
    tolerance: dict[str, Any] = field(default_factory=dict)
    warnings: tuple[str, ...] = ()
    comments: str = ""
    valid_from: str | None = None
    valid_through: str | None = None
    sample_cases: tuple[dict[str, Any], ...] = ()


@dataclass(frozen=True)
class ConceptRevision:
    """One immutable historical meaning for a stable concept identity."""

    concept_id: str
    revision_id: str
    revision_number: int
    display_name: str
    definition: str
    comments: str
    aliases: tuple[str, ...]
    hints: tuple[str, ...]
    status: ConceptStatus
    tags: tuple[str, ...]
    classifications: dict[str, str]
    valid_from: str
    valid_through: str | None
    sample_date: str | None
    created_at: str
    updated_at: str
    supersedes_revision_id: str | None
    methods: tuple[ObservationMethod, ...]
    related_concept_ids: tuple[str, ...] = ()
    samples: tuple[dict[str, Any], ...] = ()
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True)
class ConceptDraft:
    """Validated mutable intent used to create a new immutable revision."""

    concept_id: str
    display_name: str
    definition: str
    valid_from: str
    comments: str = ""
    aliases: tuple[str, ...] = ()
    hints: tuple[str, ...] = ()
    status: ConceptStatus = ConceptStatus.DRAFT
    tags: tuple[str, ...] = ()
    classifications: dict[str, str] = field(default_factory=dict)
    valid_through: str | None = None
    sample_date: str | None = None
    methods: tuple[ObservationMethod, ...] = ()
    related_concept_ids: tuple[str, ...] = ()
    samples: tuple[dict[str, Any], ...] = ()
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True)
class LineageReference:
    """Exact input observation identity retained by a calculated result."""

    observation_id: str
    concept_id: str
    concept_revision_id: str
    method_id: str
    role: str


@dataclass(frozen=True)
class Observation:
    """A value, state, event, relationship, or assertion distinct from its concept."""

    observation_id: str
    concept_id: str
    concept_revision_id: str
    method_id: str
    origin: ObservationOrigin
    result_shape: str
    value: Any
    unit: str | None = None
    dimensions: dict[str, str] = field(default_factory=dict)
    period_start: str | None = None
    period_end: str | None = None
    effective_at: str | None = None
    scope: str | None = None
    provenance: tuple[dict[str, Any], ...] = ()
    lineage: tuple[LineageReference, ...] = ()
    confidence: float | None = None
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True)
class Reconciliation:
    """Visible comparison that never merges or suppresses either observation."""

    left_observation_id: str
    right_observation_id: str
    absolute_difference: float
    within_tolerance: bool
    tolerance: float
    unit: str | None


class ConceptCatalog(Protocol):
    """Persistence-independent catalog interface used by programs and the GUI."""

    def create(self, draft: ConceptDraft) -> ConceptRevision:
        """Create the first immutable revision for one stable identity."""

    def validate(self, draft: ConceptDraft) -> None:
        """Validate editable intent without publishing a revision."""

    def revise(
        self,
        concept_id: str,
        draft: ConceptDraft,
        expected_revision_id: str,
    ) -> ConceptRevision:
        """Append a revision when the caller still targets the current revision."""

    def get(self, concept_id: str, revision_id: str | None = None) -> ConceptRevision:
        """Return a current or named historical revision."""

    def history(self, concept_id: str) -> tuple[ConceptRevision, ...]:
        """Return every immutable revision in ascending order."""

    def lookup(
        self,
        query: str = "",
        tag: str | None = None,
        status: ConceptStatus | None = None,
        valid_on: str | None = None,
    ) -> tuple[ConceptRevision, ...]:
        """Search current concepts through stable public fields."""
