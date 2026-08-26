"""Feature step deriving attacking contribution, per-90 rates, and goal involvement."""

from __future__ import annotations

import numpy as np
import pandas as pd

from src.config.logging_config import get_logger
from src.feature_engineering.models import FeatureStepSummary
from src.feature_engineering.steps.base import FeatureStep

logger = get_logger(__name__)


class AttackingContributionStep(FeatureStep):
    """Derives normalized attacking contribution and underlying threat features.

    Uses rolling averages from prior matches (which are already strictly
    lagged with ``shift(1)``) to compute per-90 normalized rates and
    team-level goal involvement ratios:

    - ``threat_per_90_last_5``: ``(threat_avg_last_5 / max(minutes_avg_last_5, 1.0)) * 90``
    - ``creativity_per_90_last_5``: ``(creativity_avg_last_5 / max(minutes_avg_last_5, 1.0)) * 90``
    - ``bps_per_90_last_5``: ``(bps_avg_last_5 / max(minutes_avg_last_5, 1.0)) * 90``
    - ``goal_involvement_rate_last_5``: ``(goals_scored_avg_last_5 + assists_avg_last_5) / max(team_attack_strength, 0.1)``
    - ``attacking_threat_index``: Composite of normalized threat and creativity per 90.

    Args:
        threat_col: Prior rolling threat column (e.g. ``threat_avg_last_5``).
        creativity_col: Prior rolling creativity column (e.g. ``creativity_avg_last_5``).
        bps_col: Prior rolling BPS column (e.g. ``bps_avg_last_5``).
        minutes_col: Prior rolling minutes column (e.g. ``minutes_avg_last_5``).
        goals_col: Prior rolling goals scored column (e.g. ``goals_scored_avg_last_5``).
        assists_col: Prior rolling assists column (e.g. ``assists_avg_last_5``).
        team_attack_col: Team attack strength rating column (e.g. ``team_attack_strength``).
    """

    def __init__(
        self,
        threat_col: str = "threat_avg_last_5",
        creativity_col: str = "creativity_avg_last_5",
        bps_col: str = "bps_avg_last_5",
        minutes_col: str = "minutes_avg_last_5",
        goals_col: str = "goals_scored_avg_last_5",
        assists_col: str = "assists_avg_last_5",
        team_attack_col: str = "team_attack_strength",
    ) -> None:
        self._threat_col = threat_col
        self._creativity_col = creativity_col
        self._bps_col = bps_col
        self._minutes_col = minutes_col
        self._goals_col = goals_col
        self._assists_col = assists_col
        self._team_attack_col = team_attack_col

    @property
    def name(self) -> str:
        """A short, human-readable identifier for this step."""
        return "attacking_contribution"

    _COL_THREAT_P90 = "threat_per_90_last_5"
    _COL_CREATIVITY_P90 = "creativity_per_90_last_5"
    _COL_BPS_P90 = "bps_per_90_last_5"
    _COL_GOAL_INVOLVEMENT = "goal_involvement_rate_last_5"
    _COL_THREAT_INDEX = "attacking_threat_index"

    _OUTPUT_COLUMNS = [
        _COL_THREAT_P90,
        _COL_CREATIVITY_P90,
        _COL_BPS_P90,
        _COL_GOAL_INVOLVEMENT,
        _COL_THREAT_INDEX,
    ]

    def apply(self, data: pd.DataFrame) -> tuple[pd.DataFrame, FeatureStepSummary]:
        """Derive attacking contribution features.

        Args:
            data: The DataFrame to derive features from.

        Returns:
            tuple[pd.DataFrame, FeatureStepSummary]: Data with new attacking features.
        """
        rows_before = len(data)
        working = data.copy()

        # Check required columns
        required = [
            self._threat_col,
            self._creativity_col,
            self._bps_col,
            self._minutes_col,
            self._goals_col,
            self._assists_col,
            self._team_attack_col,
        ]
        missing = [c for c in required if c not in working.columns]
        if missing:
            logger.warning(
                "Attacking contribution step: missing prerequisite column(s) %s.",
                missing,
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

        # Minutes-normalized metrics: (stat / max(minutes, 1.0)) * 90
        # If minutes is NaN, result is NaN. If minutes == 0, output is 0.0.
        minutes = pd.to_numeric(working[self._minutes_col], errors="coerce")
        threat = pd.to_numeric(working[self._threat_col], errors="coerce")
        creativity = pd.to_numeric(working[self._creativity_col], errors="coerce")
        bps = pd.to_numeric(working[self._bps_col], errors="coerce")
        goals = pd.to_numeric(working[self._goals_col], errors="coerce")
        assists = pd.to_numeric(working[self._assists_col], errors="coerce")
        team_atk = pd.to_numeric(working[self._team_attack_col], errors="coerce")

        # Per 90 normalization (only when minutes > 0)
        valid_min = minutes.clip(lower=1.0)
        has_min = minutes > 0

        working[self._COL_THREAT_P90] = np.where(
            minutes.isna(),
            np.nan,
            np.where(has_min, (threat / valid_min) * 90.0, 0.0),
        )
        working[self._COL_CREATIVITY_P90] = np.where(
            minutes.isna(),
            np.nan,
            np.where(has_min, (creativity / valid_min) * 90.0, 0.0),
        )
        working[self._COL_BPS_P90] = np.where(
            minutes.isna(),
            np.nan,
            np.where(has_min, (bps / valid_min) * 90.0, 0.0),
        )

        # Goal involvement rate: (goals + assists) / max(team_attack_strength, 0.1)
        valid_team_atk = team_atk.clip(lower=0.1)
        combined_gi = goals.fillna(0.0) + assists.fillna(0.0)
        working[self._COL_GOAL_INVOLVEMENT] = np.where(
            team_atk.isna(),
            np.nan,
            combined_gi / valid_team_atk,
        )

        # Composite attacking threat index: 0.6 * threat_p90 + 0.4 * creativity_p90
        threat_p90 = pd.to_numeric(working[self._COL_THREAT_P90], errors="coerce")
        creat_p90 = pd.to_numeric(working[self._COL_CREATIVITY_P90], errors="coerce")
        working[self._COL_THREAT_INDEX] = (threat_p90.fillna(0.0) * 0.6) + (
            creat_p90.fillna(0.0) * 0.4
        )

        working.index = data.index
        description = f"Added {len(self._OUTPUT_COLUMNS)} attacking contribution column(s)."
        logger.info(description)

        return working, FeatureStepSummary(
            step_name=self.name,
            rows_before=rows_before,
            rows_after=len(working),
            columns_added=list(self._OUTPUT_COLUMNS),
            description=description,
        )
