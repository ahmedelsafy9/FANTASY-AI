"""Tests for Gameweek Synchronization, Stale Cache Invalidation, and Integer Rounding."""

import json
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from src.agentic.decision_engine import DecisionEngine, _format_pts
from src.agentic.planner import InvestigationPlan, INTENT_CAPTAINCY, INTENT_PLAYER_COMPARISON, INTENT_TRANSFER_DECISION
from src.api.main import create_app
from src.api.schemas import MatchPredictionResponse, PredictionListResponse
from src.api.services.match_prediction_service import MatchPredictionService
from src.api.state import AppState
from src.chatbot.service import ChatbotService
from src.chatbot.tools import ChatbotTools
from src.config.settings import ChatbotSettings, Settings
from src.prediction.gameweek_context import GameweekContext, resolve_authoritative_gameweek
from src.prediction.loader import LoadedModel


@pytest.fixture
def sample_predictions_df() -> pd.DataFrame:
    return pd.DataFrame([
        {
            "element": 1,
            "id": 1,
            "web_name": "Salah",
            "name": "Mohamed Salah",
            "team": "Liverpool",
            "position": "MID",
            "now_cost": 128,
            "predicted_expected_points": 8.4,
            "predicted_expected_points_raw": 8.4,
            "availability_status": "fit",
            "availability_expected_minutes": 90.0,
            "injury_flag": False,
            "doubt_flag": False,
            "suspension_flag": False,
            "ruled_out_flag": False,
            "team_news": "",
            "chance_of_playing_next_round": 100,
            "selected_by_percent": 45.2,
            "fpl_form": 7.8,
            "captaincy_score": 16.8,
            "opponent_team": "Everton",
            "is_home": True,
        },
        {
            "element": 2,
            "id": 2,
            "web_name": "Semenyo",
            "name": "Antoine Semenyo",
            "team": "Bournemouth",
            "position": "MID",
            "now_cost": 56,
            "predicted_expected_points": 5.7,
            "predicted_expected_points_raw": 5.7,
            "availability_status": "fit",
            "availability_expected_minutes": 90.0,
            "injury_flag": False,
            "doubt_flag": False,
            "suspension_flag": False,
            "ruled_out_flag": False,
            "team_news": "",
            "chance_of_playing_next_round": 100,
            "selected_by_percent": 8.1,
            "fpl_form": 6.2,
            "captaincy_score": 11.4,
            "opponent_team": "Southampton",
            "is_home": False,
        },
    ])


@pytest.fixture
def mock_app_state(sample_predictions_df: pd.DataFrame) -> AppState:
    settings = Settings(chatbot=ChatbotSettings(llm_api_key=""))
    loaded_model = LoadedModel(
        model=None,
        model_name="mock",
        feature_columns=[],
        target_column="target",
        train_medians={},
        metrics={},
    )
    gw_ctx = GameweekContext(
        season="2026-27",
        latest_completed_gameweek=5,
        target_gameweek=6,
        is_gameweek_active=False,
        next_deadline="2026-09-28T10:00:00Z",
        is_synchronized=True,
        source="fpl_bootstrap",
        status="synchronized",
    )
    return AppState(
        settings=settings,
        engineered_data=pd.DataFrame(),
        loaded_model=loaded_model,
        predictions=sample_predictions_df,
        player_id_column="element",
        live_metadata_available=True,
        predicted_gameweek=6,
        latest_completed_gameweek=5,
        gameweek_context=gw_ctx,
        gameweek_synced=True,
        sync_status="synchronized",
        season="2026-27",
        generated_at=datetime.now(timezone.utc).isoformat(),
        scoring_model="multi_objective_v1",
        differential_predictions=sample_predictions_df,
    )


# ======================================================================
# 1. Authoritative Gameweek Context Tests
# ======================================================================

def test_resolve_authoritative_gameweek_from_events():
    """Test resolution of target gameweek using mock events."""
    bootstrap = {
        "events": [
            {"id": 1, "is_current": False, "is_next": False, "finished": True},
            {"id": 2, "is_current": False, "is_next": False, "finished": True},
            {"id": 3, "is_current": False, "is_next": False, "finished": True},
            {"id": 4, "is_current": False, "is_next": False, "finished": True},
            {"id": 5, "is_current": False, "is_next": False, "finished": True},
            {"id": 6, "is_current": False, "is_next": True, "finished": False, "deadline_time": "2026-09-28T10:00:00Z"},
        ]
    }
    settings = Settings()
    ctx = resolve_authoritative_gameweek(settings=settings, bootstrap_data=bootstrap)
    assert ctx.target_gameweek == 6
    assert ctx.latest_completed_gameweek == 5
    assert ctx.is_gameweek_active is False
    assert ctx.is_synchronized is True
    assert ctx.status == "synchronized"


def test_resolve_authoritative_gameweek_active_round():
    """Test resolution when a gameweek is currently active (in progress)."""
    bootstrap = {
        "events": [
            {"id": 5, "is_current": True, "is_next": False, "finished": False},
            {"id": 6, "is_current": False, "is_next": True, "finished": False},
        ]
    }
    settings = Settings()
    ctx = resolve_authoritative_gameweek(settings=settings, bootstrap_data=bootstrap)
    assert ctx.target_gameweek == 6
    assert ctx.is_gameweek_active is True


# ======================================================================
# 2. Gameweek Sync in Match Prediction & Player Services
# ======================================================================

