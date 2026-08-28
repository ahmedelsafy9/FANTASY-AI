"""Unit tests for individual feature engineering steps."""

from __future__ import annotations

import pandas as pd
import pytest

from src.feature_engineering.models import RollingFeatureSpec
from src.feature_engineering.steps.form_index import FormIndexStep
from src.feature_engineering.steps.home_away import HomeAwayFlagStep
from src.feature_engineering.steps.participation import PlayerParticipationStep
from src.feature_engineering.steps.price_trend import PriceTrendStep
from src.feature_engineering.steps.promoted_teams import PromotedAndHistoricalStep
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


# --- PlayerParticipationStep ----------------------------------------------------


def test_player_participation_excludes_current_row_no_leakage() -> None:
    """Participation metrics must strictly shift by 1 to prevent data leakage."""
    df = pd.DataFrame(
        {
            "element": [1, 1, 1, 1],
            "season": ["2022-23"] * 4,
            "GW": [1, 2, 3, 4],
            "minutes": [90, 0, 45, 90],
            "starts": [1, 0, 0, 1],
        }
    )
    step = PlayerParticipationStep(
        player_id_columns=("element",),
        chronological_columns=("season", "GW"),
        minutes_columns=("minutes",),
        starts_columns=("starts",),
        windows=(3,),
    )
    result, summary = step.apply(df)

    # Row 1 (GW1): No prior matches
    assert pd.isna(result.iloc[0]["prev_gw_minutes"])
    assert pd.isna(result.iloc[0]["prev_gw_played"])
    assert pd.isna(result.iloc[0]["prev_gw_started"])
    assert pd.isna(result.iloc[0]["prev_gw_bench_unused"])
    assert pd.isna(result.iloc[0]["starts_last_3"])
    assert pd.isna(result.iloc[0]["bench_unused_last_3"])

    # Row 2 (GW2): Prior match was GW1 (90 mins, started, played)
    assert result.iloc[1]["prev_gw_minutes"] == 90.0
    assert result.iloc[1]["prev_gw_played"] == 1.0
    assert result.iloc[1]["prev_gw_started"] == 1.0
    assert result.iloc[1]["prev_gw_bench_unused"] == 0.0
    assert result.iloc[1]["starts_last_3"] == 1.0
    assert result.iloc[1]["bench_unused_last_3"] == 0.0

    # Row 3 (GW3): Prior match was GW2 (0 mins, bench unused)
    assert result.iloc[2]["prev_gw_minutes"] == 0.0
    assert result.iloc[2]["prev_gw_played"] == 0.0
    assert result.iloc[2]["prev_gw_started"] == 0.0
    assert result.iloc[2]["prev_gw_bench_unused"] == 1.0
    # Prior history: GW1 (started=1, bench=0), GW2 (started=0, bench=1) -> mean starts = 0.5, mean bench = 0.5
    assert result.iloc[2]["starts_last_3"] == 0.5
    assert result.iloc[2]["bench_unused_last_3"] == 0.5

    # Row 4 (GW4): Prior match was GW3 (45 mins, sub)
    assert result.iloc[3]["prev_gw_minutes"] == 45.0
    assert result.iloc[3]["prev_gw_played"] == 1.0
    assert result.iloc[3]["prev_gw_started"] == 0.0
    assert result.iloc[3]["prev_gw_bench_unused"] == 0.0
    # Prior history: GW1(1), GW2(0), GW3(0) -> mean starts = 1/3
    assert result.iloc[3]["starts_last_3"] == pytest.approx(1.0 / 3.0)


def test_player_participation_infers_starts_when_starts_col_missing() -> None:
    """When starts is missing or null, infer start as minutes >= 60."""
    df = pd.DataFrame(
        {
            "element": [1, 1, 1],
            "season": ["2018-19"] * 3,
            "GW": [1, 2, 3],
            "minutes": [80, 25, 90],
        }
    )
    step = PlayerParticipationStep(
        player_id_columns=("element",),
        chronological_columns=("season", "GW"),
        minutes_columns=("minutes",),
        starts_columns=("starts",),
        windows=(3,),
    )
    result, _ = step.apply(df)

    # GW2 sees GW1 (80 mins >= 60 -> start=1.0)
    assert result.iloc[1]["prev_gw_started"] == 1.0
    # GW3 sees GW2 (25 mins < 60 -> start=0.0)
    assert result.iloc[2]["prev_gw_started"] == 0.0


