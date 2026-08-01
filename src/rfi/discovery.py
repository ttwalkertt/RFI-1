"""Repository-owned bounded discovery policies and transcript URL discovery."""

from __future__ import annotations

import json
import heapq
import re
import socket
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter
from dataclasses import dataclass, field
from datetime import date, timedelta
from enum import Enum
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Callable, Protocol

from jsonschema import Draft202012Validator

from rfi.acquisition.earnings_transcripts import (
    CandidateFailureCode,
    EarningsCallTranscriptAcquisition,
    EarningsTranscriptHttpResponse,
    EarningsTranscriptTransport,
    UrllibEarningsTranscriptTransport,
    normalize_transcript_url,
    transcript_request_headers,
)
from rfi.acquisition.contracts import (
    ContractError,
    IntervalAcquisitionRequest,
    RetrievalResult,
    SourceProfile,
)
from rfi.acquisition.repository import AcquisitionRepository
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
    max_candidate_evaluations: int = 40
    max_redirects: int = 10


DISCOVERY_BUDGET_FIELDS = frozenset(DiscoveryPolicy.__dataclass_fields__)


def redact_diagnostic_url(url: str) -> str:
    """Bounded diagnostics preserve shape while removing query-sensitive values."""
    try:
        parsed = urllib.parse.urlsplit(url)
        query = urllib.parse.parse_qsl(parsed.query, keep_blank_values=True)
        safe_query = urllib.parse.urlencode([(name, "REDACTED") for name, _ in query])
        host = (parsed.hostname or "").casefold()
        return urllib.parse.urlunsplit(
            (parsed.scheme.casefold(), host, parsed.path or "/", safe_query, "")
        )
    except (TypeError, ValueError):
        return "[invalid-url]"


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
            headers=transcript_request_headers("RFI-1 bounded source discovery"),
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
    diagnostics: dict[str, Any]


class DiscoveryFailureCode(str, Enum):
    SEARCH_TRANSPORT = "search_transport_failure"
    PAGE_PARSE = "page_parse_failure"
    HINT_FETCH_TIMEOUT = "hint_fetch_timeout"
    HINT_HTTP = "hint_http_failure"
    HINT_REDIRECT = "hint_redirect_rejected"
    HINT_TRANSPORT = "hint_transport_failure"
    CANDIDATE_FETCH_TIMEOUT = "candidate_fetch_timeout"
    CANDIDATE_HTTP = "candidate_http_failure"
    CANDIDATE_TRANSPORT = "candidate_transport_failure"
    REDIRECT_CYCLE = "redirect_cycle"


@dataclass(frozen=True)
class RankedCandidateProposal:
    """One graph proposal with its complete deterministic ordering contract."""

    phase_priority: int
    rank: tuple[object, ...]
    serial: int
    observed_url: str
    label: str
    normalized_url: str
    reasons: tuple[str, ...]
    depth: int

    def sort_key(self) -> tuple[object, ...]:
        return (
            self.phase_priority, self.rank, self.serial, self.observed_url, self.label,
            self.normalized_url, self.reasons, self.depth,
        )


@dataclass(frozen=True)
class DiscoveryFailureRecord:
    code: DiscoveryFailureCode
    legacy_code: str
    error_type: str
    url: str
    http_status: int | None = None


@dataclass(frozen=True)
class RejectedLinkRecord:
    reason: str
    url: str


@dataclass(frozen=True)
class RankingAdmissionRecord:
    url: str
    reasons: tuple[str, ...]
    candidate: bool
    depth: int


