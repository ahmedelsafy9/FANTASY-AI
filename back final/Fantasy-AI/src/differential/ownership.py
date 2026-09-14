"""Ownership derivation for the differential prediction layer.

Derives ownership percentiles and approximate ownership percentages
from the ``selected`` column in historical FPL data. Uses only
information available BEFORE the target Gameweek.

Temporal safety:
    The ``selected`` column in vaastav/FPL data represents the number
    of FPL managers who had the player selected at the START of the
    Gameweek — i.e., before the matches were played. This is safe
    pre-GW information.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from src.config.logging_config import get_logger

logger = get_logger(__name__)


def compute_ownership_percentile(
    df: pd.DataFrame,
    selected_col: str = "selected",
    season_col: str = "season",
    gw_col: str = "GW",
) -> pd.Series:
    """Compute rank-based ownership percentile within each (season, GW).

    A percentile of 0.95 means the player is more owned than 95% of
    players in that Gameweek — i.e., a "template" pick.

    A percentile of 0.05 means the player is among the least owned.

    Args:
        df: DataFrame with selected, season, and GW columns.
        selected_col: Name of the ownership count column.
        season_col: Name of the season column.
        gw_col: Name of the Gameweek column.

    Returns:
        pd.Series: Ownership percentile (0-1) aligned with df index.
    """
    sel = pd.to_numeric(df[selected_col], errors="coerce").fillna(0)
    season = df[season_col] if season_col in df.columns else pd.Series("unknown", index=df.index)
    gw = pd.to_numeric(df[gw_col], errors="coerce").fillna(0) if gw_col in df.columns else pd.Series(0, index=df.index)

    temp = pd.DataFrame({"selected": sel, "season": season, "gw": gw}, index=df.index)
    result = temp.groupby(["season", "gw"])["selected"].rank(pct=True, method="average")
    return result.fillna(0.5)


def compute_ownership_pct_approx(
    df: pd.DataFrame,
    selected_col: str = "selected",
    season_col: str = "season",
    gw_col: str = "GW",
) -> pd.Series:
    """Compute approximate ownership percentage within each (season, GW).

    Uses ``selected / max(selected_in_gw)`` as a proxy since we don't
    have the total number of FPL managers per GW.

    This is an approximation: the most selected player in a GW might
    have ~60-70% ownership, so this metric is relative, not absolute.

    Args:
        df: DataFrame with selected, season, and GW columns.
        selected_col: Name of the ownership count column.
        season_col: Name of the season column.
        gw_col: Name of the Gameweek column.

    Returns:
        pd.Series: Approximate ownership ratio (0-1) aligned with df index.
    """
    sel = pd.to_numeric(df[selected_col], errors="coerce").fillna(0)
    season = df[season_col] if season_col in df.columns else pd.Series("unknown", index=df.index)
    gw = pd.to_numeric(df[gw_col], errors="coerce").fillna(0) if gw_col in df.columns else pd.Series(0, index=df.index)

    temp = pd.DataFrame({"selected": sel, "season": season, "gw": gw}, index=df.index)
    gw_max = temp.groupby(["season", "gw"])["selected"].transform("max")
    # Avoid division by zero
    gw_max = gw_max.clip(lower=1)
    return (sel / gw_max).fillna(0.0)


def assign_ownership_band(
    ownership_percentile: pd.Series,
) -> pd.Series:
    """Assign human-readable ownership bands from percentile values.

    Args:
        ownership_percentile: Ownership percentile (0-1).

    Returns:
        pd.Series: Categorical ownership band labels.
    """
    bins = [0, 0.05, 0.20, 0.50, 0.80, 1.0]
    labels = ["Ultra-Low (<5%)", "Low (5-20%)", "Medium (20-50%)",
              "Popular (50-80%)", "Template (>80%)"]
    return pd.cut(
        ownership_percentile.clip(0, 1),
        bins=bins,
        labels=labels,
        right=True,
        include_lowest=True,
    )


def is_low_ownership(
    ownership_percentile: pd.Series,
    threshold: float = 0.20,
) -> pd.Series:
    """Return boolean mask for low-ownership players.

    Args:
        ownership_percentile: Ownership percentile (0-1).
        threshold: Percentile threshold below which a player is
            considered low-ownership.

    Returns:
        pd.Series: Boolean mask.
    """
    return ownership_percentile <= threshold
