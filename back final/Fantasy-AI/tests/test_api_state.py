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
