"""Unit tests for the Chatbot tools, PlayerResolver, and ChatbotService."""

from datetime import datetime, timezone
import pandas as pd
import pytest

from src.chatbot.player_resolver import PlayerResolver
from src.chatbot.tools import ChatbotTools, TOOL_DEFINITIONS
from src.chatbot.service import ChatbotService
from src.api.state import AppState
from src.config.settings import Settings


@pytest.fixture
def sample_predictions() -> pd.DataFrame:
    return pd.DataFrame([
        {
            "element": 1,
            "id": 1,
            "web_name": "Salah",
            "first_name": "Mohamed",
            "second_name": "Salah",
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
            "differential_flag": False,
        },
        {
            "element": 2,
            "id": 2,
            "web_name": "Palmer",
            "first_name": "Cole",
            "second_name": "Palmer",
            "name": "Cole Palmer",
            "team": "Chelsea",
            "position": "MID",
            "now_cost": 108,
            "predicted_expected_points": 7.6,
            "predicted_expected_points_raw": 7.6,
            "availability_status": "fit",
            "availability_expected_minutes": 90.0,
            "injury_flag": False,
            "doubt_flag": False,
            "suspension_flag": False,
            "ruled_out_flag": False,
            "team_news": "",
            "chance_of_playing_next_round": 100,
            "selected_by_percent": 38.0,
            "fpl_form": 8.1,
            "captaincy_score": 15.2,
            "differential_flag": False,
        },
        {
            "element": 3,
            "id": 3,
            "web_name": "De Bruyne",
            "first_name": "Kevin",
            "second_name": "De Bruyne",
            "name": "Kevin De Bruyne",
            "team": "Man City",
            "position": "MID",
            "now_cost": 95,
            "predicted_expected_points": 2.5,
            "predicted_expected_points_raw": 5.0,
            "availability_status": "doubtful",
            "availability_expected_minutes": 45.0,
            "injury_flag": False,
            "doubt_flag": True,
            "suspension_flag": False,
            "ruled_out_flag": False,
            "team_news": "Hamstring strain - 50% chance of playing",
            "chance_of_playing_next_round": 50,
            "selected_by_percent": 8.0,
            "fpl_form": 4.0,
            "captaincy_score": 5.0,
            "differential_flag": True,
        },
        {
            "element": 4,
            "id": 4,
            "web_name": "Saliba",
            "first_name": "William",
            "second_name": "Saliba",
            "name": "William Saliba",
            "team": "Arsenal",
            "position": "DEF",
            "now_cost": 60,
            "predicted_expected_points": 0.0,
            "predicted_expected_points_raw": 4.5,
            "availability_status": "major_injury",
            "availability_expected_minutes": 0.0,
            "injury_flag": True,
            "doubt_flag": False,
            "suspension_flag": False,
            "ruled_out_flag": True,
            "team_news": "Back injury - Unknown return date",
            "chance_of_playing_next_round": 0,
            "selected_by_percent": 25.0,
            "fpl_form": 3.0,
            "captaincy_score": 0.0,
            "differential_flag": False,
        },
    ])


from src.prediction.loader import LoadedModel


@pytest.fixture
def mock_app_state(sample_predictions: pd.DataFrame) -> AppState:
    settings = Settings()
    loaded_model = LoadedModel(
        model=None,
        model_name="mock",
        feature_columns=[],
        target_column="target",
        train_medians={},
        metrics={},
    )
    return AppState(
        settings=settings,
        engineered_data=pd.DataFrame(),
        loaded_model=loaded_model,
        predictions=sample_predictions,
        player_id_column="element",
        live_metadata_available=True,
        predicted_gameweek=5,
        latest_completed_gameweek=4,
        season="2026-27",
        generated_at=datetime.now(timezone.utc).isoformat(),
        scoring_model="multi_objective_v1",
        differential_predictions=sample_predictions[sample_predictions["differential_flag"] == True],
    )


def test_player_resolver_english(sample_predictions: pd.DataFrame):
    resolver = PlayerResolver(sample_predictions)
    
    # Exact web name
    res = resolver.resolve("Salah")
    assert len(res) >= 1
    assert res[0]["web_name"] == "Salah"

    # Full name
    res = resolver.resolve("Cole Palmer")
    assert len(res) >= 1
    assert res[0]["web_name"] == "Palmer"

    # Abbreviation
    res = resolver.resolve("KDB")
    assert len(res) >= 1
    assert res[0]["web_name"] == "De Bruyne"


def test_player_resolver_arabic(sample_predictions: pd.DataFrame):
    resolver = PlayerResolver(sample_predictions)

    # Arabic transliteration for Salah
    res = resolver.resolve("صلاح")
    assert len(res) >= 1
    assert res[0]["web_name"] == "Salah"

    # Arabic for Palmer
    res = resolver.resolve("بالمر")
    assert len(res) >= 1
    assert res[0]["web_name"] == "Palmer"


def test_chatbot_tools(mock_app_state: AppState):
    tools = ChatbotTools(mock_app_state)

    # 1. search_player_by_name
    search_res = tools.search_player_by_name("Salah")
    assert isinstance(search_res, list)
    assert len(search_res) >= 1
    assert search_res[0]["web_name"] == "Salah"

    # 2. get_player_info
    info = tools.get_player_info(player_name="Palmer")
    assert info["web_name"] == "Palmer"
    assert info["team"] == "Chelsea"

    # 3. get_player_availability
    avail = tools.get_player_availability(player_name="Saliba")
    assert avail["availability_status"] == "major_injury"
    assert avail["ruled_out_flag"] is True

    # 4. compare_players
    comp = tools.compare_players("Salah", "Palmer")
    assert "player1" in comp
    assert "player2" in comp
    assert comp["player1"]["web_name"] == "Salah"
    assert comp["player2"]["web_name"] == "Palmer"

    # 5. get_captain_recommendation
    cap = tools.get_captain_recommendation()
    assert "candidates" in cap

    # 6. get_current_gameweek
    gw = tools.get_current_gameweek()
    assert gw["predicted_gameweek"] == 5

    # 7. get_injured_doubtful_players
    inj = tools.get_injured_doubtful_players()
    assert inj["count"] >= 2


def test_chatbot_service_fallback(mock_app_state: AppState):
    # Without API key, service should return graceful fallback response
    service = ChatbotService(mock_app_state, api_key="")
    assert service.is_configured is False

    res = service._fallback_response("Who should I captain?")
    assert "response" in res
    assert "captain" in res["response"].lower() or "candidate" in res["response"].lower()

    res_inj = service._fallback_response("Are there injured players?")
    assert "response" in res_inj
    assert "players" in res_inj["response"].lower()
