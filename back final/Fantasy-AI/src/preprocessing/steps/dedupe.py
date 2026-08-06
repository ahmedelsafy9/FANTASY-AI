"""Preprocessing step that removes duplicate rows."""

from __future__ import annotations

import pandas as pd

from src.config.logging_config import get_logger
from src.preprocessing.steps.base import PreprocessingStep, StepSummary

logger = get_logger(__name__)


class DropDuplicatesStep(PreprocessingStep):
    """Removes fully duplicate rows and duplicate logical-key rows.

    Args:
        key_columns: Columns that, together, should uniquely identify
            a row (e.g. ``("season", "name", "GW")``). Only the subset
            of these columns actually present in the data is used.
    """

    def __init__(self, key_columns: tuple[str, ...]) -> None:
        self._key_columns = key_columns

    @property
    def name(self) -> str:
        """A short, human-readable identifier for this step."""
        return "drop_duplicates"

    def apply(self, data: pd.DataFrame) -> tuple[pd.DataFrame, StepSummary]:
        """Drop fully duplicate rows, then duplicate logical-key rows.

        Args:
            data: The DataFrame to de-duplicate.

        Returns:
            tuple[pd.DataFrame, StepSummary]: De-duplicated data and a
            summary of how many rows were removed.
        """
        rows_before = len(data)
        cleaned = data.drop_duplicates(keep="first")

        available_key_columns = [c for c in self._key_columns if c in cleaned.columns]
        if available_key_columns:
            cleaned = cleaned.drop_duplicates(subset=available_key_columns, keep="first")

        cleaned = cleaned.reset_index(drop=True)
        rows_after = len(cleaned)

        summary = StepSummary(
            step_name=self.name,
            rows_before=rows_before,
            rows_after=rows_after,
            description=(
                f"Removed {rows_before - rows_after} duplicate row(s) "
                f"(full-row and key columns {available_key_columns})."
            ),
        )
        logger.info(summary.description)
        return cleaned, summary
