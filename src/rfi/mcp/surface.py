"""Agent-legible, procedurally weak, read-only RFI MCP transcript surface."""

from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import asdict, is_dataclass
from datetime import UTC, datetime
from enum import Enum
from pathlib import Path
from typing import Any, Callable
from urllib.parse import parse_qs, urlparse

from rfi.artifacts import (
    ArtifactAssociation,
    ArtifactOrder,
    ArtifactQuery,
    ArtifactQueryError,
    ArtifactQueryService,
)
from rfi.mcp.access import ACCESS_LIMITS, TranscriptAccessGeneration
from rfi.mcp.contracts import (
    CAPABILITY_VERSION,
    McpAccessError,
    Outcome,
    SCHEMA_VERSION,
    TraceContext,
)
from rfi.mcp.dictionary import data_dictionary

SERVER_NAME = "rfi-read-only-transcript-experiment"
SERVER_VERSION = "0.1.0"
_RESPONSE_BYTE_LIMIT = 262_144


class RfiMcpSurface:
    """Minimum semantic MCP adapter; owns access facts, never investigation behavior."""

    def __init__(
        self,
        artifacts: ArtifactQueryService,
        *,
        trace_path: Path | None = None,
        firm_ids: tuple[str, ...] = ("seagate",),
        canonical_artifact_ids: tuple[str, ...] = (
            "earnings_transcript",
            "management_transcript",
        ),
    ) -> None:
        for firm_id in firm_ids:
            if not artifacts.firm_exists(firm_id):
                raise McpAccessError(
                    "unknown_object",
                    f"unknown governed firm: {firm_id}",
                    category="invalid_scope",
                )
        self.artifacts = artifacts
        self.trace_path = trace_path
        self.access = TranscriptAccessGeneration(
            artifacts,
            firm_ids=firm_ids,
            canonical_artifact_ids=canonical_artifact_ids,
        )

    def close(self) -> None:
        self.access.close()

    def list_tools(self) -> dict[str, Any]:
        """Return only the three bounded experiment tools."""
        return self._request("mcp.tools.list", {}, lambda _trace: {"tools": self.tool_specs()})

    def protocol_event(self, method: str, params: dict[str, Any]) -> dict[str, Any]:
        """Instrument one transport-level request without manufacturing planner state."""
        return self._request(
            f"mcp.protocol:{method}",
            params,
            lambda _trace: {"acknowledged": True},
        )

    def list_resources(self) -> dict[str, Any]:
        """Return discoverable descriptive and current corpus resources."""
        resources = [
            self._resource("rfi://about", "RFI retained-truth server identity"),
            self._resource("rfi://dictionary", "Versioned RFI data dictionary"),
            self._resource("rfi://capabilities", "Live read-only capabilities and health"),
        ]
        if self.access.firm_ids:
            resources.append(self._resource(
                f"rfi://transcript-corpora/{self.access.firm_ids[0]}?limit=25",
                "Current retained transcript corpus view",
            ))
        return self._request("mcp.resources.list", {}, lambda _trace: {"resources": resources})

    def list_resource_templates(self) -> dict[str, Any]:
        """Return the bounded semantic resource templates, not persistence paths."""
        templates = [
            self._template("rfi://documents/{document_id}", "Current logical document projection"),
            self._template("rfi://artifacts/{artifact_id}", "Immutable artifact metadata"),
            self._template(
                "rfi://observations/{observation_id}",
                "Immutable acquisition observation",
            ),
            self._template(
                "rfi://transcript-corpora/{firm_id}?limit={limit}&cursor={cursor}",
                "Bounded retained transcript corpus view",
            ),
            self._template(
                "rfi://transcript-segments/{segment_id}",
                "Exact verified transcript segment",
            ),
            self._template(
                "rfi://transcript-documents/{document_id}/segments?start={start}&count={count}",
                "Bounded verified ordered transcript window",
            ),
        ]
        return self._request(
            "mcp.resources.templates.list", {}, lambda _trace: {"resourceTemplates": templates}
        )

    def read_resource(self, uri: str) -> dict[str, Any]:
        """Read one semantic resource with typed unknown, stale, and integrity failures."""
        return self._request(
            f"resource:{self._resource_capability(uri)}",
            {"uri": uri},
            lambda trace: self._read_resource(uri, trace),
        )

    def call_tool(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        """Call one allowlisted selection/read tool without investigative control logic."""
        if name == "query_artifacts":
            return self._request(
                name, arguments, lambda trace: self._query_artifacts(arguments, trace)
            )
        if name == "search_transcript_segments":
            return self._request(
                name, arguments, lambda trace: self.access.search(arguments, trace)
            )
        if name == "read_artifact_bytes":
            return self._request(
                name,
                arguments,
                lambda trace: self.access.artifact_bytes(arguments, trace),
            )
        return self._error_request(
            name,
            arguments,
            McpAccessError("unknown_capability", f"unknown RFI MCP tool: {name}"),
        )

    def tool_specs(self) -> list[dict[str, Any]]:
        """Return MCP input schemas whose descriptions state evidence semantics, not workflow."""
        return [
            {
                "name": "query_artifacts",
                "description": (
                    "Select retained logical documents using governed canonical filters and "
                    "source-effective ordering. Empty is a successful no-match; failures "
                    "are not empty."
                ),
                "annotations": {
                    "readOnlyHint": True,
                    "destructiveHint": False,
                    "idempotentHint": True,
                },
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "firm_ids": {"type": "array", "items": {"type": "string"}},
                        "family_ids": {"type": "array", "items": {"type": "string"}},
                        "canonical_artifact_ids": {"type": "array", "items": {"type": "string"}},
                        "provider_ids": {"type": "array", "items": {"type": "string"}},
                        "association_kinds": {
                            "type": "array",
                            "items": {"type": "string", "enum": ["firm-canonical", "unassociated"]},
                        },
                        "durable_statuses": {
                            "type": "array",
                            "items": {"type": "string", "enum": ["durable"]},
                        },
                        "source_effective_from": {"type": ["string", "null"]},
                        "source_effective_through": {"type": ["string", "null"]},
                        "order": {"type": "string", "enum": ["newest", "oldest"]},
                        "limit": {"type": "integer", "minimum": 1, "maximum": 100},
                        "cursor": {"type": ["string", "null"]},
                    },
                    "additionalProperties": False,
                },
            },
            {
                "name": "search_transcript_segments",
                "description": (
                    "Return bounded lexical transcript candidates. Snippets and scores are "
                    "derived and non-citable; linked segment resources provide verified evidence."
                ),
                "annotations": {
                    "readOnlyHint": True,
                    "destructiveHint": False,
                    "idempotentHint": True,
                },
                "inputSchema": {
                    "type": "object",
                    "required": ["query"],
                    "properties": {
                        "query": {"type": "string", "minLength": 1},
                        "match": {"type": "string", "enum": ["any", "all"], "default": "any"},
                        "order": {
                            "type": "string",
                            "enum": ["relevance", "oldest", "latest"],
                            "default": "relevance",
                        },
                        "firm_ids": {"type": "array", "items": {"type": "string"}},
                        "canonical_artifact_ids": {"type": "array", "items": {"type": "string"}},
                        "date_from": {"type": ["string", "null"]},
                        "date_through": {"type": ["string", "null"]},
                        "document_ids": {"type": "array", "items": {"type": "string"}},
                        "limit": {"type": "integer", "minimum": 1, "maximum": 50, "default": 12},
                        "max_per_document": {
                            "type": "integer",
                            "minimum": 1,
                            "maximum": 10,
                            "default": 3,
                        },
                    },
                    "additionalProperties": False,
                },
            },
            {
                "name": "read_artifact_bytes",
                "description": (
                    "Read and verify one exact half-open byte range by immutable artifact_id. "
                    "The requested range is never silently clipped."
                ),
                "annotations": {
                    "readOnlyHint": True,
                    "destructiveHint": False,
                    "idempotentHint": True,
                },
                "inputSchema": {
                    "type": "object",
                    "required": ["artifact_id", "byte_start", "byte_end"],
                    "properties": {
                        "artifact_id": {"type": "string"},
                        "byte_start": {"type": "integer", "minimum": 0},
                        "byte_end": {"type": "integer", "minimum": 1},
                        "decode": {
                            "type": "string",
                            "enum": ["text", "base64", "both"],
                            "default": "text",
                        },
                    },
                    "additionalProperties": False,
                },
            },
        ]

    def _read_resource(self, uri: str, trace: TraceContext) -> dict[str, Any]:
        parsed = urlparse(uri)
        if parsed.scheme != "rfi":
            raise McpAccessError("invalid_request", "resource URI must use the rfi scheme")
        if uri == "rfi://about":
            return self._about()
        if uri == "rfi://dictionary":
            return data_dictionary()
        if uri == "rfi://capabilities":
            return self._capabilities()
        path = parsed.path.strip("/")
        if parsed.netloc == "documents" and path and "/" not in path:
            return self._document_resource(path, trace)
        if parsed.netloc == "artifacts" and path and "/" not in path:
            return self._artifact_resource(path, trace)
        if parsed.netloc == "observations" and path and "/" not in path:
            return self._observation_resource(path, trace)
        if parsed.netloc == "transcript-corpora" and path and "/" not in path:
            if path not in self.access.firm_ids:
                raise McpAccessError("unknown_object", f"unknown transcript corpus firm: {path}")
            query = parse_qs(parsed.query)
            limit = self._integer_query(query, "limit", 25)
            cursor = query.get("cursor", [None])[0]
            return self.access.corpus(limit=limit, cursor=cursor, trace=trace)
        if parsed.netloc == "transcript-segments" and path and "/" not in path:
            return self.access.exact_segment(path, trace)
        if parsed.netloc == "transcript-documents" and path.endswith("/segments"):
            document_id = path.removesuffix("/segments")
            query = parse_qs(parsed.query)
            return self.access.window(
                document_id,
                start=self._integer_query(query, "start", 1),
                count=self._integer_query(query, "count", 8),
                trace=trace,
            )
        raise McpAccessError("unknown_object", f"unknown RFI resource: {uri}")

    def _about(self) -> dict[str, Any]:
        return {
            "server_name": SERVER_NAME,
            "server_version": SERVER_VERSION,
            "schema_version": SCHEMA_VERSION,
            "read_only": True,
            "deployment": "local_stdio_single_user_experiment",
            "repository_authority": "RFI retained immutable artifacts and acquisition observations",
            "repository_snapshot": self.artifacts.repository_snapshot(),
            "instructions_exposed": False,
            "links": ["rfi://dictionary", "rfi://capabilities"],
        }

    def _capabilities(self) -> dict[str, Any]:
        generation = asdict(self.access.identity())
        common = {
            "schema_version": SCHEMA_VERSION,
            "version": CAPABILITY_VERSION,
            "repository_snapshot": self.artifacts.repository_snapshot(),
            "read_only": True,
        }
        return {
            "capabilities": [
                {
                    **common,
                    "capability_id": "artifact.query.v1",
                    "status": "ready",
                    "tool": "query_artifacts",
                    "bounds": {"result_limit": 100, "diagnostic_limit": 100},
                },
                {
                    **common,
                    "capability_id": "artifact.exact_bytes.v1",
                    "status": "ready",
                    "tool": "read_artifact_bytes",
                    "bounds": {
                        "artifact_range_bytes": ACCESS_LIMITS["artifact_range_bytes"]
                    },
                },
                {
                    **common,
                    "capability_id": "transcript.lexical.v1",
                    "status": self.access.health.value,
                    "tool": "search_transcript_segments",
                    "generation": generation,
                    "bounds": ACCESS_LIMITS,
                },
                {
                    **common,
                    "capability_id": "artifact.history.v1",
                    "status": "deferred",
                    "reason": (
                        "selected observation and repository links are sufficient for the "
                        "bounded experiment"
                    ),
                },
            ],
            "resources": [
                "rfi://about", "rfi://dictionary", "rfi://capabilities",
                "rfi://documents/{document_id}", "rfi://artifacts/{artifact_id}",
                "rfi://observations/{observation_id}",
                "rfi://transcript-corpora/{firm_id}",
                "rfi://transcript-segments/{segment_id}",
                "rfi://transcript-documents/{document_id}/segments",
            ],
            "deferred": [
                "query_artifact_history", "semantic_retrieval", "additional_evidence_types",
                "investigation_state", "planning", "adjudication", "report_generation", "prompts",
            ],
            "response_byte_limit": _RESPONSE_BYTE_LIMIT,
        }

    def _document_resource(self, document_id: str, trace: TraceContext) -> dict[str, Any]:
        try:
            detail = self.artifacts.detail(document_id)
        except ArtifactQueryError as error:
            raise self._artifact_error(error) from error
        summary = asdict(detail.summary)
        trace.referenced_document_ids.add(document_id)
        trace.referenced_artifact_ids.add(detail.summary.artifact_id)
        trace.referenced_observation_ids.add(detail.observation.observation_id)
        return {
            "projection_kind": "current_document",
            "summary": summary,
            "selected_observation_id": detail.observation.observation_id,
            "integrity_state": "not_verified_by_metadata_read",
            "authority_class": "repository_metadata",
            "links": [
                f"rfi://artifacts/{detail.summary.artifact_id}",
                f"rfi://observations/{detail.observation.observation_id}",
            ],
        }

    def _artifact_resource(self, artifact_id: str, trace: TraceContext) -> dict[str, Any]:
        try:
            artifact = self.artifacts.artifact(artifact_id)
        except ArtifactQueryError as error:
            raise self._artifact_error(error) from error
        trace.referenced_artifact_ids.add(artifact_id)
        trace.artifact_digests[artifact_id] = artifact.checksum_sha256
        trace.referenced_document_ids.update(artifact.document_ids)
        trace.referenced_observation_ids.update(artifact.observation_ids)
        return {
            **asdict(artifact),
            "immutable": True,
            "integrity_state": "metadata_only_not_yet_read",
            "authority_class": "source_evidence",
            "document_uris": [f"rfi://documents/{value}" for value in artifact.document_ids],
            "observation_uris": [
                f"rfi://observations/{value}" for value in artifact.observation_ids
            ],
            "exact_read_tool": "read_artifact_bytes",
        }

    def _observation_resource(self, observation_id: str, trace: TraceContext) -> dict[str, Any]:
        try:
            observation = self.artifacts.observation(observation_id)
        except ArtifactQueryError as error:
            raise self._artifact_error(error) from error
        trace.referenced_observation_ids.add(observation_id)
        trace.referenced_document_ids.add(observation.document_id)
        trace.referenced_artifact_ids.add(observation.artifact_id)
        return {
            **asdict(observation),
            "authority_class": "repository_metadata",
            "provider_identifiers_are_canonical_identity": False,
            "links": [
                f"rfi://documents/{observation.document_id}",
                f"rfi://artifacts/{observation.artifact_id}",
            ],
        }

    def _query_artifacts(self, arguments: dict[str, Any], trace: TraceContext) -> dict[str, Any]:
        try:
            firm_ids = self._strings(arguments, "firm_ids")
            unknown_firms = [value for value in firm_ids if not self.artifacts.firm_exists(value)]
            if unknown_firms:
                raise McpAccessError(
                    "unknown_object",
                    f"unknown governed firm: {unknown_firms[0]}",
                    category="invalid_scope",
                )
            query = ArtifactQuery(
                firm_ids=firm_ids,
                family_ids=self._strings(arguments, "family_ids"),
                canonical_artifact_ids=self._strings(arguments, "canonical_artifact_ids"),
                provider_ids=self._strings(arguments, "provider_ids"),
                association_kinds=tuple(
                    ArtifactAssociation(value) for value in arguments.get("association_kinds", [])
                ),
                durable_statuses=self._strings(arguments, "durable_statuses", ("durable",)),
                source_effective_from=arguments.get("source_effective_from"),
                source_effective_through=arguments.get("source_effective_through"),
                order=ArtifactOrder(arguments.get("order", "newest")),
                limit=arguments.get("limit", 50),
                cursor=arguments.get("cursor"),
            )
            page = self.artifacts.query(query)
        except ValueError as error:
            raise McpAccessError(
                "invalid_request", "query contains an unsupported enum value"
            ) from error
        except ArtifactQueryError as error:
            raise self._artifact_error(error) from error
        trace.returned_count = len(page.items)
        trace.total_count = page.total_items
        trace.cursor = query.cursor
        trace.next_cursor = page.next_cursor
        trace.truncated = page.next_cursor is not None or page.diagnostics_truncated
        trace.bounds.extend([
            {
                "name": "artifact_result_limit",
                "value": query.limit,
                "applied": page.next_cursor is not None,
            },
            {
                "name": "artifact_diagnostic_limit",
                "value": 100,
                "applied": page.diagnostics_truncated,
            },
        ])
        for item in page.items:
            trace.referenced_document_ids.add(item.document_id)
            trace.referenced_artifact_ids.add(item.artifact_id)
        return {
            "normalized_query": asdict(query),
            "items": [
                {
                    **asdict(item),
                    "document_uri": f"rfi://documents/{item.document_id}",
                    "artifact_uri": f"rfi://artifacts/{item.artifact_id}",
                }
                for item in page.items
            ],
            "page": {
                "limit": query.limit,
                "returned": len(page.items),
                "total_matching": page.total_items,
                "next_cursor": page.next_cursor,
                "truncated": page.next_cursor is not None,
                "bounds_applied": trace.bounds,
            },
            "diagnostics": [asdict(item) for item in page.diagnostics],
            "diagnostics_total": page.diagnostics_total,
            "diagnostics_truncated": page.diagnostics_truncated,
            "coverage": {"state": "indeterminate", "basis": "retained inventory only"},
        }

    def _request(
        self,
        capability: str,
        normalized_input: dict[str, Any],
        operation: Callable[[TraceContext], dict[str, Any]],
    ) -> dict[str, Any]:
        request_id = f"mcp-request-{uuid.uuid4()}"
        started = datetime.now(UTC)
        trace = TraceContext()
        try:
            data = operation(trace)
            outcome = (
                Outcome.PARTIAL
                if self._is_partial(data)
                else (Outcome.EMPTY if self._is_empty(data) else Outcome.OK)
            )
            result = self._envelope(request_id, outcome.value, data)
        except McpAccessError as error:
            result = self._envelope(request_id, "error", None, error=error.record())
        except ArtifactQueryError as error:
            mapped = self._artifact_error(error)
            result = self._envelope(request_id, "error", None, error=mapped.record())
        encoded = self._json_bytes(result)
        if len(encoded) > _RESPONSE_BYTE_LIMIT:
            error = McpAccessError(
                "response_bound_exceeded",
                "response exceeds the declared MCP response byte limit",
                details={"limit": _RESPONSE_BYTE_LIMIT, "computed_bytes": len(encoded)},
            )
            result = self._envelope(request_id, "error", None, error=error.record())
            encoded = self._json_bytes(result)
        self._record_trace(
            request_id=request_id,
            capability=capability,
            normalized_input=normalized_input,
            started=started,
            ended=datetime.now(UTC),
            result=result,
            response_bytes=encoded,
            trace=trace,
        )
        return result

    def _error_request(
        self, capability: str, normalized_input: dict[str, Any], error: McpAccessError
    ) -> dict[str, Any]:
        return self._request(
            capability,
            normalized_input,
            lambda _trace: (_ for _ in ()).throw(error),
        )

    def _envelope(
        self,
        request_id: str,
        outcome: str,
        data: dict[str, Any] | None,
        *,
        error: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return {
            "schema_version": SCHEMA_VERSION,
            "capability_version": CAPABILITY_VERSION,
            "request_id": request_id,
            "server": {"name": SERVER_NAME, "version": SERVER_VERSION},
            "repository_snapshot": self._safe_snapshot(),
            "access_generation": asdict(self.access.identity()),
            "outcome": outcome,
            "data": data,
            "error": error,
        }

    def _record_trace(
        self,
        *,
        request_id: str,
        capability: str,
        normalized_input: dict[str, Any],
        started: datetime,
        ended: datetime,
        result: dict[str, Any],
        response_bytes: bytes,
        trace: TraceContext,
    ) -> None:
        if self.trace_path is None:
            return
        record = {
            "trace_version": "rfi.mcp.trace.v1",
            "request_id": request_id,
            "capability": capability,
            "capability_version": CAPABILITY_VERSION,
            "schema_version": SCHEMA_VERSION,
            "server_version": SERVER_VERSION,
            "normalized_input": normalized_input,
            "input_sha256": hashlib.sha256(self._json_bytes(normalized_input)).hexdigest(),
            "repository_snapshot": result["repository_snapshot"],
            "access_generation": result["access_generation"],
            "started_at": started.isoformat(),
            "ended_at": ended.isoformat(),
            "duration_ms": round((ended - started).total_seconds() * 1000, 3),
            "outcome": result["outcome"],
            "error": result["error"],
            "returned_count": trace.returned_count,
            "total_count": trace.total_count,
            "cursor": trace.cursor,
            "next_cursor": trace.next_cursor,
            "bounds": trace.bounds,
            "truncated": trace.truncated,
            "referenced_document_ids": sorted(trace.referenced_document_ids),
            "referenced_artifact_ids": sorted(trace.referenced_artifact_ids),
            "referenced_observation_ids": sorted(trace.referenced_observation_ids),
            "referenced_segment_ids": sorted(trace.referenced_segment_ids),
            "artifact_digests": trace.artifact_digests,
            "range_digests": trace.range_digests,
            "response_sha256": hashlib.sha256(response_bytes).hexdigest(),
            "response_bytes": len(response_bytes),
        }
        self.trace_path.parent.mkdir(parents=True, exist_ok=True)
        with self.trace_path.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(record, sort_keys=True, default=self._json_default) + "\n")

    def _safe_snapshot(self) -> str | None:
        try:
            return self.artifacts.repository_snapshot()
        except ArtifactQueryError:
            return None

    @staticmethod
    def _is_empty(data: dict[str, Any]) -> bool:
        for key in ("items", "hits", "documents", "segments"):
            if key in data and data[key] == []:
                return True
        return False

    def _is_partial(self, data: dict[str, Any]) -> bool:
        return bool(
            data.get("diagnostics_truncated")
            or data.get("truncated")
            or data.get("page", {}).get("truncated")
            or self.access.identity().build_outcome == Outcome.PARTIAL
        )

    @staticmethod
    def _resource_capability(uri: str) -> str:
        parsed = urlparse(uri)
        return parsed.netloc or "invalid"

    @staticmethod
    def _strings(
        arguments: dict[str, Any], key: str, default: tuple[str, ...] = ()
    ) -> tuple[str, ...]:
        value = arguments.get(key, list(default))
        if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
            raise McpAccessError("invalid_request", f"{key} must be a string array")
        return tuple(value)

    @staticmethod
    def _integer_query(query: dict[str, list[str]], key: str, default: int) -> int:
        value = query.get(key, [str(default)])[0]
        try:
            return int(value)
        except ValueError as error:
            raise McpAccessError("invalid_request", f"{key} must be an integer") from error

    @staticmethod
    def _artifact_error(error: ArtifactQueryError) -> McpAccessError:
        mapping = {
            "unknown_document_id": "unknown_object",
            "unknown_artifact_id": "unknown_object",
            "unknown_observation_id": "unknown_object",
            "unknown_firm": "unknown_object",
            "invalid_query": "invalid_request",
            "checksum_mismatch": "integrity_failure",
            "missing_stored_content": "exact_evidence_unavailable",
        }
        code = mapping.get(error.code, error.code)
        return McpAccessError(code, str(error), category="repository_failure")

    @staticmethod
    def _resource(uri: str, name: str) -> dict[str, Any]:
        return {"uri": uri, "name": name, "mimeType": "application/json"}

    @staticmethod
    def _template(uri_template: str, name: str) -> dict[str, Any]:
        return {"uriTemplate": uri_template, "name": name, "mimeType": "application/json"}

    @staticmethod
    def _json_default(value: Any) -> Any:
        if isinstance(value, Enum):
            return value.value
        if is_dataclass(value):
            return asdict(value)
        raise TypeError(f"cannot serialize {type(value).__name__}")

    @classmethod
    def _json_bytes(cls, value: Any) -> bytes:
        return json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            default=cls._json_default,
        ).encode("utf-8")
