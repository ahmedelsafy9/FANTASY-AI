"""Feature step deriving expected-minutes, rotation-risk, and workload signals.

Answers the question an expert FPL manager asks before every deadline:
"Will this player actually play, and for how long?" Every output uses
only strictly prior matches (``groupby(player).shift(1)`` before any
rolling/streak/window computation) - see each column's docstring for
its exact formula and temporal availability.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from src.config.logging_config import get_logger
from src.feature_engineering.models import FeatureStepSummary
from src.feature_engineering.steps._common import chronological_sort_key, resolve_column
from src.feature_engineering.steps.base import FeatureStep

logger = get_logger(__name__)


def _consecutive_streak(condition: pd.Series, group_keys: Any) -> pd.Series:
    """Length of the current run of consecutive True values, per group.

    ``condition`` must already be shifted (i.e. represent prior matches
    only). For each row, returns how many consecutive prior matches
    (ending at the most recent one) satisfied the condition. Resets to
    0 the match after the condition breaks.
    """
    cond = condition.astype("float")
    is_false = (cond == 0.0) | cond.isna()
    block_id = is_false.groupby(group_keys).cumsum()
    if isinstance(group_keys, list):
        streak = cond.groupby([*group_keys, block_id]).cumsum()
    else:
        streak = cond.groupby([group_keys, block_id]).cumsum()
    streak = streak.where(cond == 1.0, 0.0)
    return streak.fillna(0.0)


class ExpectedMinutesStep(FeatureStep):
    """Derives expected-minutes, rotation-risk, and recent-workload features.

    All features are computed from ``shift(1)`` minutes/starts series
    (grouped by player, sorted chronologically), so every value at row
    t reflects only matches strictly before t.

    Produces:
    - minutes_std_last_5: Std. dev. of the last 5 prior matches'
      minutes. Volatility of playing time.
    - minutes_share_last_5: rolling-mean prior minutes / 90. Share of
      a full match a player has recently been getting.
    - rotation_risk_index: minutes_std_last_5 / (minutes_mean_last_5 + 1).
      Coefficient-of-variation style index; higher means less
      predictable game time, independent of the average minutes level.
    - consecutive_starts: Length of the current run of consecutive
      prior starts.
    - consecutive_60_plus: Length of the current run of consecutive
      prior appearances with >= 60 minutes.
    - consecutive_90s: Length of the current run of consecutive prior
      appearances with >= 89 minutes (allows for stoppage time).
    - minutes_prev_7d / matches_prev_7d: Total minutes / match count
      in the 7 days strictly before this match's kickoff.
    - minutes_prev_14d / matches_prev_14d: Same, over 14 days.
    - expected_minutes: An exponentially-weighted moving average
      (halflife configurable, default 3 matches) of prior minutes.
      A smoother, faster-adapting alternative to a flat rolling mean.
      This is a documented point ESTIMATE, not a calibrated
      probability of starting - no probability is invented here.

    Args:
        player_id_columns: Candidate columns identifying a player.
        chronological_columns: Candidate columns defining match order.
        minutes_columns: Candidate column names for minutes played.
        starts_columns: Candidate column names for starts.
        kickoff_time_column: Column with match kickoff timestamps.
        expected_minutes_halflife: Halflife (in matches) for the EWMA
            underlying expected_minutes.
    """

    def __init__(
        self,
        player_id_columns: tuple[str, ...],
        chronological_columns: tuple[str, ...],
        minutes_columns: tuple[str, ...] = ("minutes",),
        starts_columns: tuple[str, ...] = ("starts",),
        kickoff_time_column: str = "kickoff_time",
        expected_minutes_halflife: float = 3.0,
    ) -> None:
        self._player_id_columns = player_id_columns
        self._chronological_columns = chronological_columns
        self._minutes_columns = minutes_columns
        self._starts_columns = starts_columns
        self._kickoff_time_column = kickoff_time_column
        self._expected_minutes_halflife = expected_minutes_halflife

    @property
    def name(self) -> str:
        """A short, human-readable identifier for this step."""
        return "expected_minutes"

    _OUTPUT_COLUMNS = [
        "minutes_std_last_5",
        "minutes_share_last_5",
        "rotation_risk_index",
        "consecutive_starts",
        "consecutive_60_plus",
        "consecutive_90s",
        "minutes_prev_7d",
        "matches_prev_7d",
        "minutes_prev_14d",
        "matches_prev_14d",
        "expected_minutes",
    ]

    def apply(self, data: pd.DataFrame) -> tuple[pd.DataFrame, FeatureStepSummary]:
        """Compute expected-minutes and rotation-risk features."""
        rows_before = len(data)
        player_id_column = resolve_column(self._player_id_columns, data)
        sort_columns = chronological_sort_key(data, self._chronological_columns)
        minutes_col = resolve_column(self._minutes_columns, data)
        starts_col = resolve_column(self._starts_columns, data)

        if player_id_column is None or minutes_col is None:
            logger.warning(
                "Missing player_id (%s) or minutes column (%s); filling expected_minutes "
                "features with NaN.",
                player_id_column,
                minutes_col,
            )
            working = data.copy()
            for col in self._OUTPUT_COLUMNS:
                working[col] = pd.NA
            return working, FeatureStepSummary(
                step_name=self.name,
                rows_before=rows_before,
                rows_after=len(working),
                columns_added=list(self._OUTPUT_COLUMNS),
                description="Required columns missing; filled all expected_minutes outputs with NaN.",
            )

        working = data.copy()
        working["__original_order__"] = range(len(working))
        sort_by = [player_id_column, *sort_columns]
        working = working.sort_values(by=sort_by, kind="mergesort")

        season_col = resolve_column(("season",), working)
        group_keys = (
            [working[season_col], working[player_id_column]]
            if season_col is not None
            else working[player_id_column]
        )
        minutes_series = pd.to_numeric(working[minutes_col], errors="coerce").fillna(0.0)

        if starts_col is not None and starts_col in working.columns:
            raw_starts = pd.to_numeric(working[starts_col], errors="coerce")
            inferred_starts = (minutes_series >= 60).astype(float)
            starts_series = (raw_starts.fillna(inferred_starts) > 0).astype(float)
        else:
            starts_series = (minutes_series >= 60).astype(float)

        prior_minutes = minutes_series.groupby(group_keys).shift(1)
        prior_starts = starts_series.groupby(group_keys).shift(1)
        prior_60_plus = (prior_minutes >= 60).astype(float).where(prior_minutes.notna())
        prior_90 = (prior_minutes >= 89).astype(float).where(prior_minutes.notna())

        minutes_mean_last_5 = prior_minutes.groupby(group_keys).transform(
            lambda s: s.rolling(window=5, min_periods=1).mean()
        )
        minutes_std_last_5 = prior_minutes.groupby(group_keys).transform(
            lambda s: s.rolling(window=5, min_periods=2).std()
        )
        working["minutes_std_last_5"] = minutes_std_last_5
        working["minutes_share_last_5"] = minutes_mean_last_5 / 90.0
        working["rotation_risk_index"] = minutes_std_last_5 / (minutes_mean_last_5.fillna(0.0) + 1.0)

        working["consecutive_starts"] = _consecutive_streak(prior_starts.fillna(0.0), group_keys)
        working["consecutive_60_plus"] = _consecutive_streak(prior_60_plus.fillna(0.0), group_keys)
        working["consecutive_90s"] = _consecutive_streak(prior_90.fillna(0.0), group_keys)
        no_history_mask = prior_minutes.isna()
        for col in ("consecutive_starts", "consecutive_60_plus", "consecutive_90s"):
            working.loc[no_history_mask, col] = pd.NA

        working["expected_minutes"] = prior_minutes.groupby(group_keys).transform(
            lambda s: s.ewm(halflife=self._expected_minutes_halflife, min_periods=1).mean()
        )

        time_cols = ["minutes_prev_7d", "matches_prev_7d", "minutes_prev_14d", "matches_prev_14d"]
        if self._kickoff_time_column in working.columns:
            kickoff = pd.to_datetime(working[self._kickoff_time_column], errors="coerce", utc=True)
            if kickoff.notna().any():
                for col in time_cols:
                    working[col] = np.nan
                for _, idx in working.groupby(group_keys).groups.items():
                    sub_index = idx
                    order = np.argsort(kickoff.loc[sub_index].to_numpy(), kind="mergesort")
                    sub_idx_sorted = sub_index[order]
                    times = kickoff.loc[sub_idx_sorted].to_numpy()
                    mins = minutes_series.loc[sub_idx_sorted].to_numpy()
                    n = len(times)
                    for i in range(n):
                        t = times[i]
                        if pd.isna(t):
                            continue
                        for days, mcol, gcol in (
                            (7, "minutes_prev_7d", "matches_prev_7d"),
                            (14, "minutes_prev_14d", "matches_prev_14d"),
                        ):
                            lower = t - np.timedelta64(days, "D")
                            mask = (times < t) & (times >= lower)
                            working.loc[sub_idx_sorted[i], mcol] = float(mins[mask].sum())
                            working.loc[sub_idx_sorted[i], gcol] = float(mask.sum())
            else:
                logger.warning(
                    "Kickoff time column '%s' present but unparseable; workload window "
                    "features filled with NaN.",
                    self._kickoff_time_column,
                )
                for col in time_cols:
                    working[col] = pd.NA
        else:
            logger.warning(
                "Kickoff time column '%s' not found; workload window features filled with NaN.",
                self._kickoff_time_column,
            )
            for col in time_cols:
                working[col] = pd.NA

        working = working.sort_values(by="__original_order__", kind="mergesort")
        working = working.drop(columns="__original_order__")
        working.index = data.index

        description = f"Added {len(self._OUTPUT_COLUMNS)} expected-minutes / rotation-risk column(s)."
        summary = FeatureStepSummary(
            step_name=self.name,
            rows_before=rows_before,
            rows_after=len(working),
            columns_added=list(self._OUTPUT_COLUMNS),
            description=description,
        )
        logger.info(description)
        return working, summary
