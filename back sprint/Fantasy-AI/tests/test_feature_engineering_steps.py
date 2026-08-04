"""Unit tests for individual feature engineering steps."""

from __future__ import annotations

import pandas as pd
import pytest

from src.feature_engineering.models import RollingFeatureSpec
from src.feature_engineering.steps.form_index import FormIndexStep
from src.feature_engineering.steps.home_away import HomeAwayFlagStep
from src.feature_engineering.steps.price_trend import PriceTrendStep
from src.feature_engineering.steps.rest_days import RestDaysStep
from src.feature_engineering.steps.rolling_stats import RollingAverageStep
from src.feature_engineering.steps.team_strength import TeamStrengthStep


# --- RollingAverageStep --------------------------------------------------------


def test_rolling_average_excludes_current_row_no_leakage() -> None:
    """The rolling average for a row must never include that row's own value."""
    df = pd.DataFrame(
        {
            "element": [1, 1, 1],
            "season": ["2022-23"] * 3,
            "GW": [1, 2, 3],
            "total_points": [10, 20, 30],
        }
    )
    spec = RollingFeatureSpec(
        output_name="total_points", source_candidates=("total_points",), windows=(3,)
    )
    step = RollingAverageStep(
        player_id_columns=("element",), chronological_columns=("season", "GW"), specs=(spec,)
    )
    result, _ = step.apply(df)

    # Row 1 (GW1): no prior matches -> NaN.
    assert pd.isna(result.iloc[0]["total_points_avg_last_3"])
    # Row 2 (GW2): only prior match is GW1 (10 pts) -> average is 10, not (10+20)/2.
    assert result.iloc[1]["total_points_avg_last_3"] == 10.0
    # Row 3 (GW3): prior matches are GW1, GW2 (10, 20) -> average is 15.
    assert result.iloc[2]["total_points_avg_last_3"] == 15.0


def test_rolling_average_groups_independently_per_player() -> None:
    """Rolling averages for one player must not leak into another player's rows."""
    df = pd.DataFrame(
        {
            "element": [1, 1, 2, 2],
            "season": ["2022-23"] * 4,
            "GW": [1, 2, 1, 2],
            "total_points": [10, 20, 100, 200],
        }
    )
    spec = RollingFeatureSpec(
        output_name="total_points", source_candidates=("total_points",), windows=(3,)
    )
    step = RollingAverageStep(
        player_id_columns=("element",), chronological_columns=("season", "GW"), specs=(spec,)
    )
    result, _ = step.apply(df)

    player_2_gw2 = result[(result["element"] == 2) & (result["GW"] == 2)].iloc[0]
    assert player_2_gw2["total_points_avg_last_3"] == 100.0


def test_rolling_average_preserves_original_row_order() -> None:
    """The output row order must match the input row order exactly."""
    df = pd.DataFrame(
        {
            "element": [2, 1, 2, 1],
            "season": ["2022-23"] * 4,
            "GW": [2, 2, 1, 1],
            "total_points": [200, 20, 100, 10],
        }
    )
    spec = RollingFeatureSpec(
        output_name="total_points", source_candidates=("total_points",), windows=(3,)
    )
    step = RollingAverageStep(
        player_id_columns=("element",), chronological_columns=("season", "GW"), specs=(spec,)
    )
    result, _ = step.apply(df)
    assert result["element"].tolist() == [2, 1, 2, 1]
    assert result["total_points"].tolist() == [200, 20, 100, 10]


def test_rolling_average_falls_back_to_alternate_source_candidate() -> None:
    """A spec must use the first available candidate column (e.g. xG over expected_goals)."""
    df = pd.DataFrame(
        {"element": [1, 1], "season": ["2022-23"] * 2, "GW": [1, 2], "xG": [0.5, 0.8]}
    )
    spec = RollingFeatureSpec(
        output_name="xG", source_candidates=("expected_goals", "xG"), windows=(3,)
    )
    step = RollingAverageStep(
        player_id_columns=("element",), chronological_columns=("season", "GW"), specs=(spec,)
    )
    result, _ = step.apply(df)
    assert result.iloc[1]["xG_avg_last_3"] == 0.5


def test_rolling_average_skips_gracefully_when_source_missing() -> None:
    """A spec whose source columns are all absent must produce a NaN column, not an error."""
    df = pd.DataFrame({"element": [1], "season": ["2022-23"], "GW": [1]})
    spec = RollingFeatureSpec(
        output_name="xG", source_candidates=("expected_goals", "xG"), windows=(3,)
    )
    step = RollingAverageStep(
        player_id_columns=("element",), chronological_columns=("season", "GW"), specs=(spec,)
    )
    result, summary = step.apply(df)
    assert pd.isna(result.iloc[0]["xG_avg_last_3"])
    assert "xG" in summary.description


# --- HomeAwayFlagStep -----------------------------------------------------------


def test_home_away_flag_converts_boolean_to_int() -> None:
    """was_home True/False must become is_home 1/0."""
    df = pd.DataFrame({"was_home": [True, False]})
    step = HomeAwayFlagStep(source_column="was_home")
    result, _ = step.apply(df)
    assert result["is_home"].tolist() == [1, 0]


def test_home_away_flag_skips_gracefully_when_column_missing() -> None:
    """A missing source column must yield NaN output, not an error."""
    df = pd.DataFrame({"other": [1, 2]})
    step = HomeAwayFlagStep(source_column="was_home")
    result, _ = step.apply(df)
    assert result["is_home"].isna().all()


# --- RestDaysStep ----------------------------------------------------------------


