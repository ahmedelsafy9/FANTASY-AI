"""Feature step deriving underlying-opportunity signals (chances, not just outcomes).

Reduces dependence on noisy realized outcomes (goals/assists/points)
by giving the model per-90 rates of the *chances* a player is getting:
xG, xA, key passes, and big chances created/missed. Every input here
is already a strictly-lagged rolling average produced upstream by
:class:`~src.feature_engineering.steps.rolling_stats.RollingAverageStep`
(itself built via ``groupby(player).shift(1).rolling(...)``), so this
step only does leakage-safe arithmetic on already-safe columns.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from src.config.logging_config import get_logger
from src.feature_engineering.models import FeatureStepSummary
from src.feature_engineering.steps.base import FeatureStep

logger = get_logger(__name__)


class OpportunityStep(FeatureStep):
    """Derives per-90 underlying-opportunity rates and a composite opportunity index.

    Produces:
    - ``xG_per_90_last_5``: ``(xG_avg_last_5 / max(minutes_avg_last_5, 1)) * 90``.
    - ``xA_per_90_last_5``: Same, for xA.
    - ``key_passes_per_90_last_5``: Same, for key passes (chance creation
      that doesn't require a shot).
    - ``big_chances_created_per_90_last_5``: Same, for big chances created.
    - ``big_chances_missed_rate_last_5``: ``big_chances_missed_avg_last_5 /
      max(big_chances_created_avg_last_5, 0.1)``. Finishing-quality /
      wastefulness proxy among a player's own big chances.
    - ``xGI_per_90_last_5``: ``xG_per_90_last_5 + xA_per_90_last_5``.
      Combined expected goal involvement rate.
    - ``opportunity_index_last_5``: ``0.4 * xG_per_90_last_5 +
      0.3 * xA_per_90_last_5 + 0.3 * key_passes_per_90_last_5``. A
      single composite "how many good chances is this player
      generating per 90" signal; weights are a documented, fixed
      heuristic (xG weighted highest since it is the most direct proxy
      for a goalscoring chance), not fitted/tuned against the target.

    Args:
        xg_col: Prior rolling xG column (e.g. ``xG_avg_last_5``).
        xa_col: Prior rolling xA column (e.g. ``xA_avg_last_5``).
        minutes_col: Prior rolling minutes column (e.g. ``minutes_avg_last_5``).
        key_passes_col: Prior rolling key-passes column.
        big_chances_created_col: Prior rolling big-chances-created column.
        big_chances_missed_col: Prior rolling big-chances-missed column.
    """

    def __init__(
        self,
        xg_col: str = "xG_avg_last_5",
        xa_col: str = "xA_avg_last_5",
        minutes_col: str = "minutes_avg_last_5",
        key_passes_col: str = "key_passes_avg_last_5",
        big_chances_created_col: str = "big_chances_created_avg_last_5",
        big_chances_missed_col: str = "big_chances_missed_avg_last_5",
    ) -> None:
        self._xg_col = xg_col
        self._xa_col = xa_col
        self._minutes_col = minutes_col
        self._key_passes_col = key_passes_col
        self._big_chances_created_col = big_chances_created_col
        self._big_chances_missed_col = big_chances_missed_col

    @property
    def name(self) -> str:
        """A short, human-readable identifier for this step."""
        return "opportunity"

    _COL_XG_P90 = "xG_per_90_last_5"
    _COL_XA_P90 = "xA_per_90_last_5"
    _COL_KP_P90 = "key_passes_per_90_last_5"
    _COL_BCC_P90 = "big_chances_created_per_90_last_5"
    _COL_BCM_RATE = "big_chances_missed_rate_last_5"
    _COL_XGI_P90 = "xGI_per_90_last_5"
    _COL_OPP_INDEX = "opportunity_index_last_5"

    _OUTPUT_COLUMNS = [
        _COL_XG_P90,
        _COL_XA_P90,
        _COL_KP_P90,
        _COL_BCC_P90,
        _COL_BCM_RATE,
        _COL_XGI_P90,
        _COL_OPP_INDEX,
    ]

    def _per_90(self, numerator: pd.Series, minutes: pd.Series) -> pd.Series:
        """(numerator / max(minutes, 1)) * 90, NaN-propagating, 0 when minutes == 0."""
        valid_min = minutes.clip(lower=1.0)
        has_min = minutes > 0
        return pd.Series(
            np.where(
                minutes.isna() | numerator.isna(),
                np.nan,
                np.where(has_min, (numerator / valid_min) * 90.0, 0.0),
            ),
            index=numerator.index,
        )

    def apply(self, data: pd.DataFrame) -> tuple[pd.DataFrame, FeatureStepSummary]:
        """Derive underlying-opportunity features.

        Args:
            data: The DataFrame to derive features from.

        Returns:
            tuple[pd.DataFrame, FeatureStepSummary]: Data with new opportunity features.
        """
        rows_before = len(data)
        working = data.copy()

        required = [
            self._xg_col,
            self._xa_col,
            self._minutes_col,
            self._key_passes_col,
            self._big_chances_created_col,
            self._big_chances_missed_col,
        ]
        missing = [c for c in required if c not in working.columns]
        if missing:
            logger.warning("Opportunity step: missing prerequisite column(s) %s.", missing)
            for col in self._OUTPUT_COLUMNS:
                working[col] = pd.NA
            return working, FeatureStepSummary(
                step_name=self.name,
                rows_before=rows_before,
                rows_after=len(working),
                columns_added=list(self._OUTPUT_COLUMNS),
                description=f"Missing prerequisite column(s) {missing}; outputs are NaN.",
            )

        minutes = pd.to_numeric(working[self._minutes_col], errors="coerce")
        xg = pd.to_numeric(working[self._xg_col], errors="coerce")
        xa = pd.to_numeric(working[self._xa_col], errors="coerce")
        key_passes = pd.to_numeric(working[self._key_passes_col], errors="coerce")
        bcc = pd.to_numeric(working[self._big_chances_created_col], errors="coerce")
        bcm = pd.to_numeric(working[self._big_chances_missed_col], errors="coerce")

        working[self._COL_XG_P90] = self._per_90(xg, minutes)
        working[self._COL_XA_P90] = self._per_90(xa, minutes)
        working[self._COL_KP_P90] = self._per_90(key_passes, minutes)
        working[self._COL_BCC_P90] = self._per_90(bcc, minutes)

        valid_bcc = bcc.clip(lower=0.1)
        working[self._COL_BCM_RATE] = np.where(bcc.isna() | bcm.isna(), np.nan, bcm / valid_bcc)

        xg_p90 = pd.to_numeric(working[self._COL_XG_P90], errors="coerce")
        xa_p90 = pd.to_numeric(working[self._COL_XA_P90], errors="coerce")
        kp_p90 = pd.to_numeric(working[self._COL_KP_P90], errors="coerce")

        working[self._COL_XGI_P90] = xg_p90.fillna(0.0) + xa_p90.fillna(0.0)
        working[self._COL_OPP_INDEX] = (
            0.4 * xg_p90.fillna(0.0) + 0.3 * xa_p90.fillna(0.0) + 0.3 * kp_p90.fillna(0.0)
        )

        working.index = data.index
        description = f"Added {len(self._OUTPUT_COLUMNS)} opportunity column(s)."
        logger.info(description)

        return working, FeatureStepSummary(
            step_name=self.name,
            rows_before=rows_before,
            rows_after=len(working),
            columns_added=list(self._OUTPUT_COLUMNS),
            description=description,
        )
