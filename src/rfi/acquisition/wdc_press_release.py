"""Western Digital press releases from the deterministic Business Wire surface."""

from __future__ import annotations

import hashlib
import json
import re
import socket
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from html.parser import HTMLParser
from typing import Callable, Protocol

from rfi.acquisition.contracts import (
    ContractError,
    DiscoveryProvenance,
    JsonValue,
    PressReleaseAcquisitionSelection,
    PressReleaseAcquisitionTarget,
    PressReleaseSelectionMode,
    RetrievalResult,
    SourceProfile,
)
from rfi.acquisition.engine import (
    AdapterAcquisitionTrial,
    AdapterCandidate,
    AdapterFailure,
    AdapterSelectionCandidate,
    AdapterSelectionDecision,
    DiscoveryPage,
    FailureClass,
)
from rfi.storage.sqlite import utc_now

ADAPTER_ID = "wdc_press_release"
PROVIDER = "businesswire"
HOST = "www.businesswire.com"
SEARCH_URL = (
    "https://www.businesswire.com/newsroom?"
    "keywords=ENTIRE_RELEASE%3Atrue%3Awdc"
)
_RELEASE_PATH = re.compile(
    r"^/news/home/(?P<release_id>\d{14})/en/(?P<slug>[^/?#]+)$"
)
_WDC_ISSUER = "Western Digital Corporation"
_WDC_PUBLISHER_LABELS = frozenset({_WDC_ISSUER, "Western Digital"})
_WDC_TICKER = "NASDAQ:WDC"
_WDC_LISTING = re.compile(
    r"\)--\s*Western Digital Corporation\s*\(Nasdaq:\s*WDC\)", re.I
)
_MAX_RESPONSE_BYTES = 25_000_000
_MAX_PAGES = 50
_VOID_TAGS = frozenset({
    "area", "base", "br", "col", "embed", "hr", "img", "input", "link",
    "meta", "param", "source", "track", "wbr",
})


@dataclass(frozen=True)
class PressReleaseHttpResponse:
    """Exact bounded HTTP response at the adapter transport seam."""

    url: str
    status: int
    media_type: str
    content: bytes


class PressReleaseTransport(Protocol):
    def get(self, url: str) -> PressReleaseHttpResponse: ...


