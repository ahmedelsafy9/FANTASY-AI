"""Supervised classifiers for the differential prediction layer.

Architectures:
    1. Single-Threshold Classifier: P(total_points >= 8)
    2. Multi-Threshold Classifiers: P(6+), P(8+), P(10+), P(12+) with monotonicity
    3. Breakout Classifier: P(total_points >= total_points_avg_last_5 + delta)

Reuses the project's proven ML candidates (LightGBM, XGBoost, CatBoost, HistGBM,
RandomForest) with probability calibration and strict ranking evaluation.
"""

from __future__ import annotations

from pathlib import Path
import joblib
import numpy as np
import pandas as pd
from sklearn.calibration import CalibratedClassifierCV
from sklearn.metrics import average_precision_score, roc_auc_score

from src.config.logging_config import get_logger
from src.high_score.classifier import build_classifier_candidates
from src.differential.evaluation import evaluate_per_gameweek
from src.differential.models import DifferentialMetrics, DifferentialModelResult

logger = get_logger(__name__)


def prepare_differential_matrix(
    df: pd.DataFrame,
    feature_cols: list[str],
    train_medians: dict[str, float] | None = None,
) -> tuple[np.ndarray, dict[str, float]]:
    """Convert dataframe feature columns into an imputed numpy array.

    Args:
        df: Input DataFrame.
        feature_cols: List of column names to extract.
        train_medians: Optional precomputed medians from training split.

    Returns:
        tuple[np.ndarray, dict[str, float]]: (X array, medians dict)
    """
    if train_medians is None:
        computed_medians = {}
        for c in feature_cols:
            if c in df.columns:
                series = pd.to_numeric(df[c], errors="coerce")
                med = float(series.median()) if not np.isnan(series.median()) else 0.0
                computed_medians[c] = med
            else:
                computed_medians[c] = 0.0
        train_medians = computed_medians

    X_list = []
    for c in feature_cols:
        if c in df.columns:
            s = pd.to_numeric(df[c], errors="coerce").fillna(train_medians.get(c, 0.0))
            X_list.append(s.values)
        else:
            X_list.append(np.full(len(df), train_medians.get(c, 0.0)))

    X = np.column_stack(X_list) if X_list else np.empty((len(df), 0))
    return np.nan_to_num(X, nan=0.0, posinf=0.0, neginf=0.0), train_medians


def enforce_probability_monotonicity(
    probs_dict: dict[int, np.ndarray],
    thresholds: tuple[int, ...] = (6, 8, 10, 12),
) -> dict[int, np.ndarray]:
    """Enforce P(6+) >= P(8+) >= P(10+) >= P(12+) across probability arrays.

    Uses cumulative minimum across ascending thresholds so higher point targets
    cannot have higher predicted probability than lower point targets.

    Args:
        probs_dict: Mapping of threshold -> 1D numpy array of probabilities.
        thresholds: Ordered sequence of thresholds.

    Returns:
        dict[int, np.ndarray]: Monotonically consistent probabilities.
    """
    sorted_thresh = sorted(thresholds)
    prob_matrix = np.column_stack([probs_dict[t] for t in sorted_thresh])
    # prob_matrix[:, 0] is smallest threshold (e.g. 6), prob_matrix[:, -1] is largest (12)
    # P(6) >= P(8) >= P(10) >= P(12)
    # np.minimum.accumulate along axis 1 enforces each column <= previous column
    monotonic_matrix = np.minimum.accumulate(prob_matrix, axis=1)

    return {t: np.clip(monotonic_matrix[:, idx], 0.0, 1.0) for idx, t in enumerate(sorted_thresh)}


