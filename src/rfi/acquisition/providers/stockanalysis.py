"""Deterministic StockAnalysis transcript provider adapter."""

from __future__ import annotations

import hashlib
import json
import re
import urllib.error
import urllib.parse
from dataclasses import dataclass
from datetime import date, datetime
from html.parser import HTMLParser
from typing import Callable, Protocol

from rfi.acquisition.contracts import (
    ContractError,
    DiscoveryProvenance,
    JsonValue,
    RelatedArtifactObservation,
    RetrievalResult,
    SourceProfile,
    TranscriptLearningFeedback,
    TranscriptSeed,
    TranscriptTurnObservation,
)
from rfi.acquisition.earnings_transcripts import EarningsTranscriptHttpResponse
from rfi.acquisition.engine import (
    AdapterCandidate,
    AdapterFailure,
    DiscoveryPage,
    FailureClass,
)
from rfi.storage.sqlite import utc_now

PROVIDER = "stockanalysis"
HOST = "stockanalysis.com"
_IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9.-]{0,15}$")
_DOCUMENT_PATH = re.compile(
    r"^/stocks/(?P<ticker>[a-z0-9.-]+)/transcripts/(?P<slug>[a-z0-9][a-z0-9-]{0,199})/$"
)
_ARCHIVE_PATH = re.compile(r"^/stocks/(?P<ticker>[a-z0-9.-]+)/transcripts/$")
_TRUSTED_DATE_FORMATS = ("%Y-%m-%d", "%B %d, %Y", "%B %d %Y", "%b %d, %Y")
_DATE_LIKE = re.compile(
    r"^(?:20\d{2}[-_/]|Jan(?:uary)?\b|Feb(?:ruary)?\b|Mar(?:ch)?\b|"
    r"Apr(?:il)?\b|May\b|Jun(?:e)?\b|Jul(?:y)?\b|Aug(?:ust)?\b|"
    r"Sep(?:tember)?\b|Oct(?:ober)?\b|Nov(?:ember)?\b|Dec(?:ember)?\b)",
    re.IGNORECASE,
)
_RELATED_KINDS = {
    "annual-report": "annual_report",
    "annual_report": "annual_report",
    "slides": "presentation_slides",
    "presentation-slides": "presentation_slides",
    "earnings-release": "earnings_release",
    "earnings_release": "earnings_release",
    "audio": "audio",
    "transcript-download": "transcript_download",
}
_DIAGNOSTIC_METADATA_KEYS = (
    "company_label",
    "document_title",
    "event_type_label",
    "fiscal_period_label",
    "ticker_label",
)
_MAX_DIAGNOSTIC_METADATA_VALUE_CHARS = 256


class TranscriptProviderTransport(Protocol):
    def get(self, url: str) -> EarningsTranscriptHttpResponse: ...


@dataclass(frozen=True)
class _ArchiveEntry:
    observed_url: str
    normalized_url: str
    label: str
    position: int


class _ArchiveParser(HTMLParser):
    def __init__(self, ticker: str, parent_url: str) -> None:
        super().__init__(convert_charrefs=True)
        self.ticker = ticker
        self.parent_url = parent_url
        self.entries: list[_ArchiveEntry] = []
        self._seen: set[str] = set()
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
        if tag.casefold() != "a" or self._href is None:
            return
        observed = urllib.parse.urljoin(self.parent_url, self._href)
        try:
            normalized, ticker, _slug = validate_document_url(observed)
        except ValueError:
            self._href = None
            self._text = []
            return
        if ticker == self.ticker and normalized not in self._seen:
            self._seen.add(normalized)
            self.entries.append(_ArchiveEntry(
                observed, normalized, " ".join(self._text).strip(), len(self.entries) + 1
            ))
        self._href = None
        self._text = []


@dataclass
class _TurnBuilder:
    speaker: str
    role: str | None
    section: str | None
    paragraphs: list[str]


