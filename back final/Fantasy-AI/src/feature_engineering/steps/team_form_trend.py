"""Feature step deriving a team's short-vs-long-term form trend.

New for Phase 1 (fixture-aware prediction engine): while
``TeamStrengthStep`` (Sprint 5) captures a team's overall expanding-mean
strength, it doesn't distinguish "always been strong" from "strong
lately" — a team on a hot or cold streak. This step fills that gap with
a compact trend signal: the difference between a team's short-window
and long-window rolling average of the same per-Gameweek strength
proxy used by ``TeamStrengthStep``.
"""

from __future__ import annotations

import pandas as pd

from src.config.logging_config import get_logger
from src.feature_engineering.models import FeatureStepSummary
from src.feature_engineering.steps._common import chronological_sort_key
from src.feature_engineering.steps.base import FeatureStep

logger = get_logger(__name__)


class TeamFormTrendStep(FeatureStep):
    """Derives ``team_form_trend`` = short-window minus long-window team form.

    Positive values indicate a team performing better recently than
    over its longer-term baseline (improving form); negative values
    indicate the opposite. Like ``TeamStrengthStep``, this is computed
    from prior Gameweeks only — each row's trend reflects the team's
    form *entering* that match, with the match's own outcome excluded
    via ``shift(1)``.

    Args:
        team_column: Column identifying the player's own team.
        strength_source_column: Per-player stat used as the strength proxy
            (should match ``TeamStrengthStep``'s configuration for
            consistency).
        chronological_columns: Candidate columns defining match order.
        short_window: Number of recent Gameweeks for the "recent form" average.
        long_window: Number of recent Gameweeks for the "baseline form" average.
        output_column: Name of the output column.
    """

    def __init__(
        self,
        team_column: str,
        strength_source_column: str,
        chronological_columns: tuple[str, ...],
        short_window: int,
        long_window: int,
        output_column: str = "team_form_trend",
    ) -> None:
        self._team_column = team_column
        self._strength_source_column = strength_source_column
        self._chronological_columns = chronological_columns
        self._short_window = short_window
        self._long_window = long_window
        self._output_column = output_column

    @property
    def name(self) -> str:
        """A short, human-readable identifier for this step."""
        return "team_form_trend"

    def apply(self, data: pd.DataFrame) -> tuple[pd.DataFrame, FeatureStepSummary]:
        """Derive the team form-trend feature.

        Args:
            data: The DataFrame to derive features from.

        Returns:
            tuple[pd.DataFrame, FeatureStepSummary]: The data with the
            new trend column added.
        """
        rows_before = len(data)
        working = data.copy()
        sort_columns = chronological_sort_key(working, self._chronological_columns)

        required = (self._team_column, self._strength_source_column, *sort_columns)
        missing_required = [c for c in required if c not in working.columns]
        if missing_required:
            logger.warning(
                "Cannot compute team form trend; missing column(s): %s.", missing_required
            )
            working[self._output_column] = pd.NA
            return working, FeatureStepSummary(
                step_name=self.name,
                rows_before=rows_before,
                rows_after=len(working),
                columns_added=[self._output_column],
                description=f"Missing prerequisite column(s) {missing_required}; output is NaN.",
            )

        team_gw_group_cols = [self._team_column, *sort_columns]
        team_gw_table = (
            working.groupby(team_gw_group_cols, dropna=False)[self._strength_source_column]
            .mean()
            .reset_index()
            .rename(columns={self._strength_source_column: "__team_gw_score__"})
        )
        team_gw_table = team_gw_table.sort_values(
            by=[self._team_column, *sort_columns], kind="mergesort"
        )

        grouped_shifted = team_gw_table.groupby(self._team_column)["__team_gw_score__"].shift(1)
        short_avg = grouped_shifted.groupby(team_gw_table[self._team_column]).transform(
            lambda s: s.rolling(window=self._short_window, min_periods=1).mean()
        )
        long_avg = grouped_shifted.groupby(team_gw_table[self._team_column]).transform(
            lambda s: s.rolling(window=self._long_window, min_periods=1).mean()
        )
        team_gw_table[self._output_column] = short_avg - long_avg

        lookup = team_gw_table[[self._team_column, *sort_columns, self._output_column]]
        working = working.merge(lookup, on=[self._team_column, *sort_columns], how="left")
        working.index = data.index

        summary = FeatureStepSummary(
            step_name=self.name,
            rows_before=rows_before,
            rows_after=len(working),
            columns_added=[self._output_column],
            description=(
                f"Derived '{self._output_column}' (last {self._short_window} vs "
                f"last {self._long_window} Gameweeks, shift(1)-lagged)."
            ),
        )
        logger.info(summary.description)
        return working, summary
