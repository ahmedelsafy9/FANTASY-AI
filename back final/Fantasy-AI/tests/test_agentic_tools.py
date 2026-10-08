"""Tests for the agentic tool system.

Covers:
- Tool schemas
- Tool execution with mock data
- Tool registry operations
- Tool failure handling
- Input validation
"""

from __future__ import annotations

import pytest
import pandas as pd
from unittest.mock import MagicMock, patch
from dataclasses import dataclass

from src.agentic.tools.base import BaseTool, ToolParameter, ToolResult
from src.agentic.tools.registry import ToolRegistry


# ---------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------


def _make_mock_predictions() -> pd.DataFrame:
    """Create a minimal predictions DataFrame for testing."""
    return pd.DataFrame([
        {
            "element": 1, "web_name": "Salah", "name": "Mohamed Salah",
            "first_name": "Mohamed", "second_name": "Salah",
            "team": "Liverpool", "position": "MID",
            "value": 13.0, "now_cost": 130,
            "predicted_expected_points": 8.5,
            "predicted_total_points": 8.5,
            "score_d": 8.5,
            "availability_status": "fit",
            "injury_flag": False, "doubt_flag": False,
            "suspension_flag": False, "ruled_out_flag": False,
            "expected_to_start": True,
            "availability_expected_minutes": 90.0,
            "rotation_risk": 0.0,
            "team_news": None, "team_news_flag": False,
            "chance_of_playing_next_round": 100,
            "selected_by_percent": 45.0,
            "opponent_team": "Burnley", "is_home": True,
            "fixture_difficulty": 2.0,
            "total_points_avg_last_3": 7.0,
            "total_points_avg_last_5": 6.5,
            "minutes_avg_last_3": 88.0,
            "minutes_avg_last_5": 87.0,
            "xG_avg_last_3": 0.5,
            "xA_avg_last_3": 0.3,
            "form_index": 8.0,
            "fpl_form": "7.5",
            "fpl_points_per_game": "7.0",
            "fpl_total_points_season": 80,
            "captaincy_score": 9.0,
            "availability_adjustment_factor": 1.0,
        },
        {
            "element": 2, "web_name": "Palmer", "name": "Cole Palmer",
            "first_name": "Cole", "second_name": "Palmer",
            "team": "Chelsea", "position": "MID",
            "value": 10.5, "now_cost": 105,
            "predicted_expected_points": 7.2,
            "predicted_total_points": 7.2,
            "score_d": 7.2,
            "availability_status": "fit",
            "injury_flag": False, "doubt_flag": False,
            "suspension_flag": False, "ruled_out_flag": False,
            "expected_to_start": True,
            "availability_expected_minutes": 90.0,
            "rotation_risk": 0.0,
            "team_news": None, "team_news_flag": False,
            "chance_of_playing_next_round": 100,
            "selected_by_percent": 35.0,
            "opponent_team": "Everton", "is_home": False,
            "fixture_difficulty": 3.0,
            "total_points_avg_last_3": 6.0,
            "total_points_avg_last_5": 5.8,
            "minutes_avg_last_3": 90.0,
            "minutes_avg_last_5": 89.0,
            "xG_avg_last_3": 0.4,
            "xA_avg_last_3": 0.4,
            "form_index": 7.0,
            "fpl_form": "6.5",
            "fpl_points_per_game": "6.0",
            "fpl_total_points_season": 65,
            "captaincy_score": 7.5,
            "availability_adjustment_factor": 1.0,
        },
        {
            "element": 3, "web_name": "Saka", "name": "Bukayo Saka",
            "first_name": "Bukayo", "second_name": "Saka",
            "team": "Arsenal", "position": "MID",
            "value": 10.0, "now_cost": 100,
            "predicted_expected_points": 6.8,
            "predicted_total_points": 6.8,
            "score_d": 6.8,
            "availability_status": "doubtful",
            "injury_flag": True, "doubt_flag": True,
            "suspension_flag": False, "ruled_out_flag": False,
            "expected_to_start": False,
            "availability_expected_minutes": 45.0,
            "rotation_risk": 0.3,
            "team_news": "Hamstring concern - 75% chance",
            "team_news_flag": True,
            "chance_of_playing_next_round": 75,
            "selected_by_percent": 25.0,
            "opponent_team": "Southampton", "is_home": True,
            "fixture_difficulty": 2.0,
            "total_points_avg_last_3": 5.5,
            "total_points_avg_last_5": 6.0,
            "minutes_avg_last_3": 75.0,
            "minutes_avg_last_5": 80.0,
            "xG_avg_last_3": 0.3,
            "xA_avg_last_3": 0.5,
            "form_index": 6.5,
            "fpl_form": "6.0",
            "fpl_points_per_game": "5.5",
            "fpl_total_points_season": 55,
            "captaincy_score": 5.0,
            "availability_adjustment_factor": 0.75,
        },
        {
            "element": 4, "web_name": "Haaland", "name": "Erling Haaland",
            "first_name": "Erling", "second_name": "Haaland",
            "team": "Man City", "position": "FWD",
            "value": 14.0, "now_cost": 140,
            "predicted_expected_points": 7.8,
            "predicted_total_points": 7.8,
            "score_d": 7.8,
            "availability_status": "fit",
            "injury_flag": False, "doubt_flag": False,
            "suspension_flag": False, "ruled_out_flag": False,
            "expected_to_start": True,
            "availability_expected_minutes": 90.0,
            "rotation_risk": 0.0,
            "team_news": None, "team_news_flag": False,
            "chance_of_playing_next_round": 100,
            "selected_by_percent": 55.0,
            "opponent_team": "Fulham", "is_home": True,
            "fixture_difficulty": 2.0,
            "total_points_avg_last_3": 7.5,
            "total_points_avg_last_5": 7.0,
            "minutes_avg_last_3": 90.0,
            "minutes_avg_last_5": 88.0,
            "xG_avg_last_3": 0.8,
            "xA_avg_last_3": 0.1,
            "form_index": 8.5,
            "fpl_form": "8.0",
            "fpl_points_per_game": "7.5",
            "fpl_total_points_season": 90,
            "captaincy_score": 8.5,
            "availability_adjustment_factor": 1.0,
        },
    ])


