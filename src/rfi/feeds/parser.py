"""Dependency-free bounded RSS 2.0 and Atom normalization."""

from __future__ import annotations

from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from urllib.parse import urljoin
from xml.etree import ElementTree

from rfi.feeds.contracts import FeedEntry, FeedError, ParsedFeed

MAX_FEED_BYTES = 2_000_000
MAX_ENTRIES = 500
MAX_TEXT = 8_192


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1].lower()


def _children(node: ElementTree.Element, name: str) -> list[ElementTree.Element]:
    return [child for child in node if _local(child.tag) == name]


def _child(node: ElementTree.Element, *names: str) -> ElementTree.Element | None:
    wanted = set(names)
    return next((child for child in node if _local(child.tag) in wanted), None)


def _text(node: ElementTree.Element | None) -> str | None:
    if node is None:
        return None
    value = " ".join("".join(node.itertext()).split())[:MAX_TEXT]
    return value or None


def _time(value: str | None) -> str | None:
    if not value:
        return None
    try:
        parsed = parsedate_to_datetime(value)
    except (TypeError, ValueError):
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return value[:128]
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC).isoformat()


def parse_feed(content: bytes, source_url: str) -> ParsedFeed:
    """Validate and normalize one bounded RSS or Atom document."""
    if not isinstance(content, bytes) or not content:
        raise FeedError("feed response was empty")
    if len(content) > MAX_FEED_BYTES:
        raise FeedError(f"feed response exceeds {MAX_FEED_BYTES} bytes")
    try:
        root = ElementTree.fromstring(content)
    except ElementTree.ParseError as error:
        raise FeedError(f"feed XML is malformed: {error}") from error
    kind = _local(root.tag)
    if kind == "rss":
        channel = _child(root, "channel")
        if channel is None:
            raise FeedError("RSS document has no channel")
        title = _text(_child(channel, "title")) or source_url
        entries = tuple(
            _rss_entry(item, source_url)
            for item in _children(channel, "item")[:MAX_ENTRIES]
        )
        return ParsedFeed("rss", title, entries)
    if kind == "feed":
        title = _text(_child(root, "title")) or source_url
        entries = tuple(
            _atom_entry(item, source_url)
            for item in _children(root, "entry")[:MAX_ENTRIES]
        )
        return ParsedFeed("atom", title, entries)
    raise FeedError("document is neither RSS nor Atom")


def _rss_entry(node: ElementTree.Element, source_url: str) -> FeedEntry:
    link = _text(_child(node, "link")) or ""
    guid = _text(_child(node, "guid"))
    entry_key = guid or link
    if not entry_key:
        raise FeedError("RSS item is missing both GUID and link")
    return FeedEntry(
        entry_key,
        _text(_child(node, "title")) or "Untitled entry",
        urljoin(source_url, link) if link else "",
        _time(_text(_child(node, "pubdate", "published"))),
        _time(_text(_child(node, "updated"))),
        _text(_child(node, "author", "creator")),
        _text(_child(node, "description", "summary")),
    )


def _atom_entry(node: ElementTree.Element, source_url: str) -> FeedEntry:
    entry_id = _text(_child(node, "id"))
    links = _children(node, "link")
    link = next(
        (
            item.get("href", "")
            for item in links
            if item.get("rel", "alternate") == "alternate"
        ),
        "",
    )
    link = link or next((item.get("href", "") for item in links), "")
    entry_key = entry_id or link
    if not entry_key:
        raise FeedError("Atom entry is missing both ID and alternate link")
    author = _child(node, "author")
    return FeedEntry(
        entry_key,
        _text(_child(node, "title")) or "Untitled entry",
        urljoin(source_url, link) if link else "",
        _time(_text(_child(node, "published"))),
        _time(_text(_child(node, "updated"))),
        _text(_child(author, "name")) if author is not None else None,
        _text(_child(node, "summary", "content")),
    )
