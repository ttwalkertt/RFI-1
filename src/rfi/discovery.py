"""Repository-owned bounded discovery policies and transcript URL discovery."""

from __future__ import annotations

import json
import hashlib
import heapq
import re
import socket
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter
from dataclasses import dataclass, field, replace
from datetime import date, timedelta
from enum import Enum, IntEnum
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Callable, Protocol

from jsonschema import Draft202012Validator

from rfi.acquisition.earnings_transcripts import (
    CandidateFailureCode,
    CandidateDispositionCode,
    EarningsCallTranscriptAcquisition,
    EarningsTranscriptHttpResponse,
    EarningsTranscriptTransport,
    ReportingPeriod,
    UrllibEarningsTranscriptTransport,
    classify_transcript_document,
    normalize_transcript_url,
    reporting_period_from_evidence,
    transcript_request_headers,
)
from rfi.acquisition.contracts import (
    ContractError,
    DiscoveryProvenance,
    IntervalAcquisitionRequest,
    JsonValue,
    RetrievalResult,
    SourceProfile,
    TranscriptAcquisitionSelection,
    TranscriptAcquisitionTarget,
    TranscriptEventDisposition,
    TranscriptSeed,
    TranscriptSelectionMode,
)
from rfi.acquisition.repository import AcquisitionRepository
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
from rfi.acquisition.providers import (
    StockAnalysisTranscriptProvider,
    TranscriptProvider,
    TranscriptProviderRegistry,
)


class DiscoveryPolicyError(RuntimeError):
    """Raised when the repository policy catalog or a class selection is invalid."""


@dataclass(frozen=True)
class DiscoveryPolicy:
    max_search_queries: int
    max_results_per_query: int
    max_unique_eligible_links_per_page: int
    max_depth: int
    max_pages: int
    max_distinct_hosts: int
    max_bytes: int
    max_elapsed_seconds: int
    max_candidate_evaluations: int = 40
    max_redirects: int = 10

    @property
    def max_links_per_page(self) -> int:
        """Read compatibility for callers migrating from the obsolete policy name."""
        return self.max_unique_eligible_links_per_page


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
    classes = value.get("classes") if isinstance(value, dict) else None
    if isinstance(classes, dict):
        for policy in classes.values():
            if not isinstance(policy, dict):
                continue
            legacy = policy.pop("max_links_per_page", None)
            if legacy is not None:
                if "max_unique_eligible_links_per_page" in policy:
                    raise DiscoveryPolicyError(
                        "discovery policy contains both legacy and current per-page ceilings"
                    )
                policy["max_unique_eligible_links_per_page"] = legacy
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
    candidate_proposals: tuple[dict[str, Any], ...]
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


class GraphStagePriority(IntEnum):
    RETAINED_ANCHOR = 0
    CONFIGURED_HINT = 1
    BOUNDED_TRAVERSAL = 2


class GraphNodePriority(IntEnum):
    SEED = 0
    DISCOVERED = 1


@dataclass(frozen=True, order=True)
class LinkRank:
    """Homogeneous deterministic ordering fields for one eligible graph edge."""

    candidate_priority: int
    period_priority: int
    period_ordinal_priority: int
    hint_relation_priority: int
    same_host_priority: int
    terminology_priority: int
    document_priority: int
    depth: int
    normalized_url: str
    label: str


@dataclass(frozen=True, order=True)
class GraphQueuePriority:
    """One total-order key shared by seed and discovered graph nodes."""

    stage_priority: GraphStagePriority
    node_priority: GraphNodePriority
    seed_position: int
    link_rank: LinkRank
    normalized_url: str
    insertion_sequence: int


@dataclass(frozen=True, order=True)
class GraphQueueEntry:
    """Typed heap entry whose payload never participates in ordering."""

    priority: GraphQueuePriority
    observed_url: str = field(compare=False)
    normalized_url: str = field(compare=False)
    depth: int = field(compare=False)
    ancestors: frozenset[str] = field(compare=False)


@dataclass(frozen=True)
class RankedCandidateProposal:
    """One graph proposal with its complete deterministic ordering contract."""

    phase_priority: int
    rank: LinkRank
    serial: int
    observed_url: str
    label: str
    normalized_url: str
    observed_aliases: tuple[str, ...]
    reasons: tuple[str, ...]
    depth: int

    def sort_key(self) -> tuple[object, ...]:
        return (
            self.phase_priority, self.rank, self.serial, self.observed_url, self.label,
            self.normalized_url, self.observed_aliases, self.reasons, self.depth,
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

    def reconcile_candidate_redirect(
        self, requested_identity: str, resolved_url: str
    ) -> None:
        """Collapse an observed candidate redirect while retaining every exact alias."""
        resolved_identity = normalize_transcript_url(resolved_url)
        current = next((
            item for item in self.candidate_proposals
            if item.normalized_url == requested_identity
        ), None)
        if current is None:
            return
        aliases = tuple(dict.fromkeys((*current.observed_aliases, resolved_url)))
        existing = next((
            item for item in self.candidate_proposals
            if item is not current and item.normalized_url == resolved_identity
        ), None)
        if existing is not None:
            merged = replace(
                existing,
                observed_aliases=tuple(dict.fromkeys((*existing.observed_aliases, *aliases))),
            )
            self.candidate_proposals = [
                merged if item is existing else item
                for item in self.candidate_proposals if item is not current
            ]
            self.proposed.discard(requested_identity)
            return
        replacement = replace(
            current,
            observed_url=resolved_url,
            normalized_url=resolved_identity,
            observed_aliases=aliases,
        )
        self.candidate_proposals = [
            replacement if item is current else item for item in self.candidate_proposals
        ]
        self.proposed.discard(requested_identity)
        self.proposed.add(resolved_identity)


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
        self.cache_hits = 0
        self._responses: dict[str, EarningsTranscriptHttpResponse] = {}
        self.candidate_identities: set[str] = set()
        self.candidate_capacity_exhausted = False

    def get(self, url: str) -> EarningsTranscriptHttpResponse:
        identity = normalize_transcript_url(url)
        cached = self._responses.get(identity)
        if cached is not None:
            self.cache_hits += 1
            return cached
        self.begin_request(url)
        response = self.inner.get(url)
        redirect_chain = tuple(getattr(response, "redirects", ()))
        response_hosts = {
            (urllib.parse.urlsplit(item).hostname or "").casefold()
            for item in (*redirect_chain, response.url)
        }
        response_hosts.discard("")
        if len(self.hosts | response_hosts) > self.policy.max_distinct_hosts:
            self.exhausted = True
            self.exhausted_budget = "max_distinct_hosts"
            raise ValueError("discovery distinct-host bound exhausted")
        self.hosts.update(response_hosts)
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
        self._responses[identity] = response
        self._responses[normalize_transcript_url(response.url)] = response
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
        checkpoint_period: ReportingPeriod | None = None,
        expected_period: ReportingPeriod | None = None,
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
        phase_priority = {
            "retained_anchor": GraphStagePriority.RETAINED_ANCHOR,
            "configured_hint": GraphStagePriority.CONFIGURED_HINT,
            "bounded_traversal": GraphStagePriority.BOUNDED_TRAVERSAL,
        }

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
        ) -> tuple[LinkRank, list[str]]:
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
            reporting_period = reporting_period_from_evidence(label, target)
            period_rank, period_reason = self._period_rank(
                reporting_period, checkpoint_period, expected_period
            )
            document = int(parsed.path.casefold().endswith((".html", ".htm", ".pdf")))
            if hint_relation:
                reasons.append("configured_hint_relation")
            if same_host:
                reasons.append("same_authoritative_host")
            if terminology:
                reasons.append("transcript_earnings_terminology")
            if period_reason:
                reasons.extend((period_reason, f"reporting_period_{reporting_period.code}"))
            if document:
                reasons.append("document_like_path")
            reasons.append(f"depth_{depth}")
            return LinkRank(
                0 if is_candidate else 1,
                period_rank[0],
                period_rank[1],
                0 if hint_relation else 1,
                0 if same_host else 1,
                -terminology,
                -document,
                depth,
                target,
                label,
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
            queue: list[GraphQueueEntry] = []
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
                seed_rank, _ = ranking(
                    observed, observed,
                    EarningsCallTranscriptAcquisition._looks_like_transcript(
                        observed, observed
                    ),
                    0, observed,
                )
                heapq.heappush(queue, GraphQueueEntry(
                    GraphQueuePriority(
                        phase_priority[phase], GraphNodePriority.SEED, position,
                        seed_rank, identity, serial,
                    ),
                    observed, identity, 0, frozenset({identity}),
                ))
                serial += 1
                state.queue_admitted += 1
            while queue:
                entry = heapq.heappop(queue)
                url = entry.observed_url
                identity = entry.normalized_url
                depth = entry.depth
                ancestors = entry.ancestors
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
                            (url,), tuple(seed_reasons), 0,
                        ), queue_admission=False)
                hint_attempt: dict[str, str] | None = None
                if phase == "configured_hint":
                    hint_attempt = {"url": redact_diagnostic_url(url), "status": "attempted"}
                    state.configured_hint_attempt_sequence.append(hint_attempt)
                try:
                    response = self.transport.get(url)
                except (OSError, TimeoutError, ValueError, UnicodeError) as error:
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
                    if is_seed_candidate and resolved_identity in state.visited:
                        state.reconcile_candidate_redirect(identity, response.url)
                        reject(
                            "redirect_alias_duplicate", response.url,
                            cycle="duplicate_identity",
                        )
                        continue
                    if resolved_identity in ancestors or resolved_identity in state.visited:
                        reject("redirect_cycle", response.url, cycle="redirect_cycle")
                        failure("hint_redirect_rejected" if phase == "configured_hint"
                                else "redirect_cycle", response.url, status=response.status)
                        continue
                    state.visited.add(resolved_identity)
                if is_seed_candidate:
                    state.reconcile_candidate_redirect(identity, response.url)
                if response.media_type not in {"text/html", "application/xhtml+xml"}:
                    continue
                state.listings.append(response.url)
                parser = _PageParser()
                try:
                    parser.feed(response.content.decode("utf-8", "replace"))
                except (ValueError, UnicodeError) as error:
                    failure("page_parse_failure", response.url, error)
                    continue
                state.raw_hyperlinks += len(parser.links)
                page_unique: set[str] = set()
                links: list[tuple[LinkRank, str, str, str, bool, list[str]]] = []
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
                if len(links) > self.policy.max_unique_eligible_links_per_page:
                    exhausted = True
                    exhausted_budget = (
                        exhausted_budget or "max_unique_eligible_links_per_page"
                    )
                admitted = links[: self.policy.max_unique_eligible_links_per_page]
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
                            label or observed, target, (observed,), tuple(reasons), depth + 1,
                        ))
                        serial += 1
                    else:
                        state.queued.add(target)
                        heapq.heappush(queue, GraphQueueEntry(
                            GraphQueuePriority(
                                phase_priority[phase], GraphNodePriority.DISCOVERED,
                                0, rank, target, serial,
                            ),
                            observed, target, depth + 1, ancestors | {target},
                        ))
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
            except (OSError, TimeoutError, ValueError, UnicodeError) as error:
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
            {
                "url": item.observed_url,
                "label": item.label,
                "observed_aliases": list(item.observed_aliases),
                # This is the existing semantic link rank with topology and identity
                # tie-breakers removed so it remains globally comparable across seeds.
                "deterministic_selection_rank": [
                    item.rank.candidate_priority,
                    item.rank.period_ordinal_priority,
                    item.rank.terminology_priority,
                    item.rank.document_priority,
                ],
            }
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
                "unique_eligible_link_emergency_ceiling": (
                    self.policy.max_unique_eligible_links_per_page
                ),
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

    @staticmethod
    def _period_rank(
        period: ReportingPeriod | None,
        checkpoint: ReportingPeriod | None,
        expected: ReportingPeriod | None,
    ) -> tuple[tuple[int, int], str]:
        if period is None:
            return (4, 0), ""
        if expected is not None and period == expected:
            return (0, -period.ordinal), "reporting_period_expected"
        if checkpoint is not None and period > checkpoint:
            return (1, -period.ordinal), "reporting_period_newer_than_checkpoint"
        if checkpoint is not None and period == checkpoint:
            return (2, -period.ordinal), "reporting_period_checkpoint"
        return (3, -period.ordinal), "reporting_period_historical"


