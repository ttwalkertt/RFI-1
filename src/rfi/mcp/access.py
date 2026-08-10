"""Disposable transcript access generation with explicit health and exact evidence reads."""

from __future__ import annotations

import base64
import hashlib
import json
import re
import sqlite3
from collections import Counter
from dataclasses import asdict, replace
from typing import Any

from rfi.artifacts import (
    ArtifactOrder,
    ArtifactQuery,
    ArtifactQueryError,
    ArtifactQueryService,
)
from rfi.mcp.contracts import (
    AccessBound,
    AccessDiagnostic,
    AccessHealth,
    CAPABILITY_VERSION,
    GenerationIdentity,
    McpAccessError,
    Outcome,
    SearchCandidate,
    TraceContext,
    TranscriptProjection,
)

_TOKEN = re.compile(r"[A-Za-z0-9][A-Za-z0-9+.-]{1,}")
_STOP_WORDS = {
    "about", "across", "after", "again", "against", "also", "and", "are",
    "business", "calls", "change", "changed", "did", "does", "earnings", "for",
    "from", "has", "have", "how", "into", "management", "more", "most", "over",
    "said", "say", "than", "that", "the", "their", "this", "through", "transcript",
    "transcripts", "was", "what", "when", "where", "which", "with",
}
_BUILD_DOCUMENT_LIMIT = 100
_INTERNAL_CANDIDATE_LIMIT = 200
_SEARCH_RESULT_LIMIT = 50
_DIVERSITY_LIMIT = 10
_WINDOW_LIMIT = 20
_ARTIFACT_RANGE_LIMIT = 65_536


