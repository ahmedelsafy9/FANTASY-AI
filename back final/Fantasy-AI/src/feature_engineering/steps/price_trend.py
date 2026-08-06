"""Feature step deriving player price trend features."""

from __future__ import annotations

import pandas as pd

from src.config.logging_config import get_logger
from src.feature_engineering.models import FeatureStepSummary
from src.feature_engineering.steps._common import chronological_sort_key, resolve_column
from src.feature_engineering.steps.base import FeatureStep

logger = get_logger(__name__)


class PriceTrendStep(FeatureStep):
    """Derives price-change features over configurable lookback windows.

    For each window ``w``, adds ``price_trend_last_{w}`` representing
    the change in a player's price compared to ``w`` matches ago
    (positive = price has risen). A player's first ``w`` matches have
    no prior price to compare against and are filled with ``0``
    (no observed trend yet).

    Args:
        player_id_columns: Candidate columns identifying a player, in
            priority order.
        chronological_columns: Candidate columns defining match order.
        value_column: Column holding the player's price at each match.
        windows: Lookback windows (in matches) to compute price change
            over.
    """

    def __init__(
        self,
        player_id_columns: tuple[str, ...],
        chronological_columns: tuple[str, ...],
        value_column: str,
        windows: tuple[int, ...],
    ) -> None:
        self._player_id_columns = player_id_columns
        self._chronological_columns = chronological_columns
        self._value_column = value_column
        self._windows = windows

    @property
    def name(self) -> str:
        """A short, human-readable identifier for this step."""
        return "price_trend"

    def apply(self, data: pd.DataFrame) -> tuple[pd.DataFrame, FeatureStepSummary]:
        """Derive price-trend features for each configured window.

        Args:
            data: The DataFrame to derive features from.

        Returns:
            tuple[pd.DataFrame, FeatureStepSummary]: The data with new
            price-trend columns added.
        """
        rows_before = len(data)
        working = data.copy()
        player_id_column = resolve_column(self._player_id_columns, working)
        sort_columns = chronological_sort_key(working, self._chronological_columns)
        output_columns = [f"price_trend_last_{w}" for w in self._windows]

        if player_id_column is None or self._value_column not in working.columns:
            missing = [
                item
                for item, present in (
                    ("player identifier", player_id_column is not None),
                    (self._value_column, self._value_column in working.columns),
                )
                if not present
            ]
            logger.warning(
                "Cannot compute price trend; missing: %s. Outputs filled with 0.", missing
            )
            for column in output_columns:
                working[column] = 0
            return working, FeatureStepSummary(
                step_name=self.name,
                rows_before=rows_before,
                rows_after=len(working),
                columns_added=output_columns,
                description=f"Missing prerequisite column(s) {missing}; outputs filled with 0.",
            )

        working["__original_order__"] = range(len(working))
        sort_by = [player_id_column, *sort_columns]
        working = working.sort_values(by=sort_by, kind="mergesort")

        numeric_value = pd.to_numeric(working[self._value_column], errors="coerce")
        grouped = numeric_value.groupby(working[player_id_column])

        for window, column in zip(self._windows, output_columns):
            shifted = grouped.transform(lambda s, w=window: s.shift(w))
            working[column] = (numeric_value - shifted).fillna(0)

        working = working.sort_values(by="__original_order__", kind="mergesort")
        working = working.drop(columns="__original_order__")
        working.index = data.index

        summary = FeatureStepSummary(
            step_name=self.name,
            rows_before=rows_before,
            rows_after=len(working),
            columns_added=output_columns,
            description=f"Derived price trend column(s): {output_columns}.",
        )
        logger.info(summary.description)
        return working, summary
