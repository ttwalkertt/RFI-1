"""Native SEC EDGAR discovery and exact complete-submission retrieval."""

from __future__ import annotations

import json
import os
import re
import socket
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Callable, Protocol

from rfi.acquisition.contracts import (
    ContractError,
    DiscoveryProvenance,
    JsonValue,
    RetrievalResult,
    SourceProfile,
)
from rfi.acquisition.engine import AdapterCandidate, AdapterFailure, DiscoveryPage, FailureClass

MECHANISM = "sec-edgar"
USER_AGENT_VARIABLE = "RFI_SEC_USER_AGENT"
FORM_ORDER = ("10-K", "10-Q", "8-K")
SUBMISSIONS_ORIGIN = "https://data.sec.gov"
ARCHIVES_ORIGIN = "https://www.sec.gov"
_CONTACT = re.compile(r"^[^\s/]+(?:/[^\s]+)?\s+[^\s@]+@[^\s@]+\.[^\s@]+$")


@dataclass(frozen=True)
class EdgarHttpResponse:
    """Bounded HTTP response returned by an injectable EDGAR transport."""

    status: int
    headers: dict[str, str]
    content: bytes


class EdgarTransport(Protocol):
    """Network seam used by live HTTPS and deterministic offline fixtures."""

    def request(
        self,
        url: str,
        headers: dict[str, str],
        timeout_seconds: float,
        maximum_bytes: int,
    ) -> EdgarHttpResponse:
        """Return exact bounded bytes without interpreting EDGAR content."""


class EdgarUrllibTransport:
    """Standard-library HTTPS transport that never retains error bodies."""

    def request(
        self,
        url: str,
        headers: dict[str, str],
        timeout_seconds: float,
        maximum_bytes: int,
    ) -> EdgarHttpResponse:
        request = urllib.request.Request(url, headers=headers, method="GET")
        try:
            with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
                content = response.read(maximum_bytes + 1)
                if len(content) > maximum_bytes:
                    raise ValueError("response exceeds configured maximum bytes")
                return EdgarHttpResponse(
                    response.status,
                    {key.lower(): value for key, value in response.headers.items()},
                    content,
                )
        except urllib.error.HTTPError as error:
            return EdgarHttpResponse(
                error.code,
                {key.lower(): value for key, value in error.headers.items()},
                b"",
            )


def user_agent_from_environment(reference: str) -> str:
    """Resolve and validate only the governed runtime EDGAR identity reference."""
    expected = f"env:{USER_AGENT_VARIABLE}"
    if reference != expected:
        raise ContractError(f"user_agent_reference must be {expected}")
    value = os.environ.get(USER_AGENT_VARIABLE, "")
    if not value:
        raise ContractError(f"required EDGAR runtime identity is absent: {USER_AGENT_VARIABLE}")
    if len(value) > 200 or not _CONTACT.fullmatch(value):
        raise ContractError(
            "EDGAR runtime identity must contain an application identity and contact email"
        )
    return value


def load_edgar_profiles(root: Path) -> tuple[SourceProfile, ...]:
    """Load exactly the governed native STX and WDC EDGAR profiles."""
    profiles = []
    for path in sorted((root / "config/sources").glob("edgar-*.json")):
        profile = SourceProfile(**json.loads(path.read_text(encoding="utf-8")))
        validate_edgar_profile(profile)
        profiles.append(profile)
    if {profile.source_id for profile in profiles} != {
        "source-edgar-stx",
        "source-edgar-wdc",
    }:
        raise ContractError("native EDGAR source registry must contain exactly STX and WDC")
    return tuple(profiles)


