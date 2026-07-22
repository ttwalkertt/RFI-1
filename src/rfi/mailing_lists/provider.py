"""Lore/public-inbox-compatible bounded archive adapters."""

from __future__ import annotations

import threading
import time
import xml.etree.ElementTree as ET
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from typing import Any, Callable, Iterator
from urllib.error import HTTPError, URLError
from urllib.parse import quote, unquote, urlencode, urlsplit
from urllib.request import Request, urlopen

from rfi.mailing_lists.contracts import (
    ArchiveMessage,
    LoreTransportPolicy,
    MailingListError,
    MailingListSource,
    SelectionCriteria,
)
from rfi.mailing_lists.parser import normalize_message_id, parse_message


@dataclass
class FixtureMailingListArchive:
    """Finite deterministic public-inbox projection used by acceptance tests."""

    messages: dict[str, ArchiveMessage]

    @property
    def descendant_enumeration_complete(self) -> bool:
        return True

    def discover(
        self, criteria: SelectionCriteria, limit: int
    ) -> tuple[tuple[str, ...], bool]:
        return self.discover_page(criteria, limit, 0)

    def discover_page(
        self, criteria: SelectionCriteria, limit: int, offset: int
    ) -> tuple[tuple[str, ...], bool]:
        explicit = [normalize_message_id(item) or item for item in criteria.message_ids]
        if explicit:
            page = explicit[offset:offset + limit]
            return tuple(page), offset + len(page) < len(explicit)
        matches: list[tuple[str, str]] = []
        terms = tuple(item.casefold() for item in criteria.topic_terms)
        subjects = tuple(item.casefold() for item in criteria.subject_terms)
        participants = tuple(item.casefold() for item in criteria.participant_terms)
        query = (criteria.query or "").casefold()
        for external_id, item in self.messages.items():
            parsed = parse_message(item.raw)
            haystack = f"{parsed.subject}\n{parsed.sender}\n{parsed.text_content}".casefold()
            if query and query not in haystack:
                continue
            if terms and not any(term in haystack for term in terms):
                continue
            if subjects and not any(term in parsed.subject.casefold() for term in subjects):
                continue
            if participants and not any(term in parsed.sender.casefold() for term in participants):
                continue
            when = parsed.message_date or ""
            if criteria.date_from and when < criteria.date_from:
                continue
            if criteria.date_through and when > criteria.date_through + "\uffff":
                continue
            matches.append((when, external_id))
        ordered = tuple(item[1] for item in sorted(matches, reverse=True))
        page = ordered[offset:offset + limit]
        return page, offset + len(page) < len(ordered)

    def fetch(self, external_message_id: str) -> ArchiveMessage:
        try:
            return self.messages[normalize_message_id(external_message_id) or external_message_id]
        except KeyError as error:
            raise MailingListError(
                "missing_connector", f"archive message is unavailable: {external_message_id}"
            ) from error

    def direct_children(
        self, external_message_id: str, limit: int
    ) -> tuple[tuple[str, ...], bool]:
        parent = normalize_message_id(external_message_id) or external_message_id
        children = []
        for message_id, item in self.messages.items():
            if parse_message(item.raw).immediate_parent_id == parent:
                children.append(message_id)
        ordered = tuple(sorted(children))
        return ordered[:limit], len(ordered) > limit


class _SourceGovernor:
    """Coordinate concurrency and request starts for one source inside an RFI process."""

    def __init__(self, policy: LoreTransportPolicy) -> None:
        self._semaphore = threading.BoundedSemaphore(policy.maximum_concurrency)
        self._pace_lock = threading.Lock()
        self._last_started: float | None = None
        self.maximum_observed_concurrency = 0
        self._active = 0
        self._active_lock = threading.Lock()

    @contextmanager
    def request_slot(
        self,
        interval: float,
        monotonic: Callable[[], float],
        sleeper: Callable[[float], None],
    ) -> Iterator[float]:
        self._semaphore.acquire()
        slept = 0.0
        try:
            with self._pace_lock:
                now = monotonic()
                if self._last_started is not None:
                    remaining = interval - (now - self._last_started)
                    if remaining > 0:
                        sleeper(remaining)
                        slept = remaining
                        now = monotonic()
                self._last_started = now
            with self._active_lock:
                self._active += 1
                self.maximum_observed_concurrency = max(
                    self.maximum_observed_concurrency, self._active
                )
            yield slept
        finally:
            with self._active_lock:
                self._active -= 1
            self._semaphore.release()


