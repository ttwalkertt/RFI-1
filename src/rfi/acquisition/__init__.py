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
from rfi.acquisition.direct_url import DirectUrlAdapter
from rfi.acquisition.edgar import (
    EdgarAdapter,
    load_edgar_profiles,
    user_agent_from_environment,
    validate_edgar_profile,
)
from rfi.acquisition.fixture_adapters import (
    FixtureCatalogAdapter,
    FixtureFeedAdapter,
    fixture_profiles,
)
from rfi.acquisition.repository import AcquisitionRepository
from rfi.acquisition.runtime_config import load_runtime_configuration
from rfi.acquisition.sec_api import (
    SecApiAdapter,
    credential_from_environment,
    load_live_profiles,
    validate_live_profile,
)

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
    "DirectUrlAdapter",
    "EngineFailurePoint",
    "EdgarAdapter",
    "FailurePoint",
    "FailureClass",
    "FixtureCatalogAdapter",
    "FixtureFeedAdapter",
    "RetrievalOutcome",
    "RetrievalResult",
    "RunStatus",
    "SecApiAdapter",
    "SourceProfile",
    "credential_from_environment",
    "fixture_profiles",
    "load_live_profiles",
    "load_edgar_profiles",
    "load_runtime_configuration",
    "user_agent_from_environment",
    "validate_live_profile",
    "validate_edgar_profile",
]