def test_player_participation_groups_independently_per_player() -> None:
    """Participation metrics for one player must never leak into another player's rows."""
    df = pd.DataFrame(
        {
            "element": [1, 1, 2, 2],
            "season": ["2022-23"] * 4,
            "GW": [1, 2, 1, 2],
            "minutes": [90, 90, 0, 0],
            "starts": [1, 1, 0, 0],
        }
    )
    step = PlayerParticipationStep(
        player_id_columns=("element",),
        chronological_columns=("season", "GW"),
        minutes_columns=("minutes",),
        starts_columns=("starts",),
        windows=(3,),
    )
    result, _ = step.apply(df)

    p1_gw2 = result[(result["element"] == 1) & (result["GW"] == 2)].iloc[0]
    p2_gw2 = result[(result["element"] == 2) & (result["GW"] == 2)].iloc[0]

    assert p1_gw2["prev_gw_minutes"] == 90.0
    assert p1_gw2["prev_gw_played"] == 1.0
    assert p1_gw2["prev_gw_bench_unused"] == 0.0

    assert p2_gw2["prev_gw_minutes"] == 0.0
    assert p2_gw2["prev_gw_played"] == 0.0
    assert p2_gw2["prev_gw_bench_unused"] == 1.0


# --- PromotedAndHistoricalStep --------------------------------------------------


def test_promoted_and_historical_identifies_promoted_teams_correctly() -> None:
    """A team present in season N but absent in N-1 must be marked as promoted."""
    df = pd.DataFrame(
        {
            "name": ["P1", "P2", "P3"],
            "season": ["2021-22", "2022-23", "2022-23"],
            "team": ["Arsenal", "Arsenal", "Fulham"],
            "opponent_team": ["Chelsea", "Fulham", "Arsenal"],
            "minutes": [90, 90, 90],
            "total_points": [5, 6, 4],
        }
    )
    step = PromotedAndHistoricalStep(
        team_column="team",
        opponent_column="opponent_team",
        season_column="season",
        player_id_columns=("name",),
    )
    result, summary = step.apply(df)

    # 2021-22: First season on record, not marked as promoted
    assert result.iloc[0]["is_promoted_team"] == 0.0
    assert result.iloc[0]["opponent_is_promoted_team"] == 0.0

    # 2022-23 Arsenal vs Fulham: Arsenal not promoted, Fulham is promoted
    assert result.iloc[1]["is_promoted_team"] == 0.0
    assert result.iloc[1]["opponent_is_promoted_team"] == 1.0

    # 2022-23 Fulham vs Arsenal: Fulham is promoted, Arsenal not promoted
    assert result.iloc[2]["is_promoted_team"] == 1.0
    assert result.iloc[2]["opponent_is_promoted_team"] == 0.0


