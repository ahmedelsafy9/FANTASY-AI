"""Unit tests for src.api.services.prediction_query_service.

These tests exercise PredictionQueryService directly, with no
FastAPI/HTTP layer involved.
"""

from __future__ import annotations

import pandas as pd
import pytest

from src.api.services.prediction_query_service import PredictionQueryService
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
