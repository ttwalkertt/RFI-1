"""Repository-owned bounded discovery policies and transcript URL discovery."""

from __future__ import annotations

import json
import time
import urllib.parse
import urllib.request
from collections import deque
from dataclasses import dataclass
from datetime import date, timedelta
from html.parser import HTMLParser
from pathlib import Path
from typing import Callable, Protocol

from jsonschema import Draft202012Validator

from rfi.acquisition.earnings_transcripts import (
    EarningsCallTranscriptAcquisition,
    EarningsTranscriptHttpResponse,
    EarningsTranscriptTransport,
    UrllibEarningsTranscriptTransport,
)
from rfi.acquisition.contracts import (
    ContractError,
    IntervalAcquisitionRequest,
    RetrievalResult,
    SourceProfile,
)
from rfi.acquisition.engine import (
    AdapterCandidate,
    AdapterFailure,
    DiscoveryPage,
    FailureClass,
)
from rfi.storage.sqlite import utc_now


class DiscoveryPolicyError(RuntimeError):
    """Raised when the repository policy catalog or a class selection is invalid."""


@dataclass(frozen=True)
class DiscoveryPolicy:
    max_search_queries: int
    max_results_per_query: int
    max_links_per_page: int
    max_depth: int
    max_pages: int
    max_distinct_hosts: int
    max_bytes: int
    max_elapsed_seconds: int


DISCOVERY_BUDGET_FIELDS = frozenset(DiscoveryPolicy.__dataclass_fields__)


@dataclass(frozen=True)
class DiscoveryPolicyCatalog:
    classes: dict[str, DiscoveryPolicy]
    default_class: str

    def resolve(self, name: str | None) -> DiscoveryPolicy:
        selected = name or self.default_class
        try:
            return self.classes[selected]
        except KeyError as error:
            raise DiscoveryPolicyError(f"unknown discovery_class: {selected}") from error


def load_discovery_policies(
    path: Path = Path("config/discovery-policies.json"),
    schema_path: Path = Path("docs/discovery-policies-v1.schema.json"),
) -> DiscoveryPolicyCatalog:
    """Load and strictly validate the repository-owned named policy catalog."""
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise DiscoveryPolicyError(f"discovery policy configuration is unreadable: {error}")
    errors = sorted(Draft202012Validator(schema).iter_errors(value), key=str)
    if errors:
        raise DiscoveryPolicyError(
            "invalid discovery policy configuration: "
            + "; ".join(error.message for error in errors)
        )
    default = value["default_class"]
    if default not in value["classes"]:
        raise DiscoveryPolicyError(f"unknown default discovery class: {default}")
    return DiscoveryPolicyCatalog(
        {name: DiscoveryPolicy(**policy) for name, policy in sorted(value["classes"].items())},
        default,
    )


@dataclass(frozen=True)
class DiscoverySearchResponse:
    urls: tuple[str, ...]
    received_bytes: int


class DiscoverySearch(Protocol):
    endpoint: str

    def search(self, query: str, limit: int) -> DiscoverySearchResponse: ...


class DuckDuckGoHtmlSearch:
    """Bounded public HTML search used only to propose deterministically validated URLs."""

    endpoint = "https://html.duckduckgo.com/html/"

    def search(self, query: str, limit: int) -> DiscoverySearchResponse:
        request = urllib.request.Request(
            "https://html.duckduckgo.com/html/?" + urllib.parse.urlencode({"q": query}),
            headers={"User-Agent": "RFI-1 bounded source discovery"},
        )
        with urllib.request.urlopen(request, timeout=20) as response:
            content = response.read(2_000_000)
            parser = _SearchParser(limit + 1)
            parser.feed(content.decode("utf-8", "replace"))
        return DiscoverySearchResponse(tuple(parser.urls), len(content))


class _SearchParser(HTMLParser):
    def __init__(self, limit: int) -> None:
        super().__init__(convert_charrefs=True)
        self.limit = limit
        self.urls: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = dict(attrs)
        if tag.casefold() != "a" or "result__a" not in (values.get("class") or ""):
            return
        href = values.get("href") or ""
        parsed = urllib.parse.urlsplit(href)
        target = urllib.parse.parse_qs(parsed.query).get("uddg", [href])[0]
        if target.startswith(("http://", "https://")) and target not in self.urls:
            self.urls.append(target)
            del self.urls[self.limit :]


class _PageParser(HTMLParser):
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


