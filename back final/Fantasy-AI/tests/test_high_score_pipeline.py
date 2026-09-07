"""Unit and integration test suite for Feedback 5 High-Score Pipeline.

Tests:
- Historical training window filtering & recency weighting
- Dedicated high-score classifiers & probability monotonicity
- Upper-tail quantile ceiling regression & quantile monotonicity
- Learning-to-rank grouped by Gameweek
- Two-stage hurdle participation/magnitude model
- Leakage-safe learned multi-objective hybrid blending
- Diagnostic report generation
- HighScoreSettings configuration
"""

from __future__ import annotations

import tempfile
from pathlib import Path
import numpy as np
import pandas as pd
import pytest

from src.config.settings import get_settings, Settings, HighScoreSettings
from src.high_score.training_window import (
    get_ordered_seasons,
    filter_training_window,
    compute_recency_weights,
    SUPPORTED_WINDOWS,
)
from src.high_score.classifier import (
    make_high_score_labels,
    train_high_score_models,
    predict_high_score_probabilities,
    HIGH_SCORE_THRESHOLDS,
    HighScoreModelResult,
)
from src.high_score.quantile import (
    pinball_loss,
    train_quantile_models,
    predict_quantiles,
    DEFAULT_QUANTILES,
)
from src.high_score.ranker import (
    make_relevance_labels,
    train_gameweek_ranker,
    predict_ranking_scores,
)
from src.high_score.hurdle import (
    train_hurdle_model,
    predict_hurdle,
)
from src.high_score.hybrid import (
    fit_hybrid_weights,
    predict_hybrid_scores,
    HybridModelResult,
)
from src.high_score.diagnostics import (
    generate_training_window_report,
    generate_prediction_distribution_report,
    generate_high_score_diagnostics,
    generate_ranking_report,
    generate_feedback5_model_selection_report,
)


# ---------------------------------------------------------------------------
# Synthetic Data Fixture
# ---------------------------------------------------------------------------

@pytest.fixture
def sample_dataset() -> pd.DataFrame:
    """Create a realistic multi-season, multi-GW synthetic dataset."""
    rng = np.random.RandomState(42)
    seasons = ["2020-21", "2021-22", "2022-23", "2023-24", "2024-25", "2025-26"]
    rows = []

    for s_idx, s in enumerate(seasons):
        for gw in range(1, 6):
            for p_id in range(1, 21):
                mins = rng.choice([0, 15, 60, 90], p=[0.2, 0.1, 0.2, 0.5])
                pts = 0
                if mins > 0:
                    pts = int(rng.choice([1, 2, 3, 6, 8, 11, 15], p=[0.3, 0.3, 0.2, 0.1, 0.05, 0.03, 0.02]))
                rows.append({
                    "season": s,
                    "GW": gw,
                    "element": p_id,
                    "team": f"Team_{p_id % 4 + 1}",
                    "opponent_team": f"Team_{(p_id + 1) % 4 + 1}",
                    "was_home": bool(p_id % 2 == 0),
                    "minutes": mins,
                    "total_points": pts,
                    "feat_rolling_pts": rng.normal(pts, 1.5),
                    "feat_rolling_mins": float(mins),
                    "feat_ict_index": rng.uniform(0, 15),
                    "pred_match_home_win_prob": 0.45,
                    "pred_match_away_win_prob": 0.30,
                    "pred_match_draw_prob": 0.25,
                })
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# 1. Training Window & Recency Tests
# ---------------------------------------------------------------------------

def test_get_ordered_seasons(sample_dataset):
    seasons = get_ordered_seasons(sample_dataset)
    assert seasons == ["2020-21", "2021-22", "2022-23", "2023-24", "2024-25", "2025-26"]
    assert get_ordered_seasons(pd.DataFrame()) == []


def test_filter_training_window(sample_dataset):
    # All history
    df_all = filter_training_window(sample_dataset, window_type="all_history", target_season="2025-26")
    assert set(df_all["season"].unique()) == {"2020-21", "2021-22", "2022-23", "2023-24", "2024-25"}

    # Last 3 seasons
    df_3 = filter_training_window(sample_dataset, window_type="last_3_seasons", target_season="2025-26")
    assert set(df_3["season"].unique()) == {"2022-23", "2023-24", "2024-25"}

    # Last 1 season
    df_1 = filter_training_window(sample_dataset, window_type="last_1_season", target_season="2025-26")
    assert set(df_1["season"].unique()) == {"2024-25"}

    # With current_gw: includes past GWs of target season, strictly excludes current and future
    df_gw = filter_training_window(
        sample_dataset,
        window_type="last_2_seasons",
        target_season="2025-26",
        current_gw=3,
    )
    assert set(df_gw["season"].unique()) == {"2023-24", "2024-25", "2025-26"}
    # Verify target season only contains GW < 3
    target_gws = df_gw[df_gw["season"] == "2025-26"]["GW"].unique()
    assert set(target_gws) == {1, 2}

    # Invalid window raises
    with pytest.raises(ValueError):
        filter_training_window(sample_dataset, window_type="invalid_window")


