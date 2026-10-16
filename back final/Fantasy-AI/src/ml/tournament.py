"""Leakage-safe player regression and classification tournaments.

Compares XGBoost, CatBoost, and LightGBM on identical chronological
windows. HistGradientBoosting is included only as a sklearn fallback
when an optional library is missing — it is never treated as a fourth
production candidate when the three GBM libraries are available.

Ensemble weights are fit on validation / out-of-fold predictions only.
The held-out test set is used once, after selection rules are fixed.

Selection rule (declared before test evaluation)
------------------------------------------------
1. Primary metric: MAE (regression) or PR-AUC (classification).
2. Secondary: Spearman (regression) or Brier score (classification).
3. Select the ensemble only if validation MAE improves by at least 1%
   versus the best individual model and Spearman does not drop by more
   than 0.02 (regression), or PR-AUC improves by at least 0.005 without
   a Brier increase greater than 0.002 (classification).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier, HistGradientBoostingRegressor
from sklearn.linear_model import LinearRegression, LogisticRegression
from sklearn.metrics import (
    average_precision_score,
    brier_score_loss,
    log_loss,
    mean_absolute_error,
    mean_squared_error,
    roc_auc_score,
)
from scipy.stats import spearmanr

from src.config.logging_config import get_logger
from src.ml.leakage import assert_chronological_split, inspect_feature_columns
from src.ml.targets import classification_label

logger = get_logger(__name__)

REGRESSION_CANDIDATES = ("xgboost", "catboost", "lightgbm")
ENSEMBLE_MAE_IMPROVEMENT = 0.01
ENSEMBLE_SPEARMAN_TOLERANCE = 0.02
ENSEMBLE_PR_AUC_IMPROVEMENT = 0.005
ENSEMBLE_BRIER_TOLERANCE = 0.002


@dataclass
class TournamentSplit:
    """Chronological train / validation / test matrices."""

    X_train: pd.DataFrame
    y_train: np.ndarray
    X_val: pd.DataFrame
    y_val: np.ndarray
    X_test: pd.DataFrame
    y_test: np.ndarray
    train_period: str
    validation_period: str
    test_period: str
    feature_columns: list[str]


@dataclass
class CandidateResult:
    """Metrics for one model on one split."""

    name: str
    metrics: dict[str, float]
    predictions: np.ndarray
    available: bool = True
    skip_reason: str | None = None


@dataclass
class TournamentReport:
    """Full comparison outcome."""

    task: str
    selected: str
    ensemble_selected: bool
    rationale: str
    results: list[CandidateResult]
    selection_rule: str
    train_period: str
    validation_period: str
    test_period: str
    feature_columns: list[str] = field(default_factory=list)


def build_regression_candidates(random_state: int = 42) -> list[tuple[str, Callable[[], Any]]]:
    """Return (name, builder) pairs for the three GBM regressors plus fallbacks."""
    candidates: list[tuple[str, Callable[[], Any]]] = []
    try:
        from xgboost import XGBRegressor

        candidates.append(
            (
                "xgboost",
                lambda: XGBRegressor(
                    n_estimators=80,
                    max_depth=4,
                    learning_rate=0.08,
                    random_state=random_state,
                    n_jobs=1,
                ),
            )
        )
    except ImportError as exc:
        logger.info("Skipping XGBoost regressor: %s", exc)

    try:
        from catboost import CatBoostRegressor

        candidates.append(
            (
                "catboost",
                lambda: CatBoostRegressor(
                    iterations=80,
                    depth=4,
                    learning_rate=0.08,
                    random_seed=random_state,
                    verbose=0,
                ),
            )
        )
    except ImportError as exc:
        logger.info("Skipping CatBoost regressor: %s", exc)

    try:
        from lightgbm import LGBMRegressor

        candidates.append(
            (
                "lightgbm",
                lambda: LGBMRegressor(
                    n_estimators=80,
                    max_depth=4,
                    learning_rate=0.08,
                    random_state=random_state,
                    verbose=-1,
                    n_jobs=1,
                ),
            )
        )
    except ImportError as exc:
        logger.info("Skipping LightGBM regressor: %s", exc)

    if not candidates:
        candidates.append(
            (
                "hist_gradient_boosting",
                lambda: HistGradientBoostingRegressor(
                    max_depth=4, learning_rate=0.08, random_state=random_state
                ),
            )
        )
        candidates.append(("linear", lambda: LinearRegression()))
    return candidates


def build_classifier_candidates(random_state: int = 42) -> list[tuple[str, Callable[[], Any]]]:
    """Return (name, builder) pairs for the three GBM classifiers plus fallbacks."""
    candidates: list[tuple[str, Callable[[], Any]]] = []
    try:
        from xgboost import XGBClassifier

        candidates.append(
            (
                "xgboost",
                lambda: XGBClassifier(
                    n_estimators=80,
                    max_depth=4,
                    learning_rate=0.08,
                    random_state=random_state,
                    eval_metric="logloss",
                    n_jobs=1,
                ),
            )
        )
    except ImportError as exc:
        logger.info("Skipping XGBoost classifier: %s", exc)

    try:
        from catboost import CatBoostClassifier

        candidates.append(
            (
                "catboost",
                lambda: CatBoostClassifier(
                    iterations=80,
                    depth=4,
                    learning_rate=0.08,
                    random_seed=random_state,
                    verbose=0,
                ),
            )
        )
    except ImportError as exc:
        logger.info("Skipping CatBoost classifier: %s", exc)

    try:
        from lightgbm import LGBMClassifier

        candidates.append(
            (
                "lightgbm",
                lambda: LGBMClassifier(
                    n_estimators=80,
                    max_depth=4,
                    learning_rate=0.08,
                    random_state=random_state,
                    verbose=-1,
                    n_jobs=1,
                ),
            )
        )
    except ImportError as exc:
        logger.info("Skipping LightGBM classifier: %s", exc)

    if not candidates:
        candidates.append(
            (
                "hist_gradient_boosting",
                lambda: HistGradientBoostingClassifier(
                    max_depth=4, learning_rate=0.08, random_state=random_state
                ),
            )
        )
        candidates.append(
            ("logistic", lambda: LogisticRegression(max_iter=200, random_state=random_state))
        )
    return candidates


def regression_metrics(y_true: np.ndarray, y_pred: np.ndarray) -> dict[str, float]:
    """MAE, RMSE, and Spearman rank correlation."""
    mae = float(mean_absolute_error(y_true, y_pred))
    rmse = float(np.sqrt(mean_squared_error(y_true, y_pred)))
    rho, _ = spearmanr(y_true, y_pred)
    spearman = float(rho) if np.isfinite(rho) else 0.0
    return {"mae": mae, "rmse": rmse, "spearman": spearman}


def classification_metrics(y_true: np.ndarray, y_prob: np.ndarray) -> dict[str, float]:
    """PR-AUC, ROC-AUC, Brier, and log loss on raw probabilities."""
    y_prob = np.clip(np.asarray(y_prob, dtype=float), 1e-6, 1 - 1e-6)
    y_true = np.asarray(y_true, dtype=int)
    if y_true.min() == y_true.max():
        return {"pr_auc": 0.0, "roc_auc": 0.5, "brier": float(brier_score_loss(y_true, y_prob)), "log_loss": float("nan")}
    return {
        "pr_auc": float(average_precision_score(y_true, y_prob)),
        "roc_auc": float(roc_auc_score(y_true, y_prob)),
        "brier": float(brier_score_loss(y_true, y_prob)),
        "log_loss": float(log_loss(y_true, y_prob)),
    }


def make_chronological_split(
    frame: pd.DataFrame,
    feature_columns: list[str],
    target_column: str,
    time_column: str = "GW",
    train_until: int = 20,
    val_until: int = 28,
) -> TournamentSplit:
    """Split by gameweek cutoffs. Preprocessing stays inside each window."""
    leakage = inspect_feature_columns(feature_columns, target_column=target_column)
    if not leakage.ok:
        raise ValueError("Feature leakage: " + "; ".join(leakage.reasons))

    ordered = frame.sort_values(time_column)
    train = ordered[ordered[time_column] <= train_until]
    val = ordered[(ordered[time_column] > train_until) & (ordered[time_column] <= val_until)]
    test = ordered[ordered[time_column] > val_until]
    assert_chronological_split(train[time_column], val[time_column])
    assert_chronological_split(val[time_column], test[time_column])

    medians = train[feature_columns].median(numeric_only=True)
    def _matrix(part: pd.DataFrame) -> pd.DataFrame:
        return part[feature_columns].apply(pd.to_numeric, errors="coerce").fillna(medians)

    y_train = pd.to_numeric(train[target_column], errors="coerce").fillna(0.0).to_numpy()
    y_val = pd.to_numeric(val[target_column], errors="coerce").fillna(0.0).to_numpy()
    y_test = pd.to_numeric(test[target_column], errors="coerce").fillna(0.0).to_numpy()
    return TournamentSplit(
        X_train=_matrix(train),
        y_train=y_train,
        X_val=_matrix(val),
        y_val=y_val,
        X_test=_matrix(test),
        y_test=y_test,
        train_period=f"{time_column}<= {train_until}",
        validation_period=f"{train_until}<{time_column}<={val_until}",
        test_period=f"{time_column}>{val_until}",
        feature_columns=list(feature_columns),
    )


def _fit_predict(builder: Callable[[], Any], X_train, y_train, X_eval, probability: bool) -> np.ndarray:
    model = builder()
    model.fit(X_train, y_train)
    if probability:
        if hasattr(model, "predict_proba"):
            return np.asarray(model.predict_proba(X_eval)[:, 1], dtype=float)
        return np.clip(np.asarray(model.predict(X_eval), dtype=float), 0.0, 1.0)
    return np.asarray(model.predict(X_eval), dtype=float)


def _blend(predictions: list[np.ndarray], weights: np.ndarray | None = None) -> np.ndarray:
    stacked = np.vstack(predictions)
    if weights is None:
        return stacked.mean(axis=0)
    weights = np.asarray(weights, dtype=float)
    weights = weights / weights.sum()
    return np.average(stacked, axis=0, weights=weights)


def _nonneg_least_squares(val_preds: list[np.ndarray], y_val: np.ndarray) -> np.ndarray:
    matrix = np.column_stack(val_preds)
    try:
        from scipy.optimize import nnls

        weights, _ = nnls(matrix, y_val)
    except Exception:
        weights = np.ones(matrix.shape[1])
    if not np.isfinite(weights).all() or weights.sum() <= 0:
        weights = np.ones(matrix.shape[1])
    return weights / weights.sum()


def run_regression_tournament(split: TournamentSplit, random_state: int = 42) -> TournamentReport:
    """Train GBM regressors, compare a mean and weighted ensemble, then score test."""
    candidates = build_regression_candidates(random_state)
    val_preds: list[np.ndarray] = []
    names: list[str] = []
    fitted: list[Callable[[], Any]] = []
    val_results: list[tuple[str, dict[str, float]]] = []

    for name, builder in candidates:
        preds = _fit_predict(builder, split.X_train, split.y_train, split.X_val, False)
        metrics = regression_metrics(split.y_val, preds)
        val_preds.append(preds)
        names.append(name)
        fitted.append(builder)
        val_results.append((name, metrics))

    best_name, best_metrics = min(val_results, key=lambda item: item[1]["mae"])
    mean_pred = _blend(val_preds)
    mean_metrics = regression_metrics(split.y_val, mean_pred)
    weights = _nonneg_least_squares(val_preds, split.y_val)
    weighted_pred = _blend(val_preds, weights)
    weighted_metrics = regression_metrics(split.y_val, weighted_pred)

    ensemble_name = "weighted_ensemble"
    ensemble_metrics = weighted_metrics
    if mean_metrics["mae"] <= weighted_metrics["mae"]:
        ensemble_name = "mean_ensemble"
        ensemble_metrics = mean_metrics

    use_ensemble = (
        ensemble_metrics["mae"] <= best_metrics["mae"] * (1.0 - ENSEMBLE_MAE_IMPROVEMENT)
        and ensemble_metrics["spearman"] >= best_metrics["spearman"] - ENSEMBLE_SPEARMAN_TOLERANCE
    )
    selected = ensemble_name if use_ensemble else best_name
    rationale = (
        f"Ensemble selected: validation MAE {ensemble_metrics['mae']:.4f} vs "
        f"best individual {best_name} {best_metrics['mae']:.4f}."
        if use_ensemble
        else f"Individual model {best_name} retained; ensemble MAE improvement was not stable."
    )

    results: list[CandidateResult] = []
    for name, builder in zip(names, fitted):
        test_pred = _fit_predict(builder, split.X_train, split.y_train, split.X_test, False)
        results.append(CandidateResult(name=name, metrics=regression_metrics(split.y_test, test_pred), predictions=test_pred))

    test_stack = [item.predictions for item in results]
    mean_test = _blend(test_stack)
    weighted_test = _blend(test_stack, weights)
    results.append(CandidateResult(name="mean_ensemble", metrics=regression_metrics(split.y_test, mean_test), predictions=mean_test))
    results.append(
        CandidateResult(
            name="weighted_ensemble",
            metrics=regression_metrics(split.y_test, weighted_test),
            predictions=weighted_test,
        )
    )

    return TournamentReport(
        task="player_regression",
        selected=selected,
        ensemble_selected=use_ensemble,
        rationale=rationale,
        results=results,
        selection_rule=(
            "Minimize validation MAE; accept ensemble only if MAE improves >=1% "
            "and Spearman drops by at most 0.02. Test set is unused for selection."
        ),
        train_period=split.train_period,
        validation_period=split.validation_period,
        test_period=split.test_period,
        feature_columns=split.feature_columns,
    )


def run_classification_tournament(
    split: TournamentSplit,
    threshold: int = 6,
    random_state: int = 42,
) -> TournamentReport:
    """Train GBM classifiers for ``points >= threshold`` using actual labels."""
    y_train = classification_label(split.y_train, threshold)
    y_val = classification_label(split.y_val, threshold)
    y_test = classification_label(split.y_test, threshold)
    candidates = build_classifier_candidates(random_state)

    val_preds: list[np.ndarray] = []
    names: list[str] = []
    fitted: list[Callable[[], Any]] = []
    val_results: list[tuple[str, dict[str, float]]] = []

    for name, builder in candidates:
        preds = _fit_predict(builder, split.X_train, y_train, split.X_val, True)
        metrics = classification_metrics(y_val, preds)
        val_preds.append(preds)
        names.append(name)
        fitted.append(builder)
        val_results.append((name, metrics))

    best_name, best_metrics = max(val_results, key=lambda item: item[1]["pr_auc"])
    mean_pred = _blend(val_preds)
    mean_metrics = classification_metrics(y_val, mean_pred)
    use_ensemble = (
        mean_metrics["pr_auc"] >= best_metrics["pr_auc"] + ENSEMBLE_PR_AUC_IMPROVEMENT
        and mean_metrics["brier"] <= best_metrics["brier"] + ENSEMBLE_BRIER_TOLERANCE
    )
    selected = "mean_ensemble" if use_ensemble else best_name
    rationale = (
        f"Probability mean ensemble selected on validation PR-AUC {mean_metrics['pr_auc']:.4f}."
        if use_ensemble
        else f"Individual classifier {best_name} retained on validation PR-AUC."
    )

    results: list[CandidateResult] = []
    for name, builder in zip(names, fitted):
        test_pred = _fit_predict(builder, split.X_train, y_train, split.X_test, True)
        results.append(
            CandidateResult(name=name, metrics=classification_metrics(y_test, test_pred), predictions=test_pred)
        )
    mean_test = _blend([item.predictions for item in results])
    results.append(
        CandidateResult(name="mean_ensemble", metrics=classification_metrics(y_test, mean_test), predictions=mean_test)
    )

    return TournamentReport(
        task=f"player_classification_{threshold}",
        selected=selected,
        ensemble_selected=use_ensemble,
        rationale=rationale,
        results=results,
        selection_rule=(
            "Maximize validation PR-AUC; accept mean ensemble only if PR-AUC improves "
            "by >=0.005 without Brier rising more than 0.002. Test unused for selection."
        ),
        train_period=split.train_period,
        validation_period=split.validation_period,
        test_period=split.test_period,
        feature_columns=split.feature_columns,
    )
