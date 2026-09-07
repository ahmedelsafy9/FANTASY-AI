"""Upper-tail quantile regression for player ceiling estimation (Feedback 5).

Predicts quantiles (e.g. 0.75, 0.85, 0.90) to decompress the predicted
distribution and estimate the explosive scoring ceiling of players without
distorting the conditional mean.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor

try:
    from lightgbm import LGBMRegressor
except ImportError:
    LGBMRegressor = None

from src.config.logging_config import get_logger

logger = get_logger(__name__)

DEFAULT_QUANTILES = (0.75, 0.85, 0.90)


@dataclass
class QuantileModelResult:
    """Trained model and metadata for a specific quantile."""
    quantile: float
    model_name: str
    model: object
    feature_cols: list[str] = field(default_factory=list)
    train_medians: dict = field(default_factory=dict)
    pinball_loss: float = 0.0


def pinball_loss(y_true: np.ndarray, y_pred: np.ndarray, q: float) -> float:
    """Compute average pinball (quantile) loss."""
    diff = y_true - y_pred
    return float(np.mean(np.maximum(q * diff, (q - 1.0) * diff)))


def build_quantile_estimator(
    quantile: float,
    random_state: int = 42,
) -> tuple[str, object]:
    """Build a quantile regressor using LightGBM or HistGBM fallback."""
    if LGBMRegressor is not None:
        model = LGBMRegressor(
            objective="quantile",
            alpha=quantile,
            n_estimators=100,
            max_depth=6,
            learning_rate=0.05,
            random_state=random_state,
            n_jobs=4,
            verbosity=-1,
        )
        return "lightgbm", model

    model = HistGradientBoostingRegressor(
        loss="quantile",
        quantile=quantile,
        max_iter=100,
        max_depth=6,
        learning_rate=0.05,
        random_state=random_state,
    )
    return "histgbm", model


def train_quantile_models(
    df: pd.DataFrame,
    feature_cols: list[str],
    target_col: str = "total_points",
    quantiles: tuple[float, ...] = DEFAULT_QUANTILES,
    random_state: int = 42,
    sample_weight: np.ndarray | None = None,
) -> dict[float, QuantileModelResult]:
    """Train quantile regression models for each requested quantile.

    Args:
        df: Training DataFrame.
        feature_cols: List of features.
        target_col: Points target column.
        quantiles: Tuple of float quantiles in (0, 1).
        random_state: Random seed.
        sample_weight: Optional recency weights.

    Returns:
        dict[float, QuantileModelResult]: Models keyed by quantile.
    """
    avail = [c for c in feature_cols if c in df.columns]
    working = df.dropna(subset=[target_col]).sort_values(["season", "GW"]).reset_index(drop=True)

    X = working[avail].apply(pd.to_numeric, errors="coerce")
    medians = X.median().to_dict()
    X = X.fillna(medians).fillna(0)
    y = pd.to_numeric(working[target_col], errors="coerce").fillna(0).values

    results = {}
    for q in quantiles:
        logger.info("Training upper-tail quantile regressor for Q=%.2f...", q)
        name, model = build_quantile_estimator(q, random_state)

        fit_kw = {}
        if sample_weight is not None:
            fit_kw["sample_weight"] = sample_weight

        model.fit(X, y, **fit_kw)
        preds = model.predict(X)
        loss = pinball_loss(y, preds, q)

        results[q] = QuantileModelResult(
            quantile=q,
            model_name=name,
            model=model,
            feature_cols=avail,
            train_medians=medians,
            pinball_loss=loss,
        )
        logger.info("  Q=%.2f [%s] fitted (pinball_loss: %.4f).", q, name, loss)

    return results


def predict_quantiles(
    models: dict[float, QuantileModelResult],
    df: pd.DataFrame,
) -> pd.DataFrame:
    """Predict ceiling quantiles and enforce non-crossing monotonicity.

    Args:
        models: Dictionary of QuantileModelResult.
        df: DataFrame to predict on.

    Returns:
        pd.DataFrame: Columns 'pred_q_{int(q*100)}' for each quantile.
    """
    q_df = pd.DataFrame(index=df.index)
    sorted_qs = sorted(models.keys())

    for q in sorted_qs:
        res = models[q]
        avail = [c for c in res.feature_cols if c in df.columns]
        X = df[avail].apply(pd.to_numeric, errors="coerce").fillna(res.train_medians).fillna(0)
        preds = res.model.predict(X)
        q_df[f"pred_q_{int(q * 100)}"] = preds

    # Monotonicity check & enforcement: Q_lower <= Q_higher
    for i in range(1, len(sorted_qs)):
        prev_col = f"pred_q_{int(sorted_qs[i-1] * 100)}"
        curr_col = f"pred_q_{int(sorted_qs[i] * 100)}"
        q_df[curr_col] = np.maximum(q_df[curr_col], q_df[prev_col])

    return q_df