def test_promoted_and_historical_computes_prior_season_stats_without_leakage() -> None:
    """Prior season metrics must only aggregate the previous season (S-1), never current."""
    df = pd.DataFrame(
        {
            "name": ["A", "A", "A", "B"],
            "season": ["2021-22", "2021-22", "2022-23", "2022-23"],
            "team": ["Arsenal", "Arsenal", "Arsenal", "Arsenal"],
            "opponent_team": ["Chelsea", "Spurs", "Chelsea", "Chelsea"],
            "minutes": [90, 90, 45, 90],
            "total_points": [10, 8, 2, 4],
        }
    )
    step = PromotedAndHistoricalStep(
        team_column="team",
        opponent_column="opponent_team",
        season_column="season",
        player_id_columns=("name",),
    )
    result, _ = step.apply(df)

    # Player A in 2021-22 (first season): new to PL, 0 prior minutes/points
    p_a_2021 = result[(result["name"] == "A") & (result["season"] == "2021-22")].iloc[0]
    assert p_a_2021["player_is_new_to_pl"] == 1.0
    assert p_a_2021["prev_season_minutes"] == 0.0
    assert p_a_2021["prev_season_points"] == 0.0

    # Player A in 2022-23: not new, 2021-22 stats: mins=180, pts=18, apps=2, ppm=9.0
    p_a_2022 = result[(result["name"] == "A") & (result["season"] == "2022-23")].iloc[0]
    assert p_a_2022["player_is_new_to_pl"] == 0.0
    assert p_a_2022["prev_season_minutes"] == 180.0
    assert p_a_2022["prev_season_points"] == 18.0
    assert p_a_2022["prev_season_matches"] == 2.0
    assert p_a_2022["prev_season_ppm"] == 9.0

    # Player B in 2022-23 (first appearance): new to PL
    p_b_2022 = result[(result["name"] == "B") & (result["season"] == "2022-23")].iloc[0]
    assert p_b_2022["player_is_new_to_pl"] == 1.0
    assert p_b_2022["prev_season_minutes"] == 0.0


# --- FixtureDifficultyStep -------------------------------------------------------


from src.feature_engineering.steps.fixture_difficulty import FixtureDifficultyStep


def _make_fixture_step() -> FixtureDifficultyStep:
    """Create a FixtureDifficultyStep with default test parameters."""
    return FixtureDifficultyStep(
        team_column="team",
        opponent_column="opponent_team",
        home_column="was_home",
        chronological_columns=("season", "GW"),
    )


def _fixture_df() -> pd.DataFrame:
    """Minimal fixture DataFrame for testing.

    Two teams (Arsenal, Chelsea) playing each other over 3 GWs.
    GW1: Arsenal home 3-1 Chelsea -> Arsenal GF=3 GA=1, Chelsea GF=1 GA=3
    GW2: Chelsea home 2-0 Arsenal -> Arsenal GF=0 GA=2, Chelsea GF=2 GA=0
    GW3: Arsenal home 1-1 Chelsea -> Arsenal GF=1 GA=1, Chelsea GF=1 GA=1
    """
    return pd.DataFrame(
        {
            "team": ["Arsenal", "Chelsea", "Arsenal", "Chelsea", "Arsenal", "Chelsea"],
            "opponent_team": [
                "Chelsea", "Arsenal", "Chelsea", "Arsenal", "Chelsea", "Arsenal",
            ],
            "was_home": [True, False, False, True, True, False],
            "season": ["2022-23"] * 6,
            "GW": [1, 1, 2, 2, 3, 3],
            "team_h_score": [3, 3, 2, 2, 1, 1],
            "team_a_score": [1, 1, 0, 0, 1, 1],
            "total_points": [8, 2, 1, 6, 5, 3],
        }
    )


def test_fixture_difficulty_gw1_is_nan_no_leakage() -> None:
    """GW1 attack/defence strength must be NaN because shift(1) has no prior data."""
    step = _make_fixture_step()
    result, summary = step.apply(_fixture_df())

    assert summary.step_name == "fixture_difficulty"
    # GW1 rows — no prior data, so team_attack_strength must be NaN
    gw1 = result[result["GW"] == 1]
    assert gw1["team_attack_strength"].isna().all()
    assert gw1["team_defence_strength"].isna().all()


def test_fixture_difficulty_gw2_reflects_gw1_only() -> None:
    """GW2 ratings must reflect only GW1 results, not GW2 itself."""
    step = _make_fixture_step()
    result, _ = step.apply(_fixture_df())

    # Arsenal GW2: prior data is GW1 where Arsenal scored 3, conceded 1
    ars_gw2 = result[(result["team"] == "Arsenal") & (result["GW"] == 2)].iloc[0]
    assert ars_gw2["team_attack_strength"] == pytest.approx(3.0)
    assert ars_gw2["team_defence_strength"] == pytest.approx(1.0)

    # Chelsea GW2: prior data is GW1 where Chelsea scored 1, conceded 3
    che_gw2 = result[(result["team"] == "Chelsea") & (result["GW"] == 2)].iloc[0]
    assert che_gw2["team_attack_strength"] == pytest.approx(1.0)
    assert che_gw2["team_defence_strength"] == pytest.approx(3.0)