def train_single_threshold_classifier(
    train_df: pd.DataFrame,
    val_df: pd.DataFrame,
    feature_cols: list[str],
    threshold: int = 8,
    target_col: str = "total_points",
    random_state: int = 42,
) -> DifferentialModelResult:
    """Train candidate models on binary target (total_points >= threshold) and select the best.

    Args:
        train_df: Chronological training DataFrame.
        val_df: Chronological validation DataFrame.
        feature_cols: List of safe feature columns.
        threshold: Score threshold (default 8).
        target_col: Outcome column.
        random_state: Random seed.

    Returns:
        DifferentialModelResult: Best calibrated model and metrics.
    """
    logger.info("Training single-threshold differential classifier for threshold >= %d", threshold)

    y_train_pts = pd.to_numeric(train_df[target_col], errors="coerce").fillna(0).values
    y_train = (y_train_pts >= threshold).astype(int)

    y_val_pts = pd.to_numeric(val_df[target_col], errors="coerce").fillna(0).values
    y_val = (y_val_pts >= threshold).astype(int)

    n_pos = int(y_train.sum())
    n_neg = len(y_train) - n_pos
    pos_ratio = n_pos / max(len(y_train), 1)
    scale_pos_weight = n_neg / max(n_pos, 1) if n_pos > 0 else 1.0
    logger.info("Train positive rate for >= %d: %.2f%% (n_pos=%d, n_neg=%d)",
                threshold, pos_ratio * 100, n_pos, n_neg)

    X_train, train_medians = prepare_differential_matrix(train_df, feature_cols)
    X_val, _ = prepare_differential_matrix(val_df, feature_cols, train_medians=train_medians)

    candidates = build_classifier_candidates(random_state=random_state, scale_pos_weight=scale_pos_weight)

    best_name = ""
    best_model = None
    best_pr_auc = -1.0
    candidate_metrics: dict[str, dict] = {}

    for name, builder in candidates:
        try:
            base_model = builder()
            # Wrap in calibration if appropriate
            calibrated = CalibratedClassifierCV(estimator=base_model, cv=3, method="sigmoid")
            calibrated.fit(X_train, y_train)

            # Predict probabilities
            y_prob_val = calibrated.predict_proba(X_val)[:, 1]

            val_pr_auc = float(average_precision_score(y_val, y_prob_val)) if y_val.sum() > 0 else 0.0
            val_roc_auc = float(roc_auc_score(y_val, y_prob_val)) if y_val.sum() > 0 else 0.0

            candidate_metrics[name] = {
                "pr_auc": round(val_pr_auc, 4),
                "roc_auc": round(val_roc_auc, 4),
            }
            logger.info("Candidate %s: PR-AUC=%.4f, ROC-AUC=%.4f", name, val_pr_auc, val_roc_auc)

            if val_pr_auc > best_pr_auc:
                best_pr_auc = val_pr_auc
                best_name = name
                best_model = calibrated
        except Exception as exc:
            logger.warning("Error training candidate %s: %s", name, exc)

    if best_model is None:
        raise RuntimeError("Failed to train any differential classifier candidates.")

    # Evaluate best model with per-gameweek ranking metrics
    val_scored = val_df.copy()
    val_scored["model_score"] = best_model.predict_proba(X_val)[:, 1]
    metrics = evaluate_per_gameweek(
        name=f"Model_Single_Threshold_{threshold}_{best_name}",
        df=val_scored,
        score_col="model_score",
        target_col=target_col,
        threshold=threshold,
    )

    return DifferentialModelResult(
        model_name=best_name,
        model_type="single_threshold",
        model=best_model,
        feature_cols=feature_cols,
        train_medians=train_medians,
        threshold=threshold,
        metrics=metrics,
        all_candidate_metrics=candidate_metrics,
    )


def train_multi_threshold_classifiers(
    train_df: pd.DataFrame,
    val_df: pd.DataFrame,
    feature_cols: list[str],
    thresholds: tuple[int, ...] = (6, 8, 10, 12),
    target_col: str = "total_points",
    random_state: int = 42,
) -> dict[int, DifferentialModelResult]:
    """Train separate classifiers for multiple thresholds and ensure monotonicity.

    Args:
        train_df: Chronological training DataFrame.
        val_df: Chronological validation DataFrame.
        feature_cols: Feature columns list.
        thresholds: Point thresholds (e.g. 6, 8, 10, 12).
        target_col: Outcome column.
        random_state: Random seed.

    Returns:
        dict[int, DifferentialModelResult]: Mapping from threshold -> model result.
    """
    results: dict[int, DifferentialModelResult] = {}
    val_probs: dict[int, np.ndarray] = {}

    for th in thresholds:
        res = train_single_threshold_classifier(
            train_df=train_df,
            val_df=val_df,
            feature_cols=feature_cols,
            threshold=th,
            target_col=target_col,
            random_state=random_state,
        )
        res.model_type = "multi_threshold"
        results[th] = res

        X_val, _ = prepare_differential_matrix(val_df, feature_cols, train_medians=res.train_medians)
        val_probs[th] = res.model.predict_proba(X_val)[:, 1]

    # Enforce monotonicity on validation predictions
    mono_probs = enforce_probability_monotonicity(val_probs, thresholds=thresholds)

    # Re-evaluate with monotonic probabilities
    val_scored = val_df.copy()
    for th in thresholds:
        val_scored[f"p_{th}_plus_monotonic"] = mono_probs[th]
        results[th].metrics = evaluate_per_gameweek(
            name=f"Model_Multi_Threshold_{th}_{results[th].model_name}_monotonic",
            df=val_scored,
            score_col=f"p_{th}_plus_monotonic",
            target_col=target_col,
            threshold=th,
        )

    return results


