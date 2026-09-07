"""Hurdle Two-Stage model separating participation from point magnitude (Feedback 5).

Structure:
  Stage 1: P(meaningful appearance / points > 0) [Classifier]
  Stage 2: E(points | points > 0) [Regressor]
  Combined: E(points) = P(active) * E(points | active)
"""

from __future__ import annotations

from dataclasses import dataclass, field
import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier, HistGradientBoostingRegressor

try:
    from xgboost import XGBClassifier, XGBRegressor
except ImportError:
    XGBClassifier = None
    XGBRegressor = None

from src.config.logging_config import get_logger

logger = get_logger(__name__)


@dataclass
class HurdleModelResult:
    """Trained hurdle two-stage model."""
    classifier_name: str
    classifier: object
    regressor_name: str
    regressor: object
    feature_cols: list[str] = field(default_factory=list)
    train_medians: dict = field(default_factory=dict)


def train_hurdle_model(
    df: pd.DataFrame,
    feature_cols: list[str],
    target_col: str = "total_points",
    random_state: int = 42,
    sample_weight: np.ndarray | None = None,
) -> HurdleModelResult:
    """Train the two-stage hurdle model.

    Args:
        df: Training DataFrame.
        feature_cols: Feature columns.
        target_col: Points target.
        random_state: Random seed.
        sample_weight: Optional recency weights.

    Returns:
        HurdleModelResult with fitted Stage 1 and Stage 2 models.
    """
    avail = [c for c in feature_cols if c in df.columns]
    working = df.dropna(subset=[target_col]).sort_values(["season", "GW"]).reset_index(drop=True)

    X = working[avail].apply(pd.to_numeric, errors="coerce")
    medians = X.median().to_dict()
    X = X.fillna(medians).fillna(0)
    y = pd.to_numeric(working[target_col], errors="coerce").fillna(0).values

    # Stage 1: P(points > 0)
    y_active = (y > 0).astype(int)
    logger.info(
        "Stage 1: Fitting participation classifier (%d positive / %d total)...",
        y_active.sum(), len(y_active),
    )

    if XGBClassifier is not None:
        cls_name = "xgboost"
        cls_model = XGBClassifier(
            n_estimators=100, max_depth=5, learning_rate=0.05,
            random_state=random_state, n_jobs=4, eval_metric="logloss",
        )
    else:
        cls_name = "histgbm"
        cls_model = HistGradientBoostingClassifier(
            max_iter=100, max_depth=5, learning_rate=0.05, random_state=random_state,
        )

    fit_kw_cls = {}
    if sample_weight is not None:
        fit_kw_cls["sample_weight"] = sample_weight
    cls_model.fit(X, y_active, **fit_kw_cls)

    # Stage 2: E(points | points > 0)
    active_mask = y > 0
    X_act = X.loc[active_mask]
    y_act = y[active_mask]
    sw_act = sample_weight[active_mask] if sample_weight is not None else None

    logger.info("Stage 2: Fitting conditional points regressor on %d active rows...", len(X_act))

    if XGBRegressor is not None:
        reg_name = "xgboost"
        reg_model = XGBRegressor(
            n_estimators=100, max_depth=6, learning_rate=0.05,
            random_state=random_state, n_jobs=4,
        )
    else:
        reg_name = "histgbm"
        reg_model = HistGradientBoostingRegressor(
            max_iter=100, max_depth=6, learning_rate=0.05, random_state=random_state,
        )

    fit_kw_reg = {}
    if sw_act is not None:
        fit_kw_reg["sample_weight"] = sw_act
    reg_model.fit(X_act, y_act, **fit_kw_reg)

    logger.info("Hurdle Two-Stage model trained successfully.")

    return HurdleModelResult(
        classifier_name=cls_name,
        classifier=cls_model,
        regressor_name=reg_name,
        regressor=reg_model,
        feature_cols=avail,
        train_medians=medians,
    )


def predict_hurdle(
    hurdle_result: HurdleModelResult,
    df: pd.DataFrame,
) -> np.ndarray:
    """Predict expected points using the hurdle two-stage model.

    Args:
        hurdle_result: Trained HurdleModelResult.
        df: DataFrame to predict on.

    Returns:
        np.ndarray: Combined predictions = P(active) * max(0, E(points | active)).
    """
    avail = [c for c in hurdle_result.feature_cols if c in df.columns]
    X = df[avail].apply(pd.to_numeric, errors="coerce").fillna(hurdle_result.train_medians).fillna(0)

    # Stage 1: P(active)
    if hasattr(hurdle_result.classifier, "predict_proba"):
        p_active = hurdle_result.classifier.predict_proba(X)[:, 1]
    else:
        p_active = np.clip(hurdle_result.classifier.predict(X), 0.0, 1.0)

    # Stage 2: E(points | active)
    e_conditional = hurdle_result.regressor.predict(X)
    e_conditional = np.maximum(0.0, e_conditional)

    return p_active * e_conditional