class TranscriptPageClassification(str, Enum):
    """Content-evidenced role of one resolver seed response."""

    TRANSCRIPT_DOCUMENT = "transcript_document"
    TRANSCRIPT_LISTING = "transcript_listing"
    UNSUPPORTED = "unsupported"
    FAILED = "failed"


class BoundedTranscriptResolver:
    """Resolve supplied pages directly without recursively crawling their graph."""

    DIAGNOSTIC_SAMPLE_LIMIT = 8
    RANKING_SAMPLE_LIMIT = 10

    def __init__(
        self,
        transport: BudgetedTranscriptTransport,
        policy: DiscoveryPolicy,
    ) -> None:
        self.transport = transport
        self.policy = policy

    def resolve(
        self,
        seeds: tuple[str, ...],
        phase: str,
        seed_kind: str,
        seed_source: str,
        checkpoint_period: ReportingPeriod | None,
        expected_period: ReportingPeriod | None,
        duplicate_seed_count: int = 0,
    ) -> TranscriptDiscoveryResult:
        """Classify canonical seeds and admit documents or immediate document links."""
        canonical: list[str] = []
        seen: set[str] = set()
        duplicates = duplicate_seed_count
        for seed in seeds:
            identity = normalize_transcript_url(seed)
            if identity in seen:
                duplicates += 1
                continue
            seen.add(identity)
            canonical.append(identity)

        proposals: list[dict[str, Any]] = []
        listings: list[str] = []
        classification_counts: Counter[str] = Counter()
        classification_samples: list[dict[str, JsonValue]] = []
        failure_counts: Counter[str] = Counter()
        failure_samples: list[dict[str, JsonValue]] = []
        raw_hyperlinks = 0
        normalized_unique_hyperlinks = 0
        eligible_hyperlinks = 0
        rejected_links = 0
        exhausted = False
        exhausted_budget = ""

        for seed_position, seed in enumerate(canonical):
            if self.transport.exhausted:
                exhausted = True
                exhausted_budget = self.transport.exhausted_budget
                break
            try:
                response = self.transport.get(seed)
            except (OSError, TimeoutError, ValueError, UnicodeError) as error:
                classification = TranscriptPageClassification.FAILED
                code = self._failure_code(error)
                failure_counts[code] += 1
                if len(failure_samples) < self.DIAGNOSTIC_SAMPLE_LIMIT:
                    failure_samples.append({
                        "classification": code,
                        "url": redact_diagnostic_url(seed),
                        "error_type": error.__class__.__name__,
                    })
                if self.transport.exhausted:
                    exhausted = True
                    exhausted_budget = self.transport.exhausted_budget
                self._record_classification(
                    classification_counts, classification_samples,
                    seed, classification, seed_position,
                )
                if exhausted:
                    break
                continue

            if response.status < 200 or response.status >= 300:
                classification = TranscriptPageClassification.FAILED
                code = "seed_http_failure"
                failure_counts[code] += 1
                if len(failure_samples) < self.DIAGNOSTIC_SAMPLE_LIMIT:
                    failure_samples.append({
                        "classification": code,
                        "url": redact_diagnostic_url(response.url),
                        "http_status": response.status,
                    })
                self._record_classification(
                    classification_counts, classification_samples,
                    seed, classification, seed_position,
                )
                continue

            try:
                requested_identity = normalize_transcript_url(seed)
                redirect_identities = tuple(
                    normalize_transcript_url(item) for item in response.redirects
                )
            except ValueError:
                redirect_identities = (requested_identity,)
            if (
                requested_identity in redirect_identities
                or len(redirect_identities) != len(set(redirect_identities))
            ):
                classification = TranscriptPageClassification.FAILED
                failure_counts["redirect_cycle"] += 1
                if len(failure_samples) < self.DIAGNOSTIC_SAMPLE_LIMIT:
                    failure_samples.append({
                        "classification": "redirect_cycle",
                        "url": redact_diagnostic_url(response.url),
                    })
                self._record_classification(
                    classification_counts, classification_samples,
                    seed, classification, seed_position,
                )
                continue

            document_assessment = classify_transcript_document(response, seed)
            if document_assessment.is_transcript_document:
                classification = TranscriptPageClassification.TRANSCRIPT_DOCUMENT
                proposals.append(self._proposal(
                    response.url, seed, seed, seed_position, phase, seed_kind, seed_source,
                    checkpoint_period, expected_period, 0,
                    ("content_validated_transcript_document",),
                    tuple(dict.fromkeys((seed, response.url))),
                ))
                self._record_classification(
                    classification_counts, classification_samples,
                    seed, classification, seed_position,
                )
                continue

            direct_links: list[tuple[LinkRank, str, str, str, tuple[str, ...]]] = []
            if response.media_type.casefold() in {"text/html", "application/xhtml+xml"}:
                parser = _PageParser()
                try:
                    parser.feed(response.content.decode("utf-8", "replace"))
                except (ValueError, UnicodeError) as error:
                    classification = TranscriptPageClassification.FAILED
                    failure_counts["page_parse_failure"] += 1
                    if len(failure_samples) < self.DIAGNOSTIC_SAMPLE_LIMIT:
                        failure_samples.append({
                            "classification": "page_parse_failure",
                            "url": redact_diagnostic_url(response.url),
                            "error_type": error.__class__.__name__,
                        })
                    self._record_classification(
                        classification_counts, classification_samples,
                        seed, classification, seed_position,
                    )
                    continue
                listings.append(response.url)
                raw_hyperlinks += len(parser.links)
                page_seen: set[str] = set()
                for href, label in parser.links:
                    observed = urllib.parse.urljoin(response.url, href)
                    try:
                        target = normalize_transcript_url(observed)
                    except ValueError:
                        rejected_links += 1
                        continue
                    if target in page_seen or target == normalize_transcript_url(response.url):
                        rejected_links += 1
                        continue
                    page_seen.add(target)
                    normalized_unique_hyperlinks += 1
                    evidence = urllib.parse.unquote(f"{label} {target}").casefold()
                    is_candidate = EarningsCallTranscriptAcquisition._looks_like_transcript(
                        label, target
                    )
                    if not is_candidate and "transcripts" in evidence:
                        is_candidate = EarningsCallTranscriptAcquisition._looks_like_transcript(
                            label, target.replace("transcripts", "transcript")
                        )
                    if not is_candidate:
                        rejected_links += 1
                        continue
                    eligible_hyperlinks += 1
                    rank, reasons = self._rank(
                        target, label, response.url, checkpoint_period, expected_period
                    )
                    direct_links.append((rank, observed, target, label, tuple(reasons)))

            direct_links.sort(key=lambda item: item[0])
            if len(direct_links) > self.policy.max_unique_eligible_links_per_page:
                exhausted = True
                exhausted_budget = "max_unique_eligible_links_per_page"
            for rank, observed, target, label, reasons in direct_links[
                : self.policy.max_unique_eligible_links_per_page
            ]:
                proposals.append(self._proposal(
                    observed, label or observed, seed, seed_position, phase, seed_kind,
                    seed_source,
                    checkpoint_period, expected_period, 1, reasons, (observed, target), rank,
                ))
            classification = (
                TranscriptPageClassification.TRANSCRIPT_LISTING
                if direct_links else TranscriptPageClassification.UNSUPPORTED
            )
            self._record_classification(
                classification_counts, classification_samples,
                seed, classification, seed_position,
            )
            if exhausted:
                break

        if self.transport.exhausted:
            exhausted = True
            exhausted_budget = self.transport.exhausted_budget
        if exhausted_budget and exhausted_budget not in DISCOVERY_BUDGET_FIELDS:
            raise RuntimeError("transcript resolver reported an unknown exhausted budget")
        allowed_hosts = sorted({
            urllib.parse.urlsplit(str(item["url"])).hostname or ""
            for item in proposals
        } | self.transport.hosts)
        top = [
            {
                "url": redact_diagnostic_url(str(item["url"])),
                "reasons": list(item.get("ranking_reasons", [])),
                "depth": item.get("traversal_depth", 0),
            }
            for item in proposals[: self.RANKING_SAMPLE_LIMIT]
        ]
        return TranscriptDiscoveryResult(
            tuple(dict.fromkeys(listings)),
            tuple(proposals),
            tuple(host for host in allowed_hosts if host),
            exhausted,
            {
                "resolution_mode": "bounded_one_hop",
                "recursive_traversal": False,
                "search_queries": 0,
                "pages": self.transport.pages,
                "distinct_hosts": len(self.transport.hosts),
                "bytes": self.transport.bytes,
                "redirect_count": self.transport.redirects,
                "response_cache_hits": self.transport.cache_hits,
                "canonical_seed_count": len(canonical),
                "duplicate_seed_count": duplicates,
                "candidate_urls": len(proposals),
                "candidate_admitted_count": len(proposals),
                "raw_hyperlinks": raw_hyperlinks,
                "normalized_unique_hyperlinks": normalized_unique_hyperlinks,
                "eligible_hyperlinks": eligible_hyperlinks,
                "traversed_hyperlinks": 0,
                "rejected_link_count": rejected_links,
                "page_classification_counts": dict(sorted(classification_counts.items())),
                "page_classification_samples": classification_samples,
                "discovery_failures": sum(failure_counts.values()),
                "discovery_failure_counts": dict(sorted(failure_counts.items())),
                "transport_failures": failure_samples,
                "top_ranked_candidates": top,
                "bounds_exhausted": exhausted,
                "exhausted_budget": exhausted_budget,
                "stage_sequence": [phase],
                "configured_hint_count": len(canonical) if phase == "configured_hint" else 0,
                "configured_hint_pages": (
                    sum(classification_counts.values()) if phase == "configured_hint" else 0
                ),
                "configured_hint_status": (
                    "used" if phase == "configured_hint" and canonical else "not_supplied"
                ),
                "anchor_attempts": [],
                "configured_hint_attempt_sequence": [],
                "anchor_to_hint_fallthrough": False,
                "hint_to_traversal_fallthrough": False,
                "configured_hint_fallthrough": False,
                "bounded_traversal_fallthrough": False,
            },
        )

    @staticmethod
    def _record_classification(
        counts: Counter[str], samples: list[dict[str, JsonValue]], seed: str,
        classification: TranscriptPageClassification, position: int,
    ) -> None:
        counts[classification.value] += 1
        if len(samples) < BoundedTranscriptResolver.DIAGNOSTIC_SAMPLE_LIMIT:
            samples.append({
                "seed_position": position + 1,
                "url": redact_diagnostic_url(seed),
                "classification": classification.value,
            })

    @staticmethod
    def _failure_code(error: Exception) -> str:
        if isinstance(error, (TimeoutError, socket.timeout)):
            return "seed_fetch_timeout"
        if isinstance(error, urllib.error.HTTPError):
            return "seed_http_failure"
        return "seed_transport_failure"

    @staticmethod
    def _rank(
        target: str, label: str, parent: str,
        checkpoint: ReportingPeriod | None, expected: ReportingPeriod | None,
        depth: int = 1,
    ) -> tuple[LinkRank, list[str]]:
        parsed = urllib.parse.urlsplit(target)
        period = reporting_period_from_evidence(label, target)
        period_rank, period_reason = BoundedTranscriptDiscovery._period_rank(
            period, checkpoint, expected
        )
        terminology = int("transcript" in urllib.parse.unquote(
            f"{label} {target}"
        ).casefold()) + int(any(
            term in urllib.parse.unquote(f"{label} {target}").casefold()
            for term in ("earnings", "quarter", "results", "conference call")
        ))
        document = int(parsed.path.casefold().endswith((".html", ".htm", ".pdf")))
        same_host = (urllib.parse.urlsplit(parent).hostname or "").casefold() == (
            parsed.hostname or ""
        ).casefold()
        reasons = [
            "direct_seed_candidate" if depth == 0 else "direct_listing_candidate"
        ]
        if same_host:
            reasons.append("same_authoritative_host")
        if terminology:
            reasons.append("transcript_earnings_terminology")
        if period_reason and period is not None:
            reasons.extend((period_reason, f"reporting_period_{period.code}"))
        if document:
            reasons.append("document_like_path")
        reasons.append(f"depth_{depth}")
        return LinkRank(
            0, period_rank[0], period_rank[1], 0 if same_host else 1,
            0 if same_host else 1, -terminology, -document,
            depth, target, label,
        ), reasons

    @staticmethod
    def _proposal(
        url: str, label: str, seed: str, seed_position: int, phase: str,
        seed_kind: str, seed_source: str, checkpoint: ReportingPeriod | None,
        expected: ReportingPeriod | None, depth: int, reasons: tuple[str, ...],
        aliases: tuple[str, ...], rank: LinkRank | None = None,
    ) -> dict[str, Any]:
        normalized = normalize_transcript_url(url)
        if rank is None:
            rank, ranked_reasons = BoundedTranscriptResolver._rank(
                normalized, label, seed, checkpoint, expected, depth
            )
            reasons = tuple(dict.fromkeys((*reasons, *ranked_reasons)))
        return {
            "url": normalized,
            "label": label,
            "observed_aliases": list(dict.fromkeys((*aliases, normalized))),
            "deterministic_selection_rank": [
                rank.candidate_priority,
                rank.period_ordinal_priority,
                rank.terminology_priority,
                rank.document_priority,
            ],
            "starting_seed": seed,
            "seed_position": seed_position,
            "seed_kind": seed_kind,
            "seed_source": seed_source,
            "traversal_depth": depth,
            "parent_path": [seed] if depth == 0 else [seed, normalized],
            "ranking_reasons": list(reasons),
            "allowed_hosts": [urllib.parse.urlsplit(normalized).hostname or ""],
        }


