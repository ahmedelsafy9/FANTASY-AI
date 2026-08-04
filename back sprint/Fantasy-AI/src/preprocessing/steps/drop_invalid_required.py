"""Preprocessing step that drops rows missing required, non-nullable columns."""

from __future__ import annotations

import pandas as pd

from src.config.logging_config import get_logger
from src.preprocessing.steps.base import PreprocessingStep, StepSummary

logger = get_logger(__name__)


class DropInvalidRequiredRowsStep(PreprocessingStep):
    """Drops rows that are missing a value in any required column.

    A row missing its season, player identifier, or target variable
    cannot be usefully cleaned or imputed — it is dropped outright
    rather than carried forward with a fabricated value.

    Args:
        required_columns: Columns that must be non-null for a row to
            be kept.
    """

    def __init__(self, required_columns: tuple[str, ...]) -> None:
        self._required_columns = required_columns

    @property
    def name(self) -> str:
        """A short, human-readable identifier for this step."""
        return "drop_invalid_required_rows"

    def apply(self, data: pd.DataFrame) -> tuple[pd.DataFrame, StepSummary]:
        """Drop rows with a missing value in any required column.

        Args:
            data: The DataFrame to filter.

        Returns:
            tuple[pd.DataFrame, StepSummary]: Filtered data and a
            summary of how many rows were removed.
        """
        rows_before = len(data)
        available_required = [c for c in self._required_columns if c in data.columns]

        cleaned = (
            data.dropna(subset=available_required) if available_required else data.copy()
        )
        cleaned = cleaned.reset_index(drop=True)
        rows_after = len(cleaned)

        summary = StepSummary(
            step_name=self.name,
            rows_before=rows_before,
            rows_after=rows_after,
            description=(
                f"Dropped {rows_before - rows_after} row(s) missing a required "
                f"value in {available_required}."
            ),
        )
        logger.info(summary.description)
        return cleaned, summary
