"""Unit tests for src.feature_engineering.steps.team_form_trend."""

from __future__ import annotations

import pandas as pd

from src.feature_engineering.steps.team_form_trend import TeamFormTrendStep


def test_team_form_trend_excludes_current_gameweek_no_leakage() -> None:
    """Like TeamStrengthStep, this must only use strictly prior Gameweeks."""
    df = pd.DataFrame(
        {
            "team": ["A", "A", "A", "A"],
            "season": ["2022-23"] * 4,
            "GW": [1, 1, 2, 2],
            "total_points": [10, 20, 5, 5],
        }
    )
    step = TeamFormTrendStep(
        team_column="team",
        strength_source_column="total_points",
        chronological_columns=("season", "GW"),
        short_window=1,
        long_window=2,
    )
    result, _ = step.apply(df)
    # GW1: no prior data -> NaN.
    assert result[result["GW"] == 1]["team_form_trend"].isna().all()
    # GW2: exactly one prior GW (GW1, avg 15) for both short and long window
    # -> trend should be 0 (short == long with only one data point).
    assert (result[result["GW"] == 2]["team_form_trend"] == 0.0).all()


def test_team_form_trend_positive_when_recent_form_improves() -> None:
    """A team whose recent Gameweeks outscore its longer baseline gets a positive trend."""
    rows = []
    # Weak start (scores of 2), then a hot streak (scores of 10) for the last 2 GWs.
    scores = [2, 2, 2, 2, 2, 2, 10, 10, 10]
    for gw, score in enumerate(scores, start=1):
        rows.append({"team": "A", "season": "2022-23", "GW": gw, "total_points": score})
    df = pd.DataFrame(rows)

    step = TeamFormTrendStep(
        team_column="team",
        strength_source_column="total_points",
        chronological_columns=("season", "GW"),
        short_window=2,
        long_window=8,
    )
    result, _ = step.apply(df)
    last_row = result.iloc[-1]
    assert last_row["team_form_trend"] > 0


def test_team_form_trend_missing_columns_returns_nan_gracefully() -> None:
    """A missing prerequisite column must not raise — output is NaN with a clear summary."""
    df = pd.DataFrame({"season": ["2022-23"], "GW": [1]})
    step = TeamFormTrendStep(
        team_column="team",
        strength_source_column="total_points",
        chronological_columns=("season", "GW"),
        short_window=3,
        long_window=10,
    )
    result, summary = step.apply(df)
    assert result["team_form_trend"].isna().all()
    assert "Missing prerequisite" in summary.description


def test_team_form_trend_preserves_row_count_and_order() -> None:
    """This step must never add/remove/reorder rows."""
    df = pd.DataFrame(
        {
            "team": ["B", "A", "B", "A"],
            "season": ["2022-23"] * 4,
            "GW": [2, 2, 1, 1],
            "total_points": [5, 6, 7, 8],
        }
    )
    step = TeamFormTrendStep(
        team_column="team",
        strength_source_column="total_points",
        chronological_columns=("season", "GW"),
        short_window=3,
        long_window=10,
    )
    result, _ = step.apply(df)
    assert result["team"].tolist() == ["B", "A", "B", "A"]
    assert len(result) == 4
