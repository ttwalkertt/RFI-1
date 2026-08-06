"""Feed-entry adapter for the existing governed acquisition engine."""

from __future__ import annotations

import hashlib
from collections.abc import Callable

from rfi.acquisition import (
    AdapterCandidate,
    AdapterFailure,
    DiscoveryPage,
    DiscoveryProvenance,
    FailureClass,
    RetrievalResult,
    SourceProfile,
)
from rfi.feeds.contracts import FeedEntry, FeedError
from rfi.feeds.transport import FeedHttpTransport


class FeedEntryAdapter:
    """Expose normalized entries as candidates without owning persistence."""

    mechanism = "repository_feed"

    def __init__(
        self,
        entries: tuple[tuple[FeedEntry, str], ...],
        transport: FeedHttpTransport,
        clock: Callable[[], str],
    ) -> None:
        self._entries = entries
        self._transport = transport
        self._clock = clock
        self.by_candidate: dict[str, tuple[FeedEntry, str]] = {}

    def discover(self, profile: SourceProfile, continuation: str | None) -> DiscoveryPage:
        if continuation is not None:
            raise AdapterFailure(FailureClass.MALFORMED_ADAPTER, "feed has no continuation", False)
        candidates = []
        feed_id = str(profile.policy.get("feed_id", ""))
        feed_url = str(profile.configuration.get("feed_url", ""))
        for position, (entry, material_hash) in enumerate(self._entries, 1):
            key_hash = hashlib.sha256(entry.entry_key.encode()).hexdigest()[:24]
            candidate_id = f"feedcandidate-{key_hash}-{material_hash[:12]}"
            document_id = f"feeddocument-{key_hash}"
            self.by_candidate[candidate_id] = (entry, material_hash)
            candidates.append(AdapterCandidate(
                candidate_id,
                document_id,
                position,
                f"feedrevision-{material_hash[:24]}",
                DiscoveryProvenance(
                    self._clock(),
                    self.mechanism,
                    {"feed_id": feed_id, "entry_id": entry.entry_key[:512]},
                    tuple(value for value in (feed_url, entry.url) if value),
                    {"configured_source": True},
                ),
            ))
        return DiscoveryPage(tuple(candidates), None, {"normalized_entries": len(candidates)})

    def retrieve(self, profile: SourceProfile, candidate: AdapterCandidate) -> RetrievalResult:
        entry = self.by_candidate.get(candidate.candidate_id)
        if entry is None:
            raise AdapterFailure(FailureClass.MALFORMED_ADAPTER, "unknown feed candidate", False)
        if not entry[0].url:
            raise AdapterFailure(
                FailureClass.PERMANENT_RETRIEVAL, "feed entry has no artifact URL", False,
            )
        try:
            response = self._transport.fetch(entry[0].url)
        except FeedError as error:
            retryable = "HTTP 4" not in str(error)
            raise AdapterFailure(
                FailureClass.TRANSIENT_ADAPTER if retryable else FailureClass.PERMANENT_RETRIEVAL,
                str(error), retryable,
            ) from error
        return RetrievalResult(
            response.content,
            response.media_type,
            self._clock(),
            self.mechanism,
            {"feed_entry_id": entry[0].entry_key[:512]},
            {"http_status": response.status, "final_url": response.final_url},
        )