def test_fixture_difficulty_gw3_expanding_mean() -> None:
    """GW3 ratings must be the expanding mean of GW1 and GW2."""
    step = _make_fixture_step()
    result, _ = step.apply(_fixture_df())

    # Arsenal GW3: GW1 scored 3, GW2 scored 0 -> mean = 1.5
    #              GW1 conceded 1, GW2 conceded 2 -> mean = 1.5
    ars_gw3 = result[(result["team"] == "Arsenal") & (result["GW"] == 3)].iloc[0]
    assert ars_gw3["team_attack_strength"] == pytest.approx(1.5)
    assert ars_gw3["team_defence_strength"] == pytest.approx(1.5)


def test_fixture_difficulty_opponent_ratings_mapped() -> None:
    """Opponent attack/defence strength must be looked up from the opponent's team ratings."""
    step = _make_fixture_step()
    result, _ = step.apply(_fixture_df())

    # Arsenal GW2 faces Chelsea (who are away). Chelsea's GW2 ratings:
    # attack=1.0, defence=3.0. So Arsenal's opponent_attack=1.0, opponent_defence=3.0
    ars_gw2 = result[(result["team"] == "Arsenal") & (result["GW"] == 2)].iloc[0]
    assert ars_gw2["opponent_attack_strength"] == pytest.approx(1.0)
    assert ars_gw2["opponent_defence_strength"] == pytest.approx(3.0)


def test_fixture_difficulty_composite_features() -> None:
    """fixture_difficulty and clean_sheet_likelihood must be correctly derived."""
    step = _make_fixture_step()
    result, _ = step.apply(_fixture_df())

    # Arsenal GW2: opponent_attack=1.0, opponent_defence=3.0
    ars_gw2 = result[(result["team"] == "Arsenal") & (result["GW"] == 2)].iloc[0]

    # fixture_difficulty = opp_attack - opp_defence = 1.0 - 3.0 = -2.0
    assert ars_gw2["fixture_difficulty"] == pytest.approx(-2.0)

    # clean_sheet_likelihood = 1/(1+opp_atk) * 1/(1+team_def) = 1/2 * 1/2 = 0.25
    assert ars_gw2["clean_sheet_likelihood"] == pytest.approx(0.25)


def test_fixture_difficulty_missing_columns_graceful() -> None:
    """If score columns are missing, all outputs should be NaN without error."""
    df = pd.DataFrame(
        {
            "team": ["Arsenal"],
            "opponent_team": ["Chelsea"],
            "was_home": [True],
            "season": ["2022-23"],
            "GW": [1],
        }
    )
    step = _make_fixture_step()
    result, summary = step.apply(df)

    assert "Missing prerequisite" in summary.description
    for col in [
        "team_attack_strength",
        "team_defence_strength",
        "opponent_attack_strength",
        "opponent_defence_strength",
        "fixture_difficulty",
        "clean_sheet_likelihood",
    ]:
        assert col in result.columns
        assert result[col].isna().all()


def test_fixture_difficulty_all_output_columns_present() -> None:
    """All 6 output columns must be present in the result."""
    step = _make_fixture_step()
    result, summary = step.apply(_fixture_df())

    expected = [
        "team_attack_strength",
        "team_defence_strength",
        "opponent_attack_strength",
        "opponent_defence_strength",
        "fixture_difficulty",
        "clean_sheet_likelihood",
    ]
    for col in expected:
        assert col in result.columns
    assert len(summary.columns_added) == 6


# --- AttackingContributionStep --------------------------------------------------


from src.feature_engineering.steps.attacking_contribution import AttackingContributionStep