def validate_edgar_profile(profile: SourceProfile) -> None:
    """Reject a native source scope that could widen or violate fair access."""
    if profile.mechanism != MECHANISM:
        raise ContractError(f"native EDGAR mechanism must be {MECHANISM}")
    configuration = profile.configuration
    required = {
        "ticker",
        "cik",
        "filed_from",
        "filed_through",
        "form_limits",
        "page_size",
        "user_agent_reference",
    }
    if set(configuration) != required:
        raise ContractError("native EDGAR configuration fields are not the governed set")
    ticker = configuration["ticker"]
    cik = configuration["cik"]
    if not isinstance(ticker, str) or ticker not in {"STX", "WDC"}:
        raise ContractError("native EDGAR ticker must be STX or WDC")
    if cik != {"STX": "1137789", "WDC": "106040"}[ticker]:
        raise ContractError(f"governed EDGAR CIK mismatch for {ticker}")
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
        raise ContractError("native EDGAR form limits must be ordered 10-K, 10-Q, and 8-K")
    if any(not isinstance(limits[form], int) or limits[form] < 1 for form in FORM_ORDER):
        raise ContractError("every native EDGAR form limit must be positive")
    if configuration["page_size"] != 1:
        raise ContractError("native EDGAR page size must be one")
    if configuration["user_agent_reference"] != f"env:{USER_AGENT_VARIABLE}":
        raise ContractError("native EDGAR identity must use the governed runtime reference")
    policy = profile.policy
    if set(policy) != {
        "minimum_request_interval_seconds",
        "timeout_seconds",
        "maximum_artifact_bytes",
        "maximum_attempts_per_request",
        "maximum_live_requests",
    }:
        raise ContractError("native EDGAR policy fields are not the governed set")
    interval = policy["minimum_request_interval_seconds"]
    if not isinstance(interval, float) or interval < 0.5:
        raise ContractError("native EDGAR pacing must be at most two requests per second")
    if policy["timeout_seconds"] != 20:
        raise ContractError("native EDGAR timeout must be 20 seconds")
    if policy["maximum_artifact_bytes"] != 50_000_000:
        raise ContractError("native EDGAR artifact limit must be 50 MB")
    if policy["maximum_attempts_per_request"] != 2:
        raise ContractError("native EDGAR requests must allow exactly two bounded attempts")
    if policy["maximum_live_requests"] != 80:
        raise ContractError("native EDGAR complete acceptance request ceiling must be 80")


