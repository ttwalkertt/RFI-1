"""Dependency-free local stdio MCP transport for the bounded TASK-073 experiment."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from rfi.acquisition import AcquisitionRepository
from rfi.artifacts import ArtifactQueryService
from rfi.firms import FirmRepository
from rfi.mcp.contracts import McpAccessError
from rfi.mcp.surface import RfiMcpSurface, SERVER_NAME, SERVER_VERSION
from rfi.source_profiles import load_canonical_template

_PROTOCOL_VERSION = "2025-06-18"


class StdioMcpServer:
    """Small MCP JSON-RPC dispatcher exposing no filesystem or mutation capability."""

    def __init__(self, surface: RfiMcpSurface) -> None:
        self.surface = surface

    def dispatch(self, request: dict[str, Any]) -> dict[str, Any] | None:
        """Dispatch one JSON-RPC request or notification."""
        request_id = request.get("id")
        method = request.get("method")
        params = request.get("params") or {}
        if not isinstance(method, str) or not isinstance(params, dict):
            return self._error(request_id, -32600, "invalid JSON-RPC request")
        if method == "initialize":
            self.surface.protocol_event(method, params)
            requested = params.get("protocolVersion")
            protocol = requested if isinstance(requested, str) else _PROTOCOL_VERSION
            return self._result(request_id, {
                "protocolVersion": protocol,
                "capabilities": {
                    "tools": {"listChanged": False},
                    "resources": {"subscribe": False, "listChanged": False},
                },
                "serverInfo": {"name": SERVER_NAME, "version": SERVER_VERSION},
            })
        if method in {"notifications/initialized", "notifications/cancelled"}:
            self.surface.protocol_event(method, params)
            return None
        if method == "ping":
            self.surface.protocol_event(method, params)
            return self._result(request_id, {})
        if method == "tools/list":
            envelope = self.surface.list_tools()
            return self._result(request_id, envelope["data"])
        if method == "tools/call":
            name = params.get("name")
            arguments = params.get("arguments") or {}
            if not isinstance(name, str) or not isinstance(arguments, dict):
                return self._error(
                    request_id, -32602, "tool name and object arguments are required"
                )
            envelope = self.surface.call_tool(name, arguments)
            text = json.dumps(envelope, indent=2, sort_keys=True, default=str)
            return self._result(request_id, {
                "content": [{"type": "text", "text": text}],
                "structuredContent": envelope,
                "isError": envelope["outcome"] == "error",
            })
        if method == "resources/list":
            envelope = self.surface.list_resources()
            return self._result(request_id, envelope["data"])
        if method == "resources/templates/list":
            envelope = self.surface.list_resource_templates()
            return self._result(request_id, envelope["data"])
        if method == "resources/read":
            uri = params.get("uri")
            if not isinstance(uri, str):
                return self._error(request_id, -32602, "resource URI is required")
            envelope = self.surface.read_resource(uri)
            if envelope["outcome"] == "error":
                return self._error(request_id, -32002, "RFI resource read failed", envelope)
            return self._result(request_id, {
                "contents": [{
                    "uri": uri,
                    "mimeType": "application/json",
                    "text": json.dumps(envelope, indent=2, sort_keys=True, default=str),
                }]
            })
        return self._error(request_id, -32601, f"method not found: {method}")

    @staticmethod
    def _result(request_id: Any, value: dict[str, Any]) -> dict[str, Any]:
        return {"jsonrpc": "2.0", "id": request_id, "result": value}

    @staticmethod
    def _error(
        request_id: Any,
        code: int,
        message: str,
        data: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        error: dict[str, Any] = {"code": code, "message": message}
        if data is not None:
            error["data"] = data
        return {"jsonrpc": "2.0", "id": request_id, "error": error}

    def run(self) -> int:
        """Serve newline-delimited MCP JSON-RPC until the parent closes stdin."""
        for line in sys.stdin:
            if not line.strip():
                continue
            try:
                request = json.loads(line)
                if not isinstance(request, dict):
                    raise ValueError("request must be an object")
                response = self.dispatch(request)
            except (ValueError, json.JSONDecodeError) as error:
                response = self._error(None, -32700, f"parse error: {error}")
            except Exception as error:  # fail closed at the transport boundary
                response = self._error(None, -32603, "internal MCP adapter failure", {
                    "error_type": type(error).__name__,
                    "evidence_implication": "No evidence-absence inference is permitted.",
                })
            if response is not None:
                sys.stdout.write(json.dumps(response, separators=(",", ":"), default=str) + "\n")
                sys.stdout.flush()
        return 0


def compose_surface(state: Path, trace: Path | None) -> RfiMcpSurface:
    """Compose public repository readers from one explicitly configured local state root."""
    artifacts = ArtifactQueryService(
        AcquisitionRepository(state / "acquisition"),
        FirmRepository.open(state / "firm-catalog"),
        load_canonical_template(),
    )
    return RfiMcpSurface(artifacts, trace_path=trace)


def main() -> int:
    parser = argparse.ArgumentParser(description="Local read-only RFI transcript MCP server")
    parser.add_argument("--state", type=Path, required=True)
    parser.add_argument("--trace", type=Path)
    arguments = parser.parse_args()
    try:
        surface = compose_surface(arguments.state, arguments.trace)
    except McpAccessError as error:
        print(json.dumps(error.record(), sort_keys=True), file=sys.stderr)
        return 2
    try:
        return StdioMcpServer(surface).run()
    finally:
        surface.close()


if __name__ == "__main__":
    raise SystemExit(main())