def test_attacking_contribution_per_90_metrics() -> None:
    """Per-90 metrics must be correctly scaled: (stat / minutes) * 90."""
    df = pd.DataFrame(
        {
            "minutes_avg_last_5": [90.0, 45.0, 0.0],
            "threat_avg_last_5": [30.0, 20.0, 0.0],
            "creativity_avg_last_5": [15.0, 10.0, 0.0],
            "bps_avg_last_5": [25.0, 10.0, 0.0],
            "goals_scored_avg_last_5": [0.5, 0.2, 0.0],
            "assists_avg_last_5": [0.3, 0.1, 0.0],
            "team_attack_strength": [2.0, 1.5, 1.0],
        }
    )
    step = AttackingContributionStep()
    result, summary = step.apply(df)

    assert summary.step_name == "attacking_contribution"
    assert len(summary.columns_added) == 5

    # Row 0: 90 mins, 30 threat -> threat_p90 = (30/90)*90 = 30.0
    assert result.iloc[0]["threat_per_90_last_5"] == pytest.approx(30.0)
    assert result.iloc[0]["creativity_per_90_last_5"] == pytest.approx(15.0)
    assert result.iloc[0]["bps_per_90_last_5"] == pytest.approx(25.0)
    # Row 0 goal involvement: (0.5 + 0.3) / 2.0 = 0.40
    assert result.iloc[0]["goal_involvement_rate_last_5"] == pytest.approx(0.40)
    # Row 0 threat index: 30 * 0.6 + 15 * 0.4 = 18 + 6 = 24.0
    assert result.iloc[0]["attacking_threat_index"] == pytest.approx(24.0)

    # Row 1: 45 mins, 20 threat -> threat_p90 = (20/45)*90 = 40.0
    assert result.iloc[1]["threat_per_90_last_5"] == pytest.approx(40.0)
    assert result.iloc[1]["creativity_per_90_last_5"] == pytest.approx(20.0)

    # Row 2: 0 mins -> per 90 should be 0.0 (no division by zero error)
    assert result.iloc[2]["threat_per_90_last_5"] == pytest.approx(0.0)
    assert result.iloc[2]["creativity_per_90_last_5"] == pytest.approx(0.0)
    assert result.iloc[2]["bps_per_90_last_5"] == pytest.approx(0.0)


def test_attacking_contribution_missing_prerequisites_graceful() -> None:
    """Missing columns should return NaNs gracefully without exception."""
    df = pd.DataFrame({"element": [1, 2]})
    step = AttackingContributionStep()
    result, summary = step.apply(df)

    assert "Missing prerequisite" in summary.description
    for col in [
        "threat_per_90_last_5",
        "creativity_per_90_last_5",
        "bps_per_90_last_5",
        "goal_involvement_rate_last_5",
        "attacking_threat_index",
    ]:
        assert col in result.columns
        assert result[col].isna().all()


# --- PositionEncodingStep -------------------------------------------------------


from src.feature_engineering.steps.position import PositionEncodingStep


def test_position_encoding_canonical_values() -> None:
    """Canonical position strings must map into clean one-hot binary flags."""
    df = pd.DataFrame(
        {
            "position": ["GKP", "DEF", "MID", "FWD", "GK", "AM"],
            "season": ["2022-23"] * 6,
            "element": [1, 2, 3, 4, 5, 6],
            "name_normalized": ["a", "b", "c", "d", "e", "f"],
        }
    )
    step = PositionEncodingStep()
    result, summary = step.apply(df)

    assert summary.step_name == "position_encoding"
    assert len(summary.columns_added) == 4

    # GKP (row 0)
    assert result.iloc[0]["is_position_gkp"] == 1.0
    assert result.iloc[0]["is_position_def"] == 0.0
    assert result.iloc[0]["is_position_mid"] == 0.0
    assert result.iloc[0]["is_position_fwd"] == 0.0

    # DEF (row 1)
    assert result.iloc[1]["is_position_def"] == 1.0

    # MID (row 2)
    assert result.iloc[2]["is_position_mid"] == 1.0

    # FWD (row 3)
    assert result.iloc[3]["is_position_fwd"] == 1.0

    # GK -> GKP (row 4)
    assert result.iloc[4]["is_position_gkp"] == 1.0

    # AM -> MID (row 5)
    assert result.iloc[5]["is_position_mid"] == 1.0

    # Each row sums to exactly 1.0
    row_sums = (
        result["is_position_gkp"]
        + result["is_position_def"]
        + result["is_position_mid"]
        + result["is_position_fwd"]
    )
    assert (row_sums == 1.0).all()


