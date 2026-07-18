"""Planning and attemptability for the concrete Pull Workflow."""

from __future__ import annotations

from dataclasses import dataclass

from rfi.firms.contracts import FirmRevision
from rfi.source_profiles.contracts import (
    AcquisitionTemplate,
    RetrievalCandidate,
    SourceProfileItem,
    SourceProfileRevision,
)


@dataclass(frozen=True)
class PlannedArtifact:
    """One enabled artifact and its prioritized, snapshotted retrieval candidates."""

    artifact_id: str
    label: str
    candidates: tuple[RetrievalCandidate, ...]
    runnable_candidates: tuple[RetrievalCandidate, ...]
    attemptability_diagnostic: str


@dataclass(frozen=True)
class PlannedFirm:
    """One resolved firm bound to an exact source-profile snapshot."""

    firm: FirmRevision
    profile: SourceProfileRevision | None
    items: tuple[SourceProfileItem, ...]
    artifacts: tuple[PlannedArtifact, ...]


class PullPlanner:
    """Expand enabled profile items and classify adapter availability."""

    def __init__(self, template: AcquisitionTemplate, available_modes: tuple[str, ...]) -> None:
        self._template = template
        self._available_modes = frozenset(available_modes)
        self._artifacts = {item.artifact_id: item for item in template.artifacts}

    def plan(
        self,
        firm: FirmRevision,
        profile: SourceProfileRevision | None,
    ) -> PlannedFirm:
        """Plan only from the supplied immutable revision or documented defaults."""
        items = (
            profile.items
            if profile is not None
            else tuple(
                SourceProfileItem(item.artifact_id, item.default_enabled)
                for item in self._template.artifacts
            )
        )
        artifacts = []
        for item in items:
            if not item.enabled:
                continue
            canonical = self._artifacts[item.artifact_id]
            runnable = tuple(
                candidate
                for candidate in item.retrieval_candidates
                if candidate.mode in self._available_modes
            )
            if not item.retrieval_candidates:
                diagnostic = "No retrieval candidate configured."
            elif not runnable:
                diagnostic = "No adapter available for this retrieval mode."
            else:
                diagnostic = "Runnable retrieval candidate available."
            artifacts.append(
                PlannedArtifact(
                    item.artifact_id,
                    canonical.label,
                    item.retrieval_candidates,
                    runnable,
                    diagnostic,
                )
            )
        return PlannedFirm(firm, profile, items, tuple(artifacts))