def train_breakout_classifier(
    train_df: pd.DataFrame,
    val_df: pd.DataFrame,
    feature_cols: list[str],
    breakout_delta: float = 4.0,
    baseline_col: str = "total_points_avg_last_5",
    target_col: str = "total_points",
    random_state: int = 42,
) -> DifferentialModelResult:
    """Train a classifier targeting personal breakout (total_points >= baseline + delta).

    Args:
        train_df: Chronological training DataFrame.
        val_df: Chronological validation DataFrame.
        feature_cols: Feature columns list.
        breakout_delta: Points above baseline defining a breakout (default 4.0).
        baseline_col: Player form baseline column.
        target_col: Actual points column.
        random_state: Random seed.

    Returns:
        DifferentialModelResult: Best breakout classifier and metrics.
    """
    logger.info("Training breakout classifier (target: %s >= %s + %.1f)",
                target_col, baseline_col, breakout_delta)

    # Construct relative target
    train_df_copy = train_df.copy()
    val_df_copy = val_df.copy()

    train_base = pd.to_numeric(train_df_copy.get(baseline_col), errors="coerce").fillna(0)
    val_base = pd.to_numeric(val_df_copy.get(baseline_col), errors="coerce").fillna(0)

    train_y = pd.to_numeric(train_df_copy[target_col], errors="coerce").fillna(0)
    val_y = pd.to_numeric(val_df_copy[target_col], errors="coerce").fillna(0)

    train_df_copy["_breakout_target"] = (train_y >= (train_base + breakout_delta)).astype(int)
    val_df_copy["_breakout_target"] = (val_y >= (val_base + breakout_delta)).astype(int)

    res = train_single_threshold_classifier(
        train_df=train_df_copy,
        val_df=val_df_copy,
        feature_cols=feature_cols,
        threshold=1,
        target_col="_breakout_target",
        random_state=random_state,
    )
    res.model_type = "breakout"
    return res


def save_differential_model(
    result: DifferentialModelResult,
    output_path: str | Path,
) -> None:
    """Save differential model artifact to disk."""
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "model_name": result.model_name,
        "model_type": result.model_type,
        "model": result.model,
        "feature_cols": result.feature_cols,
        "train_medians": result.train_medians,
        "threshold": result.threshold,
        "metrics": result.metrics.to_dict() if result.metrics else None,
        "all_candidate_metrics": result.all_candidate_metrics,
    }
    joblib.dump(payload, path)
    logger.info("Saved differential model artifact to %s", path)


def load_differential_model(model_path: str | Path) -> DifferentialModelResult:
    """Load differential model artifact from disk."""
    path = Path(model_path)
    if not path.exists():
        raise FileNotFoundError(f"Differential model file not found: {path}")
    payload = joblib.load(path)
    metrics = None
    if payload.get("metrics"):
        m_dict = payload["metrics"]
        valid_keys = {f.name for f in DifferentialMetrics.__dataclass_fields__.values()}
        metrics = DifferentialMetrics(**{k: v for k, v in m_dict.items() if k in valid_keys})

    return DifferentialModelResult(
        model_name=payload.get("model_name", ""),
        model_type=payload.get("model_type", ""),
        model=payload.get("model"),
        feature_cols=payload.get("feature_cols", []),
        train_medians=payload.get("train_medians", {}),
        threshold=payload.get("threshold", 8),
        metrics=metrics,
        all_candidate_metrics=payload.get("all_candidate_metrics", {}),
    )