@dataclass
class GraphTraversalState:
    """Mutable graph state; diagnostics are projections of its transitions."""

    queued: set[str] = field(default_factory=set)
    visited: set[str] = field(default_factory=set)
    proposed: set[str] = field(default_factory=set)
    listings: list[str] = field(default_factory=list)
    candidate_proposals: list[RankedCandidateProposal] = field(default_factory=list)
    raw_hyperlinks: int = 0
    normalized_unique_hyperlinks: int = 0
    eligible_hyperlinks: int = 0
    traversed_hyperlinks: int = 0
    queue_admitted: int = 0
    rejection_counts: Counter[str] = field(default_factory=Counter)
    cycle_counts: Counter[str] = field(default_factory=Counter)
    failures: list[DiscoveryFailureRecord] = field(default_factory=list)
    rejected_samples: list[RejectedLinkRecord] = field(default_factory=list)
    ranking_samples: list[RankingAdmissionRecord] = field(default_factory=list)
    anchor_attempts: list[dict[str, object]] = field(default_factory=list)
    configured_hint_attempt_sequence: list[dict[str, str]] = field(default_factory=list)
    stage_sequence: list[str] = field(default_factory=list)

    def reject(self, reason: str, url: str, cycle: str, sample_limit: int) -> None:
        self.rejection_counts[reason] += 1
        if cycle:
            self.cycle_counts[cycle] += 1
        if len(self.rejected_samples) < sample_limit:
            self.rejected_samples.append(RejectedLinkRecord(reason, redact_diagnostic_url(url)))

    def record_failure(
        self, code: DiscoveryFailureCode, url: str, error: Exception | None,
        status: int,
    ) -> None:
        legacy_code = (
            "search_failed" if code is DiscoveryFailureCode.SEARCH_TRANSPORT
            else "page_parse_failed" if code is DiscoveryFailureCode.PAGE_PARSE
            else "page_fetch_failed"
        )
        self.failures.append(DiscoveryFailureRecord(
            code, legacy_code, error.__class__.__name__ if error else code.value,
            redact_diagnostic_url(url), status or None,
        ))

    def admit_candidate(
        self, proposal: RankedCandidateProposal, *, queue_admission: bool = True
    ) -> None:
        self.candidate_proposals.append(proposal)
        self.proposed.add(proposal.normalized_url)
        if queue_admission:
            self.queue_admitted += 1


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
        self.redirects = 0
        self.exhausted = False
        self.exhausted_budget = ""

    def get(self, url: str) -> EarningsTranscriptHttpResponse:
        self.begin_request(url)
        response = self.inner.get(url)
        redirect_chain = tuple(getattr(response, "redirects", ()))
        redirect_count = len(redirect_chain)
        if (
            not redirect_count
            and normalize_transcript_url(response.url) != normalize_transcript_url(url)
        ):
            redirect_count = 1
        self.redirects += redirect_count
        if self.redirects > self.policy.max_redirects:
            self.exhausted = True
            self.exhausted_budget = "max_redirects"
            raise ValueError("discovery redirect bound exhausted")
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
    """Traverse a bounded deterministic transcript-link graph under one named policy."""

    DIAGNOSTIC_SAMPLE_LIMIT = 8
    RANKING_SAMPLE_LIMIT = 10

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
        self, identity_terms: tuple[str, ...], source_hints: tuple[str, ...],
        retained_anchors: tuple[dict[str, object], ...] = (),
    ) -> TranscriptDiscoveryResult:
        hint_urls = tuple(dict.fromkeys(
            hint for hint in source_hints if hint.startswith(("http://", "https://"))
        ))
        planned_queries = tuple(
            f'"{term}" earnings call transcript' for term in identity_terms[:2] if term.strip()
        )
        queries_submitted = 0
        exhausted = False
        exhausted_budget = ""
        search_endpoint = getattr(self.search, "endpoint", "https://search.invalid/")
        state = GraphTraversalState()
        hint_identities = {normalize_transcript_url(url) for url in hint_urls}
        hint_hosts = {urllib.parse.urlsplit(url).hostname or "" for url in hint_urls}
        phase_priority = {"retained_anchor": 0, "configured_hint": 1,
                          "bounded_traversal": 2}

        def reject(reason: str, url: str, *, cycle: str = "") -> None:
            state.reject(reason, url, cycle, self.DIAGNOSTIC_SAMPLE_LIMIT)

        def failure(code: str, url: str, error: Exception | None = None, status: int = 0) -> None:
            state.record_failure(DiscoveryFailureCode(code), url, error, status)

        def transport_class(error: Exception, phase: str) -> str:
            prefix = "hint_" if phase == "configured_hint" else "candidate_"
            if "redirect" in str(error).casefold():
                return "hint_redirect_rejected" if phase == "configured_hint" else "redirect_cycle"
            if isinstance(error, (TimeoutError, socket.timeout)):
                return prefix + "fetch_timeout"
            if isinstance(error, urllib.error.HTTPError):
                return prefix + "http_failure"
            return prefix + "transport_failure"

        def ranking(
            target: str, label: str, is_candidate: bool, depth: int, parent: str
        ) -> tuple[tuple[object, ...], list[str]]:
            parsed = urllib.parse.urlsplit(target)
            parent_host = (urllib.parse.urlsplit(parent).hostname or "").casefold()
            host = (parsed.hostname or "").casefold()
            evidence = urllib.parse.unquote(f"{label} {target}").casefold()
            reasons: list[str] = []
            hint_relation = host in hint_hosts or any(
                target.startswith(identity.rsplit("/", 1)[0]) for identity in hint_identities
            )
            same_host = bool(host and host == parent_host)
            terminology = int("transcript" in evidence) + int(any(
                term in evidence for term in ("earnings", "quarter", "results", "conference call")
            ))
            period = int(bool(re.search(r"\bq[1-4]\b|20\d{2}", evidence)))
            document = int(parsed.path.casefold().endswith((".html", ".htm", ".pdf")))
            if hint_relation:
                reasons.append("configured_hint_relation")
            if same_host:
                reasons.append("same_authoritative_host")
            if terminology:
                reasons.append("transcript_earnings_terminology")
            if period:
                reasons.append("reporting_period")
            if document:
                reasons.append("document_like_path")
            reasons.append(f"depth_{depth}")
            return (
                not is_candidate, not hint_relation, not same_host, -terminology,
                -period, -document, depth, target, label,
            ), reasons

        def classify_link(label: str, target: str) -> tuple[bool, bool]:
            candidate = EarningsCallTranscriptAcquisition._looks_like_transcript(label, target)
            evidence = urllib.parse.unquote(f"{label} {target}").casefold()
            if not candidate and "transcripts" in evidence:
                candidate = EarningsCallTranscriptAcquisition._looks_like_transcript(
                    label, target.replace("transcripts", "transcript")
                )
            return candidate or "transcript" in evidence, candidate

        def traverse(
            urls: tuple[str, ...], phase: str,
            anchor_labels: dict[str, tuple[int, str]] | None = None,
        ) -> None:
            nonlocal exhausted, exhausted_budget
            if not urls:
                return
            state.stage_sequence.append(phase)
            queue: list[tuple[tuple[object, ...], int, str, str, str, int, frozenset[str]]] = []
            serial = 0
            for position, observed in enumerate(urls):
                try:
                    identity = normalize_transcript_url(observed)
                except ValueError:
                    reject("invalid_url", observed)
                    continue
                if identity in state.queued or identity in state.visited:
                    reason = "already_queued" if identity in state.queued else "already_visited"
                    reject(reason, observed, cycle="duplicate_identity")
                    if anchor_labels and observed in anchor_labels:
                        anchor_position, form = anchor_labels[observed]
                        state.anchor_attempts.append(self._anchor_diagnostic(
                            anchor_position, form, observed, "skipped"
                        ))
                    continue
                state.queued.add(identity)
                heapq.heappush(queue, ((position, identity), serial, observed, identity,
                                       observed, 0, frozenset({identity})))
                serial += 1
                state.queue_admitted += 1
            while queue:
                _, _, url, identity, parent, depth, ancestors = heapq.heappop(queue)
                state.queued.discard(identity)
                if identity in state.visited:
                    reject("already_visited", url, cycle="duplicate_identity")
                    continue
                is_seed_candidate = (
                    EarningsCallTranscriptAcquisition._looks_like_transcript(url, url)
                )
                if is_seed_candidate:
                    if identity not in state.proposed:
                        seed_rank, seed_reasons = ranking(url, url, True, 0, url)
                        state.admit_candidate(RankedCandidateProposal(
                            phase_priority[phase], seed_rank, serial, url, url, identity,
                            tuple(seed_reasons), 0,
                        ), queue_admission=False)
                hint_attempt: dict[str, str] | None = None
                if phase == "configured_hint":
                    hint_attempt = {"url": redact_diagnostic_url(url), "status": "attempted"}
                    state.configured_hint_attempt_sequence.append(hint_attempt)
                try:
                    response = self.transport.get(url)
                except Exception as error:
                    if anchor_labels and url in anchor_labels:
                        position, form = anchor_labels[url]
                        state.anchor_attempts.append(self._anchor_diagnostic(
                            position, form, url, "failed"
                        ))
                    if self.transport.exhausted:
                        if hint_attempt is not None:
                            hint_attempt["status"] = "budget_rejected"
                        exhausted = True
                        exhausted_budget = self.transport.exhausted_budget
                        break
                    if hint_attempt is not None:
                        hint_attempt["status"] = "failed"
                    failure(transport_class(error, phase), url, error)
                    continue
                state.visited.add(identity)
                resolved_identity = normalize_transcript_url(response.url)
                redirect_chain = tuple(getattr(response, "redirects", ()))
                chain_identities: list[str] = []
                try:
                    chain_identities = [
                        normalize_transcript_url(item) for item in redirect_chain
                    ]
                except ValueError:
                    reject("redirect_invalid_url", response.url)
                if identity in chain_identities or len(chain_identities) != len(
                    set(chain_identities)
                ):
                    reject("redirect_cycle", response.url, cycle="redirect_cycle")
                    failure("hint_redirect_rejected" if phase == "configured_hint"
                            else "redirect_cycle", response.url, status=response.status)
                    continue
                if response.status < 200 or response.status >= 300:
                    if hint_attempt is not None:
                        hint_attempt["status"] = f"http_{response.status}"
                    failure("hint_http_failure" if phase == "configured_hint"
                            else "candidate_http_failure", response.url,
                            status=response.status)
                    continue
                if anchor_labels and url in anchor_labels:
                    position, form = anchor_labels[url]
                    state.anchor_attempts.append(self._anchor_diagnostic(
                        position, form, url, "succeeded"
                    ))
                if hint_attempt is not None:
                    hint_attempt["status"] = "fetched"
                if resolved_identity != identity:
                    if resolved_identity in ancestors or resolved_identity in state.visited:
                        reject("redirect_cycle", response.url, cycle="redirect_cycle")
                        failure("hint_redirect_rejected" if phase == "configured_hint"
                                else "redirect_cycle", response.url, status=response.status)
                        continue
                    state.visited.add(resolved_identity)
                if response.media_type not in {"text/html", "application/xhtml+xml"}:
                    if EarningsCallTranscriptAcquisition._looks_like_transcript(
                        "", response.url
                    ):
                        candidates.append({"url": response.url, "label": response.url})
                    continue
                state.listings.append(response.url)
                parser = _PageParser()
                try:
                    parser.feed(response.content.decode("utf-8", "replace"))
                except Exception as error:
                    failure("page_parse_failure", response.url, error)
                    continue
                state.raw_hyperlinks += len(parser.links)
                page_unique: set[str] = set()
                links: list[tuple[tuple[object, ...], str, str, str, bool, list[str]]] = []
                for href, label in parser.links:
                    observed = urllib.parse.urljoin(response.url, href)
                    try:
                        target = normalize_transcript_url(observed)
                    except ValueError:
                        reject("non_http_or_invalid", observed)
                        continue
                    if target in page_unique:
                        reject("duplicate_edge", observed, cycle="duplicate_edge")
                        continue
                    page_unique.add(target)
                    state.normalized_unique_hyperlinks += 1
                    if target == resolved_identity:
                        reject("direct_self_reference", observed, cycle="self_reference")
                        continue
                    if target in ancestors:
                        reject("graph_cycle", observed, cycle="ancestor_cycle")
                        continue
                    if target in state.queued:
                        reject("already_queued", observed, cycle="duplicate_identity")
                        continue
                    if target in state.proposed:
                        reject("already_proposed", observed, cycle="duplicate_identity")
                        continue
                    if target in state.visited:
                        reject("already_visited", observed, cycle="duplicate_identity")
                        continue
                    eligible, is_candidate = classify_link(label, target)
                    if not eligible:
                        reject("ineligible_transcript_evidence", observed)
                        continue
                    if depth >= self.policy.max_depth and not is_candidate:
                        reject("depth_limit", observed)
                        exhausted = True
                        exhausted_budget = exhausted_budget or "max_depth"
                        continue
                    rank, reasons = ranking(target, label, is_candidate, depth + 1, response.url)
                    links.append((rank, observed, target, label, is_candidate, reasons))
                links.sort(key=lambda item: item[0])
                state.eligible_hyperlinks += len(links)
                if len(links) > self.policy.max_links_per_page:
                    exhausted = True
                    exhausted_budget = exhausted_budget or "max_links_per_page"
                admitted = links[: self.policy.max_links_per_page]
                state.traversed_hyperlinks += len(admitted)
                for rank, observed, target, label, is_candidate, reasons in admitted:
                    if len(state.ranking_samples) < self.RANKING_SAMPLE_LIMIT:
                        state.ranking_samples.append(RankingAdmissionRecord(
                            redact_diagnostic_url(observed), tuple(reasons),
                            is_candidate, depth + 1,
                        ))
                    if is_candidate:
                        state.admit_candidate(RankedCandidateProposal(
                            phase_priority[phase], rank, serial, observed,
                            label or observed, target, tuple(reasons), depth + 1,
                        ))
                        serial += 1
                    else:
                        state.queued.add(target)
                        heapq.heappush(queue, (rank, serial, observed, target, response.url,
                                               depth + 1, ancestors | {target}))
                        serial += 1
                        state.queue_admitted += 1
                if self.transport.exhausted:
                    exhausted = True
                    exhausted_budget = self.transport.exhausted_budget
                    break

        retained_urls: list[str] = []
        anchor_labels: dict[str, tuple[int, str]] = {}
        for position, anchor in enumerate(retained_anchors, 1):
            for form in ("resolved", "requested"):
                url = anchor.get(f"{form}_url")
                if isinstance(url, str) and url and url not in retained_urls:
                    retained_urls.append(url)
                    anchor_labels[url] = (position, form)
        traverse(tuple(retained_urls), "retained_anchor", anchor_labels)
        anchor_fallthrough = not exhausted and bool(hint_urls)
        if anchor_fallthrough:
            traverse(hint_urls, "configured_hint")
        hint_fallthrough = not exhausted and not state.candidate_proposals
        search_urls: list[str] = []
        for query in (() if exhausted or not hint_fallthrough else planned_queries):
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
                bounded_traversal_attempted = True
                queries_submitted += 1
                response = self.search.search(query, self.policy.max_results_per_query)
                self.transport.accept_response(response.received_bytes)
            except Exception as error:
                if self.transport.exhausted:
                    exhausted_budget = self.transport.exhausted_budget
                    exhausted = True
                    break
                failure("search_transport_failure", search_endpoint, error)
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
            search_urls.extend(response.urls[: self.policy.max_results_per_query])
            if exhausted:
                break
        if not exhausted and hint_fallthrough:
            traverse(tuple(dict.fromkeys(search_urls)), "bounded_traversal")
        ordered_candidates = sorted(
            state.candidate_proposals, key=RankedCandidateProposal.sort_key
        )
        unique_candidates = tuple(
            {"url": item.observed_url, "label": item.label}
            for item in ordered_candidates
        )
        top_candidates = [
            {"url": redact_diagnostic_url(item.observed_url),
             "reasons": list(item.reasons), "depth": item.depth}
            for item in ordered_candidates[: self.RANKING_SAMPLE_LIMIT]
        ]
        failure_counts = Counter(item.code.value for item in state.failures)
        transport_failures: list[dict[str, object]] = []
        for item in state.failures[: self.DIAGNOSTIC_SAMPLE_LIMIT]:
            sample: dict[str, object] = {
                "classification": item.code.value, "url": item.url,
            }
            if item.http_status is not None:
                sample["http_status"] = item.http_status
            if item.error_type != item.code.value:
                sample["error_type"] = item.error_type
            transport_failures.append(sample)
        if exhausted_budget and exhausted_budget not in DISCOVERY_BUDGET_FIELDS:
            raise RuntimeError("discovery reported an unknown exhausted budget")
        if exhausted != bool(exhausted_budget):
            raise RuntimeError("discovery exhaustion requires one named policy budget")
        return TranscriptDiscoveryResult(
            tuple(dict.fromkeys(state.listings)),
            unique_candidates,
            tuple(sorted(self.transport.hosts)),
            exhausted,
            {
                "search_queries": queries_submitted,
                "pages": self.transport.pages,
                "distinct_hosts": len(self.transport.hosts),
                "bytes": self.transport.bytes,
                "candidate_urls": len(unique_candidates),
                "candidate_admitted_count": len(state.candidate_proposals),
                "raw_hyperlinks": state.raw_hyperlinks,
                "normalized_unique_hyperlinks": state.normalized_unique_hyperlinks,
                "eligible_hyperlinks": state.eligible_hyperlinks,
                "traversed_hyperlinks": state.traversed_hyperlinks,
                "queue_admitted_count": state.queue_admitted,
                "visited_count": len(state.visited),
                "rejection_counts": dict(sorted(state.rejection_counts.items())),
                "cycle_counts": dict(sorted(state.cycle_counts.items())),
                "representative_rejections": [
                    {"reason": item.reason, "url": item.url}
                    for item in state.rejected_samples
                ],
                "top_ranked_candidates": top_candidates,
                "ranked_queue_admissions": [
                    {"url": item.url, "reasons": list(item.reasons),
                     "candidate": item.candidate, "depth": item.depth}
                    for item in state.ranking_samples
                ],
                "bounds_exhausted": exhausted,
                "exhausted_budget": exhausted_budget,
                "discovery_failures": sum(failure_counts.values()),
                "discovery_failure_codes": ",".join(
                    item.legacy_code for item in state.failures
                ),
                "discovery_failure_types": ",".join(
                    item.error_type for item in state.failures
                ),
                "discovery_failure_counts": dict(sorted(failure_counts.items())),
                "transport_failures": transport_failures,
                "configured_hint_count": len(hint_urls),
                "configured_hint_pages": sum(
                    identity in state.visited for identity in hint_identities
                ),
                "configured_hint_status": (
                    "not_supplied" if not hint_urls else
                    "used" if any(
                        identity in state.visited for identity in hint_identities
                    ) else "unusable"
                ),
                "anchor_attempts": state.anchor_attempts,
                "configured_hint_attempt_sequence": state.configured_hint_attempt_sequence,
                "anchor_to_hint_fallthrough": anchor_fallthrough and bool(hint_urls),
                "hint_to_traversal_fallthrough": hint_fallthrough and bool(planned_queries),
                "configured_hint_fallthrough": anchor_fallthrough and bool(hint_urls),
                "bounded_traversal_fallthrough": hint_fallthrough and bool(planned_queries),
                "stage_sequence": state.stage_sequence,
                "redirect_count": self.transport.redirects,
                "final_host": sorted(self.transport.hosts)[-1] if self.transport.hosts else "",
            },
        )

    @staticmethod
    def _anchor_diagnostic(
        position: int, form: str, url: str, status: str
    ) -> dict[str, object]:
        return {
            "position": position, "form": form, "url": redact_diagnostic_url(url),
            "query_present": bool(urllib.parse.urlsplit(url).query), "status": status,
        }


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
        repository: AcquisitionRepository | None = None,
    ) -> None:
        self._policies = policies
        self._search = search or DuckDuckGoHtmlSearch()
        self._transport = transport or UrllibEarningsTranscriptTransport()
        self._clock = clock
        self._monotonic = monotonic
        self._retrievals: dict[str, RetrievalResult] = {}
        self._repository = repository

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
            history = ()
            firm_id = profile.policy.get("firm_id")
            if self._repository is not None and isinstance(firm_id, str):
                history = self._repository.discovery_anchors(
                    firm_id, profile.source_id, self.adapter_id
                )
            if mode == "discovery":
                discovered = BoundedTranscriptDiscovery(
                    self._search, budgeted, policy
                ).discover(identity_terms, source_hints, tuple(history))
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
                early = {
                    "adapter_id": self.adapter_id,
                    "discovery_class": configuration.get("discovery_class"),
                    "coverage": "indeterminate",
                    **discovered.diagnostics,
                    "history_key": (
                        f"{profile.policy.get('firm_id')}:{profile.source_id}:{self.adapter_id}"
                    ),
                    "retained_anchor_count": len(history),
                    "retained_anchor_order": [item["normalized_url"] for item in history],
                    "candidate_evaluated_count": 0,
                    "validation_failure_counts": {},
                    "candidate_retrieval_failure_counts": {},
                }
                classification, summary = self._classify_outcome(early, ())
                early.update({"primary_classification": classification,
                              "operator_summary": summary,
                              "final_coverage_classification": "coverage_indeterminate"})
                return DiscoveryPage((), None, early)
            governed = SourceProfile(
                profile.source_id, profile.name, profile.enabled, self.mechanism,
                {
                    "listing_urls": list(listing_urls[:8]),
                    "allowed_hosts": list(discovered.allowed_hosts),
                    "candidate_proposals": list(discovered.candidate_proposals),
                    "maximum_candidates": policy.max_candidate_evaluations,
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
            "history_key": f"{profile.policy.get('firm_id')}:{profile.source_id}:{self.adapter_id}",
            "retained_anchor_count": len(history),
            "retained_anchor_order": [item["normalized_url"] for item in history],
            "pages": budgeted.pages,
            "distinct_hosts": len(budgeted.hosts),
            "bytes": budgeted.bytes,
            "bounds_exhausted": discovered.exhausted or budgeted.exhausted,
            "exhausted_budget": budgeted.exhausted_budget
            or str(discovered.diagnostics.get("exhausted_budget", "")),
        })
        if budgeted.exhausted:
            coverage = "indeterminate"
        failure_code_counts = dict(sorted(Counter(
            failure.code for failure in interval.failures
        ).items()))
        validation_failure_counts = dict(sorted(Counter(
            self._candidate_failure_code(failure)
            for failure in interval.failures if failure.code == "candidate_invalid"
        ).items()))
        retrieval_failure_counts = dict(sorted(Counter(
            self._candidate_failure_code(failure)
            for failure in interval.failures if failure.code == "candidate_unavailable"
        ).items()))
        candidate_failure_samples = []
        for failure in interval.failures:
            if failure.code not in {"candidate_unavailable", "candidate_invalid"}:
                continue
            if len(candidate_failure_samples) >= BoundedTranscriptDiscovery.DIAGNOSTIC_SAMPLE_LIMIT:
                break
            classification = self._candidate_failure_code(failure)
            sample: dict[str, object] = {"classification": classification}
            url = failure.details.get("url")
            if isinstance(url, str):
                sample["url"] = redact_diagnostic_url(url)
            status = failure.details.get("http_status")
            if isinstance(status, int):
                sample["http_status"] = status
            candidate_failure_samples.append(sample)
        candidate_limit_reached = failure_code_counts.get("candidate_limit", 0) > 0
        if candidate_limit_reached and not final_diagnostics["exhausted_budget"]:
            final_diagnostics["bounds_exhausted"] = True
            final_diagnostics["exhausted_budget"] = "max_candidate_evaluations"
            coverage = "indeterminate"
        final_diagnostics.update({
            "candidate_evaluated_count": min(
                len(discovered.candidate_proposals), policy.max_candidate_evaluations
            ),
            "validation_failure_counts": validation_failure_counts,
            "candidate_retrieval_failure_counts": retrieval_failure_counts,
            "candidate_failure_samples": candidate_failure_samples,
        })
        classification, summary = self._classify_outcome(
            {**final_diagnostics, "coverage": coverage}, interval.failures
        )
        return DiscoveryPage(tuple(candidates), None, {
            "adapter_id": self.adapter_id,
            "discovery_class": configuration.get("discovery_class"),
            "coverage": coverage,
            "validation_failures": len(interval.failures),
            "failure_code_counts": failure_code_counts,
            "primary_classification": classification,
            "operator_summary": summary,
            "final_coverage_classification": (
                "coverage_indeterminate" if coverage == "indeterminate" else coverage
            ),
            **final_diagnostics,
        })

    @staticmethod
    def _classify_outcome(
        diagnostics: dict[str, Any], failures: tuple[Any, ...]
    ) -> tuple[str, str]:
        if diagnostics.get("bounds_exhausted"):
            budget = str(diagnostics.get("exhausted_budget") or "")
            count = diagnostics.get("candidate_evaluated_count", 0)
            if budget == "max_candidate_evaluations":
                return (
                    "discovery_budget_exhausted",
                    "Discovery exhausted the candidate-evaluation budget after evaluating "
                    f"{count} ranked unique links.",
                )
            return (
                "discovery_budget_exhausted",
                f"Discovery exhausted the {budget} budget." if budget
                else "Discovery exhausted a configured budget.",
            )
        discovery_failures = diagnostics.get("discovery_failure_counts", {})
        if isinstance(discovery_failures, dict):
            if discovery_failures.get("hint_fetch_timeout"):
                return "hint_fetch_timeout", "The configured transcript hint timed out."
            if discovery_failures.get("hint_http_failure"):
                status = next((
                    item.get("http_status") for item in diagnostics.get("transport_failures", [])
                    if item.get("classification") == "hint_http_failure"
                ), None)
                suffix = f" {status}" if status else ""
                return (
                    "hint_http_failure",
                    f"The configured transcript hint returned HTTP{suffix}.",
                )
            if discovery_failures.get("hint_redirect_rejected"):
                return (
                    "hint_redirect_rejected",
                    "The configured transcript hint redirect was rejected.",
                )
            if discovery_failures.get("redirect_cycle"):
                return "redirect_cycle", "Transcript discovery rejected a redirect cycle."
        for failure in failures:
            if failure.code == "candidate_unavailable":
                code = EarningsTranscriptPullAdapter._candidate_failure_code(failure)
                messages = {
                    "candidate_http_not_found": (
                        "A transcript candidate was found but returned HTTP 404."
                    ),
                    "candidate_access_denied": (
                        "A transcript candidate was found but access was denied."
                    ),
                    "candidate_fetch_timeout": (
                        "A transcript candidate was found but retrieval timed out."
                    ),
                    "candidate_retrieval_failure": (
                        "A transcript candidate was found but retrieval failed."
                    ),
                }
                return code, messages[code]
            if failure.code == "candidate_invalid":
                code = EarningsTranscriptPullAdapter._candidate_failure_code(failure)
                messages = {
                    "candidate_unsupported_content_type": (
                        "A transcript candidate was found but its content type is unsupported."
                    ),
                    "candidate_empty": (
                        "A transcript candidate was found but its content was empty."
                    ),
                    "candidate_requires_javascript": (
                        "A transcript candidate was found but requires JavaScript."
                    ),
                    "candidate_validation_mismatch": (
                        "A transcript candidate was found but did not match transcript validation."
                    ),
                }
                return code, messages[code]
        if diagnostics.get("raw_hyperlinks", 0) and not diagnostics.get(
            "eligible_hyperlinks", 0
        ):
            return (
                "no_eligible_links",
                "No eligible transcript links were identified on the configured page.",
            )
        if diagnostics.get("candidate_urls", 0):
            return "candidate_not_found_within_bounds", "No transcript candidate validated."
        return (
            "coverage_indeterminate",
            "Discovery completed without a candidate, but coverage remains indeterminate.",
        )

    @staticmethod
    def _candidate_failure_code(failure: Any) -> str:
        value = failure.details.get("candidate_failure_code")
        try:
            return CandidateFailureCode(value).value
        except (TypeError, ValueError):
            if failure.code == "candidate_invalid":
                return CandidateFailureCode.VALIDATION_MISMATCH.value
            return CandidateFailureCode.RETRIEVAL_FAILURE.value

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