class TranscriptAcquisitionOrchestrator:
    """Own ordered transcript seed planning; trials never select their successor."""

    def __init__(
        self, repository: AcquisitionRepository | None, adapter_id: str
    ) -> None:
        self._repository = repository
        self._adapter_id = adapter_id

    def plan(
        self, profile: SourceProfile, target: TranscriptAcquisitionTarget
    ) -> tuple[AdapterAcquisitionTrial, ...]:
        history: tuple[dict[str, object], ...] = ()
        firm_id = profile.policy.get("firm_id")
        if self._repository is not None and isinstance(firm_id, str):
            history = self._repository.discovery_anchors(
                firm_id, profile.source_id, self._adapter_id
            )
        planned: list[AdapterAcquisitionTrial] = []

        mode = profile.configuration.get("mode")
        if mode == "discovery":
            provider = profile.configuration.get("provider")
            hint_kind = profile.configuration.get("discovery_hint_kind")
            hint_value = profile.configuration.get("discovery_hint_value")
            if provider:
                if not all(isinstance(value, str) and value for value in (
                    provider, hint_kind, hint_value
                )):
                    raise ContractError(
                        "provider-backed transcript discovery requires an explicit typed hint"
                    )
                planned.append(AdapterAcquisitionTrial(
                    "transcript-trial-1", str(hint_value), str(hint_kind), target,
                    "configured", (str(hint_value),), provider=str(provider),
                ))
                learned_seen: set[tuple[str, str]] = set()
                for anchor in history:
                    anchor_provider = anchor.get("provider")
                    if not isinstance(anchor_provider, str) or not anchor_provider:
                        continue
                    for form in ("resolved_url", "requested_url"):
                        value = anchor.get(form)
                        if not isinstance(value, str) or not value:
                            continue
                        key = (str(anchor_provider), normalize_transcript_url(value))
                        if key in learned_seen:
                            continue
                        learned_seen.add(key)
                        planned.append(AdapterAcquisitionTrial(
                            f"transcript-trial-{len(planned) + 1}",
                            key[1], "url", target, "learned", (key[1],),
                            provider=str(anchor_provider),
                        ))
                return tuple(planned)
            learned: list[str] = []
            learned_seen: set[str] = set()
            duplicate_seed_count = 0
            for anchor in history:
                for form in ("resolved_url", "requested_url"):
                    value = anchor.get(form)
                    if isinstance(value, str) and value:
                        normalized = normalize_transcript_url(value)
                        if normalized in learned_seen:
                            duplicate_seed_count += 1
                            continue
                        learned_seen.add(normalized)
                        learned.append(normalized)
            hints = tuple(
                value for value in profile.configuration.get("discovery_hints", ())
                if isinstance(value, str) and value.startswith(("http://", "https://"))
            )
            if learned:
                planned.append(AdapterAcquisitionTrial(
                    "transcript-trial-1",
                    learned[0],
                    "single_seed" if len(learned) == 1 else "resolution_session",
                    target,
                    "learned",
                    tuple(learned),
                    duplicate_seed_count,
                    len(learned) > 1,
                ))
            fallback = normalize_transcript_url(hints[0]) if hints else None
            if fallback is not None and fallback not in learned_seen:
                planned.append(AdapterAcquisitionTrial(
                    f"transcript-trial-{len(planned) + 1}",
                    fallback,
                    "configured_fallback",
                    target,
                    "configured",
                    (fallback,),
                ))
            if not planned:
                planned.append(AdapterAcquisitionTrial(
                    "transcript-trial-1", "deterministic-empty-discovery",
                    "empty_seed", target, "configured",
                ))
        else:
            value = profile.configuration.get("url")
            if isinstance(value, str) and value:
                normalized = normalize_transcript_url(value)
                planned.append(AdapterAcquisitionTrial(
                    "transcript-trial-1", normalized, "configured_seed", target,
                    "configured", (normalized,),
                ))
        if not planned:
            planned.append(AdapterAcquisitionTrial(
                "transcript-trial-1", "deterministic-empty-discovery",
                "empty_seed", target, "configured",
            ))
        return tuple(planned)


