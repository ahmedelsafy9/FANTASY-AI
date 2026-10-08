"""MCP (Model Context Protocol) server for Fantasy AI tools.

Exposes Fantasy AI tools via the MCP protocol using JSON-RPC over
stdio.  This allows external LLM clients (Claude, Cursor, etc.) to
discover and call Fantasy AI tools.

Run as a standalone process:
    python -m src.agentic.mcp.server

The server implements the MCP specification:
- ``initialize`` — handshake and capability declaration
- ``tools/list`` — enumerate available tools
- ``tools/call`` — execute a specific tool

No heavy MCP SDK dependency is required — this is a minimal,
spec-compliant implementation using stdlib JSON-RPC over stdio.
"""

from __future__ import annotations

import json
import sys
from typing import Any

from src.config.logging_config import get_logger

logger = get_logger(__name__)

# Protocol constants
JSONRPC_VERSION = "2.0"
MCP_PROTOCOL_VERSION = "2024-11-05"


def _make_response(id_: Any, result: Any) -> dict[str, Any]:
    """Build a JSON-RPC success response."""
    return {
        "jsonrpc": JSONRPC_VERSION,
        "id": id_,
        "result": result,
    }


def _make_error(id_: Any, code: int, message: str) -> dict[str, Any]:
    """Build a JSON-RPC error response."""
    return {
        "jsonrpc": JSONRPC_VERSION,
        "id": id_,
        "error": {"code": code, "message": message},
    }


class FantasyAIMCPServer:
    """Minimal MCP server exposing Fantasy AI tools over stdio.

    Args:
        app_state: The application state (or None for lazy loading).
    """

    def __init__(self, app_state=None) -> None:
        self._app_state = app_state
        self._registry = None
        self._initialized = False

    def _ensure_registry(self) -> None:
        """Lazily build the tool registry."""
        if self._registry is not None:
            return

        if self._app_state is None:
            # Build app state from settings
            from src.config.settings import get_settings
            from src.api.state import build_app_state

            settings = get_settings()
            self._app_state = build_app_state(settings)

        from src.agentic.tools.definitions import build_tool_registry
        self._registry = build_tool_registry(self._app_state)

    def handle_request(self, request: dict[str, Any]) -> dict[str, Any] | None:
        """Handle a single JSON-RPC request.

        Args:
            request: Parsed JSON-RPC request object.

        Returns:
            JSON-RPC response, or ``None`` for notifications.
        """
        method = request.get("method", "")
        params = request.get("params", {})
        req_id = request.get("id")

        logger.debug("MCP request: method=%s, id=%s", method, req_id)

        try:
            if method == "initialize":
                return self._handle_initialize(req_id, params)
            elif method == "notifications/initialized":
                return None  # Notification, no response
            elif method == "tools/list":
                return self._handle_tools_list(req_id)
            elif method == "tools/call":
                return self._handle_tools_call(req_id, params)
            elif method == "ping":
                return _make_response(req_id, {})
            else:
                return _make_error(
                    req_id, -32601, f"Method not found: {method}"
                )
        except Exception as exc:
            logger.exception("MCP handler error for method '%s'", method)
            return _make_error(req_id, -32603, str(exc))

    def _handle_initialize(
        self, req_id: Any, params: dict[str, Any],
    ) -> dict[str, Any]:
        """Handle the MCP initialize handshake."""
        self._initialized = True
        return _make_response(req_id, {
            "protocolVersion": MCP_PROTOCOL_VERSION,
            "capabilities": {
                "tools": {"listChanged": False},
            },
            "serverInfo": {
                "name": "fantasy-ai-mcp",
                "version": "1.0.0",
            },
        })

    def _handle_tools_list(self, req_id: Any) -> dict[str, Any]:
        """Handle tools/list — return all available tool schemas."""
        self._ensure_registry()

        tools = []
        for schema in self._registry.get_all_schemas():
            # Convert to MCP tool format
            tool = {
                "name": schema["name"],
                "description": schema["description"],
                "inputSchema": schema["parameters"],
            }
            tools.append(tool)

        return _make_response(req_id, {"tools": tools})

    def _handle_tools_call(
        self, req_id: Any, params: dict[str, Any],
    ) -> dict[str, Any]:
        """Handle tools/call — execute a specific tool."""
        self._ensure_registry()

        tool_name = params.get("name", "")
        arguments = params.get("arguments", {})

        logger.info(
            "MCP tool call: %s(args=%s)",
            tool_name,
            json.dumps(arguments, default=str)[:200],
        )

        result = self._registry.execute(tool_name, **arguments)

        if result.success:
            content = [{
                "type": "text",
                "text": json.dumps(result.data, default=str),
            }]
        else:
            content = [{
                "type": "text",
                "text": json.dumps({"error": result.error}, default=str),
            }]

        return _make_response(req_id, {
            "content": content,
            "isError": not result.success,
        })

    def run_stdio(self) -> None:
        """Run the MCP server over stdio (blocking).

        Reads JSON-RPC messages from stdin, processes them,
        and writes responses to stdout.
        """
        logger.info("Fantasy AI MCP server starting (stdio mode)...")

        for line in sys.stdin:
            line = line.strip()
            if not line:
                continue

            try:
                request = json.loads(line)
            except json.JSONDecodeError:
                error_resp = _make_error(
                    None, -32700, "Parse error: invalid JSON"
                )
                sys.stdout.write(json.dumps(error_resp) + "\n")
                sys.stdout.flush()
                continue

            response = self.handle_request(request)
            if response is not None:
                sys.stdout.write(json.dumps(response) + "\n")
                sys.stdout.flush()

        logger.info("Fantasy AI MCP server stopped.")


def main() -> None:
    """Entry point for running the MCP server as a standalone process."""
    server = FantasyAIMCPServer()
    server.run_stdio()


if __name__ == "__main__":
    main()
