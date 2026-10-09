"""Comprehensive Test Suite for the Investigate-First Agentic AI Assistant.

Validates all 12 query categories, multi-agent coordination, multi-turn memory,
evidence synthesis, selective RAG, and end-to-end evaluation prompts.
"""

from __future__ import annotations

import pandas as pd
import pytest
from unittest.mock import MagicMock

from src.agentic.conversation_state import extract_conversation_state
from src.agentic.orchestrator import AgentOrchestrator
from src.agentic.planner import (
    INTENT_CAPTAINCY,
    INTENT_CHIP_STRATEGY,
    INTENT_DIFFERENTIAL_SEARCH,
    INTENT_PLAYER_COMPARISON,
    INTENT_RESEARCH_QUESTION,
    INTENT_SIMPLE_LOOKUP,
    INTENT_SQUAD_ANALYSIS,
    INTENT_TRANSFER_DECISION,
    create_investigation_plan,
)
from src.api.state import AppState


def _make_mock_app_state() -> AppState:
    """Build mock AppState with predictions, fixtures, and metadata."""
    state = MagicMock()
    df = pd.DataFrame([
        {
            "element": 1, "id": 1, "web_name": "Salah", "name": "Mohamed Salah",
            "team": "Liverpool", "position": "MID", "team_id": 1,
            "cost": 13.0, "value": 13.0, "now_cost": 130,
            "predicted_points": 8.5, "predicted_expected_points": 8.5, "predicted_total_points": 8.5,
            "score_d": 8.5, "form": 8.1, "fpl_form": "8.1",
            "chance_of_playing_next_round": 100, "news": "",
            "status": "a", "availability_status": "fit",
            "selected_by_percent": 45.0, "minutes": 2100, "availability_expected_minutes": 90.0,
            "expected_goals": 14.0, "expected_assists": 8.0, "expected_goal_involvements": 22.0,
            "captaincy_score": 18.5, "rank": 1,
        },
        {
            "element": 2, "id": 2, "web_name": "Palmer", "name": "Cole Palmer",
            "team": "Chelsea", "position": "MID", "team_id": 2,
            "cost": 10.8, "value": 10.8, "now_cost": 108,
            "predicted_points": 7.4, "predicted_expected_points": 7.4, "predicted_total_points": 7.4,
            "score_d": 7.4, "form": 7.5, "fpl_form": "7.5",
            "chance_of_playing_next_round": 100, "news": "",
            "status": "a", "availability_status": "fit",
            "selected_by_percent": 38.0, "minutes": 2000, "availability_expected_minutes": 90.0,
            "expected_goals": 12.0, "expected_assists": 7.0, "expected_goal_involvements": 19.0,
            "captaincy_score": 15.2, "rank": 2,
        },
        {
            "element": 3, "id": 3, "web_name": "Saka", "name": "Bukayo Saka",
            "team": "Arsenal", "position": "MID", "team_id": 3,
            "cost": 10.2, "value": 10.2, "now_cost": 102,
            "predicted_points": 7.9, "predicted_expected_points": 7.9, "predicted_total_points": 7.9,
            "score_d": 7.9, "form": 8.0, "fpl_form": "8.0",
            "chance_of_playing_next_round": 100, "news": "",
            "status": "a", "availability_status": "fit",
            "selected_by_percent": 34.0, "minutes": 1950, "availability_expected_minutes": 90.0,
            "expected_goals": 11.5, "expected_assists": 9.2, "expected_goal_involvements": 20.7,
            "captaincy_score": 16.0, "rank": 3,
        },
        {
            "element": 4, "id": 4, "web_name": "Mbeumo", "name": "Bryan Mbeumo",
            "team": "Brentford", "position": "MID", "team_id": 4,
            "cost": 7.3, "value": 7.3, "now_cost": 73,
            "predicted_points": 6.8, "predicted_expected_points": 6.8, "predicted_total_points": 6.8,
            "score_d": 6.8, "form": 7.2, "fpl_form": "7.2",
            "chance_of_playing_next_round": 100, "news": "",
            "status": "a", "availability_status": "fit",
            "selected_by_percent": 11.5, "minutes": 1800, "availability_expected_minutes": 90.0,
            "expected_goals": 8.0, "expected_assists": 4.0, "expected_goal_involvements": 12.0,
            "captaincy_score": 12.0, "rank": 4, "differential_flag": True,
        },
    ])
    state.predictions = df
    state.predicted_gameweek = 6
    state.fixture_context = None
    state.player_availability = None
    state.settings = MagicMock()
    return state