def test_position_encoding_missing_fallback() -> None:
    """Missing positions without lookup data must always fall back to MID (leakage-safe).

    The old behaviour used saves > 0 to infer GKP. That is a same-GW
    outcome and must NEVER influence position inference.
    """
    df = pd.DataFrame(
        {
            "position": [None, None],
            "saves": [0, 5],
            "season": ["1999-00", "1999-00"],
            "element": [999, 998],
            "name_normalized": ["unknown_mid", "unknown_gk"],
        }
    )
    step = PositionEncodingStep(raw_data_dir="non_existent_dir")
    result, _ = step.apply(df)

    # Both rows must fall back to MID — saves column is irrelevant.
    assert result.iloc[0]["is_position_mid"] == 1.0
    assert result.iloc[0]["is_position_gkp"] == 0.0

    assert result.iloc[1]["is_position_mid"] == 1.0
    assert result.iloc[1]["is_position_gkp"] == 0.0


def test_position_encoding_saves_never_influence_position() -> None:
    """Even with very high saves, current-row saves must never flip the position."""
    df = pd.DataFrame(
        {
            "position": [None, None, None],
            "saves": [0, 10, 100],
            "season": ["2022-23"] * 3,
            "element": [1, 2, 3],
            "name_normalized": ["player_a", "player_b", "player_c"],
        }
    )
    step = PositionEncodingStep(raw_data_dir="non_existent_dir")
    result, _ = step.apply(df)

    # All three must be MID, regardless of saves.
    assert (result["is_position_mid"] == 1.0).all()
    assert (result["is_position_gkp"] == 0.0).all()
    assert (result["is_position_def"] == 0.0).all()
    assert (result["is_position_fwd"] == 0.0).all()


def test_position_encoding_valid_lookup_still_works() -> None:
    """When a valid position is present, it must be used regardless of saves."""
    df = pd.DataFrame(
        {
            "position": ["GKP", "DEF", "FWD"],
            "saves": [10, 0, 0],
            "season": ["2022-23"] * 3,
            "element": [1, 2, 3],
            "name_normalized": ["keeper", "defender", "striker"],
        }
    )
    step = PositionEncodingStep(raw_data_dir="non_existent_dir")
    result, _ = step.apply(df)

    assert result.iloc[0]["is_position_gkp"] == 1.0
    assert result.iloc[1]["is_position_def"] == 1.0
    assert result.iloc[2]["is_position_fwd"] == 1.0


def test_position_encoding_deterministic_fallback() -> None:
    """The fallback must be deterministic: always MID for unknowns."""
    df = pd.DataFrame(
        {
            "position": [None] * 5,
            "season": ["2022-23"] * 5,
            "element": list(range(100, 105)),
            "name_normalized": [f"unknown_{i}" for i in range(5)],
        }
    )
    step = PositionEncodingStep(raw_data_dir="non_existent_dir")
    result, _ = step.apply(df)

    # All must be MID.
    assert (result["is_position_mid"] == 1.0).all()
    # Each row must sum to exactly 1.0.
    row_sums = (
        result["is_position_gkp"]
        + result["is_position_def"]
        + result["is_position_mid"]
        + result["is_position_fwd"]
    )
    assert (row_sums == 1.0).all()


# --- ExpectedMinutesStep regression tests ----------------------------------------


from src.feature_engineering.steps.expected_minutes import ExpectedMinutesStep


def _make_expected_minutes_step() -> ExpectedMinutesStep:
    return ExpectedMinutesStep(
        player_id_columns=("element",),
        chronological_columns=("season", "GW"),
        minutes_columns=("minutes",),
        starts_columns=("starts",),
        kickoff_time_column="kickoff_time",
        expected_minutes_halflife=3.0,
    )


