"""Unit tests for src.automation.merge_live_data.append_live_gameweek."""

from __future__ import annotations

import pandas as pd

from src.automation.merge_live_data import append_live_gameweek


def test_append_live_gameweek_adds_new_rows() -> None:
    """New live rows with no historical duplicate must simply be appended."""
    historical = pd.DataFrame({"season": ["2022-23"], "element": [1], "GW": [1], "total_points": [5]})
    live = pd.DataFrame({"season": ["2022-23"], "element": [1], "GW": [2], "total_points": [7]})

    result = append_live_gameweek(historical, live, duplicate_key_columns=("season", "element", "GW"))

    assert len(result) == 2
    assert set(result["GW"]) == {1, 2}


def test_append_live_gameweek_live_row_overrides_historical_duplicate() -> None:
    """A live row sharing a key with a historical row must replace it."""
    historical = pd.DataFrame({"season": ["2022-23"], "element": [1], "GW": [1], "total_points": [5]})
    live = pd.DataFrame({"season": ["2022-23"], "element": [1], "GW": [1], "total_points": [9]})

    result = append_live_gameweek(historical, live, duplicate_key_columns=("season", "element", "GW"))

    assert len(result) == 1
    assert result.iloc[0]["total_points"] == 9


def test_append_live_gameweek_handles_mismatched_columns_gracefully() -> None:
    """Columns unique to either frame must survive as NaN in the other's rows."""
    historical = pd.DataFrame(
        {"season": ["2022-23"], "element": [1], "GW": [1], "ict_index": [5.5]}
    )
    live = pd.DataFrame({"season": ["2022-23"], "element": [2], "GW": [1], "total_points": [3]})

    result = append_live_gameweek(historical, live, duplicate_key_columns=("season", "element", "GW"))

    assert len(result) == 2
    assert "ict_index" in result.columns and "total_points" in result.columns
    live_row = result[result["element"] == 2].iloc[0]
    assert pd.isna(live_row["ict_index"])


def test_append_live_gameweek_returns_historical_unchanged_when_live_empty() -> None:
    """An empty live frame must leave the historical data untouched."""
    historical = pd.DataFrame({"season": ["2022-23"], "element": [1], "GW": [1], "total_points": [5]})
    live = pd.DataFrame(columns=["season", "element", "GW", "total_points"])

    result = append_live_gameweek(historical, live, duplicate_key_columns=("season", "element", "GW"))

    assert len(result) == 1
    assert result.equals(historical)
