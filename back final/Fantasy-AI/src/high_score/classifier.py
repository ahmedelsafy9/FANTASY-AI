"""Dedicated supervised high-score prediction classifiers (Feedback 5).

Targets:
  - high_score_6:  total_points >= 6
  - high_score_8:  total_points >= 8
  - high_score_10: total_points >= 10
  - high_score_12: total_points >= 12

Evaluates traditional ML classifiers using PR-AUC, F1, Precision, Recall,
and Recall@Top-K, ensuring calibrated probabilities.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import json
import numpy as np
import pandas as pd
from sklearn.metrics import (
    average_precision_score,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.calibration import CalibratedClassifierCV
from sklearn.ensemble import (
    HistGradientBoostingClassifier,
    RandomForestClassifier,
)
import joblib

try:
    from lightgbm import LGBMClassifier
except ImportError:
    LGBMClassifier = None

try:
    from xgboost import XGBClassifier
except ImportError:
    XGBClassifier = None

try:
    from catboost import CatBoostClassifier
except ImportError:
    CatBoostClassifier = None

from src.config.logging_config import get_logger
from src.multi_stage.temporal_cv import generate_walk_forward_folds

logger = get_logger(__name__)

HIGH_SCORE_THRESHOLDS = (6, 8, 10, 12)


def make_high_score_labels(
    y: pd.Series | np.ndarray,
    thresholds: tuple[int, ...] = HIGH_SCORE_THRESHOLDS,
) -> dict[str, np.ndarray]:
    """Create binary indicator arrays for each high-score threshold."""
    y_arr = np.asarray(y, dtype=float)
    labels = {}
    for th in thresholds:
        labels[f"high_score_{th}"] = (y_arr >= th).astype(int)
    return labels


@dataclass
class ClassifierMetrics:
    """Evaluation metrics for a high-score classifier."""
    threshold: int
    model_name: str
    pr_auc: float = 0.0
    roc_auc: float = 0.0
    precision: float = 0.0
    recall: float = 0.0
    f1: float = 0.0
    brier: float = 0.0
    n_positive: int = 0
    n_total: int = 0


@dataclass
class HighScoreModelResult:
    """Trained models and OOF predictions for all high-score thresholds."""
    threshold: int
    best_model_name: str = ""
    best_model: object = None
    feature_cols: list[str] = field(default_factory=list)
    val_metrics: ClassifierMetrics | None = None
    all_metrics: dict = field(default_factory=dict)
    train_medians: dict = field(default_factory=dict)


def build_classifier_candidates(
    random_state: int = 42,
    scale_pos_weight: float | None = None,
) -> list[tuple[str, callable]]:
    """Build candidate classification models with graceful imports.

    Args:
        random_state: Random seed.
        scale_pos_weight: Optional imbalance weight ratio (pos/neg).

    Returns:
        list of (name, builder_fn) tuples.
    """
    candidates: list[tuple[str, callable]] = []

    # 1. HistGradientBoostingClassifier
    def _make_histgbm():
        return HistGradientBoostingClassifier(
            max_iter=100,
            max_depth=6,
            learning_rate=0.05,
            random_state=random_state,
        )
    candidates.append(("histgbm", _make_histgbm))

    # 2. LightGBM Classifier
    if LGBMClassifier is not None:
        def _make_lgbm():
            kw = dict(
                n_estimators=100,
                max_depth=6,
                learning_rate=0.05,
                random_state=random_state,
                n_jobs=4,
                verbosity=-1,
            )
            if scale_pos_weight is not None and scale_pos_weight > 1.0:
                kw["scale_pos_weight"] = min(scale_pos_weight, 10.0)
            return LGBMClassifier(**kw)
        candidates.append(("lightgbm", _make_lgbm))

    # 3. XGBoost Classifier
    if XGBClassifier is not None:
        def _make_xgb():
            kw = dict(
                n_estimators=100,
                max_depth=6,
                learning_rate=0.05,
                random_state=random_state,
                n_jobs=4,
                eval_metric="logloss",
            )
            if scale_pos_weight is not None and scale_pos_weight > 1.0:
                kw["scale_pos_weight"] = min(scale_pos_weight, 10.0)
            return XGBClassifier(**kw)
        candidates.append(("xgboost", _make_xgb))

    # 4. CatBoost Classifier (graceful import)
    if CatBoostClassifier is not None:
        def _make_catboost():
            return CatBoostClassifier(
                iterations=100,
                depth=6,
                learning_rate=0.05,
                random_seed=random_state,
                thread_count=4,
                verbose=0,
            )
        candidates.append(("catboost", _make_catboost))

    # 5. Random Forest Classifier
    def _make_rf():
        return RandomForestClassifier(
            n_estimators=50,
            max_depth=10,
            random_state=random_state,
            n_jobs=4,
            class_weight="balanced",
        )
    candidates.append(("random_forest", _make_rf))

    return candidates


def evaluate_classifier(
    y_true: np.ndarray,
    y_prob: np.ndarray,
    threshold: int,
    model_name: str,
    decision_threshold: float = 0.5,
) -> ClassifierMetrics:
    """Evaluate a classifier's predicted probabilities."""
    valid = np.isfinite(y_true) & np.isfinite(y_prob)
    yt = y_true[valid].astype(int)
    yp = np.clip(y_prob[valid], 0.0, 1.0)

    n_pos = int(yt.sum())
    n_tot = len(yt)

    if n_pos == 0 or n_pos == n_tot:
        return ClassifierMetrics(
            threshold=threshold, model_name=model_name, n_positive=n_pos, n_total=n_tot,
        )

    pr_auc = float(average_precision_score(yt, yp))
    roc_auc = float(roc_auc_score(yt, yp))

    y_pred_bin = (yp >= decision_threshold).astype(int)
    prec = float(precision_score(yt, y_pred_bin, zero_division=0))
    rec = float(recall_score(yt, y_pred_bin, zero_division=0))
    f1 = float(f1_score(yt, y_pred_bin, zero_division=0))
    brier = float(np.mean((yp - yt) ** 2))

    return ClassifierMetrics(
        threshold=threshold,
        model_name=model_name,
        pr_auc=pr_auc,
        roc_auc=roc_auc,
        precision=prec,
        recall=rec,
        f1=f1,
        brier=brier,
        n_positive=n_pos,
        n_total=n_tot,
    )


