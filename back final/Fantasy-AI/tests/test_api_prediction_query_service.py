"""Unit tests for src.api.services.prediction_query_service.

These tests exercise PredictionQueryService directly, with no
FastAPI/HTTP layer involved.
"""

from __future__ import annotations

import pandas as pd
import pytest

from src.api.services.prediction_query_service import (
    PredictionQueryService,
    _round_prediction,
    _row_to_dict,
)
from src.core.exceptions import PlayerNotFoundError


def _sample_predictions() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "element": [1, 2, 3, 4],
            "name": ["Salah", "Haaland", "Kane", "BenchWarmer"],
            "minutes_avg_last_3": [88.0, 90.0, 85.0, 12.0],
            "predicted_total_points": [6.5, 9.2, 5.1, 8.0],
        }
    )


def test_get_all_is_sorted_descending() -> None:
    """get_all must return predictions sorted highest to lowest."""
    service = PredictionQueryService(
        _sample_predictions(), player_id_column="element", prediction_column="predicted_total_points"
    )
    result = service.get_all()
    assert result["name"].tolist() == ["Haaland", "BenchWarmer", "Salah", "Kane"]


def test_get_by_player_returns_matching_row() -> None:
    """get_by_player must return the row for the requested player."""
    service = PredictionQueryService(
        _sample_predictions(), player_id_column="element", prediction_column="predicted_total_points"
    )
    result = service.get_by_player("2")
    assert result["name"] == "Haaland"


def test_get_by_player_raises_for_unknown_id() -> None:
    """get_by_player must raise PlayerNotFoundError for an unmatched identifier."""
    service = PredictionQueryService(
        _sample_predictions(), player_id_column="element", prediction_column="predicted_total_points"
    )
    with pytest.raises(PlayerNotFoundError):
        service.get_by_player("999")


def test_get_top_respects_limit_and_order() -> None:
    """get_top must return exactly `limit` players, highest predicted first."""
    service = PredictionQueryService(
        _sample_predictions(), player_id_column="element", prediction_column="predicted_total_points"
    )
    top2 = service.get_top(2)
    assert [p["name"] for p in top2] == ["Haaland", "BenchWarmer"]


def test_get_captain_filters_by_minutes_threshold() -> None:
    """get_captain must exclude low-minutes players even if they'd score higher."""
    service = PredictionQueryService(
        _sample_predictions(), player_id_column="element", prediction_column="predicted_total_points"
    )
    # BenchWarmer has the 2nd-highest prediction but very low minutes; must be excluded.
    result = service.get_captain(minutes_columns=("minutes_avg_last_3",), min_minutes_avg=60.0)
    assert result.player["name"] == "Haaland"
    assert result.pool_size == 3  # Salah, Haaland, Kane meet the threshold


def test_get_captain_falls_back_when_no_one_meets_threshold() -> None:
    """get_captain must fall back to the full pool if nobody clears the threshold."""
    service = PredictionQueryService(
        _sample_predictions(), player_id_column="element", prediction_column="predicted_total_points"
    )
    result = service.get_captain(minutes_columns=("minutes_avg_last_3",), min_minutes_avg=999.0)
    assert result.player["name"] == "Haaland"  # still the overall best
    assert "fallback" in result.reasoning.lower() or "falls back" in result.reasoning.lower()


def test_get_captain_falls_back_when_no_minutes_column_available() -> None:
    """get_captain must consider all players if no minutes column exists at all."""
    df = _sample_predictions().drop(columns=["minutes_avg_last_3"])
    service = PredictionQueryService(
        df, player_id_column="element", prediction_column="predicted_total_points"
    )
    result = service.get_captain(minutes_columns=("minutes_avg_last_3",), min_minutes_avg=60.0)
    assert result.player["name"] == "Haaland"
    assert result.pool_size == 4


def test_get_captain_raises_on_empty_predictions() -> None:
    """get_captain must raise PlayerNotFoundError when there are no predictions at all."""
    empty = _sample_predictions().iloc[0:0]
    service = PredictionQueryService(
        empty, player_id_column="element", prediction_column="predicted_total_points"
    )
    with pytest.raises(PlayerNotFoundError):
        service.get_captain(minutes_columns=("minutes_avg_last_3",), min_minutes_avg=60.0)