def test_expected_minutes_first_row_uses_no_current_data() -> None:
    """The first-ever row for a player must NOT use the current row's minutes."""
    df = pd.DataFrame(
        {
            "element": [1],
            "season": ["2022-23"],
            "GW": [1],
            "minutes": [90],
            "starts": [1],
            "kickoff_time": ["2022-08-06T14:00:00Z"],
        }
    )
    step = _make_expected_minutes_step()
    result, _ = step.apply(df)

    # No prior history: expected_minutes must be NaN, NOT 90.
    assert pd.isna(result.iloc[0]["expected_minutes"])
    assert pd.isna(result.iloc[0]["minutes_std_last_5"])


def test_expected_minutes_consecutive_starts_from_prior_only() -> None:
    """Consecutive-start streaks must be based only on prior rows."""
    df = pd.DataFrame(
        {
            "element": [1, 1, 1, 1],
            "season": ["2022-23"] * 4,
            "GW": [1, 2, 3, 4],
            "minutes": [90, 90, 90, 90],
            "starts": [1, 1, 1, 1],
            "kickoff_time": [
                "2022-08-06T14:00:00Z",
                "2022-08-13T14:00:00Z",
                "2022-08-20T14:00:00Z",
                "2022-08-27T14:00:00Z",
            ],
        }
    )
    step = _make_expected_minutes_step()
    result, _ = step.apply(df)

    # GW1: no prior history.
    assert pd.isna(result.iloc[0]["consecutive_starts"])
    # GW2: 1 prior start (GW1).
    assert result.iloc[1]["consecutive_starts"] == 1.0
    # GW3: 2 prior consecutive starts (GW1, GW2).
    assert result.iloc[2]["consecutive_starts"] == 2.0
    # GW4: 3 prior consecutive starts (GW1, GW2, GW3).
    assert result.iloc[3]["consecutive_starts"] == 3.0


def test_expected_minutes_7d_and_14d_exclude_current_match() -> None:
    """7-day and 14-day workload windows must exclude the current match."""
    df = pd.DataFrame(
        {
            "element": [1, 1, 1],
            "season": ["2022-23"] * 3,
            "GW": [1, 2, 3],
            "minutes": [90, 90, 90],
            "starts": [1, 1, 1],
            "kickoff_time": [
                "2022-08-06T14:00:00Z",
                "2022-08-10T14:00:00Z",   # 4 days later
                "2022-08-12T14:00:00Z",   # 6 days after first, 2 after second
            ],
        }
    )
    step = _make_expected_minutes_step()
    result, _ = step.apply(df)

    # GW1: no prior match => 0 mins in prior 7 days.
    assert result.iloc[0]["minutes_prev_7d"] == 0.0
    assert result.iloc[0]["matches_prev_7d"] == 0.0

    # GW2: 1 prior match (GW1, 4 days prior) within 7d.
    assert result.iloc[1]["minutes_prev_7d"] == 90.0
    assert result.iloc[1]["matches_prev_7d"] == 1.0

    # GW3: 2 prior matches both within 7 days.
    assert result.iloc[2]["minutes_prev_7d"] == 180.0
    assert result.iloc[2]["matches_prev_7d"] == 2.0


def test_expected_minutes_shuffled_input_order() -> None:
    """Shuffled input rows must produce the same chronological result."""
    # Sorted version.
    df_sorted = pd.DataFrame(
        {
            "element": [1, 1, 1],
            "season": ["2022-23"] * 3,
            "GW": [1, 2, 3],
            "minutes": [90, 45, 60],
            "starts": [1, 0, 1],
            "kickoff_time": [
                "2022-08-06T14:00:00Z",
                "2022-08-13T14:00:00Z",
                "2022-08-20T14:00:00Z",
            ],
        }
    )
    # Shuffled version (reverse order).
    df_shuffled = df_sorted.iloc[::-1].reset_index(drop=True)

    step = _make_expected_minutes_step()
    result_sorted, _ = step.apply(df_sorted)
    result_shuffled, _ = step.apply(df_shuffled)

    # After sorting internally by (element, season, GW), the expected_minutes
    # values should be the same for matching GW rows.
    for gw in [1, 2, 3]:
        val_sorted = result_sorted[result_sorted["GW"] == gw].iloc[0]["expected_minutes"]
        val_shuffled = result_shuffled[result_shuffled["GW"] == gw].iloc[0]["expected_minutes"]
        if pd.isna(val_sorted):
            assert pd.isna(val_shuffled), f"GW{gw}: expected NaN but got {val_shuffled}"
        else:
            assert val_sorted == pytest.approx(val_shuffled), (
                f"GW{gw}: sorted={val_sorted}, shuffled={val_shuffled}"
            )


