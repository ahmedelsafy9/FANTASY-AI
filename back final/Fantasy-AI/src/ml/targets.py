"""Target definitions for player-gameweek modelling.

Prediction unit
---------------
The canonical unit is a **player-gameweek**. When a double gameweek
produces multiple fixtures in the same ``GW``, actual FPL points are the
sum of those fixtures. Training rows must already be aggregated to that
unit before they enter a tournament.

Zero vs missing
---------------
A verified completed fixture with no appearance is a valid **zero**.
It must not be dropped or imputed as missing. Postponed or unassigned
fixtures are excluded until they have an official event and outcome.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

DEFAULT_CLASSIFICATION_THRESHOLDS = (6,)
SUPPORTED_CLASSIFICATION_THRESHOLDS = (2, 6, 10)


def player_gameweek_points(
    frame: pd.DataFrame,
    points_column: str = "total_points",
    player_column: str = "element",
    season_column: str = "season",
    gameweek_column: str = "GW",
) -> pd.Series:
    """Return actual points for the player-gameweek unit.

    Missing point values on completed observations become 0, preserving
    genuine blanks as zeros rather than NaN labels.
    """
    points = pd.to_numeric(frame[points_column], errors="coerce").fillna(0.0)
    if {player_column, season_column, gameweek_column}.issubset(frame.columns):
        grouped = points.groupby(
            [frame[player_column], frame[season_column], frame[gameweek_column]],
            sort=False,
        ).transform("sum")
        return grouped
    return points


def classification_label(points: pd.Series | np.ndarray, threshold: int) -> np.ndarray:
    """Binary label ``actual_gameweek_points >= threshold``.

    Labels are derived from actual points, never from regression predictions.
    """
    if threshold not in SUPPORTED_CLASSIFICATION_THRESHOLDS and threshold not in DEFAULT_CLASSIFICATION_THRESHOLDS:
        raise ValueError(
            f"Threshold {threshold} is not a trained target. "
            f"Supported: {SUPPORTED_CLASSIFICATION_THRESHOLDS}"
        )
    values = np.asarray(points, dtype=float)
    return (values >= threshold).astype(int)