def test_round_prediction_standard_nearest_integer() -> None:
    """Verify standard nearest-integer rounding rules (half up) on required examples."""
    # Positive examples
    assert _round_prediction(7.384) == 7
    assert isinstance(_round_prediction(7.384), int)

    assert _round_prediction(5.921) == 6
    assert isinstance(_round_prediction(5.921), int)

    assert _round_prediction(10.147) == 10
    assert isinstance(_round_prediction(10.147), int)

    assert _round_prediction(10.5) == 11
    assert isinstance(_round_prediction(10.5), int)

    # Negative examples
    assert _round_prediction(-10.5) == -11
    assert isinstance(_round_prediction(-10.5), int)

    assert _round_prediction(-1.5) == -2
    assert isinstance(_round_prediction(-1.5), int)

    assert _round_prediction(-0.4) == 0
    assert isinstance(_round_prediction(-0.4), int)

    assert _round_prediction(-0.6) == -1
    assert isinstance(_round_prediction(-0.6), int)

    # Missing / None
    assert _round_prediction(None) is None


def test_dict_serialization_returns_integer_predictions_and_leaves_actual_stats() -> None:
    """_row_to_dict must return integer predicted points while leaving actual points & stats intact."""
    row = pd.Series(
        {
            "element": 1,
            "name": "Salah",
            "predicted_total_points": 7.384,
            "predicted_for_gw": 11,
            "total_points": 15,
            "minutes_avg_last_3": 88.5,
            "model_test_rmse": 1.78,
            "prediction_uncertainty_std": 0.45,
        }
    )
    result = _row_to_dict(row)

    # Prediction target is rounded to integer
    assert result["predicted_total_points"] == 7
    assert isinstance(result["predicted_total_points"], int)

    # Gameweek number remains integer
    assert result["predicted_for_gw"] == 11
    assert isinstance(result["predicted_for_gw"], int)

    # Actual FPL points remain untouched
    assert result["total_points"] == 15

    # Features and uncertainty metrics remain untouched floats
    assert result["minutes_avg_last_3"] == 88.5
    assert result["model_test_rmse"] == 1.78
    assert result["prediction_uncertainty_std"] == 0.45


def test_query_service_returns_integers_and_preserves_internal_float_predictions() -> None:
    """PredictionQueryService must return integers in dicts while keeping internal DataFrame floats intact."""
    df = pd.DataFrame(
        {
            "element": [10, 20, 30],
            "name": ["Alpha", "Beta", "Gamma"],
            "minutes_avg_last_3": [90.0, 90.0, 90.0],
            "predicted_total_points": [7.384, 5.921, 10.5],
        }
    )
    service = PredictionQueryService(
        df, player_id_column="element", prediction_column="predicted_total_points"
    )

    # 1. Internal DataFrame in get_all() retains floating point precision
    internal_df = service.get_all()
    assert isinstance(internal_df.iloc[0]["predicted_total_points"], (float, pd.Series, pd.DataFrame, float))
    assert internal_df.iloc[0]["predicted_total_points"] == pytest.approx(10.5)

    # 2. get_by_player returns integer prediction
    alpha = service.get_by_player("10")
    assert alpha["predicted_total_points"] == 7
    assert isinstance(alpha["predicted_total_points"], int)

    # 3. get_top returns integer predictions
    top = service.get_top(3)
    assert [p["name"] for p in top] == ["Gamma", "Alpha", "Beta"]
    assert top[0]["predicted_total_points"] == 11  # 10.5 -> 11
    assert top[1]["predicted_total_points"] == 7   # 7.384 -> 7
    assert top[2]["predicted_total_points"] == 6   # 5.921 -> 6
    assert all(isinstance(p["predicted_total_points"], int) for p in top)

    # 4. get_captain returns integer prediction
    captain = service.get_captain(minutes_columns=("minutes_avg_last_3",), min_minutes_avg=60.0)
    assert captain.player["name"] == "Gamma"
    assert captain.player["predicted_total_points"] == 11
    assert isinstance(captain.player["predicted_total_points"], int)


def test_ranking_preserves_raw_float_order_when_rounded_values_are_equal() -> None:
    """Players whose predictions round to the same integer must still be ranked by raw floats."""
    df = pd.DataFrame(
        {
            "element": [1, 2],
            "name": ["Player74", "Player71"],
            "minutes_avg_last_3": [90.0, 90.0],
            "predicted_total_points": [7.4, 7.1],  # Both round to 7
        }
    )
    service = PredictionQueryService(
        df, player_id_column="element", prediction_column="predicted_total_points"
    )

    top = service.get_top(2)
    # Player74 (7.4) must rank above Player71 (7.1)
    assert top[0]["name"] == "Player74"
    assert top[0]["predicted_total_points"] == 7
    assert top[1]["name"] == "Player71"
    assert top[1]["predicted_total_points"] == 7

