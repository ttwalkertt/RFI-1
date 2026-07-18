"""Direct-URL adapter that retrieves exact bytes through the acquisition engine."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from rfi.acquisition.contracts import DiscoveryProvenance, RetrievalResult, SourceProfile
from rfi.acquisition.engine import (
    AdapterCandidate,
    AdapterFailure,
    DiscoveryPage,
    FailureClass,
)


class DirectUrlAdapter:
    """Retrieve one configured HTTP(S) artifact without owning repository state."""

    mechanism = "direct_url"

    def __init__(
        self,
        clock: Callable[[], str],
        timeout_seconds: float = 30.0,
        opener: Callable[..., object] = urlopen,
    ) -> None:
        self._clock = clock
        self._timeout_seconds = timeout_seconds
        self._opener = opener

    def discover(self, profile: SourceProfile, continuation: str | None) -> DiscoveryPage:
        """Expose the configured URL as one deterministic engine candidate."""
        if continuation is not None:
            raise AdapterFailure(
                FailureClass.MALFORMED_ADAPTER,
                "direct URL retrieval does not support continuation",
                False,
            )
        url = profile.configuration.get("url")
        if not isinstance(url, str) or not url:
            raise AdapterFailure(
                FailureClass.PERMANENT_RETRIEVAL,
                "direct URL retrieval requires a configured URL",
                False,
            )
        digest = self._digest(profile)
        document_id = profile.policy.get("document_id")
        if not isinstance(document_id, str) or not document_id:
            document_id = f"document-{digest[:24]}"
        candidate = AdapterCandidate(
            candidate_id=f"candidate-{digest[:24]}",
            document_id=document_id,
            position=1,
            revision=f"revision-{digest[24:48]}",
            provenance=DiscoveryProvenance(
                discovered_at=self._clock(),
                discovery_method=self.mechanism,
                locations=(url,),
                metadata={"configured_source": True},
            ),
        )
        return DiscoveryPage((candidate,), None, {"configured_candidates": 1})

    def retrieve(
        self, profile: SourceProfile, candidate: AdapterCandidate
    ) -> RetrievalResult:
        """Retrieve exact response bytes and translate transport failures visibly."""
        url = profile.configuration.get("url")
        if not isinstance(url, str) or not url:
            raise AdapterFailure(
                FailureClass.PERMANENT_RETRIEVAL,
                "direct URL retrieval requires a configured URL",
                False,
            )
        try:
            response = self._opener(
                Request(url, headers={"User-Agent": "RFI-1 Pull Workflow"}),
                timeout=self._timeout_seconds,
            )
            with response:  # type: ignore[attr-defined]
                content = response.read()  # type: ignore[attr-defined]
                media_type = response.headers.get_content_type()  # type: ignore[attr-defined]
                status = getattr(response, "status", 200)
                final_url = response.geturl()  # type: ignore[attr-defined]
        except HTTPError as error:
            raise AdapterFailure(
                FailureClass.PERMANENT_RETRIEVAL,
                f"direct URL returned HTTP {error.code}",
                False,
            ) from error
        except (URLError, TimeoutError, OSError) as error:
            raise AdapterFailure(
                FailureClass.TRANSIENT_ADAPTER,
                "direct URL retrieval failed: "
                f"{error.reason if isinstance(error, URLError) else error}",
                True,
            ) from error
        if not isinstance(content, bytes):
            raise AdapterFailure(
                FailureClass.MALFORMED_ADAPTER,
                "direct URL transport did not return exact bytes",
                False,
            )
        expected = profile.configuration.get("expected_media_type")
        diagnostics = {
            "http_status": status,
            "final_url": final_url,
            "expected_media_type": expected if isinstance(expected, str) else "",
        }
        return RetrievalResult(
            content=content,
            media_type=media_type or "application/octet-stream",
            retrieved_at=self._clock(),
            mechanism=self.mechanism,
            diagnostics=diagnostics,
        )

    @staticmethod
    def _digest(profile: SourceProfile) -> str:
        value = json.dumps(
            {
                "source_id": profile.source_id,
                "configuration": profile.configuration,
                "policy": profile.policy,
            },
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
        return hashlib.sha256(value).hexdigest()
