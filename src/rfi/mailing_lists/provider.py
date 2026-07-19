"""Lore/public-inbox-compatible bounded archive adapters."""

from __future__ import annotations

from dataclasses import dataclass
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

from rfi.mailing_lists.contracts import (
    ArchiveMessage,
    MailingListError,
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
        explicit = [normalize_message_id(item) or item for item in criteria.message_ids]
        if explicit:
            return tuple(explicit[:limit]), len(explicit) > limit
        matches: list[tuple[str, str]] = []
        terms = tuple(item.casefold() for item in criteria.topic_terms)
        query = (criteria.query or "").casefold()
        for external_id, item in self.messages.items():
            parsed = parse_message(item.raw)
            haystack = f"{parsed.subject}\n{parsed.sender}\n{parsed.text_content}".casefold()
            if query and query not in haystack:
                continue
            if terms and not any(term in haystack for term in terms):
                continue
            when = parsed.message_date or ""
            if criteria.date_from and when < criteria.date_from:
                continue
            if criteria.date_through and when > criteria.date_through + "\uffff":
                continue
            matches.append((when, external_id))
        ordered = tuple(item[1] for item in sorted(matches, reverse=True))
        return ordered[:limit], len(ordered) > limit

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


class LoreArchive:
    """Narrow live adapter: explicit Message-IDs plus ancestor closure only."""

    def __init__(self, base_url: str, *, timeout: float = 20.0, max_bytes: int = 5_000_000) -> None:
        if not base_url.startswith("https://") or not base_url.endswith("/"):
            raise MailingListError(
                "invalid_source", "Lore archive URL must be an HTTPS directory URL"
            )
        self.base_url = base_url
        self.timeout = timeout
        self.max_bytes = max_bytes

    @property
    def descendant_enumeration_complete(self) -> bool:
        return False

    def discover(
        self, criteria: SelectionCriteria, limit: int
    ) -> tuple[tuple[str, ...], bool]:
        if not criteria.message_ids:
            raise MailingListError(
                "unsupported_selection",
                "the initial live Lore path requires one or more explicit Message-IDs",
            )
        return (
            tuple(
                normalize_message_id(item) or item for item in criteria.message_ids[:limit]
            ),
            len(criteria.message_ids) > limit,
        )

    def fetch(self, external_message_id: str) -> ArchiveMessage:
        token = external_message_id.strip().removeprefix("<").removesuffix(">")
        location = f"{self.base_url}{quote(token, safe='@')}/raw"
        request = Request(location, headers={"User-Agent": "RFI-1 bounded-mailing-list/1"})
        try:
            with urlopen(request, timeout=self.timeout) as response:
                length = response.headers.get("Content-Length")
                if length and int(length) > self.max_bytes:
                    raise MailingListError(
                        "response_too_large", "archive message exceeds byte limit"
                    )
                raw = response.read(self.max_bytes + 1)
        except (HTTPError, URLError, TimeoutError, OSError) as error:
            raise MailingListError("archive_unavailable", "Lore archive request failed") from error
        if len(raw) > self.max_bytes:
            raise MailingListError("response_too_large", "archive message exceeds byte limit")
        return ArchiveMessage(raw, location)

    def direct_children(
        self, external_message_id: str, limit: int
    ) -> tuple[tuple[str, ...], bool]:
        del external_message_id
        del limit
        return (), True
