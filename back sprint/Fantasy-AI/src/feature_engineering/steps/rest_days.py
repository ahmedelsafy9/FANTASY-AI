"""Feature step deriving days of rest since a player's previous match."""

from __future__ import annotations

import pandas as pd

from src.config.logging_config import get_logger
from src.feature_engineering.models import FeatureStepSummary
from src.feature_engineering.steps._common import resolve_column
from src.feature_engineering.steps.base import FeatureStep

logger = get_logger(__name__)


class RestDaysStep(FeatureStep):
    """Derives the number of days since a player's previous match.

    Args:
        player_id_columns: Candidate columns identifying a player, in
            priority order.
        kickoff_time_column: Column holding each match's kickoff
            timestamp (must be datetime-typed, as produced by the
            preprocessing layer's ``ConvertTypesStep``).
        default_rest_days: Value used for a player's first known match
            (no prior match to compare against) and for any negative
            or otherwise invalid gap.
        output_column: Name of the output column.
    """

    def __init__(
        self,
        player_id_columns: tuple[str, ...],
        kickoff_time_column: str,
        default_rest_days: int,
        output_column: str = "rest_days",
    ) -> None:
        self._player_id_columns = player_id_columns
        self._kickoff_time_column = kickoff_time_column
        self._default_rest_days = default_rest_days
        self._output_column = output_column

    @property
    def name(self) -> str:
        """A short, human-readable identifier for this step."""
        return "rest_days"

    def apply(self, data: pd.DataFrame) -> tuple[pd.DataFrame, FeatureStepSummary]:
        """Derive days of rest since each player's previous match.

        Args:
            data: The DataFrame to derive the feature from.

        Returns:
            tuple[pd.DataFrame, FeatureStepSummary]: The data with the
            new rest-days column added.
        """
        rows_before = len(data)
        working = data.copy()
        player_id_column = resolve_column(self._player_id_columns, working)

        if player_id_column is None or self._kickoff_time_column not in working.columns:
            missing = [
                item
                for item, present in (
                    ("player identifier", player_id_column is not None),
                    (self._kickoff_time_column, self._kickoff_time_column in working.columns),
                )
                if not present
            ]
            logger.warning(
                "Cannot compute rest days; missing: %s. Output filled with default (%d).",
                missing,
                self._default_rest_days,
            )
            working[self._output_column] = self._default_rest_days
            description = f"Missing prerequisite column(s) {missing}; filled with default."
        else:
            kickoff = pd.to_datetime(working[self._kickoff_time_column], errors="coerce", utc=True)
            working["__original_order__"] = range(len(working))
            sorted_working = working.assign(__kickoff__=kickoff).sort_values(
                by=[player_id_column, "__kickoff__"], kind="mergesort"
            )
            gap_days = (
                sorted_working.groupby(player_id_column)["__kickoff__"]
                .diff()
                .dt.total_seconds()
                / 86400.0
            )
            sorted_working[self._output_column] = gap_days
            sorted_working = sorted_working.sort_values(
                by="__original_order__", kind="mergesort"
            )
            working = sorted_working.drop(columns=["__original_order__", "__kickoff__"])
            working.index = data.index

            invalid_mask = working[self._output_column].isna() | (
                working[self._output_column] < 0
            )
            invalid_count = int(invalid_mask.sum())
            working.loc[invalid_mask, self._output_column] = self._default_rest_days
            working[self._output_column] = working[self._output_column].round().astype("Int64")

            description = (
                f"Derived '{self._output_column}' from '{self._kickoff_time_column}' "
                f"({invalid_count} row(s) filled with default {self._default_rest_days})."
            )

        summary = FeatureStepSummary(
            step_name=self.name,
            rows_before=rows_before,
            rows_after=len(working),
            columns_added=[self._output_column],
            description=description,
        )
        logger.info(summary.description)
        return working, summary
