"""Five strong baselines for the differential prediction system.

Baselines provide the benchmark that any learned model MUST outperform.
If a learned model cannot beat Baseline E (ownership-adjusted form) or
Baseline B (expected points proxy), it should NOT be deployed.

Baselines:
    Baseline A: Random Low-Ownership Players
    Baseline B: Expected Points Proxy (total_points_avg_last_5)
    Baseline C: Value Efficiency (total_points_avg_last_5 / price)
    Baseline D: Recent Form Index (form_index)
    Baseline E: Ownership-Adjusted Form (form_index * (1 - ownership_percentile))
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from src.config.logging_config import get_logger
from src.differential.evaluation import evaluate_per_gameweek
from src.differential.models import DifferentialMetrics

logger = get_logger(__name__)

BASELINE_NAMES = [
    "Baseline A: Random Low-Ownership",
    "Baseline B: Form (Last 5 Pts)",
    "Baseline C: Value Efficiency",
    "Baseline D: Form Index",
    "Baseline E: Ownership-Adjusted Form",
]


def compute_baseline_scores(
    df: pd.DataFrame,
    random_state: int = 42,
) -> pd.DataFrame:
    """Compute scoring columns for all 5 baselines.

    Args:
        df: DataFrame with required features (form, value, ownership).
        random_state: Seed for reproducible random baseline.

    Returns:
        pd.DataFrame: Copy of df with additional baseline score columns:
            - score_baseline_a
            - score_baseline_b
            - score_baseline_c
            - score_baseline_d
            - score_baseline_e
    """
    out = df.copy()
    rng = np.random.default_rng(random_state)

    def _safe_series(col_name: str, default_val: float) -> pd.Series:
        if col_name in out.columns:
            return pd.to_numeric(out[col_name], errors="coerce").fillna(default_val)
        return pd.Series(default_val, index=out.index, dtype=float)

    pts_last_5 = _safe_series("total_points_avg_last_5", 0.0)
    form = _safe_series("form_index", 0.0)
    if "form_index" not in out.columns:
        form = pts_last_5
    price = _safe_series("value", 50.0).clip(lower=40.0) / 10.0
    own_pct = _safe_series("ownership_percentile", 0.5)

    # Baseline A: Random low-ownership (players with <= 20th percentile ownership get random score; others get 0)
    low_own_mask = own_pct <= 0.20
    random_scores = np.zeros(len(out), dtype=float)
    random_scores[low_own_mask] = rng.uniform(0.01, 1.0, size=int(low_own_mask.sum()))
    out["score_baseline_a"] = random_scores

    # Baseline B: Expected points proxy (recent 5-game points average)
    out["score_baseline_b"] = pts_last_5.values

    # Baseline C: Value efficiency (points per unit price)
    out["score_baseline_c"] = (pts_last_5 / price).values

    # Baseline D: Recent form index
    out["score_baseline_d"] = form.values

    # Baseline E: Ownership-adjusted form (form * (1 - ownership_percentile))
    # Players with high form and low ownership score highest.
    ownership_multiplier = (1.0 - own_pct).clip(lower=0.0, upper=1.0)
    out["score_baseline_e"] = (form * ownership_multiplier).values

    logger.info("Computed scores for all 5 baselines on %d rows.", len(out))
    return out


def evaluate_all_baselines(
    df: pd.DataFrame,
    target_col: str = "total_points",
    ownership_col: str = "ownership_percentile",
    season_col: str = "season",
    gw_col: str = "GW",
    threshold: int = 8,
    random_state: int = 42,
) -> dict[str, DifferentialMetrics]:
    """Evaluate all 5 baselines on a validation or test set.

    Args:
        df: Evaluation DataFrame.
        target_col: Actual outcome column.
        ownership_col: Ownership percentile column.
        season_col: Season column.
        gw_col: Gameweek column.
        threshold: Score threshold for binary event (default 8).
        random_state: Seed for random baseline.

    Returns:
        dict[str, DifferentialMetrics]: Baseline name -> metrics object.
    """
    df_scored = compute_baseline_scores(df, random_state=random_state)

    baseline_configs = [
        ("Baseline A (Random Low-Own)", "score_baseline_a"),
        ("Baseline B (Form L5)", "score_baseline_b"),
        ("Baseline C (Value Efficiency)", "score_baseline_c"),
        ("Baseline D (Form Index)", "score_baseline_d"),
        ("Baseline E (Own-Adjusted Form)", "score_baseline_e"),
    ]

    results: dict[str, DifferentialMetrics] = {}
    for name, col in baseline_configs:
        metrics = evaluate_per_gameweek(
            name=name,
            df=df_scored,
            score_col=col,
            target_col=target_col,
            ownership_col=ownership_col,
            season_col=season_col,
            gw_col=gw_col,
            threshold=threshold,
        )
        results[name] = metrics

    return results
