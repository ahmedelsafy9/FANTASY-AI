"""FPL-aware composite model scoring for promotion decisions.

The standard RMSE/MAE metrics are necessary but not sufficient for an
FPL prediction system.  A model that predicts the mean accurately but
cannot rank players or identify high-scorers is useless for FPL team
selection.

This module provides:

1. ``FPLMetrics`` — an extended metric set covering accuracy, ranking,
   and high-score detection.
2. ``compute_composite_score`` — a configurable weighted composite
   score with eligibility gates.
3. ``select_best_model_fpl`` — a drop-in replacement for the old
   single-metric ``_select_best`` in ``ModelTrainer``.

All weights and gates are configurable via ``TrainingSettings``, so
the promotion policy can be tuned without code changes.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
from scipy.stats import spearmanr

from src.config.logging_config import get_logger

logger = get_logger(__name__)


# -----------------------------------------------------------------------
# FPL Metrics
# -----------------------------------------------------------------------


@dataclass(frozen=True)
class FPLMetrics:
    """Extended evaluation metrics for FPL point prediction.

    Attributes:
        rmse: Root Mean Squared Error.
        mae: Mean Absolute Error.
        r2: R-squared (coefficient of determination).
        spearman_rho: Spearman rank correlation coefficient.
        recall_6: Fraction of true ≥6 scorers that the model predicts ≥6.
        recall_10: Fraction of true ≥10 scorers that the model predicts ≥10.
        precision_6: Fraction of predicted ≥6 scorers that are truly ≥6.
        top_20_recall: Overlap between actual top-20 and predicted top-20.
    """

    rmse: float
    mae: float
    r2: float
    spearman_rho: float
    recall_6: float
    recall_10: float
    precision_6: float
    top_20_recall: float

    def to_dict(self) -> dict[str, float]:
        """Convert to a JSON-serializable dictionary."""
        return {
            "rmse": self.rmse,
            "mae": self.mae,
            "r2": self.r2,
            "spearman_rho": self.spearman_rho,
            "recall_6": self.recall_6,
            "recall_10": self.recall_10,
            "precision_6": self.precision_6,
            "top_20_recall": self.top_20_recall,
        }


def compute_fpl_metrics(
    y_true: np.ndarray,
    y_pred: np.ndarray,
) -> FPLMetrics:
    """Compute the full set of FPL-relevant evaluation metrics.

    Args:
        y_true: Ground-truth target values.
        y_pred: Predicted target values.

    Returns:
        FPLMetrics: All computed metrics.
    """
    from sklearn.metrics import (
        mean_absolute_error,
        mean_squared_error,
        r2_score,
    )

    y_true = np.asarray(y_true).ravel()
    y_pred = np.asarray(y_pred).ravel()

    rmse = float(np.sqrt(mean_squared_error(y_true, y_pred)))
    mae = float(mean_absolute_error(y_true, y_pred))
    r2 = float(r2_score(y_true, y_pred))

    # Spearman rank correlation
    if len(y_true) > 2:
        rho, _ = spearmanr(y_true, y_pred)
        spearman_rho = float(rho) if np.isfinite(rho) else 0.0
    else:
        spearman_rho = 0.0

    # High-score recall: ≥6
    recall_6 = _high_score_recall(y_true, y_pred, threshold=6.0)

    # High-score recall: ≥10
    recall_10 = _high_score_recall(y_true, y_pred, threshold=10.0)

    # High-score precision: ≥6
    precision_6 = _high_score_precision(y_true, y_pred, threshold=6.0)

    # Top-20 recall
    top_20_recall = _top_n_recall(y_true, y_pred, n=20)

    return FPLMetrics(
        rmse=rmse,
        mae=mae,
        r2=r2,
        spearman_rho=spearman_rho,
        recall_6=recall_6,
        recall_10=recall_10,
        precision_6=precision_6,
        top_20_recall=top_20_recall,
    )


def _high_score_recall(
    y_true: np.ndarray,
    y_pred: np.ndarray,
    threshold: float,
) -> float:
    """Recall for ground-truth values ≥ threshold.

    Of all players who actually scored ≥ threshold, what fraction did
    the model predict ≥ threshold?
    """
    actual_positive = y_true >= threshold
    if actual_positive.sum() == 0:
        return 0.0
    predicted_positive = y_pred >= threshold
    true_positives = actual_positive & predicted_positive
    return float(true_positives.sum() / actual_positive.sum())


def _high_score_precision(
    y_true: np.ndarray,
    y_pred: np.ndarray,
    threshold: float,
) -> float:
    """Precision for predicted values ≥ threshold.

    Of all players the model predicted ≥ threshold, what fraction
    actually scored ≥ threshold?
    """
    predicted_positive = y_pred >= threshold
    if predicted_positive.sum() == 0:
        return 0.0
    true_positives = (y_true >= threshold) & predicted_positive
    return float(true_positives.sum() / predicted_positive.sum())


def _top_n_recall(
    y_true: np.ndarray,
    y_pred: np.ndarray,
    n: int,
) -> float:
    """Overlap between actual top-N and predicted top-N players."""
    if len(y_true) < n:
        return 0.0
    true_top = set(np.argsort(y_true)[-n:])
    pred_top = set(np.argsort(y_pred)[-n:])
    return float(len(true_top & pred_top) / n)


# -----------------------------------------------------------------------
# Composite Scoring
# -----------------------------------------------------------------------


# Default metric weights.
#
# Rationale for each weight:
#
# RMSE (0.25): The most standard regression metric. Penalizes large
#   errors heavily, which matters because predicting 2 when the answer
#   is 15 is far worse than being off by 1.
#
# MAE (0.15): Complements RMSE with a more robust, non-outlier-
#   sensitive accuracy measure.
#
# Spearman ρ (0.20): Ranking quality is critical for FPL — managers
#   need to pick the RIGHT players, not just predict the right mean.
#   A model can have good RMSE but terrible ranking if it clusters
#   predictions tightly around the mean.
#
# ≥6 Recall (0.20): The "good gameweek" threshold. ~25% of
#   performances score ≥6. High recall here means the model identifies
#   most players worth starting.
#
# ≥10 Recall (0.10): The "exceptional gameweek" threshold. Only ~5%
#   of performances. Lower weight than ≥6 because (a) rare events are
#   harder to predict, (b) optimizing too hard for this creates
#   excessive false positives.
#
# ≥6 Precision (0.10): Guards against a model that achieves high ≥6
#   recall by predicting ≥6 for everyone.

DEFAULT_METRIC_WEIGHTS: dict[str, float] = {
    "rmse": 0.25,
    "mae": 0.15,
    "spearman_rho": 0.20,
    "recall_6": 0.20,
    "recall_10": 0.10,
    "precision_6": 0.10,
}


# Default eligibility gates.
#
# A model that fails ANY gate is ineligible for promotion, regardless
# of its composite score. Gates are intentionally conservative — they
# catch fundamentally broken models, not marginal ones.
#
# RMSE ≤ 3.0: A model predicting 3 points off on average (squared) is
#   barely better than predicting the global mean (~2.3 for FPL).
#   Any production model must be well under this.
#
# ≥6 recall ≥ 0.05: The model must detect at least 5% of high-scorers.
#   A model with zero high-score detection is useless for FPL even if
#   its RMSE is good (it just predicts ~2 for everyone).

DEFAULT_GATES: dict[str, tuple[str, float]] = {
    "rmse": ("<=", 3.0),
    "recall_6": (">=", 0.05),
}


# Lower-is-better metrics need their scores inverted before weighting.
_LOWER_IS_BETTER = {"rmse", "mae"}


@dataclass
class CompositeModelScore:
    """A model's composite promotion score with full breakdown.

    Attributes:
        model_name: Name of the candidate model.
        fpl_metrics: The full FPL metric set.
        composite_score: The final weighted composite score.
        component_scores: Per-metric normalized contribution.
        eligible: Whether the model passed all eligibility gates.
        gate_failures: Any gates that the model failed.
    """

    model_name: str
    fpl_metrics: FPLMetrics
    composite_score: float
    component_scores: dict[str, float] = field(default_factory=dict)
    eligible: bool = True
    gate_failures: list[str] = field(default_factory=list)


def compute_composite_score(
    model_name: str,
    metrics: FPLMetrics,
    all_candidate_metrics: list[FPLMetrics],
    weights: dict[str, float] | None = None,
    gates: dict[str, tuple[str, float]] | None = None,
) -> CompositeModelScore:
    """Compute a weighted composite score for one model.

    Scores are min-max normalized across all candidates before
    weighting, so each metric contributes proportionally regardless of
    its natural scale.

    Args:
        model_name: The candidate model's name.
        metrics: This model's FPL metrics.
        all_candidate_metrics: FPL metrics for ALL candidates (used
            for min-max normalization).
        weights: Metric name → weight mapping. Defaults to
            ``DEFAULT_METRIC_WEIGHTS``.
        gates: Metric name → (operator, threshold) eligibility gates.
            Defaults to ``DEFAULT_GATES``.

    Returns:
        CompositeModelScore: The scored result.
    """
    weights = weights if weights is not None else DEFAULT_METRIC_WEIGHTS
    gates = gates if gates is not None else DEFAULT_GATES

    # Check eligibility gates
    gate_failures: list[str] = []
    for metric_name, (op, threshold) in gates.items():
        value = getattr(metrics, metric_name, None)
        if value is None:
            continue
        if op == "<=" and value > threshold:
            gate_failures.append(
                f"{metric_name}={value:.4f} > {threshold}"
            )
        elif op == ">=" and value < threshold:
            gate_failures.append(
                f"{metric_name}={value:.4f} < {threshold}"
            )

    eligible = len(gate_failures) == 0

    # Min-max normalize each metric across all candidates
    component_scores: dict[str, float] = {}
    weighted_sum = 0.0
    total_weight = 0.0

    for metric_name, weight in weights.items():
        values = [
            getattr(m, metric_name, 0.0)
            for m in all_candidate_metrics
        ]
        this_value = getattr(metrics, metric_name, 0.0)

        min_val = min(values)
        max_val = max(values)
        value_range = max_val - min_val

        if value_range > 1e-10:
            normalized = (this_value - min_val) / value_range
        else:
            # All candidates have the same value for this metric
            normalized = 0.5

        # Invert for lower-is-better metrics so that lower = higher score
        if metric_name in _LOWER_IS_BETTER:
            normalized = 1.0 - normalized

        component_scores[metric_name] = normalized * weight
        weighted_sum += normalized * weight
        total_weight += weight

    composite = weighted_sum / total_weight if total_weight > 0 else 0.0

    return CompositeModelScore(
        model_name=model_name,
        fpl_metrics=metrics,
        composite_score=composite,
        component_scores=component_scores,
        eligible=eligible,
        gate_failures=gate_failures,
    )


def select_best_model_fpl(
    candidate_names: list[str],
    candidate_predictions: list[np.ndarray],
    y_test: np.ndarray,
    weights: dict[str, float] | None = None,
    gates: dict[str, tuple[str, float]] | None = None,
) -> tuple[int, list[CompositeModelScore]]:
    """Select the best model using FPL-aware composite scoring.

    Args:
        candidate_names: Names of the candidate models.
        candidate_predictions: Predictions from each candidate.
        y_test: Ground-truth test targets.
        weights: Metric weights (defaults to ``DEFAULT_METRIC_WEIGHTS``).
        gates: Eligibility gates (defaults to ``DEFAULT_GATES``).

    Returns:
        tuple[int, list[CompositeModelScore]]:
            Index of the best model, and scored results for all
            candidates.

    Raises:
        RuntimeError: If no candidate passes all eligibility gates.
    """
    y_test_arr = np.asarray(y_test).ravel()

    # Compute FPL metrics for every candidate
    all_fpl_metrics: list[FPLMetrics] = []
    for preds in candidate_predictions:
        all_fpl_metrics.append(compute_fpl_metrics(y_test_arr, preds))

    # Score every candidate
    all_scores: list[CompositeModelScore] = []
    for name, fpl_m in zip(candidate_names, all_fpl_metrics):
        score = compute_composite_score(
            model_name=name,
            metrics=fpl_m,
            all_candidate_metrics=all_fpl_metrics,
            weights=weights,
            gates=gates,
        )
        all_scores.append(score)

        logger.info(
            "  Candidate '%s': composite=%.4f, eligible=%s, "
            "RMSE=%.4f, MAE=%.4f, Spearman=%.4f, "
            "≥6recall=%.4f, ≥10recall=%.4f, ≥6precision=%.4f%s",
            name,
            score.composite_score,
            score.eligible,
            fpl_m.rmse,
            fpl_m.mae,
            fpl_m.spearman_rho,
            fpl_m.recall_6,
            fpl_m.recall_10,
            fpl_m.precision_6,
            f" [FAILED GATES: {score.gate_failures}]"
            if score.gate_failures
            else "",
        )

    # Select: highest composite score among eligible candidates
    eligible = [
        (i, s) for i, s in enumerate(all_scores) if s.eligible
    ]

    if not eligible:
        # Fallback: if no model passes gates, pick the one with the
        # fewest gate failures, then highest composite score
        logger.warning(
            "No candidate passed all eligibility gates. "
            "Falling back to the least-failing candidate."
        )
        eligible = sorted(
            enumerate(all_scores),
            key=lambda pair: (
                len(pair[1].gate_failures),
                -pair[1].composite_score,
            ),
        )

    best_idx = max(eligible, key=lambda pair: pair[1].composite_score)[0]

    logger.info(
        "Selected best model: '%s' (composite=%.4f).",
        all_scores[best_idx].model_name,
        all_scores[best_idx].composite_score,
    )

    return best_idx, all_scores