class _TranscriptParser(HTMLParser):
    """Parse only fixture-covered StockAnalysis transcript structures."""

    def __init__(self, page_url: str) -> None:
        super().__init__(convert_charrefs=True)
        self.page_url = page_url
        self.metadata: dict[str, str] = {}
        self.event_date_observations: list[str] = []
        self.paragraphs: list[str] = []
        self.turns: list[_TurnBuilder] = []
        self.related: list[RelatedArtifactObservation] = []
        self._transcript_depth = 0
        self._excluded_depth = 0
        self._paragraph_depth = 0
        self._text: list[str] = []
        self._turn: _TurnBuilder | None = None
        self._turn_depth = 0
        self._heading: str | None = None
        self._heading_depth = 0
        self._time_depth = 0
        self.metadata_conflict = False
        self._live_speaker_depth = 0
        self._live_role_depth = 0
        self._live_text: list[str] = []
        self._page_title_depth = 0
        self._page_date_depth = 0
        self._json_ld_depth = 0
        self._json_ld_text: list[str] = []
        self._related_depth = 0
        self._related_href: str | None = None
        self._related_link_text: list[str] = []

    def _observe_metadata(self, key: str, value: str) -> None:
        observed = value.strip()
        if not observed:
            return
        if key == "event_date":
            self.event_date_observations.append(observed)
            return
        if key in self.metadata and self.metadata[key] != observed:
            self.metadata_conflict = True
        self.metadata[key] = observed

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = dict(attrs)
        marker = (values.get("data-test") or values.get("id") or "").casefold()
        classes = (values.get("class") or "").casefold().split()
        classes_value = values.get("class") or ""
        if tag.casefold() == "script" and values.get("type") == "application/ld+json":
            self._json_ld_depth = 1
            self._json_ld_text = []
        elif self._json_ld_depth:
            self._json_ld_depth += 1
        if tag.casefold() == "h1" and "text-2xl" in classes_value:
            self._page_title_depth = 1
            self._live_text = []
        elif self._page_title_depth:
            self._page_title_depth += 1
        if tag.casefold() == "p" and all(
            value in classes_value for value in ("text-sm", "font-semibold", "text-faded")
        ):
            self._page_date_depth = 1
            self._live_text = []
        elif self._page_date_depth:
            self._page_date_depth += 1
        if self._transcript_depth:
            self._transcript_depth += 1
        elif marker in {"transcript", "transcript-content", "transcript-body"} or (
            tag.casefold() in {"article", "main"} and "transcript" in classes
        ) or (
            values.get("role") == "article"
            and (values.get("aria-label") or "").casefold() == "full transcript"
        ):
            self._transcript_depth = 1
            for source, target in (
                ("data-title", "document_title"),
                ("data-company", "company_label"),
                ("data-ticker", "ticker_label"),
                ("data-event-type", "event_type_label"),
                ("data-fiscal-period", "fiscal_period_label"),
                ("data-event-date", "event_date"),
            ):
                if values.get(source):
                    self._observe_metadata(target, str(values[source]))
        if not self._transcript_depth:
            return
        if self._related_depth:
            self._related_depth += 1
        elif marker == "related-artifacts":
            self._related_depth = 1
        if (
            tag.casefold() == "a"
            and values.get("href")
            and self._related_depth
        ):
            self._related_href = values["href"]
            self._related_link_text = []
        excluded = values.get("data-provider-summary") is not None or marker in {
            "provider-summary", "related-artifacts", "transcript-controls"
        }
        if self._excluded_depth:
            self._excluded_depth += 1
        elif excluded:
            self._excluded_depth = 1
        related_kind = values.get("data-related-kind")
        href = values.get("href") or values.get("data-url")
        if related_kind and href:
            kind = _RELATED_KINDS.get(related_kind.casefold())
            if kind:
                self.related.append(RelatedArtifactObservation(
                    kind,
                    urllib.parse.urljoin(self.page_url, href),
                    "explicitly_related_to_transcript",
                    self.page_url,
                ))
        if self._excluded_depth:
            return
        if tag.casefold() in {"h1", "h2", "h3"}:
            self._heading = tag.casefold()
            self._heading_depth = self._transcript_depth
            self._text = []
        if tag.casefold() == "time" and values.get("datetime"):
            self._observe_metadata("event_date", str(values["datetime"]))
            self._time_depth = self._transcript_depth
        speaker = values.get("data-speaker")
        if speaker:
            self._turn = _TurnBuilder(
                speaker.strip(),
                (values.get("data-role") or "").strip() or None,
                (values.get("data-section") or "").strip() or None,
                [],
            )
            self._turn_depth = self._transcript_depth
        elif (
            tag.casefold() == "div"
            and self._turn is None
            and all(value in classes for value in ("border-t", "border-sharp", "pt-5"))
        ):
            self._turn = _TurnBuilder("", None, None, [])
            self._turn_depth = self._transcript_depth
        if self._turn is not None and tag.casefold() == "div":
            if all(value in classes for value in ("text-lg", "font-bold", "text-default")):
                self._live_speaker_depth = self._transcript_depth
                self._live_text = []
            elif all(value in classes for value in ("text-sm", "italic", "text-muted")):
                self._live_role_depth = self._transcript_depth
                self._live_text = []
        if tag.casefold() == "p":
            self._paragraph_depth = self._transcript_depth
            self._text = []

    def handle_data(self, data: str) -> None:
        if self._json_ld_depth:
            self._json_ld_text.append(data)
        if self._related_href is not None:
            self._related_link_text.append(data)
        if self._page_title_depth or self._page_date_depth:
            self._live_text.append(data)
            return
        if self._live_speaker_depth or self._live_role_depth:
            self._live_text.append(data)
            return
        if self._transcript_depth and not self._excluded_depth and (
            self._paragraph_depth or self._heading
        ):
            self._text.append(data)

    def handle_endtag(self, tag: str) -> None:
        if self._json_ld_depth:
            if self._json_ld_depth == 1 and tag.casefold() == "script":
                try:
                    value = json.loads("".join(self._json_ld_text))
                except json.JSONDecodeError:
                    value = {}
                if isinstance(value, dict) and value.get("@type") == "Corporation":
                    for source, target in (
                        ("legalName", "company_label"),
                        ("tickerSymbol", "ticker_label"),
                    ):
                        observed = value.get(source)
                        if isinstance(observed, str) and observed.strip():
                            self.metadata.setdefault(target, observed.strip())
                self._json_ld_text = []
            self._json_ld_depth -= 1
        if tag.casefold() == "a" and self._related_href is not None:
            label = " ".join(" ".join(self._related_link_text).split()).casefold()
            kind = _RELATED_KINDS.get(label.replace(" ", "-"))
            if kind:
                self.related.append(RelatedArtifactObservation(
                    kind,
                    urllib.parse.urljoin(self.page_url, self._related_href),
                    "explicitly_related_to_transcript",
                    self.page_url,
                ))
            self._related_href = None
            self._related_link_text = []
        if self._page_title_depth:
            if self._page_title_depth == 1 and tag.casefold() == "h1":
                value = " ".join(" ".join(self._live_text).split())
                if value:
                    self.metadata.setdefault("document_title", value)
                    event = re.fullmatch(
                        r"(?P<event>Earnings Call): (?P<period>Q[1-4] 20\d{2})",
                        value,
                    )
                    if event is not None:
                        self.metadata.setdefault("event_type_label", event.group("event"))
                        self.metadata.setdefault("fiscal_period_label", event.group("period"))
                self._live_text = []
            self._page_title_depth -= 1
        if self._page_date_depth:
            if self._page_date_depth == 1 and tag.casefold() == "p":
                value = " ".join(" ".join(self._live_text).split())
                if value and _DATE_LIKE.match(value):
                    self._observe_metadata("event_date", value)
                self._live_text = []
            self._page_date_depth -= 1
        if not self._transcript_depth:
            return
        if self._excluded_depth:
            self._excluded_depth -= 1
        else:
            if self._turn is not None and self._live_speaker_depth:
                if self._transcript_depth == self._live_speaker_depth:
                    self._turn.speaker = " ".join(" ".join(self._live_text).split())
                    self._live_speaker_depth = 0
                    self._live_text = []
            if self._turn is not None and self._live_role_depth:
                if self._transcript_depth == self._live_role_depth:
                    self._turn.role = " ".join(" ".join(self._live_text).split()) or None
                    self._live_role_depth = 0
                    self._live_text = []
            if tag.casefold() == "p" and self._paragraph_depth:
                text = " ".join(" ".join(self._text).split())
                if text:
                    self.paragraphs.append(text)
                    if self._turn is not None:
                        self._turn.paragraphs.append(text)
                self._paragraph_depth = 0
                self._text = []
            if self._heading == tag.casefold():
                text = " ".join(" ".join(self._text).split())
                if text and self._heading == "h1":
                    self.metadata.setdefault("document_title", text)
                self._heading = None
                self._heading_depth = 0
                self._text = []
            if self._turn is not None and self._transcript_depth == self._turn_depth:
                if self._turn.speaker and self._turn.paragraphs:
                    self.turns.append(self._turn)
                self._turn = None
                self._turn_depth = 0
        if self._related_depth:
            self._related_depth -= 1
        self._transcript_depth -= 1


