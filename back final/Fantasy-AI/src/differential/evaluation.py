"""Evaluation metrics for the differential prediction system.

Focuses on ranking and rare-event metrics rather than MAE.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.stats import spearmanr
from sklearn.metrics import (
    average_precision_score,
    roc_auc_score,
    ndcg_score,
)

from src.config.logging_config import get_logger
from src.differential.models import DifferentialMetrics

logger = get_logger(__name__)


def _precision_at_k(y_true: np.ndarray, scores: np.ndarray, k: int) -> float:
    """Compute precision@K: fraction of top-K predictions that are positive."""
    if len(scores) < k or k <= 0:
        return 0.0
    top_k_idx = np.argsort(scores)[::-1][:k]
    return float(y_true[top_k_idx].sum() / k)


def _recall_at_k(y_true: np.ndarray, scores: np.ndarray, k: int) -> float:
    """Compute recall@K: fraction of positives captured in top-K."""
    if len(scores) < k or k <= 0:
        return 0.0
    n_pos = y_true.sum()
    if n_pos == 0:
        return 0.0
    top_k_idx = np.argsort(scores)[::-1][:k]
    return float(y_true[top_k_idx].sum() / n_pos)


def _top_k_hit_rate(
    actual_points: np.ndarray,
    scores: np.ndarray,
    k: int,
    point_threshold: int,
) -> float:
    """Among top-K by score, how many actually scored >= point_threshold?"""
    if len(scores) < k or k <= 0:
        return 0.0
    top_k_idx = np.argsort(scores)[::-1][:k]
    hits = (actual_points[top_k_idx] >= point_threshold).sum()
    return float(hits / k)


def _differential_hit_rate(
    actual_points: np.ndarray,
    scores: np.ndarray,
    ownership_percentile: np.ndarray,
    k: int,
    point_threshold: int,
    ownership_threshold: float = 0.20,
) -> float:
    """Among top-K differential candidates (low ownership), how many hit?

    A "differential candidate" is a player in the top-K by score who also
    has ownership below the ownership threshold.
    """
    if len(scores) < k or k <= 0:
        return 0.0
    top_k_idx = np.argsort(scores)[::-1][:k]
    # Filter to low-ownership among top-K
    low_own_mask = ownership_percentile[top_k_idx] <= ownership_threshold
    if low_own_mask.sum() == 0:
        return 0.0
    hits = (actual_points[top_k_idx][low_own_mask] >= point_threshold).sum()
    return float(hits / low_own_mask.sum())


def _ndcg_at_k(y_true: np.ndarray, scores: np.ndarray, k: int) -> float:
    """Compute NDCG@K using actual points as relevance."""
    if len(scores) < k or k <= 0:
        return 0.0
    try:
        return float(ndcg_score(
            y_true.reshape(1, -1),
            scores.reshape(1, -1),
            k=k,
        ))
    except Exception:
        return 0.0


def evaluate_differential(
    name: str,
    actual_points: np.ndarray,
    scores: np.ndarray,
    ownership_percentile: np.ndarray | None = None,
    threshold: int = 8,
    k_values: tuple[int, ...] = (5, 10, 20),
) -> DifferentialMetrics:
    """Evaluate a differential model / baseline using ranking metrics.

    Args:
        name: Model or baseline name.
        actual_points: Actual total_points for each player.
        scores: Model scores (higher = more likely to be a differential pick).
        ownership_percentile: Ownership percentile for each player.
        threshold: Point threshold for binary target (e.g. 8).
        k_values: K values for Precision@K, Recall@K.

    Returns:
        DifferentialMetrics with all computed metrics.
    """
    valid = np.isfinite(actual_points) & np.isfinite(scores)
    y = actual_points[valid]
    s = scores[valid]
    n = len(y)

    if n == 0:
        return DifferentialMetrics(name=name, threshold=threshold)

    y_binary = (y >= threshold).astype(int)
    n_pos = int(y_binary.sum())

    metrics = DifferentialMetrics(name=name, threshold=threshold, n_evaluated=n)

    # Precision@K and Recall@K
    if len(k_values) >= 1:
        metrics.precision_at_5 = _precision_at_k(y_binary, s, min(k_values[0], n))
    if len(k_values) >= 2:
        metrics.precision_at_10 = _precision_at_k(y_binary, s, min(k_values[1], n))
    if len(k_values) >= 3:
        metrics.precision_at_20 = _precision_at_k(y_binary, s, min(k_values[2], n))

    if len(k_values) >= 2:
        metrics.recall_at_10 = _recall_at_k(y_binary, s, min(k_values[1], n))
    if len(k_values) >= 3:
        metrics.recall_at_20 = _recall_at_k(y_binary, s, min(k_values[2], n))

    # PR-AUC and ROC-AUC
    if n_pos > 0 and n_pos < n:
        try:
            metrics.pr_auc = float(average_precision_score(y_binary, s))
        except Exception:
            pass
        try:
            metrics.roc_auc = float(roc_auc_score(y_binary, s))
        except Exception:
            pass

    # Top-K hit rate
    metrics.top_k_hit_rate = _top_k_hit_rate(y, s, min(20, n), threshold)

    # Spearman correlation
    try:
        sp, _ = spearmanr(y, s)
        metrics.spearman = float(sp) if np.isfinite(sp) else 0.0
    except Exception:
        pass

    # NDCG
    metrics.ndcg_at_10 = _ndcg_at_k(y, s, min(10, n))
    metrics.ndcg_at_20 = _ndcg_at_k(y, s, min(20, n))

    # Differential hit rates
    if ownership_percentile is not None:
        own = ownership_percentile[valid]
        metrics.differential_hit_rate_8 = _differential_hit_rate(y, s, own, min(20, n), 8)
        metrics.differential_hit_rate_10 = _differential_hit_rate(y, s, own, min(20, n), 10)
        metrics.differential_hit_rate_12 = _differential_hit_rate(y, s, own, min(20, n), 12)

    logger.info(
        "%s: P@5=%.3f, P@10=%.3f, PR-AUC=%.3f, ROC-AUC=%.3f, "
        "Top-K Hit=%.3f, Spearman=%.3f, Diff-Hit(8+)=%.3f",
        name, metrics.precision_at_5, metrics.precision_at_10,
        metrics.pr_auc, metrics.roc_auc,
        metrics.top_k_hit_rate, metrics.spearman, metrics.differential_hit_rate_8,
    )

    return metrics


def evaluate_per_gameweek(
    name: str,
    df: pd.DataFrame,
    score_col: str,
    target_col: str = "total_points",
    ownership_col: str = "ownership_percentile",
    season_col: str = "season",
    gw_col: str = "GW",
    threshold: int = 8,
) -> DifferentialMetrics:
    """Evaluate per-GW and aggregate metrics (more realistic than pooled).

    Computes Precision@K etc. within each Gameweek and averages, which
    avoids the problem of pooled evaluation inflating scores for GWs
    with many high-scorers.

    Args:
        name: Model name.
        df: DataFrame with predictions and actual points.
        score_col: Column name of the model's score.
        target_col: Target column.
        ownership_col: Ownership percentile column.
        season_col: Season column.
        gw_col: GW column.
        threshold: Point threshold.

    Returns:
        DifferentialMetrics averaged across Gameweeks.
    """
    all_p5, all_p10, all_p20 = [], [], []
    all_r10, all_r20 = [], []
    all_hit, all_sp = [], []
    all_dhr8, all_dhr10, all_dhr12 = [], [], []

    for _, grp in df.groupby([season_col, gw_col]):
        if len(grp) < 20:
            continue

        y = pd.to_numeric(grp[target_col], errors="coerce").fillna(0).values
        s = pd.to_numeric(grp[score_col], errors="coerce").fillna(0).values
        y_bin = (y >= threshold).astype(int)

        if y_bin.sum() == 0:
            continue

        all_p5.append(_precision_at_k(y_bin, s, 5))
        all_p10.append(_precision_at_k(y_bin, s, 10))
        all_p20.append(_precision_at_k(y_bin, s, 20))
        all_r10.append(_recall_at_k(y_bin, s, 10))
        all_r20.append(_recall_at_k(y_bin, s, 20))
        all_hit.append(_top_k_hit_rate(y, s, 20, threshold))

        try:
            sp, _ = spearmanr(y, s)
            if np.isfinite(sp):
                all_sp.append(float(sp))
        except Exception:
            pass

        if ownership_col in grp.columns:
            own = pd.to_numeric(grp[ownership_col], errors="coerce").fillna(0.5).values
            all_dhr8.append(_differential_hit_rate(y, s, own, 20, 8))
            all_dhr10.append(_differential_hit_rate(y, s, own, 20, 10))
            all_dhr12.append(_differential_hit_rate(y, s, own, 20, 12))

    def _safe_mean(lst: list[float]) -> float:
        return float(np.mean(lst)) if lst else 0.0

    # Also compute pooled PR-AUC/ROC-AUC
    all_y = pd.to_numeric(df[target_col], errors="coerce").fillna(0).values
    all_s = pd.to_numeric(df[score_col], errors="coerce").fillna(0).values
    y_bin_all = (all_y >= threshold).astype(int)
    pr_auc = 0.0
    roc_auc = 0.0
    if y_bin_all.sum() > 0 and y_bin_all.sum() < len(y_bin_all):
        try:
            pr_auc = float(average_precision_score(y_bin_all, all_s))
        except Exception:
            pass
        try:
            roc_auc = float(roc_auc_score(y_bin_all, all_s))
        except Exception:
            pass

    return DifferentialMetrics(
        name=name,
        threshold=threshold,
        precision_at_5=_safe_mean(all_p5),
        precision_at_10=_safe_mean(all_p10),
        precision_at_20=_safe_mean(all_p20),
        recall_at_10=_safe_mean(all_r10),
        recall_at_20=_safe_mean(all_r20),
        pr_auc=pr_auc,
        roc_auc=roc_auc,
        top_k_hit_rate=_safe_mean(all_hit),
        spearman=_safe_mean(all_sp),
        differential_hit_rate_8=_safe_mean(all_dhr8),
        differential_hit_rate_10=_safe_mean(all_dhr10),
        differential_hit_rate_12=_safe_mean(all_dhr12),
        n_evaluated=len(df),
    )