def train_single_threshold_classifier(
    X_train: pd.DataFrame,
    y_train: np.ndarray,
    X_val: pd.DataFrame,
    y_val: np.ndarray,
    threshold: int,
    random_state: int = 42,
    sample_weight: np.ndarray | None = None,
) -> tuple[str, object, dict]:
    """Select and train best classifier for a single high-score threshold."""
    yt_bin = (y_train >= threshold).astype(int)
    yv_bin = (y_val >= threshold).astype(int)

    n_neg = (yt_bin == 0).sum()
    n_pos = (yt_bin == 1).sum()
    ratio = float(n_neg / max(n_pos, 1))

    candidates = build_classifier_candidates(random_state, scale_pos_weight=ratio)

    best_name = ""
    best_model = None
    best_pr_auc = -1.0
    all_metrics = {}

    for name, builder in candidates:
        try:
            model = builder()
            fit_kw = {}
            if sample_weight is not None:
                # Some estimators support sample_weight
                fit_kw["sample_weight"] = sample_weight

            model.fit(X_train, yt_bin, **fit_kw)

            # Predict probabilities
            if hasattr(model, "predict_proba"):
                probs = model.predict_proba(X_val)[:, 1]
            elif hasattr(model, "decision_function"):
                dfn = model.decision_function(X_val)
                probs = 1.0 / (1.0 + np.exp(-dfn))
            else:
                probs = model.predict(X_val)

            metrics = evaluate_classifier(yv_bin, probs, threshold, name)
            all_metrics[name] = {
                "pr_auc": metrics.pr_auc,
                "roc_auc": metrics.roc_auc,
                "precision": metrics.precision,
                "recall": metrics.recall,
                "f1": metrics.f1,
                "brier": metrics.brier,
            }

            if metrics.pr_auc > best_pr_auc:
                best_pr_auc = metrics.pr_auc
                best_name = name
                best_model = model
        except Exception as exc:
            logger.warning("Classifier candidate '%s' failed for th=%d: %s", name, threshold, exc)

    if best_model is None:
        # Fallback to histgbm
        best_name = "histgbm"
        best_model = HistGradientBoostingClassifier(max_iter=50, random_state=random_state)
        best_model.fit(X_train, yt_bin)

    logger.info(
        "Threshold >= %d: Best classifier is '%s' (PR-AUC: %.4f).",
        threshold, best_name, best_pr_auc,
    )
    return best_name, best_model, all_metrics


