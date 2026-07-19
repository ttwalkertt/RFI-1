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
from rfi.acquisition.sec_form_10q import SecForm10QAdapter
from rfi.acquisition.sec_form_20f import SecForm20FAdapter
from rfi.acquisition.sec_form_6k import SecForm6KAdapter
from rfi.acquisition.sec_form_8k import SecForm8KAdapter
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

    provider = SecProviderClient(sec_user_agent)
    numbered_forms = (
        SecForm10KAdapter(provider, utc_now),
        SecForm10QAdapter(provider, utc_now),
        SecForm8KAdapter(provider, utc_now),
        SecForm20FAdapter(provider, utc_now),
        SecForm6KAdapter(provider, utc_now),
    )
    adapters = RetrievalAdapterRegistry(
        (
            RetrievalAdapterRegistration(
                RetrievalAdapterCapability("direct-url", (), ("direct_url",)),
                direct_url,
            ),
            *(
                RetrievalAdapterRegistration(
                    RetrievalAdapterCapability(
                        adapter.adapter_id,
                        adapter.artifact_ids,
                        adapter.retrieval_modes,
                    ),
                    adapter,
                )
                for adapter in numbered_forms
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