@dataclass(frozen=True)
class TranscriptDiscoveryResult:
    listing_urls: tuple[str, ...]
    candidate_proposals: tuple[dict[str, str], ...]
    allowed_hosts: tuple[str, ...]
    exhausted: bool
    diagnostics: dict[str, int | bool | str]


class BudgetedTranscriptTransport(EarningsTranscriptTransport):
    """Enforce shared page, host, byte, and elapsed limits across discovery and validation."""

    def __init__(
        self,
        inner: EarningsTranscriptTransport,
        policy: DiscoveryPolicy,
        monotonic: Callable[[], float] = time.monotonic,
    ) -> None:
        self.inner = inner
        self.policy = policy
        self.monotonic = monotonic
        self.started = monotonic()
        self.pages = 0
        self.bytes = 0
        self.hosts: set[str] = set()
        self.exhausted = False
        self.exhausted_budget = ""

    def get(self, url: str) -> EarningsTranscriptHttpResponse:
        self.begin_request(url)
        response = self.inner.get(url)
        self.accept_response(len(response.content))
        return response

    def begin_request(self, url: str) -> None:
        host = (urllib.parse.urlsplit(url).hostname or "").casefold()
        if host not in self.hosts and len(self.hosts) >= self.policy.max_distinct_hosts:
            self.exhausted = True
            self.exhausted_budget = "max_distinct_hosts"
            raise ValueError("discovery distinct-host bound exhausted")
        if self.pages >= self.policy.max_pages:
            self.exhausted = True
            self.exhausted_budget = "max_pages"
            raise ValueError("discovery page bound exhausted")
        if self.monotonic() - self.started >= self.policy.max_elapsed_seconds:
            self.exhausted = True
            self.exhausted_budget = "max_elapsed_seconds"
            raise TimeoutError("discovery elapsed-time bound exhausted")
        self.pages += 1
        self.hosts.add(host)

    def accept_response(self, received_bytes: int) -> None:
        self.bytes += received_bytes
        if self.bytes > self.policy.max_bytes:
            self.exhausted = True
            self.exhausted_budget = "max_bytes"
            raise ValueError("discovery byte bound exhausted")


