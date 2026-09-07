"""Unit and integration tests for the Match Predictions API and service."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient

from src.api.main import create_app
from src.api.schemas import MatchPredictionResponse
from src.api.services.match_prediction_service import MatchPredictionService
from src.api.state import AppState
from src.config.settings import get_settings
from src.prediction.loader import LoadedModel


class _StubMatchModel:
    """Mock fitted match model returning fixed goal predictions."""

    def predict(self, X):
        # Home (is_home=1) -> 2.1 goals, Away (is_home=0) -> 0.9 goals
        if "is_home" in X.columns:
            return np.where(X["is_home"] == 1, 2.1, 0.9)
        return np.full(len(X), 1.5)


@pytest.fixture
def mock_app_state() -> AppState:
    """Build a hermetic AppState for testing match predictions."""
    settings = get_settings()

    engineered_data = pd.DataFrame(
        {
            "season": ["2026-27"] * 6,
            "GW": [1, 1, 2, 2, 3, 3],
            "team": ["Arsenal", "Chelsea", "Arsenal", "Chelsea", "Arsenal", "Chelsea"],
            "opponent_team": ["Chelsea", "Arsenal", "Chelsea", "Arsenal", "Chelsea", "Arsenal"],
            "total_points": [50, 40, 45, 48, 52, 42],
            "goals_scored": [2, 1, 1, 2, 3, 0],
            "minutes": [990, 990, 990, 990, 990, 990],
            "was_home": [True, False, False, True, True, False],
            "finished": [True, True, True, True, True, True],
        }
    )

    predictions = pd.DataFrame(
        {
            "element": [1, 2, 3, 4],
            "name": ["Saka", "Palmer", "Gabriel", "James"],
            "team": ["Arsenal", "Chelsea", "Arsenal", "Chelsea"],
            "position": ["MID", "MID", "DEF", "DEF"],
            "predicted_expected_points": [6.5, 6.2, 4.8, 4.1],
            "predicted_fpl_rank_score": [7.1, 6.8, 5.0, 4.4],
            "prob_high_score_6": [0.45, 0.40, 0.15, 0.10],
            "value": [10.0, 10.5, 6.0, 5.5],
            "photo_url": [None, None, None, None],
            "team_logo_url": [None, None, None, None],
        }
    )

    loaded_model = LoadedModel(
        model=_StubMatchModel(),
        model_name="stub_points_model",
        feature_columns=["minutes"],
        target_column="total_points",
        train_medians={"minutes": 90.0},
        metrics={"mae": 1.0},
    )

    return AppState(
        settings=settings,
        engineered_data=engineered_data,
        loaded_model=loaded_model,
        predictions=predictions,
        player_id_column="element",
        season="2026-27",
        latest_completed_gameweek=3,
        predicted_gameweek=4,
        generated_at="2026-09-07T20:00:00Z",
    )


def test_match_prediction_service_basic(mock_app_state):
    """Test MatchPredictionService generates correct predictions and metadata."""
    service = MatchPredictionService(mock_app_state)
    service._match_model = _StubMatchModel()
    service._team_id_to_name = {1: "Arsenal", 2: "Chelsea"}
    service._fixtures_cache = [
        {
            "id": 101,
            "code": 2001,
            "event": 4,
            "team_h": 1,
            "team_a": 2,
            "kickoff_time": "2026-09-12T14:00:00Z",
        }
    ]

    response = service.predict_next_gameweek()

    # 1. Metadata check
    assert response.season == "2026-27"
    assert response.latest_completed_gameweek == 3
    assert response.predicted_gameweek == 4
    assert response.count == 1
    assert len(response.predictions) == 1

    # 2. Prediction fields check
    pred = response.predictions[0]
    assert pred.fixture_id == 101
    assert pred.home_team == "Arsenal"
    assert pred.away_team == "Chelsea"
    assert pred.predicted_home_goals == 2.1
    assert pred.predicted_away_goals == 0.9
    assert pred.home_win_probability > pred.away_win_probability
    assert pred.predicted_result == "HOME_WIN"
    assert 0.99 <= (pred.home_win_probability + pred.draw_probability + pred.away_win_probability) <= 1.01
    assert pred.confidence == pred.home_win_probability
    assert pred.confidence_level in ["HIGH", "MODERATE", "LOW"]

    # 3. Fantasy Impact integration check
    assert len(pred.top_home_players) > 0
    assert pred.top_home_players[0].name == "Saka"
    assert pred.best_captain_candidate is not None
    assert pred.best_captain_candidate.name == "Saka"
    assert pred.best_attacking_option is not None
    assert pred.best_defensive_option is not None
    assert pred.best_defensive_option.name == "Gabriel"


def test_match_prediction_dynamic_gameweek_calculation(mock_app_state):
    """Test that target gameweek increments dynamically without hardcoding."""
    mock_app_state.latest_completed_gameweek = 5
    mock_app_state.predicted_gameweek = None

    service = MatchPredictionService(mock_app_state)
    service._match_model = _StubMatchModel()
    service._team_id_to_name = {1: "Arsenal", 2: "Chelsea"}
    service._fixtures_cache = [
        {"id": 102, "event": 6, "team_h": 1, "team_a": 2, "kickoff_time": "2026-10-01T14:00:00Z"}
    ]

    response = service.predict_next_gameweek()
    assert response.latest_completed_gameweek == 5
    assert response.predicted_gameweek == 6
    assert response.count == 1
    assert response.predictions[0].gameweek == 6


def test_match_prediction_empty_fixtures_handling(mock_app_state):
    """Test graceful handling when no fixtures belong to upcoming gameweek."""
    service = MatchPredictionService(mock_app_state)
    service._fixtures_cache = []

    response = service.predict_next_gameweek()
    assert response.count == 0
    assert response.predictions == []


def test_match_prediction_model_missing_fallback(mock_app_state):
    """Test safe baseline fallback when match model artifact is missing."""
    service = MatchPredictionService(mock_app_state)
    service._match_model = None
    service._team_id_to_name = {1: "Arsenal", 2: "Chelsea"}
    service._fixtures_cache = [
        {"id": 103, "event": 4, "team_h": 1, "team_a": 2}
    ]

    response = service.predict_next_gameweek()
    assert response.count == 1
    pred = response.predictions[0]
    assert pred.predicted_home_goals > 0
    assert pred.predicted_away_goals > 0
    assert pred.home_win_probability > 0


def test_api_route_match_predictions_next_gameweek(mock_app_state):
    """Test FastAPI route GET /match-predictions/next-gameweek."""
    app = create_app()
    app.state.fantasy_ai_state = mock_app_state

    with TestClient(app) as client:
        resp = client.get("/match-predictions/next-gameweek")
        assert resp.status_code == 200
        data = resp.json()

        assert "season" in data
        assert "latest_completed_gameweek" in data
        assert "predicted_gameweek" in data
        assert "count" in data
        assert "predictions" in data
        assert isinstance(data["predictions"], list)
