"""Shared helpers used by multiple feature engineering steps.

Kept private to the ``feature_engineering`` package (leading
underscore) since these are implementation details, not part of the
public step interface.
"""

from __future__ import annotations

import pandas as pd

from src.config.logging_config import get_logger

logger = get_logger(__name__)


def resolve_column(candidates: tuple[str, ...], data: pd.DataFrame) -> str | None:
    """Return the first candidate column name present in ``data``.

    Args:
        candidates: Candidate column names, in priority order.
        data: The DataFrame to search.

    Returns:
        str | None: The first matching column name, or ``None`` if
        none of the candidates are present.
    """
    return next((c for c in candidates if c in data.columns), None)


def chronological_sort_key(
    data: pd.DataFrame, chronological_columns: tuple[str, ...]
) -> pd.DataFrame:
    """Build a sortable key DataFrame for the available chronological columns.

    Args:
        data: The DataFrame the key is derived from.
        chronological_columns: Candidate columns defining match order
            (e.g. ``("season", "GW")``). Only columns actually present
            are used.

    Returns:
        pd.DataFrame: A DataFrame of just the available chronological
        columns, suitable for passing to ``sort_values(by=...)``.
    """
    available = [c for c in chronological_columns if c in data.columns]
    if not available:
        logger.warning(
            "None of the chronological columns %s are present; falling back to "
            "original row order.",
            chronological_columns,
        )
    return available
