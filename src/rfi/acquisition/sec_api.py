"""Bounded SEC-API.io filing discovery and exact-submission retrieval."""

from __future__ import annotations

import json
import os
import socket
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Callable, Mapping, Protocol
from urllib.parse import urlparse

from rfi.acquisition.contracts import (
    ContractError,
    DiscoveryProvenance,
    JsonValue,
    RetrievalResult,
    SourceProfile,
)
from rfi.acquisition.engine import AdapterCandidate, AdapterFailure, DiscoveryPage, FailureClass

QUERY_ENDPOINT = "https://api.sec-api.io"
ARCHIVE_ORIGIN = "https://archive.sec-api.io"
ENVIRONMENT_VARIABLE = "SEC_API_IO_API_KEY"
MECHANISM = "sec-api-io"
FORM_ORDER = ("10-K", "10-Q", "8-K")


@dataclass(frozen=True)
class HttpResponse:
    """Small transport result with exact response bytes."""

    status: int
    headers: dict[str, str]
    content: bytes


class HttpTransport(Protocol):
    """Injectable network seam used by the production and fixture transports."""

    def request(
        self,
        method: str,
        url: str,
        headers: dict[str, str],
        body: bytes | None,
        timeout_seconds: float,
        maximum_bytes: int,
    ) -> HttpResponse:
        """Return one bounded exact response or raise a transport exception."""


class UrllibTransport:
    """Standard-library HTTPS transport with bounded response reads."""

    def request(
        self,
        method: str,
        url: str,
        headers: dict[str, str],
        body: bytes | None,
        timeout_seconds: float,
        maximum_bytes: int,
    ) -> HttpResponse:
        request = urllib.request.Request(url, data=body, headers=headers, method=method)
        try:
            with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
                content = response.read(maximum_bytes + 1)
                if len(content) > maximum_bytes:
                    raise ValueError("response exceeds configured maximum bytes")
                return HttpResponse(
                    response.status,
                    {key.lower(): value for key, value in response.headers.items()},
                    content,
                )
        except urllib.error.HTTPError as error:
            # Never read or retain provider error bodies: they may echo request material.
            return HttpResponse(
                error.code,
                {key.lower(): value for key, value in error.headers.items()},
                b"",
            )


def credential_from_environment(
    reference: str, environment: Mapping[str, str] | None = None
) -> str:
    """Resolve only the explicitly governed environment reference without revealing it."""
    expected = f"env:{ENVIRONMENT_VARIABLE}"
    if reference != expected:
        raise ContractError(f"credential_reference must be {expected}")
    source = os.environ if environment is None else environment
    value = source.get(ENVIRONMENT_VARIABLE, "")
    if not value:
        raise ContractError(f"required runtime credential is absent: {ENVIRONMENT_VARIABLE}")
    return value


def load_live_profiles(root: Path) -> tuple[SourceProfile, ...]:
    """Load the two checked-in deterministic governed source definitions."""
    profiles = []
    for path in sorted((root / "config/sources").glob("sec-api-*.json")):
        value = json.loads(path.read_text(encoding="utf-8"))
        profile = SourceProfile(**value)
        validate_live_profile(profile)
        profiles.append(profile)
    if {profile.source_id for profile in profiles} != {
        "source-sec-stx",
        "source-sec-wdc",
    }:
        raise ContractError("live source registry must contain exactly governed STX and WDC")
    return tuple(profiles)