def test_rest_days_computes_gap_between_matches() -> None:
    """rest_days must equal the day gap between consecutive matches for a player."""
    df = pd.DataFrame(
        {
            "element": [1, 1],
            "kickoff_time": ["2022-08-06T14:00:00Z", "2022-08-13T14:00:00Z"],
        }
    )
    step = RestDaysStep(
        player_id_columns=("element",), kickoff_time_column="kickoff_time", default_rest_days=7
    )
    result, _ = step.apply(df)
    assert result.iloc[1]["rest_days"] == 7


def test_rest_days_uses_default_for_first_match() -> None:
    """A player's first match must use the configured default rest value."""
    df = pd.DataFrame({"element": [1], "kickoff_time": ["2022-08-06T14:00:00Z"]})
    step = RestDaysStep(
        player_id_columns=("element",), kickoff_time_column="kickoff_time", default_rest_days=9
    )
    result, _ = step.apply(df)
    assert result.iloc[0]["rest_days"] == 9


# --- PriceTrendStep --------------------------------------------------------------


def test_price_trend_computes_change_over_window() -> None:
    """price_trend_last_1 must equal the price change from the previous match."""
    df = pd.DataFrame(
        {"element": [1, 1, 1], "season": ["2022-23"] * 3, "GW": [1, 2, 3], "value": [50, 51, 49]}
    )
    step = PriceTrendStep(
        player_id_columns=("element",),
        chronological_columns=("season", "GW"),
        value_column="value",
        windows=(1,),
    )
    result, _ = step.apply(df)
    assert result.iloc[1]["price_trend_last_1"] == 1  # 51 - 50
    assert result.iloc[2]["price_trend_last_1"] == -2  # 49 - 51


def test_price_trend_fills_zero_for_insufficient_history() -> None:
    """A player's first match has no prior price and must default to 0."""
    df = pd.DataFrame({"element": [1], "season": ["2022-23"], "GW": [1], "value": [50]})
    step = PriceTrendStep(
        player_id_columns=("element",),
        chronological_columns=("season", "GW"),
        value_column="value",
        windows=(1,),
    )
    result, _ = step.apply(df)
    assert result.iloc[0]["price_trend_last_1"] == 0


# --- TeamStrengthStep ------------------------------------------------------------


def test_team_strength_excludes_current_gameweek() -> None:
    """Team strength for a Gameweek must be based only on prior Gameweeks."""
    df = pd.DataFrame(
        {
            "team": ["A", "A", "A", "A"],
            "season": ["2022-23"] * 4,
            "GW": [1, 1, 2, 2],
            "total_points": [10, 20, 5, 5],
        }
    )
    step = TeamStrengthStep(
        team_column="team",
        opponent_column="opponent_team",
        strength_source_column="total_points",
        chronological_columns=("season", "GW"),
    )
    result, _ = step.apply(df)
    # GW1 rows: no prior GW -> NaN.
    assert result[result["GW"] == 1]["team_strength"].isna().all()
    # GW2 rows: prior GW1 average was (10+20)/2 = 15.
    assert (result[result["GW"] == 2]["team_strength"] == 15.0).all()


def test_team_strength_skips_opponent_when_domains_incompatible() -> None:
    """opponent_strength must be skipped (NaN) when team/opponent use incompatible ID schemes."""
    df = pd.DataFrame(
        {
            "team": ["Arsenal", "Chelsea"],
            "opponent_team": [14, 6],  # numeric IDs, incompatible with team names
            "season": ["2022-23"] * 2,
            "GW": [1, 1],
            "total_points": [10, 5],
        }
    )
    step = TeamStrengthStep(
        team_column="team",
        opponent_column="opponent_team",
        strength_source_column="total_points",
        chronological_columns=("season", "GW"),
    )
    result, summary = step.apply(df)
    assert result["opponent_strength"].isna().all()
    assert "Skipped" in summary.description


# --- FormIndexStep -----------------------------------------------------------------


def test_form_index_computes_weighted_average() -> None:
    """form_index must be the weighted sum of its configured component columns."""
    df = pd.DataFrame(
        {
            "total_points_avg_last_3": [10.0],
            "total_points_avg_last_5": [8.0],
            "total_points_avg_last_10": [6.0],
        }
    )
    step = FormIndexStep(
        component_columns=(
            "total_points_avg_last_3",
            "total_points_avg_last_5",
            "total_points_avg_last_10",
        ),
        weights=(0.5, 0.3, 0.2),
    )
    result, _ = step.apply(df)
    expected = 10.0 * 0.5 + 8.0 * 0.3 + 6.0 * 0.2
    assert result.iloc[0]["form_index"] == pytest.approx(expected)


def test_form_index_renormalizes_when_a_component_is_missing() -> None:
    """Missing components must be excluded and remaining weights renormalized."""
    df = pd.DataFrame({"total_points_avg_last_3": [10.0], "total_points_avg_last_5": [8.0]})
    step = FormIndexStep(
        component_columns=(
            "total_points_avg_last_3",
            "total_points_avg_last_5",
            "total_points_avg_last_10",
        ),
        weights=(0.5, 0.3, 0.2),
    )
    result, summary = step.apply(df)
    expected = (10.0 * 0.5 + 8.0 * 0.3) / (0.5 + 0.3)
    assert result.iloc[0]["form_index"] == pytest.approx(expected)
    assert "missing" in summary.description


def test_form_index_raises_on_mismatched_lengths() -> None:
    """Constructing FormIndexStep with mismatched columns/weights must raise ValueError."""
    with pytest.raises(ValueError):
        FormIndexStep(component_columns=("a", "b"), weights=(1.0,))
