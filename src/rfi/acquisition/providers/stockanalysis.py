"""Deterministic StockAnalysis transcript provider adapter."""

from __future__ import annotations

import hashlib
import json
import re
import urllib.error
import urllib.parse
from dataclasses import dataclass, field
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
    TranscriptEventDisposition,
    TranscriptLearningFeedback,
    TranscriptMetadataObservation,
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
_RELATED_KINDS = {
    "annual-report": "annual_report",
    "annual_report": "annual_report",
    "slides": "presentation_slides",
    "presentation-slides": "presentation_slides",
    "earnings-release": "earnings_release",
    "earnings_release": "earnings_release",
    "quarterly-report": "quarterly_report",
    "quarterly_report": "quarterly_report",
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
MIN_TURN_COUNT = 2
MIN_CONTENT_TURNS = 2
MIN_TRANSCRIPT_WORDS = 8
MIN_SPEAKER_LABELS = 2


def _normalize_opaque_text(value: str) -> str:
    """Bounded representation normalization without semantic interpretation."""
    return " ".join(value.split())


def word_count(normalized_text: str) -> int:
    """Count bounded normalized text without interpreting its subject matter."""
    return len(re.findall(r"\b\w+\b", normalized_text, flags=re.UNICODE))


def distinct_speaker_label_count(
    turns: tuple[TranscriptTurnObservation, ...],
) -> int:
    """Count exact opaque speaker labels after representation normalization."""
    return len({turn.speaker_label for turn in turns})


def is_substantial_transcript(
    *,
    turns: tuple[TranscriptTurnObservation, ...],
    normalized_text: str,
) -> bool:
    """Reject only artifacts lacking the already-parsed transcript structure."""
    contiguous_turn_text = "\n".join(
        paragraph
        for turn in turns
        for paragraph in turn.paragraphs
    )
    return (
        len(turns) >= MIN_TURN_COUNT
        and sum(bool(turn.paragraphs) for turn in turns) >= MIN_CONTENT_TURNS
        and word_count(normalized_text) >= MIN_TRANSCRIPT_WORDS
        and distinct_speaker_label_count(turns) >= MIN_SPEAKER_LABELS
        and contiguous_turn_text == normalized_text
    )


class TranscriptProviderTransport(Protocol):
    def get(self, url: str) -> EarningsTranscriptHttpResponse: ...


@dataclass(frozen=True)
class _ArchiveEntry:
    observed_url: str
    normalized_url: str
    label: str
    position: int
    event_disposition: TranscriptEventDisposition
    related: tuple[RelatedArtifactObservation, ...]


@dataclass
class _ArchiveEntryBuilder:
    observed_url: str = ""
    normalized_url: str = ""
    label: str = ""
    related: list[RelatedArtifactObservation] = field(default_factory=list)


class _ArchiveParser(HTMLParser):
    def __init__(self, ticker: str, parent_url: str) -> None:
        super().__init__(convert_charrefs=True)
        self.ticker = ticker
        self.parent_url = parent_url
        self.entries: list[_ArchiveEntry] = []
        self._seen: set[str] = set()
        self._entry: _ArchiveEntryBuilder | None = None
        self._entry_depth = 0
        self._relationship_depth = 0
        self._href: str | None = None
        self._text: list[str] = []
        self._fallback_href: str | None = None
        self._fallback_text: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = dict(attrs)
        classes = set((values.get("class") or "").casefold().split())
        if self._entry is not None:
            self._entry_depth += 1
        elif tag.casefold() == "li" and {
            "rounded-lg", "border", "border-sharp", "bg-contrast"
        }.issubset(classes):
            self._entry = _ArchiveEntryBuilder()
            self._entry_depth = 1
        if self._entry is None:
            if tag.casefold() == "a":
                self._fallback_href = values.get("href")
                self._fallback_text = []
            return
        if self._relationship_depth:
            self._relationship_depth += 1
        elif (
            tag.casefold() == "ul"
            and values.get("role") == "group"
            and values.get("aria-label") == "Downloads"
        ):
            self._relationship_depth = 1
        if tag.casefold() == "a":
            self._href = dict(attrs).get("href")
            self._text = []

    def handle_data(self, data: str) -> None:
        if self._entry is not None and self._href is not None:
            self._text.append(data)
        elif self._fallback_href is not None:
            self._fallback_text.append(data)

    def handle_endtag(self, tag: str) -> None:
        if self._entry is None:
            if tag.casefold() == "a" and self._fallback_href is not None:
                observed = urllib.parse.urljoin(self.parent_url, self._fallback_href)
                label = _normalize_opaque_text(" ".join(self._fallback_text))
                try:
                    normalized, ticker, _slug = validate_document_url(observed)
                except ValueError:
                    normalized = ""
                    ticker = ""
                if (
                    normalized
                    and ticker == self.ticker
                    and normalized not in self._seen
                ):
                    self._seen.add(normalized)
                    self.entries.append(_ArchiveEntry(
                        observed,
                        normalized,
                        label,
                        len(self.entries) + 1,
                        TranscriptEventDisposition.UNKNOWN,
                        (),
                    ))
                self._fallback_href = None
                self._fallback_text = []
            return
        if tag.casefold() == "a" and self._href is not None:
            observed = urllib.parse.urljoin(self.parent_url, self._href)
            label = _normalize_opaque_text(" ".join(self._text))
            try:
                normalized, ticker, _slug = validate_document_url(observed)
            except ValueError:
                normalized = ""
                ticker = ""
            if (
                normalized
                and ticker == self.ticker
                and not self._entry.normalized_url
            ):
                self._entry.observed_url = observed
                self._entry.normalized_url = normalized
                self._entry.label = label
            elif self._relationship_depth and label:
                kind = _RELATED_KINDS.get(label.casefold().replace(" ", "-"))
                if kind:
                    self._entry.related.append(RelatedArtifactObservation(
                        kind,
                        observed,
                        "explicitly_related_to_transcript",
                        self.parent_url,
                        label,
                    ))
            self._href = None
            self._text = []
        if self._relationship_depth:
            self._relationship_depth -= 1
        self._entry_depth -= 1
        if self._entry_depth:
            return
        entry = self._entry
        self._entry = None
        if not entry.normalized_url or entry.normalized_url in self._seen:
            return
        self._seen.add(entry.normalized_url)
        related = tuple(dict.fromkeys(entry.related))
        self.entries.append(_ArchiveEntry(
            entry.observed_url,
            entry.normalized_url,
            entry.label,
            len(self.entries) + 1,
            TranscriptEventDisposition.UNKNOWN,
            related,
        ))


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
        self._json_ld_depth = 0
        self._json_ld_text: list[str] = []
        self._related_depth = 0
        self._related_href: str | None = None
        self._related_link_text: list[str] = []
        self._related_explicit_kind: str | None = None
        self._artifact_header_depth = 0
        self._header_date_depth = 0
        self._header_date_text: list[str] = []
        self._header_label_depth = 0
        self._header_label_text: list[str] = []

    def _observe_metadata(self, key: str, value: str) -> None:
        observed = _normalize_opaque_text(value)
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
        if self._artifact_header_depth:
            self._artifact_header_depth += 1
        elif (
            tag.casefold() == "div"
            and {"flex", "flex-wrap", "items-baseline", "gap-x-3"}.issubset(classes)
        ):
            self._artifact_header_depth = 1
        if self._artifact_header_depth and tag.casefold() == "h1":
            self._header_label_depth = self._artifact_header_depth
            self._header_label_text = []
        if (
            self._artifact_header_depth
            and tag.casefold() == "p"
            and all(
                value in classes
                for value in ("text-sm", "font-semibold", "text-faded")
            )
        ):
            self._header_date_depth = self._artifact_header_depth
            self._header_date_text = []
        if self._related_depth:
            self._related_depth += 1
        elif marker == "related-artifacts" or (
            tag.casefold() == "ul"
            and values.get("role") == "group"
            and values.get("aria-label") == "Downloads"
        ):
            self._related_depth = 1
        related_kind = values.get("data-related-kind")
        explicit_kind = (
            _RELATED_KINDS.get(related_kind.casefold()) if related_kind else None
        )
        if (
            tag.casefold() == "a"
            and values.get("href")
            and (self._related_depth or explicit_kind)
        ):
            self._related_href = values["href"]
            self._related_link_text = []
            self._related_explicit_kind = explicit_kind
        href = values.get("href") or values.get("data-url")
        if explicit_kind and href and tag.casefold() != "a":
            self.related.append(RelatedArtifactObservation(
                explicit_kind,
                urllib.parse.urljoin(self.page_url, href),
                "explicitly_related_to_transcript",
                self.page_url,
                _normalize_opaque_text(values.get("data-related-label") or ""),
            ))
        if tag.casefold() == "script" and values.get("type") == "application/ld+json":
            self._json_ld_depth = 1
            self._json_ld_text = []
        elif self._json_ld_depth:
            self._json_ld_depth += 1
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
        excluded = values.get("data-provider-summary") is not None or marker in {
            "provider-summary", "related-artifacts", "transcript-controls"
        }
        if self._excluded_depth:
            self._excluded_depth += 1
        elif excluded:
            self._excluded_depth = 1
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
                _normalize_opaque_text(speaker),
                _normalize_opaque_text(values.get("data-role") or "") or None,
                _normalize_opaque_text(values.get("data-section") or "") or None,
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
        if self._header_date_depth:
            self._header_date_text.append(data)
        if self._header_label_depth:
            self._header_label_text.append(data)
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
            provider_label = _normalize_opaque_text(" ".join(self._related_link_text))
            kind = self._related_explicit_kind or _RELATED_KINDS.get(
                provider_label.casefold().replace(" ", "-")
            )
            if kind:
                self.related.append(RelatedArtifactObservation(
                    kind,
                    urllib.parse.urljoin(self.page_url, self._related_href),
                    "explicitly_related_to_transcript",
                    self.page_url,
                    provider_label,
                ))
            self._related_href = None
            self._related_link_text = []
            self._related_explicit_kind = None
        if (
            tag.casefold() == "h1"
            and self._header_label_depth == self._artifact_header_depth
        ):
            self._observe_metadata(
                "document_title", " ".join(self._header_label_text)
            )
            self._header_label_depth = 0
            self._header_label_text = []
        if (
            tag.casefold() == "p"
            and self._header_date_depth == self._artifact_header_depth
        ):
            self._observe_metadata(
                "event_date", " ".join(self._header_date_text)
            )
            self._header_date_depth = 0
            self._header_date_text = []
        if self._related_depth:
            self._related_depth -= 1
        if self._artifact_header_depth:
            self._artifact_header_depth -= 1
        if not self._transcript_depth:
            return
        if self._excluded_depth:
            self._excluded_depth -= 1
        else:
            if self._turn is not None and self._live_speaker_depth:
                if self._transcript_depth == self._live_speaker_depth:
                    self._turn.speaker = _normalize_opaque_text(" ".join(self._live_text))
                    self._live_speaker_depth = 0
                    self._live_text = []
            if self._turn is not None and self._live_role_depth:
                if self._transcript_depth == self._live_role_depth:
                    self._turn.role = _normalize_opaque_text(" ".join(self._live_text)) or None
                    self._live_role_depth = 0
                    self._live_text = []
            if tag.casefold() == "p" and self._paragraph_depth:
                text = _normalize_opaque_text(" ".join(self._text))
                if text:
                    self.paragraphs.append(text)
                    if self._turn is not None:
                        self._turn.paragraphs.append(text)
                self._paragraph_depth = 0
                self._text = []
            if self._heading == tag.casefold():
                text = _normalize_opaque_text(" ".join(self._text))
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
                    proposal_rank,
                    resolved,
                    exact_identifier,
                    normalized_identifier,
                    target,
                    TranscriptMetadataObservation(
                        entry.label,
                        None,
                        entry.event_disposition,
                        entry.related,
                    ),
                )
                for proposal_rank, entry in enumerate(admitted_entries, start=1)
            )
            diagnostics = self._diagnostics(
                seed, requested, response.url, len(candidates), "archive"
            )
            diagnostics.update({
                "candidate_discovered_count": len(parser.entries),
                "candidate_excluded_count": 0,
                "candidate_admitted_count": len(candidates),
                "candidate_bound_exhausted": len(parser.entries) > candidate_limit,
                "candidate_budget": candidate_limit,
                "event_disposition_counts": {
                    disposition.value: sum(
                        entry.event_disposition is disposition
                        for entry in parser.entries
                    )
                    for disposition in TranscriptEventDisposition
                },
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
            requested,
            seed.value,
            "",
            1,
            1,
            requested,
            configured_identifier,
            ticker,
            target,
            TranscriptMetadataObservation(
                "", None, TranscriptEventDisposition.UNKNOWN
            ),
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
        normalized_text = "\n".join(
            paragraph
            for turn in turns
            for paragraph in turn.paragraphs
        )
        if not is_substantial_transcript(
            turns=turns,
            normalized_text=normalized_text,
        ):
            raise self._failure(
                "StockAnalysis artifact lacks substantial parsed transcript structure",
                False,
                "provider_transcript_structure_insufficient",
            )
        related = tuple(dict.fromkeys(
            (item.artifact_kind, item.observed_url, item.relationship_kind,
             item.source_provenance, item.provider_label) for item in parser.related
        ))
        related_observations = tuple(
            RelatedArtifactObservation(*item) for item in related[:16]
        )
        # StockAnalysis exposes no fixture-proven, artifact-local document-type
        # classification field. Relationship observations and opaque labels are
        # deliberately not authority for the transcript's event disposition.
        event_disposition = TranscriptEventDisposition.UNKNOWN
        event_label = parser.metadata.get("document_title", "")
        metadata_observation = TranscriptMetadataObservation(
            event_label,
            event_date,
            event_disposition,
            related_observations,
            turns,
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
        retained = ("\n".join((*metadata_lines, "", normalized_text)).rstrip() + "\n").encode()
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
            "event_disposition": event_disposition.value,
            "speaker_turn_count": len(turns),
            "content_turn_count": sum(bool(turn.paragraphs) for turn in turns),
            "transcript_word_count": word_count(normalized_text),
            "distinct_speaker_label_count": distinct_speaker_label_count(turns),
            "substantial_transcript": True,
            "speaker_turn_content_sha256": hashlib.sha256(turn_payload).hexdigest(),
            "related_artifact_count": len(related_observations),
            "related_artifact_kinds": [
                item.artifact_kind for item in related_observations
            ],
            "related_artifact_samples": [
                {
                    "artifact_kind": item.artifact_kind,
                    "observed_url": item.observed_url[:512],
                    "provider_label": item.provider_label[:128],
                }
                for item in related_observations[:8]
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
            transcript_metadata_observation=metadata_observation,
        )

    def _candidate(
        self, normalized: str, observed: str, label: str, archive_position: int,
        proposal_rank: int, parent: str, exact_identifier: str,
        normalized_identifier: str, target: object,
        observation: TranscriptMetadataObservation,
    ) -> AdapterCandidate:
        digest = hashlib.sha256(normalized.encode()).hexdigest()
        return AdapterCandidate(
            f"candidate-{digest}",
            f"document-{digest}",
            1,
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
                    "proposal_rank": proposal_rank,
                    "archive_position": archive_position,
                    "event_disposition": observation.event_disposition.value,
                    "trusted_event_date_available": False,
                    "deterministic_selection_rank": [proposal_rank, 0, 0, 0],
                },
            ),
            target,  # type: ignore[arg-type]
            transcript_metadata_observation=observation,
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
