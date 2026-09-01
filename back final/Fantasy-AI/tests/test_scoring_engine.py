"""Unit tests for the deterministic FPL ScoringEngine."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.prediction.scoring_engine import FPLPointBreakdown, ScoringEngine


def test_appearance_scoring_thresholds():
    """Test appearance points rule: P(minutes > 0)*1 + P(minutes >= 60)*1."""
    # Starter with 100% certainty of 90 mins
    b_starter = ScoringEngine.explain_single(
        {"p_play_any": 1.0, "p_play_60": 1.0}, position="MID"
    )
    assert b_starter.appearance_points == 2.0

    # Bench substitute with 100% certainty of playing 20 mins (< 60)
    b_sub = ScoringEngine.explain_single(
        {"p_play_any": 1.0, "p_play_60": 0.0}, position="MID"
    )
    assert b_sub.appearance_points == 1.0

    # Unused bench / not in squad
    b_none = ScoringEngine.explain_single(
        {"p_play_any": 0.0, "p_play_60": 0.0}, position="MID"
    )
    assert b_none.appearance_points == 0.0

    # Probabilistic player (90% chance to play, 70% chance to start/60+)
    b_prob = ScoringEngine.explain_single(
        {"p_play_any": 0.90, "p_play_60": 0.70}, position="MID"
    )
    assert b_prob.appearance_points == pytest.approx(1.60)


def test_position_dependent_goal_scoring():
    """Test that goal values differ by position: GKP/DEF=6, MID=5, FWD=4."""
    events = {"expected_goals": 0.5, "p_play_any": 1.0, "p_play_60": 1.0}

    gkp = ScoringEngine.explain_single(events, position="GKP")
    assert gkp.goal_points == pytest.approx(0.5 * 6.0)

    df = ScoringEngine.explain_single(events, position="DEF")
    assert df.goal_points == pytest.approx(0.5 * 6.0)

    mid = ScoringEngine.explain_single(events, position="MID")
    assert mid.goal_points == pytest.approx(0.5 * 5.0)

    fwd = ScoringEngine.explain_single(events, position="FWD")
    assert fwd.goal_points == pytest.approx(0.5 * 4.0)


def test_assists_scoring_all_positions():
    """Test that assists are 3 points regardless of position."""
    events = {"expected_assists": 0.4, "p_play_any": 1.0, "p_play_60": 1.0}

    for pos in ["GKP", "DEF", "MID", "FWD"]:
        b = ScoringEngine.explain_single(events, position=pos)
        assert b.assist_points == pytest.approx(0.4 * 3.0)


def test_position_dependent_clean_sheet_scoring():
    """Test clean sheets: GKP/DEF=4, MID=1, FWD=0, scaled by P(minutes >= 60)."""
    events = {
        "clean_sheet_prob": 0.50,
        "p_play_any": 1.0,
        "p_play_60": 0.80,
    }

    gkp = ScoringEngine.explain_single(events, position="GKP")
    # 0.50 * 0.80 * 4 = 1.60
    assert gkp.clean_sheet_points == pytest.approx(1.60)

    df = ScoringEngine.explain_single(events, position="DEF")
    assert df.clean_sheet_points == pytest.approx(1.60)

    mid = ScoringEngine.explain_single(events, position="MID")
    # 0.50 * 0.80 * 1 = 0.40
    assert mid.clean_sheet_points == pytest.approx(0.40)

    fwd = ScoringEngine.explain_single(events, position="FWD")
    assert fwd.clean_sheet_points == pytest.approx(0.0)


def test_goals_conceded_penalty():
    """Test goals conceded penalty: -0.5 per goal for GKP/DEF (scaled by P(60+)), 0 for MID/FWD."""
    events = {
        "expected_goals_conceded": 2.0,
        "p_play_any": 1.0,
        "p_play_60": 1.0,
    }

    gkp = ScoringEngine.explain_single(events, position="GKP")
    assert gkp.goals_conceded_points == pytest.approx(-1.0)

    df = ScoringEngine.explain_single(events, position="DEF")
    assert df.goals_conceded_points == pytest.approx(-1.0)

    mid = ScoringEngine.explain_single(events, position="MID")
    assert mid.goals_conceded_points == pytest.approx(0.0)

    fwd = ScoringEngine.explain_single(events, position="FWD")
    assert fwd.goals_conceded_points == pytest.approx(0.0)


def test_saves_scoring_goalkeeper_only():
    """Test saves points: +1 pt per 3 saves for GKP only."""
    events = {"expected_saves": 3.0, "p_play_any": 1.0, "p_play_60": 1.0}

    gkp = ScoringEngine.explain_single(events, position="GKP")
    assert gkp.save_points == pytest.approx(1.0)

    for pos in ["DEF", "MID", "FWD"]:
        b = ScoringEngine.explain_single(events, position=pos)
        assert b.save_points == pytest.approx(0.0)


def test_cards_and_bonus():
    """Test card deductions (-1 yellow, -3 red) and bonus points."""
    events = {
        "expected_yellow_cards": 0.20,
        "expected_red_cards": 0.05,
        "expected_bonus": 0.75,
        "p_play_any": 1.0,
        "p_play_60": 1.0,
    }

    b = ScoringEngine.explain_single(events, position="MID")
    # -0.20 * 1 - 0.05 * 3 = -0.35
    assert b.card_points == pytest.approx(-0.35)
    assert b.bonus_points == pytest.approx(0.75)


def test_total_points_exact_sum_invariant():
    """Test that predicted_total_points is EXACTLY the sum of all individual components."""
    events = {
        "p_play_any": np.array([0.95, 0.80, 0.10, 1.0]),
        "p_play_60": np.array([0.85, 0.70, 0.05, 0.95]),
        "expected_goals": np.array([0.45, 0.05, 0.0, 0.80]),
        "expected_assists": np.array([0.30, 0.15, 0.0, 0.20]),
        "clean_sheet_prob": np.array([0.40, 0.50, 0.20, 0.30]),
        "expected_goals_conceded": np.array([1.2, 0.8, 1.5, 1.0]),
        "expected_saves": np.array([0.0, 3.6, 0.0, 0.0]),
        "expected_yellow_cards": np.array([0.15, 0.10, 0.05, 0.20]),
        "expected_red_cards": np.array([0.01, 0.0, 0.0, 0.02]),
        "expected_bonus": np.array([0.60, 0.40, 0.0, 1.20]),
    }

    positions_df = pd.DataFrame(
        {
            "is_position_gkp": [0.0, 1.0, 0.0, 0.0],
            "is_position_def": [0.0, 0.0, 1.0, 0.0],
            "is_position_mid": [1.0, 0.0, 0.0, 0.0],
            "is_position_fwd": [0.0, 0.0, 0.0, 1.0],
        }
    )

    df = ScoringEngine.calculate_breakdown(events, positions_df)

    sum_components = (
        df["predicted_appearance_points"]
        + df["predicted_goal_points"]
        + df["predicted_assist_points"]
        + df["predicted_clean_sheet_points"]
        + df["predicted_goals_conceded_points"]
        + df["predicted_save_points"]
        + df["predicted_card_points"]
        + df["predicted_bonus_points"]
    )

    np.testing.assert_allclose(
        df["predicted_total_points"].to_numpy(),
        sum_components.to_numpy(),
        rtol=1e-6,
        atol=1e-6,
    )


def test_edge_cases_and_nan_handling():
    """Test that NaNs, negatives, and extremes are safely handled without throwing."""
    events = {
        "p_play_any": [np.nan, -0.5, 1.5],
        "p_play_60": [np.nan, -0.5, 2.0],
        "expected_goals": [np.nan, -1.0, 10.0],
    }
    df = ScoringEngine.calculate_breakdown(events)
    assert not df["predicted_total_points"].isna().any()
    assert (df["predicted_p_play_any"] >= 0.0).all()
    assert (df["predicted_p_play_any"] <= 1.0).all()
    assert (df["predicted_goals"] >= 0.0).all()