def test_compute_recency_weights(sample_dataset):
    weights_exp = compute_recency_weights(sample_dataset, half_life_seasons=2.0, scheme="exponential")
    assert len(weights_exp) == len(sample_dataset)
    assert np.all(weights_exp > 0)
    assert np.isclose(weights_exp.mean(), 1.0)

    # Newer seasons should have strictly higher weights than older seasons
    w_2020 = weights_exp[sample_dataset["season"] == "2020-21"].mean()
    w_2025 = weights_exp[sample_dataset["season"] == "2025-26"].mean()
    assert w_2025 > w_2020

    # Linear scheme
    weights_lin = compute_recency_weights(sample_dataset, scheme="linear")
    assert np.isclose(weights_lin.mean(), 1.0)
    assert np.all(weights_lin > 0)

    # Scheme none
    weights_none = compute_recency_weights(sample_dataset, scheme="none")
    assert np.all(weights_none == 1.0)


# ---------------------------------------------------------------------------
# 2. Classifier & Monotonicity Tests
# ---------------------------------------------------------------------------

def test_make_high_score_labels():
    pts = np.array([0, 2, 6, 8, 10, 14])
    labels = make_high_score_labels(pts, thresholds=(6, 8, 10, 12))
    assert np.array_equal(labels["high_score_6"], [0, 0, 1, 1, 1, 1])
    assert np.array_equal(labels["high_score_8"], [0, 0, 0, 1, 1, 1])
    assert np.array_equal(labels["high_score_10"], [0, 0, 0, 0, 1, 1])
    assert np.array_equal(labels["high_score_12"], [0, 0, 0, 0, 0, 1])


def test_train_and_predict_high_score_models(sample_dataset):
    feature_cols = ["feat_rolling_pts", "feat_rolling_mins", "feat_ict_index"]
    models = train_high_score_models(
        sample_dataset,
        feature_cols=feature_cols,
        target_col="total_points",
        thresholds=(6, 8, 10),
    )

    assert 6 in models
    assert 8 in models
    assert 10 in models
    assert isinstance(models[6], HighScoreModelResult)

    probs = predict_high_score_probabilities(models, sample_dataset)
    assert "prob_high_score_6" in probs.columns
    assert "prob_high_score_8" in probs.columns
    assert "prob_high_score_10" in probs.columns

    # Verify probability bounds
    assert (probs["prob_high_score_6"] >= 0.0).all() and (probs["prob_high_score_6"] <= 1.0).all()

    # Verify monotonicity enforcement: P(>=6) >= P(>=8) >= P(>=10)
    assert (probs["prob_high_score_6"] >= probs["prob_high_score_8"] - 1e-6).all()
    assert (probs["prob_high_score_8"] >= probs["prob_high_score_10"] - 1e-6).all()


# ---------------------------------------------------------------------------
# 3. Quantile Regression & Monotonicity Tests
# ---------------------------------------------------------------------------

def test_pinball_loss():
    y_true = np.array([5.0, 10.0])
    y_pred = np.array([4.0, 12.0])
    # diff = [1.0, -2.0]
    # q=0.5 -> 0.5*1.0 + (-0.5)*(-2.0) = 0.5 + 1.0 = 1.5 / 2 = 0.75
    loss = pinball_loss(y_true, y_pred, 0.5)
    assert np.isclose(loss, 0.75)


