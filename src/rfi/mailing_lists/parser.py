"""Deterministic parsing of retained RFC 5322 evidence."""

from __future__ import annotations

import re
from datetime import UTC
from email import policy
from email.parser import BytesParser
from email.utils import parsedate_to_datetime

from rfi.mailing_lists.contracts import MailingListError, ParsedMessage

_MESSAGE_ID = re.compile(r"<[^<>\s@]+@[^<>\s]+>")
_SUBJECT_PREFIX = re.compile(r"^(?:(?:re|fwd?)\s*:\s*)+", re.IGNORECASE)
_PATCH_PREFIX = re.compile(r"^\s*\[(?:patch|rfc)(?:[^]]*)]\s*", re.IGNORECASE)


def normalize_message_id(value: str | None) -> str | None:
    if value is None:
        return None
    matches = _MESSAGE_ID.findall(value)
    if len(matches) != 1:
        return None
    local, domain = matches[0][1:-1].rsplit("@", 1)
    return f"<{local}@{domain.casefold()}>"


def message_ids(value: str | None) -> tuple[str, ...]:
    return tuple(normalize_message_id(item) or item for item in _MESSAGE_ID.findall(value or ""))


def normalize_subject(value: str) -> str:
    normalized = _SUBJECT_PREFIX.sub("", value.strip())
    normalized = _PATCH_PREFIX.sub("", normalized)
    return " ".join(normalized.casefold().split())


def parse_message(raw: bytes) -> ParsedMessage:
    """Parse headers and searchable text without changing the retained bytes."""
    try:
        message = BytesParser(policy=policy.default).parsebytes(raw)
    except Exception as error:
        raise MailingListError("malformed_message", "archive message cannot be parsed") from error
    warnings = [str(item) for item in message.defects]
    external_id = normalize_message_id(message.get("Message-ID"))
    if message.get("Message-ID") and external_id is None:
        warnings.append("malformed Message-ID")
    subject = str(message.get("Subject", "(no subject)"))
    sender = str(message.get("From", "(unknown sender)"))
    date_value = None
    if message.get("Date"):
        try:
            parsed = parsedate_to_datetime(str(message["Date"]))
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=UTC)
            date_value = parsed.astimezone(UTC).isoformat()
        except (TypeError, ValueError, OverflowError):
            warnings.append("malformed Date")
    parent_ids = message_ids(message.get("In-Reply-To"))
    if len(parent_ids) > 1:
        warnings.append("ambiguous In-Reply-To")
    parent = parent_ids[-1] if parent_ids else None
    references = message_ids(message.get("References"))
    text_parts: list[str] = []
    if message.is_multipart():
        for part in message.walk():
            if part.get_content_maintype() == "multipart":
                continue
            if (
                part.get_content_type() == "text/plain"
                and part.get_content_disposition() != "attachment"
            ):
                try:
                    text_parts.append(str(part.get_content()))
                except (LookupError, UnicodeError):
                    warnings.append("unsupported text encoding")
    elif message.get_content_maintype() == "text":
        try:
            text_parts.append(str(message.get_content()))
        except (LookupError, UnicodeError):
            warnings.append("unsupported text encoding")
    else:
        warnings.append(f"unsupported MIME representation: {message.get_content_type()}")
    return ParsedMessage(
        external_id, subject, normalize_subject(subject), sender, date_value, parent,
        references, "\n".join(text_parts), tuple(sorted(set(warnings)))
    )


def unavailable_ancestor(message_id: str) -> ParsedMessage:
    """Project an explicit non-message tombstone into the relationship graph."""
    return ParsedMessage(
        message_id,
        "[Unavailable Lore ancestor]",
        "unavailable lore ancestor",
        "(message unavailable from Lore)",
        None,
        None,
        (),
        "Lore returned HTTP 404 for this Message-ID from both the configured archive "
        "and the cross-list archive. No email content was synthesized.",
        ("confirmed unavailable Lore ancestor; tombstone is not RFC 5322 content",),
    )
