"""Feature step deriving rolling-window averages (leakage-free) per player."""

from __future__ import annotations

import pandas as pd

from src.config.logging_config import get_logger
from src.feature_engineering.models import FeatureStepSummary, RollingFeatureSpec
from src.feature_engineering.steps._common import chronological_sort_key, resolve_column
from src.feature_engineering.steps.base import FeatureStep

logger = get_logger(__name__)


class RollingAverageStep(FeatureStep):
    """Derives rolling-window averages for a configurable set of stats.

    For each :class:`RollingFeatureSpec`, this step produces one
    output column per window: ``"{output_name}_avg_last_{window}"``.
    Every rolling average is computed using ``shift(1)`` before the
    rolling window, so a row's feature reflects only *prior* matches —
    never the outcome of the match the row itself represents. This is
    essential to avoid target leakage (a rolling average of
    ``total_points`` that included the current row's own points would
    trivially predict the target).

    Handles a single generic mechanism for every "rolling ___" feature
    requested (points, minutes, BPS, ICT, xG, xA, ...) — a new stat
    only needs a new :class:`RollingFeatureSpec`, not a new step class.

    Args:
        player_id_columns: Candidate columns identifying a player, in
            priority order. The first one present is used to group
            rows.
        chronological_columns: Candidate columns defining match order
            (e.g. ``("season", "GW")``).
        specs: The rolling features to compute.
    """

    def __init__(
        self,
        player_id_columns: tuple[str, ...],
        chronological_columns: tuple[str, ...],
        specs: tuple[RollingFeatureSpec, ...],
    ) -> None:
        self._player_id_columns = player_id_columns
        self._chronological_columns = chronological_columns
        self._specs = specs

    @property
    def name(self) -> str:
        """A short, human-readable identifier for this step."""
        return "rolling_averages"

    def apply(self, data: pd.DataFrame) -> tuple[pd.DataFrame, FeatureStepSummary]:
        """Compute every configured rolling-average feature.

        Args:
            data: The DataFrame to derive features from.

        Returns:
            tuple[pd.DataFrame, FeatureStepSummary]: The data with new
            rolling-average columns added, and a summary of which
            columns were added (and which specs were skipped due to a
            missing source column).
        """
        rows_before = len(data)
        player_id_column = resolve_column(self._player_id_columns, data)
        sort_columns = chronological_sort_key(data, self._chronological_columns)

        if player_id_column is None:
            logger.warning(
                "No player identifier column found among %s; skipping rolling averages.",
                self._player_id_columns,
            )
            columns_added = [
                f"{spec.output_name}_avg_last_{w}" for spec in self._specs for w in spec.windows
            ]
            for column in columns_added:
                data = data.assign(**{column: pd.NA})
            return data, FeatureStepSummary(
                step_name=self.name,
                rows_before=rows_before,
                rows_after=len(data),
                columns_added=columns_added,
                description="No player identifier column available; all outputs are NaN.",
            )

        working = data.copy()
        working["__original_order__"] = range(len(working))
        sort_by = [player_id_column, *sort_columns]
        working = working.sort_values(by=sort_by, kind="mergesort")

        columns_added: list[str] = []
        skipped_specs: list[str] = []

        for spec in self._specs:
            source_column = resolve_column(spec.source_candidates, data)
            if source_column is None:
                skipped_specs.append(spec.output_name)
                for window in spec.windows:
                    output_column = f"{spec.output_name}_avg_last_{window}"
                    working[output_column] = pd.NA
                    columns_added.append(output_column)
                continue

            numeric_source = pd.to_numeric(working[source_column], errors="coerce")
            grouped = numeric_source.groupby(working[player_id_column])
            shifted = grouped.shift(1)

            for window in spec.windows:
                output_column = f"{spec.output_name}_avg_last_{window}"
                working[output_column] = shifted.groupby(working[player_id_column]).transform(
                    lambda s, w=window: s.rolling(window=w, min_periods=1).mean()
                )
                columns_added.append(output_column)

        working = working.sort_values(by="__original_order__", kind="mergesort")
        working = working.drop(columns="__original_order__")
        working.index = data.index

        description = f"Added {len(columns_added)} rolling-average column(s)."
        if skipped_specs:
            description += f" Skipped (no source column found): {skipped_specs}."

        summary = FeatureStepSummary(
            step_name=self.name,
            rows_before=rows_before,
            rows_after=len(working),
            columns_added=columns_added,
            description=description,
        )
        logger.info(summary.description)
        return working, summary
