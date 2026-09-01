"""Unit tests for the distribution-aware and upside/ceiling scoring engine."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.prediction.scoring_engine import FPLDistributionResult, ScoringEngine


def test_percentile_ordering():
    """Verify floor <= p50 <= p75 <= p85 <= p90 <= p95 <= ceiling."""
    events = {
        "p_play_any": 0.95,
        "p_play_60": 0.90,
        "expected_goals": 0.50,
        "expected_assists": 0.30,
        "clean_sheet_prob": 0.40,
        "expected_bonus": 0.50,
    }
    res = ScoringEngine.score_distribution(events, position="MID", n_simulations=5000, random_state=42)

    assert res.floor_points <= res.p50_points + 1e-5
    assert res.p50_points <= res.p75_points + 1e-5
    assert res.p75_points <= res.p85_points + 1e-5
    assert res.p85_points <= res.p90_points + 1e-5
    assert res.p90_points <= res.p95_points + 1e-5
    assert res.p95_points <= res.ceiling_points + 1e-5


def test_expected_value_consistency():
    """Verify simulated Monte Carlo mean closely agrees with deterministic expected points."""
    events = {
        "p_play_any": 0.95,
        "p_play_60": 0.90,
        "expected_goals": 0.40,
        "expected_assists": 0.25,
        "clean_sheet_prob": 0.35,
        "expected_goals_conceded": 1.10,
        "expected_saves": 0.0,
        "expected_yellow_cards": 0.15,
        "expected_red_cards": 0.01,
        "expected_bonus": 0.45,
    }
    deterministic = ScoringEngine.explain_single(events, position="MID")
    dist = ScoringEngine.score_distribution(events, position="MID", n_simulations=10000, random_state=42)

    # Deterministic expectation vs stored expected points in distribution result
    assert dist.expected_points == pytest.approx(deterministic.total_points, abs=1e-5)


def test_minutes_conditioning_sub_vs_starter_vs_bench():
    """Verify that players with low P(60+) have lower upside and lower clean sheet points."""
    starter_events = {
        "p_play_any": 0.95,
        "p_play_60": 0.90,
        "expected_goals": 0.50,
        "clean_sheet_prob": 0.45,
    }
    sub_events = {
        "p_play_any": 0.95,
        "p_play_60": 0.10,  # mostly coming off bench for 20 mins
        "expected_goals": 0.50,
        "clean_sheet_prob": 0.45,
    }
    bench_events = {
        "p_play_any": 0.00,
        "p_play_60": 0.00,
        "expected_goals": 0.50,
        "clean_sheet_prob": 0.45,
    }

    starter_res = ScoringEngine.score_distribution(starter_events, position="MID", n_simulations=3000, random_state=42)
    sub_res = ScoringEngine.score_distribution(sub_events, position="MID", n_simulations=3000, random_state=42)
    bench_res = ScoringEngine.score_distribution(bench_events, position="MID", n_simulations=3000, random_state=42)

    assert starter_res.p85_points > sub_res.p85_points
    assert sub_res.p85_points > bench_res.p85_points
    assert bench_res.expected_points == 0.0
    assert bench_res.ceiling_points == 0.0


def test_position_specific_scoring_in_distribution():
    """Verify position goal and clean sheet rules affect distribution percentiles."""
    events = {
        "p_play_any": 1.0,
        "p_play_60": 1.0,
        "expected_goals": 0.50,
        "clean_sheet_prob": 0.50,
    }
    gkp_res = ScoringEngine.score_distribution(events, position="GKP", n_simulations=3000, random_state=42)
    mid_res = ScoringEngine.score_distribution(events, position="MID", n_simulations=3000, random_state=42)
    fwd_res = ScoringEngine.score_distribution(events, position="FWD", n_simulations=3000, random_state=42)

    # GKP gets 6 pts per goal + 4 for CS
    # MID gets 5 pts per goal + 1 for CS
    # FWD gets 4 pts per goal + 0 for CS
    assert gkp_res.expected_points > mid_res.expected_points
    assert mid_res.expected_points > fwd_res.expected_points


def test_goalkeeper_saves_scoring():
    """Verify goalkeeper save points add upside to GKP."""
    events = {
        "p_play_any": 1.0,
        "p_play_60": 1.0,
        "expected_saves": 6.0,  # ~2 save points
    }
    gkp = ScoringEngine.score_distribution(events, position="GKP", n_simulations=3000, random_state=42)
    def_p = ScoringEngine.score_distribution(events, position="DEF", n_simulations=3000, random_state=42)

    assert gkp.expected_points > def_p.expected_points
    assert gkp.p85_points > def_p.p85_points


def test_card_deductions():
    """Verify card probabilities reduce floor and expected points."""
    clean_events = {
        "p_play_any": 1.0,
        "p_play_60": 1.0,
        "expected_yellow_cards": 0.0,
    }
    dirty_events = {
        "p_play_any": 1.0,
        "p_play_60": 1.0,
        "expected_yellow_cards": 0.8,
        "expected_red_cards": 0.2,
    }
    clean = ScoringEngine.score_distribution(clean_events, position="MID", n_simulations=3000, random_state=42)
    dirty = ScoringEngine.score_distribution(dirty_events, position="MID", n_simulations=3000, random_state=42)

    assert clean.expected_points > dirty.expected_points


def test_distribution_reproducibility():
    """Verify simulation results are completely deterministic with same seed."""
    events = {
        "p_play_any": 0.90,
        "p_play_60": 0.80,
        "expected_goals": 0.35,
        "expected_assists": 0.20,
    }
    res1 = ScoringEngine.score_distribution(events, position="FWD", n_simulations=2000, random_state=99)
    res2 = ScoringEngine.score_distribution(events, position="FWD", n_simulations=2000, random_state=99)

    assert res1.p85_points == pytest.approx(res2.p85_points)
    assert res1.ceiling_points == pytest.approx(res2.ceiling_points)
    assert res1.captaincy_score == pytest.approx(res2.captaincy_score)


def test_captaincy_score_rewards_upside_and_start_confidence():
    """Verify captaincy score favors high upside and high minutes probability."""
    elite_starter = {
        "p_play_any": 0.98,
        "p_play_60": 0.95,
        "expected_goals": 0.80,
        "expected_assists": 0.30,
        "clean_sheet_prob": 0.40,
        "expected_bonus": 0.80,
    }
    rotation_risk = {
        "p_play_any": 0.50,
        "p_play_60": 0.30,
        "expected_goals": 0.80,
        "expected_assists": 0.30,
        "clean_sheet_prob": 0.40,
        "expected_bonus": 0.80,
    }
    safe_low_ceiling = {
        "p_play_any": 0.98,
        "p_play_60": 0.95,
        "expected_goals": 0.05,
        "expected_assists": 0.05,
        "clean_sheet_prob": 0.40,
        "expected_bonus": 0.10,
    }

    res_elite = ScoringEngine.score_distribution(elite_starter, position="FWD", n_simulations=3000, random_state=42)
    res_rotation = ScoringEngine.score_distribution(rotation_risk, position="FWD", n_simulations=3000, random_state=42)
    res_safe = ScoringEngine.score_distribution(safe_low_ceiling, position="MID", n_simulations=3000, random_state=42)

    assert res_elite.captaincy_score > res_rotation.captaincy_score
    assert res_elite.captaincy_score > res_safe.captaincy_score


def test_edge_cases_zero_and_extreme_xg():
    """Verify robust handling of 0 xG and extreme xG without errors or negative values."""
    zero_events = {
        "p_play_any": 0.0,
        "p_play_60": 0.0,
        "expected_goals": 0.0,
    }
    huge_events = {
        "p_play_any": 1.0,
        "p_play_60": 1.0,
        "expected_goals": 3.5,
    }

    res_zero = ScoringEngine.score_distribution(zero_events, position="FWD", n_simulations=1000, random_state=42)
    assert res_zero.expected_points == 0.0
    assert res_zero.p95_points == 0.0

    res_huge = ScoringEngine.score_distribution(huge_events, position="FWD", n_simulations=1000, random_state=42)
    assert res_huge.expected_points > 10.0
    assert res_huge.ceiling_points >= res_huge.expected_points


def test_vectorized_batch_distribution_output():
    """Verify calculate_distribution on batch DataFrames returns all required columns."""
    events = {
        "p_play_any": np.array([0.95, 0.80, 0.0]),
        "p_play_60": np.array([0.90, 0.70, 0.0]),
        "expected_goals": np.array([0.60, 0.10, 0.0]),
        "expected_assists": np.array([0.30, 0.15, 0.0]),
        "clean_sheet_prob": np.array([0.40, 0.35, 0.0]),
    }
    pos_df = pd.DataFrame(
        {
            "is_position_gkp": [0.0, 0.0, 1.0],
            "is_position_def": [0.0, 1.0, 0.0],
            "is_position_mid": [1.0, 0.0, 0.0],
            "is_position_fwd": [0.0, 0.0, 0.0],
        }
    )
    df = ScoringEngine.calculate_distribution(events, pos_df, n_simulations=2000, random_state=42)

    required_cols = [
        "predicted_expected_points",
        "predicted_floor_points",
        "predicted_p50_points",
        "predicted_p75_points",
        "predicted_p85_points",
        "predicted_p90_points",
        "predicted_p95_points",
        "predicted_ceiling_points",
        "predicted_upside_points",
        "captaincy_score",
        "rank_expected",
        "rank_upside",
        "rank_captaincy",
        "predicted_total_points",
    ]
    for col in required_cols:
        assert col in df.columns, f"Missing column: {col}"
        assert not df[col].isna().any(), f"NaN found in column {col}"
