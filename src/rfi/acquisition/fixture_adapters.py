"""Deterministic file-backed adapters that exercise the production engine boundary."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from rfi.acquisition.contracts import DiscoveryProvenance, RetrievalResult, SourceProfile
from rfi.acquisition.engine import (
    AdapterCandidate,
    AdapterFailure,
    DiscoveryPage,
    FailureClass,
)


class FixtureAdapterBase:
    """Shared fixture decoding without repository or network access."""

    mechanism = "fixture-base"

    def __init__(self, fixture_root: Path, scenario_file: str, state: str = "default") -> None:
        self._root = fixture_root
        self._scenario_file = scenario_file
        self.state = state
        self.transient_retrieval_failures: set[str] = set()
        self.transient_discovery_failures: set[str] = set()
        self.malformed_discovery = False

    def _scenario(self) -> dict[str, Any]:
        """Load checked-in provider state for the selected deterministic phase."""
        path = self._root / self._scenario_file
        value = json.loads(path.read_text(encoding="utf-8"))
        return value["states"][self.state]

    def _candidate(self, profile: SourceProfile, value: dict[str, Any]) -> AdapterCandidate:
        """Decode one fixture item into the real adapter candidate contract."""
        return AdapterCandidate(
            candidate_id=value["candidate_id"],
            document_id=value["document_id"],
            position=value["position"],
            revision=value["revision"],
            provenance=DiscoveryProvenance(
                discovered_at=value["discovered_at"],
                discovery_method=self.mechanism,
                provider_identifiers=value.get("provider_identifiers", {}),
                locations=tuple(value.get("locations", [])),
                metadata={
                    "fixture_source": profile.source_id,
                    "ordering_key": value["position"],
                    "revision": value["revision"],
                },
            ),
            disposition=value.get("disposition", "acquire"),
            disposition_reason=value.get("disposition_reason"),
        )

    def retrieve(
        self, profile: SourceProfile, candidate: AdapterCandidate
    ) -> RetrievalResult:
        """Read exact fixture bytes or raise a classified deterministic failure."""
        del profile
        if candidate.candidate_id in self.transient_retrieval_failures:
            raise AdapterFailure(
                FailureClass.TRANSIENT_ADAPTER,
                f"fixture retrieval temporarily unavailable: {candidate.candidate_id}",
                True,
            )
        values = [
            item
            for page in self._pages()
            for item in page["candidates"]
            if item["candidate_id"] == candidate.candidate_id
            and item["revision"] == candidate.revision
        ]
        if not values:
            raise AdapterFailure(
                FailureClass.PERMANENT_RETRIEVAL,
                f"fixture content mapping absent: {candidate.candidate_id}",
                False,
            )
        value = values[0]
        content = (self._root / value["content_file"]).read_bytes()
        return RetrievalResult(
            content=content,
            media_type=value["media_type"],
            retrieved_at=value["retrieved_at"],
            mechanism=self.mechanism,
            provider_identifiers=value.get("retrieval_provider_identifiers", {}),
            diagnostics={"fixture_file": value["content_file"], "bytes": len(content)},
        )

    def _pages(self) -> list[dict[str, Any]]:
        """Return scenario pages for retrieval mapping."""
        return self._scenario()["pages"]


class FixtureCatalogAdapter(FixtureAdapterBase):
    """Single-page stable-provider-ID catalog fixture."""

    mechanism = "fixture-catalog"

    def discover(
        self, profile: SourceProfile, continuation: str | None
    ) -> DiscoveryPage:
        """Return a single deliberately unsorted catalog page."""
        if continuation is not None:
            raise AdapterFailure(
                FailureClass.MALFORMED_ADAPTER,
                "catalog adapter received unexpected continuation",
                False,
            )
        if "start" in self.transient_discovery_failures:
            raise AdapterFailure(
                FailureClass.TRANSIENT_ADAPTER,
                "catalog discovery temporarily unavailable",
                True,
            )
        if self.malformed_discovery:
            return {"not": "a discovery page"}  # type: ignore[return-value]
        page = self._pages()[0]
        return DiscoveryPage(
            tuple(self._candidate(profile, item) for item in page["candidates"]),
            None,
            {"fixture_behavior": "single_page_stable_provider_ids"},
        )


class FixtureFeedAdapter(FixtureAdapterBase):
    """Paginated URL-like discovery fixture with duplicates and continuation."""

    mechanism = "fixture-feed"

    def discover(
        self, profile: SourceProfile, continuation: str | None
    ) -> DiscoveryPage:
        """Return the page selected by the opaque provider continuation token."""
        token = continuation or "start"
        if token in self.transient_discovery_failures:
            raise AdapterFailure(
                FailureClass.TRANSIENT_ADAPTER,
                f"feed discovery temporarily unavailable at {token}",
                True,
            )
        if self.malformed_discovery:
            return {"candidates": []}  # type: ignore[return-value]
        pages = self._pages()
        index = 0 if continuation is None else int(continuation.removeprefix("page-")) - 1
        if index >= len(pages):
            raise AdapterFailure(
                FailureClass.MALFORMED_ADAPTER,
                f"unknown fixture continuation: {continuation}",
                False,
            )
        page = pages[index]
        next_token = f"page-{index + 2}" if index + 1 < len(pages) else None
        return DiscoveryPage(
            tuple(self._candidate(profile, item) for item in page["candidates"]),
            next_token,
            {
                "fixture_behavior": "paginated_url_like_references",
                "provider_page": index + 1,
            },
        )


def fixture_profiles() -> tuple[SourceProfile, SourceProfile]:
    """Return the two governed sources used by the TASK-003 kernel proof."""
    return (
        SourceProfile(
            "source-fixture-catalog",
            "Fixture stable-ID catalog",
            True,
            "fixture-catalog",
            {
                "scenario": "catalog-states.json",
                "credential_reference": "runtime:future-provider-not-used",
            },
            {"bounded_run_checkpoint": True},
        ),
        SourceProfile(
            "source-fixture-feed",
            "Fixture paginated feed",
            True,
            "fixture-feed",
            {"scenario": "feed-pages.json"},
            {"bounded_run_checkpoint": True},
        ),
    )
