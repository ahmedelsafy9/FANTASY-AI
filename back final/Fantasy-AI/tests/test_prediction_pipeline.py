"""Unit tests for next-Gameweek row building, PredictionService, and export."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest
from sklearn.linear_model import LinearRegression

from src.core.exceptions import PredictionError
from src.prediction.export import export_predictions
from src.prediction.loader import LoadedModel
from src.prediction.next_gameweek import build_next_gameweek_rows
from src.prediction.predictor import PredictionService


# --- build_next_gameweek_rows --------------------------------------------------


def test_build_next_gameweek_rows_selects_latest_row_per_player() -> None:
    """Only each player's most recent (season, GW) row must be selected."""
    df = pd.DataFrame(
        {
            "element": [1, 1, 2, 2],
            "season": ["2022-23"] * 4,
            "GW": [1, 2, 1, 2],
            "minutes": [90, 45, 90, 90],
        }
    )
    result = build_next_gameweek_rows(
        df,
        player_id_columns=("element",),
        chronological_columns=("season", "GW"),
        max_valid_gameweek=38,
    )
    assert len(result) == 2
    assert set(result["GW"]) == {2}


def test_build_next_gameweek_rows_increments_gw() -> None:
    """predicted_for_gw must be the player's latest GW plus one."""
    df = pd.DataFrame({"element": [1], "season": ["2022-23"], "GW": [5], "minutes": [90]})
    result = build_next_gameweek_rows(
        df,
        player_id_columns=("element",),
        chronological_columns=("season", "GW"),
        max_valid_gameweek=38,
    )
    assert result.iloc[0]["predicted_for_gw"] == 6


def test_build_next_gameweek_rows_wraps_at_season_end() -> None:
    """A player at the final Gameweek must roll over to GW 1 for predicted_for_gw."""
    df = pd.DataFrame({"element": [1], "season": ["2022-23"], "GW": [38], "minutes": [90]})
    result = build_next_gameweek_rows(
        df,
        player_id_columns=("element",),
        chronological_columns=("season", "GW"),
        max_valid_gameweek=38,
    )
    assert result.iloc[0]["predicted_for_gw"] == 1


def test_build_next_gameweek_rows_raises_without_player_id_column() -> None:
    """A missing player identifier column must raise PredictionError."""
    df = pd.DataFrame({"season": ["2022-23"], "GW": [1]})
    with pytest.raises(PredictionError):
        build_next_gameweek_rows(
            df,
            player_id_columns=("element", "name"),
            chronological_columns=("season", "GW"),
            max_valid_gameweek=38,
        )


def test_build_next_gameweek_rows_raises_without_chronological_column() -> None:
    """A missing chronological column must raise PredictionError."""
    df = pd.DataFrame({"element": [1], "minutes": [90]})
    with pytest.raises(PredictionError):
        build_next_gameweek_rows(
            df,
            player_id_columns=("element",),
            chronological_columns=("season", "GW"),
            max_valid_gameweek=38,
        )


# --- PredictionService -----------------------------------------------------------


def _build_loaded_model() -> LoadedModel:
    model = LinearRegression()
    model.fit([[0, 0], [1, 1], [2, 2]], [0, 2, 4])  # y = 2*a (b unused but present)
    return LoadedModel(
        model=model,
        model_name="linear_regression",
        feature_columns=["a", "b"],
        target_column="total_points",
        train_medians={"a": 1.0, "b": 1.0},
        metrics={"mae": 0.1, "rmse": 0.2, "r2": 0.99},
    )


def test_predict_adds_prediction_column() -> None:
    """predict() must add a 'predicted_<target>' column to the output."""
    service = PredictionService(_build_loaded_model())
    rows = pd.DataFrame({"a": [3.0], "b": [1.0], "name": ["Salah"]})
    result = service.predict(rows)
    assert "predicted_total_points" in result.columns
    assert result.iloc[0]["name"] == "Salah"


def test_predict_imputes_missing_feature_with_train_median() -> None:
    """A missing feature value must be imputed with its training median before prediction."""
    service = PredictionService(_build_loaded_model())
    rows = pd.DataFrame({"a": [None], "b": [1.0]})
    result = service.predict(rows)
    # a is imputed to median 1.0 -> prediction should equal the a=1.0 case.
    assert result.iloc[0]["predicted_total_points"] == pytest.approx(2.0, abs=0.5)