class TestInvestigationAssistant:
    """Test suite verifying the Investigate-First architecture."""

    def setup_method(self):
        self.app_state = _make_mock_app_state()
        self.orchestrator = AgentOrchestrator(self.app_state)

    # 1. Simple lookup
    def test_simple_lookup_minimal_tools(self):
        result = self.orchestrator.process("Who is Palmer?")
        assert result.plan.intent == INTENT_SIMPLE_LOOKUP
        assert len(result.agents_used) == 1
        assert "player_analysis" in result.agents_used
        assert result.plan.is_complex is False
        assert "Palmer" in result.formatted_fallback

    # 2. Complex transfer decision
    def test_complex_transfer_decision(self):
        result = self.orchestrator.process("Should I sell Palmer for Saka?")
        assert result.plan.intent == INTENT_TRANSFER_DECISION
        assert result.plan.is_complex is True
        assert "Palmer" in result.plan.entities
        assert "Saka" in result.plan.entities
        assert len(result.agents_used) >= 2
        # Decision matrix check
        assert result.decision is not None
        assert "Transfer Decision" in result.formatted_fallback
        assert "Verdict" in result.formatted_fallback
        assert "free transfer" in result.formatted_fallback.lower()
        assert "-4 hit" in result.formatted_fallback.lower()

    # 3. Head-to-head comparison
    def test_player_comparison(self):
        result = self.orchestrator.process("Compare Salah and Saka for the next 5 gameweeks")
        assert result.plan.intent == INTENT_PLAYER_COMPARISON
        assert result.plan.is_complex is True
        assert "Winner" in result.formatted_fallback or "Head-to-Head" in result.formatted_fallback
        assert "Key Differences" in result.formatted_fallback

    # 4. Chip strategy with RAG
    def test_chip_strategy_uses_rag(self):
        result = self.orchestrator.process("Should I wildcard now?")
        assert result.plan.intent == INTENT_CHIP_STRATEGY
        assert result.plan.use_rag is True
        assert result.plan.rag_category == "chips"
        assert result.knowledge_context is not None
        assert result.knowledge_context.get("has_knowledge") is True
        assert "Wildcard" in result.formatted_fallback
        assert "Source: FPL" in result.formatted_fallback

    # 5. RAG not called for purely live lookup
    def test_rag_not_called_for_live_lookup(self):
        result = self.orchestrator.process("Who is Salah?")
        assert result.plan.use_rag is False
        # Research agent not in required agents
        assert "research" not in result.plan.required_agents

    # 6. Missing squad context asks focused clarification
    def test_missing_squad_asks_clarification(self):
        result = self.orchestrator.process("Analyze my squad and tell me the biggest weakness")
        assert result.plan.intent == INTENT_SQUAD_ANALYSIS
        assert result.plan.missing_context == "user_squad"
        assert "I can't see your specific 15-man squad" in result.formatted_fallback

    # 7. Follow-up conversation memory
    def test_follow_up_conversation_context(self):
        history = [
            {"role": "user", "content": "Should I sell Palmer?"},
            {"role": "assistant", "content": "I would hold Palmer for now."},
        ]
        conv_state = extract_conversation_state(history, "What about Saka instead?", ["Saka"])
        assert conv_state.is_follow_up is True
        assert "Saka" in conv_state.active_players
        assert "Palmer" in conv_state.active_players

        # Process through orchestrator with history
        result = self.orchestrator.process("What about Saka instead?", conversation_history=history)
        assert "Saka" in result.plan.entities
        assert "Palmer" in result.plan.entities
        assert result.plan.intent == INTENT_TRANSFER_DECISION

    # 8. Differential search
    def test_differential_search(self):
        result = self.orchestrator.process("Give me 3 differential picks for this gameweek")
        assert result.plan.intent == INTENT_DIFFERENTIAL_SEARCH
        assert "Differential" in result.formatted_fallback
        assert "Ownership" in result.formatted_fallback

    # 9. Captaincy recommendation
    def test_captaincy_recommendation(self):
        result = self.orchestrator.process("Who should I captain this week and why?")
        assert result.plan.intent == INTENT_CAPTAINCY
        assert "Armband Pick" in result.formatted_fallback or "Captain" in result.formatted_fallback
        assert "Salah" in result.formatted_fallback

    # 10. Research rules question
    def test_research_rules_question(self):
        result = self.orchestrator.process("How does the bonus points system work?")
        assert result.plan.intent == INTENT_RESEARCH_QUESTION
        assert result.plan.use_rag is True
        assert result.knowledge_context is not None

    # 11. No fake confidence
    def test_no_fake_confidence(self):
        result = self.orchestrator.process("Should I sell Palmer for Saka?")
        for res in result.agent_results:
            assert res.confidence is None

    # 12. Graceful tool error handling
    def test_graceful_tool_error_handling(self):
        # Even on arbitrary text, orchestrator executes without crashing
        result = self.orchestrator.process("asdkfjhasdf unexpected input 1234")
        assert result.context_for_llm != ""
        assert result.total_time_ms >= 0


