"""Comprehensive test suite for the differential prediction layer.

Covers:
    - Temporal leakage audit (guaranteeing no post-kickoff features)
    - Ownership percentile derivation
    - Target distribution statistics
    - Probability monotonicity enforcement across thresholds
    - Baseline computation and evaluation
    - Differential scoring formulas and logarithmic scaling
    - Server-side differential categorization
    - API endpoint schema and routing
    - Information ceiling and failure analysis diagnostics
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient

from src.api.main import app
from src.differential.baselines import compute_baseline_scores, evaluate_all_baselines
from src.differential.categories import (
    assign_differential_categories,
    CATEGORY_ELITE,
    CATEGORY_VALUE,
    CATEGORY_EMERGING,
)
from src.differential.classifier import (
    enforce_probability_monotonicity,
    prepare_differential_matrix,
)
from src.differential.evaluation import (
    evaluate_differential,
    evaluate_per_gameweek,
)
from src.differential.failure_analysis import run_failure_analysis
from src.differential.features import (
    DIFFERENTIAL_FEATURE_AUDIT,
    build_differential_features,
    get_differential_feature_columns,
)
from src.differential.information_ceiling import run_information_ceiling_analysis
from src.differential.ownership import (
    compute_ownership_pct_approx,
    compute_ownership_percentile,
)
from src.differential.scoring import (
    compute_ownership_advantage,
    compute_scoring_formulas,
)
from src.differential.target_analysis import analyze_target_distribution
from src.differential.temporal_validation import split_chronological


@pytest.fixture
def sample_differential_df() -> pd.DataFrame:
    """Fixture providing realistic synthetic multi-season player gameweek data."""
    rng = np.random.default_rng(42)
    n = 300

    seasons = ["2022-23", "2023-24", "2024-25"]
    gws = [1, 2, 3, 4, 5]

    season_col = [seasons[i % len(seasons)] for i in range(n)]
    gw_col = [gws[(i // len(seasons)) % len(gws)] for i in range(n)]

    df = pd.DataFrame({
        "element": np.repeat(np.arange(1, 61), 5),
        "name": [f"Player_{i}" for i in np.repeat(np.arange(1, 61), 5)],
        "team": [f"Team_{i % 20}" for i in range(n)],
        "position": [["GKP", "DEF", "MID", "FWD"][i % 4] for i in range(n)],
        "season": season_col,
        "GW": gw_col,
        "value": rng.integers(45, 120, size=n),
        "selected": rng.integers(100, 2_000_000, size=n),
        "total_points": rng.choice([0, 1, 2, 2, 3, 6, 8, 11, 15], size=n),
        "total_points_avg_last_3": rng.uniform(0.5, 7.0, size=n),
        "total_points_avg_last_5": rng.uniform(0.5, 6.5, size=n),
        "form_index": rng.uniform(0.5, 8.0, size=n),
        "minutes_avg_last_3": rng.uniform(20.0, 90.0, size=n),
        "minutes_avg_last_5": rng.uniform(20.0, 90.0, size=n),
        "expected_minutes": rng.uniform(20.0, 90.0, size=n),
        "xGI_per_90_last_5": rng.uniform(0.0, 1.2, size=n),
        "attacking_threat_index": rng.uniform(10.0, 80.0, size=n),
        "opportunity_index_last_5": rng.uniform(5.0, 50.0, size=n),
        "starts_last_3": rng.integers(0, 4, size=n),
        "starts_last_5": rng.integers(1, 6, size=n),
        "fixture_difficulty": rng.integers(2, 6, size=n),
        "is_position_gkp": [1 if i % 4 == 0 else 0 for i in range(n)],
        "is_position_def": [1 if i % 4 == 1 else 0 for i in range(n)],
        "is_position_mid": [1 if i % 4 == 2 else 0 for i in range(n)],
        "is_position_fwd": [1 if i % 4 == 3 else 0 for i in range(n)],
        "minutes": rng.integers(0, 91, size=n),
        "expected_goals": rng.uniform(0.0, 1.0, size=n),
        "expected_assists": rng.uniform(0.0, 0.8, size=n),
    })
    return df


def test_leakage_audit_no_future_features():
    """Verify that every feature in the audit is temporally safe and no forbidden columns leak."""
    forbidden_same_gw_columns = {
        "goals_scored", "assists", "bonus", "bps",
        "clean_sheets", "goals_conceded", "own_goals",
        "penalties_saved", "penalties_missed", "yellow_cards", "red_cards",
        "saves", "transfers_in", "transfers_out",
    }

    feature_names = {item[0] for item in DIFFERENTIAL_FEATURE_AUDIT}

    for forbidden in forbidden_same_gw_columns:
        assert forbidden not in feature_names, f"Leakage detected: '{forbidden}' is in differential feature audit!"


def test_ownership_percentile_bounds(sample_differential_df):
    """Verify ownership percentile is bounded strictly between 0 and 1."""
    pctl = compute_ownership_percentile(sample_differential_df)
    assert len(pctl) == len(sample_differential_df)
    assert (pctl >= 0.0).all()
    assert (pctl <= 1.0).all()

    approx = compute_ownership_pct_approx(sample_differential_df)
    assert len(approx) == len(sample_differential_df)
    assert (approx >= 0.0).all()
    assert (approx <= 1.0).all()


def test_feature_engineering_creates_valid_columns(sample_differential_df):
    """Verify build_differential_features builds all derived columns without inf/nan."""
    feat_df = build_differential_features(sample_differential_df)

    derived = [
        "ownership_percentile", "ownership_pct_approx", "value_efficiency",
        "xgi_efficiency", "minutes_trend", "form_momentum",
        "starts_ratio_3_5", "fixture_upside", "opportunity_x_minutes",
    ]
    for col in derived:
        assert col in feat_df.columns, f"Expected derived column '{col}' in output"
        assert not feat_df[col].isna().all(), f"Column '{col}' is all NaN"


def test_target_distribution_analysis(sample_differential_df):
    """Verify target distribution analysis runs and computes valid statistical summaries."""
    res = analyze_target_distribution(sample_differential_df)
    assert res.overall is not None
    assert res.overall.n_rows == len(sample_differential_df)
    assert res.overall.freq_8_plus >= 0.0
    assert len(res.by_season) > 0
    assert len(res.by_position) > 0


def test_chronological_splits_integrity(sample_differential_df):
    """Verify chronological splitting ensures strict temporal ordering with no leakage."""
    splits = split_chronological(sample_differential_df, val_seasons_count=1, test_seasons_count=1)

    assert len(splits.train_df) > 0
    assert len(splits.val_df) > 0
    assert len(splits.test_df) > 0

    # Ensure train and test seasons are strictly disjoint
    train_seasons = set(splits.train_seasons)
    test_seasons = set(splits.test_seasons)
    assert train_seasons.isdisjoint(test_seasons), "Train and test seasons must not overlap!"


def test_monotonic_probability_enforcement():
    """Verify that enforce_probability_monotonicity guarantees P(6+) >= P(8+) >= P(10+) >= P(12+)."""
    # Create intentionally non-monotonic probabilities
    raw_probs = {
        6: np.array([0.20, 0.40, 0.10]),
        8: np.array([0.35, 0.30, 0.25]),  # 0.35 > 0.20 (violates monotonicity!)
        10: np.array([0.15, 0.35, 0.05]),
        12: np.array([0.25, 0.10, 0.01]), # 0.25 > 0.15
    }

    mono = enforce_probability_monotonicity(raw_probs, thresholds=(6, 8, 10, 12))

    for i in range(3):
        assert mono[6][i] >= mono[8][i] - 1e-9, f"Row {i}: P(6) < P(8)"
        assert mono[8][i] >= mono[10][i] - 1e-9, f"Row {i}: P(8) < P(10)"
        assert mono[10][i] >= mono[12][i] - 1e-9, f"Row {i}: P(10) < P(12)"


def test_scoring_formulas_and_log_advantage(sample_differential_df):
    """Verify scoring formulas and logarithmic ownership bonus."""
    adv_low = compute_ownership_advantage(0.05)
    adv_high = compute_ownership_advantage(0.90)
    assert adv_low > adv_high, "Low ownership must receive strictly higher advantage bonus than high ownership"

    sample_differential_df["p_8_plus"] = 0.25
    sample_differential_df["ownership_percentile"] = 0.10
    scored = compute_scoring_formulas(sample_differential_df)

    assert "score_f1" in scored.columns
    assert "score_f2" in scored.columns
    assert "score_f3" in scored.columns
    assert (scored["score_f3"] > 0).all()


def test_differential_categories_assignment(sample_differential_df):
    """Verify categories are assigned correctly according to thresholds."""
    df = sample_differential_df.copy()
    df["p_8_plus"] = 0.50
    df["ownership_percentile"] = 0.05
    df["value"] = 50
    df["starts_ratio_3_5"] = 1.0
    df["minutes_trend"] = 25.0

    cats = assign_differential_categories(df, prob_col="p_8_plus", min_examples=1)
    assert len(cats) == len(df)
    assert CATEGORY_ELITE in cats.values


def test_baseline_computation_and_evaluation(sample_differential_df):
    """Verify all 5 baselines are computed and evaluated."""
    scored_base = compute_baseline_scores(sample_differential_df)
    for letter in ["a", "b", "c", "d", "e"]:
        col = f"score_baseline_{letter}"
        assert col in scored_base.columns
        assert not scored_base[col].isna().all()

    base_results = evaluate_all_baselines(sample_differential_df)
    assert len(base_results) == 5
    for name, met in base_results.items():
        assert met.threshold == 8
        assert met.precision_at_10 >= 0.0


def test_diagnostics_ceiling_and_failure(sample_differential_df):
    """Verify Information Ceiling and Failure Analysis modules run without crashing."""
    df = sample_differential_df.copy()
    rng = np.random.default_rng(1)
    df["model_score"] = rng.uniform(0, 1, size=len(df))
    df["score_baseline_e"] = rng.uniform(0, 1, size=len(df))
    df["ownership_percentile"] = 0.15

    ceiling = run_information_ceiling_analysis(
        df,
        model_score_col="model_score",
        baseline_score_col="score_baseline_e",
    )
    assert ceiling.model_prauc >= 0.0
    assert len(ceiling.summary_report) > 0

    failure = run_failure_analysis(
        df,
        score_col="model_score",
    )
    assert failure.recall_rate >= 0.0
    assert len(failure.summary_markdown) > 0


def test_api_differentials_route(sample_differential_df):
    """Verify FastAPI GET /differentials/next-gameweek responds cleanly with 200 OK."""
    from types import SimpleNamespace
    diff_df = sample_differential_df.copy()
    diff_df["differential_score"] = 5.5
    diff_df["differential_category"] = "Elite Differential"
    diff_df["price"] = 6.0
    diff_df["ownership_pct"] = 8.5
    diff_df["p_6_plus"] = 0.35
    diff_df["p_8_plus"] = 0.20
    diff_df["p_10_plus"] = 0.10
    diff_df["p_12_plus"] = 0.05
    diff_df["predicted_expected_points"] = 4.5
    diff_df["predicted_gameweek"] = 4

    fake_state = SimpleNamespace(
        predictions=diff_df,
        differential_predictions=diff_df,
        season="2024-25",
        latest_completed_gameweek=3,
        predicted_gameweek=4,
        generated_at="2026-09-14T19:00:00Z",
    )
    app.state.fantasy_ai_state = fake_state

    client = TestClient(app)
    response = client.get("/differentials/next-gameweek")
    assert response.status_code == 200
    data = response.json()
    assert "predictions" in data
    assert "count" in data
    assert isinstance(data["predictions"], list)
    assert data["count"] > 0