def normalize_provider_identifier(value: str) -> str:
    """Normalize only the case and surrounding whitespace accepted by StockAnalysis."""
    exact = value.strip()
    if not _IDENTIFIER.fullmatch(exact):
        raise ValueError("StockAnalysis provider identifier is invalid")
    return exact.casefold()


def archive_url(provider_identifier: str) -> str:
    identifier = normalize_provider_identifier(provider_identifier)
    return f"https://{HOST}/stocks/{identifier}/transcripts/"


def _validate_url(url: str) -> urllib.parse.SplitResult:
    parsed = urllib.parse.urlsplit(url)
    if (
        parsed.scheme != "https"
        or (parsed.hostname or "").casefold() != HOST
        or parsed.port not in {None, 443}
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
    ):
        raise ValueError("URL is outside the StockAnalysis transcript namespace")
    return parsed


def validate_archive_url(url: str) -> tuple[str, str]:
    parsed = _validate_url(url)
    match = _ARCHIVE_PATH.fullmatch(parsed.path.casefold())
    if match is None:
        raise ValueError("URL is not a StockAnalysis transcript archive")
    ticker = normalize_provider_identifier(match.group("ticker"))
    return archive_url(ticker), ticker


def validate_document_url(url: str) -> tuple[str, str, str]:
    parsed = _validate_url(url)
    match = _DOCUMENT_PATH.fullmatch(parsed.path.casefold())
    if match is None:
        raise ValueError("URL is not a StockAnalysis transcript document")
    ticker = normalize_provider_identifier(match.group("ticker"))
    slug = match.group("slug").casefold()
    return f"https://{HOST}/stocks/{ticker}/transcripts/{slug}/", ticker, slug


