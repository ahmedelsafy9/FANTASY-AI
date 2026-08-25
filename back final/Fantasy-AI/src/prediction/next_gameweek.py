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
    """Select each current-season player's most recent row as a proxy for their next Gameweek.

    .. versionchanged:: Sprint 10
       Restricts candidate rows to the **latest season** found in the
       data.  Previously, every player who had *ever* appeared in the
       historical dataset was included, which produced thousands of
       stale prediction rows for retired/transferred players and
       triggered misleading season-rollover warnings.

    Args:
        data: The full engineered dataset (from Sprint 5).
        player_id_columns: Candidate columns identifying a player, in
            priority order. The first one present is used.
        chronological_columns: Candidate columns defining match order
            (e.g. ``("season", "GW")``). The first is treated as the
            season identifier; the last as the within-season Gameweek
            number for computing ``predicted_for_gw``.
        max_valid_gameweek: The last Gameweek of a season (typically
            38); used to detect season rollover when computing
            ``predicted_for_gw``.

    Returns:
        pd.DataFrame: One row per current-season player — their latest
        known feature state — with an added ``predicted_for_gw`` column.

    Raises:
        PredictionError: If no player identifier or Gameweek column is
            available in the data.
    """
    # ------------------------------------------------------------------
    # 1. Resolve player identifier
    # ------------------------------------------------------------------
    player_id_column = next(
        (c for c in player_id_columns if c in data.columns), None
    )
    if player_id_column is None:
        raise PredictionError(
            f"No player identifier column found among {player_id_columns}."
        )

    # ------------------------------------------------------------------
    # 2. Resolve chronological columns
    # ------------------------------------------------------------------
    sort_columns = [c for c in chronological_columns if c in data.columns]
    if not sort_columns:
        raise PredictionError(
            f"No chronological column found among {chronological_columns}; "
            "cannot determine each player's most recent match."
        )
    gw_column = sort_columns[-1]

    # ------------------------------------------------------------------
    # 3. Restrict to the current (latest) season
    #
    # The first chronological column is treated as the season
    # identifier (e.g. "season").  Filtering to the latest season
    # ensures that historical players from older seasons are never
    # included in current predictions.
    # ------------------------------------------------------------------
    season_column = sort_columns[0] if len(sort_columns) > 1 else None
    latest_season: str | None = None

    if season_column is not None and season_column in data.columns:
        latest_season = data[season_column].max()
        current_season_data = data[data[season_column] == latest_season].copy()
        logger.info(
            "Restricting prediction candidates to current season '%s' "
            "(%d row(s) out of %d total).",
            latest_season,
            len(current_season_data),
            len(data),
        )
    else:
        current_season_data = data.copy()

    if current_season_data.empty:
        raise PredictionError(
            "No rows found for the current season after filtering. "
            "Ensure the engineered dataset contains current-season data."
        )

    # ------------------------------------------------------------------
    # 4. Select each player's latest row within the current season
    # ------------------------------------------------------------------
    working = current_season_data.sort_values(by=sort_columns, kind="mergesort")
    latest_rows = working.groupby(player_id_column, as_index=False).tail(1).copy()

    # ------------------------------------------------------------------
    # 5. Compute predicted_for_gw
    # ------------------------------------------------------------------
    current_gw = pd.to_numeric(latest_rows[gw_column], errors="coerce")
    predicted_for_gw = (current_gw + 1).where(
        current_gw < max_valid_gameweek, other=1
    )
    latest_rows["predicted_for_gw"] = predicted_for_gw.astype("Int64")

    # ------------------------------------------------------------------
    # 6. Season-rollover handling
    # ------------------------------------------------------------------
    rolled_over = int((current_gw >= max_valid_gameweek).sum())
    if rolled_over:
        logger.warning(
            "%d player(s) in season '%s' are at the final Gameweek (%d); "
            "their 'predicted_for_gw' was set to 1.  If a new season has "
            "started, re-run the automation pipeline to ingest the new "
            "season's data before generating predictions.",
            rolled_over,
            latest_season if latest_season is not None else "unknown",
            max_valid_gameweek,
        )

    logger.info(
        "Built %d next-Gameweek row(s) for season '%s' (latest GW: %s).",
        len(latest_rows),
        latest_season if latest_season is not None else "unknown",
        int(current_gw.max()) if not current_gw.isna().all() else "N/A",
    )
    return latest_rows.reset_index(drop=True)

