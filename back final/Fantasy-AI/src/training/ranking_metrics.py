"""Ranking and recall metrics for Fantasy Premier League model evaluation."""

from __future__ import annotations

import numpy as np


def top_n_recall(y_true: np.ndarray, y_pred: np.ndarray, n: int = 20) -> float:
    """Calculate the overlap fraction between top-N actual and top-N predicted.

    Args:
        y_true: Ground truth target array.
        y_pred: Predicted target array.
        n: Number of top elements to compare.

    Returns:
        float: Fraction of ground-truth top-N elements present in top-N predictions.
    """
    y_true_arr = np.asarray(y_true).ravel()
    y_pred_arr = np.asarray(y_pred).ravel()

    if len(y_true_arr) < n:
        return float("nan")

    true_top_n_idx = set(np.argsort(y_true_arr)[-n:])
    pred_top_n_idx = set(np.argsort(y_pred_arr)[-n:])

    return len(true_top_n_idx & pred_top_n_idx) / n


def high_score_recall(
    y_true: np.ndarray,
    y_pred: np.ndarray,
    threshold: float = 6.0,
    pred_threshold: float = 6.0,
) -> float:
    """Calculate recall for high-scoring player performances.

    Args:
        y_true: Ground truth target array.
        y_pred: Predicted target array.
        threshold: Ground-truth target threshold to consider high score (e.g. 6.0).
        pred_threshold: Prediction threshold required to count as positive recall.

    Returns:
        float: Fraction of true high-scorers predicted above the pred_threshold.
    """
    y_true_arr = np.asarray(y_true).ravel()
    y_pred_arr = np.asarray(y_pred).ravel()

    mask = y_true_arr >= threshold

    if mask.sum() == 0:
        return float("nan")

    return float((y_pred_arr[mask] >= pred_threshold).mean())