def test_train_and_predict_quantiles(sample_dataset):
    feature_cols = ["feat_rolling_pts", "feat_rolling_mins", "feat_ict_index"]
    q_models = train_quantile_models(
        sample_dataset,
        feature_cols=feature_cols,
        target_col="total_points",
        quantiles=(0.75, 0.85, 0.90),
    )

    assert 0.75 in q_models
    assert 0.85 in q_models
    assert 0.90 in q_models

    q_preds = predict_quantiles(q_models, sample_dataset)
    assert "pred_q_75" in q_preds.columns
    assert "pred_q_85" in q_preds.columns
    assert "pred_q_90" in q_preds.columns

    # Verify monotonicity enforcement: Q75 <= Q85 <= Q90
    assert (q_preds["pred_q_75"] <= q_preds["pred_q_85"] + 1e-6).all()
    assert (q_preds["pred_q_85"] <= q_preds["pred_q_90"] + 1e-6).all()


# ---------------------------------------------------------------------------
# 4. Learning-to-Rank Tests
# ---------------------------------------------------------------------------

def test_make_relevance_labels():
    raw_pts = np.array([-1, 0, 1, 2, 4, 7, 9, 11, 16])
    rel = make_relevance_labels(raw_pts)
    assert rel[0] == 0
    assert rel[1] == 0
    assert rel[2] == 1
    assert rel[4] == 2
    assert rel[5] == 4
    assert rel[6] == 6
    assert rel[7] == 8
    assert rel[8] == 10
    # Strictly non-decreasing
    assert (np.diff(rel) >= 0).all()


def test_train_and_predict_ranker(sample_dataset):
    feature_cols = ["feat_rolling_pts", "feat_rolling_mins", "feat_ict_index"]
    ranker_res = train_gameweek_ranker(
        sample_dataset,
        feature_cols=feature_cols,
        target_col="total_points",
        season_col="season",
        gw_col="GW",
    )
    assert ranker_res.model is not None
    scores = predict_ranking_scores(ranker_res, sample_dataset)
    assert len(scores) == len(sample_dataset)
    assert np.all(np.isfinite(scores))


# ---------------------------------------------------------------------------
# 5. Hurdle Two-Stage Model Tests
# ---------------------------------------------------------------------------

def test_train_and_predict_hurdle(sample_dataset):
    feature_cols = ["feat_rolling_pts", "feat_rolling_mins", "feat_ict_index"]
    hurdle_res = train_hurdle_model(
        sample_dataset,
        feature_cols=feature_cols,
        target_col="total_points",
    )
    assert hurdle_res.classifier is not None
    assert hurdle_res.regressor is not None

    preds = predict_hurdle(hurdle_res, sample_dataset)
    assert len(preds) == len(sample_dataset)
    assert np.all(preds >= 0.0)
    assert np.all(np.isfinite(preds))


# ---------------------------------------------------------------------------
# 6. Learned Multi-Objective Hybrid Engine Tests
# ---------------------------------------------------------------------------

def test_fit_and_predict_hybrid():
    rng = np.random.RandomState(42)
    n = 200
    y_true = rng.choice([0, 1, 2, 5, 8, 12], size=n, p=[0.4, 0.2, 0.2, 0.1, 0.06, 0.04])
    oof_exp = y_true * 0.6 + rng.normal(0, 1, size=n)
    oof_hs6 = (y_true >= 6).astype(float) * 0.8 + rng.uniform(0, 0.2, size=n)
    oof_q85 = y_true * 0.9 + rng.uniform(0, 2, size=n)

    oof_df = pd.DataFrame({
        "total_points": y_true,
        "oof_exp": oof_exp,
        "oof_hs6": oof_hs6,
        "oof_q85": oof_q85,
    })

    hybrid_res = fit_hybrid_weights(oof_df, target_col="total_points")
    assert isinstance(hybrid_res, HybridModelResult)
    # Weights must be non-negative
    for w in hybrid_res.weights.values():
        assert w >= 0.0

    # Inference predictions
    inf_df = pd.DataFrame({
        "oof_exp": [3.0, 7.0],
        "oof_hs6": [0.1, 0.8],
        "oof_q85": [5.0, 11.0],
        "prob_high_score_6": [0.1, 0.8],
    })
    exp_pts, rank_scores = predict_hybrid_scores(hybrid_res, inf_df)
    assert len(exp_pts) == 2
    assert len(rank_scores) == 2
    # Player with high points & probability must rank higher
    assert rank_scores[1] > rank_scores[0]
    assert exp_pts[1] > exp_pts[0]


# ---------------------------------------------------------------------------
# 7. Diagnostics Reports Generation Tests
# ---------------------------------------------------------------------------