def test_match_prediction_service_sync(mock_app_state: AppState):
    """Verify MatchPredictionService synchronizes to authoritative target GW."""
    mps = MatchPredictionService(mock_app_state)
    assert mps.predicted_gameweek == 6

    # Mock fixture fetcher returning fixtures for GW 6
    with patch.object(mps, "_get_fixtures", return_value=[
        {"id": 101, "event": 6, "team_h": 1, "team_a": 2, "team_h_name": "Arsenal", "team_a_name": "Chelsea", "kickoff_time": "2026-09-28T15:00:00Z"}
    ]):
        result = mps.predict_next_gameweek()
        assert result.predicted_gameweek == 6
        assert result.gameweek_synced is True
        assert result.sync_status == "synchronized"
        assert len(result.predictions) == 1
        assert result.predictions[0].home_team == "Arsenal"


def test_chatbot_tool_gameweek_sync(mock_app_state: AppState):
    """Verify ChatbotTools.get_current_gameweek returns synced authoritative context."""
    tools = ChatbotTools(mock_app_state)
    gw_info = tools.get_current_gameweek()
    assert gw_info["target_gameweek"] == 6
    assert gw_info["gameweek_synced"] is True
    assert gw_info["sync_status"] == "synchronized"
    assert "gameweek_context" in gw_info


# ======================================================================
# 3. Whole-Number Integer Rounding in Chatbot & Decision Engine
# ======================================================================

def test_format_pts_helper():
    """Verify _format_pts eliminates decimal places correctly."""
    assert _format_pts(8.4) == "8"
    assert _format_pts(7.6) == "8"
    assert _format_pts(5.2) == "5"
    assert _format_pts(5.5) == "6"
    assert _format_pts(0.0) == "0"
    assert _format_pts("7.8") == "8"
    assert _format_pts("N/A") == "N/A"
    assert _format_pts(None) == "N/A"


def test_chatbot_captain_response_integer_rounding(mock_app_state: AppState):
    """Verify Chatbot captaincy recommendation formats points as integers without decimals."""
    chatbot = ChatbotService(app_state=mock_app_state)
    res = chatbot._fallback_response("Who should I captain this gameweek?")
    resp_text = res["response"]

    # Must contain rounded points, e.g. "8 pts", NOT "8.4 pts"
    assert "8.4" not in resp_text
    assert "8 pts" in resp_text
    assert res["model"] is None
    assert res["provider"] == "fallback"


def test_chatbot_arabic_captain_integer_rounding(mock_app_state: AppState):
    """Verify Arabic captaincy response formats points as whole numbers."""
    chatbot = ChatbotService(app_state=mock_app_state)
    res = chatbot._fallback_response("تفتكر اكبتن مين الجولة الجاية؟")
    resp_text = res["response"]

    # Must contain rounded points, NOT "8.4"
    assert "8.4" not in resp_text
    assert "**8** نقطة" in resp_text


def test_decision_engine_transfer_integer_rounding():
    """Verify DecisionEngine transfer synthesis outputs integer points and delta."""
    engine = DecisionEngine()
    plan = InvestigationPlan(intent=INTENT_TRANSFER_DECISION, entities=["Salah", "Semenyo"])
    data = {
        "player_analysis": {
            "comparison": {
                "player1": {"name": "Salah", "predicted_points": 8.4, "chance_of_playing_next_round": 100},
                "player2": {"name": "Semenyo", "predicted_points": 5.7, "chance_of_playing_next_round": 100},
            }
        },
        "fixture_analysis": {},
        "news_availability": {},
    }

    decision = engine._synthesize_transfer(plan, data, [], [])
    text = decision.formatted_text

    # No decimal numbers in points or deltas
    assert "8.4" not in text
    assert "5.7" not in text
    assert "2.7" not in text
    assert "8 pts" in text
    assert "6 pts" in text


def test_decision_engine_captaincy_integer_rounding():
    """Verify DecisionEngine captaincy synthesis rounds points to whole numbers."""
    engine = DecisionEngine()
    plan = InvestigationPlan(intent=INTENT_CAPTAINCY, entities=[])
    data = {
        "squad_analysis": {
            "captain_recommendation": {
                "top_captain": {"name": "Salah", "predicted_points": 8.4},
                "vice_captain": {"name": "Palmer", "predicted_points": 7.6},
                "alternatives": [{"name": "Haaland", "predicted_points": 7.2}],
            }
        }
    }

    decision = engine._synthesize_captaincy(plan, data, [], [])
    text = decision.formatted_text

    assert "8.4" not in text
    assert "7.6" not in text
    assert "8 pts" in text
    assert "Alternative Options" in text
    assert "Differentials" not in text


# ======================================================================
# 4. Low-Ownership Gem Detection Criteria
# ======================================================================

def test_low_ownership_gem_criteria(sample_predictions_df: pd.DataFrame):
    """Verify players meeting ownership <= 10% and points >= 5.0 qualify as low ownership gems."""
    salah = sample_predictions_df.iloc[0]
    semenyo = sample_predictions_df.iloc[1]

    # Salah: 45.2% ownership -> not a low ownership gem
    assert salah["selected_by_percent"] > 10.0

    # Semenyo: 8.1% ownership, 5.7 pts -> qualifies
    assert semenyo["selected_by_percent"] <= 10.0
    assert semenyo["predicted_expected_points"] >= 5.0