class BoundedTranscriptDiscovery:
    """Generate URL proposals from sparse firm identity and hints under one named policy."""

    def __init__(
        self,
        search: DiscoverySearch,
        transport: BudgetedTranscriptTransport,
        policy: DiscoveryPolicy,
    ) -> None:
        self.search = search
        self.transport = transport
        self.policy = policy

    def discover(
        self, identity_terms: tuple[str, ...], source_hints: tuple[str, ...]
    ) -> TranscriptDiscoveryResult:
        urls = [hint for hint in source_hints if hint.startswith(("http://", "https://"))]
        planned_queries = tuple(
            f'"{term}" earnings call transcript' for term in identity_terms[:2] if term.strip()
        )
        queries_submitted = 0
        exhausted = False
        exhausted_budget = ""
        failures: list[tuple[str, str]] = []
        search_endpoint = getattr(self.search, "endpoint", "https://search.invalid/")
        for query in planned_queries:
            if queries_submitted >= self.policy.max_search_queries:
                exhausted = True
                exhausted_budget = "max_search_queries"
                break
            if self.transport.monotonic() - self.transport.started >= (
                self.policy.max_elapsed_seconds
            ):
                exhausted = True
                exhausted_budget = "max_elapsed_seconds"
                break
            try:
                self.transport.begin_request(search_endpoint)
                queries_submitted += 1
                response = self.search.search(query, self.policy.max_results_per_query)
                self.transport.accept_response(response.received_bytes)
            except Exception as error:
                if self.transport.exhausted:
                    exhausted_budget = self.transport.exhausted_budget
                    exhausted = True
                    break
                failures.append(("search_failed", error.__class__.__name__))
                continue
            if self.transport.monotonic() - self.transport.started >= (
                self.policy.max_elapsed_seconds
            ):
                exhausted = True
                exhausted_budget = "max_elapsed_seconds"
                break
            if len(response.urls) > self.policy.max_results_per_query:
                exhausted = True
                exhausted_budget = "max_results_per_query"
            urls.extend(response.urls[: self.policy.max_results_per_query])
            if exhausted:
                break
        queue = deque() if exhausted else deque(
            (url, 0) for url in dict.fromkeys(urls)
        )
        visited: set[str] = set()
        listings: list[str] = []
        candidates: list[dict[str, str]] = []
        while queue:
            url, depth = queue.popleft()
            if url in visited:
                continue
            if EarningsCallTranscriptAcquisition._looks_like_transcript(url, url):
                candidates.append({"url": url, "label": url})
            try:
                response = self.transport.get(url)
            except Exception as error:
                if self.transport.exhausted:
                    exhausted = True
                    exhausted_budget = self.transport.exhausted_budget
                    break
                failures.append(("page_fetch_failed", error.__class__.__name__))
                continue
            visited.add(url)
            if response.media_type not in {"text/html", "application/xhtml+xml"}:
                if EarningsCallTranscriptAcquisition._looks_like_transcript("", response.url):
                    candidates.append({"url": response.url, "label": response.url})
                continue
            listings.append(response.url)
            parser = _PageParser()
            try:
                parser.feed(response.content.decode("utf-8", "replace"))
            except Exception as error:
                failures.append(("page_parse_failed", error.__class__.__name__))
                continue
            links = sorted(
                parser.links,
                key=lambda item: (
                    not EarningsCallTranscriptAcquisition._looks_like_transcript(
                        item[1], urllib.parse.urljoin(response.url, item[0])
                    ),
                    item[0],
                    item[1],
                ),
            )
            if len(links) > self.policy.max_links_per_page:
                exhausted = True
                exhausted_budget = "max_links_per_page"
            for href, label in links[: self.policy.max_links_per_page]:
                target = urllib.parse.urljoin(response.url, href)
                if EarningsCallTranscriptAcquisition._looks_like_transcript(label, target):
                    candidates.append({"url": target, "label": label or target})
                elif depth < self.policy.max_depth and target.startswith(("http://", "https://")):
                    queue.append((target, depth + 1))
                elif target.startswith(("http://", "https://")):
                    exhausted = True
                    exhausted_budget = "max_depth"
                    break
            if exhausted:
                break
            if self.transport.exhausted:
                exhausted = True
                exhausted_budget = self.transport.exhausted_budget
                break
        unique_candidates = tuple(
            dict((item["url"], item) for item in candidates).values()
        )
        if exhausted_budget and exhausted_budget not in DISCOVERY_BUDGET_FIELDS:
            raise RuntimeError("discovery reported an unknown exhausted budget")
        if exhausted != bool(exhausted_budget):
            raise RuntimeError("discovery exhaustion requires one named policy budget")
        return TranscriptDiscoveryResult(
            tuple(dict.fromkeys(listings)),
            unique_candidates,
            tuple(sorted(self.transport.hosts)),
            exhausted,
            {
                "search_queries": queries_submitted,
                "pages": self.transport.pages,
                "distinct_hosts": len(self.transport.hosts),
                "bytes": self.transport.bytes,
                "candidate_urls": len(unique_candidates),
                "bounds_exhausted": exhausted,
                "exhausted_budget": exhausted_budget,
                "discovery_failures": len(failures),
                "discovery_failure_codes": ",".join(code for code, _ in failures),
                "discovery_failure_types": ",".join(kind for _, kind in failures),
            },
        )