def _make_mock_app_state(predictions=None):
    """Create a minimal AppState mock."""
    if predictions is None:
        predictions = _make_mock_predictions()

    state = MagicMock()
    state.predictions = predictions
    state.season = "2026-27"
    state.predicted_gameweek = 6
    state.latest_completed_gameweek = 5
    state.generated_at = "2026-10-08T12:00:00"
    state.scoring_model = "multi_objective"
    state.differential_predictions = None
    return state


# ---------------------------------------------------------------
# Tool Base Tests
# ---------------------------------------------------------------


class DummyTool(BaseTool):
    """Minimal tool for testing the base class."""

    @property
    def name(self):
        return "dummy_tool"

    @property
    def description(self):
        return "A test tool."

    @property
    def parameters(self):
        return [
            ToolParameter(
                name="query",
                type="string",
                description="Test query",
                required=True,
            ),
            ToolParameter(
                name="limit",
                type="integer",
                description="Optional limit",
                required=False,
                default=10,
            ),
        ]

    def _execute(self, **kwargs):
        return {"query": kwargs["query"], "limit": kwargs.get("limit", 10)}


class FailingTool(BaseTool):
    """Tool that always raises an error."""

    @property
    def name(self):
        return "failing_tool"

    @property
    def description(self):
        return "Always fails."

    @property
    def parameters(self):
        return []

    def _execute(self, **kwargs):
        raise ValueError("Intentional test error")


class TestToolBase:
    """Tests for BaseTool and ToolResult."""

    def test_successful_execution(self):
        tool = DummyTool()
        result = tool.execute(query="test")
        assert result.success is True
        assert result.data == {"query": "test", "limit": 10}
        assert result.tool_name == "dummy_tool"
        assert result.execution_time_ms >= 0

    def test_missing_required_parameter(self):
        tool = DummyTool()
        result = tool.execute()  # Missing 'query'
        assert result.success is False
        assert "Missing required parameter" in result.error

    def test_default_parameter_applied(self):
        tool = DummyTool()
        result = tool.execute(query="test")
        assert result.data["limit"] == 10

    def test_explicit_parameter_override(self):
        tool = DummyTool()
        result = tool.execute(query="test", limit=5)
        assert result.data["limit"] == 5

    def test_tool_failure_handled(self):
        tool = FailingTool()
        result = tool.execute()
        assert result.success is False
        assert "Intentional test error" in result.error

    def test_schema_export(self):
        tool = DummyTool()
        schema = tool.to_schema()
        assert schema["name"] == "dummy_tool"
        assert "query" in schema["parameters"]["properties"]
        assert "required" in schema["parameters"]
        assert "query" in schema["parameters"]["required"]

    def test_tool_result_to_dict(self):
        result = ToolResult(
            success=True, data={"key": "value"},
            tool_name="test", source="test_source",
        )
        d = result.to_dict()
        assert d["success"] is True
        assert d["data"] == {"key": "value"}
        assert d["source"] == "test_source"


# ---------------------------------------------------------------
# Registry Tests
# ---------------------------------------------------------------