def _trusted_date(value: str | None) -> date | None:
    if not value:
        return None
    for date_format in _TRUSTED_DATE_FORMATS:
        try:
            return datetime.strptime(value.strip(), date_format).date()
        except ValueError:
            continue
    return None


def _trusted_event_date(observations: list[str]) -> date | None:
    """Accept only unanimous, recognized artifact-local date observations."""
    if not observations:
        return None
    normalized = tuple(_trusted_date(value) for value in observations)
    if any(value is None for value in normalized):
        return None
    accepted = {value for value in normalized if value is not None}
    return next(iter(accepted)) if len(accepted) == 1 else None


def _bounded_diagnostic_metadata(metadata: dict[str, str]) -> dict[str, str]:
    """Project trusted labels into a deterministic, body-safe diagnostic bound."""
    return {
        key: metadata[key][:_MAX_DIAGNOSTIC_METADATA_VALUE_CHARS]
        for key in _DIAGNOSTIC_METADATA_KEYS
        if key in metadata
    }


class StockAnalysisTranscriptProvider:
    """One provider-local seed attempt; it never selects or persists another seed."""

    provider = PROVIDER
    supported_seed_kinds = frozenset({"provider_identifier", "url"})
    maximum_retries = 2

    def __init__(
        self,
        transport: TranscriptProviderTransport,
        clock: Callable[[], str] = utc_now,
    ) -> None:
        self.transport = transport
        self.clock = clock
        self.retry_count = 0

    def discover(
        self,
        profile: SourceProfile,
        seed: TranscriptSeed,
        target: object,
    ) -> DiscoveryPage:
        if seed.provider != self.provider or seed.kind not in self.supported_seed_kinds:
            raise ContractError("StockAnalysis received an unsupported provider seed")
        if seed.kind == "provider_identifier":
            exact_identifier = seed.value
            normalized_identifier = normalize_provider_identifier(exact_identifier)
            requested = archive_url(exact_identifier)
            response = self._get(requested)
            resolved, resolved_identifier = validate_archive_url(response.url)
            if resolved_identifier != normalized_identifier:
                raise self._failure("archive redirect changed provider identifier", False,
                                    "provider_identifier_conflict")
            if response.media_type.casefold() not in {"text/html", "application/xhtml+xml"}:
                raise self._failure("StockAnalysis archive is not HTML", False,
                                    "provider_content_type")
            parser = _ArchiveParser(normalized_identifier, response.url)
            parser.feed(response.content.decode("utf-8", "replace"))
            if not parser.entries:
                raise self._failure(
                    "StockAnalysis archive exposed no recognized transcript documents",
                    False,
                    "provider_layout_changed",
                )
            candidate_limit = int(getattr(
                getattr(self.transport, "policy", None),
                "max_candidate_evaluations",
                40,
            ))
            admitted_entries = parser.entries[:candidate_limit]
            candidates = tuple(
                self._candidate(
                    entry.normalized_url,
                    entry.observed_url,
                    entry.label,
                    entry.position,
                    resolved,
                    exact_identifier,
                    normalized_identifier,
                    target,
                )
                for entry in admitted_entries
            )
            diagnostics = self._diagnostics(
                seed, requested, response.url, len(candidates), "archive"
            )
            diagnostics.update({
                "candidate_discovered_count": len(parser.entries),
                "candidate_admitted_count": len(candidates),
                "candidate_bound_exhausted": len(parser.entries) > candidate_limit,
                "candidate_budget": candidate_limit,
            })
            return DiscoveryPage(candidates, None, diagnostics)
        requested, ticker, _slug = validate_document_url(seed.value)
        configured_identifier = profile.configuration.get("discovery_hint_value")
        if (
            not isinstance(configured_identifier, str)
            or normalize_provider_identifier(configured_identifier) != ticker
        ):
            raise self._failure(
                "StockAnalysis URL seed belongs to an unrelated provider identifier",
                False,
                "provider_identifier_conflict",
            )
        candidate = self._candidate(
            requested, seed.value, seed.value, 1, requested, ticker, ticker, target
        )
        return DiscoveryPage((candidate,), None, self._diagnostics(
            seed, seed.value, seed.value, 1, "direct_document"
        ))

    def retrieve(self, profile: SourceProfile, candidate: AdapterCandidate) -> RetrievalResult:
        metadata = candidate.provenance.metadata
        requested = metadata.get("requested_url")
        expected_ticker = metadata.get("provider_identifier_normalized")
        if not isinstance(requested, str) or not isinstance(expected_ticker, str):
            raise ContractError("StockAnalysis candidate provenance is malformed")
        normalized, ticker, _slug = validate_document_url(requested)
        if ticker != expected_ticker:
            raise self._failure("candidate changed provider identifier", False,
                                "provider_identifier_conflict")
        response = self._get(normalized)
        resolved, resolved_ticker, _ = validate_document_url(response.url)
        if resolved_ticker != ticker:
            raise self._failure("document redirect changed provider identifier", False,
                                "provider_identifier_conflict")
        if response.media_type.casefold() not in {"text/html", "application/xhtml+xml"}:
            raise self._failure("StockAnalysis transcript is not HTML", False,
                                "provider_content_type")
        parser = _TranscriptParser(resolved)
        parser.feed(response.content.decode("utf-8", "replace"))
        if not parser.paragraphs:
            raise self._failure(
                "StockAnalysis transcript structure could not be extracted",
                False,
                "provider_layout_changed",
            )
        if parser.metadata_conflict:
            raise self._failure(
                "StockAnalysis artifact contains conflicting trusted metadata",
                False,
                "trusted_metadata_conflict",
            )
        observed_ticker = parser.metadata.get("ticker_label", "").casefold()
        if observed_ticker and observed_ticker != ticker:
            raise self._failure("artifact ticker conflicts with provider identifier", False,
                                "trusted_metadata_conflict")
        event_date = _trusted_event_date(parser.event_date_observations)
        turns = tuple(
            TranscriptTurnObservation(
                index, turn.speaker, turn.role, turn.section, tuple(turn.paragraphs)
            )
            for index, turn in enumerate(parser.turns, start=1)
        )
        related = tuple(dict.fromkeys(
            (item.artifact_kind, item.observed_url, item.relationship_kind,
             item.source_provenance) for item in parser.related
        ))
        related_observations = tuple(
            RelatedArtifactObservation(*item) for item in related[:16]
        )
        metadata_lines = [
            f"{name}: {value}" for name, value in (
                ("Title", parser.metadata.get("document_title")),
                ("Company", parser.metadata.get("company_label")),
                ("Ticker", parser.metadata.get("ticker_label")),
                ("Event type", parser.metadata.get("event_type_label")),
                ("Fiscal period", parser.metadata.get("fiscal_period_label")),
                ("Event date", event_date.isoformat() if event_date else None),
            ) if value
        ]
        retained = ("\n".join((*metadata_lines, "", *parser.paragraphs)).rstrip() + "\n").encode()
        feedback = (
            TranscriptLearningFeedback(
                "confirmed_provider_identifier", self.provider,
                "provider_identifier", expected_ticker
            ),
            TranscriptLearningFeedback(
                "reusable_direct_document", self.provider, "url", resolved
            ),
        )
        turn_payload = json.dumps(
            [item.to_dict() for item in turns],
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
        diagnostics: dict[str, JsonValue] = {
            "http_status": response.status,
            "final_url": response.url,
            "requested_url": requested,
            "resolved_url": response.url,
            "provider": self.provider,
            "provider_metadata": _bounded_diagnostic_metadata(parser.metadata),
            "trusted_event_date_available": event_date is not None,
            "speaker_turn_count": len(turns),
            "speaker_turn_content_sha256": hashlib.sha256(turn_payload).hexdigest(),
            "related_artifact_count": len(related_observations),
            "related_artifact_kinds": [
                item.artifact_kind for item in related_observations
            ],
            "related_artifacts_retrieved": 0,
            "learning_feedback_count": len(feedback),
            "provider_retry_count": self.retry_count,
            "provider_max_retries": self.maximum_retries,
        }
        if event_date is not None:
            diagnostics["trusted_event_date"] = event_date.isoformat()
        return RetrievalResult(
            content=retained,
            media_type="text/plain",
            retrieved_at=self.clock(),
            mechanism="earnings_transcript",
            provider_identifiers={
                "provider": self.provider,
                "provider_identifier": expected_ticker,
            },
            diagnostics=diagnostics,
            trusted_event_date=event_date,
            speaker_turn_observations=turns,
            related_artifact_observations=related_observations,
            transcript_learning_feedback=feedback,
        )

    def _candidate(
        self, normalized: str, observed: str, label: str, position: int,
        parent: str, exact_identifier: str, normalized_identifier: str, target: object,
    ) -> AdapterCandidate:
        digest = hashlib.sha256(normalized.encode()).hexdigest()
        return AdapterCandidate(
            f"candidate-{digest}",
            f"document-{digest}",
            position,
            f"stockanalysis-{digest[:16]}",
            DiscoveryProvenance(
                self.clock(),
                "earnings_transcript",
                {"provider": self.provider, "provider_identifier": exact_identifier},
                tuple(dict.fromkeys((parent, observed, normalized))),
                {
                    "provider_surface": "transcript",
                    "firm_id": getattr(target, "firm_id", ""),
                    "canonical_artifact_id": "earnings_transcript",
                    "requested_url": observed,
                    "resolved_url": normalized,
                    "link_label": label,
                    "provider_identifier_exact": exact_identifier,
                    "provider_identifier_normalized": normalized_identifier,
                    "deferred_candidate_evaluation": True,
                    "proposal_rank": position,
                    "deterministic_selection_rank": [position, 0, 0, 0],
                },
            ),
            target,  # type: ignore[arg-type]
        )

    def _get(self, url: str) -> EarningsTranscriptHttpResponse:
        last_error: Exception | None = None
        for retry in range(self.maximum_retries + 1):
            try:
                response = self.transport.get(url)
                if response.status in {408, 425, 429, 500, 502, 503, 504}:
                    raise urllib.error.HTTPError(
                        url, response.status, f"HTTP {response.status}", None, None
                    )
                if not 200 <= response.status < 300:
                    raise self._failure(
                        f"StockAnalysis returned HTTP {response.status}",
                        response.status >= 500,
                        "provider_http_failure",
                    )
                return response
            except AdapterFailure:
                raise
            except urllib.error.HTTPError as error:
                last_error = error
                if error.code not in {408, 425, 429, 500, 502, 503, 504}:
                    raise self._failure(
                        f"StockAnalysis returned HTTP {error.code}",
                        False,
                        "provider_http_failure",
                    ) from error
                if retry >= self.maximum_retries:
                    break
                self.retry_count += 1
            except (OSError, TimeoutError, ValueError, urllib.error.URLError) as error:
                last_error = error
                if retry >= self.maximum_retries:
                    break
                self.retry_count += 1
        assert last_error is not None
        raise self._failure(
            "StockAnalysis request failed within the provider retry bound",
            True,
            "provider_transport_failure",
        ) from last_error

    def _diagnostics(
        self, seed: TranscriptSeed, requested: str, resolved: str,
        candidates: int, surface: str,
    ) -> dict[str, JsonValue]:
        return {
            "provider": self.provider,
            "seed_provider": seed.provider,
            "seed_kind": seed.kind,
            "seed_source": seed.origin,
            "requested_url": requested,
            "resolved_url": resolved,
            "provider_surface": surface,
            "candidate_urls": candidates,
            "provider_retry_count": self.retry_count,
            "provider_max_retries": self.maximum_retries,
            "search_queries": 0,
            "coverage": "indeterminate",
        }

    @staticmethod
    def _failure(message: str, retryable: bool, code: str) -> AdapterFailure:
        return AdapterFailure(
            FailureClass.TRANSIENT_ADAPTER if retryable else FailureClass.POLICY_REJECTION,
            message,
            retryable,
            code,
        )
