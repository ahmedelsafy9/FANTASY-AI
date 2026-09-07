"""Training window filtering and recency weighting (Feedback 5).

Supports benchmarking optimal historical training windows:
- All history
- Last 5 seasons
- Last 3 seasons
- Last 2 seasons
- Last 1 season
- Exponential & linear recency weighting

Strictly preserves chronological integrity: target gameweek outcomes
are never included in the training set.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from src.config.logging_config import get_logger

logger = get_logger(__name__)

SUPPORTED_WINDOWS = (
    "all_history",
    "last_5_seasons",
    "last_3_seasons",
    "last_2_seasons",
    "last_1_season",
)

WINDOW_SEASONS_COUNT = {
    "all_history": None,
    "last_5_seasons": 5,
    "last_3_seasons": 3,
    "last_2_seasons": 2,
    "last_1_season": 1,
}


def get_ordered_seasons(df: pd.DataFrame, season_col: str = "season") -> list[str]:
    """Return sorted unique seasons in chronological order."""
    if season_col not in df.columns:
        return []
    return sorted([str(s) for s in df[season_col].dropna().unique()])


def filter_training_window(
    df: pd.DataFrame,
    window_type: str = "all_history",
    target_season: str | None = None,
    current_gw: int | None = None,
    season_col: str = "season",
    gw_col: str = "GW",
) -> pd.DataFrame:
    """Filter dataset to the specified historical training window.

    Ensures that:
    1. Only the requested number of completed seasons prior to target_season
       are included.
    2. For the target_season (if present in the training data), only
       gameweeks strictly before ``current_gw`` are included (no leakage).
    3. If target_season is None, it defaults to the latest season in df.

    Args:
        df: Input DataFrame.
        window_type: One of 'all_history', 'last_5_seasons', 'last_3_seasons',
            'last_2_seasons', 'last_1_season'.
        target_season: The season being predicted. Prior seasons are counted
            relative to this season.
        current_gw: If predicting within target_season, only GWs < current_gw
            are kept for target_season.
        season_col: Season column name.
        gw_col: Gameweek column name.

    Returns:
        pd.DataFrame: Filtered DataFrame.
    """
    if window_type not in WINDOW_SEASONS_COUNT:
        raise ValueError(
            f"Unsupported window_type '{window_type}'. "
            f"Must be one of {SUPPORTED_WINDOWS}"
        )

    all_seasons = get_ordered_seasons(df, season_col)
    if not all_seasons:
        return df.copy()

    if target_season is None:
        target_season = all_seasons[-1]
    else:
        target_season = str(target_season)

    # Prior completed seasons are those chronologically before target_season
    prior_seasons = [s for s in all_seasons if s < target_season]

    n_seasons = WINDOW_SEASONS_COUNT[window_type]
    if n_seasons is not None:
        selected_prior = prior_seasons[-n_seasons:] if len(prior_seasons) >= n_seasons else prior_seasons
    else:
        selected_prior = prior_seasons

    # Build mask
    is_selected_prior = df[season_col].astype(str).isin(selected_prior)

    # Include completed GWs of target_season if current_gw is specified
    is_completed_target = pd.Series(False, index=df.index)
    if current_gw is not None and current_gw > 1 and target_season in all_seasons:
        is_target_season = df[season_col].astype(str) == target_season
        is_prior_gw = pd.to_numeric(df[gw_col], errors="coerce") < current_gw
        is_completed_target = is_target_season & is_prior_gw

    combined_mask = is_selected_prior | is_completed_target
    filtered = df.loc[combined_mask].copy()

    logger.info(
        "Filtered training window '%s' (target_season=%s, current_gw=%s): "
        "%d rows across seasons %s.",
        window_type, target_season, current_gw,
        len(filtered), sorted(filtered[season_col].astype(str).unique()),
    )
    return filtered


def compute_recency_weights(
    df: pd.DataFrame,
    half_life_seasons: float = 2.0,
    scheme: str = "exponential",
    target_season: str | None = None,
    season_col: str = "season",
) -> np.ndarray:
    """Compute sample recency weights for historical training rows.

    Args:
        df: Input DataFrame.
        half_life_seasons: Half-life in seasons for exponential decay.
            Higher values give older seasons more weight; smaller values
            focus more sharply on recent seasons.
        scheme: 'exponential', 'linear', or 'none'.
        target_season: Reference season (age 0). Defaults to latest season in df.
        season_col: Season column name.

    Returns:
        np.ndarray: Array of non-negative float weights normalized so mean is 1.0.
    """
    n_rows = len(df)
    if n_rows == 0 or scheme == "none":
        return np.ones(n_rows, dtype=np.float64)

    all_seasons = get_ordered_seasons(df, season_col)
    if not all_seasons:
        return np.ones(n_rows, dtype=np.float64)

    ref_season = str(target_season) if target_season is not None else all_seasons[-1]
    sorted_seasons = sorted(set(all_seasons + [ref_season]))
    ref_idx = sorted_seasons.index(ref_season)

    # Calculate season age (0 for ref_season, 1 for immediately preceding, etc.)
    season_ages = {s: max(0, ref_idx - sorted_seasons.index(s)) for s in all_seasons}
    ages = df[season_col].astype(str).map(season_ages).fillna(0).values.astype(np.float64)

    if scheme == "exponential":
        decay = np.log(2.0) / max(0.1, half_life_seasons)
        raw_weights = np.exp(-decay * ages)
    elif scheme == "linear":
        max_age = max(ages.max(), 1.0)
        raw_weights = np.maximum(0.1, 1.0 - (ages / (max_age + 1.0)))
    else:
        raw_weights = np.ones(n_rows, dtype=np.float64)

    # Normalize so mean weight is 1.0 (preserves gradient scale for ML estimators)
    mean_w = np.mean(raw_weights)
    if mean_w > 0:
        weights = raw_weights / mean_w
    else:
        weights = np.ones(n_rows, dtype=np.float64)

    return weights
