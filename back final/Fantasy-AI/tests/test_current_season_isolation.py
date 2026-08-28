"""Tests proving current-season in-season rolling features are completely isolated from historical seasons."""

import numpy as np
import pandas as pd
import pytest

from src.prediction.next_gameweek import build_next_gameweek_rows


def test_changing_historical_seasons_does_not_affect_current_season_rolling_state() -> None:
    """Historical seasons must NEVER alter in-season rolling statistics for the current season."""
    # Current season matches for player 'saka' (GW1 and GW2 in 2026-27)
    current_season_df = pd.DataFrame(
        {
            "name_normalized": ["saka", "saka"],
            "name": ["Saka", "Saka"],
            "season": ["2026-27", "2026-27"],
            "GW": [1, 2],
            "total_points": [9, 6],
            "minutes": [90, 85],
            "goals_scored": [1, 0],
            "assists": [0, 1],
            "expected_goals": [0.65, 0.20],
            "expected_assists": [0.10, 0.40],
            "threat": [40.0, 25.0],
            "creativity": [30.0, 50.0],
            "influence": [35.0, 28.0],
            "bps": [32, 24],
            "bonus": [3, 1],
            "starts": [1, 1],
            "team": ["Arsenal", "Arsenal"],
            "opponent_team": ["Wolves", "Aston Villa"],
            "is_home": [1, 0],
            "fixture_difficulty": [2, 3],
            "value": [100, 100],
        }
    )

    # Scenario A: Historical season with high points
    history_scenario_a = pd.DataFrame(
        {
            "name_normalized": ["saka", "saka"],
            "name": ["Bukayo Saka", "Bukayo Saka"],
            "season": ["2025-26", "2025-26"],
            "GW": [37, 38],
            "total_points": [15, 12],
            "minutes": [90, 90],
            "goals_scored": [2, 1],
            "assists": [1, 1],
            "expected_goals": [1.2, 0.8],
            "expected_assists": [0.5, 0.6],
            "threat": [80.0, 75.0],
            "creativity": [60.0, 70.0],
            "influence": [65.0, 50.0],
            "bps": [45, 40],
            "bonus": [3, 3],
            "starts": [1, 1],
            "team": ["Arsenal", "Arsenal"],
            "opponent_team": ["Chelsea", "Everton"],
            "is_home": [1, 0],
            "fixture_difficulty": [4, 2],
            "value": [100, 100],
        }
    )

    # Scenario B: Historical season with 0 points and 0 minutes (injured / inactive)
    history_scenario_b = pd.DataFrame(
        {
            "name_normalized": ["saka", "saka"],
            "name": ["Bukayo Saka", "Bukayo Saka"],
            "season": ["2025-26", "2025-26"],
            "GW": [37, 38],
            "total_points": [0, 0],
            "minutes": [0, 0],
            "goals_scored": [0, 0],
            "assists": [0, 0],
            "expected_goals": [0.0, 0.0],
            "expected_assists": [0.0, 0.0],
            "threat": [0.0, 0.0],
            "creativity": [0.0, 0.0],
            "influence": [0.0, 0.0],
            "bps": [0, 0],
            "bonus": [0, 0],
            "starts": [0, 0],
            "team": ["Arsenal", "Arsenal"],
            "opponent_team": ["Chelsea", "Everton"],
            "is_home": [1, 0],
            "fixture_difficulty": [4, 2],
            "value": [100, 100],
        }
    )

    data_a = pd.concat([history_scenario_a, current_season_df], ignore_index=True)
    data_b = pd.concat([history_scenario_b, current_season_df], ignore_index=True)

    rows_a = build_next_gameweek_rows(
        data_a,
        player_id_columns=("name_normalized", "name"),
        chronological_columns=("season", "GW"),
        max_valid_gameweek=38,
        target_gameweek=3,
    )

    rows_b = build_next_gameweek_rows(
        data_b,
        player_id_columns=("name_normalized", "name"),
        chronological_columns=("season", "GW"),
        max_valid_gameweek=38,
        target_gameweek=3,
    )

    # Assert exactly 1 prediction row for Saka in current season
    assert len(rows_a) == 1
    assert len(rows_b) == 1

    saka_a = rows_a.iloc[0]
    saka_b = rows_b.iloc[0]

    # In-season state features must be IDENTICAL between Scenario A and Scenario B:
    # 1. Total points average
    assert saka_a["total_points_avg_last_3"] == saka_b["total_points_avg_last_3"] == (9 + 6) / 2.0
    # 2. Minutes average
    assert saka_a["minutes_avg_last_5"] == saka_b["minutes_avg_last_5"] == (90 + 85) / 2.0
    # 3. Expected minutes
    assert saka_a["expected_minutes"] == saka_b["expected_minutes"]
    # 4. Form index
    assert saka_a["form_index"] == saka_b["form_index"]
    # 5. Opportunity index
    assert saka_a["opportunity_index_last_5"] == saka_b["opportunity_index_last_5"]
    # 6. xG, xA, Threat averages
    assert saka_a["xG_avg_last_5"] == saka_b["xG_avg_last_5"] == (0.65 + 0.20) / 2.0
    assert saka_a["xA_avg_last_5"] == saka_b["xA_avg_last_5"] == (0.10 + 0.40) / 2.0
    assert saka_a["threat_avg_last_5"] == saka_b["threat_avg_last_5"] == (40.0 + 25.0) / 2.0
    # 7. Participation
    assert saka_a["prev_gw_minutes"] == saka_b["prev_gw_minutes"] == 85.0
    assert saka_a["prev_gw_started"] == saka_b["prev_gw_started"] == 1.0
    assert saka_a["starts_last_3"] == saka_b["starts_last_3"] == 1.0


def test_gw1_cold_start_leaves_in_season_features_unpolluted_by_last_season() -> None:
    """For GW1, in-season rolling statistics must be NaN / unavailable, not substituted by last season's stats."""
    # Historical season 2025-26 exists
    history_df = pd.DataFrame(
        {
            "name_normalized": ["saka"],
            "name": ["Bukayo Saka"],
            "season": ["2025-26"],
            "GW": [38],
            "total_points": [12],
            "minutes": [90],
            "expected_goals": [0.8],
            "expected_assists": [0.6],
            "threat": [75.0],
            "starts": [1],
            "team": ["Arsenal"],
        }
    )

    # GW1 row with NO prior 2026-27 matches
    current_df = pd.DataFrame(
        {
            "name_normalized": ["saka"],
            "name": ["Saka"],
            "season": ["2026-27"],
            "GW": [1],
            "total_points": [9],
            "minutes": [90],
            "expected_goals": [0.65],
            "expected_assists": [0.10],
            "threat": [40.0],
            "starts": [1],
            "team": ["Arsenal"],
        }
    )

    full_df = pd.concat([history_df, current_df], ignore_index=True)

    gw1_pred_row = build_next_gameweek_rows(
        full_df,
        player_id_columns=("name_normalized", "name"),
        chronological_columns=("season", "GW"),
        max_valid_gameweek=38,
        target_gameweek=1,
    )

    assert len(gw1_pred_row) == 1
    row = gw1_pred_row.iloc[0]

    # In-season rolling features must NOT carry 2025-26 stats
    assert row["predicted_for_gw"] == 1
    assert pd.isna(row.get("total_points_avg_last_3")) or row.get("total_points_avg_last_3") != 12.0
    assert pd.isna(row.get("minutes_avg_last_5")) or row.get("minutes_avg_last_5") != 90.0
