"""Differential scoring formulas and empirical validation.

A transparent, interpretable differential score that combines:
    1. Upside probability (P(>= 8) from calibrated classifier)
    2. Value efficiency (points or threat per unit price)
    3. Ownership advantage (logarithmic bonus for low ownership)

Multiple mathematical formulations are compared empirically against historical
Top-K hit rates and Spearman correlation rather than selected arbitrarily.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.linear_model import Ridge
from scipy.stats import spearmanr

from src.config.logging_config import get_logger
from src.differential.models import ScoringFormulaResult

logger = get_logger(__name__)


def compute_ownership_advantage(
    ownership_percentile: pd.Series | np.ndarray,
    method: str = "log",
) -> np.ndarray:
    """Compute ownership advantage factor.

    A logarithmic scale prevents extreme distortion from 0.1% owned benchwarmers
    while granting meaningful advantage to players with < 15-20% ownership.

    Args:
        ownership_percentile: Values in [0.0, 1.0].
        method: Scaling method ('log' or 'inverse_power').

    Returns:
        np.ndarray: Ownership advantage multiplier (>= 1.0).
    """
    p = np.clip(np.asarray(ownership_percentile, dtype=float), 0.001, 1.0)
    if method == "log":
        # Logarithmic advantage: log(1 + 1 / p)
        # For p=0.05 -> log(1 + 20) = log(21) = 3.04
        # For p=0.50 -> log(1 + 2) = log(3) = 1.10
        # For p=0.90 -> log(1 + 1.11) = log(2.11) = 0.75
        return np.log1p(1.0 / p)
    elif method == "inverse_power":
        return (1.0 - p) ** 0.5
    else:
        return 1.0 - p


def _safe_series(df: pd.DataFrame, col_name: str, default_val: float) -> pd.Series:
    if col_name in df.columns:
        return pd.to_numeric(df[col_name], errors="coerce").fillna(default_val)
    return pd.Series(default_val, index=df.index, dtype=float)


def compute_scoring_formulas(
    df: pd.DataFrame,
    prob_col: str = "p_8_plus",
    ridge_model: Ridge | None = None,
) -> pd.DataFrame:
    """Calculate scores under candidate scoring formulations.

    Candidates:
        F1: P(>=8) * log_ownership_adv
        F2: P(>=8) * value_efficiency * log_ownership_adv
        F3: (P(>=8)^0.7) * (value_efficiency^0.3) * (log_ownership_adv^0.5)
        F4: Ridge blend of features (if model provided)

    Args:
        df: DataFrame with predictions and features.
        prob_col: Probability column name.
        ridge_model: Optional trained Ridge regressor for F4.

    Returns:
        pd.DataFrame: DataFrame with columns score_f1, score_f2, score_f3, score_f4.
    """
    out = df.copy()

    p8 = _safe_series(out, prob_col, 0.0).clip(lower=0.0, upper=1.0)
    price = _safe_series(out, "value", 50.0).clip(lower=40.0) / 10.0
    form = _safe_series(out, "form_index", 0.0).clip(lower=0.0)
    own_pct = _safe_series(out, "ownership_percentile", 0.5)

    # Value efficiency (form points per million)
    val_eff = (form / price).clip(lower=0.01)

    # Ownership advantage
    own_adv = compute_ownership_advantage(own_pct, method="log")

    # Formulation 1: Upside * Ownership
    out["score_f1"] = (p8 * own_adv).values

    # Formulation 2: Upside * Value * Ownership
    out["score_f2"] = (p8 * val_eff * own_adv).values

    # Formulation 3: Sublinear exponent-balanced formulation
    out["score_f3"] = (
        (p8 ** 0.7) *
        (val_eff ** 0.3) *
        (np.clip(own_adv, 0.1, 10.0) ** 0.5)
    ).values

    # Formulation 4: Learned linear blend
    if ridge_model is not None:
        X_blend = np.column_stack([p8.values, val_eff.values, own_adv])
        out["score_f4"] = ridge_model.predict(X_blend)
    else:
        out["score_f4"] = out["score_f3"]

    return out


def fit_ridge_scoring_formula(
    train_df: pd.DataFrame,
    target_col: str = "total_points",
    prob_col: str = "p_8_plus",
) -> Ridge:
    """Fit a Ridge regression blender for Formulation 4 on training data."""
    p8 = _safe_series(train_df, prob_col, 0.0).clip(lower=0.0, upper=1.0).values
    price = _safe_series(train_df, "value", 50.0).clip(lower=40.0).values / 10.0
    form = _safe_series(train_df, "form_index", 0.0).clip(lower=0.0).values
    val_eff = np.clip(form / price, 0.01, 10.0)
    own_pct = _safe_series(train_df, "ownership_percentile", 0.5).values
    own_adv = compute_ownership_advantage(own_pct, method="log")

    X = np.column_stack([p8, val_eff, own_adv])
    y = _safe_series(train_df, target_col, 0.0).values

    ridge = Ridge(alpha=1.0, positive=True)
    ridge.fit(X, y)
    logger.info("Fitted Ridge scoring weights: p8=%.3f, val_eff=%.3f, own_adv=%.3f",
                ridge.coef_[0], ridge.coef_[1], ridge.coef_[2])
    return ridge


def validate_scoring_formulas(
    val_df: pd.DataFrame,
    target_col: str = "total_points",
    prob_col: str = "p_8_plus",
    ownership_col: str = "ownership_percentile",
    ridge_model: Ridge | None = None,
) -> tuple[str, list[ScoringFormulaResult]]:
    """Empirically evaluate scoring formula candidates and pick the best.

    Criteria: Top-20 differential hit rate (players with actual >= 8 points)
    and Spearman rank correlation with actual points.

    Args:
        val_df: Validation DataFrame with probabilities and outcomes.
        target_col: Actual outcome column.
        prob_col: Predicted upside probability column.
        ownership_col: Ownership percentile column.
        ridge_model: Optional trained Ridge model for F4.

    Returns:
        tuple[str, list[ScoringFormulaResult]]: (best_formula_key, results_list)
    """
    scored = compute_scoring_formulas(val_df, prob_col=prob_col, ridge_model=ridge_model)
    y_actual = pd.to_numeric(scored[target_col], errors="coerce").fillna(0.0).values
    own_vals = pd.to_numeric(scored.get(ownership_col, 0.5), errors="coerce").fillna(0.5).values

    formulas = [
        ("score_f1", "F1: P(>=8) * log_own_adv"),
        ("score_f2", "F2: P(>=8) * val_eff * log_own_adv"),
        ("score_f3", "F3: P(>=8)^0.7 * val_eff^0.3 * log_own_adv^0.5"),
        ("score_f4", "F4: Learned Ridge Blend"),
    ]

    results: list[ScoringFormulaResult] = []
    best_key = "score_f3"
    best_hit_rate = -1.0

    for col, desc in formulas:
        scores = pd.to_numeric(scored[col], errors="coerce").fillna(0.0).values
        top20_idx = np.argsort(scores)[::-1][:20]

        # Actual points of top-20
        top20_pts = y_actual[top20_idx]
        hit8 = float((top20_pts >= 8).sum() / len(top20_pts)) if len(top20_pts) > 0 else 0.0
        hit10 = float((top20_pts >= 10).sum() / len(top20_pts)) if len(top20_pts) > 0 else 0.0
        hit12 = float((top20_pts >= 12).sum() / len(top20_pts)) if len(top20_pts) > 0 else 0.0

        top10_idx = np.argsort(scores)[::-1][:10]
        avg10 = float(y_actual[top10_idx].mean()) if len(top10_idx) > 0 else 0.0
        avg20 = float(top20_pts.mean()) if len(top20_pts) > 0 else 0.0

        try:
            sp, _ = spearmanr(y_actual, scores)
            sp_val = float(sp) if np.isfinite(sp) else 0.0
        except Exception:
            sp_val = 0.0

        res = ScoringFormulaResult(
            name=col,
            formula_description=desc,
            hit_rate_8=round(hit8, 4),
            hit_rate_10=round(hit10, 4),
            hit_rate_12=round(hit12, 4),
            avg_points_top10=round(avg10, 2),
            avg_points_top20=round(avg20, 2),
            spearman_vs_actual=round(sp_val, 4),
        )
        results.append(res)
        logger.info("Scoring %s: Hit@8=%.3f, Top10AvgPts=%.2f, Spearman=%.3f",
                    desc, hit8, avg10, sp_val)

        if hit8 > best_hit_rate:
            best_hit_rate = hit8
            best_key = col

    logger.info("Selected best scoring formula: %s with Top-20 Hit@8=%.4f", best_key, best_hit_rate)
    return best_key, results
