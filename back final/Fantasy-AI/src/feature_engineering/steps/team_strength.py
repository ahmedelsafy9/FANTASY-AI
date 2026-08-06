"""Feature step deriving team and opponent strength ratings."""

from __future__ import annotations

import pandas as pd

from src.config.logging_config import get_logger
from src.feature_engineering.models import FeatureStepSummary
from src.feature_engineering.steps._common import chronological_sort_key
from src.feature_engineering.steps.base import FeatureStep

logger = get_logger(__name__)


class TeamStrengthStep(FeatureStep):
    """Derives data-driven team and opponent strength ratings.

    A team's "strength" is proxied by the average per-player output of
    ``strength_source_column`` (e.g. ``total_points``) across that
    team's squad in each Gameweek, expanded chronologically and
    shifted by one Gameweek so a row's strength reflects the team's
    form *before* that match — never the outcome of the match itself.

    ``opponent_strength`` looks up the same rating for whichever team
    is listed in ``opponent_column``. This only works if ``team_column``
    and ``opponent_column`` share the same value domain (e.g. both are
    team names, or both are the same team-ID scheme) — a domain
    compatibility check guards against silently joining on
    incompatible columns (e.g. names vs numeric IDs), which some
    historical seasons use inconsistently.

    Args:
        team_column: Column identifying the player's own team.
        opponent_column: Column identifying the opponent faced.
        strength_source_column: Per-player stat used as the strength proxy.
        chronological_columns: Candidate columns defining match order.
        team_output_column: Name of the team-strength output column.
        opponent_output_column: Name of the opponent-strength output column.
        min_domain_overlap: Minimum fraction of ``opponent_column``
            values that must also appear in ``team_column`` for the
            opponent join to be considered safe.
    """

    def __init__(
        self,
        team_column: str,
        opponent_column: str,
        strength_source_column: str,
        chronological_columns: tuple[str, ...],
        team_output_column: str = "team_strength",
        opponent_output_column: str = "opponent_strength",
        min_domain_overlap: float = 0.5,
    ) -> None:
        self._team_column = team_column
        self._opponent_column = opponent_column
        self._strength_source_column = strength_source_column
        self._chronological_columns = chronological_columns
        self._team_output_column = team_output_column
        self._opponent_output_column = opponent_output_column
        self._min_domain_overlap = min_domain_overlap

    @property
    def name(self) -> str:
        """A short, human-readable identifier for this step."""
        return "team_opponent_strength"

    def apply(self, data: pd.DataFrame) -> tuple[pd.DataFrame, FeatureStepSummary]:
        """Derive team and (where safe) opponent strength ratings.

        Args:
            data: The DataFrame to derive features from.

        Returns:
            tuple[pd.DataFrame, FeatureStepSummary]: The data with new
            strength columns added.
        """
        rows_before = len(data)
        working = data.copy()
        sort_columns = chronological_sort_key(working, self._chronological_columns)

        required = (self._team_column, self._strength_source_column, *sort_columns)
        missing_required = [c for c in required if c not in working.columns]
        if missing_required:
            logger.warning(
                "Cannot compute team strength; missing column(s): %s.", missing_required
            )
            working[self._team_output_column] = pd.NA
            working[self._opponent_output_column] = pd.NA
            return working, FeatureStepSummary(
                step_name=self.name,
                rows_before=rows_before,
                rows_after=len(working),
                columns_added=[self._team_output_column, self._opponent_output_column],
                description=f"Missing prerequisite column(s) {missing_required}; outputs are NaN.",
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
        team_gw_table[self._team_output_column] = (
            team_gw_table.groupby(self._team_column)["__team_gw_score__"]
            .apply(lambda s: s.shift(1).expanding().mean())
            .reset_index(level=0, drop=True)
        )

        strength_lookup = team_gw_table[
            [self._team_column, *sort_columns, self._team_output_column]
        ]

        working = working.merge(
            strength_lookup,
            on=[self._team_column, *sort_columns],
            how="left",
        )

        opponent_available = self._opponent_column in data.columns
        domain_compatible = False
        if opponent_available:
            team_values = set(working[self._team_column].dropna().unique())
            opponent_values = set(working[self._opponent_column].dropna().unique())
            overlap = len(team_values & opponent_values) / max(1, len(opponent_values))
            domain_compatible = overlap >= self._min_domain_overlap

        if not opponent_available or not domain_compatible:
            reason = (
                f"'{self._opponent_column}' column missing"
                if not opponent_available
                else (
                    f"'{self._team_column}' and '{self._opponent_column}' do not share a "
                    "compatible value domain (opponent likely uses a different ID scheme)"
                )
            )
            logger.warning("Skipping opponent_strength: %s.", reason)
            working[self._opponent_output_column] = pd.NA
            description = (
                f"Derived '{self._team_output_column}'. Skipped "
                f"'{self._opponent_output_column}': {reason}."
            )
        else:
            opponent_lookup = strength_lookup.rename(
                columns={
                    self._team_column: self._opponent_column,
                    self._team_output_column: self._opponent_output_column,
                }
            )
            working = working.merge(
                opponent_lookup, on=[self._opponent_column, *sort_columns], how="left"
            )
            description = (
                f"Derived '{self._team_output_column}' and '{self._opponent_output_column}'."
            )

        working.index = data.index
        summary = FeatureStepSummary(
            step_name=self.name,
            rows_before=rows_before,
            rows_after=len(working),
            columns_added=[self._team_output_column, self._opponent_output_column],
            description=description,
        )
        logger.info(summary.description)
        return working, summary
