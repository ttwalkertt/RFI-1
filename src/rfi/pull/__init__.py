"""RFI Pull Workflow public composition and contracts."""

from __future__ import annotations

from pathlib import Path

from rfi.acquisition import (
    AcquisitionRepository,
    AdapterRegistry,
    DirectUrlAdapter,
)
from rfi.firms import FirmRepository
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
    adapters = AdapterRegistry((DirectUrlAdapter(utc_now),))
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
    "RetrievalAttemptResult",
    "create_pull_workflow",
]