class TestToolRegistry:
    """Tests for the ToolRegistry."""

    def test_register_and_lookup(self):
        registry = ToolRegistry()
        registry.register(DummyTool())
        assert "dummy_tool" in registry
        assert registry.get("dummy_tool") is not None

    def test_duplicate_registration_raises(self):
        registry = ToolRegistry()
        registry.register(DummyTool())
        with pytest.raises(ValueError, match="already registered"):
            registry.register(DummyTool())

    def test_execute_via_registry(self):
        registry = ToolRegistry()
        registry.register(DummyTool())
        result = registry.execute("dummy_tool", query="hello")
        assert result.success is True
        assert result.data["query"] == "hello"

    def test_execute_unknown_tool(self):
        registry = ToolRegistry()
        result = registry.execute("nonexistent")
        assert result.success is False
        assert "Unknown tool" in result.error

    def test_list_tools(self):
        registry = ToolRegistry()
        registry.register(DummyTool())
        registry.register(FailingTool())
        names = registry.list_tools()
        assert "dummy_tool" in names
        assert "failing_tool" in names

    def test_get_all_schemas(self):
        registry = ToolRegistry()
        registry.register(DummyTool())
        schemas = registry.get_all_schemas()
        assert len(schemas) == 1
        assert schemas[0]["name"] == "dummy_tool"

    def test_count_and_len(self):
        registry = ToolRegistry()
        assert registry.count == 0
        registry.register(DummyTool())
        assert registry.count == 1
        assert len(registry) == 1


# ---------------------------------------------------------------
# Tool Definitions Tests (with mock AppState)
# ---------------------------------------------------------------


class TestToolDefinitions:
    """Tests for the concrete tool definitions using mock data."""

    def setup_method(self):
        from src.agentic.tools.definitions import build_tool_registry
        self.app_state = _make_mock_app_state()
        self.registry = build_tool_registry(self.app_state)

    def test_registry_has_all_tools(self):
        """All 16 tools should be registered."""
        assert self.registry.count == 16
        expected_tools = [
            "search_player_by_name", "get_player_info",
            "get_player_availability", "get_gameweek_predictions",
            "compare_players", "get_captain_recommendation",
            "get_current_gameweek", "get_team_players",
            "get_fixture_info", "get_top_by_position",
            "get_differential_picks", "get_injured_doubtful_players",
            "get_player_form", "get_player_stats",
            "analyze_transfer", "analyze_squad",
        ]
        for name in expected_tools:
            assert name in self.registry, f"Missing tool: {name}"

    def test_search_player(self):
        result = self.registry.execute("search_player_by_name", query="Salah")
        assert result.success is True
        assert isinstance(result.data, list)
        assert len(result.data) >= 1

    def test_get_player_info(self):
        result = self.registry.execute("get_player_info", player_name="Salah")
        assert result.success is True
        assert result.data.get("web_name") == "Salah"

    def test_get_player_info_not_found(self):
        result = self.registry.execute(
            "get_player_info", player_name="NonexistentPlayer123"
        )
        assert result.success is True  # Tool succeeds but returns error in data
        assert "error" in result.data

    def test_get_player_availability(self):
        result = self.registry.execute(
            "get_player_availability", player_name="Saka"
        )
        assert result.success is True
        assert result.data.get("availability_status") == "doubtful"

    def test_compare_players(self):
        result = self.registry.execute(
            "compare_players",
            player1_name="Salah",
            player2_name="Palmer",
        )
        assert result.success is True
        assert "player1" in result.data
        assert "player2" in result.data

    def test_get_captain_recommendation(self):
        result = self.registry.execute("get_captain_recommendation")
        assert result.success is True
        assert "candidates" in result.data

    def test_get_current_gameweek(self):
        result = self.registry.execute("get_current_gameweek")
        assert result.success is True
        assert result.data["season"] == "2026-27"
        assert result.data["predicted_gameweek"] == 6

    def test_get_injured_doubtful(self):
        result = self.registry.execute("get_injured_doubtful_players")
        assert result.success is True
        assert "players" in result.data
        # Saka is doubtful in our mock data
        names = [p.get("web_name") for p in result.data["players"]]
        assert "Saka" in names

    def test_get_player_form(self):
        result = self.registry.execute(
            "get_player_form", player_name="Salah"
        )
        assert result.success is True
        assert "total_points_avg_last_3" in result.data

    def test_get_player_stats(self):
        result = self.registry.execute(
            "get_player_stats", player_name="Palmer"
        )
        assert result.success is True
        assert "fpl_total_points_season" in result.data

    def test_analyze_transfer(self):
        result = self.registry.execute(
            "analyze_transfer",
            player_out="Palmer",
            player_in="Salah",
        )
        assert result.success is True
        assert "player_out" in result.data
        assert "player_in" in result.data
        assert "points_gain" in result.data

    def test_analyze_squad(self):
        result = self.registry.execute(
            "analyze_squad",
            player_names="Salah, Palmer, Saka, Haaland",
        )
        assert result.success is True
        assert result.data["squad_size"] == 4
        # Saka should appear in injury risks
        risk_names = [r["name"] for r in result.data["injury_risks"]]
        assert "Saka" in risk_names

    def test_get_gameweek_predictions(self):
        result = self.registry.execute(
            "get_gameweek_predictions", limit=3
        )
        assert result.success is True
        assert result.data["count"] <= 3

    def test_tool_schemas_valid(self):
        """All tool schemas should have name and description."""
        schemas = self.registry.get_all_schemas()
        for schema in schemas:
            assert "name" in schema
            assert "description" in schema
            assert "parameters" in schema
            assert schema["parameters"]["type"] == "object"
