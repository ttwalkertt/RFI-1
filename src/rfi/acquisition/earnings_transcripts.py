"""Bounded acquisition of official textual earnings-call transcripts."""

from __future__ import annotations

import hashlib
import re
import socket
import urllib.parse
import urllib.request
import urllib.error
from dataclasses import dataclass
from datetime import date, datetime
from enum import Enum
from html.parser import HTMLParser
from typing import Callable

from rfi.acquisition.contracts import (
    CandidateDocument,
    ContractError,
    DiscoveryProvenance,
    IntervalAcquisitionFailure,
    IntervalAcquisitionRequest,
    IntervalAcquisitionResult,
    IntervalArtifactEnvelope,
    IntervalCoverage,
    RetrievalResult,
    SourceProfile,
)
from rfi.storage.sqlite import utc_now
from rfi.acquisition.url_identity import normalize_discovery_url

_TRANSCRIPT = re.compile(r"\btranscript(?:ion)?\b", re.I)
_EARNINGS_CALL = re.compile(
    r"\b(?:earnings|quarter(?:ly)?|financial results|results call|conference call)\b", re.I
)
_SPEAKER_EVIDENCE = re.compile(
    r"\b(?:operator|question-and-answer|questions and answers|prepared remarks|"
    r"chief executive officer|chief financial officer)\b", re.I
)
_ISO_DATE = re.compile(r"(?<!\d)(20\d{2})[-_/](0[1-9]|1[0-2])[-_/](0[1-9]|[12]\d|3[01])(?!\d)")
_MONTH_DATE = re.compile(
    r"\b(January|February|March|April|May|June|July|August|September|October|"
    r"November|December)\s+(\d{1,2})(?:st|nd|rd|th)?,?\s+(20\d{2})\b", re.I
)
_DAY_MONTH_DATE = re.compile(
    r"\b(\d{1,2})[- ](January|February|March|April|May|June|July|August|September|"
    r"October|November|December)[- ](20\d{2})\b", re.I
)
_QUARTER_YEAR = re.compile(r"\bq([1-4])\D{0,12}(20\d{2})\b", re.I)
_YEAR_QUARTER = re.compile(r"\b(20\d{2})\D{0,12}q([1-4])\b", re.I)

TRANSCRIPT_ACCEPT = (
    "text/html, application/xhtml+xml, application/pdf;q=0.9, */*;q=0.1"
)


def transcript_request_headers(user_agent: str) -> dict[str, str]:
    """Negotiate the representations supported by transcript discovery and validation."""
    return {"User-Agent": user_agent, "Accept": TRANSCRIPT_ACCEPT}


@dataclass(frozen=True)
class EarningsTranscriptHttpResponse:
    """Exact bounded HTTP response used by the transcript retriever."""

    url: str
    status: int
    media_type: str
    content: bytes
    redirects: tuple[str, ...] = ()


class CandidateFailureCode(str, Enum):
    """Stable machine classification for candidate retrieval and validation failures."""

    HTTP_NOT_FOUND = "candidate_http_not_found"
    ACCESS_DENIED = "candidate_access_denied"
    FETCH_TIMEOUT = "candidate_fetch_timeout"
    UNSUPPORTED_CONTENT_TYPE = "candidate_unsupported_content_type"
    EMPTY_CONTENT = "candidate_empty"
    JAVASCRIPT_REQUIRED = "candidate_requires_javascript"
    VALIDATION_MISMATCH = "candidate_validation_mismatch"
    RETRIEVAL_FAILURE = "candidate_retrieval_failure"


@dataclass(frozen=True)
class CandidateFailure:
    """Typed candidate failure; its message is presentation, not classification."""

    code: CandidateFailureCode
    message: str
    http_status: int | None = None


