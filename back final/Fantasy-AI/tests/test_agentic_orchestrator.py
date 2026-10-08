"""Tests for the agent system and orchestrator.

Covers:
- Agent relevance scoring
- Agent selection
- Agent analysis execution
- Orchestrator context building
- Orchestrator end-to-end processing
- Player name extraction
"""

from __future__ import annotations

import pytest
from unittest.mock import MagicMock, patch
import pandas as pd

from src.agentic.agents.base import AgentResult, BaseAgent
from src.agentic.tools.base import ToolResult
from src.agentic.tools.registry import ToolRegistry
from src.agentic.orchestrator import (
    AgentOrchestrator,
    _extract_player_names,
    _extract_team_name,
)


# ---------------------------------------------------------------
# Mock Data
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
    ])


def _make_mock_app_state():
    state = MagicMock()
    state.predictions = _make_mock_predictions()
    state.season = "2026-27"
    state.predicted_gameweek = 6
    state.latest_completed_gameweek = 5
    state.generated_at = "2026-10-08T12:00:00"
    state.scoring_model = "multi_objective"
    state.differential_predictions = None
    return state


# ---------------------------------------------------------------
# Name Extraction Tests
# ---------------------------------------------------------------


class TestNameExtraction:
    """Tests for player and team name extraction from queries."""

    def test_extract_vs_pattern(self):
        names = _extract_player_names("Palmer vs Saka this week?")
        assert "Palmer" in names
        assert "Saka" in names

    def test_extract_or_pattern(self):
        names = _extract_player_names("Should I pick Salah or Haaland?")
        assert "Salah" in names
        assert "Haaland" in names

    def test_extract_transfer_pattern(self):
        names = _extract_player_names(
            "Should I sell Palmer and buy Salah?"
        )
        assert len(names) >= 2

    def test_extract_single_name(self):
        names = _extract_player_names("Tell me about Salah")
        assert "Salah" in names

    def test_no_names(self):
        names = _extract_player_names("How does the scoring system work?")
        # Should not extract common words
        assert "How" not in names
        assert "Should" not in names

    def test_extract_team_name(self):
        assert _extract_team_name("Who are the best Arsenal players?") == "Arsenal"

    def test_extract_team_name_none(self):
        assert _extract_team_name("Who should I captain?") is None

    def test_extract_liverpool(self):
        assert _extract_team_name("Liverpool fixtures") == "Liverpool"


# ---------------------------------------------------------------
# Agent Base Tests
# ---------------------------------------------------------------


class TestAgentBase:
    """Tests for agent relevance scoring and tool authorization."""

    def setup_method(self):
        from src.agentic.agents.player_agent import PlayerAnalysisAgent
        self.registry = ToolRegistry()
        self.agent = PlayerAnalysisAgent(self.registry)

    def test_can_handle_relevant_query(self):
        score = self.agent.can_handle("Tell me about this player's form")
        assert score > 0.0

    def test_can_handle_irrelevant_query(self):
        score = self.agent.can_handle("xyznonexistent1234567890")
        assert score == 0.0

    def test_keyword_matching(self):
        score_high = self.agent.can_handle(
            "Compare this player vs another player's stats form"
        )
        score_low = self.agent.can_handle("How does scoring work?")
        # More keyword matches = higher score
        assert score_high >= score_low


# ---------------------------------------------------------------
# Orchestrator Tests
# ---------------------------------------------------------------


class TestOrchestrator:
    """Tests for the agent orchestrator."""

    def setup_method(self):
        self.app_state = _make_mock_app_state()
        self.orchestrator = AgentOrchestrator(self.app_state)

    def test_orchestrator_initialized(self):
        assert self.orchestrator.tool_registry.count == 16
        assert self.orchestrator.retriever.is_ready

    def test_process_player_query(self):
        result = self.orchestrator.process("Tell me about Salah")
        assert len(result.agents_used) >= 1
        assert result.context_for_llm  # Non-empty context
        assert result.total_time_ms >= 0

    def test_process_captain_query(self):
        result = self.orchestrator.process(
            "Who should I captain this gameweek?"
        )
        assert len(result.agents_used) >= 1
        assert any(
            "captain" in agent.lower() or "squad" in agent.lower()
            for agent in result.agents_used
        )

    def test_process_injury_query(self):
        result = self.orchestrator.process(
            "Which key players are injured or doubtful?"
        )
        assert len(result.agents_used) >= 1

    def test_process_strategy_query(self):
        result = self.orchestrator.process(
            "When should I use my wildcard?"
        )
        assert len(result.agents_used) >= 1
        # Should retrieve knowledge
        if result.knowledge_context:
            assert result.knowledge_context.get("has_knowledge") is True

    def test_process_rules_query(self):
        result = self.orchestrator.process(
            "How does the FPL scoring system work?"
        )
        assert result.context_for_llm  # Should have context

    def test_process_transfer_query(self):
        result = self.orchestrator.process(
            "Should I replace Palmer with Salah?"
        )
        assert len(result.agents_used) >= 1

    def test_context_for_llm_not_empty(self):
        result = self.orchestrator.process("Generic question about FPL")
        assert "AGENT ANALYSIS RESULTS" in result.context_for_llm
        assert "END ANALYSIS" in result.context_for_llm

    def test_max_agents_limit(self):
        result = self.orchestrator.process(
            "Tell me about Salah's form, captain him, and check injuries"
        )
        # Should not invoke more than 3 agents
        assert len(result.agents_used) <= 3

    def test_tool_calls_tracked(self):
        result = self.orchestrator.process("Who are the injured players?")
        # Should have at least one tool call
        assert len(result.all_tool_calls) >= 1