class UrllibPressReleaseTransport:
    """Deterministic direct HTTP transport; browser state is never consulted."""

    def __init__(
        self, timeout_seconds: float = 30.0, maximum_bytes: int = _MAX_RESPONSE_BYTES
    ) -> None:
        self.timeout_seconds = timeout_seconds
        self.maximum_bytes = maximum_bytes

    def get(self, url: str) -> PressReleaseHttpResponse:
        request = urllib.request.Request(
            url,
            headers={
                "User-Agent": "RFI-1 WDC press release acquisition",
                "Accept": "text/html,application/xhtml+xml;q=0.9,*/*;q=0.1",
                "Accept-Encoding": "identity",
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
                content = response.read(self.maximum_bytes + 1)
                if len(content) > self.maximum_bytes:
                    raise AdapterFailure(
                        FailureClass.PERMANENT_RETRIEVAL,
                        "Business Wire response exceeded the configured byte limit.",
                        False,
                        "response_too_large",
                    )
                return PressReleaseHttpResponse(
                    response.geturl(),
                    int(getattr(response, "status", 200)),
                    response.headers.get_content_type(),
                    content,
                )
        except AdapterFailure:
            raise
        except urllib.error.HTTPError as error:
            retryable = error.code >= 500 or error.code == 429
            raise AdapterFailure(
                FailureClass.TRANSIENT_ADAPTER if retryable
                else FailureClass.PERMANENT_RETRIEVAL,
                f"Business Wire returned HTTP {error.code}.",
                retryable,
                "businesswire_http_error",
            ) from error
        except (urllib.error.URLError, TimeoutError, socket.timeout) as error:
            raise AdapterFailure(
                FailureClass.TRANSIENT_ADAPTER,
                "Business Wire could not be reached by deterministic HTTP.",
                True,
                "businesswire_transport_failure",
            ) from error


@dataclass(frozen=True)
class _ListingEntry:
    url: str
    release_id: str
    title: str
    snippet: str

    @property
    def advisory_date(self) -> date:
        return date.fromisoformat(
            f"{self.release_id[:4]}-{self.release_id[4:6]}-{self.release_id[6:8]}"
        )


@dataclass
class _ListingBuilder:
    href: str
    release_id: str
    title: list[str] = field(default_factory=list)
    snippet: list[str] = field(default_factory=list)
    depth: int = 0


class _ListingParser(HTMLParser):
    """Parse the server-rendered newsroom cards and pagination controls."""

    def __init__(self, page_url: str) -> None:
        super().__init__(convert_charrefs=True)
        self.page_url = page_url
        self.entries: list[_ListingEntry] = []
        self._seen: set[str] = set()
        self._builder: _ListingBuilder | None = None
        self._in_title = 0
        self._in_snippet = 0
        self._snippet_parts: list[str] = []
        self._button_depth = 0
        self._button_text: list[str] = []
        self.page_numbers: set[int] = set()
        self.has_next = False
        self.duplicate_count = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = dict(attrs)
        classes = values.get("class") or ""
        is_container = tag.casefold() not in _VOID_TAGS
        if self._in_snippet and is_container:
            self._in_snippet += 1
        elif "rich-text" in classes.split():
            self._in_snippet = 1
            self._snippet_parts = []
        if self._builder is not None and is_container:
            self._builder.depth += 1
        if tag.casefold() == "a" and self._builder is None:
            href = values.get("href") or ""
            path = urllib.parse.urlsplit(urllib.parse.urljoin(self.page_url, href)).path
            match = _RELEASE_PATH.fullmatch(path)
            if match:
                self._builder = _ListingBuilder(href, match.group("release_id"), depth=1)
        if self._builder is not None:
            if tag.casefold() == "h2":
                self._in_title = self._builder.depth
        if tag.casefold() == "button":
            self._button_depth = 1
            self._button_text = []
        elif self._button_depth and is_container:
            self._button_depth += 1

    def handle_data(self, data: str) -> None:
        if self._builder is not None:
            if self._in_title:
                self._builder.title.append(data)
        if self._in_snippet:
            self._snippet_parts.append(data)
        if self._button_depth:
            self._button_text.append(data)

    def handle_endtag(self, tag: str) -> None:
        if self._button_depth:
            self._button_depth -= 1
            if not self._button_depth:
                text = _text(self._button_text)
                if text == "Next":
                    self.has_next = True
                if text.isdigit():
                    self.page_numbers.add(int(text))
        if self._in_snippet:
            self._in_snippet -= 1
            if not self._in_snippet and self.entries:
                previous = self.entries[-1]
                self.entries[-1] = _ListingEntry(
                    previous.url,
                    previous.release_id,
                    previous.title,
                    _text(self._snippet_parts),
                )
        if self._builder is None:
            return
        if self._in_title == self._builder.depth:
            self._in_title = 0
        self._builder.depth -= 1
        if self._builder.depth:
            return
        builder = self._builder
        self._builder = None
        canonical = canonical_release_url(urllib.parse.urljoin(self.page_url, builder.href))
        if canonical in self._seen:
            self.duplicate_count += 1
            return
        title = _text(builder.title)
        if not title:
            return
        self._seen.add(canonical)
        self.entries.append(
            _ListingEntry(canonical, builder.release_id, title, _text(builder.snippet))
        )


@dataclass(frozen=True)
class ParsedPressRelease:
    title: str
    publication_timestamp: str
    issuer: str
    ticker: str
    canonical_url: str
    release_id: str
    dateline: str
    summary: str
    body: str
    contacts: str
    attachments: tuple[dict[str, str], ...]
    source_attribution: str

    @property
    def publication_datetime(self) -> datetime:
        return datetime.fromisoformat(self.publication_timestamp.replace("Z", "+00:00"))

    def normalized(self, discovery_url: str, retrieved_at: str) -> dict[str, JsonValue]:
        return {
            "title": self.title,
            "publication_timestamp": self.publication_timestamp,
            "issuer": self.issuer,
            "ticker": self.ticker,
            "canonical_url": self.canonical_url,
            "businesswire_release_id": self.release_id,
            "dateline": self.dateline,
            "summary_highlights": self.summary,
            "complete_release_body": self.body,
            "contacts": self.contacts,
            "attachments": [dict(item) for item in self.attachments],
            "source_attribution": self.source_attribution,
            "discovery_url": discovery_url,
            "retrieval_timestamp": retrieved_at,
        }


class _ReleaseParser(HTMLParser):
    """Extract fixture-covered Business Wire release fields without executing scripts."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.json_ld: list[str] = []
        self.canonical_meta = ""
        self.title_parts: list[str] = []
        self.summary_parts: list[str] = []
        self.body_parts: list[str] = []
        self.contact_parts: list[str] = []
        self.sidebar_parts: list[str] = []
        self.attachments: list[dict[str, str]] = []
        self._json_depth = 0
        self._title_depth = 0
        self._summary_depth = 0
        self._body_depth = 0
        self._contact_depth = 0
        self._sidebar_depth = 0
        self._excluded_depth = 0
        self._link_href: str | None = None
        self._link_text: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = dict(attrs)
        classes = set((values.get("class") or "").split())
        is_container = tag.casefold() not in _VOID_TAGS
        if tag.casefold() == "script" and values.get("type") == "application/ld+json":
            self._json_depth = 1
        elif self._json_depth and is_container:
            self._json_depth += 1
        for attr, marker in (
            ("_title_depth", "ui-kit-press-release__headline"),
            ("_summary_depth", "ui-kit-press-release__subhead"),
            ("_sidebar_depth", "ui-kit-press-release__sidebar"),
        ):
            depth = getattr(self, attr)
            if depth and is_container:
                setattr(self, attr, depth + 1)
            elif marker in classes:
                setattr(self, attr, 1)
        if self._body_depth and is_container:
            self._body_depth += 1
        elif values.get("id") == "bw-release-story":
            self._body_depth = 1
        if self._contact_depth and is_container:
            self._contact_depth += 1
        elif values.get("id") == "bw-release-contact-1":
            self._contact_depth = 1
        if self._excluded_depth and is_container:
            self._excluded_depth += 1
        elif (self._body_depth or self._summary_depth) and tag.casefold() in {"style", "script"}:
            self._excluded_depth = 1
        if tag.casefold() == "meta" and values.get("property") == "og:url":
            self.canonical_meta = values.get("content") or ""
        if self._body_depth and not self._excluded_depth and tag.casefold() == "a":
            self._link_href = values.get("href")
            self._link_text = []

    def handle_data(self, data: str) -> None:
        if self._json_depth:
            self.json_ld.append(data)
        if self._excluded_depth:
            return
        if self._title_depth:
            self.title_parts.append(data)
        if self._summary_depth:
            self.summary_parts.append(data)
        if self._body_depth:
            self.body_parts.append(data)
        if self._contact_depth:
            self.contact_parts.append(data)
        if self._sidebar_depth:
            self.sidebar_parts.append(data)
        if self._link_href is not None:
            self._link_text.append(data)

    def handle_endtag(self, tag: str) -> None:
        if self._link_href is not None and tag.casefold() == "a":
            href = self._link_href
            parsed = urllib.parse.urlsplit(href)
            if parsed.hostname == "mms.businesswire.com" or re.search(
                r"\.(?:pdf|docx?|xlsx?|pptx?|zip)(?:$|\?)", parsed.path, re.I
            ):
                self.attachments.append({"url": href, "label": _text(self._link_text)})
            self._link_href = None
            self._link_text = []
        if self._excluded_depth:
            self._excluded_depth -= 1
        for attr in (
            "_json_depth", "_title_depth", "_summary_depth", "_body_depth",
            "_contact_depth", "_sidebar_depth",
        ):
            depth = getattr(self, attr)
            if depth:
                setattr(self, attr, depth - 1)


def _text(parts: list[str]) -> str:
    return " ".join(" ".join(parts).split())


def canonical_release_url(url: str) -> str:
    parsed = urllib.parse.urlsplit(url)
    if parsed.scheme != "https" or (parsed.hostname or "").casefold() != HOST:
        raise ValueError("Business Wire release URL is outside the configured host")
    match = _RELEASE_PATH.fullmatch(parsed.path.rstrip("/"))
    if match is None:
        raise ValueError("Business Wire release URL has an unsupported path")
    return urllib.parse.urlunsplit(("https", HOST, parsed.path.rstrip("/"), "", ""))


def parse_press_release(content: bytes, requested_url: str) -> ParsedPressRelease:
    try:
        text = content.decode("utf-8")
    except UnicodeDecodeError as error:
        raise ValueError("Business Wire release is not UTF-8") from error
    parser = _ReleaseParser()
    parser.feed(text)
    article: dict[str, object] | None = None
    for raw in parser.json_ld:
        try:
            value = json.loads(raw)
        except json.JSONDecodeError:
            continue
        values = value if isinstance(value, list) else [value]
        for item in values:
            if isinstance(item, dict) and item.get("@type") == "NewsArticle":
                article = item
                break
    if article is None:
        raise ValueError("Business Wire release lacks NewsArticle metadata")
    author = article.get("author")
    issuer = author.get("name") if isinstance(author, dict) else None
    timestamp = article.get("datePublished")
    canonical = parser.canonical_meta or requested_url
    canonical = canonical_release_url(canonical)
    release_match = _RELEASE_PATH.fullmatch(urllib.parse.urlsplit(canonical).path)
    assert release_match is not None
    release_id = release_match.group("release_id")
    sidebar = _text(parser.sidebar_parts)
    publisher_match = re.match(
        r"^(?P<issuer>.+?)\s+(?:NASDAQ|Nasdaq)\s*:\s*(?P<symbol>[A-Z]+)\b",
        sidebar,
    )
    publisher_issuer = publisher_match.group("issuer") if publisher_match else ""
    ticker = (
        f"NASDAQ:{publisher_match.group('symbol')}" if publisher_match else ""
    )
    title = _text(parser.title_parts)
    body = _text(parser.body_parts)
    if not isinstance(timestamp, str) or not timestamp or not title or not body:
        raise ValueError("Business Wire release lacks required timestamp, title, or body")
    try:
        parsed_timestamp = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
    except ValueError as error:
        raise ValueError("Business Wire publication timestamp is malformed") from error
    if parsed_timestamp.tzinfo is None:
        raise ValueError("Business Wire publication timestamp lacks a timezone")
    marker = re.search(r"--\(\s*BUSINESS WIRE\s*\)--", body, re.I)
    dateline = body[: marker.start()].strip() if marker else ""
    return ParsedPressRelease(
        title,
        parsed_timestamp.astimezone(UTC).isoformat(),
        publisher_issuer or (issuer if isinstance(issuer, str) else ""),
        ticker,
        canonical,
        release_id,
        dateline,
        _text(parser.summary_parts),
        body,
        _text(parser.contact_parts),
        tuple(parser.attachments),
        "Business Wire",
    )


class WdcPressReleaseSelectionPolicy:
    """Strict publisher qualification and deterministic terminal reduction."""

    def __init__(self, selection: PressReleaseAcquisitionSelection) -> None:
        self.selection = selection

    def qualify(
        self, candidate: AdapterCandidate, retrieval: RetrievalResult
    ) -> AdapterSelectionDecision:
        normalized = retrieval.diagnostics.get("normalized_press_release")
        if not isinstance(normalized, dict):
            raise ContractError("press-release retrieval lacks normalized metadata")
        issuer = normalized.get("issuer")
        ticker = normalized.get("ticker")
        publication = retrieval.trusted_event_date
        exact_publisher = issuer in _WDC_PUBLISHER_LABELS and ticker == _WDC_TICKER
        in_range = publication is not None and self.selection.contains(publication)
        timestamp = normalized.get("publication_timestamp")
        if not isinstance(timestamp, str):
            raise ContractError("press-release publication timestamp is unavailable")
        position = int(datetime.fromisoformat(timestamp).timestamp())
        outcome = (
            "qualified" if exact_publisher and in_range else
            "issuer_mismatch" if not exact_publisher else
            "selection_date_mismatch"
        )
        return AdapterSelectionDecision(
            exact_publisher and in_range,
            "qualified" if exact_publisher and in_range else "validation_rejected",
            outcome,
            {
                "validated_position": position,
                "publication_timestamp": timestamp,
                "businesswire_release_id": str(normalized.get("businesswire_release_id", "")),
                "issuer": str(issuer or ""),
                "ticker": str(ticker or ""),
            },
        )

    def select(
        self, candidates: tuple[AdapterSelectionCandidate, ...]
    ) -> AdapterSelectionCandidate:
        def key(item: AdapterSelectionCandidate) -> tuple[str, str, str]:
            diagnostics = item.decision.diagnostics
            return (
                str(diagnostics["publication_timestamp"]),
                str(diagnostics["businesswire_release_id"]),
                item.candidate.candidate_id,
            )

        return (
            max(candidates, key=key)
            if self.selection.mode == PressReleaseSelectionMode.LATEST
            else min(candidates, key=key)
        )

    def attribution(self) -> dict[str, JsonValue]:
        return {
            "effective_selection_mode": self.selection.mode.value,
            "qualification_rule": (
                "Business Wire publisher panel issuer in {Western Digital, Western "
                "Digital Corporation} and ticker == NASDAQ:WDC"
            ),
        }


class WdcBusinessWirePressReleaseAdapter:
    """Configured WDC-only adapter over Business Wire's HTTP-accessible pages."""

    adapter_id = ADAPTER_ID
    mechanism = ADAPTER_ID
    artifact_ids = ("press_release",)
    retrieval_modes = ("discovery",)

    def __init__(
        self,
        transport: PressReleaseTransport | None = None,
        clock: Callable[[], str] = utc_now,
        selection: PressReleaseAcquisitionSelection | None = None,
    ) -> None:
        self._transport = transport or UrllibPressReleaseTransport()
        self._clock = clock
        self._selection = selection or PressReleaseAcquisitionSelection.latest()

    def with_selection(
        self, selection: PressReleaseAcquisitionSelection
    ) -> WdcBusinessWirePressReleaseAdapter:
        return WdcBusinessWirePressReleaseAdapter(self._transport, self._clock, selection)

    def acquisition_trials(
        self, profile: SourceProfile
    ) -> tuple[AdapterAcquisitionTrial, ...]:
        self._validate_profile(profile)
        target = PressReleaseAcquisitionTarget(
            str(profile.policy["firm_id"]), selection=self._selection
        )
        return (
            AdapterAcquisitionTrial(
                "wdc-press-release-trial-1",
                str(profile.configuration["discovery_hint_value"]),
                "configured_search_url",
                target,
                provider=PROVIDER,
                continue_candidate_failures=True,
            ),
        )

    def discover(self, profile: SourceProfile, continuation: str | None) -> DiscoveryPage:
        if continuation is not None:
            raise ContractError("wdc_press_release uses one bounded acquisition trial")
        return self.discover_trial(profile, self.acquisition_trials(profile)[0])

    def discover_trial(
        self, profile: SourceProfile, trial: AdapterAcquisitionTrial
    ) -> DiscoveryPage:
        self._validate_profile(profile)
        if trial.acquisition_target.to_dict() != PressReleaseAcquisitionTarget(
            "western-digital", selection=self._selection
        ).to_dict():
            raise ContractError("WDC press-release acquisition target changed")
        configured = str(profile.configuration["discovery_hint_value"])
        page_number = 1
        all_entries: list[tuple[int, _ListingEntry, str]] = []
        seen_urls: set[str] = set()
        seen_page_urls: set[str] = set()
        seen_page_signatures: set[tuple[str, ...]] = set()
        pages = 0
        duplicates = 0
        stop_reason = "pagination_exhausted"
        while page_number <= int(profile.configuration.get("maximum_pages", _MAX_PAGES)):
            page_url = self._page_url(configured, page_number)
            if page_url in seen_page_urls:
                raise AdapterFailure(
                    FailureClass.MALFORMED_ADAPTER,
                    "Business Wire pagination loop was detected.",
                    False,
                    "pagination_loop",
                )
            seen_page_urls.add(page_url)
            response = self._get(page_url, "discovery")
            parser = _ListingParser(page_url)
            try:
                parser.feed(response.content.decode("utf-8"))
            except (UnicodeDecodeError, ValueError) as error:
                raise AdapterFailure(
                    FailureClass.MALFORMED_ADAPTER,
                    "Business Wire discovery page is malformed.",
                    False,
                    "malformed_discovery_page",
                ) from error
            if not parser.entries:
                raise AdapterFailure(
                    FailureClass.MALFORMED_ADAPTER,
                    "Business Wire discovery returned no recognizable release cards.",
                    False,
                    "unsupported_discovery_page",
                )
            signature = tuple(entry.release_id for entry in parser.entries)
            if signature in seen_page_signatures:
                raise AdapterFailure(
                    FailureClass.MALFORMED_ADAPTER,
                    "Business Wire pagination repeated an earlier result page.",
                    False,
                    "pagination_loop",
                )
            seen_page_signatures.add(signature)
            pages += 1
            duplicates += parser.duplicate_count
            for entry in parser.entries:
                if entry.url in seen_urls:
                    duplicates += 1
                    continue
                seen_urls.add(entry.url)
                all_entries.append((len(all_entries) + 1, entry, page_url))
            dates = [entry.advisory_date for entry in parser.entries]
            if self._selection.mode == PressReleaseSelectionMode.LATEST and any(
                _WDC_LISTING.search(entry.snippet) for entry in parser.entries
            ):
                stop_reason = "publisher_candidate_observed"
                break
            if (
                self._selection.mode == PressReleaseSelectionMode.FIRST_IN_DATE_RANGE
                and self._selection.start_date is not None
                and min(dates) < self._selection.start_date
            ):
                stop_reason = "inclusive_start_boundary_crossed"
                break
            if not parser.has_next:
                break
            page_number += 1
        else:
            raise AdapterFailure(
                FailureClass.TRANSIENT_ADAPTER,
                "Business Wire discovery exceeded its configured page bound.",
                True,
                "maximum_pages_exhausted",
            )
        candidates = []
        discovered_at = self._clock()
        for position, entry, discovery_url in all_entries:
            digest = hashlib.sha256(entry.release_id.encode()).hexdigest()
            candidates.append(
                AdapterCandidate(
                    f"candidate-{digest}",
                    f"document-wdc-press-release-{entry.release_id}",
                    position,
                    f"release-{entry.release_id}",
                    DiscoveryProvenance(
                        discovered_at,
                        self.mechanism,
                        {"provider": PROVIDER, "release_id": entry.release_id},
                        (discovery_url, entry.url),
                        {
                            "firm_id": "western-digital",
                            "canonical_artifact_id": "press_release",
                            "provider": PROVIDER,
                            "configured_source": configured,
                            "requested_url": entry.url,
                            "resolved_url": entry.url,
                            "link_label": entry.title,
                            "listing_snippet": entry.snippet,
                            "discovery_url": discovery_url,
                            "deferred_candidate_evaluation": True,
                            "proposal_rank": position,
                            "acquisition_target": trial.acquisition_target.to_dict(),
                        },
                    ),
                    trial.acquisition_target,
                )
            )
        return DiscoveryPage(
            tuple(candidates),
            None,
            {
                "adapter_id": self.adapter_id,
                "provider": PROVIDER,
                "configured_search_url": configured,
                "pagination_mechanism": "preserve query and append page=N",
                "listing_pages_fetched": pages,
                "duplicate_release_urls_suppressed": duplicates,
                "discovery_stop_reason": stop_reason,
                "candidate_count": len(candidates),
                "effective_selection_mode": self._selection.mode.value,
            },
        )

    def terminal_selection_policy(
        self,
        profile: SourceProfile,
        trials: tuple[AdapterAcquisitionTrial, ...],
    ) -> WdcPressReleaseSelectionPolicy:
        self._validate_profile(profile)
        if len(trials) != 1 or trials[0].acquisition_target.selection != self._selection:
            raise ContractError("WDC press-release selection target changed")
        return WdcPressReleaseSelectionPolicy(self._selection)

    def retrieve(
        self, profile: SourceProfile, candidate: AdapterCandidate
    ) -> RetrievalResult:
        self._validate_profile(profile)
        requested = candidate.provenance.metadata.get("requested_url")
        discovery_url = candidate.provenance.metadata.get("discovery_url")
        if not isinstance(requested, str) or not isinstance(discovery_url, str):
            raise ContractError("WDC press-release candidate lacks retrieval provenance")
        response = self._get(requested, "detail")
        if response.media_type.casefold() not in {"text/html", "application/xhtml+xml"}:
            raise AdapterFailure(
                FailureClass.PERMANENT_RETRIEVAL,
                "Business Wire release has an unsupported media type.",
                False,
                "unsupported_detail_media_type",
            )
        try:
            parsed = parse_press_release(response.content, response.url)
        except ValueError as error:
            raise AdapterFailure(
                FailureClass.MALFORMED_ADAPTER,
                str(error),
                False,
                "malformed_detail_page",
            ) from error
        expected_id = candidate.provenance.provider_identifiers.get("release_id")
        if parsed.release_id != expected_id:
            raise AdapterFailure(
                FailureClass.MALFORMED_ADAPTER,
                "Business Wire detail release identity differs from discovery.",
                False,
                "release_identity_mismatch",
            )
        retrieved_at = self._clock()
        digest = hashlib.sha256(response.content).hexdigest()
        normalized = parsed.normalized(discovery_url, retrieved_at)
        return RetrievalResult(
            response.content,
            response.media_type,
            retrieved_at,
            self.mechanism,
            {"provider": PROVIDER, "release_id": parsed.release_id},
            {
                "final_url": parsed.canonical_url,
                "content_sha256": digest,
                "validated_content_sha256": digest,
                "validated_position": int(parsed.publication_datetime.timestamp()),
                "validated_revision": f"{parsed.release_id}-{digest}",
                "validated_event_date": parsed.publication_datetime.date().isoformat(),
                "trusted_event_date": parsed.publication_datetime.date().isoformat(),
                "trusted_event_date_available": True,
                "normalized_press_release": normalized,
            },
            trusted_event_date=parsed.publication_datetime.date(),
        )

    def _get(self, url: str, kind: str) -> PressReleaseHttpResponse:
        try:
            response = self._transport.get(url)
        except AdapterFailure:
            raise
        except Exception as error:
            raise AdapterFailure(
                FailureClass.TRANSIENT_ADAPTER,
                f"Business Wire {kind} retrieval failed.",
                True,
                f"{kind}_retrieval_failure",
            ) from error
        if response.status != 200 or not response.content:
            raise AdapterFailure(
                FailureClass.TRANSIENT_ADAPTER if response.status >= 500 else
                FailureClass.PERMANENT_RETRIEVAL,
                f"Business Wire {kind} response was unavailable.",
                response.status >= 500,
                f"{kind}_unavailable",
            )
        return response

    @staticmethod
    def _page_url(configured: str, page: int) -> str:
        parsed = urllib.parse.urlsplit(configured)
        query = urllib.parse.parse_qsl(parsed.query, keep_blank_values=True)
        query = [(key, value) for key, value in query if key != "page"]
        if page > 1:
            query.append(("page", str(page)))
        return urllib.parse.urlunsplit(
            (parsed.scheme, parsed.netloc, parsed.path, urllib.parse.urlencode(query), "")
        )

    def _validate_profile(self, profile: SourceProfile) -> None:
        if profile.mechanism != self.mechanism:
            raise ContractError("WDC press-release source mechanism is invalid")
        if profile.policy.get("firm_id") != "western-digital":
            raise ContractError("wdc_press_release only supports western-digital")
        if profile.policy.get("artifact_id") != "press_release":
            raise ContractError("wdc_press_release requires the press_release taxonomy")
        if profile.configuration.get("mode") != "discovery":
            raise ContractError("wdc_press_release requires discovery mode")
        if profile.configuration.get("provider") != ADAPTER_ID:
            raise ContractError("wdc_press_release requires its explicit provider")
        if profile.configuration.get("discovery_hint_kind") != "configured_search_url":
            raise ContractError("wdc_press_release requires a configured search URL")
        if profile.configuration.get("discovery_hint_value") != SEARCH_URL:
            raise ContractError("wdc_press_release search URL differs from firm authority")


__all__ = [
    "ADAPTER_ID",
    "PressReleaseHttpResponse",
    "PressReleaseTransport",
    "SEARCH_URL",
    "UrllibPressReleaseTransport",
    "WdcBusinessWirePressReleaseAdapter",
    "WdcPressReleaseSelectionPolicy",
    "canonical_release_url",
    "parse_press_release",
]