class EdgarAdapter:
    """Official submissions-data discovery and archive retrieval adapter."""

    mechanism = MECHANISM

    def __init__(
        self,
        user_agent: str,
        transport: EdgarTransport | None = None,
        clock: Callable[[], str] | None = None,
        monotonic: Callable[[], float] = time.monotonic,
        sleeper: Callable[[float], None] = time.sleep,
    ) -> None:
        if len(user_agent) > 200 or not _CONTACT.fullmatch(user_agent):
            raise ContractError(
                "EDGAR runtime identity must contain an application identity and contact email"
            )
        self._user_agent = user_agent
        self._transport = transport or EdgarUrllibTransport()
        self._clock = clock or (lambda: datetime.now().astimezone().isoformat())
        self._monotonic = monotonic
        self._sleeper = sleeper
        self._last_request_at: float | None = None
        self._request_count = 0
        self._status_counts: dict[str, int] = {}
        self._pacing_sleep_seconds = 0.0

    def usage(self) -> dict[str, JsonValue]:
        """Return sanitized request and pacing evidence without the User-Agent value."""
        return {
            "provider": "SEC EDGAR",
            "requests": self._request_count,
            "status_counts": dict(sorted(self._status_counts.items())),
            "pacing_sleep_seconds": round(self._pacing_sleep_seconds, 6),
            "runtime_identity_present": True,
            "runtime_identity_emitted": False,
        }

    def discover(self, profile: SourceProfile, continuation: str | None) -> DiscoveryPage:
        validate_edgar_profile(profile)
        offset = self._decode_continuation(continuation)
        records, discovery_references = self._submission_records(profile)
        selected = self._bounded_records(profile, records)
        candidates = (
            ()
            if offset >= len(selected)
            else (self._candidate(profile, selected[offset]),)
        )
        next_token = f"offset:{offset + 1}" if offset + 1 < len(selected) else None
        return DiscoveryPage(
            candidates,
            next_token,
            {
                "provider": "SEC EDGAR",
                "provider_surface": "submissions-api",
                "offset": offset,
                "returned": len(candidates),
                "bounded_candidates": len(selected),
                "submission_files_read": len(discovery_references),
                "request_count": self._request_count,
            },
        )

    def retrieve(self, profile: SourceProfile, candidate: AdapterCandidate) -> RetrievalResult:
        validate_edgar_profile(profile)
        accession = candidate.provenance.metadata.get("accession_no")
        cik = candidate.provenance.metadata.get("issuer_cik")
        if not isinstance(accession, str) or not isinstance(cik, str):
            raise AdapterFailure(
                FailureClass.MALFORMED_ADAPTER,
                "native EDGAR candidate lacks SEC archive identity",
                False,
            )
        accession_digits = accession.replace("-", "")
        archive_path = f"/Archives/edgar/data/{cik}/{accession_digits}/{accession}.txt"
        url = f"{ARCHIVES_ORIGIN}{archive_path}"
        response = self._request(profile, url, int(profile.policy["maximum_artifact_bytes"]))
        media_type = response.headers.get("content-type", "").split(";", 1)[0].lower()
        if media_type not in {"text/plain", "text/html", "application/octet-stream"}:
            raise AdapterFailure(
                FailureClass.PERMANENT_RETRIEVAL,
                f"native EDGAR filing has unexpected content type: {media_type or 'absent'}",
                False,
            )
        if not response.content:
            raise AdapterFailure(
                FailureClass.PERMANENT_RETRIEVAL,
                "native EDGAR filing response is empty",
                False,
            )
        if not response.content.lstrip().startswith(b"<SEC-DOCUMENT>"):
            raise AdapterFailure(
                FailureClass.PERMANENT_RETRIEVAL,
                "native EDGAR filing is not a complete submission",
                False,
            )
        return RetrievalResult(
            response.content,
            "text/plain" if media_type == "application/octet-stream" else media_type,
            self._clock(),
            self.mechanism,
            {"sec_accession": accession, "provider_surface": "edgar-archives"},
            {
                "bytes": len(response.content),
                "provider": "SEC EDGAR",
                "archive_path": archive_path,
                "request_count": self._request_count,
                "minimum_request_interval_seconds": profile.policy[
                    "minimum_request_interval_seconds"
                ],
            },
        )

    def _submission_records(
        self, profile: SourceProfile
    ) -> tuple[list[dict[str, JsonValue]], tuple[str, ...]]:
        cik_padded = str(profile.configuration["cik"]).zfill(10)
        main_path = f"/submissions/CIK{cik_padded}.json"
        main = self._json(profile, f"{SUBMISSIONS_ORIGIN}{main_path}")
        if str(main.get("cik", "")).lstrip("0") != str(profile.configuration["cik"]):
            raise AdapterFailure(
                FailureClass.MALFORMED_ADAPTER,
                "EDGAR submissions response CIK differs from governed issuer",
                False,
            )
        filings = main.get("filings")
        if not isinstance(filings, dict) or not isinstance(filings.get("recent"), dict):
            raise AdapterFailure(
                FailureClass.MALFORMED_ADAPTER,
                "EDGAR submissions response lacks filings.recent",
                False,
            )
        records = self._columnar(filings["recent"])
        for record in records:
            record["_submission_path"] = main_path
        references = [main_path]
        files = filings.get("files", [])
        if not isinstance(files, list):
            raise AdapterFailure(
                FailureClass.MALFORMED_ADAPTER,
                "EDGAR submissions historical files field is malformed",
                False,
            )
        for item in files:
            if not isinstance(item, dict):
                raise AdapterFailure(
                    FailureClass.MALFORMED_ADAPTER,
                    "EDGAR submissions historical file entry is malformed",
                    False,
                )
            name = item.get("name")
            start = item.get("filingFrom")
            through = item.get("filingTo")
            if not all(isinstance(value, str) for value in (name, start, through)):
                raise AdapterFailure(
                    FailureClass.MALFORMED_ADAPTER,
                    "EDGAR submissions historical file identity is incomplete",
                    False,
                )
            if through < profile.configuration["filed_from"] or start > profile.configuration[
                "filed_through"
            ]:
                continue
            path = f"/submissions/{name}"
            historical = self._json(profile, f"{SUBMISSIONS_ORIGIN}{path}")
            historical_records = self._columnar(historical)
            for record in historical_records:
                record["_submission_path"] = path
            records.extend(historical_records)
            references.append(path)
        return records, tuple(references)

    def _json(self, profile: SourceProfile, url: str) -> dict[str, JsonValue]:
        response = self._request(profile, url, 5_000_000)
        media_type = response.headers.get("content-type", "").split(";", 1)[0].lower()
        if media_type not in {"application/json", "application/octet-stream"}:
            raise AdapterFailure(
                FailureClass.MALFORMED_ADAPTER,
                "EDGAR submissions response has unexpected content type",
                False,
            )
        try:
            value = json.loads(response.content)
        except json.JSONDecodeError as error:
            raise AdapterFailure(
                FailureClass.MALFORMED_ADAPTER,
                "EDGAR submissions response contains malformed JSON",
                False,
            ) from error
        if not isinstance(value, dict):
            raise AdapterFailure(
                FailureClass.MALFORMED_ADAPTER,
                "EDGAR submissions JSON is not an object",
                False,
            )
        return value

    def _request(
        self, profile: SourceProfile, url: str, maximum_bytes: int
    ) -> EdgarHttpResponse:
        attempts = int(profile.policy["maximum_attempts_per_request"])
        interval = float(profile.policy["minimum_request_interval_seconds"])
        timeout = float(profile.policy["timeout_seconds"])
        for attempt in range(attempts):
            if self._request_count >= int(profile.policy["maximum_live_requests"]):
                raise AdapterFailure(
                    FailureClass.POLICY_REJECTION,
                    "governed native EDGAR request ceiling reached",
                    False,
                )
            self._pace(interval)
            self._request_count += 1
            try:
                response = self._transport.request(
                    url,
                    {
                        "User-Agent": self._user_agent,
                        "Accept-Encoding": "identity",
                        "Accept": "application/json, text/plain",
                    },
                    timeout,
                    maximum_bytes,
                )
            except (
                TimeoutError,
                socket.timeout,
                urllib.error.URLError,
                OSError,
                ValueError,
            ) as error:
                if attempt + 1 < attempts:
                    continue
                raise AdapterFailure(
                    FailureClass.TRANSIENT_ADAPTER,
                    f"native EDGAR transport failed after {attempts} bounded attempt(s)",
                    True,
                ) from error
            key = str(response.status)
            self._status_counts[key] = self._status_counts.get(key, 0) + 1
            if response.status in {429, 500, 502, 503, 504} and attempt + 1 < attempts:
                continue
            if response.status == 429:
                raise AdapterFailure(
                    FailureClass.TRANSIENT_ADAPTER,
                    "native EDGAR fair-access limit rejected the bounded request",
                    True,
                )
            if response.status in {403, 418}:
                raise AdapterFailure(
                    FailureClass.PERMANENT_RETRIEVAL,
                    "native EDGAR rejected the declared automated client",
                    False,
                )
            if response.status >= 500:
                raise AdapterFailure(
                    FailureClass.TRANSIENT_ADAPTER,
                    f"native EDGAR transient server response: HTTP {response.status}",
                    True,
                )
            if response.status < 200 or response.status >= 300:
                raise AdapterFailure(
                    FailureClass.PERMANENT_RETRIEVAL,
                    f"native EDGAR permanent response: HTTP {response.status}",
                    False,
                )
            return response
        raise AssertionError("unreachable EDGAR request state")

    def _pace(self, interval: float) -> None:
        now = self._monotonic()
        if self._last_request_at is not None:
            remaining = interval - (now - self._last_request_at)
            if remaining > 0:
                self._sleeper(remaining)
                self._pacing_sleep_seconds += remaining
                now = self._monotonic()
        self._last_request_at = now

    @staticmethod
    def _decode_continuation(continuation: str | None) -> int:
        if continuation is None:
            return 0
        try:
            prefix, value = continuation.split(":", 1)
            offset = int(value)
        except (AttributeError, ValueError) as error:
            raise AdapterFailure(
                FailureClass.MALFORMED_ADAPTER,
                "native EDGAR continuation is malformed",
                False,
            ) from error
        if prefix != "offset" or offset < 1 or offset > 4:
            raise AdapterFailure(
                FailureClass.MALFORMED_ADAPTER,
                "native EDGAR continuation is outside governed scope",
                False,
            )
        return offset

    @staticmethod
    def _columnar(value: dict[str, JsonValue]) -> list[dict[str, JsonValue]]:
        required = (
            "accessionNumber",
            "filingDate",
            "reportDate",
            "acceptanceDateTime",
            "form",
            "primaryDocument",
        )
        if any(not isinstance(value.get(name), list) for name in required):
            raise AdapterFailure(
                FailureClass.MALFORMED_ADAPTER,
                "EDGAR submissions columnar data lacks required arrays",
                False,
            )
        lengths = {len(value[name]) for name in required}  # type: ignore[arg-type]
        if len(lengths) != 1:
            raise AdapterFailure(
                FailureClass.MALFORMED_ADAPTER,
                "EDGAR submissions columnar arrays have inconsistent lengths",
                False,
            )
        result = []
        for index in range(lengths.pop()):
            result.append(
                {
                    name: items[index]
                    for name, items in value.items()
                    if isinstance(items, list) and index < len(items)
                }
            )
        return result

    @staticmethod
    def _bounded_records(
        profile: SourceProfile, records: list[dict[str, JsonValue]]
    ) -> list[dict[str, JsonValue]]:
        selected = []
        limits = profile.configuration["form_limits"]
        assert isinstance(limits, dict)
        for form in FORM_ORDER:
            matches = [
                record
                for record in records
                if record.get("form") == form
                and isinstance(record.get("filingDate"), str)
                and profile.configuration["filed_from"]
                <= record["filingDate"]
                <= profile.configuration["filed_through"]
            ]
            matches.sort(
                key=lambda record: (
                    str(record.get("filingDate", "")),
                    str(record.get("acceptanceDateTime", "")),
                    str(record.get("accessionNumber", "")),
                ),
                reverse=True,
            )
            for ordinal, record in enumerate(matches[: int(limits[form])], start=1):
                bounded = dict(record)
                bounded["_form_ordinal"] = ordinal
                selected.append(bounded)
        if len(selected) != sum(int(limits[form]) for form in FORM_ORDER):
            raise AdapterFailure(
                FailureClass.PERMANENT_RETRIEVAL,
                "native EDGAR submissions data does not satisfy the governed corpus bounds",
                False,
            )
        return selected

    @staticmethod
    def _candidate(
        profile: SourceProfile, record: dict[str, JsonValue]
    ) -> AdapterCandidate:
        required = ("accessionNumber", "filingDate", "acceptanceDateTime", "form")
        if any(not isinstance(record.get(field), str) or not record[field] for field in required):
            raise AdapterFailure(
                FailureClass.MALFORMED_ADAPTER,
                "native EDGAR filing lacks required SEC identity fields",
                False,
            )
        accession = str(record["accessionNumber"])
        accession_digits = accession.replace("-", "")
        if len(accession_digits) != 18 or not accession_digits.isdigit():
            raise AdapterFailure(
                FailureClass.MALFORMED_ADAPTER,
                "native EDGAR accession number is malformed",
                False,
            )
        form = str(record["form"])
        form_index = FORM_ORDER.index(form)
        limits = profile.configuration["form_limits"]
        assert isinstance(limits, dict)
        ordinal = record.get("_form_ordinal")
        if not isinstance(ordinal, int) or ordinal < 1:
            raise AdapterFailure(
                FailureClass.MALFORMED_ADAPTER,
                "native EDGAR candidate lacks deterministic bounded ordering",
                False,
            )
        position = (form_index + 1) * 1_000_000 + ordinal
        cik = str(profile.configuration["cik"])
        archive_path = f"/Archives/edgar/data/{cik}/{accession_digits}/{accession}.txt"
        submission_path = record.get("_submission_path")
        if not isinstance(submission_path, str):
            raise AdapterFailure(
                FailureClass.MALFORMED_ADAPTER,
                "native EDGAR candidate lacks submissions discovery provenance",
                False,
            )
        return AdapterCandidate(
            candidate_id=f"candidate-sec-{cik}-{accession_digits}-submission",
            document_id=f"document-sec-{cik}-{accession_digits}",
            position=position,
            revision=f"filing-{accession_digits}",
            provenance=DiscoveryProvenance(
                discovered_at=str(record["acceptanceDateTime"]),
                discovery_method=MECHANISM,
                provider_identifiers={"sec_accession": accession},
                locations=(
                    f"{SUBMISSIONS_ORIGIN}{submission_path}",
                    f"{ARCHIVES_ORIGIN}{archive_path}",
                ),
                metadata={
                    "provider": "SEC EDGAR",
                    "provider_surface": "submissions-api",
                    "issuer_cik": cik,
                    "issuer_ticker": profile.configuration["ticker"],
                    "accession_no": accession,
                    "form_type": form,
                    "amendment": form.endswith("/A"),
                    "filed_at": record["filingDate"],
                    "accepted_at": record["acceptanceDateTime"],
                    "period_of_report": record.get("reportDate"),
                    "primary_document": record.get("primaryDocument"),
                    "submissions_path": submission_path,
                    "complete_submission_archive_path": archive_path,
                },
            ),
        )