class EarningsTranscriptPullAdapter:
    """Discover transcript URLs, then delegate validation to the TASK-048 retriever."""

    adapter_id = "earnings-call-transcript"
    artifact_ids = ("earnings_transcript",)
    retrieval_modes = ("discovery",)
    mechanism = "earnings_transcript"

    def __init__(
        self,
        policies: DiscoveryPolicyCatalog,
        search: DiscoverySearch | None = None,
        transport: EarningsTranscriptTransport | None = None,
        clock: Callable[[], str] = utc_now,
        monotonic: Callable[[], float] = time.monotonic,
    ) -> None:
        self._policies = policies
        self._search = search or DuckDuckGoHtmlSearch()
        self._transport = transport or UrllibEarningsTranscriptTransport()
        self._clock = clock
        self._monotonic = monotonic
        self._retrievals: dict[str, RetrievalResult] = {}

    def discover(self, profile: SourceProfile, continuation: str | None) -> DiscoveryPage:
        if continuation is not None:
            raise AdapterFailure(
                FailureClass.MALFORMED_ADAPTER,
                "earnings transcript retrieval does not support continuation",
                False,
                "malformed_provider_response",
            )
        self._validate_profile(profile)
        configuration = profile.configuration
        try:
            policy = self._policies.resolve(
                str(configuration.get("discovery_class") or "") or None
            )
            budgeted = BudgetedTranscriptTransport(
                self._transport, policy, self._monotonic
            )
            mode = configuration.get("mode")
            identity_terms = tuple(
                value.removeprefix("identity:")
                for value in configuration.get("discovery_hints", ())
                if isinstance(value, str) and not value.startswith(("http://", "https://"))
            )
            source_hints = tuple(
                value for value in configuration.get("discovery_hints", ())
                if isinstance(value, str) and value.startswith(("http://", "https://"))
            )
            if mode == "discovery":
                discovered = BoundedTranscriptDiscovery(
                    self._search, budgeted, policy
                ).discover(identity_terms, source_hints)
            else:
                url = configuration.get("url")
                if not isinstance(url, str) or not url:
                    raise ContractError("URL-based transcript input requires url")
                host = urllib.parse.urlsplit(url).hostname or ""
                discovered = TranscriptDiscoveryResult(
                    (url,) if mode == "listing_page" else (),
                    () if mode == "listing_page" else ({"url": url, "label": url},),
                    (host.casefold(),), False,
                    {"search_queries": 0, "pages": 0, "distinct_hosts": 0,
                     "bytes": 0, "candidate_urls": int(mode == "direct_url"),
                     "bounds_exhausted": False, "exhausted_budget": ""},
                )
            listing_urls = discovered.listing_urls
            if not listing_urls and discovered.candidate_proposals:
                listing_urls = (discovered.candidate_proposals[0]["url"],)
            if not listing_urls:
                return DiscoveryPage((), None, {
                    "adapter_id": self.adapter_id,
                    "discovery_class": configuration.get("discovery_class"),
                    "coverage": "indeterminate",
                    **discovered.diagnostics,
                })
            governed = SourceProfile(
                profile.source_id, profile.name, profile.enabled, self.mechanism,
                {
                    "listing_urls": list(listing_urls[:8]),
                    "allowed_hosts": list(discovered.allowed_hosts),
                    "candidate_proposals": list(discovered.candidate_proposals),
                    "discover_listing_links": False,
                    "authoritative_listing": False,
                    "firm_identity_terms": list(identity_terms),
                },
                profile.policy,
            )
            today = date.fromisoformat(self._clock()[:10])
            interval = EarningsCallTranscriptAcquisition(
                governed, budgeted, self._clock
            ).acquire(IntervalAcquisitionRequest(
                str(profile.policy["firm_id"]), "earnings_transcript",
                date(2000, 1, 1), today + timedelta(days=1),
            ))
        except DiscoveryPolicyError as error:
            raise ContractError(str(error)) from error
        except Exception as error:
            raise AdapterFailure(
                FailureClass.TRANSIENT_ADAPTER,
                str(error) or error.__class__.__name__, True,
                "transcript_discovery_failed",
            ) from error
        candidates = []
        for envelope in interval.artifacts:
            candidate = AdapterCandidate(
                envelope.candidate.candidate_id, envelope.candidate.document_id,
                len(candidates) + 1, f"published-{envelope.artifact_date.isoformat()}",
                envelope.candidate.provenance,
            )
            self._retrievals[candidate.candidate_id] = envelope.retrieval
            candidates.append(candidate)
        coverage = "indeterminate" if discovered.exhausted else interval.coverage.value
        final_diagnostics = dict(discovered.diagnostics)
        final_diagnostics.update({
            "pages": budgeted.pages,
            "distinct_hosts": len(budgeted.hosts),
            "bytes": budgeted.bytes,
            "bounds_exhausted": discovered.exhausted or budgeted.exhausted,
            "exhausted_budget": budgeted.exhausted_budget
            or str(discovered.diagnostics.get("exhausted_budget", "")),
        })
        if budgeted.exhausted:
            coverage = "indeterminate"
        return DiscoveryPage(tuple(candidates), None, {
            "adapter_id": self.adapter_id,
            "discovery_class": configuration.get("discovery_class"),
            "coverage": coverage,
            "validation_failures": len(interval.failures),
            **final_diagnostics,
        })

    def retrieve(self, profile: SourceProfile, candidate: AdapterCandidate) -> RetrievalResult:
        self._validate_profile(profile)
        try:
            return self._retrievals.pop(candidate.candidate_id)
        except KeyError as error:
            raise AdapterFailure(
                FailureClass.MALFORMED_ADAPTER,
                "earnings transcript candidate was not produced by this discovery",
                False, "missing_transcript_candidate",
            ) from error

    def _validate_profile(self, profile: SourceProfile) -> None:
        if profile.mechanism != self.mechanism:
            raise ContractError("earnings transcript source mechanism is invalid")
        if profile.policy.get("artifact_id") != "earnings_transcript":
            raise ContractError("earnings transcript adapter requires canonical artifact")
        if profile.configuration.get("mode") not in self.retrieval_modes:
            raise ContractError("earnings transcript retrieval mode is unsupported")
