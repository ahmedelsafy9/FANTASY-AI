"""Tests for the Fantasy AI MCP server.

Covers:
- MCP JSON-RPC protocol handling
- initialize handshake
- tools/list endpoint
- tools/call execution
- Error handling (unknown methods, invalid JSON, tool errors)
- Ping / notification handling
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock

import pandas as pd
import pytest

from src.agentic.mcp.server import FantasyAIMCPServer, JSONRPC_VERSION, MCP_PROTOCOL_VERSION
from src.agentic.tools.definitions import build_tool_registry


@pytest.fixture
def mock_app_state():
    """Create a minimal mock AppState with predictions data."""
    state = MagicMock()
    df = pd.DataFrame([
        {
            "id": 1,
            "web_name": "Haaland",
            "name": "Erling Haaland",
            "position": "FWD",
            "team_name": "Man City",
            "team": 1,
            "cost": 15.0,
            "predicted_points": 8.5,
            "chance_of_playing_next_round": 100,
            "news": "",
            "status": "a",
            "selected_by_percent": 65.0,
            "form": 8.2,
            "total_points": 180,
            "minutes": 2100,
            "goals_scored": 20,
            "assists": 5,
            "clean_sheets": 0,
            "expected_goals": 18.5,
            "expected_assists": 4.2,
            "expected_goal_involvements": 22.7,
            "transfers_in_event": 50000,
            "transfers_out_event": 5000,
            "rank": 1,
        },
        {
            "id": 2,
            "web_name": "Salah",
            "name": "Mohamed Salah",
            "position": "MID",
            "team_name": "Liverpool",
            "team": 2,
            "cost": 13.0,
            "predicted_points": 7.8,
            "chance_of_playing_next_round": 100,
            "news": "",
            "status": "a",
            "selected_by_percent": 45.0,
            "form": 7.5,
            "total_points": 170,
            "minutes": 2050,
            "goals_scored": 16,
            "assists": 9,
            "clean_sheets": 8,
            "expected_goals": 14.0,
            "expected_assists": 8.0,
            "expected_goal_involvements": 22.0,
            "transfers_in_event": 40000,
            "transfers_out_event": 8000,
            "rank": 2,
        },
    ])
    state.predictions = df
    state.fixture_context = None
    state.player_availability = None
    return state


class TestMCPServer:
    """Tests for FantasyAIMCPServer."""

    def test_initialize(self, mock_app_state):
        server = FantasyAIMCPServer(app_state=mock_app_state)
        req = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "test-client", "version": "1.0"},
            },
        }
        resp = server.handle_request(req)
        assert resp is not None
        assert resp["jsonrpc"] == "2.0"
        assert resp["id"] == 1
        assert "result" in resp
        result = resp["result"]
        assert result["protocolVersion"] == MCP_PROTOCOL_VERSION
        assert result["serverInfo"]["name"] == "fantasy-ai-mcp"
        assert "tools" in result["capabilities"]

    def test_tools_list(self, mock_app_state):
        server = FantasyAIMCPServer(app_state=mock_app_state)
        req = {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/list",
            "params": {},
        }
        resp = server.handle_request(req)
        assert resp is not None
        assert resp["id"] == 2
        assert "tools" in resp["result"]
        tools = resp["result"]["tools"]
        assert len(tools) >= 16

        names = {t["name"] for t in tools}
        assert "search_player_by_name" in names
        assert "compare_players" in names
        assert "get_player_form" in names
        assert "analyze_transfer" in names
        assert "analyze_squad" in names

        for tool in tools:
            assert "name" in tool
            assert "description" in tool
            assert "inputSchema" in tool

    def test_tools_call_success(self, mock_app_state):
        server = FantasyAIMCPServer(app_state=mock_app_state)
        req = {
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {
                "name": "search_player_by_name",
                "arguments": {"query": "Haaland"},
            },
        }
        resp = server.handle_request(req)
        assert resp is not None
        assert resp["id"] == 3
        result = resp["result"]
        assert result["isError"] is False
        assert len(result["content"]) == 1
        assert result["content"][0]["type"] == "text"
        data = json.loads(result["content"][0]["text"])
        assert len(data) >= 1
        assert data[0]["web_name"] == "Haaland"

    def test_tools_call_unknown_tool(self, mock_app_state):
        server = FantasyAIMCPServer(app_state=mock_app_state)
        req = {
            "jsonrpc": "2.0",
            "id": 4,
            "method": "tools/call",
            "params": {
                "name": "non_existent_tool",
                "arguments": {},
            },
        }
        resp = server.handle_request(req)
        assert resp is not None
        assert resp["id"] == 4
        result = resp["result"]
        assert result["isError"] is True
        data = json.loads(result["content"][0]["text"])
        assert "error" in data

    def test_ping(self, mock_app_state):
        server = FantasyAIMCPServer(app_state=mock_app_state)
        req = {
            "jsonrpc": "2.0",
            "id": 5,
            "method": "ping",
            "params": {},
        }
        resp = server.handle_request(req)
        assert resp is not None
        assert resp["id"] == 5
        assert resp["result"] == {}

    def test_unknown_method(self, mock_app_state):
        server = FantasyAIMCPServer(app_state=mock_app_state)
        req = {
            "jsonrpc": "2.0",
            "id": 6,
            "method": "unknown/method",
            "params": {},
        }
        resp = server.handle_request(req)
        assert resp is not None
        assert resp["id"] == 6
        assert "error" in resp
        assert resp["error"]["code"] == -32601

    def test_notification(self, mock_app_state):
        server = FantasyAIMCPServer(app_state=mock_app_state)
        req = {
            "jsonrpc": "2.0",
            "method": "notifications/initialized",
            "params": {},
        }
        resp = server.handle_request(req)
        assert resp is None
