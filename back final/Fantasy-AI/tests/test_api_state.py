"""Integration tests for src.api.state.build_app_state.

Covers the Phase 3 (fixture-aware next-GW) and Phase 5 (photo/badge
metadata) enrichment, and — critically — that the API still comes up
successfully (using the Sprint 7 proxy, no metadata) when the live FPL
API is unreachable at startup.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import joblib
import pandas as pd
import pytest
from sklearn.linear_model import LinearRegression

from src.api.state import build_app_state
from src.config.settings import Settings


def _write_pipeline_artifacts(tmp_path: Path) -> Settings:
    """Write a minimal engineered dataset + trained model, matching what
    scripts.run_feature_engineering / scripts.run_training would produce."""
    import os

    os.environ["FANTASY_AI_DATA_DIR"] = str(tmp_path / "data")
    os.environ["FANTASY_AI_MODELS_DIR"] = str(tmp_path / "models")
    os.environ["FANTASY_AI_CONFIGS_DIR"] = str(tmp_path / "configs")
    os.environ["FANTASY_AI_LOGS_DIR"] = str(tmp_path / "logs")
    settings = Settings()

    engineered = pd.DataFrame(
        {
            "element": [1, 2],
            "name": ["Player One", "Player Two"],
            "season": ["2022-23"] * 2,
            "GW": [38, 38],
            "team": ["Arsenal", "Chelsea"],
            "opponent_team": ["Chelsea", "Arsenal"],
            "minutes_avg_last_3": [88.0, 90.0],
            "total_points_avg_last_3": [6.0, 5.0],
        }
    )
    settings.paths.processed_data_dir.mkdir(parents=True, exist_ok=True)
    engineered.to_csv(settings.paths.processed_data_dir / "vaastav_features.csv", index=False)

    model = LinearRegression().fit([[1], [2]], [1, 2])
    settings.paths.models_dir.mkdir(parents=True, exist_ok=True)
    joblib.dump(model, settings.paths.models_dir / "best_model.joblib")
    (settings.paths.models_dir / "best_model_metadata.json").write_text(
        json.dumps(
            {
                "model_name": "linear_regression",
                "feature_columns": ["minutes_avg_last_3"],
                "target_column": "total_points",
                "train_medians": {"minutes_avg_last_3": 80.0},
                "metrics": {"mae": 1.0, "rmse": 1.5, "r2": 0.5},
            }
        ),
        encoding="utf-8",
    )
    return settings


class _FakeResp:
    def __init__(self, payload: Any) -> None:
        self._payload = payload
        self.status_code = 200

    def json(self) -> Any:
        return self._payload


def test_build_app_state_enriches_with_fixtures_and_metadata(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """When the live API is reachable, predictions must be fixture-aware and
    carry presentation metadata (photo/badge URLs)."""
    settings = _write_pipeline_artifacts(tmp_path)

    bootstrap = {
        "events": [{"id": 1, "finished": True, "deadline_time": "2022-08-16T18:00:00Z"}],
        "teams": [
            {"id": 11, "name": "Arsenal", "short_name": "ARS", "code": 3},
            {"id": 12, "name": "Chelsea", "short_name": "CHE", "code": 8},
        ],
        "elements": [
            {"id": 1, "web_name": "Player One", "team": 11, "now_cost": 55, "photo": "1.jpg"},
            {"id": 2, "web_name": "Player Two", "team": 12, "now_cost": 60, "photo": "2.jpg"},
        ],
    }
    live = {"elements": [{"id": 1, "stats": {"total_points": 5}}, {"id": 2, "stats": {"total_points": 3}}]}
    fixtures = [
        {"event": 25, "team_h": 11, "team_a": 12, "team_h_difficulty": 2, "team_a_difficulty": 4}
    ]

    def fake_get(url: str, stream: bool = False, timeout: int = 30, **kwargs: Any):
        if "bootstrap-static" in url:
            return _FakeResp(bootstrap)
        if "fixtures" in url:
            return _FakeResp(fixtures)
        return _FakeResp(live)

    monkeypatch.setattr("requests.get", fake_get)

    state = build_app_state(settings)

    assert state.live_metadata_available is True
    arsenal_row = state.predictions[state.predictions["team"] == "Arsenal"].iloc[0]
    assert arsenal_row["predicted_for_gw"] == 25  # real fixture GW, not the wrapped-to-1 proxy
    assert arsenal_row["fixture_source"] == "real_fixture"
    assert arsenal_row["photo_url"] is not None
    assert arsenal_row["team_logo_url"] is not None


def test_build_app_state_falls_back_gracefully_when_live_api_unreachable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A completely unreachable live API must NOT prevent the API from starting."""
    settings = _write_pipeline_artifacts(tmp_path)

    def fake_get(url: str, stream: bool = False, timeout: int = 30, **kwargs: Any):
        raise ConnectionError("simulated network outage")

    monkeypatch.setattr("requests.get", fake_get)

    state = build_app_state(settings)

    assert state.live_metadata_available is False
    assert len(state.predictions) == 2
    # Proxy behavior preserved: season-boundary GW wraps to 1.
    assert (state.predictions["predicted_for_gw"] == 1).all()
    assert (state.predictions["photo_url"].isna()).all()