_GOVERNORS: dict[tuple[str, LoreTransportPolicy], _SourceGovernor] = {}
_GOVERNORS_LOCK = threading.Lock()


def _governor(source: MailingListSource) -> _SourceGovernor:
    key = (source.source_id, source.transport)
    with _GOVERNORS_LOCK:
        return _GOVERNORS.setdefault(key, _SourceGovernor(source.transport))


class LoreArchive:
    """Bounded Lore adapter with Atom discovery and thread enumeration."""

    _ATOM = "{http://www.w3.org/2005/Atom}"
    _THREAD = "{http://purl.org/syndication/thread/1.0}"

    def __init__(
        self,
        source: MailingListSource,
        *,
        opener: Callable[..., Any] = urlopen,
        monotonic: Callable[[], float] = time.monotonic,
        sleeper: Callable[[float], None] = time.sleep,
        wall_clock: Callable[[], datetime] | None = None,
    ) -> None:
        if source.provider != "lore-public-inbox":
            raise MailingListError("invalid_source", "source is not a Lore/public-inbox source")
        if (
            not source.archive_base_url.startswith("https://")
            or not source.archive_base_url.endswith("/")
        ):
            raise MailingListError(
                "invalid_source", "Lore archive URL must be an HTTPS directory URL"
            )
        self.source = source
        self.base_url = source.archive_base_url
        self.policy = source.transport
        self._opener = opener
        self._monotonic = monotonic
        self._sleeper = sleeper
        self._wall_clock = wall_clock or (lambda: datetime.now(UTC))
        self._governor = _governor(source)
        self._request_count = 0
        self._retry_count = 0
        self._pacing_sleep_seconds = 0.0
        self._backoff_sleep_seconds = 0.0
        self._thread_children: dict[str, tuple[str, ...]] = {}
        self._thread_feed_truncated: set[str] = set()

    def usage(self) -> dict[str, int | float | str]:
        return {
            "source_id": self.source.source_id,
            "requests": self._request_count,
            "retries": self._retry_count,
            "pacing_sleep_seconds": round(self._pacing_sleep_seconds, 6),
            "backoff_sleep_seconds": round(self._backoff_sleep_seconds, 6),
            "maximum_observed_concurrency": self._governor.maximum_observed_concurrency,
        }

    @property
    def descendant_enumeration_complete(self) -> bool:
        return True

    def discover(
        self, criteria: SelectionCriteria, limit: int
    ) -> tuple[tuple[str, ...], bool]:
        return self.discover_page(criteria, limit, 0)

    def discover_page(
        self, criteria: SelectionCriteria, limit: int, offset: int
    ) -> tuple[tuple[str, ...], bool]:
        if criteria.message_ids:
            page = criteria.message_ids[offset:offset + limit]
            return (
                tuple(
                    normalize_message_id(item) or item for item in page
                ),
                offset + len(page) < len(criteria.message_ids),
            )
        clauses = []
        if criteria.query:
            clauses.append(f"({criteria.query.strip()})")
        if criteria.topic_terms:
            terms = " OR ".join(
                f'bs:"{self._query_literal(item)}"' for item in criteria.topic_terms
            )
            clauses.append(f"({terms})")
        if criteria.subject_terms:
            subjects = " OR ".join(
                f's:"{self._query_literal(item)}"' for item in criteria.subject_terms
            )
            clauses.append(f"({subjects})")
        if criteria.participant_terms:
            participants = " OR ".join(
                f'f:"{self._query_literal(item)}"' for item in criteria.participant_terms
            )
            clauses.append(f"({participants})")
        if criteria.date_from or criteria.date_through:
            clauses.append(f"d:{criteria.date_from or ''}..{criteria.date_through or ''}")
        if not clauses:
            raise MailingListError(
                "unsupported_selection", "Lore discovery requires a bounded search criterion"
            )
        query = {'q': ' AND '.join(clauses), 'x': 'A'}
        if offset:
            query['o'] = str(offset)
        location = f"{self.base_url}?{urlencode(query)}"
        root = self._atom(self._request(location), "Lore search returned malformed Atom")
        message_ids = tuple(
            message_id
            for entry in root.findall(f"{self._ATOM}entry")
            if (message_id := self._entry_message_id(entry)) is not None
        )
        feed_truncated = any(
            link.get("rel") == "next" for link in root.findall(f"{self._ATOM}link")
        )
        unique = tuple(dict.fromkeys(message_ids))
        return unique[:limit], feed_truncated or len(unique) > limit

    def probe(self) -> dict[str, str]:
        """Verify that the configured archive exposes a structurally valid Atom feed."""
        location = f"{self.base_url}new.atom"
        root = self._atom(self._request(location), "Lore archive did not return a valid Atom feed")
        title = root.findtext(f"{self._ATOM}title", default="").strip()
        updated = root.findtext(f"{self._ATOM}updated", default="").strip()
        if not title:
            raise MailingListError(
                "unsupported_archive", "Lore archive Atom feed has no archive title"
            )
        return {"title": title, "updated": updated, "canonical_url": self.base_url}

    def fetch(self, external_message_id: str) -> ArchiveMessage:
        token = external_message_id.strip().removeprefix("<").removesuffix(">")
        location = f"{self.base_url}{quote(token, safe='@')}/raw"
        try:
            return ArchiveMessage(self._request(location), location)
        except MailingListError as error:
            if (
                error.code not in {"archive_request_rejected", "archive_not_found"}
                or self.base_url.endswith("/all/")
            ):
                raise
            primary_error = error
        fallback_base = "https://lore.kernel.org/all/"
        fallback = f"{fallback_base}{quote(token, safe='@')}/raw"
        try:
            return ArchiveMessage(self._request(fallback), fallback, fallback_base)
        except MailingListError as error:
            if primary_error.code == "archive_not_found" and error.code == "archive_not_found":
                raise MailingListError(
                    "archive_message_not_found",
                    "Lore has no archived message for the required Message-ID",
                    details={
                        "message_id": external_message_id,
                        "attempts": [
                            {"location": location, "http_status": 404},
                            {"location": fallback, "http_status": 404},
                        ],
                    },
                ) from error
            raise

    def _request(self, location: str) -> bytes:
        request = Request(location, headers={"User-Agent": self.policy.user_agent})
        for attempt in range(self.policy.maximum_attempts_per_request):
            try:
                with self._governor.request_slot(
                    self.policy.minimum_request_interval_seconds,
                    self._monotonic,
                    self._sleeper,
                ) as paced:
                    self._pacing_sleep_seconds += paced
                    self._request_count += 1
                    with self._opener(request, timeout=self.policy.timeout_seconds) as response:
                        length = response.headers.get("Content-Length")
                        try:
                            declared_length = int(length) if length else None
                        except (TypeError, ValueError):
                            declared_length = None
                        if (
                            declared_length is not None
                            and declared_length > self.policy.maximum_response_bytes
                        ):
                            raise MailingListError(
                                "response_too_large", "archive message exceeds byte limit"
                            )
                        raw = response.read(self.policy.maximum_response_bytes + 1)
                if len(raw) > self.policy.maximum_response_bytes:
                    raise MailingListError(
                        "response_too_large", "archive message exceeds byte limit"
                    )
                return raw
            except HTTPError as error:
                retry_after = error.headers.get("Retry-After") if error.headers else None
                try:
                    if error.code == 404:
                        raise MailingListError(
                            "archive_not_found",
                            "Lore archive has no resource for the bounded request",
                            details={"location": location, "http_status": 404},
                        ) from error
                    if error.code not in {429, 500, 502, 503, 504}:
                        raise MailingListError(
                            "archive_request_rejected",
                            f"Lore archive rejected the bounded request with HTTP {error.code}",
                            details={"location": location, "http_status": error.code},
                        ) from error
                    code = (
                        "archive_rate_limited" if error.code == 429 else "archive_unavailable"
                    )
                    message = (
                        "Lore archive rate limited the bounded request"
                        if error.code == 429
                        else f"Lore archive returned transient HTTP {error.code}"
                    )
                    if attempt + 1 >= self.policy.maximum_attempts_per_request:
                        raise MailingListError(code, message, retryable=True) from error
                finally:
                    error.close()
                self._retry(attempt, retry_after)
            except (URLError, TimeoutError, OSError) as error:
                if attempt + 1 >= self.policy.maximum_attempts_per_request:
                    raise MailingListError(
                        "archive_unavailable",
                        "Lore archive transport failed after bounded retries",
                        retryable=True,
                    ) from error
                self._retry(attempt, None)
        raise AssertionError("unreachable Lore request state")

    @classmethod
    def _atom(cls, raw: bytes, message: str) -> ET.Element:
        try:
            root = ET.fromstring(raw)
        except ET.ParseError as error:
            raise MailingListError("malformed_archive_response", message) from error
        if root.tag != f"{cls._ATOM}feed":
            raise MailingListError("unsupported_archive", message)
        return root

    @staticmethod
    def _query_literal(value: str) -> str:
        return value.strip().replace("\\", "\\\\").replace('"', '\\"')

    @staticmethod
    def _message_id_from_url(value: str | None) -> str | None:
        if not value:
            return None
        path = urlsplit(value).path.rstrip("/")
        token = unquote(path.rsplit("/", 1)[-1]) if path else ""
        return normalize_message_id(f"<{token}>")

    @classmethod
    def _entry_message_id(cls, entry: ET.Element) -> str | None:
        for link in entry.findall(f"{cls._ATOM}link"):
            if link.get("rel", "alternate") == "alternate":
                message_id = cls._message_id_from_url(link.get("href"))
                if message_id:
                    return message_id
        return None

    def _retry(self, attempt: int, retry_after: str | None) -> None:
        self._retry_count += 1
        exponential = min(
            self.policy.backoff_initial_seconds * (2**attempt),
            self.policy.backoff_maximum_seconds,
        )
        delay = max(exponential, self._retry_after_seconds(retry_after))
        delay = min(delay, self.policy.backoff_maximum_seconds)
        if delay > 0:
            self._sleeper(delay)
            self._backoff_sleep_seconds += delay

    def _retry_after_seconds(self, value: str | None) -> float:
        if not value:
            return 0.0
        try:
            return max(0.0, float(value.strip()))
        except ValueError:
            try:
                target = parsedate_to_datetime(value)
                if target.tzinfo is None:
                    target = target.replace(tzinfo=UTC)
                return max(0.0, (target - self._wall_clock()).total_seconds())
            except (TypeError, ValueError, OverflowError):
                return 0.0

    def direct_children(
        self, external_message_id: str, limit: int
    ) -> tuple[tuple[str, ...], bool]:
        parent = normalize_message_id(external_message_id) or external_message_id
        if parent not in self._thread_children:
            token = parent.strip().removeprefix("<").removesuffix(">")
            location = f"{self.base_url}{quote(token, safe='@')}/t.atom"
            try:
                raw = self._request(location)
            except MailingListError as error:
                if (
                    error.code not in {"archive_request_rejected", "archive_not_found"}
                    or self.base_url.endswith("/all/")
                ):
                    raise
                location = (
                    "https://lore.kernel.org/all/"
                    f"{quote(token, safe='@')}/t.atom"
                )
                raw = self._request(location)
            root = self._atom(raw, "Lore thread endpoint returned malformed Atom")
            children: dict[str, list[str]] = {}
            all_ids: set[str] = set()
            for entry in root.findall(f"{self._ATOM}entry"):
                message_id = self._entry_message_id(entry)
                if not message_id:
                    continue
                all_ids.add(message_id)
                relation = entry.find(f"{self._THREAD}in-reply-to")
                relation_parent = self._message_id_from_url(
                    relation.get("href") if relation is not None else None
                )
                if relation_parent:
                    children.setdefault(relation_parent, []).append(message_id)
            truncated = any(
                link.get("rel") == "next" for link in root.findall(f"{self._ATOM}link")
            )
            for message_id in all_ids | set(children):
                self._thread_children[message_id] = tuple(
                    sorted(dict.fromkeys(children.get(message_id, [])))
                )
                if truncated:
                    self._thread_feed_truncated.add(message_id)
            self._thread_children.setdefault(parent, ())
        result = self._thread_children[parent]
        return result[:limit], parent in self._thread_feed_truncated or len(result) > limit
