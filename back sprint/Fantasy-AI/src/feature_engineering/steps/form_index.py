"""Feature step deriving a composite recency-weighted form index."""

from __future__ import annotations

import pandas as pd

from src.config.logging_config import get_logger
from src.feature_engineering.models import FeatureStepSummary
from src.feature_engineering.steps.base import FeatureStep

logger = get_logger(__name__)


class FormIndexStep(FeatureStep):
    """Derives a single composite "form index" from existing rolling averages.

    Combines rolling-average columns (typically ``total_points_avg_last_3``,
    ``..._5``, ``..._10`` produced by :class:`~src.feature_engineering.steps.rolling_stats.RollingAverageStep`)
    into one recency-weighted score, so downstream models have a
    single "how hot is this player right now" feature without having
    to learn the weighting themselves.

    This step must run *after* :class:`RollingAverageStep` in the
    pipeline — if a required component column is missing, the index
    degrades gracefully by re-normalizing weights over whichever
    components are actually present, rather than failing outright.

    Args:
        component_columns: The rolling-average columns to combine, in
            the same order as ``weights``.
        weights: Weight for each component column. Renormalized over
            whichever components are actually present in the data.
        output_column: Name of the output column.
    """

    def __init__(
        self,
        component_columns: tuple[str, ...],
        weights: tuple[float, ...],
        output_column: str = "form_index",
    ) -> None:
        if len(component_columns) != len(weights):
            raise ValueError("component_columns and weights must be the same length.")
        self._component_columns = component_columns
        self._weights = weights
        self._output_column = output_column

    @property
    def name(self) -> str:
        """A short, human-readable identifier for this step."""
        return "form_index"

    def apply(self, data: pd.DataFrame) -> tuple[pd.DataFrame, FeatureStepSummary]:
        """Derive the composite form index from available rolling averages.

        Args:
            data: The DataFrame to derive the feature from.

        Returns:
            tuple[pd.DataFrame, FeatureStepSummary]: The data with the
            new form-index column added.
        """
        rows_before = len(data)
        working = data.copy()

        available_pairs = [
            (column, weight)
            for column, weight in zip(self._component_columns, self._weights)
            if column in working.columns
        ]

        if not available_pairs:
            logger.warning(
                "None of the form-index component columns %s are present; "
                "output will be NaN. Ensure RollingAverageStep runs before FormIndexStep.",
                self._component_columns,
            )
            working[self._output_column] = pd.NA
            description = (
                f"No component columns present among {self._component_columns}; output is NaN."
            )
        else:
            total_weight = sum(weight for _, weight in available_pairs)
            working[self._output_column] = sum(
                pd.to_numeric(working[column], errors="coerce").fillna(0) * (weight / total_weight)
                for column, weight in available_pairs
            )
            missing = [c for c in self._component_columns if c not in working.columns]
            description = f"Derived '{self._output_column}' from {[c for c, _ in available_pairs]}."
            if missing:
                description += f" (missing and excluded: {missing})"

        summary = FeatureStepSummary(
            step_name=self.name,
            rows_before=rows_before,
            rows_after=len(working),
            columns_added=[self._output_column],
            description=description,
        )
        logger.info(summary.description)
        return working, summary
