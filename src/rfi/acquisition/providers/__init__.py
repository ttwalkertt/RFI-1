"""Explicit transcript-provider implementations and dispatch registry."""

from __future__ import annotations

from typing import Callable, Protocol

from rfi.acquisition.contracts import ContractError, RetrievalResult, SourceProfile, TranscriptSeed
from rfi.acquisition.earnings_transcripts import EarningsTranscriptTransport
from rfi.acquisition.engine import AdapterCandidate, DiscoveryPage
from rfi.acquisition.providers.stockanalysis import StockAnalysisTranscriptProvider


class TranscriptProvider(Protocol):
    provider: str

    def discover(
        self, profile: SourceProfile, seed: TranscriptSeed, target: object
    ) -> DiscoveryPage: ...

    def retrieve(self, profile: SourceProfile, candidate: AdapterCandidate) -> RetrievalResult: ...


class TranscriptProviderFactory(Protocol):
    """Provider-neutral constructor registered for explicit name-based dispatch."""

    provider: str

    def __call__(
        self,
        transport: EarningsTranscriptTransport,
        clock: Callable[[], str],
    ) -> TranscriptProvider: ...


class TranscriptProviderRegistry:
    """One explicit provider-name dispatch definition; URL shape is never consulted."""

    def __init__(self, providers: tuple[TranscriptProviderFactory, ...]) -> None:
        self._providers = {provider.provider: provider for provider in providers}
        if len(self._providers) != len(providers):
            raise ContractError("duplicate transcript provider registration")

    def create(
        self,
        name: str,
        transport: EarningsTranscriptTransport,
        clock: Callable[[], str],
    ) -> TranscriptProvider:
        implementation = self.resolve(name)
        return implementation(transport, clock)

    def resolve(self, name: str) -> TranscriptProviderFactory:
        """Resolve one explicit provider name without consulting seed content."""
        if not isinstance(name, str) or not name.strip():
            raise ContractError("transcript provider must be a non-empty string")
        implementation = self._providers.get(name)
        if implementation is None:
            raise ContractError(f"unknown transcript provider: {name}")
        return implementation

    def registrations(self) -> dict[str, str]:
        return {
            name: implementation.__name__
            for name, implementation in sorted(self._providers.items())
        }


__all__ = [
    "StockAnalysisTranscriptProvider",
    "TranscriptProvider",
    "TranscriptProviderFactory",
    "TranscriptProviderRegistry",
]