def test_predict_raises_when_feature_column_entirely_absent() -> None:
    """A feature column missing entirely (not just some NaNs) must raise PredictionError."""
    service = PredictionService(_build_loaded_model())
    rows = pd.DataFrame({"a": [1.0]})  # missing 'b' entirely
    with pytest.raises(PredictionError):
        service.predict(rows)


# --- export_predictions -----------------------------------------------------------


def test_export_predictions_sorts_descending_and_writes_csv(tmp_path: Path) -> None:
    """export_predictions must sort by prediction descending and write a CSV."""
    df = pd.DataFrame(
        {
            "element": [1, 2, 3],
            "name": ["A", "B", "C"],
            "team": ["X", "Y", "Z"],
            "predicted_for_gw": [5, 5, 5],
            "predicted_total_points": [2.0, 9.0, 5.0],
        }
    )
    output_path = tmp_path / "predictions.csv"
    exported = export_predictions(
        df,
        id_columns=("element", "name", "team"),
        prediction_column="predicted_total_points",
        output_path=output_path,
    )

    assert output_path.exists()
    assert exported["name"].tolist() == ["B", "C", "A"]

    reloaded = pd.read_csv(output_path)
    assert reloaded["name"].tolist() == ["B", "C", "A"]


def test_export_predictions_omits_absent_id_columns(tmp_path: Path) -> None:
    """Identifying columns not present in the data must be silently omitted."""
    df = pd.DataFrame({"name": ["A"], "predicted_total_points": [5.0]})
    output_path = tmp_path / "predictions.csv"
    exported = export_predictions(
        df,
        id_columns=("element", "name", "team"),
        prediction_column="predicted_total_points",
        output_path=output_path,
    )
    assert "element" not in exported.columns
    assert "team" not in exported.columns
    assert "name" in exported.columns


# --- Phase 4: uncertainty metrics ---------------------------------------------


def test_predict_adds_model_test_rmse_when_present() -> None:
    """model_test_rmse must be added directly from the model's stored test metrics."""
    from sklearn.linear_model import LinearRegression

    model = LinearRegression().fit([[0, 0], [1, 1], [2, 2]], [0, 2, 4])
    loaded = LoadedModel(
        model=model, model_name="linear_regression", feature_columns=["a", "b"],
        target_column="total_points", train_medians={"a": 1.0, "b": 1.0},
        metrics={"mae": 0.1, "rmse": 1.234, "r2": 0.9},
    )
    result = PredictionService(loaded).predict(pd.DataFrame({"a": [1.0], "b": [1.0]}))
    assert (result["model_test_rmse"] == 1.234).all()


def test_predict_adds_per_row_ensemble_uncertainty_for_random_forest() -> None:
    """A RandomForest model must get a genuine, per-row-varying uncertainty column."""
    from sklearn.ensemble import RandomForestRegressor

    model = RandomForestRegressor(n_estimators=8, random_state=0).fit(
        [[1, 1], [2, 2], [3, 1], [1, 3], [4, 4]], [2, 4, 3, 3, 8]
    )
    loaded = LoadedModel(
        model=model, model_name="random_forest", feature_columns=["a", "b"],
        target_column="total_points", train_medians={"a": 1.0, "b": 1.0},
        metrics={"mae": 0.5, "rmse": 1.7, "r2": 0.4},
    )
    result = PredictionService(loaded).predict(pd.DataFrame({"a": [1.0, 4.0], "b": [1.0, 4.0]}))
    assert "prediction_uncertainty_std" in result.columns
    assert (result["prediction_uncertainty_std"] >= 0).all()


def test_predict_omits_uncertainty_for_non_ensemble_model() -> None:
    """A linear model must NOT get a fabricated per-row uncertainty column."""
    from sklearn.linear_model import LinearRegression

    model = LinearRegression().fit([[0, 0], [1, 1]], [0, 2])
    loaded = LoadedModel(
        model=model, model_name="linear_regression", feature_columns=["a", "b"],
        target_column="total_points", train_medians={"a": 1.0, "b": 1.0},
        metrics={"mae": 0.1, "rmse": 1.0, "r2": 0.9},
    )
    result = PredictionService(loaded).predict(pd.DataFrame({"a": [1.0], "b": [1.0]}))
    assert "prediction_uncertainty_std" not in result.columns