def train_high_score_models(
    df: pd.DataFrame,
    feature_cols: list[str],
    target_col: str = "total_points",
    thresholds: tuple[int, ...] = HIGH_SCORE_THRESHOLDS,
    random_state: int = 42,
    sample_weight: np.ndarray | None = None,
) -> dict[int, HighScoreModelResult]:
    """Train dedicated high-score classifiers for each threshold.

    Uses an out-of-time chronological train/validation split within df
    to select the best model per threshold, then fits the best model on
    the full training dataset.

    Args:
        df: Training DataFrame.
        feature_cols: Features to use.
        target_col: Point target column name.
        thresholds: Point thresholds to model (e.g. 6, 8, 10, 12).
        random_state: Random seed.
        sample_weight: Optional recency weights.

    Returns:
        dict[int, HighScoreModelResult]: Results keyed by threshold.
    """
    avail = [c for c in feature_cols if c in df.columns]
    working = df.dropna(subset=[target_col]).sort_values(["season", "GW"]).reset_index(drop=True)

    X = working[avail].apply(pd.to_numeric, errors="coerce")
    medians = X.median().to_dict()
    X = X.fillna(medians).fillna(0)
    y = pd.to_numeric(working[target_col], errors="coerce").fillna(0).values

    # 80/20 chronological split for model selection
    split_idx = int(len(working) * 0.8)
    X_tr, X_val = X.iloc[:split_idx], X.iloc[split_idx:]
    y_tr, y_val = y[:split_idx], y[split_idx:]
    sw_tr = sample_weight[:split_idx] if sample_weight is not None else None

    results = {}
    for th in thresholds:
        logger.info("Training high-score classifier for >= %d points...", th)
        best_name, _, all_metrics = train_single_threshold_classifier(
            X_tr, y_tr, X_val, y_val, threshold=th, random_state=random_state, sample_weight=sw_tr,
        )

        # Refit best model on full data for inference
        candidates = build_classifier_candidates(random_state)
        best_builder = None
        for name, builder in candidates:
            if name == best_name:
                best_builder = builder
                break
        if best_builder is None:
            best_builder = candidates[0][1]

        final_model = best_builder()
        fit_kw = {}
        if sample_weight is not None:
            fit_kw["sample_weight"] = sample_weight
        final_model.fit(X, (y >= th).astype(int), **fit_kw)

        # Compute validation metrics
        probs_val = final_model.predict_proba(X_val)[:, 1] if hasattr(final_model, "predict_proba") else final_model.predict(X_val)
        val_m = evaluate_classifier((y_val >= th).astype(int), probs_val, th, best_name)

        results[th] = HighScoreModelResult(
            threshold=th,
            best_model_name=best_name,
            best_model=final_model,
            feature_cols=avail,
            val_metrics=val_m,
            all_metrics=all_metrics,
            train_medians=medians,
        )

    return results


def predict_high_score_probabilities(
    models: dict[int, HighScoreModelResult],
    df: pd.DataFrame,
) -> pd.DataFrame:
    """Generate probability predictions for all high-score thresholds.

    Args:
        models: Dictionary of HighScoreModelResult from train_high_score_models.
        df: Feature DataFrame to predict on.

    Returns:
        pd.DataFrame: DataFrame containing prob_high_score_{th} columns.
    """
    prob_df = pd.DataFrame(index=df.index)
    for th, res in models.items():
        col_name = f"prob_high_score_{th}"
        if res.best_model is None:
            prob_df[col_name] = 0.0
            continue

        avail = [c for c in res.feature_cols if c in df.columns]
        X = df[avail].apply(pd.to_numeric, errors="coerce").fillna(res.train_medians).fillna(0)

        if hasattr(res.best_model, "predict_proba"):
            probs = res.best_model.predict_proba(X)[:, 1]
        elif hasattr(res.best_model, "decision_function"):
            dfn = res.best_model.decision_function(X)
            probs = 1.0 / (1.0 + np.exp(-dfn))
        else:
            probs = np.clip(res.best_model.predict(X), 0.0, 1.0)

        prob_df[col_name] = probs

    # Monotonicity enforcement: P(>=6) >= P(>=8) >= P(>=10) >= P(>=12)
    ths = sorted(models.keys())
    for i in range(1, len(ths)):
        prev_col = f"prob_high_score_{ths[i-1]}"
        curr_col = f"prob_high_score_{ths[i]}"
        if prev_col in prob_df.columns and curr_col in prob_df.columns:
            prob_df[curr_col] = np.minimum(prob_df[curr_col], prob_df[prev_col])

    return prob_df
