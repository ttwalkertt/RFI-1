"""Transcript-specific IQA over repository-owned artifact read contracts."""

from __future__ import annotations

import hashlib
import re
import sqlite3
from collections import Counter
from dataclasses import asdict
from typing import Any

from rfi.artifacts import ArtifactOrder, ArtifactQuery, ArtifactQueryService
from rfi.research.contracts import (
    CorpusDescription,
    EvidenceExcerpt,
    ResearchError,
    SearchHit,
    SearchResult,
    TranscriptDocument,
    TranscriptScope,
    TranscriptSegment,
)

_TOKEN = re.compile(r"[A-Za-z0-9][A-Za-z0-9+.-]{1,}")
_STOP_WORDS = {
    "about", "across", "after", "again", "against", "also", "and", "are",
    "business", "calls", "change", "changed", "did", "does", "earnings", "for",
    "from", "has", "have", "how", "into", "management", "more", "most", "over",
    "said", "say", "than", "that", "the", "their", "this", "through", "transcript",
    "transcripts", "was", "what", "when", "where", "which", "with",
}


class TranscriptKnowledgeAccess:
    """Rebuildable paragraph search and exact expansion over retained transcript truth."""

    def __init__(self, artifacts: ArtifactQueryService, scope: TranscriptScope) -> None:
        self._artifacts = artifacts
        self.scope = scope
        self._documents: dict[str, TranscriptDocument] = {}
        self._segments: dict[str, TranscriptSegment] = {}
        self._by_document: dict[str, list[TranscriptSegment]] = {}
        self._details: dict[str, Any] = {}
        self._snapshot = ""
        self._index = sqlite3.connect(":memory:")
        self._build()

    @property
    def repository_snapshot(self) -> str:
        """Return the public artifact-query snapshot used for this access generation."""
        return self._snapshot

    def close(self) -> None:
        """Release the disposable in-memory access index."""
        self._index.close()

    def describe_corpus(self) -> CorpusDescription:
        """Return corpus orientation plus the model-facing data dictionary."""
        documents = tuple(sorted(
            self._documents.values(), key=lambda item: (item.event_date, item.document_id)
        ))
        artifact_counts = Counter(item.canonical_artifact_id for item in documents)
        event_counts = Counter(item.event_kind or "unavailable" for item in documents)
        dates = [item.event_date for item in documents]
        gaps = []
        if any(not item.speaker_context_available for item in documents):
            gaps.append(
                "speaker labels were not retained in one or more transcript artifacts; "
                "do not attribute those passages to a named speaker"
            )
        if any(item.event_kind is None for item in documents):
            gaps.append(
                "repository event-kind diagnostics are absent on historical observations; "
                "canonical artifact classification remains authoritative"
            )
        gaps.append(
            "retained-artifact coverage is bounded and does not prove that every call or "
            "management event was acquired"
        )
        return CorpusDescription(
            authority="repository-retained immutable transcript evidence",
            repository_snapshot=self._snapshot,
            scope=self.scope,
            documents=documents,
            segment_count=len(self._segments),
            date_from=min(dates) if dates else None,
            date_through=max(dates) if dates else None,
            canonical_artifact_counts=dict(sorted(artifact_counts.items())),
            event_kind_counts=dict(sorted(event_counts.items())),
            metadata_gaps=tuple(gaps),
            capabilities={
                "describe_corpus": (
                    "Orient to retained documents, dates, classifications, and metadata gaps."
                ),
                "search_transcripts": (
                    "Lexically search retained paragraph segments with date/document filters; "
                    "results are candidates, not citations."
                ),
                "expand_segments": (
                    "Read verified exact retained-byte context and provenance; only expanded "
                    "segment IDs may be cited."
                ),
                "inspect_document": (
                    "Read an ordered bounded paragraph window when search snippets lack context."
                ),
            },
        )

    def search(
        self,
        query: str,
        *,
        match: str = "any",
        order: str = "relevance",
        date_from: str | None = None,
        date_through: str | None = None,
        document_ids: tuple[str, ...] = (),
        limit: int = 12,
        max_per_document: int = 3,
    ) -> SearchResult:
        """Return diverse compact lexical candidates without fabricating semantic recall."""
        if match not in {"any", "all"}:
            raise ResearchError("search match must be 'any' or 'all'")
        if order not in {"relevance", "oldest", "latest"}:
            raise ResearchError("search order must be 'relevance', 'oldest', or 'latest'")
        if not 1 <= limit <= 12 or not 1 <= max_per_document <= 4:
            raise ResearchError("search limits are outside the governed bounds")
        terms = self._terms(query)
        if not terms:
            raise ResearchError("search query has no indexable terms")
        operator = " OR " if match == "any" else " AND "
        expression = operator.join(f'"{term}"' for term in terms)
        clauses = ["segment_fts MATCH ?"]
        parameters: list[Any] = [expression]
        if date_from:
            clauses.append("segments.event_date >= ?")
            parameters.append(date_from)
        if date_through:
            clauses.append("segments.event_date <= ?")
            parameters.append(date_through)
        if document_ids:
            unknown = set(document_ids) - set(self._documents)
            if unknown:
                raise ResearchError(f"unknown document ID: {sorted(unknown)[0]}")
            placeholders = ",".join("?" for _ in document_ids)
            clauses.append(f"segments.document_id IN ({placeholders})")
            parameters.extend(document_ids)
        where = " AND ".join(clauses)
        total = int(self._index.execute(
            "SELECT count(*) FROM segment_fts JOIN segments "
            "ON segments.rowid=segment_fts.rowid WHERE " + where,
            parameters,
        ).fetchone()[0])
        ordering = {
            "relevance": "rank,segments.event_date,segments.segment_id",
            "oldest": (
                "segments.event_date,segments.document_id,segments.ordinal,rank"
            ),
            "latest": (
                "segments.event_date DESC,segments.document_id,segments.ordinal,rank"
            ),
        }[order]
        rows = self._index.execute(
            "SELECT segments.segment_id,bm25(segment_fts,1.0,0.15) AS rank "
            "FROM segment_fts JOIN segments ON segments.rowid=segment_fts.rowid "
            "WHERE " + where + " ORDER BY " + ordering + " "
            "LIMIT 200",
            parameters,
        ).fetchall()
        selected: list[SearchHit] = []
        per_document: Counter[str] = Counter()
        for segment_id, rank in rows:
            segment = self._segments[str(segment_id)]
            if per_document[segment.document_id] >= max_per_document:
                continue
            per_document[segment.document_id] += 1
            selected.append(SearchHit(
                segment.segment_id,
                segment.document_id,
                segment.title,
                segment.event_date,
                segment.canonical_artifact_id,
                segment.event_kind,
                segment.ordinal,
                round(-float(rank), 6),
                self._excerpt(segment.text, terms),
            ))
            if len(selected) >= limit:
                break
        note = (
            "No retained paragraph matched this lexical search. This is a meaningful failed "
            "search, but not proof that the concept is absent under every possible wording."
            if not selected
            else "Search covers all indexed retained paragraphs in the declared corpus snapshot."
        )
        return SearchResult(
            query,
            terms,
            order,
            tuple(selected),
            total,
            total > len(selected),
            note,
        )

    def expand(
        self, segment_ids: tuple[str, ...], *, context_radius: int = 1
    ) -> tuple[EvidenceExcerpt, ...]:
        """Return exact verified neighboring context for selected segment identities."""
        if not segment_ids or len(segment_ids) > 4:
            raise ResearchError("expand requires between one and four segment IDs")
        if not 0 <= context_radius <= 1:
            raise ResearchError("context radius must be zero or one")
        output = []
        for segment_id in dict.fromkeys(segment_ids):
            if segment_id not in self._segments:
                raise ResearchError(f"unknown segment ID: {segment_id}")
            segment = self._segments[segment_id]
            siblings = self._by_document[segment.document_id]
            index = segment.ordinal - 1
            selected = siblings[
                max(0, index - context_radius):min(len(siblings), index + context_radius + 1)
            ]
            start, end = selected[0].byte_start, selected[-1].byte_end
            content = self._artifacts.content(segment.document_id).content
            exact = content[start:end]
            detail = self._details[segment.document_id]
            output.append(EvidenceExcerpt(
                evidence_id=segment.segment_id,
                document_id=segment.document_id,
                artifact_id=segment.artifact_id,
                title=segment.title,
                event_date=segment.event_date,
                canonical_artifact_id=segment.canonical_artifact_id,
                event_kind=segment.event_kind,
                speaker_label=segment.speaker_label,
                context_byte_start=start,
                context_byte_end=end,
                context_sha256=hashlib.sha256(exact).hexdigest(),
                text=exact.decode("utf-8", "replace").strip(),
                provenance_locations=tuple(
                    item.location for item in detail.provenance_locations
                ),
            ))
        return tuple(output)

    def inspect_document(
        self, document_id: str, *, start_ordinal: int = 1, count: int = 8
    ) -> tuple[TranscriptSegment, ...]:
        """Read one bounded ordered window without exposing artifact storage layout."""
        if document_id not in self._by_document:
            raise ResearchError(f"unknown document ID: {document_id}")
        if start_ordinal < 1 or not 1 <= count <= 5:
            raise ResearchError("document window is outside the governed bounds")
        segments = self._by_document[document_id]
        return tuple(segments[start_ordinal - 1:start_ordinal - 1 + count])

    def tool_schemas(self) -> tuple[dict[str, Any], ...]:
        """Return the complete allowlisted capability surface for a model adapter."""
        return (
            self._tool("describe_corpus", "Orient to the retained transcript corpus.", {
                "type": "object", "properties": {}, "additionalProperties": False,
                "required": [],
            }),
            self._tool(
                "search_transcripts",
                "Search retained paragraph candidates. Search hits are not citable until expanded.",
                {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string"},
                        "match": {"type": "string", "enum": ["any", "all"]},
                        "order": {
                            "type": "string",
                            "enum": ["relevance", "oldest", "latest"],
                        },
                        "date_from": {"type": ["string", "null"]},
                        "date_through": {"type": ["string", "null"]},
                        "document_ids": {"type": "array", "items": {"type": "string"}},
                        "limit": {"type": "integer", "minimum": 1, "maximum": 12},
                        "max_per_document": {
                            "type": "integer", "minimum": 1, "maximum": 4,
                        },
                    },
                    "required": [
                        "query", "match", "order", "date_from", "date_through",
                        "document_ids", "limit", "max_per_document",
                    ],
                    "additionalProperties": False,
                },
            ),
            self._tool(
                "expand_segments",
                "Expand candidates to exact citable retained evidence and provenance.",
                {
                    "type": "object",
                    "properties": {
                        "segment_ids": {
                            "type": "array", "items": {"type": "string"},
                            "minItems": 1, "maxItems": 4,
                        },
                        "context_radius": {"type": "integer", "minimum": 0, "maximum": 1},
                    },
                    "required": ["segment_ids", "context_radius"],
                    "additionalProperties": False,
                },
            ),
            self._tool(
                "inspect_document",
                "Read a bounded ordered paragraph window from one retained document.",
                {
                    "type": "object",
                    "properties": {
                        "document_id": {"type": "string"},
                        "start_ordinal": {"type": "integer", "minimum": 1},
                        "count": {"type": "integer", "minimum": 1, "maximum": 5},
                    },
                    "required": ["document_id", "start_ordinal", "count"],
                    "additionalProperties": False,
                },
            ),
        )

    def dispatch(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        """Execute one allowlisted tool call and return JSON-shaped public contracts."""
        if name == "describe_corpus":
            value = asdict(self.describe_corpus())
            value["documents"] = [
                {
                    key: item[key]
                    for key in (
                        "document_id", "artifact_id", "title", "firm_id",
                        "canonical_artifact_id", "event_date", "event_kind",
                        "segment_count", "speaker_context_available",
                    )
                }
                for item in value["documents"]
            ]
            value["progressive_disclosure_note"] = (
                "Document checksums, byte sizes, provider, and provenance are withheld from "
                "orientation; exact expansion returns them when evidence is inspected."
            )
            return value
        if name == "search_transcripts":
            result = self.search(
                str(arguments["query"]),
                match=str(arguments["match"]),
                order=str(arguments["order"]),
                date_from=arguments.get("date_from"),
                date_through=arguments.get("date_through"),
                document_ids=tuple(arguments["document_ids"]),
                limit=int(arguments["limit"]),
                max_per_document=int(arguments["max_per_document"]),
            )
            return asdict(result)
        if name == "expand_segments":
            excerpts = self.expand(
                tuple(arguments["segment_ids"]),
                context_radius=int(arguments["context_radius"]),
            )
            return {"evidence": [asdict(item) for item in excerpts]}
        if name == "inspect_document":
            segments = self.inspect_document(
                str(arguments["document_id"]),
                start_ordinal=int(arguments["start_ordinal"]),
                count=int(arguments["count"]),
            )
            return {"segments": [asdict(item) for item in segments]}
        raise ResearchError(f"unknown investigation tool: {name}")

    def _build(self) -> None:
        self._index.execute(
            "CREATE TABLE segments("
            "segment_id TEXT UNIQUE,document_id TEXT,event_date TEXT,ordinal INTEGER)"
        )
        self._index.execute(
            "CREATE VIRTUAL TABLE segment_fts USING fts5(content,title,tokenize='porter unicode61')"
        )
        query = ArtifactQuery(
            firm_ids=self.scope.firm_ids,
            canonical_artifact_ids=self.scope.canonical_artifact_ids,
            source_effective_from=self.scope.source_effective_from,
            source_effective_through=self.scope.source_effective_through,
            order=ArtifactOrder.OLDEST,
            limit=100,
        )
        page = self._artifacts.query(query)
        self._snapshot = page.repository_snapshot
        if page.next_cursor:
            raise ResearchError("transcript scope exceeds the current bounded 100-document slice")
        for summary in page.items:
            detail = self._artifacts.detail(summary.document_id)
            retained = self._artifacts.content(summary.document_id)
            diagnostics = detail.observation.diagnostics
            event_date = str(
                diagnostics.get("trusted_event_date")
                or diagnostics.get("validated_event_date")
                or summary.source_effective.value[:10]
            )
            provider_metadata = diagnostics.get("provider_metadata", {})
            if not isinstance(provider_metadata, dict):
                provider_metadata = {}
            title = str(
                provider_metadata.get("document_title")
                or self._header(retained.content).get("Title")
                or summary.display_title
            )
            segments = self._segment(
                retained.content,
                summary.document_id,
                summary.artifact_id,
                retained.checksum_sha256,
                title,
                event_date,
                str(summary.canonical_artifact_id),
                diagnostics.get("transcript_event_kind"),
            )
            locations = tuple(item.location for item in detail.provenance_locations)
            document = TranscriptDocument(
                summary.document_id,
                summary.artifact_id,
                title,
                str(summary.firm_id),
                str(summary.canonical_artifact_id),
                event_date,
                self._optional_text(diagnostics.get("transcript_event_kind")),
                summary.provider,
                retained.checksum_sha256,
                len(retained.content),
                len(segments),
                any(item.speaker_label for item in segments),
                locations,
            )
            self._documents[document.document_id] = document
            self._by_document[document.document_id] = list(segments)
            self._details[document.document_id] = detail
            for segment in segments:
                cursor = self._index.execute(
                    "INSERT INTO segments("
                    "segment_id,document_id,event_date,ordinal) VALUES (?,?,?,?)",
                    (
                        segment.segment_id, segment.document_id,
                        segment.event_date, segment.ordinal,
                    ),
                )
                self._index.execute(
                    "INSERT INTO segment_fts(rowid,content,title) VALUES (?,?,?)",
                    (cursor.lastrowid, segment.text, segment.title),
                )
                self._segments[segment.segment_id] = segment
        self._index.commit()

    @staticmethod
    def _segment(
        content: bytes,
        document_id: str,
        artifact_id: str,
        artifact_sha256: str,
        title: str,
        event_date: str,
        canonical_artifact_id: str,
        event_kind: Any,
    ) -> tuple[TranscriptSegment, ...]:
        lines = content.splitlines(keepends=True)
        offset = 0
        body = False
        segments = []
        for raw in lines:
            start, end = offset, offset + len(raw)
            offset = end
            text = raw.decode("utf-8", "replace").strip()
            if not body:
                if not text:
                    body = True
                continue
            if not text:
                continue
            digest = hashlib.sha256(content[start:end]).hexdigest()
            identity = hashlib.sha256(
                f"{artifact_id}:{start}:{end}:{digest}".encode()
            ).hexdigest()
            segments.append(TranscriptSegment(
                f"transcript-segment-{identity}",
                document_id,
                artifact_id,
                len(segments) + 1,
                start,
                end,
                digest,
                text,
                event_date,
                title,
                canonical_artifact_id,
                TranscriptKnowledgeAccess._optional_text(event_kind),
                None,
            ))
        if not segments:
            raise ResearchError(
                f"retained transcript has no addressable body paragraphs: {document_id}"
            )
        if hashlib.sha256(content).hexdigest() != artifact_sha256:
            raise ResearchError(f"artifact checksum mismatch during access build: {document_id}")
        return tuple(segments)

    @staticmethod
    def _header(content: bytes) -> dict[str, str]:
        first = content.split(b"\n\n", 1)[0].decode("utf-8", "replace")
        output = {}
        for line in first.splitlines():
            if ": " in line:
                key, value = line.split(": ", 1)
                output[key] = value
        return output

    @staticmethod
    def _terms(query: str) -> tuple[str, ...]:
        values = []
        for token in _TOKEN.findall(query.casefold()):
            token = token.strip(".-")
            if len(token) > 1 and token not in _STOP_WORDS and token not in values:
                values.append(token)
        return tuple(values[:12])

    @staticmethod
    def _excerpt(text: str, terms: tuple[str, ...]) -> str:
        lowered = text.casefold()
        positions = [lowered.find(term) for term in terms if lowered.find(term) >= 0]
        start = max(0, min(positions) - 140) if positions else 0
        end = min(len(text), start + 360)
        prefix = "…" if start else ""
        suffix = "…" if end < len(text) else ""
        return prefix + text[start:end] + suffix

    @staticmethod
    def _optional_text(value: Any) -> str | None:
        return value if isinstance(value, str) and value else None

    @staticmethod
    def _tool(name: str, description: str, parameters: dict[str, Any]) -> dict[str, Any]:
        return {
            "type": "function",
            "name": name,
            "description": description,
            "parameters": parameters,
            "strict": True,
        }