# --- OpportunityStep regression tests --------------------------------------------


from src.feature_engineering.steps.opportunity import OpportunityStep


def test_opportunity_uses_only_rolling_lagged_inputs() -> None:
    """Opportunity step operates on already-lagged rolling averages, never raw current-GW."""
    df = pd.DataFrame(
        {
            # These represent rolling-lagged averages produced by RollingAverageStep.
            "xG_avg_last_5": [0.3, 0.5],
            "xA_avg_last_5": [0.1, 0.2],
            "minutes_avg_last_5": [90.0, 45.0],
            "key_passes_avg_last_5": [2.0, 1.0],
            "big_chances_created_avg_last_5": [1.0, 0.5],
            "big_chances_missed_avg_last_5": [0.2, 0.1],
        }
    )
    step = OpportunityStep()
    result, summary = step.apply(df)

    assert summary.step_name == "opportunity"
    # xG_per_90 for row 0: (0.3 / 90) * 90 = 0.3
    assert result.iloc[0]["xG_per_90_last_5"] == pytest.approx(0.3)
    # xG_per_90 for row 1: (0.5 / 45) * 90 = 1.0
    assert result.iloc[1]["xG_per_90_last_5"] == pytest.approx(1.0)
    # xGI_per_90 = xG_per_90 + xA_per_90
    assert result.iloc[0]["xGI_per_90_last_5"] == pytest.approx(
        result.iloc[0]["xG_per_90_last_5"] + result.iloc[0]["xA_per_90_last_5"]
    )


def test_opportunity_current_gw_stats_never_enter_feature() -> None:
    """Current-GW raw xG/xA/key_passes/big_chances must not pollute opportunity features.

    Even if current-GW raw columns exist alongside the rolling averages,
    the step must only read the rolling-lagged columns.
    """
    df = pd.DataFrame(
        {
            # Lagged rolling averages (safe).
            "xG_avg_last_5": [0.2],
            "xA_avg_last_5": [0.1],
            "minutes_avg_last_5": [90.0],
            "key_passes_avg_last_5": [1.0],
            "big_chances_created_avg_last_5": [0.5],
            "big_chances_missed_avg_last_5": [0.1],
            # Raw current-GW columns (must be ignored).
            "expected_goals": [2.5],
            "expected_assists": [1.5],
            "key_passes": [10],
            "big_chances_created": [5],
            "big_chances_missed": [3],
        }
    )
    step = OpportunityStep()
    result, _ = step.apply(df)

    # The feature must reflect the lagged inputs (0.2 xG), NOT the raw current-GW (2.5).
    assert result.iloc[0]["xG_per_90_last_5"] == pytest.approx(0.2)
    assert result.iloc[0]["xA_per_90_last_5"] == pytest.approx(0.1)


def test_opportunity_missing_inputs_produces_nan_not_error() -> None:
    """If rolling-lagged inputs are missing, opportunity features must be NaN."""
    df = pd.DataFrame({"element": [1, 2]})
    step = OpportunityStep()
    result, summary = step.apply(df)

    assert "Missing prerequisite" in summary.description
    for col in [
        "xG_per_90_last_5",
        "xA_per_90_last_5",
        "key_passes_per_90_last_5",
        "big_chances_created_per_90_last_5",
        "big_chances_missed_rate_last_5",
        "xGI_per_90_last_5",
        "opportunity_index_last_5",
    ]:
        assert col in result.columns

