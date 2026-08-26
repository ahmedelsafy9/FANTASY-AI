"""Feature step deriving fixture difficulty via team attack & defence strength.

Uses match-level score columns (``team_h_score``, ``team_a_score``) to
compute per-team goals-for and goals-against rates, then maps these onto
both the player's team and the opponent to produce directional fixture
difficulty signals.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from src.config.logging_config import get_logger
from src.feature_engineering.models import FeatureStepSummary
from src.feature_engineering.steps._common import chronological_sort_key
from src.feature_engineering.steps.base import FeatureStep

logger = get_logger(__name__)


class FixtureDifficultyStep(FeatureStep):
    """Derives attack/defence strength ratings and fixture difficulty.

    For each ``(team, season, GW)`` match, we derive:

    - **team_goals_for**: Goals scored by the team in that match
      (``team_h_score`` if home, ``team_a_score`` if away).
    - **team_goals_against**: Goals conceded by the team in that match.

    From these match-level values we compute per-team, per-season
    expanding means with a ``shift(1)`` lag (so GW *n*'s rating
    reflects only GW 1..n−1):

    - ``team_attack_strength``: Expanding mean of team's goals scored.
    - ``team_defence_strength``: Expanding mean of team's goals conceded.
    - ``opponent_attack_strength``: The opponent's attack strength rating.
    - ``opponent_defence_strength``: The opponent's defence strength rating.
    - ``fixture_difficulty``: ``opponent_attack_strength − opponent_defence_strength``.
    - ``clean_sheet_likelihood``: ``1 / (1 + opponent_attack_strength) * (1 / (1 + team_defence_strength))``.

    Args:
        team_column: Column identifying the player's own team.
        opponent_column: Column identifying the opponent faced.
        home_column: Boolean column indicating home (True) / away (False).
        chronological_columns: Candidate columns defining match order.
        team_h_score_column: Column with the home team's match goals.
        team_a_score_column: Column with the away team's match goals.
    """

    def __init__(
        self,
        team_column: str,
        opponent_column: str,
        home_column: str,
        chronological_columns: tuple[str, ...],
        team_h_score_column: str = "team_h_score",
        team_a_score_column: str = "team_a_score",
    ) -> None:
        self._team_column = team_column
        self._opponent_column = opponent_column
        self._home_column = home_column
        self._chronological_columns = chronological_columns
        self._team_h_score_column = team_h_score_column
        self._team_a_score_column = team_a_score_column

    @property
    def name(self) -> str:
        """A short, human-readable identifier for this step."""
        return "fixture_difficulty"

    # ------------------------------------------------------------------ #
    #  Output column names                                                 #
    # ------------------------------------------------------------------ #
    _COL_TEAM_ATTACK = "team_attack_strength"
    _COL_TEAM_DEFENCE = "team_defence_strength"
    _COL_OPP_ATTACK = "opponent_attack_strength"
    _COL_OPP_DEFENCE = "opponent_defence_strength"
    _COL_FIXTURE_DIFF = "fixture_difficulty"
    _COL_CS_LIKELIHOOD = "clean_sheet_likelihood"

    _OUTPUT_COLUMNS = [
        _COL_TEAM_ATTACK,
        _COL_TEAM_DEFENCE,
        _COL_OPP_ATTACK,
        _COL_OPP_DEFENCE,
        _COL_FIXTURE_DIFF,
        _COL_CS_LIKELIHOOD,
    ]

    def apply(self, data: pd.DataFrame) -> tuple[pd.DataFrame, FeatureStepSummary]:
        """Derive fixture difficulty features.

        Args:
            data: The DataFrame to derive features from.

        Returns:
            tuple[pd.DataFrame, FeatureStepSummary]: The data with new
            fixture difficulty columns added.
        """
        rows_before = len(data)
        working = data.copy()
        sort_columns = chronological_sort_key(working, self._chronological_columns)

        # ---- prerequisite check ---- #
        required = (
            self._team_column,
            self._opponent_column,
            self._home_column,
            self._team_h_score_column,
            self._team_a_score_column,
            *sort_columns,
        )
        missing = [c for c in required if c not in working.columns]
        if missing:
            logger.warning(
                "Cannot compute fixture difficulty; missing column(s): %s.", missing
            )
            for col in self._OUTPUT_COLUMNS:
                working[col] = pd.NA
            return working, FeatureStepSummary(
                step_name=self.name,
                rows_before=rows_before,
                rows_after=len(working),
                columns_added=list(self._OUTPUT_COLUMNS),
                description=f"Missing prerequisite column(s) {missing}; outputs are NaN.",
            )

        # ---- 1. Derive match-level goals for / against per team ---- #
        # Collapse to one row per (team, season, GW) match.
        match_group_cols = [self._team_column, *sort_columns]
        is_home = working[self._home_column].astype(bool)

        working["__goals_for__"] = np.where(
            is_home,
            pd.to_numeric(working[self._team_h_score_column], errors="coerce"),
            pd.to_numeric(working[self._team_a_score_column], errors="coerce"),
        )
        working["__goals_against__"] = np.where(
            is_home,
            pd.to_numeric(working[self._team_a_score_column], errors="coerce"),
            pd.to_numeric(working[self._team_h_score_column], errors="coerce"),
        )

        # One row per match: take the first (all rows in the same match
        # share the same team_h_score / team_a_score / was_home).
        match_table = (
            working.groupby(match_group_cols, dropna=False)[
                ["__goals_for__", "__goals_against__"]
            ]
            .first()
            .reset_index()
        )

        # ---- 2. Expanding mean with shift(1) per team ---- #
        match_table = match_table.sort_values(
            by=[self._team_column, *sort_columns], kind="mergesort"
        )

        for src, dst in [
            ("__goals_for__", self._COL_TEAM_ATTACK),
            ("__goals_against__", self._COL_TEAM_DEFENCE),
        ]:
            match_table[dst] = match_table.groupby(self._team_column)[src].transform(
                lambda s: s.shift(1).expanding().mean()
            )

        # ---- 3. Build lookup and merge team ratings ---- #
        strength_lookup = match_table[
            [self._team_column, *sort_columns, self._COL_TEAM_ATTACK, self._COL_TEAM_DEFENCE]
        ]

        # Merge team's own ratings.
        working = working.merge(
            strength_lookup,
            on=[self._team_column, *sort_columns],
            how="left",
        )

        # ---- 4. Opponent ratings via rename + merge ---- #
        opponent_available = self._opponent_column in working.columns
        if opponent_available:
            team_values = set(working[self._team_column].dropna().unique())
            opponent_values = set(working[self._opponent_column].dropna().unique())
            overlap = len(team_values & opponent_values) / max(1, len(opponent_values))

            if overlap >= 0.5:
                opponent_lookup = strength_lookup.rename(
                    columns={
                        self._team_column: self._opponent_column,
                        self._COL_TEAM_ATTACK: self._COL_OPP_ATTACK,
                        self._COL_TEAM_DEFENCE: self._COL_OPP_DEFENCE,
                    }
                )
                working = working.merge(
                    opponent_lookup,
                    on=[self._opponent_column, *sort_columns],
                    how="left",
                )
            else:
                logger.warning(
                    "Skipping opponent fixture difficulty: team/opponent domain "
                    "overlap %.1f%% < 50%%.",
                    overlap * 100,
                )
                working[self._COL_OPP_ATTACK] = pd.NA
                working[self._COL_OPP_DEFENCE] = pd.NA
        else:
            logger.warning(
                "Skipping opponent fixture difficulty: '%s' column missing.",
                self._opponent_column,
            )
            working[self._COL_OPP_ATTACK] = pd.NA
            working[self._COL_OPP_DEFENCE] = pd.NA

        # ---- 5. Composite features ---- #
        opp_atk = pd.to_numeric(working[self._COL_OPP_ATTACK], errors="coerce")
        opp_def = pd.to_numeric(working[self._COL_OPP_DEFENCE], errors="coerce")
        team_def = pd.to_numeric(working[self._COL_TEAM_DEFENCE], errors="coerce")

        working[self._COL_FIXTURE_DIFF] = opp_atk - opp_def
        working[self._COL_CS_LIKELIHOOD] = (1.0 / (1.0 + opp_atk)) * (
            1.0 / (1.0 + team_def)
        )

        # ---- cleanup ---- #
        working.drop(columns=["__goals_for__", "__goals_against__"], inplace=True)
        working.index = data.index

        columns_added = [c for c in self._OUTPUT_COLUMNS if c in working.columns]
        description = (
            f"Added {len(columns_added)} fixture difficulty column(s)."
        )
        logger.info(description)

        return working, FeatureStepSummary(
            step_name=self.name,
            rows_before=rows_before,
            rows_after=len(working),
            columns_added=columns_added,
            description=description,
        )
