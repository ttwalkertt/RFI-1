"""Deterministic structural parsing for SEC complete-submission artifacts."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass

from rfi.source_objects.contracts import ParseStatus, SourceInput, SourceObject

_DOCUMENT_START = re.compile(br"(?m)^<DOCUMENT>\r?$\n?")
_DOCUMENT_END = re.compile(br"(?m)^</DOCUMENT>\r?$\n?")
_HEADER_FIELD = re.compile(
    br"(?m)^[ \t]*([A-Z][A-Z0-9 .()/'&-]{2,}):[ \t]*(.*?)\r?$"
)
_DOCUMENT_FIELD = re.compile(br"(?m)^<(TYPE|SEQUENCE|FILENAME|DESCRIPTION)>([^\r\n<]*)")


@dataclass(frozen=True)
class ParseResult:
    """Objects and explicit outcome for one parsed artifact."""

    objects: tuple[SourceObject, ...]
    status: ParseStatus
    message: str | None


def _digest(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _identity(
    artifact_id: str, kind: str, role: str, start: int, end: int, digest: str
) -> str:
    material = f"source-object-v1\0{artifact_id}\0{kind}\0{role}\0{start}\0{end}\0{digest}"
    return f"source-object-{hashlib.sha256(material.encode()).hexdigest()}"


def _object(
    source: SourceInput,
    kind: str,
    role: str,
    ordinal: int,
    start: int,
    end: int,
    parent_id: str | None = None,
    attributes: dict[str, str] | None = None,
) -> SourceObject:
    digest = _digest(source.content[start:end])
    return SourceObject(
        source_object_id=_identity(source.artifact_id, kind, role, start, end, digest),
        document_id=source.document_id,
        artifact_id=source.artifact_id,
        kind=kind,
        role=role,
        ordinal=ordinal,
        byte_start=start,
        byte_end=end,
        content_sha256=digest,
        parent_id=parent_id,
        attributes=attributes or {},
    )


def parse_sec_submission(source: SourceInput) -> ParseResult:
    """Parse bounded SEC SGML structure while retaining exact byte locators."""
    content = source.content
    if not content.startswith(b"<SEC-DOCUMENT>"):
        return ParseResult((), ParseStatus.UNSUPPORTED, "unsupported artifact signature")
    root = _object(source, "artifact", "sec-submission", 0, 0, len(content))
    starts = list(_DOCUMENT_START.finditer(content))
    header_end = starts[0].start() if starts else len(content)
    header = _object(source, "region", "sec-header", 0, 0, header_end, root.source_object_id)
    objects = [root, header]
    field_counts: dict[str, int] = {}
    for match in _HEADER_FIELD.finditer(content, 0, header_end):
        role = match.group(1).decode("ascii", errors="replace").strip().lower()
        role = re.sub(r"[^a-z0-9]+", "-", role).strip("-")
        field_counts[role] = field_counts.get(role, 0) + 1
        value_start, value_end = match.span(2)
        value = match.group(2).decode("utf-8", errors="replace").strip()
        objects.append(
            _object(
                source,
                "field",
                role,
                field_counts[role] - 1,
                value_start,
                value_end,
                header.source_object_id,
                {"value": value},
            )
        )
    incomplete = not starts
    cursor = header_end
    for ordinal, start_match in enumerate(starts):
        end_match = _DOCUMENT_END.search(content, start_match.end())
        if end_match is None:
            block_end = len(content)
            incomplete = True
        else:
            block_end = end_match.end()
        block = _object(
            source,
            "region",
            "embedded-document",
            ordinal,
            start_match.start(),
            block_end,
            root.source_object_id,
        )
        objects.append(block)
        for field_match in _DOCUMENT_FIELD.finditer(content, start_match.end(), block_end):
            name = field_match.group(1).decode("ascii").lower()
            value_start, value_end = field_match.span(2)
            value = field_match.group(2).decode("utf-8", errors="replace").strip()
            objects.append(
                _object(
                    source,
                    "field",
                    f"document-{name}",
                    ordinal,
                    value_start,
                    value_end,
                    block.source_object_id,
                    {"value": value},
                )
            )
        cursor = block_end
    if cursor < len(content):
        tail = content[cursor:].strip()
        if tail not in {b"", b"</SEC-DOCUMENT>"}:
            incomplete = True
    status = ParseStatus.INCOMPLETE if incomplete else ParseStatus.COMPLETE
    message = "missing or unclosed SEC document structure" if incomplete else None
    return ParseResult(tuple(objects), status, message)
