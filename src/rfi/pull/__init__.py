"""RFI Pull Workflow public composition and contracts."""

from __future__ import annotations

from pathlib import Path

from rfi.acquisition import (
    AcquisitionRepository,
    DirectUrlAdapter,
)
from rfi.acquisition.edgar import USER_AGENT_VARIABLE, user_agent_from_environment
from rfi.acquisition.runtime_config import load_runtime_configuration
from rfi.acquisition.sec_form_10k import SecForm10KAdapter
from rfi.acquisition.sec_provider import SecProviderClient
from rfi.firms import FirmRepository
from rfi.pull.adapters import (
    RetrievalAdapterCapability,
    RetrievalAdapterError,
    RetrievalAdapterRegistration,
    RetrievalAdapterRegistry,
)
from rfi.pull.contracts import (
    ArtifactOutcome,
    ArtifactPullResult,
    ConfiguredFirm,
    FirmPullResult,
    PullError,
    PullRequest,
    PullRunResult,
    PullStage,
    PullStatus,
    PullSummary,
    RetrievalAttemptResult,
)
from rfi.pull.repository import PullRunRepository
from rfi.pull.workflow import PullWorkflow, utc_now
from rfi.source_profiles import SourceProfileRepository, load_canonical_template


def create_pull_workflow(state: Path) -> PullWorkflow:
    """Compose the production Pull Workflow over existing application state."""
    template = load_canonical_template()
    firms = FirmRepository.open(state / "firm-catalog")
    profiles = SourceProfileRepository.open(state / "source-profiles", template)
    acquisition = AcquisitionRepository(state / "acquisition")
    direct_url = DirectUrlAdapter(utc_now)

    def sec_user_agent() -> str:
        """Resolve governed runtime identity lazily, immediately before live SEC access."""
        runtime = load_runtime_configuration(Path.cwd())
        return user_agent_from_environment(
            f"env:{USER_AGENT_VARIABLE}", runtime
        )

    sec_10k = SecForm10KAdapter(SecProviderClient(sec_user_agent), utc_now)
    adapters = RetrievalAdapterRegistry(
        (
            RetrievalAdapterRegistration(
                RetrievalAdapterCapability("direct-url", (), ("direct_url",)),
                direct_url,
            ),
            RetrievalAdapterRegistration(
                RetrievalAdapterCapability(
                    sec_10k.adapter_id,
                    sec_10k.artifact_ids,
                    sec_10k.retrieval_modes,
                ),
                sec_10k,
            ),
        )
    )
    return PullWorkflow(
        firms,
        profiles,
        template,
        acquisition,
        adapters,
        PullRunRepository(state / "pull-workflows"),
    )


__all__ = [
    "ArtifactOutcome",
    "ArtifactPullResult",
    "ConfiguredFirm",
    "FirmPullResult",
    "PullError",
    "PullRequest",
    "PullRunRepository",
    "PullRunResult",
    "PullStage",
    "PullStatus",
    "PullSummary",
    "PullWorkflow",
    "RetrievalAdapterCapability",
    "RetrievalAdapterError",
    "RetrievalAdapterRegistration",
    "RetrievalAdapterRegistry",
    "RetrievalAttemptResult",
    "create_pull_workflow",
]
