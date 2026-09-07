"""Learned Multi-Objective Hybrid Engine (Feedback 5).

Combines:
1. Expected Points Regression
2. High-Score Probability P(>=6)
3. Upper-Tail Ceiling Score (P85 / P90)
4. Optional Match Predictions

CRITICAL LEAKAGE RULE:
Blending weights are fitted STRICTLY on historical out-of-fold (OOF)
validation predictions. Never uses the final test set.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import numpy as np
import pandas as pd
from sklearn.linear_model import Ridge

from src.config.logging_config import get_logger

logger = get_logger(__name__)


@dataclass
class HybridModelResult:
    """Trained multi-objective hybrid scoring engine."""
    weights: dict[str, float] = field(default_factory=dict)
    intercept: float = 0.0
    blender: object = None
    component_names: list[str] = field(default_factory=list)
    val_mae: float = 0.0
    val_spearman: float = 0.0


def fit_hybrid_weights(
    oof_predictions: pd.DataFrame,
    target_col: str = "total_points",
    component_cols: list[str] | None = None,
    alpha: float = 10.0,
) -> HybridModelResult:
    """Learn non-negative blending weights strictly on historical OOF predictions.

    Args:
        oof_predictions: DataFrame containing OOF predictions for each component
            and the actual target column.
        target_col: Target column name.
        component_cols: List of column names representing component predictions:
            e.g. ['oof_expected_points', 'oof_prob_high_score_6', 'oof_pred_q_85'].
        alpha: L2 regularization strength.

    Returns:
        HybridModelResult with learned non-negative weights and intercept.
    """
    if component_cols is None:
        component_cols = [
            c for c in oof_predictions.columns
            if c.startswith("oof_") and c != f"oof_{target_col}"
        ]

    avail_components = [c for c in component_cols if c in oof_predictions.columns]
    if not avail_components:
        raise ValueError(f"No component columns found in oof_predictions: {component_cols}")

    valid_mask = oof_predictions[target_col].notna()
    for c in avail_components:
        valid_mask &= oof_predictions[c].notna()

    valid_df = oof_predictions.loc[valid_mask]
    if len(valid_df) < 50:
        logger.warning("Insufficient valid OOF rows (%d) for hybrid fitting.", len(valid_df))
        return HybridModelResult()

    X_oof = valid_df[avail_components].values
    y_actual = valid_df[target_col].values

    # Fit non-negative constrained Ridge regression strictly on OOF data
    blender = Ridge(alpha=alpha, positive=True, fit_intercept=True)
    blender.fit(X_oof, y_actual)

    weights_dict = {
        name: float(w) for name, w in zip(avail_components, blender.coef_)
    }
    intercept = float(blender.intercept_)

    from scipy.stats import spearmanr
    from sklearn.metrics import mean_absolute_error

    val_preds = blender.predict(X_oof)
    val_mae = float(mean_absolute_error(y_actual, val_preds))
    sp_corr, _ = spearmanr(y_actual, val_preds)
    val_sp = float(sp_corr) if np.isfinite(sp_corr) else 0.0

    logger.info(
        "Learned OOF Hybrid Weights: %s (intercept=%.4f). Val MAE=%.4f, Spearman=%.4f.",
        weights_dict, intercept, val_mae, val_sp,
    )

    return HybridModelResult(
        weights=weights_dict,
        intercept=intercept,
        blender=blender,
        component_names=avail_components,
        val_mae=val_mae,
        val_spearman=val_sp,
    )


def predict_hybrid_scores(
    hybrid_result: HybridModelResult,
    component_predictions: pd.DataFrame,
    upside_boost_factor: float = 1.5,
) -> tuple[np.ndarray, np.ndarray]:
    """Compute calibrated expected points and upside-boosted FPL rank score.

    Args:
        hybrid_result: Trained HybridModelResult with learned weights.
        component_predictions: DataFrame with inference-time component predictions.
        upside_boost_factor: Weight scaling factor for P(>=6) in final ranking score.

    Returns:
        tuple[np.ndarray, np.ndarray]:
            1. predicted_expected_points (calibrated expected value)
            2. predicted_fpl_rank_score (optimized for ranking/captaincy)
    """
    n_rows = len(component_predictions)
    if hybrid_result.blender is None or not hybrid_result.component_names:
        fallback = np.zeros(n_rows)
        return fallback, fallback

    # Align columns
    feature_matrix = np.zeros((n_rows, len(hybrid_result.component_names)))
    for idx, c_name in enumerate(hybrid_result.component_names):
        # Match oof column name to inference column name (e.g. oof_prob_high_score_6 -> prob_high_score_6)
        inf_name = c_name.replace("oof_", "")
        if inf_name in component_predictions.columns:
            feature_matrix[:, idx] = component_predictions[inf_name].fillna(0).values
        elif c_name in component_predictions.columns:
            feature_matrix[:, idx] = component_predictions[c_name].fillna(0).values

    # 1. Calibrated Expected Points (strictly learned linear blend)
    expected_points = hybrid_result.blender.predict(feature_matrix)
    expected_points = np.maximum(0.0, expected_points)

    # 2. Upside-Boosted FPL Rank Score
    # Enhances captaincy/ranking by giving bonus weight to probability of explosive game
    rank_score = expected_points.copy()
    for th in [6, 8, 10]:
        for candidate_col in [f"prob_high_score_{th}", f"oof_hs{th}", f"oof_hs_{th}", f"hs_{th}", f"hs{th}"]:
            if candidate_col in component_predictions.columns:
                p_val = component_predictions[candidate_col].fillna(0).values
                weight = upside_boost_factor if th == 6 else (upside_boost_factor * 0.5)
                rank_score += weight * p_val
                break

    return expected_points, rank_score

