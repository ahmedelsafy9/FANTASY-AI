"""Model selection utilities for multi-stage prediction.

Builds candidate model specs per task with graceful import detection
for optional dependencies (CatBoost, XGBoost, LightGBM).
HistGradientBoosting is always available as a sklearn built-in.
"""

from __future__ import annotations

from sklearn.ensemble import (
    HistGradientBoostingRegressor,
    RandomForestRegressor,
)
from sklearn.linear_model import Ridge

from src.config.logging_config import get_logger

logger = get_logger(__name__)

# Graceful optional imports
try:
    from lightgbm import LGBMRegressor
except ImportError:
    LGBMRegressor = None
    logger.info("LightGBM not available — will be skipped as a candidate.")

try:
    from xgboost import XGBRegressor
except ImportError:
    XGBRegressor = None
    logger.info("XGBoost not available — will be skipped as a candidate.")

try:
    from catboost import CatBoostRegressor
except ImportError:
    CatBoostRegressor = None
    logger.info("CatBoost not available — will be skipped as a candidate.")


def _make_lgbm(random_state: int = 42, **kwargs):
    """Build a LightGBM regressor with sensible defaults."""
    defaults = dict(
        n_estimators=100,
        max_depth=6,
        learning_rate=0.05,
        random_state=random_state,
        n_jobs=4,
        verbosity=-1,
    )
    defaults.update(kwargs)
    return LGBMRegressor(**defaults)


def _make_xgb(random_state: int = 42, **kwargs):
    """Build an XGBoost regressor with sensible defaults."""
    defaults = dict(
        n_estimators=100,
        max_depth=6,
        learning_rate=0.05,
        random_state=random_state,
        n_jobs=4,
    )
    defaults.update(kwargs)
    return XGBRegressor(**defaults)


def _make_catboost(random_state: int = 42, **kwargs):
    """Build a CatBoost regressor with sensible defaults."""
    defaults = dict(
        iterations=100,
        depth=6,
        learning_rate=0.05,
        random_seed=random_state,
        thread_count=4,
        verbose=0,
    )
    defaults.update(kwargs)
    return CatBoostRegressor(**defaults)


def _make_histgbm(random_state: int = 42, **kwargs):
    """Build a HistGradientBoosting regressor."""
    defaults = dict(
        max_iter=100,
        max_depth=6,
        learning_rate=0.05,
        random_state=random_state,
    )
    defaults.update(kwargs)
    return HistGradientBoostingRegressor(**defaults)


def _make_ridge(random_state: int = 42, **kwargs):
    """Build a Ridge regressor."""
    defaults = dict(alpha=1.0)
    defaults.update(kwargs)
    return Ridge(**defaults)


def _make_rf(random_state: int = 42, **kwargs):
    """Build a Random Forest regressor."""
    defaults = dict(
        n_estimators=50,
        max_depth=10,
        random_state=random_state,
        n_jobs=4,
    )
    defaults.update(kwargs)
    return RandomForestRegressor(**defaults)


def build_match_candidates(random_state: int = 42) -> list[tuple[str, callable]]:
    """Build candidate models for match result prediction.

    Returns:
        list of (name, builder_fn) tuples.
    """
    candidates = [
        ("ridge", lambda: _make_ridge(random_state)),
        ("histgbm", lambda: _make_histgbm(random_state)),
    ]
    if LGBMRegressor is not None:
        candidates.append(("lightgbm", lambda: _make_lgbm(random_state)))
    if XGBRegressor is not None:
        candidates.append(("xgboost", lambda: _make_xgb(random_state)))
    if CatBoostRegressor is not None:
        candidates.append(("catboost", lambda: _make_catboost(random_state)))
    return candidates


