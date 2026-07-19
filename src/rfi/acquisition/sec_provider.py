"""Bounded authoritative SEC provider mechanics without filing-specific policy."""

from __future__ import annotations

import json
import re
import socket
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Callable, Protocol

from rfi.acquisition.contracts import ContractError
from rfi.acquisition.engine import AdapterFailure, FailureClass

SEC_SUBMISSIONS_ORIGIN = "https://data.sec.gov"
SEC_ARCHIVES_ORIGIN = "https://www.sec.gov"
_ACCESSION = re.compile(r"^\d{10}-\d{2}-\d{6}$")
_PRIMARY_DOCUMENT = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
_CONTACT = re.compile(r"^[^\s/]+(?:/[^\s]+)?\s+[^\s@]+@[^\s@]+\.[^\s@]+$")


class SecResponseTooLarge(ValueError):
    """Raised when a provider response crosses its declared byte boundary."""


@dataclass(frozen=True)
class SecHttpResponse:
    """Exact bounded provider response returned by an injectable transport."""

    status: int
    headers: dict[str, str]
    content: bytes
    final_url: str


class SecTransport(Protocol):
    """Transport seam for live HTTPS and deterministic fixture replacement."""

    def request(
        self,
        url: str,
        headers: dict[str, str],
        timeout_seconds: float,
        maximum_bytes: int,
    ) -> SecHttpResponse:
        """Return exact bounded bytes without interpreting SEC filing policy."""


class _BoundedRedirectHandler(urllib.request.HTTPRedirectHandler):
    """Use urllib redirects with an explicit small maximum."""

    max_redirections = 3


class SecUrllibTransport:
    """Standard-library HTTPS transport that discards provider error bodies."""

    def __init__(self) -> None:
        self._opener = urllib.request.build_opener(_BoundedRedirectHandler())

    def request(
        self,
        url: str,
        headers: dict[str, str],
        timeout_seconds: float,
        maximum_bytes: int,
    ) -> SecHttpResponse:
        """Issue one GET and retain only bounded successful response bytes."""
        request = urllib.request.Request(url, headers=headers, method="GET")
        try:
            with self._opener.open(request, timeout=timeout_seconds) as response:
                content = response.read(maximum_bytes + 1)
                if len(content) > maximum_bytes:
                    raise SecResponseTooLarge(
                        "SEC response exceeds the configured maximum bytes"
                    )
                return SecHttpResponse(
                    response.status,
                    {key.lower(): value for key, value in response.headers.items()},
                    content,
                    response.geturl(),
                )
        except urllib.error.HTTPError as error:
            return SecHttpResponse(
                error.code,
                {key.lower(): value for key, value in error.headers.items()},
                b"",
                error.geturl(),
            )


@dataclass(frozen=True)
class SecFilingMetadata:
    """Authoritative provider-native filing metadata before artifact-specific selection."""

    issuer_cik: str
    accession_number: str
    filing_date: str
    report_date: str
    acceptance_datetime: str
    form: str
    primary_document: str
    submissions_url: str


@dataclass(frozen=True)
class SecRetrievedDocument:
    """Exact archive bytes and bounded transport attributes."""

    content: bytes
    media_type: str
    archive_url: str
    http_status: int


