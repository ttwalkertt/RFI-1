"""Artifact-semantic retrieval adapter capability and selection boundary."""

from __future__ import annotations

from dataclasses import dataclass

from rfi.acquisition.engine import AdapterRegistry, SourceAdapter
from rfi.source_profiles.contracts import RetrievalCandidate


class RetrievalAdapterError(RuntimeError):
    """Raised when retrieval-adapter capability selection is absent or ambiguous."""


@dataclass(frozen=True)
class RetrievalAdapterCapability:
    """One explicit artifact/mode capability declaration."""

    adapter_id: str
    artifact_ids: tuple[str, ...]
    retrieval_modes: tuple[str, ...]

    def supports(self, artifact_id: str, mode: str) -> bool:
        """Return whether this declaration can satisfy the exact configured intent."""
        artifact_supported = not self.artifact_ids or artifact_id in self.artifact_ids
        return artifact_supported and mode in self.retrieval_modes


@dataclass(frozen=True)
class RetrievalAdapterRegistration:
    """Bind declared pull capability to one acquisition-engine source adapter."""

    capability: RetrievalAdapterCapability
    source_adapter: SourceAdapter


class RetrievalAdapterRegistry:
    """Deterministic, inspectable capability selection without artifact branching."""

    def __init__(
        self, registrations: tuple[RetrievalAdapterRegistration, ...] = ()
    ) -> None:
        self._registrations: dict[str, RetrievalAdapterRegistration] = {}
        for registration in registrations:
            capability = registration.capability
            if not capability.adapter_id:
                raise RetrievalAdapterError("retrieval adapter identity must not be blank")
            if capability.adapter_id in self._registrations:
                raise RetrievalAdapterError(
                    f"retrieval adapter already registered: {capability.adapter_id}"
                )
            if not capability.retrieval_modes:
                raise RetrievalAdapterError(
                    f"retrieval adapter declares no modes: {capability.adapter_id}"
                )
            if len(set(capability.artifact_ids)) != len(capability.artifact_ids):
                raise RetrievalAdapterError(
                    f"retrieval adapter repeats an artifact: {capability.adapter_id}"
                )
            if len(set(capability.retrieval_modes)) != len(capability.retrieval_modes):
                raise RetrievalAdapterError(
                    f"retrieval adapter repeats a mode: {capability.adapter_id}"
                )
            self._registrations[capability.adapter_id] = registration
        ordered = tuple(self._registrations.values())
        for index, left in enumerate(ordered):
            for right in ordered[index + 1 :]:
                shared_modes = set(left.capability.retrieval_modes).intersection(
                    right.capability.retrieval_modes
                )
                left_artifacts = set(left.capability.artifact_ids)
                right_artifacts = set(right.capability.artifact_ids)
                artifact_overlap = (
                    not left_artifacts
                    or not right_artifacts
                    or bool(left_artifacts.intersection(right_artifacts))
                )
                if shared_modes and artifact_overlap:
                    raise RetrievalAdapterError(
                        "ambiguous retrieval adapter declarations: "
                        f"{left.capability.adapter_id}, {right.capability.adapter_id}"
                    )

    def compatible(
        self, artifact_id: str, candidate: RetrievalCandidate
    ) -> tuple[RetrievalAdapterRegistration, ...]:
        """Return compatible registrations in stable adapter identity order."""
        return tuple(
            registration
            for adapter_id, registration in sorted(self._registrations.items())
            if registration.capability.supports(artifact_id, candidate.mode)
        )

    def select(
        self, artifact_id: str, candidate: RetrievalCandidate
    ) -> RetrievalAdapterRegistration:
        """Select exactly one compatible adapter or fail closed."""
        matches = self.compatible(artifact_id, candidate)
        if not matches:
            raise RetrievalAdapterError(
                "no compatible retrieval adapter for "
                f"artifact {artifact_id} and mode {candidate.mode}"
            )
        if len(matches) != 1:
            identities = ", ".join(item.capability.adapter_id for item in matches)
            raise RetrievalAdapterError(
                "ambiguous retrieval adapter capability for "
                f"artifact {artifact_id} and mode {candidate.mode}: {identities}"
            )
        return matches[0]

    def registrations(self) -> tuple[dict[str, object], ...]:
        """Return deterministic operator-visible capability declarations."""
        return tuple(
            {
                "adapter_id": item.capability.adapter_id,
                "artifact_ids": list(item.capability.artifact_ids),
                "retrieval_modes": list(item.capability.retrieval_modes),
                "acquisition_mechanism": item.source_adapter.mechanism,
                "implementation": type(item.source_adapter).__name__,
            }
            for _adapter_id, item in sorted(self._registrations.items())
        )

    def acquisition_registry(self, adapter_id: str) -> AdapterRegistry:
        """Project the selected adapter into the mechanism-keyed acquisition boundary."""
        registration = self._registrations.get(adapter_id)
        if registration is None:
            raise RetrievalAdapterError(
                f"retrieval adapter is not registered: {adapter_id}"
            )
        return AdapterRegistry((registration.source_adapter,))