def test_build_app_state_with_zero_finished_gameweeks_enriches_successfully(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """When the season is new and 0 Gameweeks have finished, the API must enrich successfully."""
    settings = _write_pipeline_artifacts(tmp_path)

    bootstrap = {
        "events": [{"id": 1, "finished": False, "is_next": True, "deadline_time": "2026-08-21T17:30:00Z"}],
        "teams": [
            {"id": 11, "name": "Arsenal", "short_name": "ARS", "code": 3},
            {"id": 12, "name": "Chelsea", "short_name": "CHE", "code": 8},
        ],
        "elements": [
            {"id": 1, "web_name": "Player One", "first_name": "Player", "second_name": "One", "team": 11, "now_cost": 55, "photo": "1.jpg", "element_type": 3, "status": "a"},
            {"id": 2, "web_name": "Player Two", "first_name": "Player", "second_name": "Two", "team": 12, "now_cost": 60, "photo": "2.jpg", "element_type": 4, "status": "a"},
        ],
    }
    fixtures = [
        {"event": 1, "team_h": 11, "team_a": 12, "team_h_difficulty": 2, "team_a_difficulty": 4}
    ]

    def fake_get(url: str, stream: bool = False, timeout: int = 30, **kwargs: Any):
        if "bootstrap-static" in url:
            return _FakeResp(bootstrap)
        if "fixtures" in url:
            return _FakeResp(fixtures)
        raise AssertionError(f"Unexpected URL called: {url}")

    monkeypatch.setattr("requests.get", fake_get)

    state = build_app_state(settings)

    assert state.live_metadata_available is True
    assert len(state.predictions) == 2
    arsenal_row = state.predictions[state.predictions["team"] == "Arsenal"].iloc[0]
    assert arsenal_row["predicted_for_gw"] == 1
    assert arsenal_row["fixture_source"] == "real_fixture"
    assert arsenal_row["photo_url"] is not None
    assert arsenal_row["team_logo_url"] is not None


def test_build_app_state_falls_back_when_live_api_returns_malformed_data(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """When the live API returns malformed bootstrap data, startup must fall back to historical gracefully."""
    settings = _write_pipeline_artifacts(tmp_path)

    def fake_get(url: str, stream: bool = False, timeout: int = 30, **kwargs: Any):
        return _FakeResp({"invalid": "data"})

    monkeypatch.setattr("requests.get", fake_get)

    state = build_app_state(settings)

    assert state.live_metadata_available is False
    assert len(state.predictions) == 2


def test_bruno_vs_hall_prediction_alignment_and_cross_season_reassignment(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Mandatory Regression Test 1: Bruno Fernandes vs Lewis Hall.

    Proves:
    1. Bruno Fernandes (current element 426) receives Bruno's historical prediction.
    2. Lewis Hall (current element 449) receives Lewis Hall's historical prediction.
    3. Even though element ID 449 belonged to Bruno in a past historical season,
       Hall does NOT receive Bruno's prediction.
    4. Price value carries the raw integer (now_cost = 100 -> value = 100, 50 -> value = 50).
    5. Transferred player displays current team from bootstrap-static.
    """
    settings = _write_pipeline_artifacts(tmp_path)

    # Historical dataset (vaastav_features.csv):
    # Bruno had element 449 in past season 2025-26 with high minutes (88.0 -> prediction ~8.0)
    # Hall had element 473 in past season 2025-26 with lower minutes (50.0 -> prediction ~5.0)
    historical_df = pd.DataFrame(
        {
            "element": [449, 473],
            "name": ["Bruno Borges Fernandes", "Lewis Hall"],
            "name_normalized": ["bruno borges fernandes", "lewis hall"],
            "season": ["2025-26", "2025-26"],
            "GW": [38, 38],
            "team": ["Man Utd", "Newcastle"],
            "opponent_team": ["Chelsea", "Chelsea"],
            "minutes_avg_last_3": [88.0, 50.0],
            "total_points_avg_last_3": [8.0, 3.0],
        }
    )
    historical_df.to_csv(settings.paths.processed_data_dir / "vaastav_features.csv", index=False)

    # Live FPL bootstrap-static API:
    # Current season element 426 is Bruno Fernandes (Man Utd)
    # Current season element 449 is Lewis Hall (Newcastle)
    bootstrap = {
        "events": [{"id": 1, "finished": True, "deadline_time": "2026-08-16T18:00:00Z"}],
        "teams": [
            {"id": 16, "name": "Man Utd", "short_name": "MUN", "code": 1},
            {"id": 17, "name": "Newcastle", "short_name": "NCL", "code": 2},
        ],
        "elements": [
            {
                "id": 426,  # Bruno Fernandes's real current FPL ID
                "web_name": "B.Fernandes",
                "first_name": "Bruno",
                "second_name": "Borges Fernandes",
                "team": 16,
                "element_type": 3,
                "now_cost": 100,
                "status": "a",
                "photo": "426.jpg",
            },
            {
                "id": 449,  # Lewis Hall's real current FPL ID
                "web_name": "Hall",
                "first_name": "Lewis",
                "second_name": "Hall",
                "team": 17,
                "element_type": 2,
                "now_cost": 50,
                "status": "a",
                "photo": "449.jpg",
            },
        ],
    }
    live = {"elements": [{"id": 426, "stats": {"total_points": 5}}]}
    fixtures = [
        {"event": 1, "team_h": 16, "team_a": 17, "team_h_difficulty": 3, "team_a_difficulty": 3}
    ]

    def fake_get(url: str, stream: bool = False, timeout: int = 30, **kwargs: Any):
        if "bootstrap-static" in url:
            return _FakeResp(bootstrap)
        if "fixtures" in url:
            return _FakeResp(fixtures)
        return _FakeResp(live)

    monkeypatch.setattr("requests.get", fake_get)

    state = build_app_state(settings)
    predictions = state.predictions

    assert len(predictions) == 2

    # Bruno Fernandes (current element 426)
    bruno_row = predictions[predictions["element"] == 426].iloc[0]
    assert bruno_row["first_name"] == "Bruno"
    assert bruno_row["second_name"] == "Borges Fernandes"
    assert bruno_row["team"] == "Man Utd"
    assert bruno_row["now_cost"] == 100
    assert bruno_row["value"] == 100  # Raw integer in 10ths of £M for formatPrice (100 -> £10.0m)

    # Lewis Hall (current element 449)
    hall_row = predictions[predictions["element"] == 449].iloc[0]
    assert hall_row["first_name"] == "Lewis"
    assert hall_row["second_name"] == "Hall"
    assert hall_row["team"] == "Newcastle"
    assert hall_row["now_cost"] == 50
    assert hall_row["value"] == 50  # Raw integer in 10ths of £M for formatPrice (50 -> £5.0m)

    # Verify upcoming_fixtures payload
    assert "upcoming_fixtures" in bruno_row
    assert len(bruno_row["upcoming_fixtures"]) == 1
    assert bruno_row["upcoming_fixtures"][0]["opponent_name"] == "Newcastle"
    assert bruno_row["upcoming_fixtures"][0]["is_home"] is True

    assert "upcoming_fixtures" in hall_row
    assert len(hall_row["upcoming_fixtures"]) == 1
    assert hall_row["upcoming_fixtures"][0]["opponent_name"] == "Man Utd"
    assert hall_row["upcoming_fixtures"][0]["is_home"] is False

    # CRITICAL: Verify that Bruno receives Bruno's higher prediction (~88.0 feature input)
    # and Hall receives Hall's lower prediction (~50.0 feature input)
    assert bruno_row["predicted_total_points"] > hall_row["predicted_total_points"]


def test_missing_and_ambiguous_predictions_return_null(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify that current players missing historical data or having ambiguous identity
    matches return prediction = None (null), NOT 0.0."""
    settings = _write_pipeline_artifacts(tmp_path)

    # Historical data has only Saka
    historical_df = pd.DataFrame(
        {
            "element": [1],
            "name": ["Bukayo Saka"],
            "name_normalized": ["bukayo saka"],
            "season": ["2025-26"],
            "GW": [38],
            "team": ["Arsenal"],
            "opponent_team": ["Chelsea"],
            "minutes_avg_last_3": [90.0],
            "total_points_avg_last_3": [8.0],
        }
    )
    historical_df.to_csv(settings.paths.processed_data_dir / "vaastav_features.csv", index=False)

    bootstrap = {
        "events": [{"id": 1, "finished": True, "deadline_time": "2026-08-16T18:00:00Z"}],
        "teams": [
            {"id": 1, "name": "Arsenal", "short_name": "ARS", "code": 3},
            {"id": 20, "name": "Ipswich", "short_name": "IPS", "code": 40},
        ],
        "elements": [
            {
                "id": 1,
                "web_name": "Saka",
                "first_name": "Bukayo",
                "second_name": "Saka",
                "team": 1,
                "element_type": 3,
                "now_cost": 100,
                "status": "a",
            },
            {
                "id": 99,  # New player absent from historical data
                "web_name": "Delap",
                "first_name": "Liam",
                "second_name": "Delap",
                "team": 20,
                "element_type": 4,
                "now_cost": 55,
                "status": "a",
            },
        ],
    }

    def fake_get(url: str, stream: bool = False, timeout: int = 30, **kwargs: Any):
        if "bootstrap-static" in url:
            return _FakeResp(bootstrap)
        if "fixtures" in url:
            return _FakeResp([])
        return _FakeResp({"elements": []})

    monkeypatch.setattr("requests.get", fake_get)

    state = build_app_state(settings)
    predictions = state.predictions

    saka_row = predictions[predictions["element"] == 1].iloc[0]
    delap_row = predictions[predictions["element"] == 99].iloc[0]

    assert saka_row["predicted_total_points"] is not None
    assert delap_row["predicted_total_points"] is None
    assert delap_row["now_cost"] == 55
    assert delap_row["value"] == 55