@dataclass(frozen=True, order=True)
class ReportingPeriod:
    """Recognizable calendar reporting quarter used only for deterministic ordering."""

    year: int
    quarter: int

    def __post_init__(self) -> None:
        if self.year < 2000 or self.year > 2100 or self.quarter not in {1, 2, 3, 4}:
            raise ValueError("reporting period is outside the supported range")

    @property
    def ordinal(self) -> int:
        return self.year * 4 + self.quarter

    @property
    def code(self) -> str:
        return f"{self.year}-Q{self.quarter}"

    def next(self) -> ReportingPeriod:
        return (
            ReportingPeriod(self.year + 1, 1)
            if self.quarter == 4 else ReportingPeriod(self.year, self.quarter + 1)
        )

    def previous(self) -> ReportingPeriod:
        return (
            ReportingPeriod(self.year - 1, 4)
            if self.quarter == 1 else ReportingPeriod(self.year, self.quarter - 1)
        )

    @classmethod
    def from_date(cls, value: date) -> ReportingPeriod:
        return cls(value.year, ((value.month - 1) // 3) + 1)

    @classmethod
    def parse(cls, value: str) -> ReportingPeriod:
        match = re.fullmatch(r"(20\d{2})-Q([1-4])", value, re.I)
        if match is None:
            raise ValueError("reporting period must use YYYY-QN")
        return cls(int(match.group(1)), int(match.group(2)))


def reporting_period_from_evidence(*values: str | bytes) -> ReportingPeriod | None:
    """Extract an explicit quarter/year or calendar date without validating a candidate."""
    for value in values:
        text = value.decode("utf-8", "replace") if isinstance(value, bytes) else value
        match = _QUARTER_YEAR.search(text)
        if match:
            return ReportingPeriod(int(match.group(2)), int(match.group(1)))
        match = _YEAR_QUARTER.search(text)
        if match:
            return ReportingPeriod(int(match.group(1)), int(match.group(2)))
        for pattern, date_format in (
            (_ISO_DATE, None), (_MONTH_DATE, "%B %d %Y"),
            (_DAY_MONTH_DATE, "%d %B %Y"),
        ):
            match = pattern.search(text)
            if match is None:
                continue
            try:
                parsed = (
                    date(*(int(part) for part in match.groups()))
                    if date_format is None
                    else datetime.strptime(" ".join(match.groups()), date_format).date()
                )
            except ValueError:
                continue
            return ReportingPeriod.from_date(parsed)
    return None


class CandidateDispositionCode(str, Enum):
    VALID_NEW_ARTIFACT = "valid_new_artifact"
    CURRENT_CHECKPOINT_PERIOD = "current_checkpoint_period"
    OLDER_THAN_CHECKPOINT = "older_than_checkpoint"
    HISTORICAL_PERIOD = "historical_period"
    DUPLICATE_CANDIDATE = "duplicate_candidate"
    WRONG_REPORTING_PERIOD = "wrong_reporting_period"
    WRONG_FIRM = "wrong_firm"
    CANDIDATE_URL_INVALID = "candidate_url_invalid"


@dataclass(frozen=True)
class CandidateDisposition:
    code: str
    url: str
    reporting_period: str | None = None


def normalize_transcript_url(url: str) -> str:
    """Transcript-facing name for the shared repository normalization contract."""
    return normalize_discovery_url(url)


class EarningsTranscriptTransport:
    """Small injectable transport boundary for official public IR pages."""

    def get(self, url: str) -> EarningsTranscriptHttpResponse:
        raise NotImplementedError


class UrllibEarningsTranscriptTransport(EarningsTranscriptTransport):
    """Bounded urllib transport with an explicit product user agent."""

    def __init__(self, timeout_seconds: float = 30.0, maximum_bytes: int = 20_000_000) -> None:
        self.timeout_seconds = timeout_seconds
        self.maximum_bytes = maximum_bytes

    def get(self, url: str) -> EarningsTranscriptHttpResponse:
        request = urllib.request.Request(
            url,
            headers=transcript_request_headers("RFI-1 transcript acquisition"),
        )
        with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
            content = response.read(self.maximum_bytes + 1)
            if len(content) > self.maximum_bytes:
                raise ValueError("response exceeds configured maximum bytes")
            return EarningsTranscriptHttpResponse(
                response.geturl(), getattr(response, "status", 200),
                response.headers.get_content_type(), content,
            )


@dataclass(frozen=True)
class _Proposal:
    url: str
    label: str
    evidence_url: str


class _LinkParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.links: list[tuple[str, str]] = []
        self._href: str | None = None
        self._text: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.casefold() == "a":
            self._href = dict(attrs).get("href")
            self._text = []

    def handle_data(self, data: str) -> None:
        if self._href is not None:
            self._text.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag.casefold() == "a" and self._href is not None:
            self.links.append((self._href, " ".join(self._text).strip()))
            self._href = None
            self._text = []


class EarningsCallTranscriptAcquisition:
    """Discover and validate official transcript HTML/PDF without persisting it."""

    mechanism = "earnings_transcript"

    def __init__(
        self,
        source: SourceProfile,
        transport: EarningsTranscriptTransport | None = None,
        clock: Callable[[], str] = utc_now,
    ) -> None:
        if source.mechanism != self.mechanism:
            raise ContractError("earnings transcript source has the wrong mechanism")
        if source.policy.get("artifact_id") != "earnings_transcript":
            raise ContractError("earnings transcript source policy has the wrong artifact type")
        self.source = source
        self.transport = transport or UrllibEarningsTranscriptTransport()
        self.clock = clock
        self.candidate_dispositions: tuple[CandidateDisposition, ...] = ()

    def acquire(self, request: IntervalAcquisitionRequest) -> IntervalAcquisitionResult:
        """Return validated successes and conservative coverage for one interval."""
        if request.artifact_type != "earnings_transcript":
            raise ContractError("earnings transcript acquisition requires earnings_transcript")
        if self.source.policy.get("firm_id") != request.firm_id:
            raise ContractError("earnings transcript source policy does not match requested firm")
        if request.start_date == request.end_date:
            return IntervalAcquisitionResult((), (), IntervalCoverage.COMPLETE)

        listing_urls = self._string_list("listing_urls", minimum=1, maximum=8)
        allowed_hosts = set(self._string_list("allowed_hosts", minimum=0, maximum=16))
        allowed_hosts.update(urllib.parse.urlsplit(url).hostname or "" for url in listing_urls)
        failures: list[IntervalAcquisitionFailure] = []
        proposals: list[_Proposal] = []
        for listing_url in listing_urls:
            try:
                response = self._fetch(listing_url, allowed_hosts)
                if response.media_type not in {"text/html", "application/xhtml+xml"}:
                    raise ValueError("authoritative listing is not HTML")
                parser = _LinkParser()
                parser.feed(response.content.decode("utf-8", "replace"))
                if self.source.configuration.get("discover_listing_links", True) is True:
                    for href, label in parser.links:
                        url = urllib.parse.urljoin(response.url, href)
                        if self._looks_like_transcript(label, url):
                            proposals.append(_Proposal(url, label, response.url))
            except Exception as error:  # transport/parser failures become structured evidence
                failures.append(self._failure("listing_unavailable", listing_url, error, True))

        # Explicit proposals are an implementation seam: all still pass the same deterministic
        # host, date, media, and transcript validation as listing-derived candidates.
        for item in self.source.configuration.get("candidate_proposals", []):
            if isinstance(item, dict) and isinstance(item.get("url"), str):
                label = item.get("label") if isinstance(item.get("label"), str) else ""
                proposals.append(_Proposal(item["url"], label, "invocation-candidate-proposal"))

        artifacts: list[IntervalArtifactEnvelope] = []
        historical_artifacts: list[IntervalArtifactEnvelope] = []
        dispositions: list[CandidateDisposition] = []
        checkpoint_period = self._configured_reporting_period("checkpoint_reporting_period")
        expected_period = self._configured_reporting_period("expected_reporting_period")
        expected_period_evaluated = False
        seen: set[str] = set()
        for proposal in proposals[: self._positive_int("maximum_candidates", 40, 1, 100)]:
            try:
                normalized = self._normalize_url(proposal.url)
            except Exception as error:
                candidate_failure = CandidateFailure(
                    CandidateFailureCode.VALIDATION_MISMATCH,
                    str(error) or error.__class__.__name__,
                )
                failures.append(
                    self._failure(
                        "candidate_invalid", proposal.url, error, False,
                        self._identifier("candidate", proposal.url),
                        candidate_failure,
                    )
                )
                dispositions.append(CandidateDisposition(
                    CandidateDispositionCode.CANDIDATE_URL_INVALID.value, proposal.url
                ))
                continue
            if normalized in seen:
                dispositions.append(CandidateDisposition(
                    CandidateDispositionCode.DUPLICATE_CANDIDATE.value, normalized
                ))
                continue
            seen.add(normalized)
            proposal_period = reporting_period_from_evidence(proposal.label, normalized)
            expected_period_evaluated = expected_period_evaluated or (
                proposal_period == expected_period
            )
            source_artifact_id = self._identifier("candidate", normalized)
            try:
                response = self._fetch(normalized, allowed_hosts)
            except Exception as error:
                candidate_failure = self._candidate_retrieval_failure(error)
                failures.append(
                    self._failure(
                        "candidate_unavailable", normalized, error, True, source_artifact_id,
                        candidate_failure,
                    )
                )
                dispositions.append(CandidateDisposition(
                    candidate_failure.code.value, normalized,
                    proposal_period.code if proposal_period else None,
                ))
                continue
            try:
                artifact_date = self._artifact_date(proposal.label, response.url, response.content)
                if artifact_date is None:
                    raise ValueError("candidate publication/event date could not be established")
                if not request.contains(artifact_date):
                    dispositions.append(CandidateDisposition(
                        CandidateDispositionCode.WRONG_REPORTING_PERIOD.value, normalized
                    ))
                    continue
                period = ReportingPeriod.from_date(artifact_date)
                expected_period_evaluated = (
                    expected_period_evaluated or period == expected_period
                )
                validation_failure = self._transcript_validation_failure(
                    response, proposal.label
                )
                if validation_failure is not None:
                    failures.append(self._failure(
                        "candidate_invalid", normalized,
                        ValueError(validation_failure.message), False,
                        source_artifact_id, validation_failure,
                    ))
                    dispositions.append(CandidateDisposition(
                        validation_failure.code.value, normalized,
                        period.code,
                    ))
                    continue
                try:
                    self._validate_firm_identity(response, proposal.label)
                except ValueError as error:
                    candidate_failure = CandidateFailure(
                        CandidateFailureCode.VALIDATION_MISMATCH, str(error)
                    )
                    failures.append(self._failure(
                        "candidate_invalid", normalized, error, False,
                        source_artifact_id, candidate_failure,
                    ))
                    dispositions.append(CandidateDisposition(
                        CandidateDispositionCode.WRONG_FIRM.value, normalized,
                        period.code,
                    ))
                    continue
                if checkpoint_period is not None and period <= checkpoint_period:
                    disposition = (
                        CandidateDispositionCode.CURRENT_CHECKPOINT_PERIOD
                        if period == checkpoint_period
                        else CandidateDispositionCode.OLDER_THAN_CHECKPOINT
                    )
                    dispositions.append(CandidateDisposition(
                        disposition.value, normalized, period.code
                    ))
                    continue
                if checkpoint_period is None and expected_period is not None and (
                    period < expected_period
                ):
                    dispositions.append(CandidateDisposition(
                        CandidateDispositionCode.HISTORICAL_PERIOD.value,
                        normalized, period.code,
                    ))
                    historical_artifacts.append(
                        self._envelope(proposal, response, artifact_date)
                    )
                else:
                    artifacts.append(self._envelope(proposal, response, artifact_date))
                    dispositions.append(CandidateDisposition(
                        CandidateDispositionCode.VALID_NEW_ARTIFACT.value,
                        normalized, period.code,
                    ))
            except Exception as error:
                candidate_failure = CandidateFailure(
                    CandidateFailureCode.VALIDATION_MISMATCH,
                    str(error) or error.__class__.__name__,
                )
                failures.append(
                    self._failure(
                        "candidate_invalid", normalized, error, False, source_artifact_id,
                        candidate_failure,
                    )
                )
                dispositions.append(CandidateDisposition(
                    CandidateFailureCode.VALIDATION_MISMATCH.value, normalized
                ))

        if not expected_period_evaluated:
            artifacts.extend(historical_artifacts)

        if len(proposals) > self._positive_int("maximum_candidates", 40, 1, 100):
            failures.append(IntervalAcquisitionFailure(
                "candidate_limit", "candidate discovery exceeded the configured bound", False,
                details={"discovered": len(proposals)},
            ))
        if failures:
            coverage = IntervalCoverage.INCOMPLETE
        elif self.source.configuration.get("authoritative_listing") is True:
            coverage = IntervalCoverage.COMPLETE
        else:
            coverage = IntervalCoverage.INDETERMINATE
        self.candidate_dispositions = tuple(dispositions)
        return IntervalAcquisitionResult(tuple(artifacts), tuple(failures), coverage)

    def _envelope(
        self, proposal: _Proposal, response: EarningsTranscriptHttpResponse, artifact_date: date
    ) -> IntervalArtifactEnvelope:
        normalized = self._normalize_url(response.url)
        digest = hashlib.sha256(normalized.encode()).hexdigest()
        discovered_at = self.clock()
        return IntervalArtifactEnvelope(
            CandidateDocument(
                f"candidate-{digest}", self.source.source_id, f"document-{digest}",
                DiscoveryProvenance(
                    discovered_at, self.mechanism, locations=(proposal.evidence_url, normalized),
                    metadata={
                        "firm_id": self.source.policy["firm_id"],
                        "canonical_artifact_id": "earnings_transcript",
                        "link_label": proposal.label,
                        "requested_url": proposal.url,
                        "resolved_url": response.url,
                    },
                ),
            ),
            artifact_date,
            RetrievalResult(
                response.content, response.media_type, discovered_at, self.mechanism,
                diagnostics={"http_status": response.status, "final_url": response.url},
            ),
        )

    def _fetch(self, url: str, allowed_hosts: set[str]) -> EarningsTranscriptHttpResponse:
        normalized = self._normalize_url(url)
        host = urllib.parse.urlsplit(normalized).hostname or ""
        if not any(host == allowed or host.endswith(f".{allowed}") for allowed in allowed_hosts):
            raise ValueError("candidate host is outside the governed official-source policy")
        response = self.transport.get(normalized)
        if response.status < 200 or response.status >= 300:
            raise urllib.error.HTTPError(
                normalized, response.status, f"HTTP {response.status}", None, None
            )
        final_host = urllib.parse.urlsplit(response.url).hostname or ""
        if not any(
            final_host == allowed or final_host.endswith(f".{allowed}")
            for allowed in allowed_hosts
        ):
            raise ValueError("redirect left the governed official-source policy")
        return response

    @staticmethod
    def _transcript_validation_failure(
        response: EarningsTranscriptHttpResponse, label: str
    ) -> CandidateFailure | None:
        media_type = response.media_type.casefold()
        if not response.content.strip():
            return CandidateFailure(
                CandidateFailureCode.EMPTY_CONTENT, "candidate content is empty"
            )
        if media_type in {"text/html", "application/xhtml+xml"}:
            if not response.content.lstrip().lower().startswith((b"<!doctype html", b"<html")):
                return CandidateFailure(
                    CandidateFailureCode.VALIDATION_MISMATCH,
                    "HTML candidate lacks an HTML document signature",
                )
            text = re.sub(r"<[^>]+>", " ", response.content.decode("utf-8", "replace"))
            if re.search(r"\b(?:enable|requires?)\s+javascript\b", text, re.I) and len(text) < 500:
                return CandidateFailure(
                    CandidateFailureCode.JAVASCRIPT_REQUIRED,
                    "candidate requires JavaScript",
                )
            if not (_TRANSCRIPT.search(label + " " + text) and _EARNINGS_CALL.search(text)):
                return CandidateFailure(
                    CandidateFailureCode.VALIDATION_MISMATCH,
                    "HTML candidate is not identified as an earnings-call transcript",
                )
            if not _SPEAKER_EVIDENCE.search(text):
                return CandidateFailure(
                    CandidateFailureCode.VALIDATION_MISMATCH,
                    "HTML candidate lacks transcript speaker/section evidence",
                )
            return None
        if media_type == "application/pdf":
            if not response.content.startswith(b"%PDF-"):
                return CandidateFailure(
                    CandidateFailureCode.VALIDATION_MISMATCH,
                    "PDF candidate lacks a PDF signature",
                )
            evidence = urllib.parse.unquote(label + " " + response.url)
            if not (_TRANSCRIPT.search(evidence) and _EARNINGS_CALL.search(evidence)):
                return CandidateFailure(
                    CandidateFailureCode.VALIDATION_MISMATCH,
                    "PDF link is not identified as an earnings-call transcript",
                )
            return None
        return CandidateFailure(
            CandidateFailureCode.UNSUPPORTED_CONTENT_TYPE,
            f"unsupported transcript media type: {response.media_type}",
        )

    @staticmethod
    def _candidate_retrieval_failure(error: Exception) -> CandidateFailure:
        status = getattr(error, "code", None)
        message = str(error) or error.__class__.__name__
        if isinstance(error, urllib.error.HTTPError):
            error.close()
        if status == 404:
            return CandidateFailure(CandidateFailureCode.HTTP_NOT_FOUND, message, status)
        if status in {401, 403}:
            return CandidateFailure(CandidateFailureCode.ACCESS_DENIED, message, status)
        reason = error.reason if isinstance(error, urllib.error.URLError) else None
        if isinstance(error, (TimeoutError, socket.timeout)) or isinstance(
            reason, (TimeoutError, socket.timeout)
        ):
            return CandidateFailure(CandidateFailureCode.FETCH_TIMEOUT, message)
        return CandidateFailure(CandidateFailureCode.RETRIEVAL_FAILURE, message, status)

    @staticmethod
    def _looks_like_transcript(label: str, url: str) -> bool:
        evidence = urllib.parse.unquote(label + " " + url).replace("_", " ").replace("-", " ")
        return bool(_TRANSCRIPT.search(evidence) and _EARNINGS_CALL.search(evidence))

    def _validate_firm_identity(
        self, response: EarningsTranscriptHttpResponse, label: str
    ) -> None:
        terms = self._string_list("firm_identity_terms", minimum=0, maximum=32)
        if not terms:
            return
        evidence = urllib.parse.unquote(label + " " + response.url)
        if response.media_type.casefold() in {"text/html", "application/xhtml+xml"}:
            evidence += " " + re.sub(
                r"<[^>]+>", " ", response.content.decode("utf-8", "replace")
            )
        normalized = re.sub(r"[^a-z0-9]+", " ", evidence.casefold())
        if not any(
            re.sub(r"[^a-z0-9]+", " ", term.casefold()).strip() in normalized
            for term in terms
            if term.strip()
        ):
            raise ValueError("transcript candidate lacks configured firm identity evidence")

    @staticmethod
    def _artifact_date(*values: str | bytes) -> date | None:
        # Preserve evidence priority: a descriptive link label is more specific than unrelated
        # dates elsewhere in a full event page, followed by the final URL and then document body.
        for value in values:
            text = value.decode("utf-8", "replace") if isinstance(value, bytes) else value
            match = _ISO_DATE.search(text)
            if match:
                try:
                    return date(*(int(part) for part in match.groups()))
                except ValueError:
                    pass
            match = _MONTH_DATE.search(text)
            if match:
                try:
                    return datetime.strptime(" ".join(match.groups()), "%B %d %Y").date()
                except ValueError:
                    pass
            match = _DAY_MONTH_DATE.search(text)
            if match:
                try:
                    return datetime.strptime(" ".join(match.groups()), "%d %B %Y").date()
                except ValueError:
                    pass
        return None

    def _string_list(self, name: str, minimum: int, maximum: int) -> tuple[str, ...]:
        value = self.source.configuration.get(name, [])
        if not isinstance(value, list) or any(
            not isinstance(item, str) or not item for item in value
        ):
            raise ContractError(f"earnings transcript {name} must be a string array")
        if not minimum <= len(value) <= maximum:
            raise ContractError(f"earnings transcript {name} count is outside its bound")
        return tuple(value)

    def _positive_int(self, name: str, default: int, minimum: int, maximum: int) -> int:
        value = self.source.configuration.get(name, default)
        if (
            isinstance(value, bool)
            or not isinstance(value, int)
            or not minimum <= value <= maximum
        ):
            raise ContractError(f"earnings transcript {name} is outside its bound")
        return value

    def _configured_reporting_period(self, name: str) -> ReportingPeriod | None:
        value = self.source.configuration.get(name)
        if value is None:
            return None
        if not isinstance(value, str):
            raise ContractError(f"earnings transcript {name} must be a string")
        try:
            return ReportingPeriod.parse(value)
        except ValueError as error:
            raise ContractError(f"earnings transcript {name} is invalid") from error

    @staticmethod
    def _normalize_url(url: str) -> str:
        return normalize_transcript_url(url)

    @staticmethod
    def _identifier(prefix: str, value: str) -> str:
        return f"{prefix}-{hashlib.sha256(value.encode()).hexdigest()}"

    @staticmethod
    def _failure(
        code: str, url: str, error: Exception, retryable: bool,
        source_artifact_id: str | None = None,
        candidate_failure: CandidateFailure | None = None,
    ) -> IntervalAcquisitionFailure:
        details: dict[str, object] = {
            "url": url, "error_type": error.__class__.__name__
        }
        if candidate_failure is not None:
            details["candidate_failure_code"] = candidate_failure.code.value
            if candidate_failure.http_status is not None:
                details["http_status"] = candidate_failure.http_status
        return IntervalAcquisitionFailure(
            code, str(error) or error.__class__.__name__, retryable, source_artifact_id,
            details,
        )
