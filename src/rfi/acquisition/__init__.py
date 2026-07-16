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
from rfi.acquisition.engine import (
    AcquisitionEngine,
    AcquisitionKernel,
    AcquisitionRunResult,
    AdapterCandidate,
    AdapterFailure,
    AdapterRegistry,
    DiscoveryPage,
    EngineFailurePoint,
    FailureClass,
    RunStatus,
)
from rfi.acquisition.fixture_adapters import (
    FixtureCatalogAdapter,
    FixtureFeedAdapter,
    fixture_profiles,
)
from rfi.acquisition.repository import AcquisitionRepository

__all__ = [
    "AcquisitionReceipt",
    "AcquisitionEngine",
    "AcquisitionKernel",
    "AcquisitionRepository",
    "AcquisitionRunResult",
    "AdapterCandidate",
    "AdapterFailure",
    "AdapterRegistry",
    "CandidateDocument",
    "Checkpoint",
    "DiscoveryProvenance",
    "DiscoveryPage",
    "EngineFailurePoint",
    "FailurePoint",
    "FailureClass",
    "FixtureCatalogAdapter",
    "FixtureFeedAdapter",
    "RetrievalOutcome",
    "RetrievalResult",
    "RunStatus",
    "SourceProfile",
    "fixture_profiles",
]
