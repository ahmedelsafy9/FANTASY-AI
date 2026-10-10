"""Route-level tests for the chatbot API endpoints."""

from datetime import datetime, timezone
import pandas as pd
import pytest
from fastapi.testclient import TestClient

from src.api.main import create_app
from src.api.state import AppState
from src.config.settings import Settings, ChatbotSettings
from src.prediction.loader import LoadedModel


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
    ])


@pytest.fixture
def client(sample_predictions: pd.DataFrame) -> TestClient:
    app = create_app()

    settings = Settings(chatbot=ChatbotSettings(llm_api_key=""))

    loaded_model = LoadedModel(
        model=None,
        model_name="mock",
        feature_columns=[],
        target_column="target",
        train_medians={},
        metrics={},
    )

    fake_state = AppState(
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
        differential_predictions=sample_predictions,
    )

    app.state.fantasy_ai_state = fake_state
    return TestClient(app)


def test_chatbot_status_endpoint(client: TestClient):
    response = client.get("/chatbot/status")
    assert response.status_code == 200
    data = response.json()
    assert data["enabled"] is True
    assert data["configured"] is False  # empty API key in fixture
    assert data["provider"] == "gemini"
    assert data["model"] == "gemini-3.8-flash"


def test_chatbot_message_fallback_endpoint(client: TestClient):
    response = client.post(
        "/chatbot/message",
        json={"message": "Who should I captain this gameweek?"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "response" in data
    assert len(data["response"]) > 0
    assert "Salah" in data["response"] or "captain" in data["response"].lower()
    assert data.get("fallback") is True
    assert data.get("provider") == "fallback"
    assert data.get("model") is None


def test_chatbot_message_validation(client: TestClient):
    # Empty message should be rejected with 422
    response = client.post(
        "/chatbot/message",
        json={"message": ""},
    )
    assert response.status_code == 422
