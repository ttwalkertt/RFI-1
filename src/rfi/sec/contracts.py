"""SEC-specific authoritative source and workflow contracts."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol

from rfi.firms.contracts import FirmRevision


class SecWorkflowError(RuntimeError):
    """Raised for malformed SEC workflow requests or durable state."""


class SecApplicability(StrEnum):
    DIRECT = "direct"
    PARENT = "parent"
    NON_APPLICABLE = "non_applicable"


class SecWorkflowOutcome(StrEnum):
    SUCCESS = "success"
    SUCCESS_WITH_SOURCE_BOOTSTRAP = "success_with_source_bootstrap"
    NON_APPLICABLE = "non_applicable"
    NO_QUALIFYING_FILING = "no_qualifying_filing"
    SOURCE_AMBIGUITY = "source_ambiguity"
    SOURCE_CONFLICT = "source_conflict"
    RETRIEVAL_FAILURE = "retrieval_failure"
    CANCELLED = "cancelled"


class SecWorkflowState(StrEnum):
    RECEIVED = "received"
    APPLICABILITY_DETERMINED = "applicability_determined"
    SOURCE_LOADED = "source_loaded"
    SOURCE_VALIDATED = "source_validated"
    IDENTITY_RESOLVED = "identity_resolved"
    SOURCE_PERSISTED = "source_persisted"
    FILING_POLICY_DETERMINED = "filing_policy_determined"
    FILINGS_ENUMERATED = "filings_enumerated"
    FILING_SELECTED = "filing_selected"
    DOCUMENT_RETRIEVED = "document_retrieved"
    RETRIEVAL_VALIDATED = "retrieval_validated"
    ARTIFACT_INGESTED = "artifact_ingested"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


@dataclass(frozen=True)
class SecSourceKnowledge:
    firm_id: str
    applicability: SecApplicability
    legal_issuer: str
    cik: str | None
    filing_regime: str
    verification_status: str
    verified_at: str
    parent_firm_id: str | None = None


@dataclass(frozen=True)
class SecResolution:
    """Authoritative resolver result; ambiguity is explicit, never guessed."""

    source: SecSourceKnowledge | None
    candidates: tuple[str, ...] = ()
    diagnostic: str = ""


class SecIdentityResolver(Protocol):
    def resolve(self, firm: FirmRevision, verified_at: str) -> SecResolution:
        """Resolve one firm using authoritative identity evidence."""

    def validate(
        self, firm: FirmRevision, source: SecSourceKnowledge, verified_at: str
    ) -> SecResolution:
        """Validate an existing source without silently replacing identity."""


@dataclass(frozen=True)
class SecWorkflowResult:
    run_id: str
    firm_id: str
    outcome: SecWorkflowOutcome
    current_state: SecWorkflowState
    requested_at: str
    completed_at: str
    source_bootstrapped: bool
    source_refreshed: bool
    artifact_ids: tuple[str, ...]
    states: tuple[SecWorkflowState, ...]
    diagnostics: tuple[str, ...]

