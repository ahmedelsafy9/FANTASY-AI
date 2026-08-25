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


# --- Sprint 10: current-season filtering tests --------------------------------


def test_build_next_gw_excludes_historical_players() -> None:
    """Players from older seasons must NOT appear in current predictions."""
    df = pd.DataFrame(
        {
            "element": [1, 2, 3, 3],
            "season": ["2021-22", "2021-22", "2022-23", "2022-23"],
            "GW": [38, 38, 1, 2],
            "minutes": [90, 90, 90, 90],
        }
    )
    result = build_next_gameweek_rows(
        df,
        player_id_columns=("element",),
        chronological_columns=("season", "GW"),
        max_valid_gameweek=38,
    )
    # Only element 3 from 2022-23 should appear; elements 1, 2 are old-season only.
    assert len(result) == 1
    assert result.iloc[0]["element"] == 3
    assert result.iloc[0]["predicted_for_gw"] == 3


def test_build_next_gw_multi_season_no_duplicates() -> None:
    """Multiple historical seasons must not cause duplicate player candidates."""
    df = pd.DataFrame(
        {
            "element": [10, 10, 10, 20, 20],
            "season": ["2020-21", "2021-22", "2022-23", "2021-22", "2022-23"],
            "GW": [38, 38, 5, 38, 10],
            "minutes": [90, 90, 90, 90, 90],
        }
    )
    result = build_next_gameweek_rows(
        df,
        player_id_columns=("element",),
        chronological_columns=("season", "GW"),
        max_valid_gameweek=38,
    )
    # Only 2022-23 rows matter. element 10 at GW5, element 20 at GW10.
    assert len(result) == 2
    assert set(result["element"]) == {10, 20}
    assert set(result["predicted_for_gw"]) == {6, 11}


def test_build_next_gw_old_gw38_players_not_rolled_to_gw1() -> None:
    """GW38 players from old seasons must NOT become fake GW1 predictions
    when a newer season exists."""
    df = pd.DataFrame(
        {
            "element": [1, 2],
            "season": ["2021-22", "2022-23"],
            "GW": [38, 1],
            "minutes": [90, 90],
        }
    )
    result = build_next_gameweek_rows(
        df,
        player_id_columns=("element",),
        chronological_columns=("season", "GW"),
        max_valid_gameweek=38,
    )
    # Element 1 from 2021-22 must be excluded entirely.
    # Element 2 from 2022-23 GW1 -> predicted_for_gw = 2.
    assert len(result) == 1
    assert result.iloc[0]["element"] == 2
    assert result.iloc[0]["predicted_for_gw"] == 2


def test_build_next_gw_uses_element_within_single_season() -> None:
    """Within a single season, 'element' should work as a valid player ID."""
    df = pd.DataFrame(
        {
            "element": [100, 100, 200],
            "season": ["2026-27"] * 3,
            "GW": [1, 2, 1],
            "minutes": [90, 45, 90],
        }
    )
    result = build_next_gameweek_rows(
        df,
        player_id_columns=("element",),
        chronological_columns=("season", "GW"),
        max_valid_gameweek=38,
    )
    assert len(result) == 2
    assert set(result["element"]) == {100, 200}
    # element 100 latest GW is 2 -> predicted 3; element 200 latest GW is 1 -> predicted 2
    result_sorted = result.sort_values("element").reset_index(drop=True)
    assert result_sorted.iloc[0]["predicted_for_gw"] == 3  # element 100
    assert result_sorted.iloc[1]["predicted_for_gw"] == 2  # element 200


def test_build_next_gw_preserves_current_player_count() -> None:
    """The output row count must match the number of unique players in the
    current season, not the total across all seasons."""
    old_players = pd.DataFrame(
        {
            "element": list(range(1, 501)),
            "season": ["2021-22"] * 500,
            "GW": [38] * 500,
            "minutes": [90] * 500,
        }
    )
    current_players = pd.DataFrame(
        {
            "element": list(range(1, 21)),
            "season": ["2022-23"] * 20,
            "GW": [1] * 20,
            "minutes": [90] * 20,
        }
    )
    df = pd.concat([old_players, current_players], ignore_index=True)
    result = build_next_gameweek_rows(
        df,
        player_id_columns=("element",),
        chronological_columns=("season", "GW"),
        max_valid_gameweek=38,
    )
    # Must produce exactly 20 rows (current season), not 500+.
    assert len(result) == 20
    assert (result["predicted_for_gw"] == 2).all()


def test_build_next_gw_single_season_gw38_still_rolls() -> None:
    """When there is only one season and all players are at GW38,
    the rollover to GW1 should still work (backward compat)."""
    df = pd.DataFrame(
        {
            "element": [1, 2],
            "season": ["2022-23", "2022-23"],
            "GW": [38, 38],
            "minutes": [90, 90],
        }
    )
    result = build_next_gameweek_rows(
        df,
        player_id_columns=("element",),
        chronological_columns=("season", "GW"),
        max_valid_gameweek=38,
    )
    assert len(result) == 2
    assert (result["predicted_for_gw"] == 1).all()


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
