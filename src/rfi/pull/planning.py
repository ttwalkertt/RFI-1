"""Planning and attemptability for the concrete Pull Workflow."""

from __future__ import annotations

from dataclasses import asdict, dataclass

from rfi.firms.contracts import FirmRevision
from rfi.pull.adapters import RetrievalAdapterRegistry
from rfi.source_profiles.contracts import (
    AcquisitionTemplate,
    RetrievalCandidate,
    SourceProfileItem,
    SourceProfileRevision,
)
from rfi.source_profiles.synthesis import effective_items


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

    def __init__(
        self, template: AcquisitionTemplate, adapters: RetrievalAdapterRegistry,
        firms: object | None = None,
    ) -> None:
        self._template = template
        self._adapters = adapters
        self._firms = firms
        self._artifacts = {item.artifact_id: item for item in template.artifacts}
        self._modes = {item.mode: item for item in template.retrieval_modes}

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
        if self._firms is not None:
            items = effective_items(self._firms, firm.firm_id, items)  # type: ignore[arg-type]
        artifacts = []
        for item in items:
            if not item.enabled:
                continue
            canonical = self._artifacts[item.artifact_id]
            configured = tuple(
                candidate
                for candidate in item.retrieval_candidates
                if self._has_required_configuration(candidate)
            )
            runnable = tuple(
                candidate
                for candidate in configured
                if self._adapters.compatible(item.artifact_id, candidate)
            )
            if not item.retrieval_candidates:
                diagnostic = "No retrieval candidate configured."
            elif not configured:
                diagnostic = "Retrieval candidate lacks required configuration."
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

    def _has_required_configuration(self, candidate: RetrievalCandidate) -> bool:
        """Apply the canonical mode contract to synthesized as well as persisted candidates."""
        mode = self._modes.get(candidate.mode)
        if mode is None:
            return False
        values = asdict(candidate)
        populated = set()
        for name, value in values.items():
            if name in {"mode", "priority"}:
                continue
            if isinstance(value, str):
                present = bool(value.strip())
            else:
                present = value not in ((), [], None)
            if present:
                populated.add(name)
        return set(mode.required_fields).issubset(populated) and (
            not mode.required_any or bool(set(mode.required_any).intersection(populated))
        )