class SecProviderClient:
    """Bounded SEC identity, submissions-metadata, and archive-document service."""

    def __init__(
        self,
        user_agent: Callable[[], str],
        transport: SecTransport | None = None,
        timeout_seconds: float = 20.0,
        maximum_attempts: int = 2,
        minimum_request_interval_seconds: float = 0.5,
        maximum_submissions_bytes: int = 5_000_000,
        maximum_artifact_bytes: int = 50_000_000,
        monotonic: Callable[[], float] = time.monotonic,
        sleeper: Callable[[float], None] = time.sleep,
    ) -> None:
        if timeout_seconds <= 0:
            raise ContractError("SEC timeout must be positive")
        if maximum_attempts < 1 or maximum_attempts > 3:
            raise ContractError("SEC attempts must be between one and three")
        if minimum_request_interval_seconds < 0.1:
            raise ContractError("SEC request interval must be at least 0.1 seconds")
        if maximum_submissions_bytes < 1 or maximum_artifact_bytes < 1:
            raise ContractError("SEC response byte limits must be positive")
        self._user_agent = user_agent
        self._transport = transport or SecUrllibTransport()
        self._timeout_seconds = timeout_seconds
        self._maximum_attempts = maximum_attempts
        self._minimum_interval = minimum_request_interval_seconds
        self._maximum_submissions_bytes = maximum_submissions_bytes
        self._maximum_artifact_bytes = maximum_artifact_bytes
        self._monotonic = monotonic
        self._sleeper = sleeper
        self._last_request_at: float | None = None
        self._request_count = 0
        self._retry_count = 0
        self._status_counts: dict[str, int] = {}

    @staticmethod
    def normalize_cik(value: str) -> str:
        """Normalize an explicitly labeled or bare SEC CIK without guessing."""
        normalized = value.strip()
        if normalized.upper().startswith("CIK:"):
            normalized = normalized[4:].strip()
        if not normalized.isdigit() or len(normalized) > 10:
            raise ContractError("SEC issuer identifier must be a one-to-ten digit CIK")
        result = normalized.lstrip("0") or "0"
        if result == "0":
            raise ContractError("SEC issuer identifier must not be zero")
        return result

    def filings(self, cik: str) -> tuple[SecFilingMetadata, ...]:
        """Retrieve and validate the issuer's authoritative recent filing metadata."""
        normalized = self.normalize_cik(cik)
        path = f"/submissions/CIK{normalized.zfill(10)}.json"
        url = f"{SEC_SUBMISSIONS_ORIGIN}{path}"
        response = self._request(url, self._maximum_submissions_bytes)
        self._require_media_type(
            response, {"application/json", "application/octet-stream"}, "submissions"
        )
        if not response.content:
            raise self._malformed("SEC submissions response is empty")
        try:
            value = json.loads(response.content)
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise self._malformed("SEC submissions response contains malformed JSON") from error
        if not isinstance(value, dict):
            raise self._malformed("SEC submissions response is not a JSON object")
        response_cik = str(value.get("cik", ""))
        try:
            authoritative_cik = self.normalize_cik(response_cik)
        except ContractError as error:
            raise self._malformed("SEC submissions response lacks issuer identity") from error
        if authoritative_cik != normalized:
            raise self._malformed(
                "SEC submissions issuer identity differs from the requested CIK"
            )
        filings = value.get("filings")
        recent = filings.get("recent") if isinstance(filings, dict) else None
        if not isinstance(recent, dict):
            raise self._malformed("SEC submissions response lacks filings.recent")
        return self._columnar(authoritative_cik, url, recent)

    def primary_document(
        self, cik: str, accession_number: str, primary_document: str
    ) -> SecRetrievedDocument:
        """Retrieve one exact primary filing document from the authoritative SEC archive."""
        normalized = self.normalize_cik(cik)
        if not _ACCESSION.fullmatch(accession_number):
            raise self._malformed("SEC filing accession number is malformed")
        accession_digits = accession_number.replace("-", "")
        if not _PRIMARY_DOCUMENT.fullmatch(primary_document) or ".." in primary_document:
            raise self._malformed("SEC primary-document identity is unsafe or malformed")
        path = (
            f"/Archives/edgar/data/{normalized}/{accession_digits}/"
            f"{primary_document}"
        )
        url = f"{SEC_ARCHIVES_ORIGIN}{path}"
        response = self._request(url, self._maximum_artifact_bytes)
        media_type = self._media_type(response)
        allowed = {
            "text/html",
            "application/xhtml+xml",
            "text/plain",
            "application/octet-stream",
        }
        if media_type not in allowed:
            raise AdapterFailure(
                FailureClass.PERMANENT_RETRIEVAL,
                "SEC primary filing has an unexpected content type",
                False,
                "unsupported_artifact_representation",
            )
        if not response.content:
            raise AdapterFailure(
                FailureClass.PERMANENT_RETRIEVAL,
                "SEC primary filing response is empty",
                False,
                "empty_artifact_content",
            )
        content_length = response.headers.get("content-length")
        if content_length:
            try:
                expected = int(content_length)
            except ValueError as error:
                raise self._malformed("SEC response Content-Length is malformed") from error
            if expected != len(response.content):
                raise AdapterFailure(
                    FailureClass.PERMANENT_RETRIEVAL,
                    "SEC primary filing response is truncated",
                    False,
                    "truncated_artifact_content",
                )
        if media_type in {"text/html", "application/xhtml+xml"}:
            prefix = response.content.lstrip()[:256].lower()
            if b"<html" not in prefix and b"<!doctype html" not in prefix:
                raise AdapterFailure(
                    FailureClass.PERMANENT_RETRIEVAL,
                    "SEC primary filing HTML signature is invalid",
                    False,
                    "invalid_artifact_content",
                )
        normalized_media_type = (
            "text/html" if media_type == "application/octet-stream" else media_type
        )
        return SecRetrievedDocument(
            response.content,
            normalized_media_type,
            url,
            response.status,
        )

    def usage(self) -> dict[str, object]:
        """Return sanitized network evidence without request identity or response bodies."""
        return {
            "provider": "SEC EDGAR",
            "requests": self._request_count,
            "retries": self._retry_count,
            "status_counts": dict(sorted(self._status_counts.items())),
            "timeout_seconds": self._timeout_seconds,
            "maximum_attempts": self._maximum_attempts,
            "minimum_request_interval_seconds": self._minimum_interval,
            "maximum_submissions_bytes": self._maximum_submissions_bytes,
            "maximum_artifact_bytes": self._maximum_artifact_bytes,
            "redirect_limit": _BoundedRedirectHandler.max_redirections,
            "runtime_identity_emitted": False,
        }

    def _request(self, url: str, maximum_bytes: int) -> SecHttpResponse:
        """Execute one bounded provider operation with stable failure semantics."""
        parsed = urllib.parse.urlsplit(url)
        if parsed.scheme != "https" or parsed.netloc not in {
            "data.sec.gov",
            "www.sec.gov",
        }:
            raise ContractError("SEC provider URL is outside the authoritative endpoint scope")
        try:
            user_agent = self._user_agent()
        except (ContractError, OSError) as error:
            raise AdapterFailure(
                FailureClass.PERMANENT_RETRIEVAL,
                "required SEC runtime request identity is unavailable or invalid",
                False,
                "missing_runtime_identity",
            ) from error
        if len(user_agent) > 200 or not _CONTACT.fullmatch(user_agent):
            raise AdapterFailure(
                FailureClass.PERMANENT_RETRIEVAL,
                "required SEC runtime request identity is unavailable or invalid",
                False,
                "invalid_runtime_identity",
            )
        for attempt in range(self._maximum_attempts):
            self._pace()
            self._request_count += 1
            try:
                response = self._transport.request(
                    url,
                    {
                        "User-Agent": user_agent,
                        "Accept": "application/json, text/html, text/plain",
                        "Accept-Encoding": "identity",
                    },
                    self._timeout_seconds,
                    maximum_bytes,
                )
            except SecResponseTooLarge as error:
                raise AdapterFailure(
                    FailureClass.PERMANENT_RETRIEVAL,
                    "SEC response exceeded the configured size boundary",
                    False,
                    "artifact_size_limit_exceeded",
                ) from error
            except (TimeoutError, socket.timeout) as error:
                if attempt + 1 < self._maximum_attempts:
                    self._retry_count += 1
                    continue
                raise AdapterFailure(
                    FailureClass.TRANSIENT_ADAPTER,
                    "SEC request timed out after bounded attempts",
                    True,
                    "network_timeout",
                ) from error
            except (urllib.error.URLError, OSError, ValueError) as error:
                if attempt + 1 < self._maximum_attempts:
                    self._retry_count += 1
                    continue
                raise AdapterFailure(
                    FailureClass.TRANSIENT_ADAPTER,
                    "SEC transport failed after bounded attempts",
                    True,
                    "temporary_service_failure",
                ) from error
            self._status_counts[str(response.status)] = (
                self._status_counts.get(str(response.status), 0) + 1
            )
            if response.status in {429, 500, 502, 503, 504}:
                if attempt + 1 < self._maximum_attempts:
                    self._retry_count += 1
                    continue
                code = "rate_limited" if response.status == 429 else "temporary_service_failure"
                raise AdapterFailure(
                    FailureClass.TRANSIENT_ADAPTER,
                    "SEC rate limit rejected the bounded request"
                    if response.status == 429
                    else "SEC service remained unavailable after bounded attempts",
                    True,
                    code,
                )
            if response.status == 404 and parsed.netloc == "data.sec.gov":
                raise AdapterFailure(
                    FailureClass.PERMANENT_RETRIEVAL,
                    "SEC issuer submissions record was not found",
                    False,
                    "issuer_not_found",
                )
            if response.status < 200 or response.status >= 300:
                raise AdapterFailure(
                    FailureClass.PERMANENT_RETRIEVAL,
                    f"SEC request failed permanently with HTTP {response.status}",
                    False,
                    "permanent_request_failure",
                )
            final = urllib.parse.urlsplit(response.final_url)
            if final.scheme != "https" or final.netloc != parsed.netloc:
                raise AdapterFailure(
                    FailureClass.PERMANENT_RETRIEVAL,
                    "SEC response redirected outside its authoritative origin",
                    False,
                    "unsafe_redirect",
                )
            return response
        raise AssertionError("unreachable SEC request state")

    def _pace(self) -> None:
        now = self._monotonic()
        if self._last_request_at is not None:
            remaining = self._minimum_interval - (now - self._last_request_at)
            if remaining > 0:
                self._sleeper(remaining)
                now = self._monotonic()
        self._last_request_at = now

    @classmethod
    def _columnar(
        cls, cik: str, submissions_url: str, value: dict[str, object]
    ) -> tuple[SecFilingMetadata, ...]:
        required = (
            "accessionNumber",
            "filingDate",
            "reportDate",
            "acceptanceDateTime",
            "form",
            "primaryDocument",
        )
        if any(not isinstance(value.get(name), list) for name in required):
            raise cls._malformed("SEC submissions metadata lacks required arrays")
        arrays = {name: value[name] for name in required}
        lengths = {len(items) for items in arrays.values()}  # type: ignore[arg-type]
        if len(lengths) != 1:
            raise cls._malformed("SEC submissions metadata arrays have inconsistent lengths")
        records = []
        for index in range(lengths.pop()):
            fields = {name: arrays[name][index] for name in required}  # type: ignore[index]
            if any(not isinstance(item, str) for item in fields.values()):
                raise cls._malformed("SEC filing metadata contains a missing identity field")
            identity_fields = (
                fields["accessionNumber"],
                fields["filingDate"],
                fields["acceptanceDateTime"],
                fields["form"],
            )
            if any(not item for item in identity_fields):
                raise cls._malformed("SEC filing metadata contains a missing identity field")
            accession = str(fields["accessionNumber"])
            if not _ACCESSION.fullmatch(accession):
                raise cls._malformed("SEC filing metadata contains a malformed accession")
            records.append(
                SecFilingMetadata(
                    cik,
                    accession,
                    str(fields["filingDate"]),
                    str(fields["reportDate"]),
                    str(fields["acceptanceDateTime"]),
                    str(fields["form"]),
                    str(fields["primaryDocument"]),
                    submissions_url,
                )
            )
        return tuple(records)

    @staticmethod
    def _media_type(response: SecHttpResponse) -> str:
        return response.headers.get("content-type", "").split(";", 1)[0].strip().lower()

    @classmethod
    def _require_media_type(
        cls, response: SecHttpResponse, allowed: set[str], label: str
    ) -> None:
        if cls._media_type(response) not in allowed:
            raise cls._malformed(f"SEC {label} response has an unexpected content type")

    @staticmethod
    def _malformed(message: str) -> AdapterFailure:
        return AdapterFailure(
            FailureClass.MALFORMED_ADAPTER,
            message,
            False,
            "malformed_provider_response",
        )
