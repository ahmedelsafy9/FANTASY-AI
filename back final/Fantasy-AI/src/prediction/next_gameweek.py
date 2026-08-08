"""Builds one feature row per player representing their next Gameweek.

**Known simplification**: this project's rolling-window features
(Sprint 5) are computed with a one-match lag (``shift(1)`` before each
rolling/expanding window), so a player's most recently *played* row
already reflects their state *entering* that match — not the state
entering the match *after* it. Recomputing a true next-Gameweek row
would mean re-running the full feature engineering pipeline with a
synthetic future fixture appended per player (unknown opponent, unknown
kickoff time, etc.).

For this baseline, we approximate next-Gameweek features with each
player's most recent row's feature values — over a 3/5/10-match
rolling window, one additional match barely moves the average, so the
approximation is reasonable for a baseline, but it is *not* exact and
should be revisited (e.g. in Sprint 9) once real upcoming-fixture data
(opponent, home/away, rest days) is available to build a proper future
row.
"""

from __future__ import annotations

import pandas as pd

from src.config.logging_config import get_logger
from src.core.exceptions import PredictionError

logger = get_logger(__name__)


def build_next_gameweek_rows(
    data: pd.DataFrame,
    player_id_columns: tuple[str, ...],
    chronological_columns: tuple[str, ...],
    max_valid_gameweek: int,
) -> pd.DataFrame:
    """Select each player's most recent row as a proxy for their next Gameweek.

    Args:
        data: The full engineered dataset (from Sprint 5).
        player_id_columns: Candidate columns identifying a player, in
            priority order. The first one present is used.
        chronological_columns: Candidate columns defining match order
            (e.g. ``("season", "GW")``). The last one is treated as
            the within-season Gameweek number for computing
            ``predicted_for_gw``.
        max_valid_gameweek: The last Gameweek of a season (typically
            38); used to detect season rollover when computing
            ``predicted_for_gw``.

    Returns:
        pd.DataFrame: One row per player — their latest known feature
        state — with an added ``predicted_for_gw`` column.

    Raises:
        PredictionError: If no player identifier or Gameweek column is
            available in the data.
    """
    stable_candidates = ("name_normalized", "name")
    player_id_column = next((c for c in stable_candidates if c in data.columns), None)
    if player_id_column is None:
        player_id_column = next((c for c in player_id_columns if c in data.columns), None)
    if player_id_column is None:
        raise PredictionError(
            f"No player identifier column found among {player_id_columns}."
        )

    sort_columns = [c for c in chronological_columns if c in data.columns]
    if not sort_columns:
        raise PredictionError(
            f"No chronological column found among {chronological_columns}; "
            "cannot determine each player's most recent match."
        )
    gw_column = sort_columns[-1]

    working = data.sort_values(by=sort_columns, kind="mergesort")
    latest_rows = working.groupby(player_id_column, as_index=False).tail(1).copy()

    current_gw = pd.to_numeric(latest_rows[gw_column], errors="coerce")
    predicted_for_gw = (current_gw + 1).where(current_gw < max_valid_gameweek, other=1)
    latest_rows["predicted_for_gw"] = predicted_for_gw.astype("Int64")

    rolled_over = int((current_gw >= max_valid_gameweek).sum())
    if rolled_over:
        logger.warning(
            "%d player(s) were at the final Gameweek (%d); their 'predicted_for_gw' "
            "was set to 1 (next season) — treat these with extra caution, as no "
            "new-season context (transfers, new team) is reflected in their features.",
            rolled_over,
            max_valid_gameweek,
        )

    logger.info(
        "Built %d next-Gameweek row(s) from the latest known match per player.",
        len(latest_rows),
    )
    return latest_rows.reset_index(drop=True)