def validate_live_profile(profile: SourceProfile) -> None:
    """Fail closed on any scope that could silently widen the live corpus."""
    if profile.mechanism != MECHANISM:
        raise ContractError(f"live profile mechanism must be {MECHANISM}")
    configuration = profile.configuration
    required = {
        "ticker",
        "cik",
        "filed_from",
        "filed_through",
        "form_limits",
        "page_size",
        "credential_reference",
    }
    if set(configuration) != required:
        raise ContractError("live profile configuration fields are not the governed set")
    ticker = configuration["ticker"]
    cik = configuration["cik"]
    if not isinstance(ticker, str) or ticker not in {"STX", "WDC"}:
        raise ContractError("live ticker must be governed STX or WDC")
    expected_cik = {"STX": "1137789", "WDC": "106040"}[ticker]
    if cik != expected_cik:
        raise ContractError(f"governed CIK mismatch for {ticker}")
    for field in ("filed_from", "filed_through"):
        value = configuration[field]
        if not isinstance(value, str):
            raise ContractError(f"{field} must be an ISO date")
        try:
            datetime.strptime(value, "%Y-%m-%d")
        except ValueError as error:
            raise ContractError(f"{field} must be an ISO date") from error
    if configuration["filed_from"] > configuration["filed_through"]:
        raise ContractError("filed_from must not follow filed_through")
    limits = configuration["form_limits"]
    if not isinstance(limits, dict) or tuple(limits) != FORM_ORDER:
        raise ContractError("form_limits must contain ordered 10-K, 10-Q, and 8-K bounds")
    if any(not isinstance(limits[form], int) or limits[form] < 1 for form in FORM_ORDER):
        raise ContractError("every governed form limit must be a positive integer")
    page_size = configuration["page_size"]
    if not isinstance(page_size, int) or page_size < 1 or page_size > 10:
        raise ContractError("page_size must be between 1 and 10")
    if configuration["credential_reference"] != f"env:{ENVIRONMENT_VARIABLE}":
        raise ContractError("live credential must use the governed environment reference")
    policy = profile.policy
    if set(policy) != {
        "connect_read_timeout_seconds",
        "maximum_artifact_bytes",
        "maximum_attempts_per_request",
        "maximum_live_requests",
    }:
        raise ContractError("live profile policy fields are not the governed set")
    maximum_requests = policy["maximum_live_requests"]
    if maximum_requests != 80:
        raise ContractError(
            "maximum_live_requests must bound two issuers, two runs, and retry attempts at 80"
        )
    if policy["maximum_attempts_per_request"] not in {1, 2, 3}:
        raise ContractError("maximum_attempts_per_request must be between 1 and 3")
    if not isinstance(policy["maximum_artifact_bytes"], int) or policy[
        "maximum_artifact_bytes"
    ] < 1024:
        raise ContractError("maximum_artifact_bytes is too small")
    if not isinstance(policy["connect_read_timeout_seconds"], int) or policy[
        "connect_read_timeout_seconds"
    ] < 1:
        raise ContractError("connect_read_timeout_seconds must be positive")


