"""Feature step deriving a numeric home/away flag."""

from __future__ import annotations

import pandas as pd

from src.config.logging_config import get_logger
from src.feature_engineering.models import FeatureStepSummary
from src.feature_engineering.steps.base import FeatureStep

logger = get_logger(__name__)


class HomeAwayFlagStep(FeatureStep):
    """Derives a numeric ``is_home`` feature from a boolean/text home column.

    Args:
        source_column: Column indicating whether the match was played
            at home (boolean, or a boolean-like string/number).
        output_column: Name of the numeric (0/1) output column.
    """

    def __init__(self, source_column: str, output_column: str = "is_home") -> None:
        self._source_column = source_column
        self._output_column = output_column

    @property
    def name(self) -> str:
        """A short, human-readable identifier for this step."""
        return "home_away_flag"

    def apply(self, data: pd.DataFrame) -> tuple[pd.DataFrame, FeatureStepSummary]:
        """Derive the numeric home/away flag.

        Args:
            data: The DataFrame to derive the feature from.

        Returns:
            tuple[pd.DataFrame, FeatureStepSummary]: The data with the
            new flag column added.
        """
        rows_before = len(data)
        working = data.copy()

        if self._source_column not in working.columns:
            logger.warning(
                "Source column '%s' not found; %s will be all-NaN.",
                self._source_column,
                self._output_column,
            )
            working[self._output_column] = pd.NA
            description = f"Source column '{self._source_column}' missing; output is NaN."
        else:
            working[self._output_column] = (
                working[self._source_column].astype("boolean").astype("Int64")
            )
            description = f"Derived '{self._output_column}' from '{self._source_column}'."

        summary = FeatureStepSummary(
            step_name=self.name,
            rows_before=rows_before,
            rows_after=len(working),
            columns_added=[self._output_column],
            description=description,
        )
        logger.info(summary.description)
        return working, summary
