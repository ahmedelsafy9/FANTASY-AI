"""Preprocessing step that fills missing values in known-zero-meaning columns."""

from __future__ import annotations

import pandas as pd

from src.config.logging_config import get_logger
from src.preprocessing.steps.base import PreprocessingStep, StepSummary

logger = get_logger(__name__)


class FillMissingValuesStep(PreprocessingStep):
    """Fills missing values in columns where "missing" means "zero occurrences".

    Many FPL stat columns (goals, assists, bonus points, minutes, ...)
    are absent from a row precisely because the event did not happen —
    not because the value is unknown. For those columns, a missing
    value is safely filled with ``0``. Any other column is left
    untouched, since imputing an unknown value with 0 would be
    misleading (e.g. a price or a rolling average).

    Args:
        zero_fill_columns: Columns where missing values should be
            filled with ``0``.
    """

    def __init__(self, zero_fill_columns: tuple[str, ...]) -> None:
        self._zero_fill_columns = zero_fill_columns

    @property
    def name(self) -> str:
        """A short, human-readable identifier for this step."""
        return "fill_missing_values"

    def apply(self, data: pd.DataFrame) -> tuple[pd.DataFrame, StepSummary]:
        """Fill missing values in configured zero-fill columns.

        Args:
            data: The DataFrame to fill.

        Returns:
            tuple[pd.DataFrame, StepSummary]: The filled data and a
            summary of how many cells were filled, per column.
        """
        rows_before = len(data)
        cleaned = data.copy()

        fill_counts: dict[str, int] = {}
        for column in self._zero_fill_columns:
            if column not in cleaned.columns:
                continue
            missing_count = int(cleaned[column].isna().sum())
            if missing_count == 0:
                continue
            cleaned[column] = cleaned[column].fillna(0)
            fill_counts[column] = missing_count

        summary = StepSummary(
            step_name=self.name,
            rows_before=rows_before,
            rows_after=len(cleaned),
            description=f"Filled missing values with 0 in: {fill_counts}.",
        )
        logger.info(summary.description)
        return cleaned, summary