def test_diagnostic_reports_generation():
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)

        # 1. Training window report
        win_results = [
            {
                "window": "Window A: All History",
                "mae": 1.0067,
                "rmse": 2.0024,
                "r2": 0.3018,
                "spearman": 0.7108,
                "top10_recall": 0.1189,
                "top20_recall": 0.1652,
                "captain_pts": 5.32,
                "prec_6": 0.3467,
                "rec_6": 0.0866,
                "pred_std": 1.27,
                "pred_max": 8.84,
            },
            {
                "window": "Window B: Last 5 Seasons",
                "mae": 1.0054,
                "rmse": 1.9961,
                "r2": 0.3061,
                "spearman": 0.7124,
                "top10_recall": 0.1245,
                "top20_recall": 0.1730,
                "captain_pts": 6.91,
                "prec_6": 0.4577,
                "rec_6": 0.1140,
                "pred_std": 1.54,
                "pred_max": 10.35,
            },
        ]
        rep1 = generate_training_window_report(win_results, tmp_path / "training_window_report.md")
        assert "Window B: Last 5 Seasons" in rep1
        assert (tmp_path / "training_window_report.md").exists()

        # 2. Prediction distribution report
        y_true = np.array([0, 0, 1, 2, 6, 8, 12, 16])
        y_pred = np.array([0.5, 0.8, 1.2, 1.8, 5.5, 7.2, 9.5, 11.2])
        rep2 = generate_prediction_distribution_report(y_true, y_pred, tmp_path / "prediction_distribution_report.md")
        assert "Prediction Distribution" in rep2
        assert (tmp_path / "prediction_distribution_report.md").exists()

        # 3. High score diagnostics
        metrics = {
            6: {"model_name": "xgboost", "pr_auc": 0.38, "roc_auc": 0.82, "precision": 0.42, "recall": 0.28, "f1": 0.34, "brier": 0.07, "n_positive": 80, "n_total": 1000},
            10: {"model_name": "lightgbm", "pr_auc": 0.22, "roc_auc": 0.86, "precision": 0.35, "recall": 0.18, "f1": 0.24, "brier": 0.03, "n_positive": 20, "n_total": 1000},
        }
        rep3 = generate_high_score_diagnostics(metrics, tmp_path / "high_score_diagnostics.md")
        assert "High-Score Discrimination Diagnostic Report" in rep3
        assert (tmp_path / "high_score_diagnostics.md").exists()

        # 4. Ranking report
        rank_m = {
            "spearman": 0.7125,
            "top10_recall": 0.1245,
            "top20_recall": 0.1730,
            "captain_pts": 6.91,
            "captain_top3_capture": 0.35,
            "captain_top5_capture": 0.52,
        }
        rep4 = generate_ranking_report(rank_m, tmp_path / "ranking_report.md")
        assert "FPL Ranking & Captaincy Selection Report" in rep4
        assert (tmp_path / "ranking_report.md").exists()

        # 5. Model selection report
        cands = [
            {"candidate": "Model A: Feedback 3 Baseline", "mae": 1.0067, "rmse": 2.0024, "r2": 0.3018, "spearman": 0.7108, "top10_recall": 0.1189, "captain_pts": 5.32, "prec_6": 0.3467, "rec_6": 0.0866, "prec_10": 0.20, "rec_10": 0.02, "pred_std": 1.27, "pred_max": 8.84},
            {"candidate": "Model F: Learned Multi-Objective Hybrid", "mae": 0.9856, "rmse": 1.9850, "r2": 0.3120, "spearman": 0.7150, "top10_recall": 0.1262, "captain_pts": 6.91, "prec_6": 0.4412, "rec_6": 0.1240, "prec_10": 0.28, "rec_10": 0.06, "pred_std": 1.62, "pred_max": 11.20},
        ]
        rep5 = generate_feedback5_model_selection_report(
            cands, tmp_path / "model_selection_report.md", "PROMOTE", "Outperformed on MAE and Captain points."
        )
        assert "**RECOMMENDATION**: **PROMOTE**" in rep5
        assert (tmp_path / "model_selection_report.md").exists()


# ---------------------------------------------------------------------------
# 8. HighScoreSettings Tests
# ---------------------------------------------------------------------------

def test_high_score_settings():
    settings = get_settings()
    assert hasattr(settings, "high_score")
    hs = settings.high_score
    assert isinstance(hs, HighScoreSettings)
    assert hs.training_window in SUPPORTED_WINDOWS
    assert 6 in hs.high_score_thresholds
    assert 0.85 in hs.quantile_alphas
    assert hs.upside_boost_factor > 0

