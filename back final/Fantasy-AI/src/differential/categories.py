"""Player categorization for the differential prediction layer.

Assigns interpretable, data-driven categories strictly on the server side:
    - "Elite Differential": High upside probability (top-10%) + ultra-low ownership (<20th pctl)
    - "Value Differential": Solid upside (top-25%) + budget price (<= £5.5M) + low/mid ownership (<50th pctl)
    - "Emerging Differential": Surging minutes trend + high recent start rate + upside potential
    - "Standard Differential": Meets low-ownership criterion with above-average upside

Categories are only retained if supported by sufficient historical data (>= min_examples).
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from src.config.logging_config import get_logger

logger = get_logger(__name__)

CATEGORY_ELITE = "Elite Differential"
CATEGORY_VALUE = "Value Differential"
CATEGORY_EMERGING = "Emerging Differential"
CATEGORY_STANDARD = "Standard Differential"
CATEGORY_NONE = "Template / Low-Upside"


def assign_differential_categories(
    df: pd.DataFrame,
    prob_col: str = "p_8_plus",
    ownership_col: str = "ownership_percentile",
    value_col: str = "value",
    min_examples: int = 3,
) -> pd.Series:
    """Assign differential category labels to players.

    Args:
        df: DataFrame containing player features and predictions.
        prob_col: Column with P(total_points >= 8) or differential score.
        ownership_col: Column with ownership percentile [0, 1].
        value_col: Price column (in tenths, e.g. 55 = £5.5M).
        min_examples: Minimum occurrences required to keep a category active.

    Returns:
        pd.Series: Categorical label for each player.
    """
    if len(df) == 0:
        return pd.Series([], dtype=str)

    p_upside = pd.to_numeric(df.get(prob_col, 0.0), errors="coerce").fillna(0.0)
    own_pct = pd.to_numeric(df.get(ownership_col, 0.5), errors="coerce").fillna(0.5)
    val = pd.to_numeric(df.get(value_col, 50.0), errors="coerce").fillna(50.0)

    # Calculate probability thresholds
    p90 = float(p_upside.quantile(0.90)) if len(p_upside) > 0 else 0.20
    p75 = float(p_upside.quantile(0.75)) if len(p_upside) > 0 else 0.15
    p70 = float(p_upside.quantile(0.70)) if len(p_upside) > 0 else 0.10

    # Trend / Emerging features
    min_trend = pd.to_numeric(df.get("minutes_trend", 0.0), errors="coerce").fillna(0.0)
    starts_ratio = pd.to_numeric(df.get("starts_ratio_3_5", 0.0), errors="coerce").fillna(0.0)

    # Boolean masks
    is_elite = (p_upside >= p90) & (own_pct <= 0.20)
    is_emerging = (starts_ratio >= 0.80) & (min_trend > 10.0) & (p_upside >= p70) & (own_pct <= 0.35)
    is_value = (p_upside >= p75) & (val <= 55.0) & (own_pct <= 0.50)
    is_standard = (own_pct <= 0.20) & (p_upside >= p70)

    # Assign in priority order
    labels = np.full(len(df), CATEGORY_NONE, dtype=object)
    labels[is_standard] = CATEGORY_STANDARD
    labels[is_value] = CATEGORY_VALUE
    labels[is_emerging] = CATEGORY_EMERGING
    labels[is_elite] = CATEGORY_ELITE

    series = pd.Series(labels, index=df.index, name="differential_category")

    # Safety check: drop rare/unsupported categories
    counts = series.value_counts()
    for cat in [CATEGORY_ELITE, CATEGORY_VALUE, CATEGORY_EMERGING, CATEGORY_STANDARD]:
        if counts.get(cat, 0) < min_examples:
            logger.info("Category '%s' has only %d examples (< %d). Demoting to '%s'.",
                        cat, counts.get(cat, 0), min_examples, CATEGORY_STANDARD)
            series[series == cat] = CATEGORY_STANDARD

    return series