@dataclass(frozen=True)
class TranscriptTerminalSelectionPolicy:
    """Qualify and globally reduce validated transcripts for a date-range target."""

    selection: TranscriptAcquisitionSelection

    def qualify(
        self, candidate: AdapterCandidate, retrieval: RetrievalResult
    ) -> AdapterSelectionDecision:
        observation = retrieval.transcript_metadata_observation
        if (
            observation is not None
            and observation.event_disposition
            is TranscriptEventDisposition.EXPLICIT_NON_EARNINGS
        ):
            return AdapterSelectionDecision(
                False,
                "validation_rejected",
                "explicit_non_earnings_event",
                {
                    "event_disposition": (
                        TranscriptEventDisposition.EXPLICIT_NON_EARNINGS.value
                    ),
                    "trusted_event_date_available": (
                        observation.trusted_event_date is not None
                    ),
                },
            )
        event_date = retrieval.trusted_event_date
        if event_date is None:
            existing_value = retrieval.diagnostics.get("validated_event_date")
            if isinstance(existing_value, str):
                try:
                    event_date = date.fromisoformat(existing_value)
                except ValueError as error:
                    raise ContractError(
                        "validated transcript event date is malformed"
                    ) from error
        if event_date is None:
            return AdapterSelectionDecision(
                False,
                "validation_rejected",
                "event_date_unavailable",
                {"trusted_event_date_available": False},
            )
        value = event_date.isoformat()
        rank = self._deterministic_rank(candidate)
        period = ((event_date.month - 1) // 3) + 1
        evidence = {
            "validated_event_date": value,
            "validated_position": event_date.year * 4 + period,
            "validated_revision": f"published-{value}",
            "validated_content_sha256": hashlib.sha256(retrieval.content).hexdigest(),
            "deterministic_selection_rank": list(rank),
        }
        if not self.selection.contains(event_date):
            return AdapterSelectionDecision(
                False,
                CandidateDispositionCode.WRONG_REPORTING_PERIOD.value,
                "selection_date_mismatch",
                evidence,
            )
        return AdapterSelectionDecision(
            True,
            CandidateDispositionCode.VALID_NEW_ARTIFACT.value,
            "validated",
            evidence,
        )

    def select(
        self, candidates: tuple[AdapterSelectionCandidate, ...]
    ) -> AdapterSelectionCandidate:
        if not candidates:
            raise ContractError("terminal transcript selection requires candidates")
        return min(candidates, key=self._selection_key)

    def attribution(self) -> dict[str, JsonValue]:
        if self.selection.start_date is None or self.selection.end_date is None:
            raise ContractError("terminal transcript selection range is malformed")
        return {
            "effective_selection_mode": self.selection.mode.value,
            "requested_date_range": {
                "start_date": self.selection.start_date.isoformat(),
                "end_date": self.selection.end_date.isoformat(),
            },
        }

    def _selection_key(
        self, item: AdapterSelectionCandidate
    ) -> tuple[object, ...]:
        event_date = item.decision.diagnostics.get("validated_event_date")
        digest = item.decision.diagnostics.get("validated_content_sha256")
        if not isinstance(event_date, str) or not isinstance(digest, str):
            raise ContractError("qualified transcript selection evidence is malformed")
        return (event_date, self._deterministic_rank(item.candidate), digest)

    @staticmethod
    def _deterministic_rank(candidate: AdapterCandidate) -> tuple[int, ...]:
        value = candidate.provenance.metadata.get("deterministic_selection_rank")
        if not isinstance(value, list) or len(value) != 4 or any(
            isinstance(item, bool) or not isinstance(item, int) for item in value
        ):
            raise ContractError("deterministic transcript selection rank is malformed")
        return tuple(value)


class EarningsTranscriptPullAdapter:
    """Execute one orchestrator-selected transcript trial through TASK-048 validation."""

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
        selection: TranscriptAcquisitionSelection | None = None,
    ) -> None:
        self._policies = policies
        self._search = search or DuckDuckGoHtmlSearch()
        self._transport = transport or UrllibEarningsTranscriptTransport()
        self._clock = clock
        self._monotonic = monotonic
        self._budgets: dict[str, BudgetedTranscriptTransport] = {}
        self._provider_adapters: dict[tuple[str, str], TranscriptProvider] = {}
        self._provider_registry = TranscriptProviderRegistry(
            (StockAnalysisTranscriptProvider,)
        )
        self._validated_expected: set[str] = set()
        self._repository = repository
        self._selection = selection or TranscriptAcquisitionSelection.latest()
        if not isinstance(self._selection, TranscriptAcquisitionSelection):
            raise ContractError("transcript acquisition selection is malformed")
        self._orchestrator = TranscriptAcquisitionOrchestrator(
            repository, self.adapter_id
        )

    def discover(self, profile: SourceProfile, continuation: str | None) -> DiscoveryPage:
        """Compatibility entry point for callers that request one aggregate discovery page."""
        return self._discover(profile, continuation)

    def acquisition_trials(
        self, profile: SourceProfile
    ) -> tuple[AdapterAcquisitionTrial, ...]:
        """Plan one learned resolution phase and at most one configured fallback."""
        self._validate_profile(profile)
        self._budgets.pop(profile.source_id, None)
        self._provider_adapters.clear()
        self._validated_expected.discard(profile.source_id)
        firm_id = profile.policy.get("firm_id")
        if not isinstance(firm_id, str):
            raise ContractError("transcript acquisition target requires firm_id")
        target = TranscriptAcquisitionTarget(firm_id, selection=self._selection)
        return self._orchestrator.plan(profile, target)

    def with_selection(
        self, selection: TranscriptAcquisitionSelection
    ) -> EarningsTranscriptPullAdapter:
        """Create an invocation-scoped adapter while retaining deterministic policy."""
        return EarningsTranscriptPullAdapter(
            self._policies,
            self._search,
            self._transport,
            self._clock,
            self._monotonic,
            self._repository,
            selection,
        )

    def injected_trial(
        self,
        profile: SourceProfile,
        target: TranscriptAcquisitionTarget,
        starting_seed: str,
    ) -> AdapterAcquisitionTrial:
        """Validate one advisory operator seed and bind it to the immutable target."""
        self._validate_profile(profile)
        if not isinstance(target, TranscriptAcquisitionTarget):
            raise ContractError("injected transcript acquisition target is malformed")
        if target.firm_id != profile.policy.get("firm_id"):
            raise ContractError("injected transcript target firm differs from source profile")
        if target.selection != self._selection:
            raise ContractError("injected transcript trial selection changed")
        normalized = normalize_transcript_url(starting_seed)
        self._budgets.pop(profile.source_id, None)
        self._provider_adapters.clear()
        self._validated_expected.discard(profile.source_id)
        provider = profile.configuration.get("provider")
        return AdapterAcquisitionTrial(
            "transcript-trial-1", normalized, "single_seed", target,
            "operator_supplied", (normalized,), provider=(
                str(provider) if isinstance(provider, str) else ""
            ),
        )

    def terminal_selection_policy(
        self, profile: SourceProfile,
        trials: tuple[AdapterAcquisitionTrial, ...],
    ) -> TranscriptTerminalSelectionPolicy | None:
        """Keep transcript qualification and reduction outside the neutral engine."""
        self._validate_profile(profile)
        if not trials or any(
            trial.acquisition_target.selection != self._selection for trial in trials
        ):
            raise ContractError("terminal transcript selection target changed")
        if self._selection.mode == TranscriptSelectionMode.FIRST_IN_DATE_RANGE:
            return TranscriptTerminalSelectionPolicy(self._selection)
        return None

    def discover_trial(
        self, profile: SourceProfile, trial: AdapterAcquisitionTrial
    ) -> DiscoveryPage:
        """Execute one orchestrator-selected bounded resolution phase."""
        if not isinstance(trial, AdapterAcquisitionTrial):
            raise ContractError("deterministic transcript trial is malformed")
        if trial.acquisition_target.selection != self._selection:
            raise ContractError("deterministic transcript trial selection changed")
        if trial.provider:
            return self._discover_provider(profile, trial)
        return self._discover(profile, None, trial)

    def _discover_provider(
        self, profile: SourceProfile, trial: AdapterAcquisitionTrial
    ) -> DiscoveryPage:
        self._validate_profile(profile)
        configured_provider = profile.configuration.get("provider")
        if trial.seed_source == "configured" and trial.provider != configured_provider:
            raise ContractError("transcript trial provider differs from firm configuration")
        try:
            policy = self._policies.resolve(
                str(profile.configuration.get("discovery_class") or "") or None
            )
        except DiscoveryPolicyError as error:
            raise ContractError(str(error)) from error
        budgeted = self._budgets.get(profile.source_id)
        if budgeted is None:
            budgeted = BudgetedTranscriptTransport(
                self._transport, policy, self._monotonic
            )
            self._budgets[profile.source_id] = budgeted
        provider_key = (profile.source_id, trial.provider)
        provider = self._provider_adapters.get(provider_key)
        if provider is None:
            provider = self._provider_registry.create(
                trial.provider, budgeted, self._clock
            )
            self._provider_adapters[provider_key] = provider
        seed = TranscriptSeed(
            trial.provider,
            "url" if trial.seed_source == "operator_supplied" else trial.seed_kind,
            trial.starting_seed,
            trial.seed_source,
        )
        page = provider.discover(profile, seed, trial.acquisition_target)
        admitted: list[AdapterCandidate] = []
        candidate_limit_reached = False
        unevaluated_admitted: set[str] = set()
        remaining = max(
            0,
            policy.max_candidate_evaluations - len(budgeted.candidate_identities),
        )
        for candidate in page.candidates:
            requested_url = candidate.provenance.metadata.get("requested_url")
            if not isinstance(requested_url, str):
                raise ContractError("provider candidate lacks a requested URL identity")
            identity = candidate.candidate_id
            if identity in budgeted.candidate_identities:
                admitted.append(candidate)
                continue
            if identity in unevaluated_admitted:
                admitted.append(candidate)
                continue
            if len(unevaluated_admitted) >= remaining:
                candidate_limit_reached = True
                continue
            unevaluated_admitted.add(identity)
            admitted.append(candidate)
        return DiscoveryPage(tuple(admitted), None, {
            **page.diagnostics,
            "adapter_id": self.adapter_id,
            "discovery_class": profile.configuration.get("discovery_class"),
            "pages": budgeted.pages,
            "bytes": budgeted.bytes,
            "distinct_hosts": len(budgeted.hosts),
            "redirect_count": budgeted.redirects,
            "bounds_exhausted": budgeted.exhausted,
            "exhausted_budget": budgeted.exhausted_budget,
            "candidate_budget": policy.max_candidate_evaluations,
            "candidate_admitted_count": len(admitted),
            "candidate_bound_exhausted": candidate_limit_reached,
            "run_unique_candidate_count": len(budgeted.candidate_identities),
            "candidate_evaluated_count": 0,
        })

    def _discover(
        self, profile: SourceProfile, continuation: str | None,
        trial: AdapterAcquisitionTrial | None = None,
    ) -> DiscoveryPage:
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
            mode = configuration.get("mode")
            resolver_kinds = {
                "single_seed", "resolution_session", "configured_fallback",
                "configured_seed", "empty_seed",
            }
            resolution_trial = (
                trial is not None
                and mode == "discovery"
                and trial.seed_kind in resolver_kinds
            )
            budgeted = (
                self._budgets.get(profile.source_id) if resolution_trial else None
            )
            if budgeted is None:
                budgeted = BudgetedTranscriptTransport(
                    self._transport, policy, self._monotonic
                )
            elif (
                resolution_trial
                and trial is not None
                and trial.seed_kind == "configured_fallback"
                and budgeted.candidate_capacity_exhausted
            ):
                raise AdapterFailure(
                    FailureClass.TRANSIENT_ADAPTER,
                    "Transcript run-level candidate evaluation budget was exhausted.",
                    True,
                    "max_candidate_evaluations",
                )
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
            if (
                resolution_trial
                and trial is not None
                and trial.seed_kind != "resolution_session"
            ):
                history = ()
            today = date.fromisoformat(self._clock()[:10])
            checkpoint_period, expected_period, period_basis = (
                self._reporting_period_context(
                    profile, () if resolution_trial else tuple(history), today
                )
            )
            if mode == "discovery":
                if resolution_trial:
                    assert trial is not None
                    phase = (
                        "retained_anchor"
                        if trial.seed_kind == "resolution_session"
                        else "configured_hint"
                    )
                    seeds = () if trial.seed_kind == "empty_seed" else trial.seeds
                    discovered = BoundedTranscriptResolver(
                        budgeted, policy
                    ).resolve(
                        seeds,
                        phase,
                        trial.seed_kind,
                        trial.seed_source,
                        checkpoint_period,
                        expected_period,
                        trial.duplicate_seed_count,
                    )
                else:
                    if trial is not None and trial.seed_kind != "configured_pipeline":
                        raise ContractError(
                            f"unknown deterministic transcript seed kind: {trial.seed_kind}"
                        )
                    discovered = BoundedTranscriptDiscovery(
                        self._search, budgeted, policy
                    ).discover(
                        identity_terms, source_hints, tuple(history),
                        checkpoint_period, expected_period,
                    )
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
            if (
                resolution_trial
                and discovered.exhausted
                and not discovered.candidate_proposals
            ):
                raise AdapterFailure(
                    FailureClass.TRANSIENT_ADAPTER,
                    "Transcript run-level resolution budget was exhausted.",
                    True,
                    str(discovered.diagnostics.get("exhausted_budget") or "budget_exhausted"),
                )
            if not discovered.listing_urls and not discovered.candidate_proposals:
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
                    "candidate_disposition_counts": {},
                    "candidate_disposition_samples": [],
                    "validation_failure_counts": {},
                    "candidate_retrieval_failure_counts": {},
                    "checkpoint_reporting_period": (
                        checkpoint_period.code if checkpoint_period else ""
                    ),
                    "expected_reporting_period": expected_period.code,
                    "reporting_period_basis": period_basis,
                    **self._trial_diagnostics(trial),
                }
                classification, summary = self._classify_outcome(early, ())
                early.update({"primary_classification": classification,
                              "operator_summary": summary,
                              "final_coverage_classification": "coverage_indeterminate"})
                return DiscoveryPage((), None, early)
        except DiscoveryPolicyError as error:
            raise ContractError(str(error)) from error
        selected_values: list[dict[str, Any]] = []
        candidate_limit_reached = False
        for proposal in discovered.candidate_proposals:
            identity = normalize_transcript_url(str(proposal["url"]))
            if identity in budgeted.candidate_identities:
                selected_values.append(proposal)
                continue
            if len(budgeted.candidate_identities) >= policy.max_candidate_evaluations:
                candidate_limit_reached = True
                budgeted.candidate_capacity_exhausted = True
                continue
            budgeted.candidate_identities.add(identity)
            selected_values.append(proposal)
        selected = tuple(selected_values)
        candidates = []
        discovered_at = self._clock()
        for proposal_rank, proposal in enumerate(selected):
            url = str(proposal["url"])
            label = str(proposal.get("label") or url)
            normalized = normalize_transcript_url(url)
            aliases = tuple(
                value for value in proposal.get("observed_aliases", ())
                if isinstance(value, str) and value
            ) or (url,)
            period = reporting_period_from_evidence(label, normalized) or expected_period
            digest = hashlib.sha256(normalized.encode()).hexdigest()
            candidates.append(AdapterCandidate(
                f"candidate-{digest}", f"document-{digest}", period.ordinal,
                f"proposal-{period.code.casefold()}",
                DiscoveryProvenance(
                    discovered_at, self.mechanism,
                    locations=tuple(dict.fromkeys((*aliases, normalized))),
                    metadata={
                        "firm_id": profile.policy["firm_id"],
                        "canonical_artifact_id": "earnings_transcript",
                        "link_label": label,
                        "requested_url": aliases[0],
                        "resolved_url": url,
                        "observed_aliases": list(aliases),
                        "allowed_hosts": list(
                            proposal.get("allowed_hosts", discovered.allowed_hosts)
                        ),
                        "firm_identity_terms": list(identity_terms),
                        "checkpoint_reporting_period": (
                            checkpoint_period.code if checkpoint_period else ""
                        ),
                        "expected_reporting_period": expected_period.code,
                        "deferred_candidate_evaluation": True,
                        "proposal_rank": proposal_rank,
                        "deterministic_selection_rank": list(
                            proposal.get("deterministic_selection_rank", (0, 0, 0, 0))
                        ),
                        **{
                            key: proposal[key]
                            for key in (
                                "traversal_depth", "parent_path", "ranking_reasons",
                            )
                            if key in proposal
                        },
                        **(
                            {
                                key: proposal[key]
                                for key in ("starting_seed", "seed_kind", "seed_source")
                                if key in proposal
                            }
                            if trial is not None
                            and trial.seed_kind == "resolution_session"
                            else {}
                        ),
                        "acquisition_target": (
                            trial.acquisition_target.to_dict() if trial is not None else
                            TranscriptAcquisitionTarget(
                                str(profile.policy["firm_id"]), selection=self._selection
                            ).to_dict()
                        ),
                    },
                ),
                (
                    trial.acquisition_target if trial is not None else
                    TranscriptAcquisitionTarget(
                        str(profile.policy["firm_id"]), selection=self._selection
                    )
                ),
            ))
        self._budgets[profile.source_id] = budgeted
        self._validated_expected.discard(profile.source_id)
        coverage = "indeterminate"
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
            "checkpoint_reporting_period": (
                checkpoint_period.code if checkpoint_period else ""
            ),
            "expected_reporting_period": expected_period.code,
            "reporting_period_basis": period_basis,
            "candidate_selected_count": len(candidates),
            "run_unique_candidate_count": len(budgeted.candidate_identities),
            "candidate_evaluated_count": 0,
            "candidate_disposition_counts": {},
            "candidate_disposition_samples": [],
            "validation_failure_counts": {},
            "candidate_retrieval_failure_counts": {},
            "candidate_failure_samples": [],
            **self._trial_diagnostics(trial),
        })
        if budgeted.exhausted:
            coverage = "indeterminate"
        if candidate_limit_reached and not final_diagnostics["exhausted_budget"]:
            final_diagnostics["bounds_exhausted"] = True
            final_diagnostics["exhausted_budget"] = "max_candidate_evaluations"
            coverage = "indeterminate"
        classification, summary = self._classify_outcome(
            {**final_diagnostics, "coverage": coverage}, ()
        )
        return DiscoveryPage(tuple(candidates), None, {
            "adapter_id": self.adapter_id,
            "discovery_class": configuration.get("discovery_class"),
            "coverage": coverage,
            "validation_failures": 0,
            "failure_code_counts": {},
            "primary_classification": classification,
            "operator_summary": summary,
            "final_coverage_classification": (
                "coverage_indeterminate" if coverage == "indeterminate" else coverage
            ),
            **final_diagnostics,
        })

    @staticmethod
    def _trial_diagnostics(
        trial: AdapterAcquisitionTrial | None,
    ) -> dict[str, Any]:
        if trial is None:
            return {}
        return {
            "trial_id": trial.trial_id,
            "starting_seed": redact_diagnostic_url(trial.starting_seed),
            "starting_seed_count": len(trial.seeds),
            "starting_seed_samples": [
                redact_diagnostic_url(seed) for seed in trial.seeds[:8]
            ],
            "starting_seed_samples_omitted": len(trial.seeds) > 8,
            "duplicate_seed_count": trial.duplicate_seed_count,
            "seed_kind": trial.seed_kind,
            "seed_source": trial.seed_source,
            "trial_outcome": "pending_validation",
            "effective_selection_mode": (
                trial.acquisition_target.selection.mode.value
            ),
            "requested_date_range": (
                {
                    "start_date": trial.acquisition_target.selection.start_date.isoformat(),
                    "end_date": trial.acquisition_target.selection.end_date.isoformat(),
                }
                if trial.acquisition_target.selection.mode
                == TranscriptSelectionMode.FIRST_IN_DATE_RANGE
                else None
            ),
        }

    @staticmethod
    def _classify_outcome(
        diagnostics: dict[str, Any], failures: tuple[Any, ...]
    ) -> tuple[str, str]:
        if diagnostics.get("bounds_exhausted"):
            budget = str(diagnostics.get("exhausted_budget") or "")
            count = diagnostics.get(
                "candidate_evaluated_count",
                diagnostics.get("candidate_selected_count", 0),
            )
            if not count:
                count = diagnostics.get("candidate_selected_count", 0)
            if budget == "max_candidate_evaluations":
                dispositions = diagnostics.get("candidate_disposition_counts")
                stale = retrieval = validation = 0
                if isinstance(dispositions, dict):
                    stale = sum(int(dispositions.get(code, 0)) for code in (
                        CandidateDispositionCode.CURRENT_CHECKPOINT_PERIOD.value,
                        CandidateDispositionCode.OLDER_THAN_CHECKPOINT.value,
                        CandidateDispositionCode.HISTORICAL_PERIOD.value,
                    ))
                    retrieval = sum(int(dispositions.get(code, 0)) for code in (
                        CandidateFailureCode.HTTP_NOT_FOUND.value,
                        CandidateFailureCode.ACCESS_DENIED.value,
                        CandidateFailureCode.FETCH_TIMEOUT.value,
                        CandidateFailureCode.RETRIEVAL_FAILURE.value,
                    ))
                    validation = sum(int(dispositions.get(code, 0)) for code in (
                        CandidateFailureCode.UNSUPPORTED_CONTENT_TYPE.value,
                        CandidateFailureCode.EMPTY_CONTENT.value,
                        CandidateFailureCode.JAVASCRIPT_REQUIRED.value,
                        CandidateFailureCode.VALIDATION_MISMATCH.value,
                        CandidateDispositionCode.WRONG_FIRM.value,
                        CandidateDispositionCode.CANDIDATE_URL_INVALID.value,
                    ))
                details = []
                if stale:
                    details.append(f"{stale} historical or checkpoint-period")
                if retrieval:
                    details.append(f"{retrieval} retrieval failures")
                if validation:
                    details.append(f"{validation} validation failures")
                return (
                    "discovery_budget_exhausted",
                    "Discovery exhausted the candidate-evaluation budget after selecting "
                    f"{count} ranked unique links"
                    + (f" ({', '.join(details)})." if details else "."),
                )
            if budget == "max_unique_eligible_links_per_page":
                ceiling = diagnostics.get("unique_eligible_link_emergency_ceiling", 1000)
                return (
                    "discovery_emergency_ceiling_exhausted",
                    f"Discovery reached the {ceiling} unique-eligible-link emergency ceiling "
                    "on one page; current-period coverage remains indeterminate.",
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
        dispositions = diagnostics.get("candidate_disposition_counts", {})
        if isinstance(dispositions, dict) and dispositions:
            stale = sum(int(dispositions.get(code, 0)) for code in (
                CandidateDispositionCode.CURRENT_CHECKPOINT_PERIOD.value,
                CandidateDispositionCode.OLDER_THAN_CHECKPOINT.value,
                CandidateDispositionCode.HISTORICAL_PERIOD.value,
            ))
            if stale == sum(int(value) for value in dispositions.values()):
                return (
                    "historical_candidates_only",
                    f"Discovery evaluated {stale} historical or checkpoint-period transcript "
                    "candidates; current-period coverage remains indeterminate.",
                )
        if diagnostics.get("raw_hyperlinks", 0) and not diagnostics.get(
            "eligible_hyperlinks", 0
        ):
            return (
                "no_eligible_links",
                "No eligible transcript links were identified on the configured page.",
            )
        if diagnostics.get("candidate_urls", 0):
            count = diagnostics.get("candidate_selected_count", 0)
            return (
                "candidate_proposals_ready",
                f"Discovery selected {count} ranked transcript candidate"
                f"{'s' if count != 1 else ''} for retrieval.",
            )
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

    def _reporting_period_context(
        self, profile: SourceProfile, retained_anchors: tuple[dict[str, object], ...],
        today: date,
    ) -> tuple[ReportingPeriod | None, ReportingPeriod, str]:
        checkpoint: ReportingPeriod | None = None
        if self._repository is not None:
            current = self._repository.checkpoints()["sources"].get(profile.source_id)
            attempt_id = current.get("attempt_id") if isinstance(current, dict) else None
            if isinstance(attempt_id, str):
                for record in self._repository.history():
                    if record.get("attempt_id") != attempt_id:
                        continue
                    candidate = record.get("candidate")
                    provenance = candidate.get("provenance") if isinstance(candidate, dict) else {}
                    metadata = provenance.get("metadata") if isinstance(provenance, dict) else {}
                    if isinstance(metadata, dict):
                        checkpoint = reporting_period_from_evidence(*(
                            value for value in (
                                metadata.get("link_label"), metadata.get("requested_url"),
                                metadata.get("resolved_url"),
                            ) if isinstance(value, str)
                        ))
                    if checkpoint is not None:
                        return checkpoint, checkpoint.next(), "acquisition_checkpoint"
        for anchor in retained_anchors:
            checkpoint = reporting_period_from_evidence(*(
                value for value in (
                    anchor.get("resolved_url"), anchor.get("requested_url")
                ) if isinstance(value, str)
            ))
            if checkpoint is not None:
                return checkpoint, checkpoint.next(), "retained_anchor"
        expected = ReportingPeriod.from_date(today).previous()
        return None, expected, "latest_completed_calendar_quarter"

    def retrieve(self, profile: SourceProfile, candidate: AdapterCandidate) -> RetrievalResult:
        self._validate_profile(profile)
        metadata = candidate.provenance.metadata
        provider_name = candidate.provenance.provider_identifiers.get("provider")
        if isinstance(provider_name, str) and provider_name:
            if provider_name != profile.configuration.get("provider"):
                raise ContractError("transcript candidate provider changed")
            provider = self._provider_adapters.get((profile.source_id, provider_name))
            if provider is None:
                raise AdapterFailure(
                    FailureClass.MALFORMED_ADAPTER,
                    "provider retrieval requires its dispatched discovery context",
                    False,
                    "missing_provider_context",
                )
            budgeted = self._budgets.get(profile.source_id)
            if budgeted is None:
                raise AdapterFailure(
                    FailureClass.MALFORMED_ADAPTER,
                    "provider retrieval requires a shared run budget",
                    False,
                    "missing_provider_budget",
                )
            if candidate.candidate_id not in budgeted.candidate_identities:
                if (
                    len(budgeted.candidate_identities)
                    >= budgeted.policy.max_candidate_evaluations
                ):
                    budgeted.exhausted = True
                    budgeted.candidate_capacity_exhausted = True
                    budgeted.exhausted_budget = "max_candidate_evaluations"
                    raise AdapterFailure(
                        FailureClass.POLICY_REJECTION,
                        "Transcript candidate evaluation budget is exhausted.",
                        False,
                        "max_candidate_evaluations",
                    )
                budgeted.candidate_identities.add(candidate.candidate_id)
            return provider.retrieve(profile, candidate)
        url = metadata.get("resolved_url")
        label = metadata.get("link_label")
        allowed_hosts = metadata.get("allowed_hosts")
        identity_terms = metadata.get("firm_identity_terms")
        target_value = metadata.get("acquisition_target")
        if not isinstance(target_value, dict):
            raise AdapterFailure(
                FailureClass.MALFORMED_ADAPTER,
                "earnings transcript proposal lacks acquisition target",
                False, "missing_transcript_acquisition_target",
            )
        target = candidate.acquisition_target
        if target is None or target.to_dict() != target_value:
            raise ContractError("transcript candidate acquisition target changed")
        selection = target.selection
        if not isinstance(url, str) or not isinstance(label, str):
            raise AdapterFailure(
                FailureClass.MALFORMED_ADAPTER,
                "earnings transcript proposal lacks retrieval metadata",
                False, "missing_transcript_candidate",
            )
        budgeted = self._budgets.get(profile.source_id)
        if budgeted is None:
            raise AdapterFailure(
                FailureClass.MALFORMED_ADAPTER,
                "earnings transcript retrieval requires a preceding discovery",
                False, "missing_transcript_discovery_context",
            )
        governed = SourceProfile(
            profile.source_id, profile.name, profile.enabled, self.mechanism,
            {
                "listing_urls": [],
                "allowed_hosts": list(allowed_hosts) if isinstance(allowed_hosts, list) else [],
                "candidate_proposals": [{"url": url, "label": label}],
                "maximum_candidates": 1,
                "discover_listing_links": False,
                "authoritative_listing": False,
                "firm_identity_terms": (
                    list(identity_terms) if isinstance(identity_terms, list) else []
                ),
                "checkpoint_reporting_period": (
                    metadata.get("checkpoint_reporting_period") or None
                    if selection.mode == TranscriptSelectionMode.LATEST else None
                ),
                "expected_reporting_period": (
                    metadata.get("expected_reporting_period")
                    if selection.mode == TranscriptSelectionMode.LATEST else None
                ),
                "validated_event_date_evidence": (
                    "artifact_content"
                    if selection.mode == TranscriptSelectionMode.FIRST_IN_DATE_RANGE
                    else "advisory_priority"
                ),
                "defer_date_qualification": (
                    selection.mode == TranscriptSelectionMode.FIRST_IN_DATE_RANGE
                ),
            },
            profile.policy,
        )
        retriever = EarningsCallTranscriptAcquisition(governed, budgeted, self._clock)
        proposal_period = reporting_period_from_evidence(label, url)
        expected_value = metadata.get("expected_reporting_period")
        expected = (
            ReportingPeriod.parse(expected_value)
            if isinstance(expected_value, str) and expected_value else None
        )
        if (
            selection.mode == TranscriptSelectionMode.LATEST
            and
            profile.source_id in self._validated_expected
            and expected is not None and proposal_period is not None
            and proposal_period < expected
        ):
            raise AdapterFailure(
                FailureClass.POLICY_REJECTION,
                "A validated expected-period transcript already takes precedence.",
                False, "historical_candidate_superseded",
            )
        interval_start = (
            date.min
            if selection.mode == TranscriptSelectionMode.FIRST_IN_DATE_RANGE
            else date(2000, 1, 1)
        )
        interval_end = (
            date.max
            if selection.mode == TranscriptSelectionMode.FIRST_IN_DATE_RANGE
            else date.fromisoformat(self._clock()[:10]) + timedelta(days=1)
        )
        assert interval_start is not None
        cache_hits_before = budgeted.cache_hits
        interval = retriever.acquire(IntervalAcquisitionRequest(
            str(profile.policy["firm_id"]), "earnings_transcript",
            interval_start, interval_end,
        ))
        if len(interval.artifacts) == 1:
            envelope = interval.artifacts[0]
            if ReportingPeriod.from_date(envelope.artifact_date) == expected:
                self._validated_expected.add(profile.source_id)
            return replace(envelope.retrieval, diagnostics={
                **envelope.retrieval.diagnostics,
                "candidate_disposition": (
                    retriever.candidate_dispositions[0].code
                    if retriever.candidate_dispositions else "valid_new_artifact"
                ),
                "requested_aliases": list(metadata.get("observed_aliases", [])),
                "validated_position": ReportingPeriod.from_date(
                    envelope.artifact_date
                ).ordinal,
                "validated_revision": f"published-{envelope.artifact_date.isoformat()}",
                "validated_event_date": envelope.artifact_date.isoformat(),
                "effective_selection_mode": selection.mode.value,
                "response_cache_reused": budgeted.cache_hits > cache_hits_before,
                "requested_date_range": (
                    {
                        "start_date": selection.start_date.isoformat(),
                        "end_date": selection.end_date.isoformat(),
                    }
                    if selection.mode == TranscriptSelectionMode.FIRST_IN_DATE_RANGE
                    and selection.start_date is not None and selection.end_date is not None
                    else None
                ),
            })
        if len(interval.artifacts) > 1:
            raise ContractError("single transcript proposal produced multiple artifacts")
        if interval.failures:
            failure = interval.failures[0]
            code = self._candidate_failure_code(failure)
            retrieval_failure = failure.code == "candidate_unavailable"
            raise AdapterFailure(
                FailureClass.TRANSIENT_ADAPTER if retrieval_failure
                else FailureClass.POLICY_REJECTION,
                self._candidate_operator_message(code),
                retrieval_failure,
                code,
            )
        disposition = (
            retriever.candidate_dispositions[0].code
            if retriever.candidate_dispositions else "candidate_validation_mismatch"
        )
        raise AdapterFailure(
            FailureClass.POLICY_REJECTION,
            "Transcript candidate did not establish a new validated artifact.",
            False, disposition,
        )

    @staticmethod
    def _candidate_operator_message(code: str) -> str:
        return {
            CandidateFailureCode.HTTP_NOT_FOUND.value:
                "A transcript candidate was found but returned HTTP 404.",
            CandidateFailureCode.ACCESS_DENIED.value:
                "A transcript candidate was found but access was denied.",
            CandidateFailureCode.FETCH_TIMEOUT.value:
                "A transcript candidate was found but retrieval timed out.",
            CandidateFailureCode.RETRIEVAL_FAILURE.value:
                "A transcript candidate was found but retrieval failed.",
            CandidateFailureCode.UNSUPPORTED_CONTENT_TYPE.value:
                "A transcript candidate was found but its content type is unsupported.",
            CandidateFailureCode.EMPTY_CONTENT.value:
                "A transcript candidate was found but its content was empty.",
            CandidateFailureCode.JAVASCRIPT_REQUIRED.value:
                "A transcript candidate was found but requires JavaScript.",
            CandidateFailureCode.VALIDATION_MISMATCH.value:
                "A transcript candidate was found but did not match transcript validation.",
        }.get(code, "Transcript candidate retrieval failed.")

    def _validate_profile(self, profile: SourceProfile) -> None:
        if profile.mechanism != self.mechanism:
            raise ContractError("earnings transcript source mechanism is invalid")
        if profile.policy.get("artifact_id") != "earnings_transcript":
            raise ContractError("earnings transcript adapter requires canonical artifact")
        if profile.configuration.get("mode") not in self.retrieval_modes:
            raise ContractError("earnings transcript retrieval mode is unsupported")
        provider = profile.configuration.get("provider")
        hint_kind = profile.configuration.get("discovery_hint_kind")
        hint_value = profile.configuration.get("discovery_hint_value")
        if any(value not in (None, "") for value in (provider, hint_kind, hint_value)):
            if not all(isinstance(value, str) and value for value in (
                provider, hint_kind, hint_value
            )):
                raise ContractError(
                    "provider-backed transcript configuration requires provider, "
                    "hint kind, and value"
                )
            if provider != "stockanalysis":
                raise ContractError(f"unknown transcript provider: {provider}")
            if hint_kind != "provider_identifier":
                raise ContractError("StockAnalysis hint kind is unsupported")
