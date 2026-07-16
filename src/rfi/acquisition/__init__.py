"""Repository-owned acquisition substrate contracts and persistence."""

from rfi.acquisition.contracts import (
    AcquisitionReceipt,
    CandidateDocument,
    Checkpoint,
    DiscoveryProvenance,
    FailurePoint,
    RetrievalOutcome,
    RetrievalResult,
    SourceProfile,
)
from rfi.acquisition.repository import AcquisitionRepository

__all__ = [
    "AcquisitionReceipt",
    "AcquisitionRepository",
    "CandidateDocument",
    "Checkpoint",
    "DiscoveryProvenance",
    "FailurePoint",
    "RetrievalOutcome",
    "RetrievalResult",
    "SourceProfile",
]
