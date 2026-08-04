"""Merges newly ingested live-API Gameweek rows into the historical dataset.

The live FPL API and the Vaastav historical repository don't share an
identical schema (the live API's stat field names mostly overlap, but
Vaastav's merged files carry extra derived columns the live API
doesn't expose, and vice versa). Rather than forcing an exact column
match, this merge takes the same permissive approach
``VaastavDataSource.load()`` already uses to combine seasons with
differing columns: concatenate and let non-overlapping columns become
``NaN`` — every downstream layer (preprocessing, feature engineering)
already tolerates missing columns gracefully, so this is consistent
with the rest of the codebase rather than a special case.
"""

from __future__ import annotations

import pandas as pd

from src.config.logging_config import get_logger

logger = get_logger(__name__)


def append_live_gameweek(
    historical: pd.DataFrame,
    live: pd.DataFrame,
    duplicate_key_columns: tuple[str, ...],
) -> pd.DataFrame:
    """Append live-API rows to the historical dataset, replacing any overlap.

    If the live data includes a Gameweek that's already present in the
    historical data (e.g. this pipeline ran twice against the same
    Gameweek), the live version wins — it's the freshest source of
    truth for the current season.

    Args:
        historical: The existing merged historical dataset.
        live: Newly fetched live-API rows (from
            ``FPLApiDataSource.load()``).
        duplicate_key_columns: Columns identifying a unique match
            (e.g. ``("season", "element", "GW")``); only the subset
            present in both frames is used.

    Returns:
        pd.DataFrame: The combined dataset, with live rows taking
        precedence over any historical duplicate.
    """
    if live.empty:
        logger.info("No live rows to append; returning historical data unchanged.")
        return historical

    combined = pd.concat([historical, live], ignore_index=True, sort=False)

    available_key_columns = [
        c for c in duplicate_key_columns if c in historical.columns and c in live.columns
    ]
    if available_key_columns:
        # Keep last occurrence: live rows were concatenated after historical
        # rows, so a duplicate key resolves in favor of the live version.
        combined = combined.drop_duplicates(subset=available_key_columns, keep="last")
    else:
        logger.warning(
            "No shared key columns among %s; appending without de-duplication.",
            duplicate_key_columns,
        )

    combined = combined.reset_index(drop=True)
    logger.info(
        "Appended %d live row(s) to %d historical row(s) -> %d total row(s).",
        len(live),
        len(historical),
        len(combined),
    )
    return combined