class SecApiAdapter:
    """Commercial provider adapter that owns HTTP, mapping, and provider continuations."""

    mechanism = MECHANISM

    def __init__(
        self,
        api_key: str,
        transport: HttpTransport | None = None,
        clock: Callable[[], str] | None = None,
        sleeper: Callable[[float], None] = time.sleep,
    ) -> None:
        if not api_key:
            raise ContractError("SEC-API.io runtime credential must not be blank")
        self._api_key = api_key
        self._transport = transport or UrllibTransport()
        self._clock = clock or (lambda: datetime.now().astimezone().isoformat())
        self._sleeper = sleeper
        self._request_count = 0
        self._status_counts: dict[str, int] = {}
        self._quota_headers: dict[str, str] = {}

    def usage(self) -> dict[str, JsonValue]:
        """Return sanitized task-local request and quota evidence."""
        return {
            "provider": "SEC-API.io",
            "requests": self._request_count,
            "status_counts": dict(sorted(self._status_counts.items())),
            "quota_headers": dict(sorted(self._quota_headers.items())),
        }

    def discover(self, profile: SourceProfile, continuation: str | None) -> DiscoveryPage:
        validate_live_profile(profile)
        form_index, offset = self._decode_continuation(continuation)
        form = FORM_ORDER[form_index]
        configuration = profile.configuration
        limits = configuration["form_limits"]
        assert isinstance(limits, dict)
        limit = int(limits[form])
        page_size = min(int(configuration["page_size"]), limit - offset)
        payload = {
            "query": (
                f'cik:{configuration["cik"]} AND ticker:{configuration["ticker"]} '
                f'AND formType:"{form}" AND filedAt:[{configuration["filed_from"]} '
                f'TO {configuration["filed_through"]}]'
            ),
            "from": str(offset),
            "size": str(page_size),
            "sort": [{"filedAt": {"order": "desc"}}, {"accessionNo": {"order": "desc"}}],
        }
        response = self._request(profile, "POST", QUERY_ENDPOINT, json.dumps(payload).encode())
        self._require_json(response, "discovery")
        try:
            value = json.loads(response.content)
        except json.JSONDecodeError as error:
            raise AdapterFailure(
                FailureClass.MALFORMED_ADAPTER,
                "SEC-API.io discovery returned malformed JSON",
                False,
            ) from error
        if not isinstance(value, dict) or not isinstance(value.get("filings"), list):
            raise AdapterFailure(
                FailureClass.MALFORMED_ADAPTER,
                "SEC-API.io discovery response lacks a filings array",
                False,
            )
        filings = value["filings"]
        if len(filings) > page_size:
            raise AdapterFailure(
                FailureClass.MALFORMED_ADAPTER,
                "SEC-API.io discovery exceeded the requested page bound",
                False,
            )
        candidates = tuple(
            self._map_candidate(profile, filing, form_index, offset + index)
            for index, filing in enumerate(filings)
        )
        consumed = offset + len(filings)
        if consumed < limit and len(filings) == page_size:
            next_token = f"{form_index}:{consumed}"
        elif form_index + 1 < len(FORM_ORDER):
            next_token = f"{form_index + 1}:0"
        else:
            next_token = None
        return DiscoveryPage(
            candidates,
            next_token,
            {
                "provider": "SEC-API.io",
                "form": form,
                "offset": offset,
                "requested_size": page_size,
                "returned": len(filings),
                "request_count": self._request_count,
            },
        )

    def retrieve(self, profile: SourceProfile, candidate: AdapterCandidate) -> RetrievalResult:
        validate_live_profile(profile)
        link = candidate.provenance.metadata.get("link_to_txt")
        if not isinstance(link, str):
            raise AdapterFailure(
                FailureClass.MALFORMED_ADAPTER,
                "SEC filing candidate lacks the complete-submission reference",
                False,
            )
        parsed = urlparse(link)
        if parsed.scheme != "https" or parsed.hostname not in {"www.sec.gov", "sec.gov"}:
            raise AdapterFailure(
                FailureClass.MALFORMED_ADAPTER,
                "SEC filing complete-submission reference is not an approved SEC HTTPS URL",
                False,
            )
        if not parsed.path.startswith("/Archives/edgar/data/") or not parsed.path.endswith(".txt"):
            raise AdapterFailure(
                FailureClass.MALFORMED_ADAPTER,
                "SEC filing complete-submission reference has an unexpected path",
                False,
            )
        archive_url = f"{ARCHIVE_ORIGIN}{parsed.path}"
        response = self._request(profile, "GET", archive_url, None)
        media_type = response.headers.get("content-type", "").split(";", 1)[0].lower()
        if media_type not in {"text/plain", "text/html", "application/octet-stream"}:
            raise AdapterFailure(
                FailureClass.PERMANENT_RETRIEVAL,
                f"SEC-API.io filing response has unexpected content type: {media_type or 'absent'}",
                False,
            )
        if not response.content:
            raise AdapterFailure(
                FailureClass.PERMANENT_RETRIEVAL,
                "SEC-API.io filing response is empty",
                False,
            )
        if not response.content.startswith(b"<SEC-DOCUMENT>"):
            raise AdapterFailure(
                FailureClass.PERMANENT_RETRIEVAL,
                "SEC-API.io filing response is not a complete SEC submission",
                False,
            )
        return RetrievalResult(
            response.content,
            "text/plain" if media_type == "application/octet-stream" else media_type,
            self._clock(),
            self.mechanism,
            {
                "sec_accession": str(candidate.provenance.metadata["accession_no"]),
                "provider_surface": "filing-download-api",
            },
            {
                "bytes": len(response.content),
                "provider": "SEC-API.io",
                "retrieval_reference": archive_url,
                "request_count": self._request_count,
                "quota_headers": dict(sorted(self._quota_headers.items())),
            },
        )

    def _request(
        self, profile: SourceProfile, method: str, url: str, body: bytes | None
    ) -> HttpResponse:
        policy = profile.policy
        attempts = int(policy["maximum_attempts_per_request"])
        timeout = float(policy["connect_read_timeout_seconds"])
        maximum = (
            2_000_000 if method == "POST" else int(policy["maximum_artifact_bytes"])
        )
        last_error: BaseException | None = None
        for attempt in range(attempts):
            if self._request_count >= int(policy["maximum_live_requests"]):
                raise AdapterFailure(
                    FailureClass.POLICY_REJECTION,
                    "governed maximum live request count reached",
                    False,
                )
            self._request_count += 1
            try:
                response = self._transport.request(
                    method,
                    url,
                    {
                        "Authorization": self._api_key,
                        "Accept": "application/json" if method == "POST" else "text/plain",
                        "Content-Type": "application/json",
                        "User-Agent": "RFI-1 TASK-004 bounded acquisition",
                    },
                    body,
                    timeout,
                    maximum,
                )
            except (
                TimeoutError,
                socket.timeout,
                urllib.error.URLError,
                OSError,
                ValueError,
            ) as error:
                last_error = error
                if attempt + 1 < attempts:
                    self._sleeper(min(2**attempt, 2))
                    continue
                raise AdapterFailure(
                    FailureClass.TRANSIENT_ADAPTER,
                    f"SEC-API.io transport failed after {attempts} bounded attempt(s)",
                    True,
                ) from error
            self._record_response(response)
            if response.status in {429, 500, 502, 503, 504} and attempt + 1 < attempts:
                self._sleeper(min(2**attempt, 2))
                continue
            if response.status in {401, 403}:
                raise AdapterFailure(
                    FailureClass.PERMANENT_RETRIEVAL,
                    "SEC-API.io authentication was rejected",
                    False,
                )
            if response.status == 429:
                raise AdapterFailure(
                    FailureClass.TRANSIENT_ADAPTER,
                    "SEC-API.io quota or rate limit rejected the bounded request",
                    True,
                )
            if response.status >= 500:
                raise AdapterFailure(
                    FailureClass.TRANSIENT_ADAPTER,
                    f"SEC-API.io transient server response: HTTP {response.status}",
                    True,
                )
            if response.status < 200 or response.status >= 300:
                raise AdapterFailure(
                    FailureClass.PERMANENT_RETRIEVAL,
                    f"SEC-API.io permanent response: HTTP {response.status}",
                    False,
                )
            return response
        raise AssertionError(f"unreachable transport state: {last_error}")

    def _record_response(self, response: HttpResponse) -> None:
        key = str(response.status)
        self._status_counts[key] = self._status_counts.get(key, 0) + 1
        for name, value in response.headers.items():
            lowered = name.lower()
            if ("rate" in lowered or "quota" in lowered) and len(value) <= 64:
                self._quota_headers[lowered] = value

    @staticmethod
    def _require_json(response: HttpResponse, operation: str) -> None:
        media_type = response.headers.get("content-type", "").split(";", 1)[0].lower()
        if media_type != "application/json":
            raise AdapterFailure(
                FailureClass.MALFORMED_ADAPTER,
                f"SEC-API.io {operation} response has unexpected content type",
                False,
            )

    @staticmethod
    def _decode_continuation(continuation: str | None) -> tuple[int, int]:
        if continuation is None:
            return 0, 0
        try:
            form_index_text, offset_text = continuation.split(":", 1)
            form_index, offset = int(form_index_text), int(offset_text)
        except (ValueError, AttributeError) as error:
            raise AdapterFailure(
                FailureClass.MALFORMED_ADAPTER,
                "SEC-API.io continuation token is malformed",
                False,
            ) from error
        if form_index not in range(len(FORM_ORDER)) or offset < 0:
            raise AdapterFailure(
                FailureClass.MALFORMED_ADAPTER,
                "SEC-API.io continuation token is outside governed scope",
                False,
            )
        return form_index, offset

    @staticmethod
    def _map_candidate(
        profile: SourceProfile, filing: object, form_index: int, ordinal: int
    ) -> AdapterCandidate:
        if not isinstance(filing, dict):
            raise AdapterFailure(
                FailureClass.MALFORMED_ADAPTER, "SEC-API.io filing is not an object", False
            )
        required = ("accessionNo", "cik", "formType", "filedAt", "linkToTxt")
        if any(not isinstance(filing.get(field), str) or not filing[field] for field in required):
            raise AdapterFailure(
                FailureClass.MALFORMED_ADAPTER,
                "SEC-API.io filing lacks required SEC identity fields",
                False,
            )
        accession = str(filing["accessionNo"])
        accession_digits = accession.replace("-", "")
        if len(accession_digits) != 18 or not accession_digits.isdigit():
            raise AdapterFailure(
                FailureClass.MALFORMED_ADAPTER, "SEC accession number is malformed", False
            )
        cik = str(filing["cik"]).lstrip("0") or "0"
        expected_cik = str(profile.configuration["cik"])
        form = str(filing["formType"])
        expected_form = FORM_ORDER[form_index]
        if cik != expected_cik or form != expected_form:
            raise AdapterFailure(
                FailureClass.MALFORMED_ADAPTER,
                "SEC-API.io filing falls outside governed issuer or form scope",
                False,
            )
        ticker = str(profile.configuration["ticker"])
        provider_identifiers = {"sec_accession": accession}
        if isinstance(filing.get("id"), str) and filing["id"]:
            provider_identifiers["sec_api_filing_id"] = str(filing["id"])
        locations = tuple(
            str(filing[name])
            for name in ("linkToTxt", "linkToFilingDetails")
            if isinstance(filing.get(name), str) and filing[name]
        )
        return AdapterCandidate(
            candidate_id=f"candidate-sec-{cik}-{accession_digits}-submission",
            document_id=f"document-sec-{cik}-{accession_digits}",
            position=(form_index + 1) * 1_000_000 + ordinal + 1,
            revision=f"filing-{accession_digits}",
            provenance=DiscoveryProvenance(
                discovered_at=str(filing["filedAt"]),
                discovery_method=MECHANISM,
                provider_identifiers=provider_identifiers,
                locations=locations,
                metadata={
                    "provider": "SEC-API.io",
                    "provider_surface": "filing-query-api",
                    "issuer_cik": cik,
                    "issuer_ticker": ticker,
                    "accession_no": accession,
                    "form_type": form,
                    "amendment": form.endswith("/A"),
                    "filed_at": str(filing["filedAt"]),
                    "period_of_report": filing.get("periodOfReport"),
                    "company_name": filing.get("companyName"),
                    "link_to_txt": str(filing["linkToTxt"]),
                },
            ),
        )