class TranscriptAccessGeneration:
    """Transcript-only lexical access whose identity never becomes retained authority."""

    capability_id = "transcript.lexical.v1"

    def __init__(
        self,
        artifacts: ArtifactQueryService,
        *,
        firm_ids: tuple[str, ...],
        canonical_artifact_ids: tuple[str, ...],
        source_effective_from: str | None = None,
        source_effective_through: str | None = None,
    ) -> None:
        self.artifacts = artifacts
        self.firm_ids = firm_ids
        self.canonical_artifact_ids = canonical_artifact_ids
        self.source_effective_from = source_effective_from
        self.source_effective_through = source_effective_through
        self._documents: dict[str, dict[str, Any]] = {}
        self._segments: dict[str, TranscriptProjection] = {}
        self._by_document: dict[str, list[TranscriptProjection]] = {}
        self._index = sqlite3.connect(":memory:")
        self._authority_snapshot = "unavailable"
        self._health = AccessHealth.UNAVAILABLE
        self._eligible = 0
        self._build_outcome = Outcome.OK
        self._diagnostics: list[AccessDiagnostic] = []
        self._generation_id = "transcript-access-unavailable"
        self._build()

    def close(self) -> None:
        """Release the replaceable process-local index."""
        self._index.close()

    @property
    def health(self) -> AccessHealth:
        return self._health

    @property
    def authority_snapshot(self) -> str:
        return self._authority_snapshot

    def identity(self) -> GenerationIdentity:
        """Return the complete externally visible generation record."""
        return GenerationIdentity(
            capability_id=self.capability_id,
            capability_version=CAPABILITY_VERSION,
            generation_id=self._generation_id,
            authority_snapshot=self._authority_snapshot,
            health=self._health,
            eligible_document_count=self._eligible,
            indexed_document_count=len(self._documents),
            indexed_segment_count=len(self._segments),
            build_outcome=self._build_outcome,
            build_bounds=(
                AccessBound(
                    "build_document_limit",
                    _BUILD_DOCUMENT_LIMIT,
                    self._eligible > _BUILD_DOCUMENT_LIMIT,
                    "Documents beyond this limit are omitted with a partial outcome.",
                ),
                AccessBound(
                    "artifact_query_page_limit",
                    100,
                    self._eligible > 100,
                    "Repository catalog pages are traversed until the build bound is reached.",
                ),
                AccessBound(
                    "artifact_diagnostic_limit_per_page",
                    100,
                    any(
                        item.code == "artifact_diagnostics_truncated"
                        for item in self._diagnostics
                    ),
                    "Additional repository diagnostics are not hidden; truncation is diagnosed.",
                ),
            ),
            diagnostics=tuple(self._diagnostics),
        )

    def ensure_current(self) -> None:
        """Fail closed when repository authority no longer matches the generation."""
        if self._health == AccessHealth.CORRUPT:
            raise McpAccessError("access_corrupt", "transcript access is corrupt")
        if self._health == AccessHealth.UNAVAILABLE:
            raise McpAccessError("access_unavailable", "transcript access is unavailable")
        try:
            current = self.artifacts.repository_snapshot()
        except ArtifactQueryError as error:
            raise self._artifact_error(error) from error
        if current != self._authority_snapshot:
            self._health = AccessHealth.STALE
        if self._health == AccessHealth.STALE:
            raise McpAccessError(
                "access_stale",
                "repository authority changed after transcript access generation build",
                category="stale_access",
                retryable=True,
                details={
                    "generation_snapshot": self._authority_snapshot,
                    "repository_snapshot": current,
                },
            )

    def corpus(
        self, *, limit: int, cursor: str | None, trace: TraceContext
    ) -> dict[str, Any]:
        """Return one bounded transcript corpus page and explicit coverage facts."""
        self.ensure_current()
        if not 1 <= limit <= 100:
            raise McpAccessError("invalid_request", "corpus limit must be between 1 and 100")
        offset = self._decode_cursor(cursor)
        documents = sorted(
            self._documents.values(), key=lambda item: (item["event_date"], item["document_id"])
        )
        selected = documents[offset:offset + limit]
        next_cursor = (
            self._encode_cursor(offset + len(selected))
            if offset + len(selected) < len(documents)
            else None
        )
        trace.returned_count = len(selected)
        trace.total_count = len(documents)
        trace.cursor = cursor
        trace.next_cursor = next_cursor
        trace.truncated = next_cursor is not None or self._build_outcome == Outcome.PARTIAL
        trace.bounds.append({
            "name": "corpus_page_limit",
            "value": limit,
            "applied": len(documents) > limit,
        })
        for item in selected:
            trace.referenced_document_ids.add(item["document_id"])
            trace.referenced_artifact_ids.add(item["artifact_id"])
            trace.referenced_observation_ids.add(item["observation_id"])
        dates = [item["event_date"] for item in documents]
        return {
            "scope": self.scope(),
            "documents": selected,
            "inventory": {
                "eligible_documents": self._eligible,
                "indexed_documents": len(documents),
                "indexed_segments": len(self._segments),
                "date_from": min(dates) if dates else None,
                "date_through": max(dates) if dates else None,
            },
            "metadata_gaps": self._metadata_gaps(),
            "coverage": {
                "state": "indeterminate",
                "basis": (
                    "retained inventory only; historical acquisition completeness "
                    "is not aggregated"
                ),
            },
            "page": {
                "limit": limit,
                "returned": len(selected),
                "total_matching": len(documents),
                "next_cursor": next_cursor,
                "truncated": trace.truncated,
                "bounds_applied": trace.bounds,
            },
        }

    def search(self, arguments: dict[str, Any], trace: TraceContext) -> dict[str, Any]:
        """Return bounded lexical candidates with all internal and diversity bounds exposed."""
        self.ensure_current()
        query = arguments.get("query")
        match = arguments.get("match", "any")
        order = arguments.get("order", "relevance")
        limit = arguments.get("limit", 12)
        max_per_document = arguments.get("max_per_document", 3)
        if not isinstance(query, str):
            raise McpAccessError("invalid_request", "query must be a string")
        if match not in {"any", "all"}:
            raise McpAccessError("unsupported_query", "match must be any or all")
        if order not in {"relevance", "oldest", "latest"}:
            raise McpAccessError(
                "unsupported_order", "order must be relevance, oldest, or latest"
            )
        if (
            isinstance(limit, bool)
            or not isinstance(limit, int)
            or not 1 <= limit <= _SEARCH_RESULT_LIMIT
        ):
            raise McpAccessError("invalid_request", "limit must be between 1 and 50")
        if (
            isinstance(max_per_document, bool)
            or not isinstance(max_per_document, int)
            or not 1 <= max_per_document <= _DIVERSITY_LIMIT
        ):
            raise McpAccessError("invalid_request", "max_per_document must be between 1 and 10")
        terms = self._terms(query)
        if not terms:
            raise McpAccessError("invalid_request", "query has no indexable terms")
        self._validate_scope_filters(arguments)
        document_ids = tuple(arguments.get("document_ids") or ())
        unknown = set(document_ids) - set(self._documents)
        if unknown:
            raise McpAccessError(
                "unknown_object",
                f"unknown transcript document: {sorted(unknown)[0]}",
                category="invalid_scope",
            )
        clauses = ["segment_fts MATCH ?"]
        operator = " OR " if match == "any" else " AND "
        parameters: list[Any] = [operator.join(f'"{term}"' for term in terms)]
        for key, sql in (
            ("date_from", "segments.event_date >= ?"),
            ("date_through", "segments.event_date <= ?"),
        ):
            value = arguments.get(key)
            if value is not None:
                if not isinstance(value, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
                    raise McpAccessError("invalid_request", f"{key} must use YYYY-MM-DD")
                clauses.append(sql)
                parameters.append(value)
        if document_ids:
            clauses.append(
                "segments.document_id IN ("
                + ",".join("?" for _ in document_ids)
                + ")"
            )
            parameters.extend(document_ids)
        where = " AND ".join(clauses)
        try:
            total = int(self._index.execute(
                "SELECT count(*) FROM segment_fts JOIN segments "
                "ON segments.rowid=segment_fts.rowid WHERE " + where,
                parameters,
            ).fetchone()[0])
            ordering = {
                "relevance": "rank,segments.event_date,segments.segment_id",
                "oldest": "segments.event_date,segments.document_id,segments.ordinal,rank",
                "latest": "segments.event_date DESC,segments.document_id,segments.ordinal,rank",
            }[order]
            rows = self._index.execute(
                "SELECT segments.segment_id,bm25(segment_fts,1.0,0.15) AS rank "
                "FROM segment_fts JOIN segments ON segments.rowid=segment_fts.rowid "
                "WHERE " + where + " ORDER BY " + ordering + " LIMIT ?",
                (*parameters, _INTERNAL_CANDIDATE_LIMIT),
            ).fetchall()
        except sqlite3.Error as error:
            self._health = AccessHealth.CORRUPT
            raise McpAccessError("access_corrupt", "transcript index query failed") from error
        selected: list[SearchCandidate] = []
        per_document: Counter[str] = Counter()
        for segment_id, rank in rows:
            segment = self._segments[str(segment_id)]
            if per_document[segment.document_id] >= max_per_document:
                continue
            per_document[segment.document_id] += 1
            selected.append(SearchCandidate(
                segment_id=segment.segment_id,
                segment_uri=f"rfi://transcript-segments/{segment.segment_id}",
                document_id=segment.document_id,
                document_uri=f"rfi://documents/{segment.document_id}",
                artifact_id=segment.artifact_id,
                artifact_uri=f"rfi://artifacts/{segment.artifact_id}",
                ordinal=segment.ordinal,
                event_date=segment.event_date,
                event_date_basis=segment.event_date_basis,
                canonical_artifact_id=segment.canonical_artifact_id,
                score=round(-float(rank), 6),
                rank_basis="fts5_bm25_porter_unicode61",
                snippet=self._excerpt(segment.text, terms),
            ))
            if len(selected) >= limit:
                break
        internal_truncated = total > len(rows)
        result_truncated = total > len(selected)
        bounds = [
            {
                "name": "normalized_term_limit",
                "value": 12,
                "applied": len(_TOKEN.findall(query.casefold())) > len(terms),
            },
            {
                "name": "internal_candidate_limit",
                "value": _INTERNAL_CANDIDATE_LIMIT,
                "applied": internal_truncated,
            },
            {
                "name": "max_per_document",
                "value": max_per_document,
                "applied": any(
                    value >= max_per_document for value in per_document.values()
                ),
            },
            {
                "name": "result_limit",
                "value": limit,
                "applied": len(selected) >= limit and total > len(selected),
            },
        ]
        trace.bounds.extend(bounds)
        trace.returned_count = len(selected)
        trace.total_count = total
        trace.truncated = result_truncated
        for item in selected:
            trace.referenced_segment_ids.add(item.segment_id)
            trace.referenced_document_ids.add(item.document_id)
            trace.referenced_artifact_ids.add(item.artifact_id)
        return {
            "query": query,
            "normalized_terms": terms,
            "match": match,
            "order": order,
            "scope": self.scope(),
            "hits": [asdict(item) for item in selected],
            "total_matches": total,
            "returned": len(selected),
            "truncated": result_truncated,
            "bounds_applied": bounds,
            "pagination": {"supported": False, "cursor": None, "next_cursor": None},
            "coverage": {
                "query": "complete" if not internal_truncated else "bounded",
                "index": self._build_outcome.value,
                "retained_corpus": "indeterminate",
            },
        }

    def exact_segment(self, segment_id: str, trace: TraceContext) -> dict[str, Any]:
        """Re-read and verify an exact segment through immutable artifact identity."""
        self.ensure_current()
        segment = self._segments.get(segment_id)
        if segment is None:
            raise McpAccessError("unknown_object", f"unknown transcript segment: {segment_id}")
        try:
            artifact = self.artifacts.artifact_content(segment.artifact_id)
        except ArtifactQueryError as error:
            if error.code == "integrity_failure":
                self._health = AccessHealth.CORRUPT
            raise self._artifact_error(error) from error
        exact = artifact.content[segment.byte_start:segment.byte_end]
        digest = hashlib.sha256(exact).hexdigest()
        if digest != segment.segment_sha256:
            self._health = AccessHealth.CORRUPT
            raise McpAccessError(
                "integrity_failure",
                "transcript segment byte span does not match its immutable locator",
                category="integrity_failure",
            )
        trace.referenced_segment_ids.add(segment.segment_id)
        trace.referenced_document_ids.add(segment.document_id)
        trace.referenced_artifact_ids.add(segment.artifact_id)
        trace.referenced_observation_ids.add(segment.observation_id)
        trace.artifact_digests[segment.artifact_id] = artifact.checksum_sha256
        trace.range_digests[f"{segment.byte_start}:{segment.byte_end}"] = digest
        return {
            **asdict(segment),
            "text": exact.decode("utf-8", "replace").strip(),
            "artifact_sha256": artifact.checksum_sha256,
            "requested_range": {
                "byte_start": segment.byte_start,
                "byte_end": segment.byte_end,
            },
            "range_sha256": digest,
            "whole_artifact_verified": True,
            "segment_verified": True,
            "evidence_state": "exact_verified",
            "authority_class": "source_evidence",
            "links": self._links(segment),
        }

    def window(
        self,
        document_id: str,
        *,
        start: int,
        count: int,
        trace: TraceContext,
    ) -> dict[str, Any]:
        """Return verified ordered segment context without implicit investigation policy."""
        self.ensure_current()
        if document_id not in self._by_document:
            raise McpAccessError("unknown_object", f"unknown transcript document: {document_id}")
        if start < 1 or not 1 <= count <= _WINDOW_LIMIT:
            raise McpAccessError("invalid_range", "window start/count is outside declared bounds")
        segments = self._by_document[document_id]
        selected = segments[start - 1:start - 1 + count]
        values = [self.exact_segment(item.segment_id, trace) for item in selected]
        trace.returned_count = len(values)
        trace.total_count = len(segments)
        trace.truncated = start - 1 + len(values) < len(segments)
        trace.bounds.append({
            "name": "window_segment_limit",
            "value": _WINDOW_LIMIT,
            "applied": count == _WINDOW_LIMIT,
        })
        return {
            "document_id": document_id,
            "start_ordinal": start,
            "requested_count": count,
            "segments": values,
            "returned": len(values),
            "document_segment_count": len(segments),
            "preceding_available": start > 1,
            "following_available": start - 1 + len(values) < len(segments),
            "bounds_applied": trace.bounds,
        }

    def artifact_bytes(self, arguments: dict[str, Any], trace: TraceContext) -> dict[str, Any]:
        """Return a verified exact immutable-artifact byte range without silent clipping."""
        artifact_id = arguments.get("artifact_id")
        start = arguments.get("byte_start")
        end = arguments.get("byte_end")
        decode = arguments.get("decode", "text")
        if not isinstance(artifact_id, str):
            raise McpAccessError("invalid_request", "artifact_id is required")
        if (
            isinstance(start, bool)
            or isinstance(end, bool)
            or not isinstance(start, int)
            or not isinstance(end, int)
            or start < 0
            or end <= start
        ):
            raise McpAccessError("invalid_range", "byte range must be non-empty and half-open")
        if end - start > _ARTIFACT_RANGE_LIMIT:
            raise McpAccessError(
                "invalid_range",
                f"requested byte range exceeds {_ARTIFACT_RANGE_LIMIT} bytes",
            )
        if decode not in {"text", "base64", "both"}:
            raise McpAccessError("unsupported_query", "decode must be text, base64, or both")
        try:
            artifact = self.artifacts.artifact_content(artifact_id)
        except ArtifactQueryError as error:
            raise self._artifact_error(error) from error
        if end > len(artifact.content):
            raise McpAccessError(
                "invalid_range",
                "requested byte range exceeds immutable artifact size; no bytes were clipped",
                details={"artifact_size": len(artifact.content)},
            )
        exact = artifact.content[start:end]
        digest = hashlib.sha256(exact).hexdigest()
        value: dict[str, Any] = {
            "artifact_id": artifact_id,
            "artifact_uri": f"rfi://artifacts/{artifact_id}",
            "media_type": artifact.media_type,
            "artifact_size": len(artifact.content),
            "artifact_sha256": artifact.checksum_sha256,
            "requested_range": {"byte_start": start, "byte_end": end, "convention": "half-open"},
            "range_sha256": digest,
            "complete_for_requested_range": True,
            "whole_artifact_verified": True,
            "bounds_applied": [
                {"name": "artifact_range_bytes", "value": _ARTIFACT_RANGE_LIMIT, "applied": False}
            ],
        }
        if decode in {"base64", "both"}:
            value["base64_bytes"] = base64.b64encode(exact).decode()
        if decode in {"text", "both"}:
            value["text_rendering"] = exact.decode("utf-8", "replace")
            value["text_rendering_is_exact_bytes"] = False
        trace.referenced_artifact_ids.add(artifact_id)
        trace.artifact_digests[artifact_id] = artifact.checksum_sha256
        trace.range_digests[f"{start}:{end}"] = digest
        trace.bounds.extend(value["bounds_applied"])
        trace.returned_count = 1
        return value

    def scope(self) -> dict[str, Any]:
        return {
            "firm_ids": self.firm_ids,
            "canonical_artifact_ids": self.canonical_artifact_ids,
            "source_effective_from": self.source_effective_from,
            "source_effective_through": self.source_effective_through,
        }

    def document(self, document_id: str) -> dict[str, Any]:
        self.ensure_current()
        item = self._documents.get(document_id)
        if item is None:
            raise McpAccessError("unknown_object", f"unknown transcript document: {document_id}")
        return item

    def segment_ids(self) -> tuple[str, ...]:
        return tuple(sorted(self._segments))

    def document_ids(self) -> tuple[str, ...]:
        return tuple(sorted(self._documents))

    def _build(self) -> None:
        self._index.execute(
            "CREATE TABLE segments("
            "segment_id TEXT UNIQUE,document_id TEXT,event_date TEXT,ordinal INTEGER)"
        )
        self._index.execute(
            "CREATE VIRTUAL TABLE segment_fts USING "
            "fts5(content,title,tokenize='porter unicode61')"
        )
        query = ArtifactQuery(
            firm_ids=self.firm_ids,
            canonical_artifact_ids=self.canonical_artifact_ids,
            source_effective_from=self.source_effective_from,
            source_effective_through=self.source_effective_through,
            order=ArtifactOrder.OLDEST,
            limit=100,
        )
        cursor: str | None = None
        summaries = []
        try:
            while len(summaries) < _BUILD_DOCUMENT_LIMIT:
                page = self.artifacts.query(replace(query, cursor=cursor))
                if self._authority_snapshot == "unavailable":
                    self._authority_snapshot = page.repository_snapshot
                    self._eligible = page.total_items
                if page.repository_snapshot != self._authority_snapshot:
                    raise McpAccessError(
                        "access_stale", "repository changed during access build"
                    )
                summaries.extend(page.items[:_BUILD_DOCUMENT_LIMIT - len(summaries)])
                self._diagnostics.extend(
                    AccessDiagnostic(
                        item.code, item.message, item.document_id, item.artifact_id
                    )
                    for item in page.diagnostics
                )
                if page.diagnostics_truncated:
                    self._diagnostics.append(AccessDiagnostic(
                        "artifact_diagnostics_truncated",
                        f"repository page returned 100 of {page.diagnostics_total} diagnostics",
                    ))
                cursor = page.next_cursor
                if cursor is None or len(summaries) >= _BUILD_DOCUMENT_LIMIT:
                    break
        except McpAccessError:
            raise
        except ArtifactQueryError as error:
            self._diagnostics.append(AccessDiagnostic(error.code, str(error)))
            self._health = AccessHealth.UNAVAILABLE
            return
        if self._eligible > _BUILD_DOCUMENT_LIMIT:
            self._diagnostics.append(AccessDiagnostic(
                "build_document_limit",
                f"indexed {_BUILD_DOCUMENT_LIMIT} of {self._eligible} eligible documents",
            ))
        for summary in summaries:
            try:
                detail = self.artifacts.detail(summary.document_id)
                retained = self.artifacts.artifact_content(summary.artifact_id)
                segments = self._segment(
                    retained.content,
                    summary.document_id,
                    summary.artifact_id,
                    retained.checksum_sha256,
                    summary.display_title,
                    summary.source_effective.value[:10],
                    summary.source_effective.basis,
                    str(summary.canonical_artifact_id),
                    detail.observation.observation_id,
                    detail.observation.diagnostics.get("transcript_event_kind"),
                )
            except (ArtifactQueryError, McpAccessError) as error:
                code = (
                    error.code
                    if isinstance(error, (ArtifactQueryError, McpAccessError))
                    else "build_failure"
                )
                self._diagnostics.append(
                    AccessDiagnostic(code, str(error), summary.document_id, summary.artifact_id)
                )
                continue
            self._documents[summary.document_id] = {
                "document_id": summary.document_id,
                "document_uri": f"rfi://documents/{summary.document_id}",
                "artifact_id": summary.artifact_id,
                "artifact_uri": f"rfi://artifacts/{summary.artifact_id}",
                "observation_id": detail.observation.observation_id,
                "observation_uri": (
                    f"rfi://observations/{detail.observation.observation_id}"
                ),
                "firm_id": summary.firm_id,
                "canonical_artifact_id": summary.canonical_artifact_id,
                "title": summary.display_title,
                "title_basis": "artifact_summary_display_projection",
                "event_date": summary.source_effective.value[:10],
                "event_date_basis": summary.source_effective.basis,
                "event_kind": self._optional_text(
                    detail.observation.diagnostics.get("transcript_event_kind")
                ),
                "speaker_context_available": any(
                    item.speaker_label for item in segments
                ),
                "segment_count": len(segments),
                "artifact_sha256": retained.checksum_sha256,
                "content_size": len(retained.content),
                "authority_class": "repository_metadata",
            }
            self._by_document[summary.document_id] = list(segments)
            for segment in segments:
                cursor_row = self._index.execute(
                    "INSERT INTO segments("
                    "segment_id,document_id,event_date,ordinal) VALUES (?,?,?,?)",
                    (
                        segment.segment_id,
                        segment.document_id,
                        segment.event_date,
                        segment.ordinal,
                    ),
                )
                self._index.execute(
                    "INSERT INTO segment_fts(rowid,content,title) VALUES (?,?,?)",
                    (cursor_row.lastrowid, segment.text, segment.title),
                )
                self._segments[segment.segment_id] = segment
        self._index.commit()
        self._build_outcome = (
            Outcome.PARTIAL
            if len(self._documents) < self._eligible or self._diagnostics
            else Outcome.OK
        )
        self._health = (
            AccessHealth.READY
            if self._documents or self._eligible == 0
            else AccessHealth.UNAVAILABLE
        )
        identity = {
            "snapshot": self._authority_snapshot,
            "scope": self.scope(),
            "documents": [
                (item["document_id"], item["artifact_id"], item["segment_count"])
                for item in sorted(
                    self._documents.values(), key=lambda value: value["document_id"]
                )
            ],
        }
        digest = hashlib.sha256(
            repr(identity).encode("utf-8")
        ).hexdigest()
        self._generation_id = f"transcript-access-{digest}"

    @staticmethod
    def _segment(
        content: bytes,
        document_id: str,
        artifact_id: str,
        artifact_sha256: str,
        title: str,
        event_date: str,
        event_date_basis: str,
        canonical_artifact_id: str,
        observation_id: str,
        event_kind: Any,
    ) -> tuple[TranscriptProjection, ...]:
        if hashlib.sha256(content).hexdigest() != artifact_sha256:
            raise McpAccessError("integrity_failure", "artifact checksum mismatch during build")
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
            segments.append(TranscriptProjection(
                segment_id=f"transcript-segment-{identity}",
                document_id=document_id,
                artifact_id=artifact_id,
                ordinal=len(segments) + 1,
                byte_start=start,
                byte_end=end,
                segment_sha256=digest,
                text=text,
                event_date=event_date,
                event_date_basis=event_date_basis,
                title=title,
                title_basis="artifact_summary_display_projection",
                canonical_artifact_id=canonical_artifact_id,
                event_kind=TranscriptAccessGeneration._optional_text(event_kind),
                speaker_label=None,
                observation_id=observation_id,
            ))
        if not segments:
            raise McpAccessError(
                "unsegmentable_transcript",
                "retained transcript has no addressable body paragraphs",
            )
        return tuple(segments)

    def _validate_scope_filters(self, arguments: dict[str, Any]) -> None:
        for key, expected in (
            ("firm_ids", set(self.firm_ids)),
            ("canonical_artifact_ids", set(self.canonical_artifact_ids)),
        ):
            supplied = arguments.get(key)
            if supplied is None:
                continue
            if not isinstance(supplied, list) or any(
                not isinstance(item, str) for item in supplied
            ):
                raise McpAccessError("invalid_request", f"{key} must be a string array")
            unknown = set(supplied) - expected
            if unknown:
                raise McpAccessError(
                    "unknown_object",
                    f"{key} references an object outside the declared transcript scope",
                    category="invalid_scope",
                    details={"unknown": sorted(unknown)},
                )

    def _metadata_gaps(self) -> list[str]:
        gaps = []
        if any(not item["speaker_context_available"] for item in self._documents.values()):
            gaps.append("speaker labels are unavailable in normalized retained bytes")
        if any(item["event_kind"] is None for item in self._documents.values()):
            gaps.append("historical event-kind diagnostics are unavailable")
        gaps.append("retained-corpus coverage is indeterminate")
        return gaps

    @staticmethod
    def _links(segment: TranscriptProjection) -> list[dict[str, str]]:
        return [
            {"rel": "document", "uri": f"rfi://documents/{segment.document_id}"},
            {"rel": "artifact", "uri": f"rfi://artifacts/{segment.artifact_id}"},
            {"rel": "observation", "uri": f"rfi://observations/{segment.observation_id}"},
        ]

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
        return (
            ("…" if start else "")
            + text[start:end]
            + ("…" if end < len(text) else "")
        )

    @staticmethod
    def _optional_text(value: Any) -> str | None:
        return value if isinstance(value, str) and value else None

    def _encode_cursor(self, offset: int) -> str:
        payload = json.dumps(
            {"generation_id": self._generation_id, "offset": offset},
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
        return base64.urlsafe_b64encode(payload).decode().rstrip("=")

    def _decode_cursor(self, cursor: str | None) -> int:
        if cursor is None:
            return 0
        try:
            payload = json.loads(base64.urlsafe_b64decode(cursor + "===").decode())
            offset = payload["offset"]
        except (ValueError, UnicodeError, json.JSONDecodeError, KeyError, TypeError) as error:
            raise McpAccessError("invalid_cursor", "corpus cursor is malformed") from error
        if payload.get("generation_id") != self._generation_id:
            raise McpAccessError(
                "stale_cursor", "corpus cursor belongs to another access generation"
            )
        if isinstance(offset, bool) or not isinstance(offset, int) or offset < 0:
            raise McpAccessError("invalid_cursor", "corpus cursor is malformed")
        return offset

    @staticmethod
    def _artifact_error(error: ArtifactQueryError) -> McpAccessError:
        mapping = {
            "unknown_artifact_id": "unknown_object",
            "unknown_document_id": "unknown_object",
            "unknown_observation_id": "unknown_object",
            "checksum_mismatch": "integrity_failure",
            "missing_stored_content": "exact_evidence_unavailable",
        }
        code = mapping.get(error.code, error.code)
        category = "integrity_failure" if code == "integrity_failure" else "repository_failure"
        return McpAccessError(code, str(error), category=category)


ACCESS_LIMITS = {
    "build_document_limit": _BUILD_DOCUMENT_LIMIT,
    "artifact_query_page_limit": 100,
    "artifact_diagnostic_limit_per_page": 100,
    "normalized_term_limit": 12,
    "internal_candidate_limit": _INTERNAL_CANDIDATE_LIMIT,
    "search_result_limit": _SEARCH_RESULT_LIMIT,
    "max_per_document": _DIVERSITY_LIMIT,
    "window_segment_limit": _WINDOW_LIMIT,
    "artifact_range_bytes": _ARTIFACT_RANGE_LIMIT,
}