class TestEvaluationDemonstrationPrompts:
    """Evaluates the 8 mandatory demonstration prompts from the specification."""

    def setup_method(self):
        self.app_state = _make_mock_app_state()
        self.orchestrator = AgentOrchestrator(self.app_state)

    def test_demo_1_sell_palmer_for_saka(self):
        r = self.orchestrator.process("Should I sell Palmer for Saka?")
        assert r.plan.intent == INTENT_TRANSFER_DECISION
        assert len(r.agents_used) >= 2
        assert "Verdict" in r.formatted_fallback
        print(f"\n[DEMO 1] Time: {r.total_time_ms}ms | Agents: {r.agents_used}")

    def test_demo_2_compare_salah_and_saka(self):
        r = self.orchestrator.process("Compare Salah and Saka for the next 5 gameweeks.")
        assert r.plan.intent == INTENT_PLAYER_COMPARISON
        assert "Salah" in r.plan.entities and "Saka" in r.plan.entities
        print(f"\n[DEMO 2] Time: {r.total_time_ms}ms | Agents: {r.agents_used}")

    def test_demo_3_wildcard_now(self):
        r = self.orchestrator.process("Should I wildcard now?")
        assert r.plan.intent == INTENT_CHIP_STRATEGY
        assert r.plan.use_rag is True
        print(f"\n[DEMO 3] Time: {r.total_time_ms}ms | Agents: {r.agents_used}")

    def test_demo_4_squad_weakness(self):
        r = self.orchestrator.process("Analyze my squad and tell me the biggest weakness.")
        assert r.plan.intent == INTENT_SQUAD_ANALYSIS
        assert r.plan.missing_context == "user_squad"
        print(f"\n[DEMO 4] Time: {r.total_time_ms}ms | Agents: {r.agents_used}")

    def test_demo_5_captain_pick(self):
        r = self.orchestrator.process("Who should I captain this week and why?")
        assert r.plan.intent == INTENT_CAPTAINCY
        assert "Salah" in r.formatted_fallback
        print(f"\n[DEMO 5] Time: {r.total_time_ms}ms | Agents: {r.agents_used}")

    def test_demo_6_differential_picks(self):
        r = self.orchestrator.process("Give me 3 differential picks for this gameweek.")
        assert r.plan.intent == INTENT_DIFFERENTIAL_SEARCH
        assert "Ownership" in r.formatted_fallback
        print(f"\n[DEMO 6] Time: {r.total_time_ms}ms | Agents: {r.agents_used}")

    def test_demo_7_minus_4_hit(self):
        r = self.orchestrator.process("Is taking a -4 hit for this transfer worth it?")
        assert r.plan.intent == INTENT_TRANSFER_DECISION
        print(f"\n[DEMO 7] Time: {r.total_time_ms}ms | Agents: {r.agents_used}")

    def test_demo_8_biggest_risks(self):
        r = self.orchestrator.process("What are the biggest risks in my current team?")
        assert r.plan.intent == INTENT_SQUAD_ANALYSIS
        print(f"\n[DEMO 8] Time: {r.total_time_ms}ms | Agents: {r.agents_used}")

    def test_partial_squad_analysis_9_players(self):
        query = (
            "Analyze these 9 players and identify my biggest weakness: "
            "Salah, Palmer, Saka, Haaland, Watkins, Isak, Gabriel, Saliba, Porro"
        )
        r = self.orchestrator.process(query)
        assert r.plan.intent == INTENT_SQUAD_ANALYSIS
        # Must not be a hard block
        assert "I can't see your specific 15-man squad" not in r.decision.formatted_text
        # Must analyze the provided players and include provisional squad notice
        assert "Provisional" in r.decision.formatted_text or "Incomplete Squad" in r.decision.formatted_text
        assert "Weaknesses" in r.decision.formatted_text

    def test_multiturn_reference_resolution_and_stale_prevention(self):
        # Turn 1: Compare Watkins and Isak
        r1 = self.orchestrator.process("Compare Watkins and Isak")
        assert "Watkins" in r1.plan.entities and "Isak" in r1.plan.entities
        history = [
            {"role": "user", "content": "Compare Watkins and Isak"},
            {"role": "assistant", "content": r1.decision.formatted_text},
        ]

        # Turn 2: What about Havertz instead?
        r2 = self.orchestrator.process("What about Havertz instead?", conversation_history=history)
        assert "Havertz" in r2.plan.entities
        history.extend([
            {"role": "user", "content": "What about Havertz instead?"},
            {"role": "assistant", "content": r2.decision.formatted_text},
        ])

        # Turn 3: Which one has better fixtures? (No explicit names in query)
        r3 = self.orchestrator.process("Which one has better fixtures?", conversation_history=history)
        assert len(r3.plan.entities) >= 1
        history.extend([
            {"role": "user", "content": "Which one has better fixtures?"},
            {"role": "assistant", "content": r3.decision.formatted_text},
        ])

        # Turn 4: Would you make the transfer for a -4? (Follow-up hit strategy)
        r4 = self.orchestrator.process("Would you make the transfer for a -4?", conversation_history=history)
        assert r4.plan.intent == INTENT_TRANSFER_DECISION
        assert len(r4.plan.entities) >= 1
        history.extend([
            {"role": "user", "content": "Would you make the transfer for a -4?"},
            {"role": "assistant", "content": r4.decision.formatted_text},
        ])

        # Turn 5: Fresh unrelated query should NOT inherit stale entities
        r5 = self.orchestrator.process("How do bonus points work in FPL?", conversation_history=history)
        assert r5.plan.intent == INTENT_RESEARCH_QUESTION
        assert len(r5.plan.entities) == 0