def build_contribution_candidates(
    target: str,
    random_state: int = 42,
) -> list[tuple[str, callable]]:
    """Build candidate models for a specific contribution target.

    Args:
        target: Target name (e.g. "goals_scored", "assists", "clean_sheets").
        random_state: Random seed for reproducibility.

    Returns:
        list of (name, builder_fn) tuples.
    """
    candidates = [
        ("histgbm", lambda: _make_histgbm(random_state)),
    ]
    if LGBMRegressor is not None:
        candidates.append(("lightgbm", lambda: _make_lgbm(random_state)))
    if XGBRegressor is not None:
        candidates.append(("xgboost", lambda: _make_xgb(random_state)))
    if CatBoostRegressor is not None:
        candidates.append(("catboost", lambda: _make_catboost(random_state)))
    return candidates


def build_points_candidates(random_state: int = 42) -> list[tuple[str, callable]]:
    """Build candidate models for FPL points prediction.

    Returns:
        list of (name, builder_fn) tuples.
    """
    candidates = [
        ("ridge", lambda: _make_ridge(random_state)),
        ("random_forest", lambda: _make_rf(random_state)),
        ("histgbm", lambda: _make_histgbm(random_state)),
    ]
    if LGBMRegressor is not None:
        candidates.append(("lightgbm", lambda: _make_lgbm(random_state)))
    if XGBRegressor is not None:
        candidates.append(("xgboost", lambda: _make_xgb(random_state)))
    if CatBoostRegressor is not None:
        candidates.append(("catboost", lambda: _make_catboost(random_state)))
    return candidates


def select_best_model(
    candidates: list[tuple[str, callable]],
    X_train, y_train,
    X_val, y_val,
    metric: str = "mae",
    sample_weight=None,
) -> tuple[str, object, dict[str, float]]:
    """Train all candidates and select the best based on validation metric.

    Args:
        candidates: List of (name, builder_fn) tuples.
        X_train: Training features.
        y_train: Training targets.
        X_val: Validation features.
        y_val: Validation targets.
        metric: Primary metric for selection ("mae", "rmse", "r2").
        sample_weight: Optional training sample weights.

    Returns:
        Tuple of (best_name, best_fitted_model, all_metrics_dict).
    """
    from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
    from scipy.stats import spearmanr

    lower_is_better = {"mae", "rmse", "brier"}
    results = []

    for name, builder in candidates:
        try:
            model = builder()
            fit_kw = {}
            if sample_weight is not None:
                fit_kw["sample_weight"] = sample_weight
            model.fit(X_train, y_train, **fit_kw)
            preds = model.predict(X_val)

            mae = float(mean_absolute_error(y_val, preds))
            rmse = float(np.sqrt(mean_squared_error(y_val, preds)))
            r2 = float(r2_score(y_val, preds))

            y_val_arr = np.asarray(y_val).ravel()
            preds_arr = np.asarray(preds).ravel()
            if len(y_val_arr) > 2:
                sp_corr, _ = spearmanr(y_val_arr, preds_arr)
                sp = float(sp_corr) if np.isfinite(sp_corr) else 0.0
            else:
                sp = 0.0

            metrics = {"mae": mae, "rmse": rmse, "r2": r2, "spearman": sp}
            results.append((name, model, metrics))
            logger.info(
                "  %s: MAE=%.4f, RMSE=%.4f, R²=%.4f, Spearman=%.4f",
                name, mae, rmse, r2, sp,
            )
        except Exception as exc:
            logger.warning("  %s failed: %s", name, exc)

    if not results:
        raise RuntimeError("All candidate models failed during selection.")

    # Sort by primary metric
    if metric in lower_is_better:
        results.sort(key=lambda r: r[2].get(metric, float("inf")))
    else:
        results.sort(key=lambda r: -r[2].get(metric, float("-inf")))

    best_name, best_model, best_metrics = results[0]
    logger.info("Selected best model: '%s' (%s=%.4f).", best_name, metric, best_metrics[metric])

    all_metrics = {name: m for name, _, m in results}
    return best_name, best_model, all_metrics


import numpy as np
